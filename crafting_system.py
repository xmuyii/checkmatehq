# -*- coding: utf-8 -*-
"""
crafting_system.py — Item Crafting System
==========================================
Players combine resources and fragments to create unique items
unavailable in the regular store. Crafting requires research gates,
building requirements, and time.

CRAFTING CATEGORIES:
  protective    — Suits, formats, wallets (craft instead of buying)
  military      — Troop boosters, siege tools, battle items
  economic      — Resource multipliers, storage expanders, yield boosters
  intelligence  — Scout tools, trap detectors, sector jammers
  legendary     — Unique items, one per server per week, require rare mats
  consumable    — Single-use battle items, speedups, shields

CRAFT STATION:
  Crafting requires the Trap Factory building (repurposed as craft station).
  Higher building level = more crafting slots and faster craft times.
  Craft Factory Lv1 = 1 slot, 1x speed
  Craft Factory Lv2 = 2 slots, 1.2x speed
  Craft Factory Lv3 = 3 slots, 1.5x speed

RECIPE DISCOVERY:
  Some recipes are visible from the start.
  Hidden recipes are discovered by:
    - Researching relevant tech (e.g. hazmat_engineering unlocks hazmat recipes)
    - Finding recipe fragments in ancient_vault nodes (rare drops)
    - Purchasing recipe books from the Black Market
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ═══════════════════════════════════════════════════════════════════════════
#  RECIPE DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════

RECIPES: Dict[str, dict] = {

    # ── PROTECTIVE ITEMS ──────────────────────────────────────────────────
    "craft_basic_suit": {
        "name":          "Basic Radiation Suit",
        "output_key":    "basic_suit",
        "output_qty":    1,
        "category":      "protective",
        "emoji":         "🧪",
        "ingredients":   {"iron": 50, "bronze": 30},
        "craft_time_secs": 300,
        "research_required": "hazard_awareness",
        "building_required": "trap_factory",
        "building_level": 1,
        "description":   "Craft a Basic Radiation Suit instead of buying it. Cheaper by 30%.",
        "hidden":        False,
        "craft_cost_gold": 0,
    },
    "craft_hazmat_suit": {
        "name":          "Hazmat Suit",
        "output_key":    "hazmat_suit",
        "output_qty":    1,
        "category":      "protective",
        "emoji":         "☢️",
        "ingredients":   {"iron": 100, "stone": 20, "relics": 5},
        "craft_time_secs": 600,
        "research_required": "hazmat_engineering",
        "building_required": "trap_factory",
        "building_level": 1,
        "description":   "Full hazmat protection. 20 minutes.",
        "hidden":        False,
        "craft_cost_gold": 0,
    },
    "craft_bitcoin_format": {
        "name":          "Bitcoin Format",
        "output_key":    "bitcoin_format",
        "output_qty":    1,
        "category":      "protective",
        "emoji":         "💾",
        "ingredients":   {"blockchain_fragment": 5, "iron": 20},
        "craft_time_secs": 480,
        "research_required": "crypto_security",
        "building_required": "trap_factory",
        "building_level": 1,
        "description":   "Protects against Crypto Wastes hazards. 20 minutes.",
        "hidden":        False,
        "craft_cost_gold": 0,
    },
    "craft_cold_wallet": {
        "name":          "Cold Wallet",
        "output_key":    "cold_wallet",
        "output_qty":    1,
        "category":      "protective",
        "emoji":         "🔐",
        "ingredients":   {"blockchain_fragment": 20, "relics": 10},
        "craft_time_secs": 1200,
        "research_required": "advanced_crypto_security",
        "building_required": "trap_factory",
        "building_level": 2,
        "description":   "Maximum crypto protection. 45 minutes. Survives Market Crash.",
        "hidden":        False,
        "craft_cost_gold": 0,
    },

    # ── MILITARY ITEMS ────────────────────────────────────────────────────
    "craft_battle_ration": {
        "name":          "Battle Ration",
        "output_key":    "battle_ration",
        "output_qty":    3,
        "category":      "military",
        "emoji":         "🥩",
        "ingredients":   {"wood": 30, "bronze": 10},
        "craft_time_secs": 120,
        "research_required": "basic_military",
        "building_required": "trap_factory",
        "building_level": 1,
        "description":   "Feed troops before battle. +10% attack power for 30 minutes. Stackable.",
        "hidden":        False,
        "craft_cost_gold": 0,
        "effect": {"attack_power_bonus_pct": 0.10, "duration_minutes": 30},
    },
    "craft_siege_hammer": {
        "name":          "Siege Hammer",
        "output_key":    "siege_hammer",
        "output_qty":    1,
        "category":      "military",
        "emoji":         "🔨",
        "ingredients":   {"iron": 80, "stone": 40, "relics": 3},
        "craft_time_secs": 900,
        "research_required": "siege_tactics",
        "building_required": "trap_factory",
        "building_level": 2,
        "description":   "Used during fortress sieges. +50% damage to fortress HP per attack. One use.",
        "hidden":        False,
        "craft_cost_gold": 0,
        "effect": {"fortress_damage_bonus_pct": 0.50},
    },
    "craft_war_banner": {
        "name":          "War Banner",
        "output_key":    "war_banner",
        "output_qty":    1,
        "category":      "military",
        "emoji":         "🚩",
        "ingredients":   {"iron": 60, "relics": 8, "stone": 30},
        "craft_time_secs": 720,
        "research_required": "commander_doctrine",
        "building_required": "trap_factory",
        "building_level": 2,
        "description":   "Plant at a node. All alliance members in the same sector get +15% power for 1 hour.",
        "hidden":        False,
        "craft_cost_gold": 0,
        "effect": {"alliance_power_bonus_pct": 0.15, "duration_minutes": 60},
    },
    "craft_decoy_signal": {
        "name":          "Decoy Signal",
        "output_key":    "decoy_signal",
        "output_qty":    2,
        "category":      "military",
        "emoji":         "📡",
        "ingredients":   {"bronze": 40, "iron": 20},
        "craft_time_secs": 300,
        "research_required": "basic_scouting",
        "building_required": "trap_factory",
        "building_level": 1,
        "description":   "Deploy at a node. Enemies who scout it see fake high resource numbers. Lasts 2 hours.",
        "hidden":        True,
        "hidden_unlock": "sector_awareness",
        "craft_cost_gold": 0,
        "effect": {"fake_resource_multiplier": 3.0, "duration_minutes": 120},
    },

    # ── ECONOMIC ITEMS ────────────────────────────────────────────────────
    "craft_yield_crystal": {
        "name":          "Yield Crystal",
        "output_key":    "yield_crystal",
        "output_qty":    1,
        "category":      "economic",
        "emoji":         "💎",
        "ingredients":   {"relics": 10, "stone": 50, "iron": 30},
        "craft_time_secs": 600,
        "research_required": "advanced_mining",
        "building_required": "trap_factory",
        "building_level": 2,
        "description":   "Place at an occupied node. Doubles resource yield for 2 hours. One use.",
        "hidden":        False,
        "craft_cost_gold": 0,
        "effect": {"node_yield_multiplier": 2.0, "duration_minutes": 120},
    },
    "craft_storage_seal": {
        "name":          "Storage Seal",
        "output_key":    "storage_seal",
        "output_qty":    1,
        "category":      "economic",
        "emoji":         "🔏",
        "ingredients":   {"stone": 60, "iron": 40},
        "craft_time_secs": 480,
        "research_required": "resource_compression",
        "building_required": "trap_factory",
        "building_level": 1,
        "description":   "Protects 30% of base resources from the next raid. One use.",
        "hidden":        False,
        "craft_cost_gold": 0,
        "effect": {"raid_protection_pct": 0.30},
    },
    "craft_converter_kit": {
        "name":          "Resource Converter Kit",
        "output_key":    "converter_kit",
        "output_qty":    1,
        "category":      "economic",
        "emoji":         "⚗️",
        "ingredients":   {"relics": 5, "bronze": 50, "wood": 100},
        "craft_time_secs": 360,
        "research_required": "resource_compression",
        "building_required": "trap_factory",
        "building_level": 1,
        "description":   "Converts 500 of any resource into 250 of any other resource. One use.",
        "hidden":        False,
        "craft_cost_gold": 0,
    },

    # ── INTELLIGENCE ITEMS ────────────────────────────────────────────────
    "craft_sector_lens": {
        "name":          "Sector Lens",
        "output_key":    "sector_lens",
        "output_qty":    1,
        "category":      "intelligence",
        "emoji":         "🔭",
        "ingredients":   {"relics": 8, "iron": 30, "stone": 20},
        "craft_time_secs": 480,
        "research_required": "basic_scouting",
        "building_required": "trap_factory",
        "building_level": 1,
        "description":   "View any sector's node map without teleporting there. One use.",
        "hidden":        False,
        "craft_cost_gold": 0,
    },
    "craft_trap_detector": {
        "name":          "Trap Detector",
        "output_key":    "trap_detector",
        "output_qty":    2,
        "category":      "intelligence",
        "emoji":         "🧲",
        "ingredients":   {"bronze": 60, "iron": 20},
        "craft_time_secs": 300,
        "research_required": "basic_trapping",
        "building_required": "trap_factory",
        "building_level": 1,
        "description":   "Used before scouting. 80% chance to neutralise mousetraps. One use per scout.",
        "hidden":        False,
        "craft_cost_gold": 0,
    },
    "craft_signal_jammer_kit": {
        "name":          "Portable Jammer Kit",
        "output_key":    "portable_jammer",
        "output_qty":    1,
        "category":      "intelligence",
        "emoji":         "📡",
        "ingredients":   {"relics": 15, "iron": 80, "stone": 40},
        "craft_time_secs": 1200,
        "research_required": "sector_jamming",
        "building_required": "trap_factory",
        "building_level": 3,
        "description":   "One-use sector jam for players who haven't unlocked the Volt Tier 5 ability. 2-minute jam.",
        "hidden":        True,
        "hidden_unlock": "sector_jamming",
        "craft_cost_gold": 0,
        "effect": {"jam_duration_secs": 120},
    },

    # ── LEGENDARY ITEMS ───────────────────────────────────────────────────
    # One per server per week. Requires rare materials from ancient vaults.
    "craft_commanders_sigil": {
        "name":          "Commander's Sigil",
        "output_key":    "commanders_sigil",
        "output_qty":    1,
        "category":      "legendary",
        "emoji":         "🌟",
        "ingredients":   {"relics": 50, "blockchain_fragment": 30, "iron": 200, "stone": 100},
        "craft_time_secs": 3600,
        "research_required": "prestige_theory",
        "building_required": "trap_factory",
        "building_level": 3,
        "description":   "Legendary. +50% to ALL stats for 24 hours. Only one can exist at a time server-wide.",
        "hidden":        True,
        "hidden_unlock": "prestige_theory",
        "craft_cost_gold": 500,
        "server_unique":  True,
        "effect": {"all_stats_bonus_pct": 0.50, "duration_minutes": 1440},
    },
    "craft_void_lattice_trap": {
        "name":          "Void Lattice Trap",
        "output_key":    "void_lattice",
        "output_qty":    1,
        "category":      "legendary",
        "emoji":         "🕸️",
        "ingredients":   {"relics": 40, "stone": 80, "iron": 150},
        "craft_time_secs": 2400,
        "research_required": "prestige_theory",
        "building_required": "trap_factory",
        "building_level": 3,
        "description":   "The most powerful trap. Instantly ejects any attacker and stuns them for 30 minutes.",
        "hidden":        True,
        "hidden_unlock": "void_theory",
        "craft_cost_gold": 0,
    },
    "craft_ancient_banner": {
        "name":          "Ancient War Banner",
        "output_key":    "ancient_banner",
        "output_qty":    1,
        "category":      "legendary",
        "emoji":         "🏴",
        "ingredients":   {"relics": 35, "iron": 120, "blockchain_fragment": 15},
        "craft_time_secs": 1800,
        "research_required": "commander_doctrine",
        "building_required": "trap_factory",
        "building_level": 3,
        "description":   "Alliance-wide +25% power for 6 hours when planted at a sector PvP outpost.",
        "hidden":        True,
        "hidden_unlock": "alliance_protocols",
        "craft_cost_gold": 200,
        "effect": {"alliance_power_bonus_pct": 0.25, "duration_minutes": 360},
    },

    # ── CONSUMABLES ───────────────────────────────────────────────────────
    "craft_smoke_bomb": {
        "name":          "Smoke Bomb",
        "output_key":    "smoke_bomb",
        "output_qty":    3,
        "category":      "consumable",
        "emoji":         "💨",
        "ingredients":   {"wood": 20, "bronze": 15},
        "craft_time_secs": 180,
        "research_required": "basic_scouting",
        "building_required": "trap_factory",
        "building_level": 1,
        "description":   "Use when fleeing a node. Auto-collects resources and teleports you instantly. One use.",
        "hidden":        False,
        "craft_cost_gold": 0,
    },
    "craft_energy_cell": {
        "name":          "Energy Cell",
        "output_key":    "energy_cell",
        "output_qty":    1,
        "category":      "consumable",
        "emoji":         "⚡",
        "ingredients":   {"iron": 15, "bronze": 20},
        "craft_time_secs": 120,
        "research_required": "energy_systems",
        "building_required": "trap_factory",
        "building_level": 1,
        "description":   "Instantly restores 100 energy. Useful before predator fights.",
        "hidden":        False,
        "craft_cost_gold": 0,
        "effect": {"energy_restore": 100},
    },
    "craft_reinforced_shield": {
        "name":          "Reinforced Shield (12h)",
        "output_key":    "shield_reinforced",
        "output_qty":    1,
        "category":      "consumable",
        "emoji":         "🛡️",
        "ingredients":   {"iron": 60, "stone": 30},
        "craft_time_secs": 600,
        "research_required": "advanced_defense",
        "building_required": "trap_factory",
        "building_level": 2,
        "description":   "12-hour shield. Stronger than store basic (8h). Cannot be crafted in bulk.",
        "hidden":        False,
        "craft_cost_gold": 0,
        "effect": {"shield_duration_hours": 12, "shield_drain_per_attack_hours": 1.5},
    },
}

CATEGORY_LABELS = {
    "protective":   "🧪 Protective Items",
    "military":     "⚔️ Military Items",
    "economic":     "💰 Economic Items",
    "intelligence": "🔭 Intelligence Items",
    "legendary":    "🌟 Legendary Items",
    "consumable":   "🎒 Consumables",
}


# ═══════════════════════════════════════════════════════════════════════════
#  CRAFT QUEUE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

def get_craft_slots(user: dict) -> int:
    """Get how many crafting slots the player has based on trap_factory level."""
    buildings = user.get("buildings", {}) or {}
    level     = buildings.get("trap_factory", 0)
    if level >= 3:
        return 3
    elif level >= 2:
        return 2
    elif level >= 1:
        return 1
    return 0


def get_craft_speed_multiplier(user: dict) -> float:
    """Higher trap_factory level = faster crafting."""
    buildings = user.get("buildings", {}) or {}
    level     = buildings.get("trap_factory", 0)
    return {0: 1.0, 1: 1.0, 2: 1.2, 3: 1.5}.get(level, 1.0)


def is_recipe_unlocked(user: dict, recipe_key: str) -> Tuple[bool, str]:
    """
    Check if a recipe is available to the player.
    Returns (unlocked, reason_if_not)
    """
    recipe = RECIPES.get(recipe_key)
    if not recipe:
        return False, "Recipe not found."

    # Hidden recipes need to be discovered first
    if recipe.get("hidden"):
        discovered = user.get("discovered_recipes", []) or []
        if recipe_key not in discovered:
            return False, "Recipe not yet discovered. Find it in ancient vaults or the Black Market."

    # Research gate
    req_research = recipe.get("research_required")
    if req_research:
        from research_tree import is_researched
        if not is_researched(user, req_research):
            from research_tree import RESEARCH_TREE
            rname = RESEARCH_TREE.get(req_research, {}).get("name", req_research)
            return False, f"Requires research: {rname}"

    # Building gate
    req_building = recipe.get("building_required")
    req_level    = recipe.get("building_level", 1)
    if req_building:
        buildings = user.get("buildings", {}) or {}
        level     = buildings.get(req_building, 0)
        if level < req_level:
            bname = req_building.replace("_", " ").title()
            return False, f"Requires {bname} Level {req_level}. Current: {level}."

    return True, "OK"


def can_afford_recipe(user: dict, recipe_key: str) -> Tuple[bool, str]:
    """Check if player has all ingredients. Returns (can_afford, missing_str)."""
    recipe = RECIPES.get(recipe_key)
    if not recipe:
        return False, "Recipe not found."

    base_res  = user.get("base_resources", {}) or {}
    resources = base_res.get("resources", {}) or {}
    missing   = []

    for ingredient, amount in recipe.get("ingredients", {}).items():
        # Ingredients are always base resources (already-applied), not
        # backpack items. If a player has an unused resource pack in their
        # inventory, they need to "use" it first — base_resources is the
        # single source of truth for craftable ingredients.
        have = resources.get(ingredient, 0)
        if have < amount:
            missing.append(f"{amount - have} more {ingredient}")

    # Check gold cost — gold is a top-level field, never an inventory item
    gold_cost = recipe.get("craft_cost_gold", 0)
    if gold_cost > 0:
        have_gold = user.get("gold", 0) or 0
        if have_gold < gold_cost:
            missing.append(f"{gold_cost - have_gold} more gold 🪙")

    if missing:
        return False, "Need: " + ", ".join(missing)
    return True, "OK"


def start_craft(
    user: dict,
    recipe_key: str,
) -> Tuple[bool, str, dict]:
    """
    Begin crafting an item. Deducts ingredients and adds to craft queue.
    Returns (success, message, updated_user)
    """
    recipe = RECIPES.get(recipe_key)
    if not recipe:
        return False, "❌ Unknown recipe.", user

    # Unlock check
    unlocked, reason = is_recipe_unlocked(user, recipe_key)
    if not unlocked:
        return False, f"🔒 {reason}", user

    # Slot check
    slots   = get_craft_slots(user)
    if slots == 0:
        return False, "❌ You need a Trap Factory (Lv1+) to craft items.", user

    queue = user.get("craft_queue", []) or []
    if len(queue) >= slots:
        return False, (
            f"❌ All {slots} crafting slot(s) busy.\n"
            f"Upgrade Trap Factory for more slots."
        ), user

    # Check server-unique limit
    if recipe.get("server_unique"):
        if _check_server_unique_active(recipe_key):
            return False, (
                f"❌ A *{recipe['name']}* already exists on the server.\n"
                f"Only one can exist at a time. Wait for it to expire."
            ), user

    # Afford check
    can_afford, miss_msg = can_afford_recipe(user, recipe_key)
    if not can_afford:
        return False, f"❌ {miss_msg}", user

    # Deduct ingredients
    user = _deduct_ingredients(user, recipe)

    # Calculate craft time
    speed     = get_craft_speed_multiplier(user)
    base_time = recipe.get("craft_time_secs", 300)
    craft_time = max(30, int(base_time / speed))
    done_at   = (datetime.utcnow() + timedelta(seconds=craft_time)).isoformat()

    craft_entry = {
        "recipe_key":   recipe_key,
        "recipe_name":  recipe["name"],
        "started_at":   datetime.utcnow().isoformat(),
        "done_at":      done_at,
        "craft_secs":   craft_time,
        "output_key":   recipe["output_key"],
        "output_qty":   recipe["output_qty"],
    }

    queue.append(craft_entry)
    user["craft_queue"] = queue

    time_str = _format_secs(craft_time)
    return True, (
        f"⚗️ *Crafting started: {recipe['name']}*\n"
        f"Time: {time_str}\n"
        f"Output: {recipe['emoji']} ×{recipe['output_qty']}\n"
        f"_Progress visible on your dashboard._"
    ), user


def check_and_complete_crafts(user: dict) -> Tuple[dict, List[str]]:
    """
    Check craft queue and complete any finished items.
    Returns (updated_user, list_of_completed_item_names)
    Call this on every user load.
    """
    queue     = user.get("craft_queue", []) or []
    now       = datetime.utcnow()
    completed = []
    remaining = []

    for entry in queue:
        try:
            done_at = datetime.fromisoformat(entry["done_at"])
        except Exception:
            remaining.append(entry)
            continue

        if now >= done_at:
            # Complete — add to backpack via the shared, correct helper
            output_key = entry["output_key"]
            output_qty = entry["output_qty"]
            recipe_for_output = RECIPES.get(entry["recipe_key"], {})
            from supabase_db import add_inventory_item
            user = add_inventory_item(
                user, output_key, output_qty,
                recipe_for_output.get("name", output_key.replace("_", " ").title()),
                category=recipe_for_output.get("category", "consumable"),
            )
            completed.append(entry["recipe_name"])

            # Mark server-unique as active
            recipe = RECIPES.get(entry["recipe_key"], {})
            if recipe.get("server_unique"):
                _mark_server_unique_active(entry["recipe_key"], output_qty)
        else:
            remaining.append(entry)

    user["craft_queue"] = remaining
    return user, completed


def apply_speedup_to_craft(
    user: dict,
    recipe_key: str,
    speedup_item_key: str,
) -> Tuple[bool, str, dict]:
    """Apply a speedup item to an active craft."""
    from resource_registry import RESOURCES
    speedup_data = RESOURCES.get(speedup_item_key, {})
    reduction    = speedup_data.get("reduces_timer_minutes", 0) * 60

    if reduction == 0:
        return False, "❌ Not a valid speedup item.", user

    from supabase_db import get_inventory_item, remove_inventory_item
    row = get_inventory_item(user, speedup_item_key)
    have_qty = int(row.get("qty", row.get("quantity", 0)) or 0) if row else 0
    if have_qty < 1:
        return False, f"❌ No {speedup_item_key} in inventory.", user

    queue = user.get("craft_queue", []) or []
    for i, entry in enumerate(queue):
        if entry.get("recipe_key") == recipe_key:
            try:
                current_done = datetime.fromisoformat(entry["done_at"])
                new_done     = current_done - timedelta(seconds=reduction)
                floor        = datetime.utcnow() + timedelta(seconds=10)
                if new_done < floor:
                    new_done = floor
                queue[i]["done_at"] = new_done.isoformat()
                user["craft_queue"] = queue

                # Consume speedup from the real backpack list
                user = remove_inventory_item(user, speedup_item_key)

                remaining = max(0, (new_done - datetime.utcnow()).total_seconds())
                return True, f"⏩ Craft sped up! Completes in {_format_secs(int(remaining))}.", user
            except Exception as e:
                return False, f"❌ Speedup failed: {e}", user

    return False, "❌ No active craft for that recipe.", user


def discover_recipe(user: dict, recipe_key: str) -> Tuple[bool, str, dict]:
    """
    Mark a hidden recipe as discovered for a player.
    Called when they find a recipe fragment in a vault node.
    """
    if recipe_key not in RECIPES:
        return False, "Unknown recipe.", user

    discovered = user.get("discovered_recipes", []) or []
    if recipe_key in discovered:
        return False, "Already discovered.", user

    discovered.append(recipe_key)
    user["discovered_recipes"] = discovered
    recipe = RECIPES[recipe_key]
    return True, (
        f"📜 *Recipe Discovered!*\n"
        f"{recipe['emoji']} *{recipe['name']}*\n"
        f"{recipe['description']}\n"
        f"Now available in your Crafting Station."
    ), user


# ═══════════════════════════════════════════════════════════════════════════
#  DISPLAY FORMATTERS
# ═══════════════════════════════════════════════════════════════════════════

def format_craft_menu(user: dict, category: str = None) -> str:
    """Format the crafting menu, optionally filtered by category."""
    slots    = get_craft_slots(user)
    queue    = user.get("craft_queue", []) or []
    speed    = get_craft_speed_multiplier(user)

    buildings = user.get("buildings", {}) or {}
    tf_level  = buildings.get("trap_factory", 0)

    lines = [
        "⚗️ *CRAFTING STATION*",
        f"━━━━━━━━━━━━━━━━━━━━━━━━",
        f"Trap Factory Lv{tf_level}  |  Slots: {len(queue)}/{slots}  |  Speed: {speed:.1f}×",
    ]

    if tf_level == 0:
        lines.append(
            "\n❌ *No Trap Factory built.*\n"
            "Build one to unlock crafting."
        )
        return "\n".join(lines)

    # Active queue progress bars
    if queue:
        lines.append("\n⏳ *IN PROGRESS:*")
        now = datetime.utcnow()
        for entry in queue:
            name    = entry.get("recipe_name", "?")
            try:
                started = datetime.fromisoformat(entry["started_at"])
                done    = datetime.fromisoformat(entry["done_at"])
                total   = (done - started).total_seconds()
                elapsed = (now - started).total_seconds()
                pct     = min(100, int(elapsed / max(total, 1) * 100))
                rem     = max(0, (done - now).total_seconds())
                filled  = pct // 5
                bar     = "█" * filled + "░" * (20 - filled)
                lines.append(f"  {name}\n  [{bar}] {pct}% — {_format_secs(int(rem))}")
            except Exception:
                lines.append(f"  {name}")

    # Recipes grouped by category
    lines.append(f"\n📋 *RECIPES:*")
    target_cats = [category] if category else list(CATEGORY_LABELS.keys())

    for cat in target_cats:
        cat_recipes = [
            (k, v) for k, v in RECIPES.items()
            if v.get("category") == cat
        ]
        if not cat_recipes:
            continue

        lines.append(f"\n{CATEGORY_LABELS[cat]}")

        for rkey, recipe in cat_recipes:
            unlocked, reason = is_recipe_unlocked(user, rkey)
            can_afford, _    = can_afford_recipe(user, rkey) if unlocked else (False, "")
            name             = recipe["name"]
            emoji            = recipe["emoji"]
            out_qty          = recipe["output_qty"]
            time_str         = _format_secs(int(recipe["craft_time_secs"] / speed))

            if recipe.get("hidden") and rkey not in (user.get("discovered_recipes") or []):
                lines.append(f"  ❓ *???* — Hidden recipe")
                continue

            if unlocked:
                status = "⚗️" if can_afford else "💡"
            else:
                status = "🔒"

            lines.append(
                f"  {status} {emoji} *{name}* ×{out_qty} — {time_str}"
            )

    lines.append(f"\n━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def format_recipe_detail(recipe_key: str, user: dict) -> str:
    """Detailed view of a single recipe."""
    recipe = RECIPES.get(recipe_key)
    if not recipe:
        return "❌ Recipe not found."

    unlocked, lock_reason = is_recipe_unlocked(user, recipe_key)
    can_afford, miss_str  = can_afford_recipe(user, recipe_key) if unlocked else (False, "")
    speed      = get_craft_speed_multiplier(user)
    craft_time = _format_secs(int(recipe["craft_time_secs"] / speed))

    base_res  = user.get("base_resources", {}) or {}
    resources = base_res.get("resources", {}) or {}

    lines = [
        f"{recipe['emoji']} *{recipe['name']}*",
        f"_{recipe['description']}_",
        f"━━━━━━━━━━━━━━━━━━━━━━━━",
        f"Output: ×{recipe['output_qty']}  |  Time: {craft_time}",
    ]

    if recipe.get("server_unique"):
        lines.append("⚠️ *Server-unique* — only one can exist at a time")

    lines.append("\n*Ingredients:*")
    for ing, amount in recipe.get("ingredients", {}).items():
        have = resources.get(ing, 0)
        icon = "✅" if have >= amount else "❌"
        lines.append(f"  {icon} {ing}: {have}/{amount}")

    gold_cost = recipe.get("craft_cost_gold", 0)
    if gold_cost > 0:
        have_gold = user.get("gold", 0) or 0
        icon      = "✅" if have_gold >= gold_cost else "❌"
        lines.append(f"  {icon} Gold: {have_gold}/{gold_cost} 🪙")

    effect = recipe.get("effect", {})
    if effect:
        lines.append("\n*Effect:*")
        for k, v in effect.items():
            lines.append(f"  • {k.replace('_',' ').title()}: {v}")

    if not unlocked:
        lines.append(f"\n🔒 *Locked:* {lock_reason}")
    elif not can_afford:
        lines.append(f"\n❌ *Missing:* {miss_str}")
    else:
        lines.append(f"\n✅ *Ready to craft*")

    lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def format_craft_queue_display(user: dict) -> str:
    """Compact craft queue for HUD dashboard progress bars."""
    queue = user.get("craft_queue", []) or []
    if not queue:
        return ""

    now   = datetime.utcnow()
    lines = ["\n⚗️ *CRAFTING:*"]

    for entry in queue:
        name = entry.get("recipe_name", "?")
        try:
            started = datetime.fromisoformat(entry["started_at"])
            done    = datetime.fromisoformat(entry["done_at"])
            total   = max(1, (done - started).total_seconds())
            elapsed = (now - started).total_seconds()
            pct     = min(100, int(elapsed / total * 100))
            rem     = max(0, (done - now).total_seconds())
            filled  = pct // 5
            bar     = "█" * filled + "░" * (20 - filled)
            lines.append(f"  {name}\n  [{bar}] {pct}% — {_format_secs(int(rem))}")
        except Exception:
            lines.append(f"  {name} — in progress")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
#  INLINE KEYBOARDS
# ═══════════════════════════════════════════════════════════════════════════

def kb_craft_menu(user: dict) -> InlineKeyboardMarkup:
    """Crafting menu with category tabs."""
    buttons = []
    for cat, label in CATEGORY_LABELS.items():
        has_available = any(
            is_recipe_unlocked(user, rk)[0]
            for rk, rv in RECIPES.items()
            if rv.get("category") == cat
            and (not rv.get("hidden") or rk in (user.get("discovered_recipes") or []))
        )
        icon = "" if has_available else "🔒 "
        buttons.append([InlineKeyboardButton(
            text=f"{icon}{label}",
            callback_data=f"craft:cat:{cat}"
        )])

    buttons.append([InlineKeyboardButton("⬅️ My Base", callback_data="menu_base")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_recipe_list(user: dict, category: str) -> InlineKeyboardMarkup:
    """List of recipes in a category."""
    buttons  = []
    speed    = get_craft_speed_multiplier(user)

    for rkey, recipe in RECIPES.items():
        if recipe.get("category") != category:
            continue
        if recipe.get("hidden") and rkey not in (user.get("discovered_recipes") or []):
            continue

        unlocked, _ = is_recipe_unlocked(user, rkey)
        can_afford, _ = can_afford_recipe(user, rkey) if unlocked else (False, "")
        emoji = recipe["emoji"]
        name  = recipe["name"]
        icon  = "⚗️" if (unlocked and can_afford) else ("💡" if unlocked else "🔒")

        buttons.append([InlineKeyboardButton(
            text=f"{icon} {emoji} {name}",
            callback_data=f"craft:detail:{rkey}"
        )])

    buttons.append([InlineKeyboardButton("⬅️ Categories", callback_data="craft:menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_recipe_detail(recipe_key: str, user: dict) -> InlineKeyboardMarkup:
    """Recipe detail with craft/speedup/back buttons."""
    recipe    = RECIPES.get(recipe_key, {})
    unlocked, _ = is_recipe_unlocked(user, recipe_key)
    can_afford, _ = can_afford_recipe(user, recipe_key) if unlocked else (False, "")
    cat       = recipe.get("category", "consumable")

    buttons = []
    if unlocked and can_afford:
        buttons.append([InlineKeyboardButton(
            text=f"⚗️ Craft {recipe.get('name','')}", callback_data=f"craft:start:{recipe_key}"
        )])

    # Check if currently crafting this
    queue = user.get("craft_queue", []) or []
    in_queue = any(e.get("recipe_key") == recipe_key for e in queue)
    if in_queue:
        buttons.append([InlineKeyboardButton(
            text="⏩ Apply Speedup", callback_data=f"craft:speedup_menu:{recipe_key}"
        )])

    buttons.append([InlineKeyboardButton(f"⬅️ Back", callback_data=f"craft:cat:{cat}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ═══════════════════════════════════════════════════════════════════════════
#  INTERNAL HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _deduct_ingredients(user: dict, recipe: dict) -> dict:
    """Remove ingredients (base resources) and gold cost (top-level field)."""
    base_res  = user.get("base_resources", {}) or {}
    resources = base_res.get("resources", {}) or {}

    for ingredient, amount in recipe.get("ingredients", {}).items():
        resources[ingredient] = max(0, resources.get(ingredient, 0) - amount)

    base_res["resources"]  = resources
    user["base_resources"] = base_res

    gold_cost = recipe.get("craft_cost_gold", 0)
    if gold_cost > 0:
        user["gold"] = max(0, (user.get("gold", 0) or 0) - gold_cost)

    return user


def _check_server_unique_active(recipe_key: str) -> bool:
    """Check if a server-unique item is currently active somewhere."""
    try:
        flag_file = f"unique_{recipe_key}.txt"
        if not os.path.exists(flag_file):
            return False
        with open(flag_file) as f:
            expires_str = f.read().strip()
        expires = datetime.fromisoformat(expires_str)
        return datetime.utcnow() < expires
    except Exception:
        return False


def _mark_server_unique_active(recipe_key: str, duration_minutes: int = 1440):
    """Mark a server-unique item as active."""
    import os
    try:
        flag_file = f"unique_{recipe_key}.txt"
        expires   = (datetime.utcnow() + timedelta(minutes=duration_minutes)).isoformat()
        with open(flag_file, "w") as f:
            f.write(expires)
    except Exception:
        pass


def _format_secs(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        m = seconds // 60
        s = seconds % 60
        return f"{m}m {s}s" if s else f"{m}m"
    else:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h}h {m}m"


import os