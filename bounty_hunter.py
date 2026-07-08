# -*- coding: utf-8 -*-
"""
bounty_hunter.py — Bounty Hunter Career System
================================================
A dedicated player career path with unique mechanics unavailable
to regular commanders. Bounty hunters are the game's assassins —
they track, pursue, and eliminate high-value targets for gold rewards.

CAREER ACTIVATION:
  Any player can activate the Bounty Hunter career from their profile.
  It costs 500 gold and is a permanent role addition (not a replacement).
  You keep your base, troops, alliance — you just gain hunter abilities.

HUNTER ABILITIES (unlocked by hunter XP, not skill points):
  Tier 1 — Tracker:      See targets' last known sector on bounty board
  Tier 2 — Shadow:       Teleport to a target's sector costs 0 charges (once per day)
  Tier 3 — Infiltrator:  Can scout targets in adjacent sectors without going there
  Tier 4 — Ghost:        Arrival in a sector not logged for 10 minutes
  Tier 5 — Assassin:     First strike in any battle with a bounty target +30% power

HUNTER XP:
  Earned only by completing bounties. Each kill earns hunter XP.
  Hunter XP is separate from commander XP — it tracks hunter career only.

BOUNTY BOARD:
  Players appear automatically when:
    - Unshielded 4+ hours
    - Bitcoin balance above 0.01 BTC (Whale tag)
    - Sector Ruler (always visible)
    - Manual bounty placed by another player
  Players can be removed by: buying their way off (500 gold), shielding up,
  or if they are a ruler — only by losing the throne.

KILL CONFIRMATION:
  To claim a bounty, the hunter must:
    1. Be in the same sector as the target
    2. Win a battle against them (node or roaming duel)
    3. Call !claim [bounty_id] within 5 minutes of the kill
  The system verifies the battle log before paying out.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ═══════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

CAREER_ACTIVATION_COST  = 500    # Gold to become a bounty hunter
BOUNTY_MIN_REWARD        = 50    # Minimum gold for a placed bounty
BOUNTY_MAX_REWARD        = 5000  # Maximum gold for a placed bounty
BOUNTY_DURATION_HOURS    = 48    # Bounties expire after 48h
CLAIM_WINDOW_MINUTES     = 5     # Minutes after kill to claim bounty
SHIELD_DOWN_HOURS        = 4     # Hours unshielded before appearing on board
BITCOIN_WHALE_THRESHOLD  = 0.01  # BTC above this = Whale tag

# Hunter tier XP thresholds
HUNTER_TIERS = {
    1: {"name": "Tracker",     "emoji": "🔭", "xp_required": 0,    "description": "See targets' last known sector on bounty board."},
    2: {"name": "Shadow",      "emoji": "🌑", "xp_required": 100,  "description": "Once per day: teleport to a target's sector free."},
    3: {"name": "Infiltrator", "emoji": "🕵️", "xp_required": 300,  "description": "Scout bounty targets in adjacent sectors remotely."},
    4: {"name": "Ghost",       "emoji": "👻", "xp_required": 600,  "description": "Arrival in a sector not logged for 10 minutes."},
    5: {"name": "Assassin",    "emoji": "💀", "xp_required": 1000, "description": "First strike vs bounty targets: +30% attack power."},
}

HUNTER_XP_PER_KILL = {
    "D": 10,   # Low-value bounty
    "C": 25,
    "B": 50,
    "A": 100,
    "S": 200,  # High-value target
}

# Bounty rank determined by target's power tier
BOUNTY_RANKS = {
    "Novice":    "D",
    "Recruit":   "D",
    "Soldier":   "C",
    "Commander": "B",
    "Warlord":   "A",
    "Emperor":   "S",
    "Immortal":  "S",
    "Ascendant": "S",
}


# ═══════════════════════════════════════════════════════════════════════════
#  CAREER MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

def is_bounty_hunter(user: dict) -> bool:
    """Check if a player has activated the Bounty Hunter career."""
    return bool(user.get("is_bounty_hunter", False))


def activate_hunter_career(user: dict) -> Tuple[bool, str, dict]:
    """
    Activate the Bounty Hunter career for a player.
    Costs CAREER_ACTIVATION_COST gold.
    Returns (success, message, updated_user)
    """
    if is_bounty_hunter(user):
        return False, "✅ You are already a Bounty Hunter.", user

    inv  = user.get("inventory", {}) or {}
    gold = inv.get("gold", {}).get("qty", 0) if isinstance(inv, dict) else 0

    if gold < CAREER_ACTIVATION_COST:
        return False, (
            f"❌ Bounty Hunter career costs {CAREER_ACTIVATION_COST} 🪙.\n"
            f"You have {gold} 🪙."
        ), user

    # Deduct gold
    inv["gold"]["qty"] = gold - CAREER_ACTIVATION_COST
    user["inventory"]  = inv

    # Activate career
    user["is_bounty_hunter"]    = True
    user["hunter_xp"]           = 0
    user["hunter_tier"]         = 1
    user["hunter_kills"]        = 0
    user["hunter_earnings"]     = 0
    user["hunter_activated_at"] = datetime.utcnow().isoformat()
    user["hunter_free_teleport_used_date"] = None

    return True, (
        f"💀 *BOUNTY HUNTER CAREER ACTIVATED*\n\n"
        f"You are now a Tier 1 Tracker.\n"
        f"Find targets on the Bounty Board.\n"
        f"Kill them. Collect the reward.\n\n"
        f"Hunter XP is earned through kills only.\n"
        f"Advance through 5 tiers to become an Assassin."
    ), user


def get_hunter_tier(user: dict) -> int:
    """Get the player's current hunter tier (1-5)."""
    if not is_bounty_hunter(user):
        return 0
    xp     = user.get("hunter_xp", 0)
    tier   = 1
    for t, data in HUNTER_TIERS.items():
        if xp >= data["xp_required"]:
            tier = t
    return tier


