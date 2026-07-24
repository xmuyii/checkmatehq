"""
referral_system.py — Referral links with activation-gated rewards
=====================================================================
Reward triggers on the REFERRED player reaching an activation milestone,
not on raw signup — this is the standard anti-farming pattern. A flat
signup reward is trivially exploitable via disposable accounts.
"""

from typing import Optional, Tuple

REFERRAL_REWARD_CREDITS = 500
ACTIVATION_LEVEL = 3   # referred player must reach this level for reward to trigger


def make_referral_link(bot_username: str, user_id: str) -> str:
    """Telegram deep link — payload becomes the /start argument."""
    return f"https://t.me/{bot_username}?start=ref_{user_id}"


def parse_referral_payload(start_arg: str) -> Optional[str]:
    """Extract referrer_id from a '/start ref_<id>' payload, or None."""
    if start_arg and start_arg.startswith("ref_"):
        return start_arg[4:]
    return None


def register_referral(new_user_id: str, referrer_id: str) -> bool:
    """
    Call this ONCE, only during a genuinely new registration (never on an
    existing user re-clicking a link). Records the relationship but does
    NOT grant any reward yet — that happens later, in check_referral_activation.
    """
    from supabase_db import get_user, save_user

    if new_user_id == referrer_id:
        return False   # can't refer yourself

    referrer = get_user(referrer_id)
    if not referrer:
        return False   # referral code doesn't match a real player

    new_user = get_user(new_user_id)
    if not new_user or new_user.get("referred_by"):
        return False   # already has a referrer, or doesn't exist yet

    new_user["referred_by"] = referrer_id
    new_user["referral_reward_claimed"] = False
    save_user(new_user_id, new_user)

    pending = referrer.get("pending_referrals", []) or []
    pending.append(new_user_id)
    referrer["pending_referrals"] = pending
    save_user(referrer_id, referrer)

    return True


def check_referral_activation(user_id: str) -> Optional[str]:
    """
    Call this wherever a player's level changes (your existing level-up
    code path). If they just crossed ACTIVATION_LEVEL and were referred,
    grant the referrer their reward exactly once.
    Returns a notification string for the referrer, or None.
    """
    from supabase_db import get_user, save_user

    user = get_user(user_id)
    if not user:
        return None

    if user.get("referral_reward_claimed"):
        return None   # already paid out — never pay twice

    referrer_id = user.get("referred_by")
    if not referrer_id:
        return None   # wasn't referred by anyone

    if user.get("level", 1) < ACTIVATION_LEVEL:
        return None   # not activated yet

    referrer = get_user(referrer_id)
    if not referrer:
        return None

    referrer["credits"] = (referrer.get("credits", 0) or 0) + REFERRAL_REWARD_CREDITS
    referrer["referral_count"] = (referrer.get("referral_count", 0) or 0) + 1
    pending = [p for p in referrer.get("pending_referrals", []) if p != user_id]
    referrer["pending_referrals"] = pending
    save_user(referrer_id, referrer)

    user["referral_reward_claimed"] = True
    save_user(user_id, user)

    msg = (
        f"🎉 Your referral {user.get('username','a player')} reached level "
        f"{ACTIVATION_LEVEL}! +{REFERRAL_REWARD_CREDITS} 💳 Credits earned."
    )
    referrer["pending_notification"] = msg
    save_user(referrer_id, referrer)
    return msg


def format_referral_stats(user: dict) -> str:
    count   = user.get("referral_count", 0)
    pending = len(user.get("pending_referrals", []) or [])
    return (
        f"🔗 *REFERRALS*\n"
        f"✅ Activated: {count}\n"
        f"⏳ Pending: {pending}\n"
        f"💳 Total earned: {count * REFERRAL_REWARD_CREDITS:,} Credits"
    )