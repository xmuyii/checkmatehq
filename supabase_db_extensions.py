"""
supabase_db.py — Additions & Fixes for The 64
==============================================
NEW in this patch:
  - claim_all_by_type(): claim every unclaimed item of a given type at once
  - get_grouped_unclaimed(): returns grouped dict for clean display
  - use_item_from_inventory(): apply an item's effect immediately
  - use_all_items_of_type(): use every inventory item of a given type
  - add_resources(): bulk add multiple resources at once
  - get_army_power(): quick power summary for a player

All original functions from supabase_db.py are preserved; this file
extends the module. Import from this file OR merge into supabase_db.py.
"""

# ── This file is meant to be merged into supabase_db.py ──────────────────
# The functions below augment the existing module.

from supabase_db import (
    get_user, save_user, add_xp, _next_id, _fix_item_ids,
    add_unclaimed_item, get_unclaimed_items, get_inventory,
)
from datetime import datetime
from typing import Tuple, Dict, List, Optional
import random


# ══════════════════════════════════════════════════════════════════
#  GROUPED UNCLAIMED ITEMS — For the new UI
# ══════════════════════════════════════════════════════════════════

def get_grouped_unclaimed(user_id: str) -> Dict[str, dict]:
    """
    Return unclaimed items grouped by type.
    Format:
    {
        "shield": {"count": 2, "ids": [1, 4], "sample": {...}},
        "wood_crate": {"count": 3, "ids": [2, 3, 5], "sample": {...}},
    }
    """
    items = get_unclaimed_items(user_id)
    grouped: Dict[str, dict] = {}
    for item in items:
        itype = item.get("type", "unknown").replace("locked_", "")
        if itype not in grouped:
            grouped[itype] = {"count": 0, "ids": [], "sample": item}
        grouped[itype]["count"] += 1
        grouped[itype]["ids"].append(item.get("id"))
    return grouped


def claim_all_by_type(user_id: str, item_type: str) -> Tuple[bool, str]:
    """
    Claim all unclaimed items of a specific type at once.
    Moves them all to inventory (up to the slot limit).
    Returns (success, message).
    """
    uid = str(user_id)
    user = get_user(uid)
    if not user:
        return False, "Player not found"

    unclaimed = user.get("unclaimed_items", [])
    inv = user.get("inventory", [])
    slots = user.get("backpack_slots", 5)

    # Find all matching items
    matching = [it for it in unclaimed if it.get("type", "").replace("locked_", "") == item_type
                or it.get("type", "") == item_type]

    if not matching:
        return False, f"No unclaimed items of type: {item_type}"

    # How many can we fit?
    available_slots = slots - len(inv)
    to_claim = matching[:available_slots]
    skipped = len(matching) - len(to_claim)

    claimed_ids = set(it["id"] for it in to_claim)

    for item in to_claim:
        inv.append({
            "id":               _next_id(inv),
            "type":             item.get("type"),
            "xp_reward":        item.get("xp_reward", 0),
            "multiplier_value": item.get("multiplier_value", 0),
            "acquired":         datetime.utcnow().isoformat(),
        })

    user["inventory"] = inv
    user["unclaimed_items"] = [it for it in unclaimed if it.get("id") not in claimed_ids]
    save_user(uid, user)

    msg = f"✅ Claimed {len(to_claim)}× {item_type.replace('_', ' ').title()}"
    if skipped:
        msg += f"\n⚠️ {skipped} item(s) skipped — inventory full."
    return True, msg


# ══════════════════════════════════════════════════════════════════
#  ITEM USAGE — Apply items directly from inventory
# ══════════════════════════════════════════════════════════════════