def get_hunter_tier_data(user: dict) -> dict:
    """Get full tier data for the player's current hunter tier."""
    tier = get_hunter_tier(user)
    return HUNTER_TIERS.get(tier, HUNTER_TIERS[1])


def award_hunter_xp(user: dict, bounty_rank: str) -> Tuple[dict, bool, Optional[str]]:
    """
    Award hunter XP after a successful kill.
    Returns (updated_user, tier_up: bool, tier_up_message)
    """
    if not is_bounty_hunter(user):
        return user, False, None

    xp_gain      = HUNTER_XP_PER_KILL.get(bounty_rank, 10)
    old_tier     = get_hunter_tier(user)
    user["hunter_xp"] = user.get("hunter_xp", 0) + xp_gain
    new_tier     = get_hunter_tier(user)
    user["hunter_tier"] = new_tier

    if new_tier > old_tier:
        tier_data = HUNTER_TIERS[new_tier]
        msg = (
            f"⬆️ *HUNTER TIER UP!*\n"
            f"{tier_data['emoji']} You are now a *{tier_data['name']}*\n"
            f"New ability: {tier_data['description']}"
        )
        return user, True, msg

    return user, False, None


def has_hunter_ability(user: dict, ability_tier: int) -> bool:
    """Check if player has unlocked a specific hunter ability."""
    if not is_bounty_hunter(user):
        return False
    return get_hunter_tier(user) >= ability_tier


def use_free_hunter_teleport(user: dict) -> Tuple[bool, str, dict]:
    """
    Tier 2 ability: free teleport to a target's sector once per day.
    Returns (success, message, updated_user)
    """
    if not has_hunter_ability(user, 2):
        return False, "🔒 Requires Hunter Tier 2 (Shadow).", user

    today      = datetime.utcnow().strftime("%Y-%m-%d")
    last_used  = user.get("hunter_free_teleport_used_date", "")

    if last_used == today:
        return False, "❌ Free hunter teleport already used today. Resets at midnight UTC.", user

    user["hunter_free_teleport_used_date"] = today
    return True, "🌑 *Shadow Teleport activated.* This teleport costs no charges.", user


