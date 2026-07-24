# -*- coding: utf-8 -*-
"""
training_system.py — Fixed (drop-in replacement)
==================================================
Changes from original:

FIX 1 — TRAINING_QUEUES in-memory dict lost on every Railway restart.
  Queue now stored in players.training_queue JSONB column.
  add_to_training_queue() writes to DB. process_training_queue() reads from DB.
  Backwards compat: TRAINING_QUEUES still exists as empty dict (prevents
  ImportError if anything still references it).

FIX 2 — get_training_queue_display() was called from main.py but never existed.
  Added. Returns compact progress bars for the HUD dashboard.

FIX 3 — DB table was referenced as 'users' in direct supabase calls.
  All direct supabase calls now use 'players'.

Everything else (UNITS, UNIT_NAMES, UNIT_COSTS, TRAINING_TIMES, cost checks,
format_unit_catalog, format_training_status, format_training_queue usage)
is preserved exactly.
"""

import json
from datetime import datetime, timedelta
from typing import Tuple, Dict, List
from supabase_db import get_user, save_user

# Kept for backwards compat — no longer used for actual storage
TRAINING_QUEUES: Dict[str, List[dict]] = {}

# ═══════════════════════════════════════════════════════════════════════════
#  UNIT DEFINITIONS — unchanged from original
# ═══════════════════════════════════════════════════════════════════════════

UNITS = {
    "pawns": {
        "name":        "👣 Pawns",
        "description": "Untrained conscripts. Weak but disposable.",
        "costs":       {"wood": 2, "bronze": 0, "iron": 0, "xp": 0, "silver": 0},
        "stats":       {"attack": 2, "defense": 1, "health": 10},
        "food_upkeep": 0.3,
        "train_time":  20,
        "min_level":   1,
        "lore":        '"They will die first. That is their purpose." — GameMaster',
    },
    "footmen": {
        "name":        "👹 Footmen",
        "description": "Basic infantry. The backbone of any army.",
        "costs":       {"wood": 5, "bronze": 1, "iron": 0, "xp": 10, "silver": 0},
        "stats":       {"attack": 5, "defense": 3, "health": 20},
        "food_upkeep": 0.5,
        "train_time":  30,
        "min_level":   1,
        "lore":        '"They bleed. They die. They hold the line." — GameMaster',
    },
    "archers": {
        "name":        "🏹 Archers",
        "description": "Ranged precision. Strike before they reach you.",
        "costs":       {"wood": 8, "bronze": 2, "iron": 0, "xp": 25, "silver": 0},
        "stats":       {"attack": 8, "defense": 2, "health": 15},
        "food_upkeep": 0.8,
        "train_time":  45,
        "min_level":   2,
        "lore":        '"Distance is the archer\'s dominion." — GameMaster',
    },
    "lancers": {
        "name":        "🗡️ Lancers",
        "description": "Heavy cavalry. Devastating on the charge.",
        "costs":       {"wood": 0, "bronze": 10, "iron": 3, "xp": 50, "silver": 50},
        "stats":       {"attack": 15, "defense": 8, "health": 45},
        "food_upkeep": 1.5,
        "train_time":  60,
        "min_level":   4,
        "lore":        '"When lancers charge, cowards pray." — GameMaster',
    },
    "castellans": {
        "name":        "🏰 Castellans",
        "description": "Elite fortress guards. Near-indestructible defenders.",
        "costs":       {"wood": 0, "bronze": 5, "iron": 15, "xp": 100, "silver": 150},
        "stats":       {"attack": 12, "defense": 25, "health": 100},
        "food_upkeep": 2.5,
        "train_time":  90,
        "min_level":   7,
        "lore":        '"A castellan never retreats. They die at their post." — GameMaster',
    },
    "warlords": {
        "name":        "💀 Warlords",
        "description": "Legendary commanders. One equals fifty lesser troops.",
        "costs":       {"wood": 0, "bronze": 0, "iron": 30, "xp": 250, "silver": 500},
        "stats":       {"attack": 60, "defense": 40, "health": 300},
        "food_upkeep": 8.0,
        "train_time":  240,
        "min_level":   12,
        "lore":        '"Their name alone breaks enemy morale." — GameMaster',
    },
}

