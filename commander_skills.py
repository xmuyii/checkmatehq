# -*- coding: utf-8 -*-
"""
commander_skills.py — Commander Skill Tree System
==================================================
4 developmental paths unique to The 64 Game's world.
Each commander level = 1 skill point (level 100 = 100 points).
Points can be freely reset — encourages experimentation.
Locked behind commander_doctrine research.

THE FOUR PATHS:
  ⚡ VOLT        — Electronic warfare, scouting, jamming, traps
  🔥 INCENDIARY  — Attack power, raids, node conquest, scorched earth
  🧬 RECON       — Resource efficiency, collection speed, node capacity
  🛡️ BULWARK     — Defense, shields, troop survival, bunker mode

PROGRESSION MODEL (Sellers):
  Each path has 5 tiers. Within a path, tiers must be unlocked in order.
  Players CANNOT unlock Tier 3 without Tier 2 in the same path.
  Cross-path: no restrictions — you can be Volt T3 + Incendiary T1 simultaneously.
  This creates genuine build diversity and meta-game discussion.

RESET MECHANIC:
  Free reset at any time. Points returned to unspent pool.
  Encourages players to adapt to different objectives without punishment.
  A war declaration might trigger a full respec from Recon to Incendiary.
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ═══════════════════════════════════════════════════════════════════════════
#  SKILL TREE DEFINITION
# ═══════════════════════════════════════════════════════════════════════════

SKILL_PATHS: Dict[str, dict] = {

    # ── ⚡ VOLT PATH ──────────────────────────────────────────────────────
    # Intelligence, deception, electronic warfare.
    # The spy's path. Volt players know everything before they act.
    # High skill ceiling — rewards patience and information advantage.
    "volt": {
        "name":        "⚡ VOLT",
        "tagline":     "Know everything. Leave no trace.",
        "color_emoji": "⚡",
        "description": "Electronic warfare and intelligence mastery. "
                       "Volt commanders see more, reveal less, and vanish without a trace.",
        "tiers": [
            {
                "tier":        1,
                "name":        "Signal Awareness",
                "cost":        5,
                "description": "Scout missions return 2 minutes faster. "
                               "You see incoming march alerts 30 seconds earlier than others.",
                "effect_key":  "volt_t1",
                "effects": {
                    "scout_time_reduction_secs": 120,
                    "march_alert_early_secs":    30,
                },
                "power_value": 200,
            },
            {
                "tier":        2,
                "name":        "Ghost Protocol",
                "cost":        10,
                "description": "20% chance your scout avoids mousetraps. "
                               "When you teleport into a sector, your arrival is NOT logged "
                               "in the sector event feed for 5 minutes.",
                "effect_key":  "volt_t2",
                "effects": {
                    "scout_trap_avoid_pct":     0.20,
                    "arrival_stealth_minutes":  5,
                },
                "power_value": 400,
            },
            {
                "tier":        3,
                "name":        "Firewall Mastery",
                "cost":        20,
                "description": "Your firewall intercept rate rises to 70% (from 50%). "
                               "Incoming scouts that fail to intercept still reveal "
                               "fake stats 80% of the time.",
                "effect_key":  "volt_t3",
                "effects": {
                    "firewall_intercept_pct":   0.70,
                    "fake_stats_pct":           0.80,
                },
                "power_value": 700,
            },
            {
                "tier":        4,
                "name":        "Cross-Sector Vision",
                "cost":        30,
                "description": "You can scout players in adjacent sectors without teleporting there. "
                               "Scout arrives in 8 minutes instead of 5. "
                               "Costs 50% more silver.",
                "effect_key":  "volt_t4",
                "effects": {
                    "adjacent_sector_scout":    True,
                    "adjacent_scout_time_mins": 8,
                    "adjacent_scout_cost_mult": 1.5,
                },
                "power_value": 1100,
            },
            {
                "tier":        5,
                "name":        "Sector Jammer",
                "cost":        35,
                "description": "ULTIMATE: Jam an entire sector for 3 minutes. "
                               "Sector chat, event feed, and node map all go dark. "
                               "Your actions in this window leave no trace. "
                               "6-hour cooldown. Ruler is alerted but not told who.",
                "effect_key":  "volt_t5",
                "effects": {
                    "jam_duration_secs":   180,
                    "jam_cooldown_secs":   21600,
                    "jam_untraceable":     True,
                },
                "power_value": 1800,
                "ultimate":    True,
            },
        ],
    },

    # ── 🔥 INCENDIARY PATH ────────────────────────────────────────────────
    # Aggression, raids, conquest.
    # The warlord's path. Incendiary players hit harder and move faster.
    # Straightforward high-reward — rewards aggression and timing.
    "incendiary": {
        "name":        "🔥 INCENDIARY",
        "tagline":     "Hit first. Hit hardest. Take everything.",
        "color_emoji": "🔥",
        "description": "Offensive doctrine and raid mastery. "
                       "Incendiary commanders strike without warning and leave ruins behind.",
        "tiers": [
            {
                "tier":        1,
                "name":        "Combat Training",
                "cost":        5,
                "description": "+10% attack power in all battles. "
                               "Your battle reports show more detailed enemy troop counts.",
                "effect_key":  "incendiary_t1",
                "effects": {
                    "attack_power_bonus_pct": 0.10,
                    "detailed_battle_report": True,
                },
                "power_value": 200,
            },
            {
                "tier":        2,
                "name":        "Rapid Advance",
                "cost":        10,
                "description": "March time to nodes reduced by 20%. "
                               "Speedup items are 25% more effective on your marches.",
                "effect_key":  "incendiary_t2",
                "effects": {
                    "march_time_reduction_pct": 0.20,
                    "speedup_bonus_pct":        0.25,
                },
                "power_value": 400,
            },
            {
                "tier":        3,
                "name":        "Plunder Expert",
                "cost":        20,
                "description": "Steal 60% of resources on raid victory (up from 50%). "
                               "Your carrying capacity increases by 30%.",
                "effect_key":  "incendiary_t3",
                "effects": {
                    "raid_steal_pct":      0.60,
                    "carry_capacity_mult": 1.30,
                },
                "power_value": 700,
            },
            {
                "tier":        4,
                "name":        "Blitzkrieg",
                "cost":        30,
                "description": "Once every 24 hours: instant node breach — "
                               "attack a node without marching time. "
                               "The defender gets zero warning.",
                "effect_key":  "incendiary_t4",
                "effects": {
                    "instant_breach_daily": True,
                    "breach_cooldown_hrs":  24,
                },
                "power_value": 1100,
            },
            {
                "tier":        5,
                "name":        "Scorched Earth",
                "cost":        35,
                "description": "ULTIMATE: When you voluntarily leave a node, "
                               "activate Scorched Earth — the node yields 30% less "
                               "for the next 2 hours for whoever takes it. "
                               "Use !scorch before teleporting. Pure spite. Pure power.",
                "effect_key":  "incendiary_t5",
                "effects": {
                    "scorch_yield_reduction_pct": 0.30,
                    "scorch_duration_hours":      2,
                },
                "power_value": 1800,
                "ultimate":    True,
            },
        ],
    },

    # ── 🧬 RECON PATH ────────────────────────────────────────────────────
    # Resource efficiency, collection, node management.
    # The economist's path. Recon players are rich while others are fighting.
    # Indirect power — rewards patience and long-term thinking.
    "recon": {
        "name":        "🧬 RECON",
        "tagline":     "While they fight, you collect.",
        "color_emoji": "🧬",
        "description": "Resource intelligence and extraction mastery. "
                       "Recon commanders turn sectors into personal treasuries.",
        "tiers": [
            {
                "tier":        1,
                "name":        "Efficient Extraction",
                "cost":        5,
                "description": "+15% resource yield from all nodes. "
                               "Node pending resource capacity increases by 25%.",
                "effect_key":  "recon_t1",
                "effects": {
                    "node_yield_bonus_pct":    0.15,
                    "node_capacity_bonus_pct": 0.25,
                },
                "power_value": 200,
            },
            {
                "tier":        2,
                "name":        "Accelerated Mining",
                "cost":        10,
                "description": "Resources tick 20% faster at nodes you occupy. "
                               "Sector resource buffs apply to you at 1.5× the normal rate.",
                "effect_key":  "recon_t2",
                "effects": {
                    "tick_speed_bonus_pct":   0.20,
                    "sector_buff_mult":       1.50,
                },
                "power_value": 400,
            },
            {
                "tier":        3,
                "name":        "Dual Occupation",
                "cost":        20,
                "description": "You can occupy 2 nodes simultaneously in the same sector. "
                               "This is the most economically powerful ability in the game. "
                               "Other players cannot do this.",
                "effect_key":  "recon_t3",
                "effects": {
                    "max_nodes_occupied": 2,
                },
                "power_value": 700,
            },
            {
                "tier":        4,
                "name":        "Auto-Collector",
                "cost":        30,
                "description": "When a node reaches 80% capacity, resources auto-collect "
                               "into your inventory without you having to press collect. "
                               "You never lose resources to a full node again.",
                "effect_key":  "recon_t4",
                "effects": {
                    "auto_collect_threshold_pct": 0.80,
                },
                "power_value": 1100,
            },
            {
                "tier":        5,
                "name":        "Resource Sense",
                "cost":        35,
                "description": "ULTIMATE: Before occupying a node, you can see exactly "
                               "how many resources are pending there AND which nodes in "
                               "the sector have the highest current yield multiplier. "
                               "Pure intelligence advantage for resource decisions.",
                "effect_key":  "recon_t5",
                "effects": {
                    "see_node_pending_before_occupy": True,
                    "see_sector_yield_map":           True,
                },
                "power_value": 1800,
                "ultimate":    True,
            },
        ],
    },

    # ── 🛡️ BULWARK PATH ────────────────────────────────────────────────
    # Defense, survival, shield management.
    # The fortress path. Bulwark commanders are nearly impossible to dislodge.
    # Defensive mastery — rewards staying power and base management.
    "bulwark": {
        "name":        "🛡️ BULWARK",
        "tagline":     "They will break on you.",
        "color_emoji": "🛡️",
        "description": "Defensive mastery and survival doctrine. "
                       "Bulwark commanders turn their positions into fortresses "
                       "that bleed attackers dry.",
        "tiers": [
            {
                "tier":        1,
                "name":        "Reinforced Shields",
                "cost":        5,
                "description": "All shield durations +25%. "
                               "When your shield expires, you get a 30-minute warning "
                               "DM before it drops (others get no warning).",
                "effect_key":  "bulwark_t1",
                "effects": {
                    "shield_duration_bonus_pct": 0.25,
                    "shield_expiry_warning_mins": 30,
                },
                "power_value": 200,
            },
            {
                "tier":        2,
                "name":        "Hardened Garrison",
                "cost":        10,
                "description": "Troop survival rate in hazard phase ticks +30% "
                               "(fewer troops die per penalty tick). "
                               "Defender first-strike bonus: +15% power when defending a node.",
                "effect_key":  "bulwark_t2",
                "effects": {
                    "hazard_troop_survival_bonus_pct": 0.30,
                    "defender_first_strike_bonus_pct": 0.15,
                },
                "power_value": 400,
            },
            {
                "tier":        3,
                "name":        "Fortified Position",
                "cost":        20,
                "description": "Attackers who lose against you at a node take "
                               "an extra 10% casualties. "
                               "Your traps at home base deal 20% more damage.",
                "effect_key":  "bulwark_t3",
                "effects": {
                    "attacker_extra_casualty_pct": 0.10,
                    "trap_damage_bonus_pct":       0.20,
                },
                "power_value": 700,
            },
            {
                "tier":        4,
                "name":        "Bunker Mode",
                "cost":        30,
                "description": "When you are on your home node (base plot), "
                               "sector hazard phases CANNOT eject you. "
                               "Your base is immune to the environment. "
                               "Field operations still take hazard damage.",
                "effect_key":  "bulwark_t4",
                "effects": {
                    "home_node_hazard_immune": True,
                },
                "power_value": 1100,
            },
            {
                "tier":        5,
                "name":        "Last Stand",
                "cost":        35,
                "description": "ULTIMATE: When your troops at a node drop below 20%, "
                               "they fight at 2× power. The closer to death, "
                               "the more dangerous you become. "
                               "Attackers who trigger this rarely survive.",
                "effect_key":  "bulwark_t5",
                "effects": {
                    "last_stand_threshold_pct": 0.20,
                    "last_stand_power_mult":    2.0,
                },
                "power_value": 1800,
                "ultimate":    True,
            },
        ],
    },
}

# Total skill points per path if fully maxed
MAX_POINTS_PER_PATH = sum(t["cost"] for t in SKILL_PATHS["volt"]["tiers"])   # = 100


# ═══════════════════════════════════════════════════════════════════════════
#  SKILL POINT MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

def get_total_skill_points(user: dict) -> int:
    """Total skill points = commander level. Level 100 = 100 points."""
    level = user.get("level", 1)
    return max(0, level)


def get_spent_points(user: dict) -> Dict[str, int]:
    """Points spent per path."""
    spent = user.get("skill_points_spent", {})
    if not isinstance(spent, dict):
        spent = {}
    return {
        "volt":        spent.get("volt", 0),
        "incendiary":  spent.get("incendiary", 0),
        "recon":       spent.get("recon", 0),
        "bulwark":     spent.get("bulwark", 0),
    }


def get_unspent_points(user: dict) -> int:
    """Points available to spend."""
    total = get_total_skill_points(user)
    spent = get_spent_points(user)
    return max(0, total - sum(spent.values()))


def get_unlocked_tiers(user: dict, path: str) -> List[int]:
    """Get list of unlocked tier numbers for a path (1-indexed)."""
    spent = get_spent_points(user)
    path_spent = spent.get(path, 0)
    tiers      = SKILL_PATHS[path]["tiers"]
    unlocked   = []
    cumulative = 0
    for tier_data in tiers:
        cumulative += tier_data["cost"]
        if path_spent >= cumulative:
            unlocked.append(tier_data["tier"])
    return unlocked


def get_highest_unlocked_tier(user: dict, path: str) -> int:
    """Get highest unlocked tier for a path (0 = none unlocked)."""
    unlocked = get_unlocked_tiers(user, path)
    return max(unlocked) if unlocked else 0


def has_skill(user: dict, effect_key: str) -> bool:
    """Check if a player has a specific skill effect unlocked."""
    for path_key, path_data in SKILL_PATHS.items():
        for tier in path_data["tiers"]:
            if tier["effect_key"] == effect_key:
                target_tier = tier["tier"]
                return target_tier in get_unlocked_tiers(user, path_key)
    return False


def get_skill_effect(user: dict, effect_key: str) -> Optional[dict]:
    """Get the effects dict for a skill if unlocked, else None."""
    for path_key, path_data in SKILL_PATHS.items():
        for tier in path_data["tiers"]:
            if tier["effect_key"] == effect_key:
                target_tier = tier["tier"]
                if target_tier in get_unlocked_tiers(user, path_key):
                    return tier["effects"]
    return None


def allocate_skill_points(
    user: dict,
    path: str,
    tier_target: int,
) -> Tuple[bool, str, dict]:
    """
    Allocate points to unlock a specific tier in a path.
    Must unlock tiers in order (can't skip Tier 2 to get Tier 3).

    Returns (success, message, updated_user)
    """
    from research_tree import is_feature_unlocked
    if not is_feature_unlocked(user, "commander_skill_points"):
        return False, (
            "🔒 Skill tree locked.\n"
            "Research *Commander Doctrine* to unlock skill points."
        ), user

    if path not in SKILL_PATHS:
        return False, f"❌ Unknown path: {path}", user

    tiers = SKILL_PATHS[path]["tiers"]
    if tier_target < 1 or tier_target > len(tiers):
        return False, f"❌ Invalid tier: {tier_target}", user

    # Check already unlocked
    already = get_unlocked_tiers(user, path)
    if tier_target in already:
        return False, f"✅ Already unlocked Tier {tier_target} in {SKILL_PATHS[path]['name']}.", user

    # Check sequential — must have previous tier
    if tier_target > 1 and (tier_target - 1) not in already:
        return False, (
            f"❌ Must unlock Tier {tier_target - 1} first.\n"
            f"You cannot skip tiers within a path."
        ), user

    # Calculate cost of this tier
    tier_data = tiers[tier_target - 1]
    cost      = tier_data["cost"]

    # Check unspent points
    unspent = get_unspent_points(user)
    if unspent < cost:
        return False, (
            f"❌ Not enough skill points.\n"
            f"Need: {cost}  |  Available: {unspent}\n"
            f"Gain points by levelling up."
        ), user

    # Allocate
    spent = user.get("skill_points_spent", {})
    if not isinstance(spent, dict):
        spent = {}
    spent[path] = spent.get(path, 0) + cost
    user["skill_points_spent"] = spent

    path_name = SKILL_PATHS[path]["name"]
    tier_name = tier_data["name"]

    return True, (
        f"⚡ *{tier_name}* unlocked!\n"
        f"Path: {path_name}\n"
        f"Effect: {tier_data['description']}\n"
        f"Remaining points: {get_unspent_points(user)}"
    ), user


def reset_skill_points(user: dict) -> Tuple[bool, str, dict]:
    """
    Reset all skill points. Free of charge.
    All points returned to unspent pool.
    """
    from research_tree import is_feature_unlocked
    if not is_feature_unlocked(user, "commander_skill_points"):
        return False, "🔒 Skill tree not yet unlocked.", user

    user["skill_points_spent"] = {"volt": 0, "incendiary": 0, "recon": 0, "bulwark": 0}

    total = get_total_skill_points(user)
    return True, (
        f"🔄 *All skill points reset.*\n"
        f"You have {total} points to reallocate.\n"
        f"Choose your new path."
    ), user


def get_skill_power_total(user: dict) -> int:
    """Calculate total power contribution from all unlocked skills."""
    total = 0
    for path_key, path_data in SKILL_PATHS.items():
        unlocked = get_unlocked_tiers(user, path_key)
        for tier in path_data["tiers"]:
            if tier["tier"] in unlocked:
                total += tier.get("power_value", 0)
    return total


def get_all_active_effects(user: dict) -> Dict[str, any]:
    """
    Get a flat dict of all active skill effects for a player.
    Used by other systems to check bonuses without knowing which path gave them.

    Example return:
    {
        "attack_power_bonus_pct": 0.10,
        "march_time_reduction_pct": 0.20,
        "node_yield_bonus_pct": 0.15,
        "shield_duration_bonus_pct": 0.25,
        ...
    }
    """
    effects = {}
    for path_key, path_data in SKILL_PATHS.items():
        unlocked = get_unlocked_tiers(user, path_key)
        for tier in path_data["tiers"]:
            if tier["tier"] in unlocked:
                for effect_key, effect_val in tier["effects"].items():
                    # Numeric effects stack additively
                    if isinstance(effect_val, (int, float)) and effect_key in effects:
                        effects[effect_key] = effects[effect_key] + effect_val
                    else:
                        effects[effect_key] = effect_val
    return effects


# ═══════════════════════════════════════════════════════════════════════════
#  INLINE KEYBOARD BUILDERS
# ═══════════════════════════════════════════════════════════════════════════

def kb_skill_tree_main(user: dict) -> InlineKeyboardMarkup:
    """Main skill tree menu — shows all 4 paths with current investment."""
    spent   = get_spent_points(user)
    unspent = get_unspent_points(user)
    buttons = []

    for path_key, path_data in SKILL_PATHS.items():
        path_spent  = spent.get(path_key, 0)
        highest     = get_highest_unlocked_tier(user, path_key)
        max_tier    = len(path_data["tiers"])
        emoji       = path_data["color_emoji"]
        name        = path_data["name"]

        if highest == 0:
            status = "Not started"
        elif highest == max_tier:
            status = "MAXED ✨"
        else:
            status = f"Tier {highest}/{max_tier}"

        buttons.append([
            InlineKeyboardButton(
                f"{emoji} {name} — {status} ({path_spent}pts)",
                callback_data=f"skills:path:{path_key}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            f"🔄 Reset All Points",
            callback_data="skills:reset_confirm"
        ),
        InlineKeyboardButton(
            f"📊 {unspent} pts free",
            callback_data="skills:summary"
        ),
    ])
    buttons.append([InlineKeyboardButton("« Back", callback_data="base:dashboard")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_skill_path_detail(user: dict, path: str) -> InlineKeyboardMarkup:
    """Show tiers within a specific path with invest/locked state."""
    if path not in SKILL_PATHS:
        return InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton("« Back", callback_data="skills:menu")
        ]])

    path_data = SKILL_PATHS[path]
    tiers     = path_data["tiers"]
    unlocked  = get_unlocked_tiers(user, path)
    unspent   = get_unspent_points(user)
    buttons   = []

    for tier in tiers:
        t_num  = tier["tier"]
        t_name = tier["name"]
        cost   = tier["cost"]
        is_ult = tier.get("ultimate", False)
        ult_tag = " 🌟" if is_ult else ""

        if t_num in unlocked:
            label = f"✅ T{t_num}: {t_name}{ult_tag}"
            cb    = f"skills:tier_info:{path}:{t_num}"
        elif (t_num == 1 or (t_num - 1) in unlocked) and unspent >= cost:
            label = f"⬆️ T{t_num}: {t_name}{ult_tag} [{cost}pts]"
            cb    = f"skills:unlock:{path}:{t_num}"
        elif (t_num == 1 or (t_num - 1) in unlocked) and unspent < cost:
            label = f"💡 T{t_num}: {t_name}{ult_tag} [Need {cost}pts]"
            cb    = f"skills:tier_info:{path}:{t_num}"
        else:
            label = f"🔒 T{t_num}: {t_name}{ult_tag}"
            cb    = f"skills:tier_info:{path}:{t_num}"

        buttons.append([InlineKeyboardButton(label, callback_data=cb)])

    buttons.append([
        InlineKeyboardButton("« All Paths", callback_data="skills:menu"),
        InlineKeyboardButton(f"🔄 Reset",   callback_data="skills:reset_confirm"),
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_reset_confirm() -> InlineKeyboardMarkup:
    """Confirm skill point reset."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("✅ Yes — Reset All Points", callback_data="skills:reset_execute")],
        [InlineKeyboardButton("✗ Cancel",                 callback_data="skills:menu")],
    ])