ITEM_EFFECTS: Dict[str, dict] = {
    "shield": {
        "description": "Activates your base shield for 24 hours",
        "action":      "shield",
    },
    "shield_potion": {
        "description": "Restores a disrupted shield to ACTIVE",
        "action":      "restore_shield",
    },
    "wood_crate": {
        "description": "Opens for XP and wood resources",
        "action":      "open_crate",
        "resources":   {"wood": (20, 60)},
    },
    "bronze_crate": {
        "description": "Opens for XP and bronze resources",
        "action":      "open_crate",
        "resources":   {"bronze": (10, 40)},
    },
    "iron_crate": {
        "description": "Opens for XP and iron resources",
        "action":      "open_crate",
        "resources":   {"iron": (5, 25)},
    },
    "super_crate": {
        "description": "Opens for XP and premium resources",
        "action":      "open_crate",
        "resources":   {"diamond": (2, 10), "iron": (10, 30)},
    },
    "teleport": {
        "description": "Teleport to any sector (1-9)",
        "action":      "teleport",
    },
    "free_teleport": {
        "description": "Free teleport to any sector (1-9)",
        "action":      "teleport",
    },
    "food_ration": {
        "description": "Instantly feeds your army for 4 hours",
        "action":      "add_food",
        "food_amount": 40,
    },
    "repair_kit": {
        "description": "Restores 50 base durability",
        "action":      "repair_base",
        "durability":  50,
    },
}