# ═══════════════════════════════════════════════════════════════════════════
#  BOUNTY BOARD
# ═══════════════════════════════════════════════════════════════════════════

def should_appear_on_board(user: dict) -> Tuple[bool, str]:
    """
    Determine if a player should appear on the bounty board automatically.
    Returns (should_appear, reason_key)
    """
    from datetime import datetime

    # Sector Ruler — always visible
    dominance = user.get("dominance_scores", {})
    if isinstance(dominance, dict) and dominance:
        pass  # Ruler status checked separately via sector_state

    # Bitcoin Whale
    inv = user.get("inventory", {})
    if isinstance(inv, dict):
        btc = inv.get("bitcoin", {})
        if isinstance(btc, dict) and btc.get("qty", 0) >= BITCOIN_WHALE_THRESHOLD:
            return True, "bitcoin_whale"

    # Unshielded too long
    shielded    = user.get("base_shielded", False)
    shield_exp  = user.get("shield_expires_at", "")
    if not shielded:
        return True, "unshielded"
    if shield_exp:
        try:
            exp  = datetime.fromisoformat(shield_exp)
            now  = datetime.utcnow()
            if now > exp:
                hours_down = (now - exp).total_seconds() / 3600
                if hours_down >= SHIELD_DOWN_HOURS:
                    return True, f"unshielded_{int(hours_down)}h"
        except Exception:
            pass

    return False, ""


def place_bounty(
    poster_user: dict,
    target_id: str,
    target_name: str,
    target_home_sector: Optional[int],
    reward_gold: int,
    reason: str,
    supabase,
    DB_TABLE: str = "players",
) -> Tuple[bool, str, dict]:
    """
    Player manually places a bounty. Deducts gold. Reveals target's home sector.
    Returns (success, message, updated_poster)
    """
    reward_gold = max(BOUNTY_MIN_REWARD, min(BOUNTY_MAX_REWARD, reward_gold))

    inv   = poster_user.get("inventory", {}) or {}
    gold  = inv.get("gold", {}).get("qty", 0) if isinstance(inv, dict) else 0

    if gold < reward_gold:
        return False, f"❌ Not enough gold. Have {gold} 🪙, need {reward_gold} 🪙.", poster_user

    # Deduct gold
    if isinstance(inv, dict) and "gold" in inv:
        inv["gold"]["qty"] = gold - reward_gold
    poster_user["inventory"] = inv

    # Determine rank from target's power
    try:
        from power_system_v2 import get_power_tier, get_total_power
        target_user = supabase.table(DB_TABLE).select("*").eq(
            "user_id", target_id
        ).execute()
        if target_user.data:
            from supabase_db import normalize_user
            tu    = normalize_user(target_user.data[0])
            power = get_total_power(tu)
            tier  = get_power_tier(power)
            # Extract tier name from emoji string like "🟣 Commander"
            tier_name = tier.split(" ")[-1] if " " in tier else "Soldier"
            rank  = BOUNTY_RANKS.get(tier_name, "C")
        else:
            rank = "C"
    except Exception:
        rank = "C"

    bounty_id  = f"bnty_{int(datetime.utcnow().timestamp())}_{target_id[-4:]}"
    expires_at = (datetime.utcnow() + timedelta(hours=BOUNTY_DURATION_HOURS)).isoformat()

    try:
        supabase.table("bounty_board").insert({
            "bounty_id":          bounty_id,
            "target_id":          target_id,
            "target_name":        target_name,
            "target_home_sector": target_home_sector,
            "posted_by_id":       poster_user.get("user_id"),
            "posted_by_name":     poster_user.get("username", "Unknown"),
            "reward_gold":        reward_gold,
            "reason":             reason,
            "rank":               rank,
            "posted_at":          datetime.utcnow().isoformat(),
            "expires_at":         expires_at,
            "status":             "active",
        }).execute()
    except Exception as e:
        return False, f"❌ Could not post bounty: {e}", poster_user

    return True, (
        f"🎯 *Bounty posted on @{target_name}!*\n"
        f"Reward: {reward_gold} 🪙  |  Rank: {rank}\n"
        f"Reason: {reason}\n"
        f"Expires in: {BOUNTY_DURATION_HOURS}h"
        + (f"\n🏠 Home sector revealed to hunters." if target_home_sector else "")
    ), poster_user


