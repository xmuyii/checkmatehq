"""
build_system.py — Base Building System
=======================================
Buildings upgrade base capabilities. Each building has levels 1-10.

BASE LEVEL caps (driven by XP level, not a separate building):
  XP level 1-4  → base level 1
  XP level 5-9  → base level 2
  Every 5 levels → +1 base level  (max base level 10)

Troop capacity:  base_level × 1000  (level 1 = 1000, level 10 = 10000)
Trap capacity:   base_level × 500   (level 1 = 500,  level 10 = 5000)
Resource cap:    base_level × 1000  per resource type (level 1 = 1000, level 10 = 10000)
  — Storage building can multiply this cap.
"""

from typing import Dict, Tuple

# ═══════════════════════════════════════════════════════════════════════════
#  BUILDING CATALOGUE
# ═══════════════════════════════════════════════════════════════════════════

BUILDING_TYPES: Dict[str, dict] = {

    # ── Military ──────────────────────────────────────────────────────────
    "training_grounds": {
        "name":        "⚔️ Training Grounds",
        "description": "Increases troop capacity. Each level adds 500 soldier slots.",
        "category":    "military",
        "unlock_base_level": 1,
        "max_level":   10,
        "cost_per_level": lambda lvl: {
            "wood":   100 * lvl,
            "bronze": 50  * lvl,
            "iron":   20  * lvl,
        },
        "bonus": lambda lvl: {"extra_troop_capacity": 500 * lvl},
        "build_time_secs": lambda lvl: 60 * lvl,          # 1 min per level
    },

    "cemetery": {
        "name":        "⚰️ Cemetery",
        "description": "Honours fallen kings. Reduces morale penalty after defeats. "
                       "Each level stores 100 fallen king records and grants +5% defence bonus.",
        "category":    "military",
        "unlock_base_level": 1,
        "max_level":   10,
        "cost_per_level": lambda lvl: {
            "wood":   80  * lvl,
            "bronze": 40  * lvl,
            "iron":   10  * lvl,
        },
        "bonus": lambda lvl: {
            "fallen_king_records":  100 * lvl,
            "defence_bonus_pct":      5 * lvl,
        },
        "build_time_secs": lambda lvl: 45 * lvl,
    },

    "barracks": {
        "name":        "🏕️ Barracks",
        "description": "Speeds up troop training. Each level reduces training time by 10%.",
        "category":    "military",
        "unlock_base_level": 1,
        "max_level":   10,
        "cost_per_level": lambda lvl: {
            "wood":   120 * lvl,
            "bronze": 60  * lvl,
            "iron":   25  * lvl,
        },
        "bonus": lambda lvl: {"training_time_reduction_pct": 10 * lvl},
        "build_time_secs": lambda lvl: 90 * lvl,
    },

    "armory": {
        "name":        "🛡️ Armory",
        "description": "Reduces deploy time for defensive items and troops. "
                       "Each level cuts deploy time by 5 seconds (min 5 s).",
        "category":    "military",
        "unlock_base_level": 2,
        "max_level":   10,
        "cost_per_level": lambda lvl: {
            "bronze": 80  * lvl,
            "iron":   40  * lvl,
            "diamond": 5  * lvl,
        },
        "bonus": lambda lvl: {"deploy_speedup_secs": 5 * lvl},
        "build_time_secs": lambda lvl: 120 * lvl,
    },

    "war_room": {
        "name":        "🗺️ War Room",
        "description": "Reduces attack cooldown. Each level cuts attack cooldown by 10 minutes.",
        "category":    "military",
        "unlock_base_level": 3,
        "max_level":   10,
        "cost_per_level": lambda lvl: {
            "bronze": 100 * lvl,
            "iron":   60  * lvl,
            "diamond": 8  * lvl,
        },
        "bonus": lambda lvl: {"attack_cooldown_reduction_mins": 10 * lvl},
        "build_time_secs": lambda lvl: 150 * lvl,
    },

    "infirmary": {
        "name":        "🏥 Infirmary",
        "description": "Recovers wounded troops after battle. Each level recovers 5% more troops.",
        "category":    "military",
        "unlock_base_level": 2,
        "max_level":   10,
        "cost_per_level": lambda lvl: {
            "wood":   90  * lvl,
            "bronze": 45  * lvl,
        },
        "bonus": lambda lvl: {"troop_recovery_pct": 5 * lvl},
        "build_time_secs": lambda lvl: 60 * lvl,
    },

    # ── Resources ─────────────────────────────────────────────────────────
    "storage": {
        "name":        "🏦 Storage",
        "description": "Increases resource cap per type. Each level adds 1000 to each resource cap.",
        "category":    "resources",
        "unlock_base_level": 1,
        "max_level":   10,
        "cost_per_level": lambda lvl: {
            "wood":   150 * lvl,
            "bronze": 70  * lvl,
        },
        "bonus": lambda lvl: {"resource_cap_bonus": 1000 * lvl},
        "build_time_secs": lambda lvl: 60 * lvl,
    },

    "mine": {
        "name":        "⛏️ Mine",
        "description": "Passively generates resources over time. Each level adds 10 of each resource/hour.",
        "category":    "resources",
        "unlock_base_level": 1,
        "max_level":   10,
        "cost_per_level": lambda lvl: {
            "wood":   100 * lvl,
            "iron":   20  * lvl,
        },
        "bonus": lambda lvl: {"passive_resources_per_hour": 10 * lvl},
        "build_time_secs": lambda lvl: 90 * lvl,
    },

    "farm": {
        "name":        "🌾 Farm",
        "description": "Produces food to sustain troops. Each level adds 50 food/hour.",
        "category":    "resources",
        "unlock_base_level": 1,
        "max_level":   10,
        "cost_per_level": lambda lvl: {
            "wood":   80  * lvl,
            "bronze": 20  * lvl,
        },
        "bonus": lambda lvl: {"food_per_hour": 50 * lvl},
        "build_time_secs": lambda lvl: 45 * lvl,
    },

    # ── Defence ───────────────────────────────────────────────────────────
    "trap_factory": {
        "name":        "🔩 Trap Factory",
        "description": "Increases trap capacity. Each level adds 250 trap slots.",
        "category":    "defence",
        "unlock_base_level": 2,
        "max_level":   10,
        "cost_per_level": lambda lvl: {
            "bronze": 60  * lvl,
            "iron":   30  * lvl,
        },
        "bonus": lambda lvl: {"extra_trap_capacity": 250 * lvl},
        "build_time_secs": lambda lvl: 75 * lvl,
    },

    "watchtower": {
        "name":        "🗼 Watchtower",
        "description": "Early warning: reveals when a scout is sent against you. "
                       "Each level increases scout detection range.",
        "category":    "defence",
        "unlock_base_level": 2,
        "max_level":   10,
        "cost_per_level": lambda lvl: {
            "wood":   100 * lvl,
            "bronze": 50  * lvl,
        },
        "bonus": lambda lvl: {"scout_detection_bonus": lvl},
        "build_time_secs": lambda lvl: 90 * lvl,
    },

    "walls": {
        "name":        "🧱 Walls",
        "description": "Reduces resource stolen per raid. Each level saves 5% more resources.",
        "category":    "defence",
        "unlock_base_level": 1,
        "max_level":   10,
        "cost_per_level": lambda lvl: {
            "wood":   200 * lvl,
            "stone":  50  * lvl,
            "iron":   10  * lvl,
        },
        "bonus": lambda lvl: {"raid_resource_protection_pct": 5 * lvl},
        "build_time_secs": lambda lvl: 120 * lvl,
    },
}