# Backwards compat aliases
UNIT_NAMES     = {k: v["name"]       for k, v in UNITS.items()}
UNIT_COSTS     = {k: v["costs"]      for k, v in UNITS.items()}
TRAINING_TIMES = {k: v["train_time"] for k, v in UNITS.items()}


# ═══════════════════════════════════════════════════════════════════════════
#  CAPACITY HELPERS — unchanged
# ═══════════════════════════════════════════════════════════════════════════

def get_max_queue_size(barracks_level: int) -> int:
    return 5 + (barracks_level * 2)

def get_training_speed_bonus(barracks_level: int) -> float:
    return 1.0 - min(0.5, barracks_level * 0.05)

def get_available_units(player_level: int) -> List[str]:
    return [k for k, v in UNITS.items() if player_level >= v["min_level"]]


# ═══════════════════════════════════════════════════════════════════════════
#  PERSISTENT QUEUE HELPERS
#  FIX 1: read/write from players.training_queue column, not memory dict
# ═══════════════════════════════════════════════════════════════════════════

def _get_queue_from_user(user: dict) -> List[dict]:
    """Load training queue from user dict."""
    from supabase_db import safe_json
    q = safe_json(user.get("training_queue"), default=[])
    return q if isinstance(q, list) else []


def _save_queue_to_db(user_id: str, queue: List[dict]):
    """Persist training queue to players.training_queue column."""
    try:
        from supabase_db import supabase
        supabase.table("players").update(
            {"training_queue": queue}
        ).eq("user_id", str(user_id)).execute()
    except Exception as e:
        print(f"[TRAINING] Queue save error for {user_id}: {e}")


# ═══════════════════════════════════════════════════════════════════════════
#  COST CHECK & DEDUCTION — unchanged from original
# ═══════════════════════════════════════════════════════════════════════════

def check_training_cost(user: dict, unit_type: str, amount: int) -> Tuple[bool, str]:
    if unit_type not in UNITS:
        return False, f"Unknown unit: {unit_type}"

    unit  = UNITS[unit_type]
    level = user.get("level", 1)

    if level < unit["min_level"]:
        return False, (
            f"❌ *{unit['name']}* requires Level {unit['min_level']}.\n"
            f"You are Level {level}. Keep playing to unlock."
        )

    costs     = unit["costs"]
    base_res  = user.get("base_resources", {}) or {}
    resources = base_res.get("resources", {}) or {}
    missing   = []

    for res in ("wood", "bronze", "iron"):
        total = costs.get(res, 0) * amount
        if total > 0 and resources.get(res, 0) < total:
            missing.append(f"{res.capitalize()}: need {total:,}, have {resources.get(res,0):,}")

    xp_cost = costs.get("xp", 0) * amount
    if xp_cost > 0 and user.get("xp", 0) < xp_cost:
        missing.append(f"XP: need {xp_cost:,}, have {user.get('xp',0):,}")

    silver_cost = costs.get("silver", 0) * amount
    if silver_cost > 0 and user.get("silver", 0) < silver_cost:
        missing.append(f"Silver: need {silver_cost:,}, have {user.get('silver',0):,}")

    if missing:
        return False, "❌ *Insufficient resources:*\n" + "\n".join(f"  • {m}" for m in missing)
    return True, "OK"


def deduct_training_cost(user: dict, unit_type: str, amount: int) -> dict:
    unit      = UNITS[unit_type]
    costs     = unit["costs"]
    base_res  = user.get("base_resources", {}) or {}
    resources = base_res.get("resources", {}) or {}

    for res in ("wood", "bronze", "iron"):
        total = costs.get(res, 0) * amount
        if total > 0:
            resources[res] = max(0, resources.get(res, 0) - total)

    base_res["resources"] = resources
    user["base_resources"] = base_res

    xp_cost = costs.get("xp", 0) * amount
    if xp_cost > 0:
        user["xp"] = max(0, user.get("xp", 0) - xp_cost)

    silver_cost = costs.get("silver", 0) * amount
    if silver_cost > 0:
        user["silver"] = max(0, user.get("silver", 0) - silver_cost)

    return user


