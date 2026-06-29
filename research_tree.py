# -*- coding: utf-8 -*-
"""
research_tree.py — Master Research & Unlock System
===================================================
Every feature, node type, resource, and action in the game is locked
behind a research entry. Completing research unlocks the listed items.

STRUCTURE:
  - RESEARCH_TREE dict: all research definitions
  - Helper functions: check prerequisites, start research, complete research
  - Format functions: display research menu, progress, tree view

TIERS:
  1 — Starter (no prerequisites, low cost, fast)
  2 — Mid-game (one prerequisite)
  3 — Advanced (two prerequisites, higher cost)
  4 — Endgame (deep prerequisites, expensive, slow)

TO ADD A NEW RESEARCH:
  1. Add entry to RESEARCH_TREE below
  2. List what it unlocks in the "unlocks" field
  3. Set prerequisites and tier
  4. Add matching resource entries in resource_registry.py if needed
"""

from datetime import datetime, timedelta
from typing import Tuple, Dict, List, Optional
from supabase_db import get_user, save_user

# ═══════════════════════════════════════════════════════════════════════════
#  RESEARCH TREE DEFINITION
# ═══════════════════════════════════════════════════════════════════════════

RESEARCH_TREE: Dict[str, dict] = {

    # ──────────────────────────────────────────────────────────────────────
    # TIER 1 — Starter Research (no prerequisites)
    # ──────────────────────────────────────────────────────────────────────

    "basic_mining": {
        "name": "⛏️ Basic Mining",
        "tier": 1,
        "prerequisites": [],
        "cost": {"wood": 50, "bronze": 20},
        "time_seconds": 300,
        "unlocks": [
            "iron_mine_node",        # Can occupy iron mine nodes
            "stone_quarry_node",     # Can occupy stone quarry nodes
            "node_collect",          # !collect command
            "node_occupy",           # !occupy command
        ],
        "description": "Teaches your troops to extract iron and stone from sector nodes.",
        "category": "resource",
        "power_reward": 100,
    },

    "basic_scouting": {
        "name": "🔭 Basic Scouting",
        "tier": 1,
        "prerequisites": [],
        "cost": {"bronze": 30},
        "time_seconds": 300,
        "unlocks": [
            "scout_action",          # !scout command
            "scout_same_sector",     # Can scout players in same sector
        ],
        "description": "Trains scouts to observe enemy positions. "
                       "Scouts can only operate within your current sector.",
        "category": "military",
        "power_reward": 100,
    },

    "basic_trapping": {
        "name": "🪤 Basic Trapping",
        "tier": 1,
        "prerequisites": [],
        "cost": {"wood": 80},
        "time_seconds": 240,
        "unlocks": [
            "spike_pit",             # Trap type
            "arrow_tower",           # Trap type
            "mousetrap",             # Anti-scout trap
        ],
        "description": "Unlocks basic trap construction at your base.",
        "category": "defense",
        "power_reward": 80,
    },

    "sector_awareness": {
        "name": "📡 Sector Awareness",
        "tier": 1,
        "prerequisites": [],
        "cost": {"bronze": 40},
        "time_seconds": 180,
        "unlocks": [
            "sector_report",         # See the sector event feed
            "sector_map_view",       # !map command — see all nodes
            "sector_phase_warning",  # Get warned before phase changes
        ],
        "description": "Gives your command post awareness of sector-wide events "
                       "and incoming hazard phases.",
        "category": "intelligence",
        "power_reward": 80,
    },

    "basic_construction": {
        "name": "🏗️ Basic Construction",
        "tier": 1,
        "prerequisites": [],
        "cost": {"wood": 100},
        "time_seconds": 240,
        "unlocks": [
            "storage",               # Storage building
            "mine",                  # Mine building
            "farm",                  # Farm building
        ],
        "description": "Unlocks resource buildings for your base.",
        "category": "building",
        "power_reward": 80,
    },

    "basic_military": {
        "name": "⚔️ Basic Military",
        "tier": 1,
        "prerequisites": [],
        "cost": {"bronze": 50, "wood": 30},
        "time_seconds": 300,
        "unlocks": [
            "training_grounds",      # Building
            "barracks",              # Building
            "footmen_training",      # Troop type
            "archers_training",      # Troop type
            "march_action",          # !march command — send troops to node
        ],
        "description": "Establishes your military hierarchy. Unlocks troop training and marching.",
        "category": "military",
        "power_reward": 120,
    },

    "hazard_awareness": {
        "name": "☢️ Hazard Awareness",
        "tier": 1,
        "prerequisites": ["sector_awareness"],
        "cost": {"iron": 30, "stone": 10},
        "time_seconds": 600,
        "unlocks": [
            "hazard_warning_system", # Receive hazard alerts before phase hits
            "suit_purchase_basic",   # Can buy basic_suit from store
            "basic_suit",            # Resource unlocked
            "sector_phase_timer",    # See exact timer on current phase
        ],
        "description": "Alerts you to incoming hazardous sector phases. "
                       "Unlocks Basic Radiation Suit for purchase.",
        "category": "survival",
        "power_reward": 150,
    },

    # ──────────────────────────────────────────────────────────────────────
    # TIER 2 — Mid-Game Research
    # ──────────────────────────────────────────────────────────────────────

    "advanced_mining": {
        "name": "⛏️ Advanced Mining",
        "tier": 2,
        "prerequisites": ["basic_mining"],
        "cost": {"iron": 40, "bronze": 60},
        "time_seconds": 600,
        "unlocks": [
            "relic_cache_node",      # Can occupy relic cache nodes
            "bitcoin_node_access",   # Can occupy bitcoin nodes (vault sectors)
            "bitcoin",               # Bitcoin resource unlocked
            "node_capacity_boost",   # +25% node resource capacity
        ],
        "description": "Advanced extraction techniques. Unlocks relic and bitcoin node access.",
        "category": "resource",
        "power_reward": 200,
    },

    "resource_compression": {
        "name": "📦 Resource Compression",
        "tier": 2,
        "prerequisites": ["basic_mining"],
        "cost": {"wood": 100, "bronze": 50},
        "time_seconds": 480,
        "unlocks": [
            "item_stacking",         # Items of same type merge in backpack
            "bulk_collect",          # Collect all pending nodes at once
        ],
        "description": "Items and resources of the same type now stack in your backpack. "
                       "No more individual entries for every XP drop.",
        "category": "logistics",
        "power_reward": 100,
    },

    "siege_tactics": {
        "name": "⚔️ Siege Tactics",
        "tier": 2,
        "prerequisites": ["basic_scouting", "basic_military"],
        "cost": {"iron": 50, "bronze": 40},
        "time_seconds": 600,
        "unlocks": [
            "node_attack",           # !attack [node] command
            "march_speedup_use",     # Can use speedup items on marches
            "speedup_5m",            # 5-min speedup item unlocked
            "speedup_30m",           # 30-min speedup item unlocked
            "lancer_training",       # Troop type
        ],
        "description": "Offensive doctrine. Unlocks node attacks, speedups, and advanced troops.",
        "category": "military",
        "power_reward": 200,
    },

    "alliance_protocols": {
        "name": "👥 Alliance Protocols",
        "tier": 2,
        "prerequisites": ["sector_awareness"],
        "cost": {"bronze": 60, "wood": 80},
        "time_seconds": 480,
        "unlocks": [
            "alliance_store_access", # Can buy from alliance shop
            "alliance_tasks",        # Alliance tasks become available
            "alliance_points_earning", # Earn AP from tasks
            "alliance_broadcast",    # !alliance chat relay command
            "resource_sharing",      # !share command with alliance members
        ],
        "description": "Establishes alliance infrastructure. "
                       "Unlocks alliance shop, tasks, AP earning, and comms relay.",
        "category": "alliance",
        "power_reward": 150,
    },

    "advanced_defense": {
        "name": "🛡️ Advanced Defense",
        "tier": 2,
        "prerequisites": ["basic_trapping"],
        "cost": {"iron": 60, "stone": 20},
        "time_seconds": 600,
        "unlocks": [
            "walls",                 # Building
            "armory",                # Building
            "shield_advanced",       # 24h shield item
            "cannon",                # Trap type
            "poison_gas",            # Trap type
        ],
        "description": "Hardens your base. Advanced shield, walls, and trap types.",
        "category": "defense",
        "power_reward": 200,
    },

    "sector_dominance": {
        "name": "👑 Sector Dominance",
        "tier": 2,
        "prerequisites": ["sector_awareness", "basic_military"],
        "cost": {"iron": 50, "relics": 5},
        "time_seconds": 720,
        "unlocks": [
            "dominance_score_tracking", # See your dominance score
            "pvp_node_occupy",       # Can occupy PvP outpost nodes
            "ruler_tax_receive",     # If ruler, receive resource taxes
            "banishment_scroll",     # Item unlocked for purchase
            "bounty_board_access",   # Can view and place bounties
        ],
        "description": "Opens the path to sector rulership. "
                       "Unlocks PvP nodes, bounty board, and banishment.",
        "category": "dominance",
        "power_reward": 250,
    },

    "crypto_mining_101": {
        "name": "₿ Crypto Mining 101",
        "tier": 2,
        "prerequisites": ["advanced_mining"],
        "cost": {"iron": 50, "relics": 10},
        "time_seconds": 900,
        "unlocks": [
            "sector_65_access",      # Crypto Wastes sector entry
            "satoshi",               # Satoshi resource unlocked
            "crypto_dust",           # Crypto dust resource unlocked
            "binance_node",          # Node type
            "coinbase_node",         # Node type
        ],
        "description": "Opens access to the Crypto Wastes sector. "
                       "Unlocks Satoshi and Crypto Dust resources.",
        "category": "crypto",
        "power_reward": 300,
    },

    # ──────────────────────────────────────────────────────────────────────
    # TIER 3 — Advanced Research
    # ──────────────────────────────────────────────────────────────────────

    "hazmat_engineering": {
        "name": "☢️ Hazmat Engineering",
        "tier": 3,
        "prerequisites": ["hazard_awareness"],
        "cost": {"iron": 100, "stone": 20, "relics": 5},
        "time_seconds": 1200,
        "unlocks": [
            "hazmat_suit",           # Hazmat suit resource unlocked
            "suit_purchase_hazmat",  # Can buy hazmat suit from store
            "ancient_vault_node",    # Can occupy ancient vault nodes
            "lava_moat",             # Trap type
        ],
        "description": "Full hazmat protection engineering. "
                       "Unlocks the 20-minute Hazmat Suit and ancient vault nodes.",
        "category": "survival",
        "power_reward": 350,
    },

    "commander_doctrine": {
        "name": "🎖️ Commander Doctrine",
        "tier": 3,
        "prerequisites": ["siege_tactics"],
        "cost": {"relics": 10, "iron": 60},
        "time_seconds": 900,
        "unlocks": [
            "skill_tree_access",     # Commander skill tree UI
            "commander_skill_points", # Skill points now allocatable
            "castellan_training",    # Troop type
            "war_room",              # Building
        ],
        "description": "Establishes commander specialization doctrine. "
                       "Unlocks the 4-path skill tree and elite troops.",
        "category": "military",
        "power_reward": 400,
    },

    "energy_systems": {
        "name": "⚡ Energy Systems",
        "tier": 3,
        "prerequisites": ["advanced_mining"],
        "cost": {"iron": 80, "relics": 8},
        "time_seconds": 1200,
        "unlocks": [
            "energy",                # Energy commander resource unlocked
            "predator_combat",       # Can attack predators on nodes
            "gun_range_access",      # Gun range mini-game in base sector
            "energy_cell_item",      # Energy refill item in store
        ],
        "description": "Installs energy infrastructure. "
                       "Unlocks energy token, predator combat, and the gun range.",
        "category": "resource",
        "power_reward": 350,
    },

    "advanced_trapping": {
        "name": "🔱 Advanced Trapping",
        "tier": 3,
        "prerequisites": ["advanced_defense"],
        "cost": {"iron": 70, "stone": 15},
        "time_seconds": 900,
        "unlocks": [
            "tesla_tower",           # Trap type
            "inferno",               # Trap type
            "trap_factory",          # Building
            "firewall_defense",      # Anti-scout electronic defense
        ],
        "description": "Mastery-level trap systems including the devastating Inferno and Tesla Tower.",
        "category": "defense",
        "power_reward": 350,
    },

    "distributed_ledger": {
        "name": "🔗 Distributed Ledger",
        "tier": 3,
        "prerequisites": ["crypto_mining_101"],
        "cost": {"relics": 20, "iron": 60},
        "time_seconds": 1800,
        "unlocks": [
            "blockchain_fragment",   # Resource unlocked
            "kraken_node",           # Kraken Depths node
            "craft_bitcoin_format",  # Can craft bitcoin format item
            "satoshi_conversion",    # Can convert satoshi to bitcoin
        ],
        "description": "Unlocks blockchain fragment collection and Kraken Depths node access.",
        "category": "crypto",
        "power_reward": 400,
    },

    "crypto_security": {
        "name": "🔒 Crypto Security",
        "tier": 3,
        "prerequisites": ["crypto_mining_101", "hazard_awareness"],
        "cost": {"iron": 80, "relics": 15},
        "time_seconds": 1200,
        "unlocks": [
            "bitcoin_format",        # Protective item unlocked
            "suit_purchase_bitcoin_format", # Can buy from store
        ],
        "description": "Secures your crypto holdings against scammers and rug pulls. "
                       "Unlocks Bitcoin Format protective item.",
        "category": "crypto",
        "power_reward": 350,
    },

    "sector_jamming": {
        "name": "📡 Sector Jamming",
        "tier": 3,
        "prerequisites": ["sector_dominance", "commander_doctrine"],
        "cost": {"relics": 15, "iron": 80, "stone": 20},
        "time_seconds": 1500,
        "unlocks": [
            "volt_path_tier5",       # Sector jammer skill (Volt tree final tier)
            "jam_sector_action",     # !jam command
            "locate_jammer_action",  # !locate command (ruler counter)
        ],
        "description": "Electronic warfare capability. "
                       "Unlocks the sector jammer and anti-jam locate ability.",
        "category": "intelligence",
        "power_reward": 500,
    },

    # ──────────────────────────────────────────────────────────────────────
    # TIER 4 — Endgame Research
    # ──────────────────────────────────────────────────────────────────────

    "void_theory": {
        "name": "🌑 Void Theory",
        "tier": 4,
        "prerequisites": ["hazmat_engineering"],
        "cost": {"relics": 20, "stone": 40, "iron": 80},
        "time_seconds": 2400,
        "unlocks": [
            "void_suit",             # Void suit unlocked
            "suit_purchase_void",    # Can buy from store
            "void_sector_entry",     # Sector 9 Void Canyon entry
            "void_lattice",          # Trap type (most powerful)
        ],
        "description": "Theoretical understanding of void physics. "
                       "Unlocks the Void Suit and permits entry to Void Canyon.",
        "category": "survival",
        "power_reward": 600,
    },

    "advanced_crypto_security": {
        "name": "🔐 Advanced Crypto Security",
        "tier": 4,
        "prerequisites": ["distributed_ledger", "crypto_security"],
        "cost": {"relics": 40, "iron": 120},
        "time_seconds": 3600,
        "unlocks": [
            "cold_wallet",           # Cold Wallet protective item
            "suit_purchase_cold_wallet", # Can buy from store
            "deep_web_node",         # Deep Web node in Crypto Wastes
            "51_percent_attack_immunity", # Survive rarest crypto hazard
        ],
        "description": "Maximum crypto security. Cold Wallet and Deep Web node access. "
                       "Survives even a Market Crash.",
        "category": "crypto",
        "power_reward": 700,
    },

    "prestige_theory": {
        "name": "👑 Prestige Theory",
        "tier": 4,
        "prerequisites": ["commander_doctrine", "void_theory"],
        "cost": {"relics": 50, "stone": 80, "iron": 150},
        "time_seconds": 3600,
        "unlocks": [
            "prestige_action",       # Can prestige at level 1000
            "void_lattice",          # Trap type
            "infirmary",             # Building (recover lost troops)
            "cemetery",              # Building (morale from fallen)
        ],
        "description": "The path beyond level 1000. Unlocks prestige mechanics.",
        "category": "progression",
        "power_reward": 800,
    },

    "satoshi_converter": {
        "name": "⚡ Satoshi Converter",
        "tier": 3,
        "prerequisites": ["crypto_mining_101"],
        "cost": {"relics": 10, "iron": 40},
        "time_seconds": 600,
        "unlocks": [
            "convert_satoshi_to_bitcoin",  # !convert satoshi command
        ],
        "description": "Installs the conversion mechanism. 100,000 Satoshi = 1 BTC.",
        "category": "crypto",
        "power_reward": 200,
    },
}