# ═══════════════════════════════════════════════════════════════════════════
#  BASE LEVEL FORMULA
# ═══════════════════════════════════════════════════════════════════════════

def get_base_level(xp_level: int) -> int:
    """Convert XP level to base level (1-10)."""
    if xp_level < 5:
        return 1
    return min(10, 1 + (xp_level - 1) // 5)


# ═══════════════════════════════════════════════════════════════════════════
#  CAPACITY CALCULATIONS
# ═══════════════════════════════════════════════════════════════════════════

def get_troop_capacity(xp_level: int, buildings: dict) -> int:
    """Max soldiers this base can hold."""
    base_lvl   = get_base_level(xp_level)
    base_cap   = base_lvl * 1000
    tg_level   = buildings.get("training_grounds", 0)
    tg_bonus   = BUILDING_TYPES["training_grounds"]["bonus"](tg_level)["extra_troop_capacity"] if tg_level > 0 else 0
    return base_cap + tg_bonus


def get_trap_capacity(xp_level: int, buildings: dict) -> int:
    """Max traps this base can hold."""
    base_lvl   = get_base_level(xp_level)
    base_cap   = base_lvl * 500
    tf_level   = buildings.get("trap_factory", 0)
    tf_bonus   = BUILDING_TYPES["trap_factory"]["bonus"](tf_level)["extra_trap_capacity"] if tf_level > 0 else 0
    return base_cap + tf_bonus


def get_resource_cap(xp_level: int, buildings: dict) -> int:
    """Max of each resource type this base can store."""
    base_lvl   = get_base_level(xp_level)
    base_cap   = base_lvl * 1000
    st_level   = buildings.get("storage", 0)
    st_bonus   = BUILDING_TYPES["storage"]["bonus"](st_level)["resource_cap_bonus"] if st_level > 0 else 0
    return base_cap + st_bonus


def get_training_speedup_pct(buildings: dict) -> int:
    """Percentage reduction in training time from Barracks."""
    br_level = buildings.get("barracks", 0)
    if br_level == 0:
        return 0
    return BUILDING_TYPES["barracks"]["bonus"](br_level)["training_time_reduction_pct"]


def get_attack_cooldown_reduction_mins(buildings: dict) -> int:
    """Minutes cut from attack cooldown by War Room."""
    wr_level = buildings.get("war_room", 0)
    if wr_level == 0:
        return 0
    return BUILDING_TYPES["war_room"]["bonus"](wr_level)["attack_cooldown_reduction_mins"]


def get_deploy_speedup_secs(buildings: dict) -> int:
    """Seconds cut from defence deploy time by Armory."""
    am_level = buildings.get("armory", 0)
    if am_level == 0:
        return 0
    return BUILDING_TYPES["armory"]["bonus"](am_level)["deploy_speedup_secs"]


def get_troop_recovery_pct(buildings: dict) -> int:
    """Percentage of troops recovered after battle by Infirmary."""
    inf_level = buildings.get("infirmary", 0)
    if inf_level == 0:
        return 0
    return BUILDING_TYPES["infirmary"]["bonus"](inf_level)["troop_recovery_pct"]


def get_defence_bonus_pct(buildings: dict) -> int:
    """Percentage defence bonus from Cemetery."""
    cem_level = buildings.get("cemetery", 0)
    if cem_level == 0:
        return 0
    return BUILDING_TYPES["cemetery"]["bonus"](cem_level)["defence_bonus_pct"]


def apply_building_bonuses(user: dict) -> dict:
    """
    Return a dict of all active building bonuses for a player.
    Attach to user dict so attack/defence/training code can read it.
    """
    xp_level  = user.get("level", 1)
    buildings = user.get("buildings", {})
    if not isinstance(buildings, dict):
        buildings = {}
    return {
        "troop_capacity":          get_troop_capacity(xp_level, buildings),
        "trap_capacity":           get_trap_capacity(xp_level, buildings),
        "resource_cap":            get_resource_cap(xp_level, buildings),
        "training_speedup_pct":    get_training_speedup_pct(buildings),
        "attack_cooldown_reduction_mins": get_attack_cooldown_reduction_mins(buildings),
        "deploy_speedup_secs":     get_deploy_speedup_secs(buildings),
        "troop_recovery_pct":      get_troop_recovery_pct(buildings),
        "defence_bonus_pct":       get_defence_bonus_pct(buildings),
    }


# ═══════════════════════════════════════════════════════════════════════════
#  BUILDING HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def get_available_buildings(xp_level: int) -> list:
    """Return list of building IDs unlocked at this XP level."""
    base_lvl = get_base_level(xp_level)
    return [
        bid for bid, bdata in BUILDING_TYPES.items()
        if bdata["unlock_base_level"] <= base_lvl
    ]


def can_build_building(building_id: str, xp_level: int) -> Tuple[bool, str]:
    """Check if this building is available at the player's XP level."""
    if building_id not in BUILDING_TYPES:
        return False, f"Unknown building: {building_id}"
    bdata    = BUILDING_TYPES[building_id]
    base_lvl = get_base_level(xp_level)
    if bdata["unlock_base_level"] > base_lvl:
        return False, (
            f"Requires base level {bdata['unlock_base_level']} "
            f"(you are base level {base_lvl})"
        )
    return True, "OK"


def calculate_building_cost(building_id: str, target_level: int) -> dict:
    """Return resource cost to build/upgrade to target_level."""
    if building_id not in BUILDING_TYPES:
        return {}
    cost_fn = BUILDING_TYPES[building_id]["cost_per_level"]
    return cost_fn(target_level)


def get_build_time(building_id: str, target_level: int, buildings: dict) -> int:
    """
    Return build time in seconds, reduced by speedup items or Armory.
    """
    if building_id not in BUILDING_TYPES:
        return 60
    raw_secs    = BUILDING_TYPES[building_id]["build_time_secs"](target_level)
    armory_save = get_deploy_speedup_secs(buildings)
    return max(5, raw_secs - armory_save)


def format_buildings_menu(xp_level: int, current_buildings: dict) -> str:
    """Format a text menu of all available buildings with costs and bonuses."""
    available = get_available_buildings(xp_level)
    base_lvl  = get_base_level(xp_level)

    lines = [
        f"🏗️ *BASE BUILDINGS* (Base Level {base_lvl})",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    categories = {"military": "⚔️ Military", "resources": "📦 Resources", "defence": "🛡️ Defence"}
    for cat_key, cat_label in categories.items():
        cat_buildings = [b for b in available if BUILDING_TYPES[b]["category"] == cat_key]
        if not cat_buildings:
            continue
        lines.append(f"\n*{cat_label}*")
        for bid in cat_buildings:
            bdata     = BUILDING_TYPES[bid]
            cur_level = current_buildings.get(bid, 0)
            next_lvl  = cur_level + 1
            cost      = calculate_building_cost(bid, next_lvl)
            cost_str  = " + ".join(f"{v} {k}" for k, v in cost.items())
            bonus     = bdata["bonus"](next_lvl)
            bonus_str = ", ".join(f"+{v} {k.replace('_', ' ')}" for k, v in bonus.items())
            lines.append(
                f"  {bdata['name']} Lv{cur_level}→{next_lvl}\n"
                f"  💰 {cost_str}\n"
                f"  ✨ {bonus_str}"
            )

    lines.append(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("Use `/build [building_name]` to construct.")
    return "\n".join(lines)