# ═══════════════════════════════════════════════════════════════════════════
#  ADD TO QUEUE — FIX 1 applied: saves to DB, not memory dict
# ═══════════════════════════════════════════════════════════════════════════

def add_to_training_queue(user_id: str, unit_type: str, amount: int) -> Tuple[bool, str]:
    user_id = str(user_id)
    user    = get_user(user_id)
    if not user:
        return False, "❌ Player not found."

    if unit_type not in UNITS:
        return False, f"❌ Unknown unit. Available: {', '.join(UNITS)}"

    if not (1 <= amount <= 100):
        return False, "❌ Amount must be 1–100."

    can_afford, err = check_training_cost(user, unit_type, amount)
    if not can_afford:
        return False, err

    unit = UNITS[unit_type]

    # Speed from barracks
    buildings      = user.get("buildings", {}) or {}
    barracks_level = buildings.get("barracks", 1)
    if isinstance(barracks_level, dict):
        barracks_level = barracks_level.get("level", 1)
    speed_mult  = get_training_speed_bonus(barracks_level)
    actual_time = max(5, int(unit["train_time"] * amount * speed_mult))

    # Deduct costs and persist user
    user = deduct_training_cost(user, unit_type, amount)
    save_user(user_id, user)

    # Append to persistent queue
    queue        = _get_queue_from_user(user)
    completes_at = (datetime.utcnow() + timedelta(seconds=actual_time)).isoformat()
    queue.append({
        "unit_type":    unit_type,
        "amount":       amount,
        "started_at":   datetime.utcnow().isoformat(),
        "completes_at": completes_at,
    })
    _save_queue_to_db(user_id, queue)

    # Also mirror to in-memory dict for any legacy code that reads it
    TRAINING_QUEUES[user_id] = queue

    costs     = unit["costs"]
    cost_parts = []
    for res in ("wood", "bronze", "iron"):
        v = costs.get(res, 0) * amount
        if v:
            cost_parts.append(f"{v:,} {res}")
    if costs.get("xp", 0) * amount:
        cost_parts.append(f"{costs['xp']*amount:,} XP")
    if costs.get("silver", 0) * amount:
        cost_parts.append(f"{costs['silver']*amount:,} silver")

    cost_str = " • ".join(cost_parts) if cost_parts else "Free"
    m, s     = divmod(actual_time, 60)
    time_str = f"{m}m {s}s" if m else f"{s}s"

    return True, (
        f"⚔️ *TRAINING INITIATED*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{unit['name']} × {amount}\n"
        f"💸 Cost: {cost_str}\n"
        f"⏱️ Completes in: {time_str}\n"
        f"🏛️ Barracks Lv.{barracks_level}"
        + (" (speed bonus)" if barracks_level > 1 else "") + "\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🃏 _{unit.get('lore', '')}_"
    )


# ═══════════════════════════════════════════════════════════════════════════
#  PROCESS QUEUE — FIX 1 applied: reads from DB, writes back to DB
# ═══════════════════════════════════════════════════════════════════════════

def process_training_queue(user_id: str) -> Dict:
    user_id = str(user_id)
    user    = get_user(user_id)
    if not user:
        return {"ok": False, "completed": {}}

    queue     = _get_queue_from_user(user)
    now       = datetime.utcnow()
    completed = []
    remaining = []

    for item in queue:
        try:
            done = datetime.fromisoformat(item["completes_at"])
            if now >= done:
                completed.append(item)
            else:
                remaining.append(item)
        except Exception:
            remaining.append(item)

    if not completed:
        TRAINING_QUEUES[user_id] = remaining
        return {"ok": True, "completed": {}}

    military = user.get("military", {}) or {}
    summary  = {}
    for item in completed:
        ut  = item["unit_type"]
        amt = item["amount"]
        military[ut] = military.get(ut, 0) + amt
        summary[ut]  = summary.get(ut, 0) + amt

    user["military"]       = military
    user["training_queue"] = remaining
    save_user(user_id, user)
    _save_queue_to_db(user_id, remaining)
    TRAINING_QUEUES[user_id] = remaining

    return {"ok": True, "completed": summary}