# ═══════════════════════════════════════════════════════════════════════════
#  RESEARCH HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def get_research(key: str) -> Optional[dict]:
    """Get research definition by key."""
    return RESEARCH_TREE.get(key)


def is_researched(user: dict, research_key: str) -> bool:
    """Check if a player has completed a specific research."""
    return bool(user.get("researches", {}).get(research_key, False))


def is_in_progress(user: dict, research_key: str) -> bool:
    """Check if research is currently being conducted."""
    queue = user.get("research_queue", {})
    return research_key in queue


def get_prerequisites_met(user: dict, research_key: str) -> Tuple[bool, List[str]]:
    """
    Check if all prerequisites for a research are completed.
    Returns (all_met: bool, missing: list of unmet prerequisite keys)
    """
    research = RESEARCH_TREE.get(research_key)
    if not research:
        return False, [f"Unknown research: {research_key}"]

    missing = []
    for prereq in research.get("prerequisites", []):
        if not is_researched(user, prereq):
            prereq_data = RESEARCH_TREE.get(prereq, {})
            missing.append(prereq_data.get("name", prereq))

    return len(missing) == 0, missing


def can_afford_research(user: dict, research_key: str) -> Tuple[bool, str]:
    """
    Check if player can afford the research cost.
    Returns (can_afford: bool, message: str)
    """
    research = RESEARCH_TREE.get(research_key)
    if not research:
        return False, "Research not found"

    cost = research.get("cost", {})
    base_resources = user.get("base_resources", {}).get("resources", {})

    for resource, amount in cost.items():
        have = base_resources.get(resource, 0)
        if have < amount:
            return False, f"Need {amount} {resource}, have {have}"

    return True, "OK"


