# -*- coding: utf-8 -*-
"""
resource_registry.py — Master Resource & Token Registry
========================================================
Single source of truth for every resource, token, and consumable item
in the game. All other systems read from here dynamically.

TO ADD A NEW RESOURCE:
  1. Copy the template at the bottom of this file
  2. Fill in the fields
  3. Add the matching research entry in research_tree.py
  4. Done — inventory, shop, power, and sector systems pick it up automatically

CATEGORIES:
  basic             — Wood, bronze, iron, stone (core building materials)
  premium           — Gold (earnable premium currency)
  premium_scarce    — Bitcoin (ultra scarce, high value)
  crypto            — Satoshi, blockchain_fragment, crypto_dust (Crypto Wastes sector)
  commander_resource— Energy (commander-only, not in base vault)
  protective_item   — Suits, formats, wallets (consumables with timers)
  relic             — Relics and unique sector drops
"""

from typing import Optional

# ═══════════════════════════════════════════════════════════════════════════
#  MASTER RESOURCE REGISTRY
# ═══════════════════════════════════════════════════════════════════════════

RESOURCES: dict = {

    # ──────────────────────────────────────────────────────────────────────
    # BASIC RESOURCES — Available from the start, no research required
    # ──────────────────────────────────────────────────────────────────────

    "wood": {
        "display_name": "Wood",
        "emoji": "🪵",
        "category": "basic",
        "stackable": True,
        "tradeable": True,
        "research_required": None,
        "max_stack": 999999,
        "base_weight": 1,
        "description": "Basic building material. Found everywhere. Used in most construction.",
        "drop_sources": ["word_game", "sector_1", "sector_7", "sector_8",
                         "iron_mine_node", "stone_quarry_node"],
        "shop_purchasable": False,
        "sink_uses": ["building", "traps", "research", "crafting"],
        "decimal_allowed": False,
        "commander_only": False,
        "consumable": False,
        "regen_per_hour": None,
        "conversion": None,
    },

    "bronze": {
        "display_name": "Bronze",
        "emoji": "🧱",
        "category": "basic",
        "stackable": True,
        "tradeable": True,
        "research_required": None,
        "max_stack": 999999,
        "base_weight": 1,
        "description": "Early-game metal. Used for traps and basic military.",
        "drop_sources": ["word_game", "sector_1", "sector_2", "sector_4", "sector_8"],
        "shop_purchasable": False,
        "sink_uses": ["building", "traps", "training", "research"],
        "decimal_allowed": False,
        "commander_only": False,
        "consumable": False,
        "regen_per_hour": None,
        "conversion": None,
    },

    "iron": {
        "display_name": "Iron",
        "emoji": "⛓️",
        "category": "basic",
        "stackable": True,
        "tradeable": True,
        "research_required": None,
        "max_stack": 999999,
        "base_weight": 2,
        "description": "Mid-tier metal. Core military and advanced building material.",
        "drop_sources": ["word_game", "sector_1", "sector_2", "sector_3",
                         "sector_5", "sector_9", "iron_mine_node"],
        "shop_purchasable": False,
        "sink_uses": ["building", "traps", "research", "crafting", "suits"],
        "decimal_allowed": False,
        "commander_only": False,
        "consumable": False,
        "regen_per_hour": None,
        "conversion": None,
    },

    "stone": {
        "display_name": "Stone",
        "emoji": "🪨",
        "category": "basic",
        "stackable": True,
        "tradeable": True,
        "research_required": None,
        "max_stack": 999999,
        "base_weight": 3,
        "description": "Heavy construction material. Required for advanced structures.",
        "drop_sources": ["word_game", "sector_3", "sector_5", "sector_6",
                         "sector_8", "sector_9", "stone_quarry_node"],
        "shop_purchasable": False,
        "sink_uses": ["building", "traps", "research", "suits"],
        "decimal_allowed": False,
        "commander_only": False,
        "consumable": False,
        "regen_per_hour": None,
        "conversion": None,
    },

    "relics": {
        "display_name": "Relics",
        "emoji": "🏺",
        "category": "relic",
        "stackable": True,
        "tradeable": True,
        "research_required": None,
        "max_stack": 99999,
        "base_weight": 5,
        "description": "Ancient artifacts. Rare and powerful. Used in high-tier research and crafting.",
        "drop_sources": ["word_game", "sector_4", "sector_6", "sector_7",
                         "sector_9", "relic_cache_node", "ancient_vault_node",
                         "vault_sector_60", "vault_sector_64"],
        "shop_purchasable": False,
        "sink_uses": ["research", "crafting", "prestige", "suits", "scrolls"],
        "decimal_allowed": False,
        "commander_only": False,
        "consumable": False,
        "regen_per_hour": None,
        "conversion": None,
    },

    # ──────────────────────────────────────────────────────────────────────
    # PREMIUM CURRENCIES
    # ──────────────────────────────────────────────────────────────────────

    "gold": {
        "display_name": "Gold",
        "emoji": "🪙",
        "category": "premium",
        "stackable": True,
        "tradeable": True,
        "research_required": None,
        "max_stack": 999999,
        "base_weight": 0,
        "description": "Premium in-game currency. Earnable and purchasable. Used in the store.",
        "drop_sources": ["vault_sectors", "daily_claim", "bounty_rewards",
                         "sector_dominance_reward", "predator_loot"],
        "shop_purchasable": True,
        "shop_cost": None,          # This IS a store currency, not bought with itself
        "sink_uses": ["store", "speedups", "suits", "scrolls", "shield_purchase",
                      "teleport_bundles", "bounty_placement"],
        "decimal_allowed": False,
        "commander_only": False,
        "consumable": False,
        "regen_per_hour": None,
        "conversion": None,
    },

    "bitcoin": {
        "display_name": "Bitcoin",
        "emoji": "₿",
        "category": "premium_scarce",
        "stackable": True,
        "tradeable": True,
        "research_required": "advanced_mining",
        "max_stack": 999,
        "base_weight": 0,
        "description": "Scarce digital currency. Extremely rare. Highest value resource in the game.",
        "drop_sources": ["bitcoin_node", "vault_sector_60", "vault_sector_64",
                         "prestige_reward", "satoshi_conversion"],
        "shop_purchasable": True,
        "shop_cost": None,          # Real-money purchase in store
        "sink_uses": ["store_purchases", "teleport_bundles", "alliance_shop",
                      "advanced_research", "cold_wallet_craft"],
        "decimal_allowed": True,    # Can hold 0.001 BTC
        "decimal_places": 8,
        "commander_only": False,
        "consumable": False,
        "regen_per_hour": None,
        "conversion": None,
    },

    # ──────────────────────────────────────────────────────────────────────
    # COMMANDER RESOURCE
    # ──────────────────────────────────────────────────────────────────────

    "energy": {
        "display_name": "Energy",
        "emoji": "⚡",
        "category": "commander_resource",
        "stackable": True,
        "tradeable": False,         # Soulbound — commander personal resource
        "research_required": "energy_systems",
        "max_stack": 500,
        "base_weight": 0,
        "description": "Commander energy. Used for predator combat and gun range. Regenerates over time.",
        "drop_sources": ["passive_regen", "energy_cell_item", "daily_claim"],
        "shop_purchasable": True,
        "shop_cost": {"gold": 50},  # 50 gold = 100 energy
        "shop_amount": 100,
        "sink_uses": ["predator_combat", "gun_range"],
        "decimal_allowed": False,
        "commander_only": True,     # Does NOT appear in base vault
        "consumable": False,
        "regen_per_hour": 10,       # +10 energy per hour passively
        "cost_per_action": 50,
        "conversion": None,
    },

    # ──────────────────────────────────────────────────────────────────────
    # CRYPTO SECTOR RESOURCES — Locked behind crypto_mining_101 research
    # ──────────────────────────────────────────────────────────────────────

    "satoshi": {
        "display_name": "Satoshi",
        "emoji": "⚡₿",
        "category": "crypto",
        "stackable": True,
        "tradeable": True,
        "research_required": "crypto_mining_101",
        "max_stack": 9999999,
        "base_weight": 0,
        "description": "Fractional Bitcoin. Accumulates into BTC. 100,000 Satoshi = 1 BTC.",
        "drop_sources": ["binance_node", "coinbase_node", "kraken_node"],
        "shop_purchasable": False,
        "sink_uses": ["convert_to_bitcoin"],
        "decimal_allowed": False,
        "commander_only": False,
        "consumable": False,
        "regen_per_hour": None,
        "conversion": {"to": "bitcoin", "rate": 100000},  # 100k satoshi = 1 BTC
    },

    "crypto_dust": {
        "display_name": "Crypto Dust",
        "emoji": "✨",
        "category": "crypto",
        "stackable": True,
        "tradeable": True,
        "research_required": "crypto_mining_101",
        "max_stack": 9999,
        "base_weight": 0,
        "description": "Worthless fragments left after a rug pull or crash. Can be refined into Satoshi.",
        "drop_sources": ["rug_pull_hazard", "market_crash_hazard"],
        "shop_purchasable": False,
        "sink_uses": ["refine_to_satoshi"],
        "decimal_allowed": False,
        "commander_only": False,
        "consumable": False,
        "regen_per_hour": None,
        "conversion": {"to": "satoshi", "rate": 1000},    # 1000 dust = 1 satoshi
    },

    "blockchain_fragment": {
        "display_name": "Blockchain Fragment",
        "emoji": "🔗",
        "category": "crypto",
        "stackable": True,
        "tradeable": False,         # Soulbound — cannot be traded
        "research_required": "distributed_ledger",
        "max_stack": 500,
        "base_weight": 0,
        "description": "A verified block of chain data. Used to craft Bitcoin Format and Cold Wallet items.",
        "drop_sources": ["binance_node", "kraken_node", "deep_web_node"],
        "shop_purchasable": False,
        "sink_uses": ["craft_bitcoin_format", "craft_cold_wallet", "advanced_crypto_research"],
        "decimal_allowed": False,
        "commander_only": False,
        "consumable": False,
        "regen_per_hour": None,
        "conversion": None,
    },

    # ──────────────────────────────────────────────────────────────────────
    # PROTECTIVE ITEMS — Consumable suits and formats with timers
    # ──────────────────────────────────────────────────────────────────────

    "basic_suit": {
        "display_name": "Basic Radiation Suit",
        "emoji": "🧪",
        "category": "protective_item",
        "stackable": True,
        "tradeable": True,
        "research_required": "hazard_awareness",
        "max_stack": 10,
        "base_weight": 5,
        "description": "Basic protection against lethal heat and radiation. Lasts 10 minutes. "
                       "Required for hazardous sector phases (Tier 1).",
        "drop_sources": ["store", "alliance_shop", "craft"],
        "shop_purchasable": True,
        "shop_cost": {"gold": 150},
        "craft_cost": {"iron": 50, "bronze": 30},
        "sink_uses": ["equip_suit"],
        "decimal_allowed": False,
        "commander_only": False,
        "consumable": True,
        "duration_minutes": 10,
        "protects_against": ["lethal_heat", "toxic_gas"],
        "suit_tier": 1,
        "regen_per_hour": None,
        "conversion": None,
    },

    "hazmat_suit": {
        "display_name": "Hazmat Suit",
        "emoji": "☢️",
        "category": "protective_item",
        "stackable": True,
        "tradeable": True,
        "research_required": "hazmat_engineering",
        "max_stack": 5,
        "base_weight": 8,
        "description": "Full hazmat protection. Lasts 20 minutes. "
                       "Protects against heat, gas, and basic radiation (Tier 2).",
        "drop_sources": ["store", "alliance_shop", "craft"],
        "shop_purchasable": True,
        "shop_cost": {"gold": 300},
        "craft_cost": {"iron": 100, "stone": 20, "relics": 5},
        "sink_uses": ["equip_suit"],
        "decimal_allowed": False,
        "commander_only": False,
        "consumable": True,
        "duration_minutes": 20,
        "protects_against": ["lethal_heat", "toxic_gas", "void_radiation"],
        "suit_tier": 2,
        "regen_per_hour": None,
        "conversion": None,
    },

    "void_suit": {
        "display_name": "Void Suit",
        "emoji": "🌑",
        "category": "protective_item",
        "stackable": True,
        "tradeable": True,
        "research_required": "void_theory",
        "max_stack": 3,
        "base_weight": 10,
        "description": "Cosmic-grade protection. Required for Void Canyon. Lasts 15 minutes. "
                       "The only suit that survives void radiation (Tier 3).",
        "drop_sources": ["store", "vault_sectors"],  # Cannot be crafted
        "shop_purchasable": True,
        "shop_cost": {"gold": 800},
        "craft_cost": None,         # Cannot be crafted
        "sink_uses": ["equip_suit"],
        "decimal_allowed": False,
        "commander_only": False,
        "consumable": True,
        "duration_minutes": 15,
        "protects_against": ["void_radiation", "reality_distortion"],
        "suit_tier": 3,
        "void_sector_compatible": True,
        "regen_per_hour": None,
        "conversion": None,
    },

    "bitcoin_format": {
        "display_name": "Bitcoin Format",
        "emoji": "💾",
        "category": "protective_item",
        "stackable": True,
        "tradeable": True,
        "research_required": "crypto_security",
        "max_stack": 10,
        "base_weight": 0,
        "description": "Formats your wallet against scammers and rug pulls. "
                       "Required for Crypto Wastes hazard phases. Lasts 20 minutes.",
        "drop_sources": ["store", "alliance_shop", "craft"],
        "shop_purchasable": True,
        "shop_cost": {"gold": 200},
        "craft_cost": {"blockchain_fragment": 5, "iron": 20},
        "sink_uses": ["equip_suit"],
        "decimal_allowed": False,
        "commander_only": False,
        "consumable": True,
        "duration_minutes": 20,
        "protects_against": ["rug_pull", "crypto_scammer", "market_crash"],
        "suit_tier": 2,
        "regen_per_hour": None,
        "conversion": None,
    },

    "cold_wallet": {
        "display_name": "Cold Wallet",
        "emoji": "🔐",
        "category": "protective_item",
        "stackable": True,
        "tradeable": True,
        "research_required": "advanced_crypto_security",
        "max_stack": 3,
        "base_weight": 0,
        "description": "Offline storage. Immune to ALL crypto sector hazards for 45 minutes. "
                       "Required for Deep Web node. Survives Market Crash (Tier 3).",
        "drop_sources": ["store", "craft"],
        "shop_purchasable": True,
        "shop_cost": {"gold": 500, "bitcoin": 0.001},
        "craft_cost": {"blockchain_fragment": 20, "relics": 10},
        "sink_uses": ["equip_suit"],
        "decimal_allowed": False,
        "commander_only": False,
        "consumable": True,
        "duration_minutes": 45,
        "protects_against": ["rug_pull", "crypto_scammer", "market_crash", "51_percent_attack"],
        "suit_tier": 3,
        "regen_per_hour": None,
        "conversion": None,
    },

    # ──────────────────────────────────────────────────────────────────────
    # UTILITY ITEMS
    # ──────────────────────────────────────────────────────────────────────

    "speedup_5m": {
        "display_name": "5-Minute Speedup",
        "emoji": "⏩",
        "category": "utility",
        "stackable": True,
        "tradeable": True,
        "research_required": "siege_tactics",
        "max_stack": 99,
        "base_weight": 0,
        "description": "Reduces any march or build timer by 5 minutes.",
        "drop_sources": ["store", "word_game_rare", "bounty_reward"],
        "shop_purchasable": True,
        "shop_cost": {"gold": 30},
        "sink_uses": ["march_speedup", "build_speedup"],
        "decimal_allowed": False,
        "commander_only": False,
        "consumable": True,
        "duration_minutes": None,
        "reduces_timer_minutes": 5,
        "regen_per_hour": None,
        "conversion": None,
    },

    "speedup_30m": {
        "display_name": "30-Minute Speedup",
        "emoji": "⏩⏩",
        "category": "utility",
        "stackable": True,
        "tradeable": True,
        "research_required": "siege_tactics",
        "max_stack": 50,
        "base_weight": 0,
        "description": "Reduces any march or build timer by 30 minutes.",
        "drop_sources": ["store", "vault_sectors", "bounty_reward"],
        "shop_purchasable": True,
        "shop_cost": {"gold": 150},
        "sink_uses": ["march_speedup", "build_speedup"],
        "decimal_allowed": False,
        "commander_only": False,
        "consumable": True,
        "duration_minutes": None,
        "reduces_timer_minutes": 30,
        "regen_per_hour": None,
        "conversion": None,
    },

    "teleport_charge": {
        "display_name": "Teleport Charge",
        "emoji": "🌀",
        "category": "utility",
        "stackable": True,
        "tradeable": False,         # Cannot trade teleports
        "research_required": None,  # Free daily claim needs no research
        "max_stack": 99,
        "base_weight": 0,
        "description": "Single-use teleport to any sector. 3 free charges claimable daily. "
                       "Unclaimed daily charges expire at midnight UTC.",
        "drop_sources": ["daily_claim", "store"],
        "shop_purchasable": True,
        "shop_cost": {"gold": 40},  # 40 gold per extra teleport
        "shop_amount": 1,
        "sink_uses": ["teleport"],
        "decimal_allowed": False,
        "commander_only": False,
        "consumable": True,
        "daily_free_amount": 3,     # 3 free per day
        "regen_per_hour": None,
        "conversion": None,
    },

    "banishment_scroll": {
        "display_name": "Banishment Scroll",
        "emoji": "📜",
        "category": "utility",
        "stackable": True,
        "tradeable": False,         # Ruler tool — cannot trade
        "research_required": "sector_dominance",
        "max_stack": 5,
        "base_weight": 0,
        "description": "Expels a player from your controlled sector for 48 hours. "
                       "Sector Ruler use only. Banishment lifted if ruler loses control.",
        "drop_sources": ["store", "alliance_shop"],
        "shop_purchasable": True,
        "shop_cost": {"gold": 500, "relics": 10},
        "sink_uses": ["banish_player"],
        "decimal_allowed": False,
        "commander_only": False,
        "consumable": True,
        "banish_duration_hours": 48,
        "regen_per_hour": None,
        "conversion": None,
    },

    "shield_basic": {
        "display_name": "Basic Shield",
        "emoji": "🛡️",
        "category": "utility",
        "stackable": True,
        "tradeable": False,
        "research_required": None,
        "max_stack": 10,
        "base_weight": 0,
        "description": "Protects your base from raids for 8 hours. "
                       "Attackers can reduce duration by 2h per attack attempt.",
        "drop_sources": ["store", "daily_claim", "word_game_rare"],
        "shop_purchasable": True,
        "shop_cost": {"gold": 80},
        "sink_uses": ["activate_shield"],
        "decimal_allowed": False,
        "commander_only": False,
        "consumable": True,
        "shield_duration_hours": 8,
        "shield_drain_per_attack_hours": 2,
        "regen_per_hour": None,
        "conversion": None,
    },

    "shield_advanced": {
        "display_name": "Advanced Shield",
        "emoji": "🛡️🛡️",
        "category": "utility",
        "stackable": True,
        "tradeable": False,
        "research_required": "advanced_defense",
        "max_stack": 5,
        "base_weight": 0,
        "description": "Protects your base for 24 hours. "
                       "More resistant to disruption — attackers drain 1h per attempt.",
        "drop_sources": ["store"],
        "shop_purchasable": True,
        "shop_cost": {"gold": 200},
        "sink_uses": ["activate_shield"],
        "decimal_allowed": False,
        "commander_only": False,
        "consumable": True,
        "shield_duration_hours": 24,
        "shield_drain_per_attack_hours": 1,
        "regen_per_hour": None,
        "conversion": None,
    },
}


