"""
training_system.py — Military Training with XP, Resources & Time Gates
=======================================================================
Troops require BOTH resources AND XP to train.
Progress bars show real-time training status.
GameMaster narrates every training milestone.
"""

import json
from datetime import datetime, timedelta
from typing import Tuple, Dict, List
from supabase_db import get_user, save_user

# In-memory training queues (cleared on restart; Supabase stores completed state)
TRAINING_QUEUES: Dict[str, List[dict]] = {}

# ══════════════════════════════════════════════════════════════════
#  UNIT DEFINITIONS — Cost in resources + XP + time
# ══════════════════════════════════════════════════════════════════

UNITS = {
    "pawns": {
        "name":         "👣 Pawns",
        "description":  "Untrained conscripts. Weak but disposable.",
        "costs": {
            "wood":   2,
            "bronze": 0,
            "iron":   0,
            "xp":     0,       # No XP required
            "silver": 0,
        },
        "stats":        {"attack": 2, "defense": 1, "health": 10},
        "food_upkeep":  0.3,   # food/hour
        "train_time":   20,    # seconds per unit
        "min_level":    1,
        "lore":         "\"They will die first. That is their purpose.\" — GameMaster",
    },
    "footmen": {
        "name":         "👹 Footmen",
        "description":  "Basic infantry. The backbone of any army.",
        "costs": {
            "wood":   5,
            "bronze": 1,
            "iron":   0,
            "xp":     10,
            "silver": 0,
        },
        "stats":        {"attack": 5, "defense": 3, "health": 20},
        "food_upkeep":  0.5,
        "train_time":   30,
        "min_level":    1,
        "lore":         "\"They bleed. They die. They hold the line.\" — GameMaster",
    },
    "archers": {
        "name":         "🏹 Archers",
        "description":  "Ranged precision. Strike before they reach you.",
        "costs": {
            "wood":   8,
            "bronze": 2,
            "iron":   0,
            "xp":     25,
            "silver": 0,
        },
        "stats":        {"attack": 8, "defense": 2, "health": 15},
        "food_upkeep":  0.8,
        "train_time":   45,
        "min_level":    2,
        "lore":         "\"Distance is the archer's dominion.\" — GameMaster",
    },
    "lancers": {
        "name":         "🗡️ Lancers",
        "description":  "Heavy cavalry. Devastating on the charge.",
        "costs": {
            "wood":   0,
            "bronze": 10,
            "iron":   3,
            "xp":     50,
            "silver": 50,
        },
        "stats":        {"attack": 15, "defense": 8, "health": 45},
        "food_upkeep":  1.5,
        "train_time":   60,
        "min_level":    4,
        "lore":         "\"When lancers charge, cowards pray.\" — GameMaster",
    },
    "castellans": {
        "name":         "🏰 Castellans",
        "description":  "Elite fortress guards. Near-indestructible defenders.",
        "costs": {
            "wood":   0,
            "bronze": 5,
            "iron":   15,
            "xp":     100,
            "silver": 150,
        },
        "stats":        {"attack": 12, "defense": 25, "health": 100},
        "food_upkeep":  2.5,
        "train_time":   90,
        "min_level":    7,
        "lore":         "\"A castellan never retreats. They die at their post.\" — GameMaster",
    },
    "warlords": {
        "name":         "💀 Warlords",
        "description":  "Legendary commanders. One equals fifty lesser troops.",
        "costs": {
            "wood":   0,
            "bronze": 0,
            "iron":   30,
            "xp":     250,
            "silver": 500,
        },
        "stats":        {"attack": 60, "defense": 40, "health": 300},
        "food_upkeep":  8.0,
        "train_time":   240,
        "min_level":    12,
        "lore":         "\"Their name alone breaks enemy morale.\" — GameMaster",
    },
}

# ══════════════════════════════════════════════════════════════════
#  TRAINING CAPACITY — Barracks level limits concurrent training
# ══════════════════════════════════════════════════════════════════

def get_max_queue_size(barracks_level: int) -> int:
    """Max units trainable simultaneously."""
    return 5 + (barracks_level * 2)

def get_training_speed_bonus(barracks_level: int) -> float:
    """% speed bonus from barracks upgrades (0.1 = 10% faster per level)."""
    return 1.0 - min(0.5, barracks_level * 0.05)  # Max 50% speed reduction


# ══════════════════════════════════════════════════════════════════
#  CORE TRAINING FUNCTIONS
# ══════════════════════════════════════════════════════════════════

def get_available_units(player_level: int) -> List[str]:
    """Return unit types the player has unlocked based on level."""
    return [utype for utype, udata in UNITS.items()
            if player_level >= udata["min_level"]]

