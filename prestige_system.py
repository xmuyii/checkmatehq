# -*- coding: utf-8 -*-
"""
prestige_system.py — Prestige System
======================================
Players who reach Level 100 can Prestige — reset to Level 1 with a
permanent power multiplier that stacks across prestige tiers.

PRESTIGE TIERS:
  Tier 0 — No prestige          ×1.00 (base)
  Tier 1 — Iron Commander       ×1.10
  Tier 2 — Bronze Commander     ×1.25
  Tier 3 — Steel Commander      ×1.50
  Tier 4 — Gold Commander       ×2.00
  Tier 5 — Diamond Commander    ×3.00 (maximum)

WHAT RESETS:
  Level, XP, building levels, research, military (troops),
  training queue, building queue, sector nodes occupied,
  current_node, march_queue

WHAT IS KEPT:
  Gold, Bitcoin, Credits, Relics (inventory items),
  Alliance membership and AP, Bounty Hunter career + XP,
  Prestige tier and multiplier, Base name,
  Suit inventory, Discovered recipes, Sector dominance scores

PRESTIGE REWARDS (on top of multiplier):
  Tier 1 → 500 gold + "Iron Commander" title
  Tier 2 → 1000 gold + unique avatar badge
  Tier 3 → 2000 gold + 3 days shield
  Tier 4 → 5000 gold + permanent +1 teleport charge daily
  Tier 5 → 10000 gold + Legendary recipe tome unlocked

Called from main.py via:
  from prestige_system import can_prestige, execute_prestige,
      get_prestige_tier, format_prestige_status, PRESTIGE_BONUSES
"""

from datetime import datetime, timedelta
from typing import Tuple
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ═══════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

PRESTIGE_REQUIRED_LEVEL = 100

PRESTIGE_BONUSES = {
    0: {
        "name":        "Commander",
        "emoji":       "🎖️",
        "multiplier":  1.00,
        "gold_reward": 0,
        "description": "Base state. No prestige yet.",
    },
    1: {
        "name":        "Iron Commander",
        "emoji":       "⚙️",
        "multiplier":  1.10,
        "gold_reward": 500,
        "description": "+10% permanent power. Iron will forged through fire.",
        "special":     "iron_title",
    },
    2: {
        "name":        "Bronze Commander",
        "emoji":       "🥉",
        "multiplier":  1.25,
        "gold_reward": 1000,
        "description": "+25% permanent power. The battlefield remembers you.",
        "special":     "bronze_badge",
    },
    3: {
        "name":        "Steel Commander",
        "emoji":       "⚔️",
        "multiplier":  1.50,
        "gold_reward": 2000,
        "description": "+50% permanent power. A 3-day shield granted.",
        "special":     "shield_72h",
    },
    4: {
        "name":        "Gold Commander",
        "emoji":       "🥇",
        "multiplier":  2.00,
        "gold_reward": 5000,
        "description": "×2 permanent power. +1 bonus teleport charge per day.",
        "special":     "bonus_daily_teleport",
    },
    5: {
        "name":        "Diamond Commander",
        "emoji":       "💎",
        "multiplier":  3.00,
        "gold_reward": 10000,
        "description": "×3 permanent power. Maximum prestige. Legendary recipe tome unlocked.",
        "special":     "legendary_recipe_tome",
    },
}

MAX_PRESTIGE = 5

# Fields that get reset on prestige
RESET_FIELDS = {
    "level":           1,
    "xp":              0,
    "buildings":       {},
    "building_queue":  {},
    "researches":      {},
    "research_queue":  {},
    "research_power":  0,
    "military":        {},
    "training_queue":  [],
    "march_queue":     [],
    "current_node":    None,
    "traps":           {},
    "base_hq_level":   1,
    "base_level":      1,
    "energy":          100,
    "skill_points_spent": {"volt": 0, "incendiary": 0, "recon": 0, "bulwark": 0},
    "dominance_scores": {},
    "dominance_total":  0,
    "banishments":      {},
}