# ═══════════════════════════════════════════════════════════════════════════
#  REGISTRY HELPER FUNCTIONS
#  All other systems use these — never read RESOURCES dict directly
# ═══════════════════════════════════════════════════════════════════════════

def get_resource(key: str) -> Optional[dict]:
    """Get full resource definition. Returns None if key not found."""
    return RESOURCES.get(key)


def get_display_name(key: str) -> str:
    """Get display name for a resource key."""
    res = RESOURCES.get(key)
    return res["display_name"] if res else key.replace("_", " ").title()


def get_emoji(key: str) -> str:
    """Get emoji for a resource key."""
    res = RESOURCES.get(key)
    return res["emoji"] if res else "📦"


def is_unlocked(user: dict, resource_key: str) -> bool:
    """Check if a resource is unlocked for the given user."""
    res = RESOURCES.get(resource_key)
    if not res:
        return False
    required = res.get("research_required")
    if required is None:
        return True
    return bool(user.get("researches", {}).get(required, False))


def get_unlocked_resources(user: dict) -> dict:
    """Return all resources currently unlocked for this user."""
    return {k: v for k, v in RESOURCES.items() if is_unlocked(user, k)}


def get_resources_by_category(category: str) -> dict:
    """Get all resources of a given category."""
    return {k: v for k, v in RESOURCES.items() if v.get("category") == category}


