"""
gift_system.py — Hourly free gift crates
==========================================
Every hour, each player is offered one free gift crate. Tiers are picked
randomly (weighted). If not claimed before it expires, it's lost — no
stacking of missed hours. Builds a "check back regularly" habit loop.

Storage: user["free_gift"] — a single dict (not a list; only one gift can
be pending at a time), shape:
    {
        "id": int,
        "tier": "common"|"rare"|"epic"|"legendary",
        "granted_at": iso timestamp,
        "expires_at": iso timestamp (granted_at + 1 hour),
    }
None / missing means no gift currently pending.

Migration: no new column needed — free_gift can live inside the existing
JSONB blob pattern. Add a column explicitly if you'd rather it be typed:
    alter table players add column if not exists free_gift jsonb;
"""

import random
from datetime import datetime, timedelta
from typing import Optional, Tuple

GIFT_EXPIRY_MINUTES = 60

# Each tier: contents + relative weight (higher = more common)
GIFT_TIERS = {
    "common": {
        "emoji":  "🎁",
        "name":   "Common Gift",
        "weight": 60,
        "contents": {"credits": 20, "resources": {"wood": 100, "bronze": 50}},
    },
    "rare": {
        "emoji":  "🎀",
        "name":   "Rare Gift",
        "weight": 25,
        "contents": {"credits": 50, "resources": {"iron": 80, "stone": 40}},
    },
    "epic": {
        "emoji":  "💜",
        "name":   "Epic Gift",
        "weight": 12,
        "contents": {"credits": 120, "gold": 5, "resources": {"relics": 10}},
    },
    "legendary": {
        "emoji":  "💛",
        "name":   "Legendary Gift",
        "weight": 3,
        "contents": {"credits": 300, "gold": 25, "resources": {"relics": 30}},
    },
}


def _pick_tier() -> str:
    tiers   = list(GIFT_TIERS.keys())
    weights = [GIFT_TIERS[t]["weight"] for t in tiers]
    return random.choices(tiers, weights=weights, k=1)[0]


def grant_hourly_gift(user: dict) -> dict:
    """
    Ensure the player has a fresh gift available. Called from the hourly
    scheduler job (grant_hourly_gifts_to_all). Overwrites any expired,
    unclaimed gift — missed gifts are lost, never stacked.
    """
    now      = datetime.utcnow()
    existing = user.get("free_gift")

    if existing:
        try:
            expires = datetime.fromisoformat(existing["expires_at"])
            if now < expires:
                return user   # still has an active, unexpired gift — don't overwrite
        except Exception:
            pass   # malformed — fall through and replace it

    tier = _pick_tier()
    user["free_gift"] = {
        "id":         int(now.timestamp()),
        "tier":       tier,
        "granted_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=GIFT_EXPIRY_MINUTES)).isoformat(),
    }
    return user


def grant_hourly_gifts_to_all(supabase, DB_TABLE: str) -> int:
    """
    Scheduler entry point — call once per hour. Grants a fresh gift to
    every player who doesn't currently have an active unclaimed one.
    """
    from supabase_db import get_user, save_user
    granted = 0
    try:
        result = supabase.table(DB_TABLE).select("user_id").execute()
        for row in (result.data or []):
            uid = row.get("user_id")
            if not uid:
                continue
            try:
                user = get_user(uid)
                if not user:
                    continue
                before = user.get("free_gift")
                user = grant_hourly_gift(user)
                if user.get("free_gift") != before:
                    save_user(uid, user)
                    granted += 1
            except Exception as e:
                print(f"[GIFT] grant failed for {uid}: {e}")
    except Exception as e:
        print(f"[GIFT] grant_hourly_gifts_to_all error: {e}")
    return granted


def claim_free_gift(user_id: str) -> Tuple[bool, str]:
    """Claim the player's current pending gift, if any and not expired."""
    from supabase_db import get_user, save_user
    user = get_user(user_id)
    if not user:
        return False, "❌ User not found."

    gift = user.get("free_gift")
    if not gift:
        return False, "🎁 No gift available right now — check back soon!"

    try:
        expires = datetime.fromisoformat(gift["expires_at"])
    except Exception:
        user["free_gift"] = None
        save_user(user_id, user)
        return False, "🎁 That gift expired."

    if datetime.utcnow() >= expires:
        user["free_gift"] = None
        save_user(user_id, user)
        return False, "🎁 That gift expired — a new one arrives next hour!"

    tier_key = gift.get("tier", "common")
    granted_msg = grant_gift_contents(user, tier_key)

    user["free_gift"] = None
    save_user(user_id, user)

    return True, granted_msg


def grant_gift_contents(user: dict, tier_key: str) -> str:
    """
    Apply a gift tier's contents directly to an in-memory user dict.
    Caller is responsible for save_user(). Returns a display message.
    Shared by claim_free_gift() and the alliance-purchase bonus gifts.
    """
    tier = GIFT_TIERS.get(tier_key, GIFT_TIERS["common"])
    contents = tier["contents"]
    lines = [f"{tier['emoji']} *{tier['name']}* opened!"]

    if "credits" in contents:
        user["credits"] = (user.get("credits", 0) or 0) + contents["credits"]
        lines.append(f"  +{contents['credits']} 💳 Credits")

    if "gold" in contents:
        user["gold"] = (user.get("gold", 0) or 0) + contents["gold"]
        lines.append(f"  +{contents['gold']} 🪙 Gold")

    if "resources" in contents:
        from build_system import clamp_resource_add
        for res_type, amount in contents["resources"].items():
            clamp_resource_add(user, res_type, amount)
            lines.append(f"  +{amount} {res_type.title()}")

    return "\n".join(lines)


def get_gift_hud_line(user: dict) -> str:
    """One-line gift status for the main dashboard HUD."""
    gift = user.get("free_gift")
    if not gift:
        return ""
    try:
        expires   = datetime.fromisoformat(gift["expires_at"])
        remaining = (expires - datetime.utcnow()).total_seconds()
        if remaining <= 0:
            return ""
        m, s = divmod(int(remaining), 60)
        tier = GIFT_TIERS.get(gift.get("tier", "common"), GIFT_TIERS["common"])
        return f"{tier['emoji']} Gift ready! ({m}m {s}s left to claim)"
    except Exception:
        return ""


def grant_bonus_gift_packs(user_id: str, count: int, min_tier: str = "common") -> None:
    """
    Grant `count` extra gift crates immediately (bypassing the hourly-slot
    limit) — used for the alliance-purchase bonus. These are opened
    immediately rather than queued, since a player could otherwise only
    ever hold one pending gift at a time.
    """
    from supabase_db import get_user, save_user
    user = get_user(user_id)
    if not user:
        return

    tier_order = ["common", "rare", "epic", "legendary"]
    min_index  = tier_order.index(min_tier) if min_tier in tier_order else 0
    allowed_tiers = tier_order[min_index:]

    summary_lines = []
    for _ in range(count):
        tier_key = random.choice(allowed_tiers)
        msg = grant_gift_contents(user, tier_key)
        summary_lines.append(msg)

    save_user(user_id, user)

    user["pending_notification"] = (
        f"🎉 *{count} bonus gift pack(s) opened!*\n\n" + "\n\n".join(summary_lines)
    )
    save_user(user_id, user)
try:
    from build_system import clamp_resource_add
except ImportError:
    def clamp_resource_add(user, res_type, amount):
        # Stopgap: no cap enforcement until build_system.clamp_resource_add exists
        res = user.setdefault("base_resources", {}).setdefault("resources", {})
        res[res_type] = res.get(res_type, 0) + amount
        return user