def start_research(user: dict, research_key: str) -> Tuple[bool, str, dict]:
    """
    Begin a research project.
    Returns (success: bool, message: str, updated_user: dict)
    """
    if is_researched(user, research_key):
        return False, f"Already researched", user

    if is_in_progress(user, research_key):
        return False, f"Research already in progress", user

    research = RESEARCH_TREE.get(research_key)
    if not research:
        return False, f"Unknown research", user

    # Check prerequisites
    prereqs_met, missing = get_prerequisites_met(user, research_key)
    if not prereqs_met:
        return False, f"Missing prerequisites: {', '.join(missing)}", user

    # Check cost
    can_afford, msg = can_afford_research(user, research_key)
    if not can_afford:
        return False, msg, user

    # Deduct cost
    cost = research.get("cost", {})
    base_res = user.get("base_resources", {})
    resources = base_res.get("resources", {})
    for resource, amount in cost.items():
        resources[resource] = resources.get(resource, 0) - amount
    base_res["resources"] = resources
    user["base_resources"] = base_res

    # Add to research queue
    if "research_queue" not in user:
        user["research_queue"] = {}

    time_seconds = research.get("time_seconds", 300)
    completion_time = (datetime.utcnow() + timedelta(seconds=time_seconds)).isoformat()

    user["research_queue"][research_key] = {
        "completion_time": completion_time,
        "started_at": datetime.utcnow().isoformat(),
        "time_seconds": time_seconds,
    }

    name = research.get("name", research_key)
    return True, f"🔬 {name} research started! Completes in {_format_time(time_seconds)}.", user