def use_item(user_id: str, item_type: str) -> Tuple[bool, str, dict]:
    """
    Use one item of the given type from inventory.
    Applies the item's effect immediately.
    Returns (success, message, effect_data).
    """
    uid = str(user_id)
    user = get_user(uid)
    if not user:
        return False, "Player not found", {}

    inv = user.get("inventory", [])
    # Find first matching item
    item = next(
        (it for it in inv if it.get("type", "").replace("locked_", "") == item_type
         or it.get("type", "") == item_type),
        None
    )
    if not item:
        return False, f"No {item_type.replace('_', ' ')} in your inventory.", {}

    effect_info = ITEM_EFFECTS.get(item_type.replace("locked_", ""), {})
    action = effect_info.get("action", "unknown")
    effect_data: dict = {}

    # Apply effect
    if action == "shield":
        user["shield_status"] = "ACTIVE"
        effect_data = {"shield": "ACTIVE"}
        result_msg = "🛡️ *Shield ACTIVATED!* Your base is now protected."

    elif action == "restore_shield":
        current = user.get("shield_status", "UNPROTECTED")
        user["shield_status"] = "ACTIVE"
        effect_data = {"shield": "restored"}
        result_msg = "🧪 *Shield restored to ACTIVE!*"

    elif action == "open_crate":
        xp_reward = item.get("xp_reward", 0) or random.randint(50, 150)
        res_ranges = effect_info.get("resources", {})
        resources_gained = {}
        base_res = user.get("base_resources", {})
        res_dict = base_res.get("resources", {})
        for res_type, (low, high) in res_ranges.items():
            amt = random.randint(low, high)
            res_dict[res_type] = res_dict.get(res_type, 0) + amt
            resources_gained[res_type] = amt
        base_res["resources"] = res_dict
        user["base_resources"] = base_res
        user["xp"] = user.get("xp", 0) + xp_reward
        user["level"] = 1 + (user["xp"] // 100)
        effect_data = {"xp": xp_reward, "resources": resources_gained}
        res_lines = "\n".join(
            f"  +{amt} {res.capitalize()}" for res, amt in resources_gained.items()
        )
        result_msg = (
            f"📦 *{item_type.replace('_', ' ').title()} OPENED!*\n"
            f"  ✨ +{xp_reward} XP\n"
            f"{res_lines}"
        )

    elif action == "add_food":
        food_add = effect_info.get("food_amount", 40)
        base_res = user.get("base_resources", {})
        base_res["food"] = base_res.get("food", 0) + food_add
        user["base_resources"] = base_res
        effect_data = {"food": food_add}
        result_msg = f"🍖 *Food Ration used!* +{food_add} food."

    elif action == "repair_base":
        dur = effect_info.get("durability", 50)
        effect_data = {"durability": dur}
        result_msg = f"🔧 *Repair Kit used!* Base durability +{dur}."

    elif action == "teleport":
        # Can't auto-apply sector; return info for caller to handle
        effect_data = {"needs_destination": True}
        result_msg = "🌀 *Teleport ready!* Choose a sector: `!teleport [1-9]`"

    else:
        result_msg = f"📦 Used {item_type.replace('_', ' ').title()}."
        effect_data = {}

    # Remove item from inventory
    item_id = item.get("id")
    user["inventory"] = [it for it in inv if it.get("id") != item_id]
    save_user(uid, user)

    return True, result_msg, effect_data


def use_all_items_of_type(user_id: str, item_type: str) -> Tuple[bool, str]:
    """
    Use ALL inventory items of a given type.
    Stacks the effects (e.g., open all wood crates at once).
    """
    uid = str(user_id)
    user = get_user(uid)
    if not user:
        return False, "Player not found"

    inv = user.get("inventory", [])
    matching = [
        it for it in inv
        if it.get("type", "").replace("locked_", "") == item_type
        or it.get("type", "") == item_type
    ]

    if not matching:
        return False, f"No {item_type} in inventory."

    count = len(matching)
    total_xp = 0
    total_resources: Dict[str, int] = {}

    effect_info = ITEM_EFFECTS.get(item_type.replace("locked_", ""), {})
    action = effect_info.get("action", "unknown")

    for item in matching:
        if action == "open_crate":
            xp = item.get("xp_reward", 0) or random.randint(50, 150)
            total_xp += xp
            res_ranges = effect_info.get("resources", {})
            for res_type, (low, high) in res_ranges.items():
                amt = random.randint(low, high)
                total_resources[res_type] = total_resources.get(res_type, 0) + amt
        elif action == "add_food":
            total_resources["food"] = total_resources.get("food", 0) + effect_info.get("food_amount", 40)
        elif action == "shield":
            user["shield_status"] = "ACTIVE"

    # Apply resources
    base_res = user.get("base_resources", {})
    res_dict = base_res.get("resources", {})
    for res_type, amt in total_resources.items():
        if res_type == "food":
            base_res["food"] = base_res.get("food", 0) + amt
        else:
            res_dict[res_type] = res_dict.get(res_type, 0) + amt
    base_res["resources"] = res_dict
    user["base_resources"] = base_res

    # Apply XP
    if total_xp > 0:
        user["xp"] = user.get("xp", 0) + total_xp
        user["level"] = 1 + (user["xp"] // 100)

    # Remove all used items
    used_ids = {it.get("id") for it in matching}
    user["inventory"] = [it for it in inv if it.get("id") not in used_ids]
    save_user(uid, user)

    lines = [f"✅ *Used {count}× {item_type.replace('_', ' ').title()}*"]
    if total_xp:
        lines.append(f"  ✨ +{total_xp:,} XP total")
    for res, amt in total_resources.items():
        if res != "food":
            lines.append(f"  +{amt:,} {res.capitalize()}")
    if "food" in total_resources:
        lines.append(f"  🍖 +{total_resources['food']} food")

    return True, "\n".join(lines)


# ══════════════════════════════════════════════════════════════════
#  RESOURCE UTILITIES
# ══════════════════════════════════════════════════════════════════

def add_resources(user_id: str, resources: Dict[str, int], food: int = 0) -> bool:
    """Add multiple resources at once. Returns True on success."""
    user = get_user(str(user_id))
    if not user:
        return False
    base_res = user.get("base_resources", {})
    res_dict = base_res.get("resources", {})
    for res_type, amt in resources.items():
        res_dict[res_type] = res_dict.get(res_type, 0) + amt
    base_res["resources"] = res_dict
    if food:
        base_res["food"] = base_res.get("food", 0) + food
    user["base_resources"] = base_res
    save_user(str(user_id), user)
    return True


def deduct_resources(user_id: str, resources: Dict[str, int]) -> Tuple[bool, str]:
    """
    Deduct multiple resources. Returns (success, error_msg).
    Atomically checks ALL before deducting any.
    """
    user = get_user(str(user_id))
    if not user:
        return False, "Player not found"
    base_res = user.get("base_resources", {})
    res_dict = base_res.get("resources", {})

    # Validate all first
    shortfalls = []
    for res_type, amt in resources.items():
        have = res_dict.get(res_type, 0)
        if have < amt:
            shortfalls.append(f"{res_type.capitalize()}: need {amt:,}, have {have:,}")
    if shortfalls:
        return False, "Insufficient resources:\n" + "\n".join(f"  • {s}" for s in shortfalls)

    # Deduct
    for res_type, amt in resources.items():
        res_dict[res_type] = res_dict.get(res_type, 0) - amt
    base_res["resources"] = res_dict
    user["base_resources"] = base_res
    save_user(str(user_id), user)
    return True, "OK"


def get_army_power_summary(user_id: str) -> dict:
    """Quick power summary for a player's army."""
    from revenge_system import calculate_army_power
    user = get_user(str(user_id))
    if not user:
        return {"total_troops": 0, "attack": 0, "defense": 0}
    military = user.get("military", {})
    return calculate_army_power(military)