def claim_bounty(
    hunter_user: dict,
    bounty_id: str,
    target_id: str,
    supabase,
    DB_TABLE: str = "players",
    save_user_fn=None,
) -> Tuple[bool, str, dict]:
    """
    Hunter claims a bounty after defeating the target.
    Verifies kill is recent (within CLAIM_WINDOW_MINUTES).
    Awards gold + hunter XP.
    Returns (success, message, updated_hunter)
    """
    if not is_bounty_hunter(hunter_user):
        return False, (
            "❌ You need to be a Bounty Hunter to claim bounties.\n"
            "Activate from your Profile → Career."
        ), hunter_user

    hunter_id = hunter_user.get("user_id", "")

    # Load bounty
    try:
        r = supabase.table("bounty_board").select("*").eq(
            "bounty_id", bounty_id
        ).execute()
        if not r.data:
            return False, "❌ Bounty not found or already claimed.", hunter_user
        bounty = r.data[0]
    except Exception as e:
        return False, f"❌ Error loading bounty: {e}", hunter_user

    if bounty.get("status") != "active":
        return False, "❌ This bounty is no longer active.", hunter_user

    if bounty.get("target_id") != target_id:
        return False, "❌ Target mismatch.", hunter_user

    # Verify kill recency — check battle log
    # Battle log stores timestamp of last battle between these two players
    recent_kill = _verify_recent_kill(hunter_id, target_id, supabase, DB_TABLE)
    if not recent_kill:
        return False, (
            f"❌ No recent kill confirmed.\n"
            f"You must defeat @{bounty.get('target_name','target')} "
            f"within {CLAIM_WINDOW_MINUTES} minutes of claiming."
        ), hunter_user

    # Award gold
    reward     = bounty.get("reward_gold", 0)
    rank       = bounty.get("rank", "C")
    inv        = hunter_user.get("inventory", {}) or {}
    if "gold" in inv and isinstance(inv.get("gold"), dict):
        inv["gold"]["qty"] = inv["gold"].get("qty", 0) + reward
    else:
        inv["gold"] = {"qty": reward, "display": "Gold",
                       "emoji": "🪙", "category": "premium"}
    hunter_user["inventory"] = inv

    # Award hunter XP
    hunter_user["hunter_kills"]    = hunter_user.get("hunter_kills", 0) + 1
    hunter_user["hunter_earnings"] = hunter_user.get("hunter_earnings", 0) + reward
    hunter_user, tier_up, tier_msg = award_hunter_xp(hunter_user, rank)

    # Mark bounty claimed
    try:
        supabase.table("bounty_board").update({
            "status":       "claimed",
            "claimed_by_id": hunter_id,
            "claimed_by_name": hunter_user.get("username", "Hunter"),
            "claimed_at":   datetime.utcnow().isoformat(),
        }).eq("bounty_id", bounty_id).execute()
    except Exception:
        pass

    # Notify target
    target_notif = (
        f"🎯 *BOUNTY CLAIMED ON YOU*\n"
        f"@{hunter_user.get('username','Hunter')} collected a bounty after defeating you.\n"
        f"Reward they received: {reward} 🪙"
    )
    if save_user_fn:
        try:
            target = save_user_fn(target_id, None)
            if target:
                target["pending_notification"] = target_notif
                save_user_fn(target_id, target)
        except Exception:
            pass

    result_msg = (
        f"🎯 *BOUNTY CLAIMED!*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Target: @{bounty.get('target_name','?')}\n"
        f"Reward: +{reward} 🪙\n"
        f"Hunter XP: +{HUNTER_XP_PER_KILL.get(rank, 10)}\n"
        f"Total kills: {hunter_user['hunter_kills']}\n"
        f"Career earnings: {hunter_user['hunter_earnings']} 🪙"
    )

    if tier_up and tier_msg:
        result_msg += f"\n\n{tier_msg}"

    return True, result_msg, hunter_user