def get_protective_items() -> dict:
    """Get all protective/suit items."""
    return get_resources_by_category("protective_item")


def get_suit_for_hazard(hazard_type: str) -> list:
    """
    Return list of resource keys that protect against a specific hazard.
    Used by sector cycle system to check if a player is protected.
    """
    suits = []
    for key, res in RESOURCES.items():
        if res.get("category") == "protective_item":
            if hazard_type in res.get("protects_against", []):
                suits.append(key)
    return suits


def get_drop_sources_for_sector(sector_id: int) -> list:
    """Get all resources that drop in a given sector."""
    sector_key = f"sector_{sector_id}"
    return [k for k, v in RESOURCES.items()
            if sector_key in v.get("drop_sources", [])]


def get_tradeable_resources() -> dict:
    """Get all resources that can be traded between alliance members."""
    return {k: v for k, v in RESOURCES.items() if v.get("tradeable", False)}


def get_purchasable_resources() -> dict:
    """Get all resources available in the store."""
    return {k: v for k, v in RESOURCES.items() if v.get("shop_purchasable", False)}


def get_stackable_resources() -> list:
    """Get list of resource keys that stack in inventory."""
    return [k for k, v in RESOURCES.items() if v.get("stackable", True)]


def get_conversions() -> dict:
    """Get all resources that have a conversion path."""
    return {k: v["conversion"] for k, v in RESOURCES.items()
            if v.get("conversion") is not None}