# Fields that are KEPT on prestige (everything not in RESET_FIELDS)
KEPT_FIELDS_NOTE = """
Kept: gold, bitcoin, credits, inventory (suits/items/recipes),
      base_name, alliance_id, alliance_role, alliance_points,
      is_bounty_hunter, hunter_xp, hunter_tier, hunter_kills,
      hunter_earnings, prestige (incremented), prestige_multiplier,
      discovered_recipes, notification_prefs, notifications_seen,
      home_sector, teleport_charges, last_active, username
"""


# ═══════════════════════════════════════════════════════════════════════════
#  CORE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def can_prestige(level: int, current_prestige: int) -> Tuple[bool, str]:
    """
    Check if a player can prestige.
    Returns (can: bool, reason: str)
    """
    if level < PRESTIGE_REQUIRED_LEVEL:
        return False, (
            f"❌ Prestige requires Level {PRESTIGE_REQUIRED_LEVEL}.\n"
            f"You are Level {level}. "
            f"({PRESTIGE_REQUIRED_LEVEL - level} levels remaining)"
        )

    if current_prestige >= MAX_PRESTIGE:
        return False, (
            f"✅ You are already at maximum prestige "
            f"({PRESTIGE_BONUSES[MAX_PRESTIGE]['emoji']} "
            f"{PRESTIGE_BONUSES[MAX_PRESTIGE]['name']}).\n"
            f"There is nowhere higher to climb."
        )

    return True, "OK"


def get_prestige_tier(user: dict) -> int:
    """Get current prestige tier (0-5)."""
    return min(MAX_PRESTIGE, max(0, int(user.get("prestige", 0) or 0)))


def get_prestige_multiplier(user: dict) -> float:
    """Get the player's current power multiplier from prestige."""
    tier = get_prestige_tier(user)
    return PRESTIGE_BONUSES.get(tier, PRESTIGE_BONUSES[0])["multiplier"]


def execute_prestige(user: dict) -> dict:
    """
    Execute a prestige. Increments tier, resets fields, applies rewards.
    Returns updated user dict.
    Call save_user() after this.
    """
    current_tier = get_prestige_tier(user)
    new_tier     = min(MAX_PRESTIGE, current_tier + 1)
    bonus        = PRESTIGE_BONUSES[new_tier]

    # Apply all resets
    for field, default in RESET_FIELDS.items():
        user[field] = default

    # Increment prestige
    user["prestige"]             = new_tier
    user["prestige_multiplier"]  = bonus["multiplier"]
    user["prestige_title"]       = bonus["name"]
    user["prestige_emoji"]       = bonus["emoji"]
    user["prestige_date"]        = datetime.utcnow().isoformat()

    # Apply gold reward
   # Apply gold reward — gold is a top-level field, never an inventory item
    gold_reward   = bonus.get("gold_reward", 0)
    user["gold"]  = (user.get("gold", 0) or 0) + gold_reward

    # Apply special rewards
    special = bonus.get("special", "")

    if special == "shield_72h":
        expires = (datetime.utcnow() + timedelta(hours=72)).isoformat()
        user["base_shielded"]    = True
        user["shield_expires_at"] = expires

    elif special == "bonus_daily_teleport":
        user["prestige_bonus_teleport"] = True   # Scheduler checks this flag

    elif special == "legendary_recipe_tome":
        discovered = user.get("discovered_recipes", []) or []
        for recipe in [
            "craft_commanders_sigil",
            "craft_void_lattice_trap",
            "craft_ancient_banner",
        ]:
            if recipe not in discovered:
                discovered.append(recipe)
        user["discovered_recipes"] = discovered

    # Reset base resources to starter amounts
    user["base_resources"] = {
        "resources": {
            "wood":   100,
            "bronze": 50,
            "iron":   20,
            "stone":  10,
            "relics": 0,
        },
        "food":           50,
        "current_streak": 0,
    }

    # Add prestige achievement to history
    history = user.get("prestige_history", []) or []
    history.append({
        "tier":     new_tier,
        "date":     datetime.utcnow().isoformat(),
        "gold_reward": gold_reward,
    })
    user["prestige_history"] = history

    return user


# ═══════════════════════════════════════════════════════════════════════════
#  DISPLAY
# ═══════════════════════════════════════════════════════════════════════════