def get_training_status(user_id: str) -> Dict:
    result = process_training_queue(user_id)
    user   = get_user(str(user_id))
    queue  = _get_queue_from_user(user) if user else []
    return {"queue": queue, "completed_this_call": result.get("completed", {})}


# ═══════════════════════════════════════════════════════════════════════════
#  DISPLAY — uses formatting.format_training_queue as original intended
# ═══════════════════════════════════════════════════════════════════════════

def format_training_status(user_id: str) -> str:
    """Full training status with progress bars. Used in training menu."""
    from formatting import format_training_queue, thin_divider
    status    = get_training_status(user_id)
    queue     = status["queue"]
    completed = status["completed_this_call"]
    lines     = []

    if completed:
        lines.append("✅ *TRAINING COMPLETE!*")
        for utype, amt in completed.items():
            name = UNITS.get(utype, {}).get("name", utype)
            lines.append(f"  {name} ×{amt} — now ready for battle!")
        lines.append("")

    lines.append(format_training_queue(queue))

    if not queue and not completed:
        lines.append("")
        lines.append("_Use_ `!train [unit] [amount]` _to build your army._")
        user = get_user(str(user_id))
        if user:
            level   = user.get("level", 1)
            unlocked = get_available_units(level)
            lines.append(f"\n⚔️ *Available at Level {level}:*")
            for utype in unlocked:
                u = UNITS[utype]
                lines.append(f"  {u['name']} — `!train {utype} [amount]`")

    return "\n".join(lines)


def get_training_queue_display(user_id: str) -> str:
    """
    FIX 2 — was missing but called from main.py _render_main_hud.
    Compact progress bars for the HUD dashboard.
    Returns empty string when nothing is training.
    """
    from formatting import format_training_queue
    result = process_training_queue(str(user_id))
    user   = get_user(str(user_id))
    if not user:
        return ""
    queue = _get_queue_from_user(user)
    if not queue and not result.get("completed"):
        return ""
    return format_training_queue(queue)


def format_unit_catalog(player_level: int, user: dict = None) -> str:
    """Full unit catalog with costs and lock status."""
    lines = ["⚔️ *UNIT CATALOG*", "━" * 32,
             "_Train troops to defend your base and raid enemies._", ""]
    for utype, unit in UNITS.items():
        locked   = player_level < unit["min_level"]
        status   = f"🔒 Level {unit['min_level']}" if locked else "✅ Available"
        costs    = unit["costs"]
        cp       = []
        for res in ("wood", "bronze", "iron"):
            if costs.get(res, 0):
                cp.append(f"{costs[res]} {res}")
        if costs.get("xp", 0):
            cp.append(f"{costs['xp']} XP")
        if costs.get("silver", 0):
            cp.append(f"{costs['silver']} silver")
        cost_str = " + ".join(cp) if cp else "Free"
        secs     = unit["train_time"]
        time_str = f"{secs//60}m {secs%60}s" if secs >= 60 else f"{secs}s"
        stats    = unit["stats"]

        lines += [
            f"{unit['name']} [{status}]",
            f"  _{unit['description']}_",
            f"  💸 Cost/unit: {cost_str}",
            f"  ⏱️  Time/unit: {time_str}",
            f"  ⚔️  ATK:{stats['attack']} DEF:{stats['defense']} HP:{stats['health']}",
            f"  🥫 Upkeep: {unit['food_upkeep']}/hr",
            "",
        ]

    lines += ["─" * 32, "Use `!train [unit] [amount]` to recruit"]
    return "\n".join(lines)


def complete_all_trainings(user_id: str) -> Dict:
    """Force-complete all training (admin/testing)."""
    user_id = str(user_id)
    user    = get_user(user_id)
    if not user:
        return {"success": False}

    queue    = _get_queue_from_user(user)
    military = user.get("military", {}) or {}
    completed = {}

    for item in queue:
        ut  = item["unit_type"]
        amt = item["amount"]
        military[ut] = military.get(ut, 0) + amt
        completed[ut] = completed.get(ut, 0) + amt

    user["military"]       = military
    user["training_queue"] = []
    save_user(user_id, user)
    _save_queue_to_db(user_id, [])
    TRAINING_QUEUES[user_id] = []

    return {"success": True, "completed": completed,
            "total": sum(completed.values())}