def check_and_complete_research(user: dict) -> Tuple[dict, List[str]]:
    """
    Check research queue and complete any finished research.
    Returns (updated_user, list of completed research names)
    Call this whenever user data is loaded.
    """
    queue = user.get("research_queue", {})
    if not queue:
        return user, []

    completed_names = []
    now = datetime.utcnow()
    keys_to_remove = []

    for research_key, data in queue.items():
        try:
            completion = datetime.fromisoformat(data["completion_time"])
        except Exception:
            keys_to_remove.append(research_key)
            continue

        if now >= completion:
            # Complete it
            if "researches" not in user:
                user["researches"] = {}
            user["researches"][research_key] = True

            research = RESEARCH_TREE.get(research_key, {})
            name = research.get("name", research_key)
            completed_names.append(name)

            # Award power
            power_reward = research.get("power_reward", 0)
            if power_reward:
                user["research_power"] = user.get("research_power", 0) + power_reward

            keys_to_remove.append(research_key)

    for key in keys_to_remove:
        queue.pop(key, None)

    user["research_queue"] = queue
    return user, completed_names


def get_available_research(user: dict) -> List[dict]:
    """
    Get all research the player can start right now
    (prerequisites met, not yet researched, not in progress).
    """
    available = []
    for key, research in RESEARCH_TREE.items():
        if is_researched(user, key):
            continue
        if is_in_progress(user, key):
            continue
        prereqs_met, _ = get_prerequisites_met(user, key)
        if prereqs_met:
            available.append({"key": key, **research})
    return sorted(available, key=lambda x: x["tier"])


