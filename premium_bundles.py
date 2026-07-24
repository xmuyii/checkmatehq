"""
premium_bundles.py — Stars-only bundle packs + alliance purchase bonus
========================================================================
Bundles are purchased via Telegram Stars (native invoice flow, currency
"XTR") — NOT through store_system.purchase_item's gold/credits/bitcoin
deduction logic. This module owns the catalog and the post-payment
crediting, wired to main.py's successful_payment handler.

ALLIANCE PURCHASE BONUS RULE (per design):
  - Buyer always receives the bundle contents.
  - If buyer is in an alliance at time of purchase:
      * Buyer receives BONUS_GIFT_COUNT extra gift packs (min tier: rare)
      * Every OTHER member of buyer's alliance also receives
        BONUS_GIFT_COUNT gift packs each — for free, without buying
        anything themselves.
  - If buyer is NOT in an alliance: bundle is granted, but NO bonus gift
    packs at all (this is the incentive to join/create an alliance
    before buying bundles).
"""

from typing import Tuple
from datetime import datetime

BONUS_GIFT_COUNT = 10
BONUS_GIFT_MIN_TIER = "rare"   # alliance bonus gifts skew better than the free hourly gift

PREMIUM_BUNDLES = {
    "starter_bundle": {
        "name":  "🚀 Starter Bundle",
        "desc":  "A boost for new commanders.",
        "stars": 100,
        "contents": {
            "credits": 500,
            "gold": 20,
            "resources": {"wood": 500, "bronze": 300, "iron": 200},
        },
    },
    "warlord_bundle": {
        "name":  "⚔️ Warlord Bundle",
        "desc":  "Gold, gear, and resources for serious players.",
        "stars": 350,
        "contents": {
            "credits": 1500,
            "gold": 100,
            "resources": {"iron": 800, "stone": 500, "relics": 50},
        },
    },
    "diamond_bundle": {
        "name":  "💎 Diamond Bundle",
        "desc":  "The whale-tier bundle. Maximum value.",
        "stars": 1000,
        "contents": {
            "credits": 5000,
            "gold": 400,
            "resources": {"relics": 250, "stone": 1500},
        },
    },
}


def grant_bundle_contents(user: dict, bundle_key: str) -> str:
    """Apply a bundle's contents to an in-memory user dict. Caller saves."""
    bundle = PREMIUM_BUNDLES.get(bundle_key)
    if not bundle:
        return "❌ Bundle not found."

    contents = bundle["contents"]
    lines = [f"{bundle['name']} unlocked!"]

    if "credits" in contents:
        user["credits"] = (user.get("credits", 0) or 0) + contents["credits"]
        lines.append(f"  +{contents['credits']:,} 💳 Credits")

    if "gold" in contents:
        user["gold"] = (user.get("gold", 0) or 0) + contents["gold"]
        lines.append(f"  +{contents['gold']:,} 🪙 Gold")

    if "resources" in contents:
        from build_system import clamp_resource_add
        for res_type, amount in contents["resources"].items():
            clamp_resource_add(user, res_type, amount)
            lines.append(f"  +{amount:,} {res_type.title()}")

    return "\n".join(lines)


def process_bundle_purchase(buyer_id: str, bundle_key: str) -> Tuple[bool, str]:
    """
    Call this from the successful_payment handler after a Stars payment
    for a bundle completes. Grants the bundle to the buyer, then applies
    the alliance bonus gift distribution if applicable.
    """
    from supabase_db import get_user, save_user

    buyer = get_user(buyer_id)
    if not buyer:
        return False, "❌ Buyer not found."

    bundle_msg = grant_bundle_contents(buyer, bundle_key)
    save_user(buyer_id, buyer)

    alliance_id = buyer.get("alliance_id")
    bonus_msg = ""

    if alliance_id:
        from gift_system import grant_bonus_gift_packs
        from alliance_system import get_alliance_members

        # Buyer gets their own bonus gifts too
        grant_bonus_gift_packs(buyer_id, BONUS_GIFT_COUNT, min_tier=BONUS_GIFT_MIN_TIER)

        # Every OTHER alliance member gets bonus gifts, for free
        members = get_alliance_members(alliance_id)
        notified = 0
        for member_id in members:
            if member_id == buyer_id:
                continue
            grant_bonus_gift_packs(member_id, BONUS_GIFT_COUNT, min_tier=BONUS_GIFT_MIN_TIER)
            notified += 1

        bonus_msg = (
            f"\n\n🎉 Alliance bonus! You + {notified} alliance member(s) "
            f"each received {BONUS_GIFT_COUNT} bonus gift packs!"
        )

    return True, bundle_msg + bonus_msg