def can_convert(resource_key: str, user: dict) -> tuple:
    """
    Check if user can convert a resource.
    Returns (can_convert: bool, target_resource: str, rate: int, reason: str)
    """
    res = RESOURCES.get(resource_key)
    if not res:
        return False, None, 0, "Resource not found"
    conv = res.get("conversion")
    if not conv:
        return False, None, 0, f"{get_display_name(resource_key)} cannot be converted"
    if not is_unlocked(user, resource_key):
        return False, None, 0, f"Research required: {res.get('research_required')}"
    return True, conv["to"], conv["rate"], "OK"


def format_resource_amount(key: str, amount) -> str:
    """Format resource amount with emoji and name for display."""
    res = RESOURCES.get(key, {})
    emoji = res.get("emoji", "📦")
    name = res.get("display_name", key)
    if res.get("decimal_allowed") and isinstance(amount, float):
        return f"{emoji} {amount:.8f} {name}"
    return f"{emoji} {int(amount):,} {name}"


def validate_resource_key(key: str) -> bool:
    """Check if a resource key exists in the registry."""
    return key in RESOURCES


def get_all_keys() -> list:
    """Get all registered resource keys."""
    return list(RESOURCES.keys())


def get_regen_resources() -> dict:
    """Get all resources that regenerate over time."""
    return {k: v for k, v in RESOURCES.items()
            if v.get("regen_per_hour") is not None}