def get_research_progress(user: dict, research_key: str) -> Optional[dict]:
    """Get progress info for a research currently in queue."""
    queue = user.get("research_queue", {})
    if research_key not in queue:
        return None

    data = queue[research_key]
    try:
        completion = datetime.fromisoformat(data["completion_time"])
        started = datetime.fromisoformat(data["started_at"])
    except Exception:
        return None

    now = datetime.utcnow()
    if now >= completion:
        return None

    total = data["time_seconds"]
    elapsed = (now - started).total_seconds()
    remaining = max(0, total - elapsed)
    pct = min(100, (elapsed / total) * 100) if total > 0 else 100

    return {
        "research_key": research_key,
        "completion_time": completion,
        "total_seconds": total,
        "elapsed_seconds": elapsed,
        "remaining_seconds": remaining,
        "progress_pct": pct,
    }


def get_unlock_source(unlock_key: str) -> Optional[str]:
    """
    Given an unlock key, return which research provides it.
    Useful for showing players what to research to get a feature.
    """
    for research_key, research in RESEARCH_TREE.items():
        if unlock_key in research.get("unlocks", []):
            return research_key
    return None


def is_feature_unlocked(user: dict, feature_key: str) -> bool:
    """
    Check if a specific feature/unlock is available to the player.
    Searches through all completed research for the unlock key.
    """
    completed = user.get("researches", {})
    for research_key in completed:
        research = RESEARCH_TREE.get(research_key, {})
        if feature_key in research.get("unlocks", []):
            return True
    return False