def kb_unlock_confirm(path: str, tier: int, cost: int) -> InlineKeyboardMarkup:
    """Confirm spending points on a tier."""
    path_name = SKILL_PATHS.get(path, {}).get("name", path)
    tier_name = SKILL_PATHS[path]["tiers"][tier - 1]["name"]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            f"✅ Unlock {tier_name} [{cost}pts]",
            callback_data=f"skills:unlock_confirm:{path}:{tier}"
        )],
        [InlineKeyboardButton("✗ Cancel", callback_data=f"skills:path:{path}")],
    ])


# ═══════════════════════════════════════════════════════════════════════════
#  DISPLAY FORMATTERS
# ═══════════════════════════════════════════════════════════════════════════

def format_skill_tree_summary(user: dict) -> str:
    """Full skill tree status for the player."""
    total   = get_total_skill_points(user)
    unspent = get_unspent_points(user)
    spent   = get_spent_points(user)
    power   = get_skill_power_total(user)
    level   = user.get("level", 1)

    lines = [
        f"🎖️ *COMMANDER SKILL TREE*",
        f"Level {level}  |  Total Points: {total}  |  Free: {unspent}",
        f"Skill Power: +{power:,}",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    for path_key, path_data in SKILL_PATHS.items():
        emoji        = path_data["color_emoji"]
        name         = path_data["name"]
        tagline      = path_data["tagline"]
        path_spent   = spent.get(path_key, 0)
        unlocked     = get_unlocked_tiers(user, path_key)
        highest      = max(unlocked) if unlocked else 0
        tiers        = path_data["tiers"]
        max_tier     = len(tiers)

        # Progress bar
        bar_len  = 5
        filled   = highest
        bar      = "█" * filled + "░" * (bar_len - filled)

        lines.append(f"\n{emoji} *{name}*")
        lines.append(f"_{tagline}_")
        lines.append(f"[{bar}] Tier {highest}/{max_tier}  |  {path_spent}pts invested")

        # Show active abilities
        if unlocked:
            for tier in tiers:
                if tier["tier"] in unlocked:
                    ult = " 🌟" if tier.get("ultimate") else ""
                    lines.append(f"  ✅ T{tier['tier']}: {tier['name']}{ult}")

        # Show next available
        next_tier_num = highest + 1
        if next_tier_num <= max_tier:
            next_tier = tiers[next_tier_num - 1]
            cost      = next_tier["cost"]
            can       = "⬆️" if unspent >= cost else "💡"
            lines.append(f"  {can} Next: T{next_tier_num} {next_tier['name']} [{cost}pts]")

    lines.append(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    if unspent > 0:
        lines.append(f"*{unspent} points to allocate.* Tap a path below.")
    else:
        lines.append("All points allocated. Use Reset to try a new build.")

    return "\n".join(lines)


def format_path_detail(user: dict, path: str) -> str:
    """Detailed view of a single skill path."""
    if path not in SKILL_PATHS:
        return "❌ Unknown path."

    path_data = SKILL_PATHS[path]
    tiers     = path_data["tiers"]
    unlocked  = get_unlocked_tiers(user, path)
    unspent   = get_unspent_points(user)

    lines = [
        f"{path_data['color_emoji']} *{path_data['name']}*",
        f"_{path_data['tagline']}_",
        f"{path_data['description']}",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    for tier in tiers:
        t_num  = tier["tier"]
        t_name = tier["name"]
        cost   = tier["cost"]
        desc   = tier["description"]
        is_ult = tier.get("ultimate", False)

        if t_num in unlocked:
            header = f"✅ *Tier {t_num}: {t_name}*" + (" 🌟 ULTIMATE" if is_ult else "")
        elif (t_num == 1 or (t_num - 1) in unlocked):
            can = "⬆️ Available" if unspent >= cost else f"💡 Need {cost - unspent} more pts"
            header = f"{can} — *Tier {t_num}: {t_name}*" + (" 🌟" if is_ult else "")
        else:
            header = f"🔒 *Tier {t_num}: {t_name}*" + (" 🌟" if is_ult else "")

        lines.append(f"\n{header}  [{cost}pts]")
        lines.append(f"  {desc}")

    lines.append(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"Free points: {unspent}")

    return "\n".join(lines)


def format_tier_info(path: str, tier_num: int) -> str:
    """Detailed info on a single tier."""
    if path not in SKILL_PATHS:
        return "❌ Unknown path."
    tiers = SKILL_PATHS[path]["tiers"]
    if tier_num < 1 or tier_num > len(tiers):
        return "❌ Invalid tier."

    tier  = tiers[tier_num - 1]
    path_data = SKILL_PATHS[path]

    lines = [
        f"{path_data['color_emoji']} *{path_data['name']} — Tier {tier_num}*",
        f"*{tier['name']}*" + (" 🌟 ULTIMATE" if tier.get("ultimate") else ""),
        f"Cost: {tier['cost']} skill points",
        f"Power Value: +{tier.get('power_value', 0):,}",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"{tier['description']}",
        f"\n*Raw Effects:*",
    ]

    for eff_key, eff_val in tier["effects"].items():
        if isinstance(eff_val, float) and eff_val < 2:
            display = f"{int(eff_val * 100)}%"
        elif isinstance(eff_val, bool):
            display = "Active" if eff_val else "Inactive"
        else:
            display = str(eff_val)
        lines.append(f"  • {eff_key.replace('_', ' ').title()}: {display}")

    return "\n".join(lines)