def apply_energy_regen(user: dict) -> dict:
    """
    Apply passive energy regeneration based on time elapsed since last regen.
    Call this whenever user data is loaded.
    Returns updated user dict.
    """
    from datetime import datetime

    if not is_unlocked(user, "energy"):
        return user

    energy_res = RESOURCES["energy"]
    regen_rate = energy_res["regen_per_hour"]
    max_energy = energy_res["max_stack"]

    last_regen_str = user.get("energy_last_regen")
    now = datetime.utcnow()

    if last_regen_str:
        try:
            last_regen = datetime.fromisoformat(last_regen_str)
            hours_elapsed = (now - last_regen).total_seconds() / 3600
            regen_amount = int(hours_elapsed * regen_rate)
            if regen_amount > 0:
                current = user.get("energy", 0)
                user["energy"] = min(current + regen_amount, max_energy)
                user["energy_last_regen"] = now.isoformat()
        except Exception:
            user["energy_last_regen"] = now.isoformat()
    else:
        user["energy_last_regen"] = now.isoformat()

    return user


# ═══════════════════════════════════════════════════════════════════════════
#  INVENTORY MIGRATION
#  Converts old unclaimed_items list format to new stacked inventory dict
# ═══════════════════════════════════════════════════════════════════════════

def migrate_inventory(user: dict) -> dict:
    """
    One-time migration from old unclaimed_items list to stacked inventory dict.
    Safe to call on every load — detects old format and converts, skips if already new.
    """
    # Already migrated or empty
    if isinstance(user.get("inventory"), dict):
        return user

    old_items = user.get("unclaimed_items", [])
    if not isinstance(old_items, list):
        user["inventory"] = {}
        return user

    new_inventory: dict = {}

    for item in old_items:
        if not isinstance(item, dict):
            continue
        key = item.get("key", item.get("type", "unknown"))
        amount = item.get("amount", item.get("qty", 1))

        if key == "unknown" or not key:
            continue

        if key in new_inventory:
            new_inventory[key]["qty"] += amount
        else:
            res = RESOURCES.get(key, {})
            new_inventory[key] = {
                "qty": amount,
                "display": res.get("display_name", key.replace("_", " ").title()),
                "emoji": res.get("emoji", "📦"),
                "category": res.get("category", "misc"),
            }

    user["inventory"] = new_inventory
    user["unclaimed_items"] = []   # Clear old list
    return user