def remove_self_from_board(
    user: dict,
    supabase,
    DB_TABLE: str = "players",
) -> Tuple[bool, str, dict]:
    """
    Player pays to remove themselves from the bounty board.
    Cannot remove if they are a Sector Ruler.
    """
    REMOVAL_COST = 500
    inv  = user.get("inventory", {}) or {}
    gold = inv.get("gold", {}).get("qty", 0) if isinstance(inv, dict) else 0

    if gold < REMOVAL_COST:
        return False, (
            f"❌ Costs {REMOVAL_COST} 🪙 to remove yourself from the board.\n"
            f"You have {gold} 🪙."
        ), user

    inv["gold"]["qty"] = gold - REMOVAL_COST
    user["inventory"]  = inv

    # Expire all active bounties on this player
    try:
        supabase.table("bounty_board").update({
            "status": "expired"
        }).eq("target_id", user.get("user_id")).eq("status", "active").execute()
    except Exception:
        pass

    # Set a cooldown so they don't immediately reappear
    user["board_removal_expires"] = (
        datetime.utcnow() + timedelta(hours=24)
    ).isoformat()

    return True, (
        f"✅ Removed from bounty board for 24 hours.\n"
        f"Cost: {REMOVAL_COST} 🪙\n"
        f"⚠️ If your shield drops, you'll reappear."
    ), user


def _verify_recent_kill(
    hunter_id: str,
    target_id: str,
    supabase,
    DB_TABLE: str,
) -> bool:
    """
    Verify that the hunter recently won a battle against the target.
    Checks the battle_log table or the player's recent_battles field.
    Returns True if a win was recorded within CLAIM_WINDOW_MINUTES.
    """
    cutoff = (
        datetime.utcnow() - timedelta(minutes=CLAIM_WINDOW_MINUTES)
    ).isoformat()

    try:
        # Check battle_log table if it exists
        r = supabase.table("battle_log").select("*").eq(
            "attacker_id", hunter_id
        ).eq("defender_id", target_id).eq(
            "result", "attacker_won"
        ).gte("timestamp", cutoff).execute()

        if r.data:
            return True
    except Exception:
        pass

    # Fallback: check player's recent_battles field
    try:
        r = supabase.table(DB_TABLE).select(
            "recent_battles"
        ).eq("user_id", hunter_id).execute()

        if r.data:
            from supabase_db import safe_json
            battles = safe_json(r.data[0].get("recent_battles"), default=[])
            for b in battles:
                if (b.get("opponent_id") == target_id
                        and b.get("result") == "won"
                        and b.get("timestamp", "") >= cutoff):
                    return True
    except Exception:
        pass

    return False


# ═══════════════════════════════════════════════════════════════════════════
#  DISPLAY FORMATTERS
# ═══════════════════════════════════════════════════════════════════════════