def check_training_cost(user: dict, unit_type: str, amount: int) -> Tuple[bool, str]:
    """
    Check if player can afford to train `amount` of `unit_type`.
    Returns (can_afford, error_message).
    """
    if unit_type not in UNITS:
        return False, f"Unknown unit: {unit_type}"

    unit = UNITS[unit_type]
    level = user.get("level", 1)

    # Level gate
    if level < unit["min_level"]:
        return False, (
            f"❌ *{unit['name']}* requires Level {unit['min_level']}.\n"
            f"You are Level {level}. Keep playing to unlock."
        )

    costs = unit["costs"]
    base_res = user.get("base_resources", {})
    resources = base_res.get("resources", {})

    # Check each resource cost
    missing = []
    for res_type in ("wood", "bronze", "iron"):
        cost_each = costs.get(res_type, 0)
        total_cost = cost_each * amount
        if total_cost > 0:
            have = resources.get(res_type, 0)
            if have < total_cost:
                missing.append(f"{res_type.capitalize()}: need {total_cost:,}, have {have:,}")

    # Check XP cost
    xp_cost = costs.get("xp", 0) * amount
    if xp_cost > 0 and user.get("xp", 0) < xp_cost:
        missing.append(f"XP: need {xp_cost:,}, have {user.get('xp', 0):,}")

    # Check silver cost
    silver_cost = costs.get("silver", 0) * amount
    if silver_cost > 0 and user.get("silver", 0) < silver_cost:
        missing.append(f"Silver: need {silver_cost:,}, have {user.get('silver', 0):,}")

    if missing:
        return False, "❌ *Insufficient resources:*\n" + "\n".join(f"  • {m}" for m in missing)

    return True, "OK"


def deduct_training_cost(user: dict, unit_type: str, amount: int) -> dict:
    """Deduct all costs for training and return updated user dict."""
    unit = UNITS[unit_type]
    costs = unit["costs"]

    base_res = user.get("base_resources", {})
    resources = base_res.get("resources", {})

    for res_type in ("wood", "bronze", "iron"):
        cost_total = costs.get(res_type, 0) * amount
        if cost_total > 0:
            resources[res_type] = max(0, resources.get(res_type, 0) - cost_total)

    base_res["resources"] = resources
    user["base_resources"] = base_res

    xp_cost = costs.get("xp", 0) * amount
    if xp_cost > 0:
        user["xp"] = max(0, user.get("xp", 0) - xp_cost)

    silver_cost = costs.get("silver", 0) * amount
    if silver_cost > 0:
        user["silver"] = max(0, user.get("silver", 0) - silver_cost)

    return user


def add_to_training_queue(user_id: str, unit_type: str, amount: int) -> Tuple[bool, str]:
    """
    Queue units for training. Checks level, resources, and XP.
    Returns (success, message).
    """
    user = get_user(user_id)
    if not user:
        return False, "❌ Player not found."

    if unit_type not in UNITS:
        available = ", ".join(UNITS.keys())
        return False, f"❌ Unknown unit. Available: {available}"

    if amount <= 0 or amount > 100:
        return False, "❌ Amount must be between 1 and 100."

    # Check costs
    can_afford, error_msg = check_training_cost(user, unit_type, amount)
    if not can_afford:
        return False, error_msg

    unit = UNITS[unit_type]

    # Barracks speed bonus
    buildings = user.get("base_buildings", {})
    barracks_level = buildings.get("barracks", {}).get("level", 1)
    speed_mult = get_training_speed_bonus(barracks_level)
    base_time = unit["train_time"] * amount
    actual_time = int(base_time * speed_mult)

    # Deduct costs
    user = deduct_training_cost(user, unit_type, amount)
    save_user(user_id, user)

    # Queue it
    if user_id not in TRAINING_QUEUES:
        TRAINING_QUEUES[user_id] = []

    completes_at = (datetime.utcnow() + timedelta(seconds=actual_time)).isoformat()
    queue_item = {
        "unit_type":    unit_type,
        "amount":       amount,
        "started_at":   datetime.utcnow().isoformat(),
        "completes_at": completes_at,
    }
    TRAINING_QUEUES[user_id].append(queue_item)

    costs = unit["costs"]
    cost_parts = []
    for res in ("wood", "bronze", "iron"):
        v = costs.get(res, 0) * amount
        if v:
            cost_parts.append(f"{v:,} {res}")
    if costs.get("xp", 0) * amount:
        cost_parts.append(f"{costs['xp'] * amount:,} XP")
    if costs.get("silver", 0) * amount:
        cost_parts.append(f"{costs['silver'] * amount:,} silver")

    cost_str = " • ".join(cost_parts) if cost_parts else "Free"
    mins = actual_time // 60
    secs = actual_time % 60
    time_str = f"{mins}m {secs}s" if mins else f"{secs}s"

    # GameMaster lore line
    lore = unit.get("lore", "")

    return True, (
        f"⚔️ *TRAINING INITIATED*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{unit['name']} × {amount}\n"
        f"💸 Cost: {cost_str}\n"
        f"⏱️ Completes in: {time_str}\n"
        f"🏛️ Barracks Lv.{barracks_level} {'(speed bonus active)' if barracks_level > 1 else ''}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🃏 _{lore}_"
    )