def get_locked_message(feature_key: str) -> str:
    """
    Returns a helpful locked message telling the player what to research.
    """
    source = get_unlock_source(feature_key)
    if source:
        research = RESEARCH_TREE[source]
        name = research.get("name", source)
        tier = research.get("tier", "?")
        return (f"🔒 *Locked* — Research *{name}* (Tier {tier}) to unlock this.\n"
                f"Use `!research {source}` to begin.")
    return "🔒 *Locked* — This feature is not yet available."


# ═══════════════════════════════════════════════════════════════════════════
#  FORMAT FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def _format_time(seconds: int) -> str:
    """Format seconds into readable time string."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    else:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h}h {m}m"


def format_research_menu(user: dict) -> str:
    """Format the full research menu grouped by tier."""
    completed = user.get("researches", {})
    in_progress = user.get("research_queue", {})

    lines = ["🔬 *RESEARCH CENTER*\n━━━━━━━━━━━━━━━━━━━━━━━━━━"]

    tier_names = {
        1: "📗 TIER 1 — STARTER",
        2: "📘 TIER 2 — MID GAME",
        3: "📙 TIER 3 — ADVANCED",
        4: "📕 TIER 4 — ENDGAME",
    }

    for tier in [1, 2, 3, 4]:
        tier_items = [(k, v) for k, v in RESEARCH_TREE.items() if v.get("tier") == tier]
        if not tier_items:
            continue

        lines.append(f"\n{tier_names[tier]}")

        for key, research in sorted(tier_items, key=lambda x: x[0]):
            name = research.get("name", key)

            if key in completed:
                status = "✅"
            elif key in in_progress:
                prog = get_research_progress(user, key)
                if prog:
                    pct = int(prog["progress_pct"])
                    remaining = _format_time(int(prog["remaining_seconds"]))
                    status = f"⏳ {pct}% ({remaining})"
                else:
                    status = "⏳"
            else:
                prereqs_met, missing = get_prerequisites_met(user, key)
                if prereqs_met:
                    cost_str = _format_cost(research.get("cost", {}))
                    time_str = _format_time(research.get("time_seconds", 0))
                    status = f"📖 Available [{cost_str} | {time_str}]"
                else:
                    status = f"🔒 Needs: {', '.join(missing[:2])}"

            lines.append(f"  {status} {name}")

    lines.append(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("Start: `!research [key]`  Info: `!research info [key]`")

    return "\n".join(lines)


def format_research_detail(research_key: str, user: dict) -> str:
    """Format detailed info for a single research entry."""
    research = RESEARCH_TREE.get(research_key)
    if not research:
        return f"❌ Research '{research_key}' not found."

    name = research.get("name", research_key)
    desc = research.get("description", "")
    cost = research.get("cost", {})
    time_s = research.get("time_seconds", 0)
    prereqs = research.get("prerequisites", [])
    unlocks = research.get("unlocks", [])
    tier = research.get("tier", "?")

    lines = [
        f"🔬 *{name}*",
        f"Tier {tier} | {_format_time(time_s)}",
        f"\n{desc}",
        f"\n*Cost:* {_format_cost(cost)}",
    ]

    if prereqs:
        prereq_names = [RESEARCH_TREE.get(p, {}).get("name", p) for p in prereqs]
        lines.append(f"*Prerequisites:* {', '.join(prereq_names)}")

    if unlocks:
        lines.append(f"*Unlocks:*")
        for u in unlocks:
            lines.append(f"  • {u.replace('_', ' ').title()}")

    # Status
    if is_researched(user, research_key):
        lines.append(f"\n✅ *Already researched*")
    elif is_in_progress(user, research_key):
        prog = get_research_progress(user, research_key)
        if prog:
            lines.append(f"\n⏳ *In progress:* {_format_time(int(prog['remaining_seconds']))} remaining")
    else:
        prereqs_met, missing = get_prerequisites_met(user, research_key)
        can_afford, afford_msg = can_afford_research(user, research_key)
        if not prereqs_met:
            lines.append(f"\n🔒 *Missing prerequisites:* {', '.join(missing)}")
        elif not can_afford:
            lines.append(f"\n❌ *Cannot afford:* {afford_msg}")
        else:
            lines.append(f"\n📖 *Ready to research* — `!research {research_key}`")

    return "\n".join(lines)


def _format_cost(cost: dict) -> str:
    """Format cost dict into readable string."""
    if not cost:
        return "Free"
    parts = []
    emoji_map = {
        "wood": "🪵", "bronze": "🧱", "iron": "⛓️",
        "stone": "🪨", "relics": "🏺", "gold": "🪙",
        "bitcoin": "₿",
    }
    for res, amt in cost.items():
        emoji = emoji_map.get(res, "📦")
        parts.append(f"{emoji}{amt}")
    return " ".join(parts)


def format_active_research(user: dict) -> str:
    """Format currently active research for dashboard display."""
    queue = user.get("research_queue", {})
    if not queue:
        return ""

    lines = ["\n🔬 *RESEARCH IN PROGRESS*\n━━━━━━━━━━━━━━━━━━"]
    for key in queue:
        prog = get_research_progress(user, key)
        if not prog:
            continue
        research = RESEARCH_TREE.get(key, {})
        name = research.get("name", key)
        pct = int(prog["progress_pct"])
        remaining = _format_time(int(prog["remaining_seconds"]))

        bar_len = 20
        filled = int(bar_len * pct / 100)
        bar = "█" * filled + "░" * (bar_len - filled)

        lines.append(f"{name}")
        lines.append(f"[{bar}] {pct}% — {remaining}")

    lines.append("━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)