def format_inventory_display(user: dict) -> str:
    """Format the player's full inventory for display. Grouped by category."""
    inventory = user.get("inventory", {})
    if not inventory:
        return "🎒 *Backpack is empty*"

    # Group by category
    categories: dict = {}
    for key, data in inventory.items():
        if data.get("qty", 0) <= 0:
            continue
        cat = data.get("category", "misc")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append((key, data))

    category_labels = {
        "basic": "📦 Basic Resources",
        "premium": "🪙 Premium Currency",
        "premium_scarce": "₿ Scarce Assets",
        "crypto": "💻 Crypto Assets",
        "commander_resource": "⚡ Commander Resources",
        "protective_item": "🧪 Protective Items",
        "utility": "🔧 Utility Items",
        "relic": "🏺 Relics & Artifacts",
        "misc": "🎁 Miscellaneous",
    }

    lines = ["🎒 *BACKPACK*\n━━━━━━━━━━━━━━━━━━━━━━━━"]

    for cat, label in category_labels.items():
        if cat not in categories:
            continue
        lines.append(f"\n{label}")
        for key, data in sorted(categories[cat], key=lambda x: x[1]["qty"], reverse=True):
            emoji = data.get("emoji", "📦")
            name = data.get("display", key)
            qty = data.get("qty", 0)
            res = RESOURCES.get(key, {})
            if res.get("decimal_allowed") and isinstance(qty, float):
                qty_str = f"{qty:.8f}"
            else:
                qty_str = f"{qty:,}"
            lines.append(f"  {emoji} {name}: ×{qty_str}")

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
#  NEW RESOURCE TEMPLATE
#  Copy this block and fill in the fields to add a new resource.
#  Then add the matching research entry in research_tree.py.
# ═══════════════════════════════════════════════════════════════════════════