def process_training_queue(user_id: str) -> Dict:
    """Process and apply completed training. Returns completed units dict."""
    user = get_user(user_id)
    if not user:
        return {"ok": False, "completed": {}}

    queue = TRAINING_QUEUES.get(user_id, [])
    now = datetime.utcnow()
    completed_items = []
    remaining = []

    for item in queue:
        try:
            completes = datetime.fromisoformat(item["completes_at"])
            if now >= completes:
                completed_items.append(item)
            else:
                remaining.append(item)
        except Exception:
            remaining.append(item)

    if completed_items:
        military = user.get("military", {})
        completed_summary = {}
        for item in completed_items:
            utype = item["unit_type"]
            amt = item["amount"]
            military[utype] = military.get(utype, 0) + amt
            completed_summary[utype] = completed_summary.get(utype, 0) + amt
        user["military"] = military
        TRAINING_QUEUES[user_id] = remaining
        save_user(user_id, user)
        return {"ok": True, "completed": completed_summary}

    TRAINING_QUEUES[user_id] = remaining
    return {"ok": True, "completed": {}}


def get_training_status(user_id: str) -> Dict:
    """Return current queue status without processing completions."""
    result = process_training_queue(user_id)
    queue = TRAINING_QUEUES.get(user_id, [])
    return {
        "queue": queue,
        "completed_this_call": result.get("completed", {}),
    }


def format_training_status(user_id: str) -> str:
    """Full training status message with progress bars."""
    from formatting import format_training_queue, thin_divider
    status = get_training_status(user_id)
    queue = status["queue"]
    completed = status["completed_this_call"]

    lines = []

    if completed:
        lines.append("✅ *TRAINING COMPLETE!*")
        for utype, amt in completed.items():
            unit = UNITS.get(utype, {})
            name = unit.get("name", utype)
            lines.append(f"  {name} ×{amt} — now ready for battle!")
        lines.append("")

    lines.append(format_training_queue(queue))

    if not queue and not completed:
        lines.append("")
        lines.append("_Use_ `!train [unit] [amount]` _to build your army._")
        # Show what's available
        user = get_user(user_id)
        if user:
            level = user.get("level", 1)
            unlocked = get_available_units(level)
            lines.append(f"\n⚔️ *Available units at Level {level}:*")
            for utype in unlocked:
                u = UNITS[utype]
                lines.append(f"  {u['name']} — `!train {utype} [amount]`")

    return "\n".join(lines)


def format_unit_catalog(player_level: int, user: dict = None) -> str:
    """Display all units with costs and unlock requirements."""
    lines = [
        "⚔️ *UNIT CATALOG*",
        "═" * 32,
        "_Train troops to defend your base and raid enemies._",
        "",
    ]
    for utype, unit in UNITS.items():
        locked = player_level < unit["min_level"]
        status = f"🔒 Unlock at Level {unit['min_level']}" if locked else "✅ Available"
        costs = unit["costs"]
        cost_parts = []
        for res in ("wood", "bronze", "iron"):
            if costs.get(res, 0):
                cost_parts.append(f"{costs[res]} {res}")
        if costs.get("xp", 0):
            cost_parts.append(f"{costs['xp']} XP")
        if costs.get("silver", 0):
            cost_parts.append(f"{costs['silver']} silver")
        cost_str = " + ".join(cost_parts) if cost_parts else "Free"

        secs = unit["train_time"]
        time_str = f"{secs//60}m {secs%60}s" if secs >= 60 else f"{secs}s"
        stats = unit["stats"]

        lines.append(f"{unit['name']} [{status}]")
        lines.append(f"  _{unit['description']}_")
        lines.append(f"  💸 Cost/unit: {cost_str}")
        lines.append(f"  ⏱️  Time/unit: {time_str}")
        lines.append(f"  ⚔️  ATK:{stats['attack']} DEF:{stats['defense']} HP:{stats['health']}")
        lines.append(f"  🍖 Upkeep: {unit['food_upkeep']}/hr")
        lines.append("")

    lines.append("─" * 32)
    lines.append("Use `!train [unit] [amount]` to recruit")
    return "\n".join(lines)


def complete_all_trainings(user_id: str) -> Dict:
    """Force-complete all training (admin/testing command)."""
    user = get_user(user_id)
    if not user:
        return {"success": False}

    queue = TRAINING_QUEUES.get(user_id, [])
    military = user.get("military", {})
    completed = {}

    for item in queue:
        utype = item["unit_type"]
        amt = item["amount"]
        military[utype] = military.get(utype, 0) + amt
        completed[utype] = completed.get(utype, 0) + amt

    user["military"] = military
    save_user(user_id, user)
    TRAINING_QUEUES[user_id] = []

    return {"success": True, "completed": completed,
            "total": sum(completed.values())}