def format_bounty_board(
    active_bounties: List[dict],
    auto_visible: List[dict],
    viewer: dict,
    is_hunter: bool = False,
) -> str:
    """Format the full bounty board display."""
    from teleport_system import SECTOR_QUICK_INFO

    lines = [
        "🎯 *BOUNTY BOARD*",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    if is_hunter:
        tier_data = get_hunter_tier_data(viewer)
        xp        = viewer.get("hunter_xp", 0)
        kills     = viewer.get("hunter_kills", 0)
        earnings  = viewer.get("hunter_earnings", 0)
        lines.append(
            f"{tier_data['emoji']} *{tier_data['name']}* Hunter  |  "
            f"XP: {xp}  |  Kills: {kills}  |  Earned: {earnings} 🪙\n"
        )

    # Auto-visible players
    if auto_visible:
        lines.append("👁️ *VISIBLE TARGETS* (no bounty posted)")
        for p in auto_visible[:8]:
            reason      = p.get("board_reason", "")
            name        = p.get("username", "?")
            home_sid    = p.get("home_sector")
            home_str    = ""

            # Hunters with Tier 1+ see last known sector
            if is_hunter and home_sid:
                hi       = SECTOR_QUICK_INFO.get(home_sid, {})
                home_str = f"  🏠 {hi.get('emoji','')} {hi.get('name', f'S{home_sid}')}"

            if "bitcoin_whale" in reason:
                inv  = p.get("inventory", {})
                btc  = inv.get("bitcoin", {}).get("qty", 0) if isinstance(inv, dict) else 0
                tag  = f"₿ WHALE ({btc:.4f} BTC)"
                lines.append(f"  💰 @{name} — {tag}{home_str}")
            elif "unshielded" in reason:
                tag  = "🔓 UNSHIELDED"
                lines.append(f"  🔓 @{name} — {tag}{home_str}")
            else:
                lines.append(f"  📍 @{name} — {reason}{home_str}")

    # Active bounties
    if active_bounties:
        lines.append(f"\n💰 *ACTIVE BOUNTIES* ({len(active_bounties)})")
        for b in sorted(active_bounties, key=lambda x: x.get("reward_gold", 0), reverse=True):
            target  = b.get("target_name", "?")
            reward  = b.get("reward_gold", 0)
            reason  = b.get("reason", "?")
            rank    = b.get("rank", "C")
            bid     = b.get("bounty_id", "")
            poster  = b.get("posted_by_name", "?")

            from alliance_missions import RANK_COLORS
            color   = RANK_COLORS.get(rank, "⬜")

            home_str = ""
            if is_hunter:
                home_sid = b.get("target_home_sector")
                if home_sid:
                    hi       = SECTOR_QUICK_INFO.get(home_sid, {})
                    home_str = f"\n     🏠 {hi.get('emoji','')} {hi.get('name', f'S{home_sid}')}"

            try:
                exp     = datetime.fromisoformat(b.get("expires_at",""))
                hrs_left = max(0, int((exp - datetime.utcnow()).total_seconds() // 3600))
                exp_str = f"{hrs_left}h"
            except Exception:
                exp_str = "?"

            lines.append(
                f"\n  {color} *[{rank}] @{target}*\n"
                f"     💰 {reward} 🪙  |  ⏱️ {exp_str}\n"
                f"     {reason} — by @{poster}{home_str}"
            )

    if not active_bounties and not auto_visible:
        lines.append("\n_Board is clear. No targets today._")

    lines.append(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def format_hunter_profile(user: dict) -> str:
    """Format the hunter career profile section."""
    if not is_bounty_hunter(user):
        return (
            "💀 *BOUNTY HUNTER CAREER*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "_Not activated._\n\n"
            f"Activate for {CAREER_ACTIVATION_COST} 🪙 to unlock:\n"
            "• Bounty board access\n"
            "• Target tracking\n"
            "• Hunter XP and tier progression\n"
            "• Unique combat abilities vs targets"
        )

    tier      = get_hunter_tier(user)
    tier_data = HUNTER_TIERS[tier]
    xp        = user.get("hunter_xp", 0)
    kills     = user.get("hunter_kills", 0)
    earnings  = user.get("hunter_earnings", 0)

    # Next tier progress
    next_tier_data = HUNTER_TIERS.get(tier + 1)
    if next_tier_data:
        xp_needed = next_tier_data["xp_required"]
        xp_pct    = min(100, int(xp / xp_needed * 100))
        filled    = xp_pct // 10
        xp_bar    = "█" * filled + "░" * (10 - filled)
        next_str  = (
            f"\n📈 *Next:* {HUNTER_TIERS[tier+1]['emoji']} {HUNTER_TIERS[tier+1]['name']}\n"
            f"[{xp_bar}] {xp}/{xp_needed} XP"
        )
    else:
        next_str = "\n🏆 *Maximum tier reached.*"

    lines = [
        f"💀 *BOUNTY HUNTER*",
        f"━━━━━━━━━━━━━━━━━━━━━━━━",
        f"{tier_data['emoji']} *{tier_data['name']}* (Tier {tier})",
        f"_{tier_data['description']}_",
        f"",
        f"Kills: *{kills}*  |  XP: *{xp}*",
        f"Career earnings: *{earnings} 🪙*",
        next_str,
        f"",
        f"*UNLOCKED ABILITIES:*",
    ]

    for t in range(1, tier + 1):
        td = HUNTER_TIERS[t]
        lines.append(f"  ✅ {td['emoji']} {td['name']}: {td['description']}")

    if tier < 5:
        lines.append(f"\n*LOCKED:*")
        for t in range(tier + 1, 6):
            td = HUNTER_TIERS[t]
            lines.append(f"  🔒 {td['emoji']} {td['name']}: {td['description']}")

    lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
#  INLINE KEYBOARDS
# ═══════════════════════════════════════════════════════════════════════════

def kb_bounty_board(
    active_bounties: List[dict],
    viewer: dict,
    is_hunter: bool,
) -> InlineKeyboardMarkup:
    """Bounty board keyboard."""
    buttons = []

    # Top 3 bounties as quick-hunt buttons (hunters only)
    if is_hunter:
        for b in active_bounties[:3]:
            target = b.get("target_name", "?")
            reward = b.get("reward_gold", 0)
            bid    = b.get("bounty_id", "")
            buttons.append([InlineKeyboardButton(
                text=f"🎯 Hunt @{target} ({reward}🪙)",
                callback_data=f"hunter:view_bounty:{bid}"
            )])

    buttons.append([
        InlineKeyboardButton(text="💰 Place Bounty",   callback_data="hunter:place_bounty"),
        InlineKeyboardButton(text="🔄 Refresh",        callback_data="hunter:board"),
    ])

    if is_hunter:
        buttons.append([
            InlineKeyboardButton(text="💀 Hunter Profile", callback_data="hunter:profile"),
        ])
    else:
        buttons.append([
            InlineKeyboardButton(text="💀 Become a Hunter", callback_data="hunter:activate"),
        ])

    buttons.append([
        InlineKeyboardButton(text="🛡️ Remove Me from Board", callback_data="hunter:remove_self"),
        InlineKeyboardButton(text="⬅️ Back",                 callback_data="menu_back"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_hunter_profile(user: dict) -> InlineKeyboardMarkup:
    """Hunter profile keyboard."""
    buttons = []
    if is_bounty_hunter(user):
        buttons.append([
            InlineKeyboardButton(text="🎯 Bounty Board", callback_data="hunter:board"),
        ])
        if has_hunter_ability(user, 2):
            buttons.append([
                InlineKeyboardButton(text="🌑 Shadow Teleport", callback_data="hunter:shadow_teleport"),
            ])
    else:
        buttons.append([
            InlineKeyboardButton(text=f"💀 Activate Hunter ({CAREER_ACTIVATION_COST}🪙)",
                                 callback_data="hunter:activate_confirm"),
        ])
    buttons.append([InlineKeyboardButton(text="⬅️ Profile", callback_data="menu_profile")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_place_bounty_amount(target_id: str, target_name: str) -> InlineKeyboardMarkup:
    """Quick amount selection for placing a bounty."""
    amounts = [50, 100, 250, 500, 1000, 2500]
    buttons = []
    row     = []
    for amt in amounts:
        row.append(InlineKeyboardButton(
            text=f"{amt}🪙",
            callback_data=f"hunter:place_confirm:{target_id}:{amt}"
        ))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("✗ Cancel", callback_data="hunter:board")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