"""
"RESOURCE_KEY": {
    "display_name": "",
    "emoji": "",
    "category": "",           # basic/premium/premium_scarce/crypto/
                              # commander_resource/protective_item/relic/utility
    "stackable": True,
    "tradeable": True,        # False = soulbound
    "research_required": "",  # Research key string, or None if available from start
    "max_stack": 999999,
    "base_weight": 1,         # 0 for digital/weightless
    "description": "",
    "drop_sources": [],       # node names, sector IDs (e.g. "sector_3"), event names
    "shop_purchasable": False,
    "shop_cost": {},          # {"gold": X} or {"bitcoin": X} or None
    "craft_cost": None,       # {"resource_key": amount} or None
    "sink_uses": [],          # What consumes/destroys this resource
    "decimal_allowed": False, # True for BTC-type resources
    "commander_only": False,  # True = doesn't show in base vault
    "consumable": False,      # True = one-time use item
    "duration_minutes": None, # For consumables with timers
    "protects_against": [],   # For protective items — list of hazard keys
    "suit_tier": None,        # 1/2/3 for protective suits
    "regen_per_hour": None,   # For regenerating resources like energy
    "conversion": None,       # {"to": "other_key", "rate": X} or None
    "banish_duration_hours": None,
    "shield_duration_hours": None,
    "shield_drain_per_attack_hours": None,
    "daily_free_amount": None,
    "reduces_timer_minutes": None,
    "void_sector_compatible": False,
},
"""
