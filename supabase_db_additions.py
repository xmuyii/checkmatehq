# -*- coding: utf-8 -*-
"""
supabase_db_additions.py
========================
PASTE THESE FUNCTIONS INTO supabase_db.py

These are the functions that main.py imports from supabase_db
but that are currently missing, causing the NameError crashes.

HOW TO USE:
  Open supabase_db.py and paste each function block at the bottom
  of the file, before any __all__ or if __name__ == "__main__" lines.
"""

# ═══════════════════════════════════════════════════════════════════════════
# PASTE BLOCK 1 — Credits system
# main.py imports: claim_daily_login_credits, award_scoreboard_credits,
#                  get_credits, add_credits, spend_credits,
#                  CREDITS_TO_PLAY, CREDITS_RANK_REWARDS, CREDITS_DAILY_LOGIN
# ═══════════════════════════════════════════════════════════════════════════

CREDITS_TO_PLAY    = 10     # Credits to enter a Fusion round
CREDITS_DAILY_LOGIN = 50   # Credits from daily login
CREDITS_RANK_REWARDS = {    # Credits awarded by leaderboard rank
    1: 50, 2: 45, 3: 30,
    4: 20, 5: 10,
    6: 5,  7: 5,  8: 5, 9: 5, 10: 5,
}


def get_credits(user_id: str) -> int:
    """Get a player's current credit balance."""
    from supabase_db import get_user as _get_user
    user = _get_user(str(user_id))
    if not user:
        return 0
    return int(user.get("credits", 0) or 0)


def add_credits(user_id: str, amount: int) -> int:
    """Add credits to a player. Returns new balance."""
    from supabase_db import get_user as _get_user, save_user as _save_user
    user = _get_user(str(user_id))
    if not user:
        return 0
    current = int(user.get("credits", 0) or 0)
    new_bal = current + amount
    _save_user(str(user_id), {**user, "credits": new_bal})
    return new_bal


def spend_credits(user_id: str, amount: int) -> tuple:
    """
    Spend credits. Returns (success: bool, new_balance: int).
    Fails if player doesn't have enough.
    """
    from supabase_db import get_user as _get_user, save_user as _save_user
    user = _get_user(str(user_id))
    if not user:
        return False, 0
    current = int(user.get("credits", 0) or 0)
    if current < amount:
        return False, current
    new_bal = current - amount
    _save_user(str(user_id), {**user, "credits": new_bal})
    return True, new_bal


def claim_daily_login_credits(user_id: str) -> tuple:
    """
    Claim daily login credits. Returns (awarded: bool, amount: int, new_balance: int).
    Can only be claimed once per UTC day.
    """
    from datetime import datetime
    from supabase_db import get_user as _get_user, save_user as _save_user
    user = _get_user(str(user_id))
    if not user:
        return False, 0, 0

    today      = datetime.utcnow().strftime("%Y-%m-%d")
    last_claim = user.get("last_daily_credit_claim", "")

    if last_claim == today:
        return False, 0, int(user.get("credits", 0) or 0)

    amount  = CREDITS_DAILY_LOGIN
    current = int(user.get("credits", 0) or 0)
    new_bal = current + amount

    _save_user(str(user_id), {
        **user,
        "credits":                 new_bal,
        "last_daily_credit_claim": today,
    })
    return True, amount, new_bal


def award_scoreboard_credits(user_id: str, rank: int) -> int:
    """
    Award credits based on leaderboard rank. Returns amount awarded.
    Called at end of each round for top 10 players.
    """
    amount = CREDITS_RANK_REWARDS.get(rank, 0)
    if amount > 0:
        add_credits(str(user_id), amount)
    return amount


# ═══════════════════════════════════════════════════════════════════════════
# PASTE BLOCK 2 — Teleport grant (replaces the broken version)
# main.py imports: grant_free_teleports_to_all
# ═══════════════════════════════════════════════════════════════════════════

def grant_free_teleports_to_all() -> int:
    """
    Grant 3 free teleport charges to all players who haven't claimed today.
    Uses the teleport_charges integer column — never touches inventory.
    Returns count of players granted.
    Safe to call synchronously at startup.
    """
    from datetime import datetime
    today   = datetime.utcnow().strftime("%Y-%m-%d")
    granted = 0

    try:
        result = supabase.table(DB_TABLE).select(
            "user_id, teleport_charges, teleport_daily_claimed_date"
        ).execute()

        users = result.data or []

        for user in users:
            try:
                uid = user.get("user_id")
                if not uid:
                    continue
                if user.get("teleport_daily_claimed_date") == today:
                    continue

                current = int(user.get("teleport_charges") or 0)
                supabase.table(DB_TABLE).update({
                    "teleport_charges":             current + 3,
                    "teleport_daily_claimed_date":  today,
                }).eq("user_id", uid).execute()
                granted += 1

            except Exception as e:
                print(f"[WARN] Could not grant teleports to {user.get('user_id','?')}: {e}")

        print(f"[TELEPORTS] Granted 3 charges to {granted} players")

    except Exception as e:
        print(f"[ERROR] grant_free_teleports_to_all: {e}")

    return granted


# ═══════════════════════════════════════════════════════════════════════════
# PASTE BLOCK 3 — safe_json and normalize_user (fixes the append crash)
# ═══════════════════════════════════════════════════════════════════════════

import json as _json

def safe_json(value, default=None):
    """
    Safely parse a value that might be a JSON string or already parsed.
    Prevents 'str object has no attribute append/get/keys' errors.
    """
    if default is None:
        default = {}
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value or value in ('null', 'None', ''):
            return default
        try:
            return _json.loads(value)
        except Exception:
            return default
    return default


def normalize_user(user: dict) -> dict:
    """
    Normalize all JSON fields on a user dict from Supabase.
    Call at the top of get_user() before returning.
    """
    if not user:
        return user

    dict_fields = [
        "inventory", "military", "buildings", "building_queue",
        "researches", "research_queue", "base_resources", "traps",
        "weapons", "buffs", "banishments", "visas", "visa_applications",
        "commander_location", "current_node", "active_suit",
        "skill_points_spent", "dominance_scores",
    ]
    for field in dict_fields:
        user[field] = safe_json(user.get(field), default={})

    list_fields = [
        "unclaimed_items", "march_queue", "eject_log",
        "teleport_history", "visa_queue",
    ]
    for field in list_fields:
        user[field] = safe_json(user.get(field), default=[])

    if not user.get("commander_location"):
        user["commander_location"] = {"sector_id": 1}
    if not isinstance(user.get("base_resources"), dict):
        user["base_resources"] = {"resources": {}, "food": 0, "current_streak": 0}
    if not isinstance(user["base_resources"].get("resources"), dict):
        user["base_resources"]["resources"] = {}
    if user.get("credits") is None:
        user["credits"] = 0

    return user