def format_prestige_status(user: dict) -> str:
    """Full prestige status page."""
    tier       = get_prestige_tier(user)
    bonus      = PRESTIGE_BONUSES[tier]
    level      = user.get("level", 1)
    mult       = bonus["multiplier"]
    next_tier  = tier + 1

    lines = [
        f"👑 *PRESTIGE STATUS*",
        f"━━━━━━━━━━━━━━━━━━━━━━━━",
        f"{bonus['emoji']} *{bonus['name']}*",
        f"Power Multiplier: ×{mult}",
        f"Current Level: {level} / {PRESTIGE_REQUIRED_LEVEL}",
        f"",
    ]

    # Progress to next prestige
    if tier < MAX_PRESTIGE:
        next_bonus = PRESTIGE_BONUSES[next_tier]
        levels_left = max(0, PRESTIGE_REQUIRED_LEVEL - level)
        pct  = min(100, int(level / PRESTIGE_REQUIRED_LEVEL * 100))
        filled = pct // 5
        bar  = "█" * filled + "░" * (20 - filled)
        lines += [
            f"*Next: {next_bonus['emoji']} {next_bonus['name']}* (Tier {next_tier})",
            f"[{bar}] {level}/{PRESTIGE_REQUIRED_LEVEL}",
            f"Levels remaining: {levels_left}",
            f"",
            f"*Prestige {next_tier} rewards:*",
            f"  ×{next_bonus['multiplier']} permanent power multiplier",
            f"  +{next_bonus['gold_reward']:,} 🪙 gold",
            f"  {next_bonus['description']}",
        ]
        if levels_left == 0:
            lines += ["", "✅ *Ready to Prestige!* Tap below."]
    else:
        lines.append("💎 *Maximum prestige achieved.*")

    lines.append("")
    lines.append("*All Prestige Tiers:*")
    for t, b in PRESTIGE_BONUSES.items():
        if t == 0:
            continue
        marker = "✅" if tier >= t else ("⬜" if tier < t else "🔓")
        lines.append(f"  {marker} {b['emoji']} {b['name']} — ×{b['multiplier']}")

    lines.append(f"\n━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(
        "*What resets:* Level, XP, Buildings, Research, Troops\n"
        "*What stays:* Gold, Bitcoin, Items, Alliance, Hunter career, Inventory"
    )
    return "\n".join(lines)


def format_prestige_confirm(user: dict) -> str:
    """Confirmation screen before prestige."""
    tier     = get_prestige_tier(user)
    new_tier = tier + 1
    bonus    = PRESTIGE_BONUSES[new_tier]
    level    = user.get("level", 1)

    return (
        f"⚠️ *PRESTIGE CONFIRMATION*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"You are about to Prestige to:\n"
        f"{bonus['emoji']} *{bonus['name']}* (Tier {new_tier})\n\n"
        f"*You will receive:*\n"
        f"  ×{bonus['multiplier']} permanent power multiplier\n"
        f"  +{bonus['gold_reward']:,} 🪙 gold\n"
        f"  {bonus['description']}\n\n"
        f"*You will lose:*\n"
        f"  All levels, XP, buildings, research\n"
        f"  All troops and training queues\n"
        f"  All sector occupancy and node positions\n\n"
        f"*You keep:*\n"
        f"  Gold, Bitcoin, items, alliance, hunter career\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"This action *cannot be undone.*"
    )


# ═══════════════════════════════════════════════════════════════════════════
#  KEYBOARDS
# ═══════════════════════════════════════════════════════════════════════════

def kb_prestige_status(user: dict) -> InlineKeyboardMarkup:
    tier  = get_prestige_tier(user)
    level = user.get("level", 1)
    can, _ = can_prestige(level, tier)
    buttons = []
    if can:
        buttons.append([InlineKeyboardButton(
            text="👑 PRESTIGE NOW",
            callback_data="prestige:confirm"
        )])
    buttons.append([InlineKeyboardButton("⬅️ Profile", callback_data="menu_profile")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_prestige_confirm() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("✅ YES — Prestige Now", callback_data="prestige:execute")],
        [InlineKeyboardButton("✗ Cancel",             callback_data="prestige:status")],
    ])
