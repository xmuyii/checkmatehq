# -*- coding: utf-8 -*-
"""
sector_nodes.py — Sector Node Definitions & Occupancy System
=============================================================
Handles all node-level logic:
  - Node definitions per sector (lore names, types, resources)
  - Exclusive occupancy (one player per node)
  - Resource accumulation (passive tick, stored as pending token)
  - Collection (manual !collect or auto-collect on departure)
  - Travel time (marching to a node takes time — not instant)
  - Predator spawns (multi-player monster on node)
  - Battle triggers (occupying a taken node starts a march conflict)

OCCUPANCY MODEL:
  - A player occupies exactly one node at a time
  - Nodes are exclusive — second player triggers march → battle
  - Roaming players (in sector, no node) are visible and attackable
  - Base plot nodes are permanent — cannot be contested normally

NODE TYPES:
  iron_mine        — Generates iron
  stone_quarry     — Generates stone
  relic_cache      — Generates relics (slower, higher value)
  ancient_vault    — Generates relics + unique drops (suit required)
  bitcoin_node     — Generates bitcoin (vault sectors only)
  crypto_mine      — Generates satoshi (Crypto Wastes sector)
  pvp_node         — Outpost — no resources, grants sector vision + dominance bonus
  base_plot        — Permanent player base location
"""

from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List
import json


from resource_registry import RESOURCES, is_unlocked, get_display_name, get_emoji

# ═══════════════════════════════════════════════════════════════════════════
#  NODE TYPE DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════

NODE_TYPES: Dict[str, dict] = {
    "iron_mine": {
        "resource": "iron",
        "base_yield_per_minute": 5,
        "capacity": 500,
        "research_required": "basic_mining",
        "description": "Extracts iron ore from the surrounding rock.",
        "emoji": "⛏️",
        "weight_per_unit": 2,
    },
    "stone_quarry": {
        "resource": "stone",
        "base_yield_per_minute": 4,
        "capacity": 400,
        "research_required": "basic_mining",
        "description": "Quarries stone from exposed cliff faces.",
        "emoji": "🪨",
        "weight_per_unit": 3,
    },
    "relic_cache": {
        "resource": "relics",
        "base_yield_per_minute": 1,
        "capacity": 50,
        "research_required": "advanced_mining",
        "description": "Slowly uncovers ancient relics buried in the sector.",
        "emoji": "🏺",
        "weight_per_unit": 5,
    },
    "ancient_vault": {
        "resource": "relics",
        "base_yield_per_minute": 3,
        "capacity": 100,
        "research_required": "hazmat_engineering",
        "requires_suit": True,
        "description": "High-yield relic extraction. Environmental protection required.",
        "emoji": "🔮",
        "weight_per_unit": 5,
        "unique_drop_chance": 0.05,  # 5% chance per minute of unique item
    },
    "bitcoin_node": {
        "resource": "bitcoin",
        "base_yield_per_minute": 0.0001,
        "capacity": 0.05,
        "research_required": "advanced_mining",
        "description": "Extremely rare. Only found in vault sectors.",
        "emoji": "₿",
        "weight_per_unit": 0,
        "sector_restricted": [60, 61, 62, 63, 64],
    },
    "crypto_mine": {
        "resource": "satoshi",
        "base_yield_per_minute": 50,
        "capacity": 5000,
        "research_required": "crypto_mining_101",
        "description": "Digital currency extraction in the Crypto Wastes.",
        "emoji": "⚡₿",
        "weight_per_unit": 0,
    },
    "pvp_node": {
        "resource": None,
        "base_yield_per_minute": 0,
        "capacity": 0,
        "research_required": "sector_dominance",
        "description": "Strategic outpost. No resources but grants sector-wide vision "
                       "and +3 dominance per minute (vs normal +1).",
        "emoji": "📡",
        "dominance_bonus_per_minute": 3,  # vs base 1 for resource nodes
        "grants_sector_vision": True,
    },
    "base_plot": {
        "resource": None,
        "base_yield_per_minute": 0,
        "capacity": 0,
        "research_required": None,
        "description": "Permanent base location. Cannot be contested through normal attacks. "
                       "Requires a Base Siege operation to capture.",
        "emoji": "🏰",
        "permanent": True,
        "immune_to_hazards": True,   # Base itself never takes hazard damage
    },
}

# ═══════════════════════════════════════════════════════════════════════════
#  SECTOR NODE DEFINITIONS
#  Each sector has unique named nodes. Lore names are fixed per sector.
#  Players learn these names and develop attachment to specific locations.
# ═══════════════════════════════════════════════════════════════════════════

SECTOR_NODES: Dict[int, dict] = {

    # ── SECTOR 1: Badlands-8 ─────────────────────────────────────────────
    1: {
        "A": {
            "name": "The Rust Flats",
            "type": "iron_mine",
            "lore": "A wide expanse of rust-red earth where iron veins run shallow.",
        },
        "B": {
            "name": "Ironbone Canyon",
            "type": "iron_mine",
            "lore": "Deep canyon walls striped with iron deposits. Wind howls through it.",
        },
        "C": {
            "name": "The Grit Shelf",
            "type": "stone_quarry",
            "lore": "A naturally exposed shelf of dense stone. Easy pickings for quarriers.",
        },
        "D": {
            "name": "Dustwall Outpost",
            "type": "pvp_node",
            "lore": "A crumbling watchtower at the sector's edge. Who holds it sees all.",
        },
        "E": {
            "name": "The Buried Cache",
            "type": "relic_cache",
            "lore": "Sand covers the ruins of an old civilization. Dig carefully.",
        },
        "F": {
            "name": "Badlands Base Alpha",
            "type": "base_plot",
            "lore": "A stable plateau with defensible edges. Room for a permanent base.",
        },
        "G": {
            "name": "Badlands Base Beta",
            "type": "base_plot",
            "lore": "A second plateau on the western edge. Less visible from the canyon.",
        },
        "H": {
            "name": "Badlands Base Gamma",
            "type": "base_plot",
            "lore": "Northern position. Harsh conditions but good sightlines.",
        },
    },

    # ── SECTOR 2: Crimson Wastes ──────────────────────────────────────────
    2: {
        "A": {
            "name": "The Red Seam",
            "type": "iron_mine",
            "lore": "Crimson-stained iron runs through this seam like blood.",
        },
        "B": {
            "name": "Ashbed Quarry",
            "type": "stone_quarry",
            "lore": "Volcanic ash has hardened into dense stone slabs here.",
        },
        "C": {
            "name": "The Ember Fields",
            "type": "iron_mine",
            "lore": "The ground smolders. Iron deposits are rich but extraction is dangerous.",
        },
        "D": {
            "name": "Crimson Watch",
            "type": "pvp_node",
            "lore": "A ridge overlooking the entire Crimson Wastes. Contested for centuries.",
        },
        "E": {
            "name": "The Scorched Vault",
            "type": "relic_cache",
            "lore": "Relics from before the great burning. Partially melted but valuable.",
        },
        "F": {
            "name": "Crimson Base Alpha",
            "type": "base_plot",
            "lore": "A heat-resistant plateau. The red dust stains everything permanently.",
        },
        "G": {
            "name": "Crimson Base Beta",
            "type": "base_plot",
            "lore": "Sheltered by a basalt ridge. Slightly cooler than the open wastes.",
        },
    },

    # ── SECTOR 3: Obsidian Peaks ──────────────────────────────────────────
    3: {
        "A": {
            "name": "The Ironjaw Tunnels",
            "type": "iron_mine",
            "lore": "Narrow tunnels carved by ancient miners. Walls teeth-like with iron shards.",
        },
        "B": {
            "name": "Ashfall Ridge",
            "type": "iron_mine",
            "lore": "Iron ore rains down with the volcanic ash here. Constant supply.",
        },
        "C": {
            "name": "The Quarry Shelf",
            "type": "stone_quarry",
            "lore": "Obsidian-laced stone. Difficult to cut but extremely dense.",
        },
        "D": {
            "name": "Cinder Vault",
            "type": "relic_cache",
            "lore": "A chamber insulated by centuries of volcanic cinder. Relics preserved inside.",
        },
        "E": {
            "name": "The Deep Crack",
            "type": "ancient_vault",
            "lore": "A fissure leading into the mountain's core. Rich in relics but lethal without protection.",
            "requires_suit": "hazmat_suit",
        },
        "F": {
            "name": "Summit Outpost",
            "type": "pvp_node",
            "lore": "The highest point in Obsidian Peaks. Whoever stands here commands the sector.",
        },
        "G": {
            "name": "Peak Base Alpha",
            "type": "base_plot",
            "lore": "A lava-cooled platform with natural stone walls. Fortifiable.",
        },
        "H": {
            "name": "Peak Base Beta",
            "type": "base_plot",
            "lore": "Hidden behind an obsidian spire. Hard to find, harder to attack.",
        },
    },

    # ── SECTOR 4: Shattered Valley ────────────────────────────────────────
    4: {
        "A": {
            "name": "The Fracture Line",
            "type": "iron_mine",
            "lore": "A crack in the earth exposing raw iron veins across a kilometer.",
        },
        "B": {
            "name": "Splinter Quarry",
            "type": "stone_quarry",
            "lore": "The valley shattered this stone into manageable fragments. Easy extraction.",
        },
        "C": {
            "name": "The Broken Hoard",
            "type": "relic_cache",
            "lore": "An ancient storehouse cracked open by seismic activity. Relics scattered everywhere.",
        },
        "D": {
            "name": "Valley Crossroads",
            "type": "pvp_node",
            "lore": "Where all paths through the valley converge. Nothing moves through without being seen.",
        },
        "E": {
            "name": "The Shard Fields",
            "type": "iron_mine",
            "lore": "Iron shards littering the valley floor. Harvestable but dangerous terrain.",
        },
        "F": {
            "name": "Valley Base Alpha",
            "type": "base_plot",
            "lore": "A stable ground pocket amid the shattered terrain.",
        },
        "G": {
            "name": "Valley Base Beta",
            "type": "base_plot",
            "lore": "Elevated position above the valley floor. Flood-proof.",
        },
    },

    # ── SECTOR 5: Frozen Abyss ────────────────────────────────────────────
    5: {
        "A": {
            "name": "The Permafrost Seam",
            "type": "iron_mine",
            "lore": "Iron locked in permafrost. Extraction requires breaking the ice first.",
        },
        "B": {
            "name": "Glacier Quarry",
            "type": "stone_quarry",
            "lore": "Ice-preserved stone. Exceptionally pure once thawed.",
        },
        "C": {
            "name": "The Frozen Archive",
            "type": "ancient_vault",
            "lore": "An entire ancient building frozen mid-collapse. Relics inside, perfectly preserved.",
            "requires_suit": "basic_suit",
        },
        "D": {
            "name": "The Ice Spire",
            "type": "pvp_node",
            "lore": "A natural ice tower with views across the entire Frozen Abyss.",
        },
        "E": {
            "name": "Coldvein Deposits",
            "type": "stone_quarry",
            "lore": "Blue-tinted stone unique to the abyss. High density.",
        },
        "F": {
            "name": "Abyss Base Alpha",
            "type": "base_plot",
            "lore": "A geothermally warmed cavity. Livable despite the surrounding freeze.",
        },
        "G": {
            "name": "Abyss Base Beta",
            "type": "base_plot",
            "lore": "Ice-walled naturally. Defensible but bitterly cold.",
        },
    },

    # ── SECTOR 6: Molten Gorge ────────────────────────────────────────────
    6: {
        "A": {
            "name": "The Magma Shelf",
            "type": "stone_quarry",
            "lore": "Cooled lava formed this dense stone shelf. Reheats during lava flow phases.",
        },
        "B": {
            "name": "Lavaborn Trenches",
            "type": "iron_mine",
            "lore": "Iron pushed to the surface by magma pressure. Extreme yield, extreme risk.",
        },
        "C": {
            "name": "The Relic Eruption",
            "type": "ancient_vault",
            "lore": "Each eruption uncovers ancient relics. The only place to access them is during lava flow — if you can survive it.",
            "requires_suit": "hazmat_suit",
        },
        "D": {
            "name": "Ember Outpost",
            "type": "pvp_node",
            "lore": "A heat-scorched watchtower. The sector ruler has always held this point.",
        },
        "E": {
            "name": "The Cooling Pools",
            "type": "relic_cache",
            "lore": "Lava cools into pools here. Relics settle at the bottom like sediment.",
        },
        "F": {
            "name": "Gorge Base Alpha",
            "type": "base_plot",
            "lore": "Built on cooled basalt. Structurally sound but surrounded by active lava channels.",
        },
    },

    # ── SECTOR 7: Twilight Marshes ────────────────────────────────────────
    7: {
        "A": {
            "name": "The Moonwood Grove",
            "type": "iron_mine",
            "lore": "Trees here grow iron-rich sap. Extraction is unlike any other sector.",
        },
        "B": {
            "name": "Mirewood Stand",
            "type": "iron_mine",
            "lore": "Dense ironwood forest. Cutting the trees yields both wood and iron.",
        },
        "C": {
            "name": "The Spirit Cache",
            "type": "relic_cache",
            "lore": "Relics drift through the fog here, almost moving on their own.",
        },
        "D": {
            "name": "Twilight Spire",
            "type": "pvp_node",
            "lore": "An ancient tower. Visibility is perfect at twilight, zero at other times.",
        },
        "E": {
            "name": "The Fog Vault",
            "type": "ancient_vault",
            "lore": "A ruin swallowed by perpetual fog. Navigation requires protection.",
            "requires_suit": "basic_suit",
        },
        "F": {
            "name": "Marsh Base Alpha",
            "type": "base_plot",
            "lore": "Built on raised ground above the waterline. The only dry land in the marshes.",
        },
        "G": {
            "name": "Marsh Base Beta",
            "type": "base_plot",
            "lore": "A floating platform anchored to the marsh floor. Unusual but defensible.",
        },
    },

    # ── SECTOR 8: Silent Forest ────────────────────────────────────────────
    8: {
        "A": {
            "name": "Ancient Bough",
            "type": "iron_mine",
            "lore": "Ironwood trees older than memory. Their cores are pure ore.",
        },
        "B": {
            "name": "The Still Quarry",
            "type": "stone_quarry",
            "lore": "No sound here. The stone comes out perfectly clean.",
        },
        "C": {
            "name": "Rootstone Deposits",
            "type": "stone_quarry",
            "lore": "Tree roots have compressed stone into an unusually dense form over centuries.",
        },
        "D": {
            "name": "The Canopy Watch",
            "type": "pvp_node",
            "lore": "A platform in the highest trees. You see the forest floor from here. Others don't see you.",
        },
        "E": {
            "name": "The Silent Vault",
            "type": "relic_cache",
            "lore": "A vault sealed by the forest itself. Open it carefully.",
        },
        "F": {
            "name": "Forest Base Alpha",
            "type": "base_plot",
            "lore": "Hidden within the dense canopy. Hard to spot from outside the tree line.",
        },
        "G": {
            "name": "Forest Base Beta",
            "type": "base_plot",
            "lore": "Ground-level clearing. Exposed but spacious.",
        },
        "H": {
            "name": "Forest Base Gamma",
            "type": "base_plot",
            "lore": "Northern edge. Borders both Sector 7 and Sector 9.",
        },
    },

    # ── SECTOR 9: Void Canyon ─────────────────────────────────────────────
    9: {
        "A": {
            "name": "The Rift Mouth",
            "type": "relic_cache",
            "lore": "Where the void tears reality open. Relics fall through from somewhere else.",
            "requires_suit": "void_suit",
        },
        "B": {
            "name": "Shattered Meridian",
            "type": "ancient_vault",
            "lore": "The meridian where reality broke. Nothing makes sense here but the relics are real.",
            "requires_suit": "void_suit",
        },
        "C": {
            "name": "The Null Point",
            "type": "pvp_node",
            "lore": "A point where void energy cancels itself. Only the brave — or the foolish — hold this.",
            "requires_suit": "void_suit",
        },
        "D": {
            "name": "Cosmic Sediment",
            "type": "bitcoin_node",
            "lore": "Digital currency condensed from cosmic energy. Theory made resource.",
            "requires_suit": "void_suit",
        },
        "E": {
            "name": "Void Base Alpha",
            "type": "base_plot",
            "lore": "The only stable ground in Void Canyon. Base structure is immune to void effects. Field troops are not.",
        },
    },

    # ── SECTOR 65: The Crypto Wastes ──────────────────────────────────────
    65: {
        "A": {
            "name": "Binance Exchange",
            "type": "crypto_mine",
            "lore": "The largest digital exchange floor in the wastes. High volume, high risk.",
        },
        "B": {
            "name": "Coinbase Vault",
            "type": "crypto_mine",
            "lore": "Regulated and slower, but the scammers hit here less often.",
        },
        "C": {
            "name": "Kraken Depths",
            "type": "crypto_mine",
            "lore": "Deep liquidity pools. Blockchain fragments form here naturally.",
            "requires_suit": "bitcoin_format",
        },
        "D": {
            "name": "The Deep Web",
            "type": "ancient_vault",
            "lore": "No one talks about what's in the Deep Web. The assets are real though.",
            "requires_suit": "cold_wallet",
        },
        "E": {
            "name": "Mempool Outpost",
            "type": "pvp_node",
            "lore": "Unconfirmed transactions pile up here. So do disputes. Contested constantly.",
        },
        "F": {
            "name": "Crypto Base Alpha",
            "type": "base_plot",
            "lore": "A cold storage facility repurposed as a base. Digital and physical security.",
        },
        "G": {
            "name": "Crypto Base Beta",
            "type": "base_plot",
            "lore": "Decentralized — no single owner recorded. That's the point.",
        },
    },
}

# Travel time in seconds between nodes within the same sector
INTRA_SECTOR_TRAVEL_SECONDS = 120   # 2 minutes to march to a node in same sector

# Travel time multiplier for cross-sector (requires teleport — this applies to march
# sent from home sector to a specific node while commander is already there)
CROSS_SECTOR_MARCH_SECONDS = 900    # 15 min base for sending reinforcements cross-sector


# ═══════════════════════════════════════════════════════════════════════════
#  NODE OCCUPANCY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def get_sector_nodes(sector_id: int) -> dict:
    """Get all node definitions for a sector."""
    return SECTOR_NODES.get(sector_id, {})


def get_node(sector_id: int, node_key: str) -> Optional[dict]:
    """Get a specific node definition."""
    sector = SECTOR_NODES.get(sector_id, {})
    node = sector.get(node_key.upper())
    if node:
        node_type = NODE_TYPES.get(node["type"], {})
        return {**node_type, **node}   # Node-specific overrides type defaults
    return None


def get_node_occupant(sector_state: dict, sector_id: int, node_key: str) -> Optional[dict]:
    """
    Get the current occupant of a node.
    sector_state: the shared sector state dict (loaded from DB/file)
    Returns dict with player info or None if vacant.
    """
    key = f"{sector_id}:{node_key.upper()}"
    return sector_state.get("occupancy", {}).get(key)


def is_node_vacant(sector_state: dict, sector_id: int, node_key: str) -> bool:
    """Check if a node is currently unoccupied."""
    return get_node_occupant(sector_state, sector_id, node_key) is None


def set_node_occupant(
    sector_state: dict,
    sector_id: int,
    node_key: str,
    player_id: str,
    player_name: str,
    troops: dict,
) -> dict:
    """
    Record a player as occupying a node.
    Updates sector_state in place and returns it.
    """
    key = f"{sector_id}:{node_key.upper()}"
    if "occupancy" not in sector_state:
        sector_state["occupancy"] = {}

    sector_state["occupancy"][key] = {
        "player_id": player_id,
        "player_name": player_name,
        "troops": troops,
        "occupied_since": datetime.utcnow().isoformat(),
        "pending_resources": 0.0,
        "last_tick": datetime.utcnow().isoformat(),
    }
    return sector_state


def clear_node_occupant(sector_state: dict, sector_id: int, node_key: str) -> dict:
    """Remove occupant from a node (player left or was ejected)."""
    key = f"{sector_id}:{node_key.upper()}"
    sector_state.get("occupancy", {}).pop(key, None)
    return sector_state


def get_player_current_node(user: dict) -> Optional[dict]:
    """
    Get the node a player is currently occupying (if any).
    Returns dict with sector_id, node_key, node_name or None.
    """
    return user.get("current_node")


def get_player_sector(user: dict) -> Optional[int]:
    """Get the sector the player's commander is currently in."""
    loc = user.get("commander_location", {})
    return loc.get("sector_id")


def get_player_home_sector(user: dict) -> Optional[int]:
    """Get the player's permanent home sector."""
    return user.get("home_sector")


# ═══════════════════════════════════════════════════════════════════════════
#  RESOURCE ACCUMULATION (NODE TICK)
# ═══════════════════════════════════════════════════════════════════════════

def tick_node_resources(
    sector_state: dict,
    sector_id: int,
    node_key: str,
    phase_multiplier: float = 1.0,
) -> Tuple[dict, float]:
    """
    Calculate resources accumulated at a node since last tick.
    Applies sector phase multiplier.
    Updates pending_resources in sector_state.
    Returns (updated_sector_state, amount_added_this_tick)
    """
    key = f"{sector_id}:{node_key.upper()}"
    occupancy = sector_state.get("occupancy", {})

    if key not in occupancy:
        return sector_state, 0.0

    occupant = occupancy[key]
    node_def = get_node(sector_id, node_key)
    if not node_def:
        return sector_state, 0.0

    node_type = node_def.get("type", "")
    type_def = NODE_TYPES.get(node_type, {})

    # Base yield per minute
    base_yield = type_def.get("base_yield_per_minute", 0)
    if base_yield == 0:
        return sector_state, 0.0   # PvP nodes and base plots don't generate

    # Time elapsed since last tick
    last_tick_str = occupant.get("last_tick")
    now = datetime.utcnow()
    if last_tick_str:
        try:
            last_tick = datetime.fromisoformat(last_tick_str)
            minutes_elapsed = (now - last_tick).total_seconds() / 60.0
        except Exception:
            minutes_elapsed = 0.0
    else:
        minutes_elapsed = 0.0

    if minutes_elapsed <= 0:
        return sector_state, 0.0

    # Calculate accumulation
    capacity = type_def.get("capacity", 999)
    pending = occupant.get("pending_resources", 0.0)

    raw_amount = base_yield * minutes_elapsed * phase_multiplier
    space_remaining = capacity - pending
    added = min(raw_amount, space_remaining)  # Cannot exceed capacity

    occupant["pending_resources"] = pending + added
    occupant["last_tick"] = now.isoformat()
    occupancy[key] = occupant
    sector_state["occupancy"] = occupancy

    return sector_state, added


def collect_node_resources(
    sector_state: dict,
    sector_id: int,
    node_key: str,
    player_id: str,
    user: dict,
) -> Tuple[dict, dict, str]:
    """
    Player collects pending resources from their node.
    Moves pending_resources from node token → player inventory.

    Returns:
        (updated_sector_state, updated_user, message)
    """
    key = f"{sector_id}:{node_key.upper()}"
    occupancy = sector_state.get("occupancy", {})

    if key not in occupancy:
        return sector_state, user, "❌ You are not occupying this node."

    occupant = occupancy[key]
    if occupant.get("player_id") != player_id:
        return sector_state, user, "❌ This node is occupied by another player."

    # First tick to get latest accumulation
    sector_state, _ = tick_node_resources(sector_state, sector_id, node_key)
    occupant = sector_state["occupancy"][key]

    pending = occupant.get("pending_resources", 0.0)
    if pending <= 0:
        return sector_state, user, "📭 Nothing to collect yet. Resources are still accumulating."

    node_def = get_node(sector_id, node_key)
    resource_key = node_def.get("resource")

    if not resource_key:
        return sector_state, user, "❌ This node type generates no resources."

    # Add to player inventory
    amount = int(pending) if not RESOURCES.get(resource_key, {}).get("decimal_allowed") else pending
    user = _add_to_inventory(user, resource_key, amount)

    # Clear pending
    occupant["pending_resources"] = 0.0
    occupancy[key] = occupant
    sector_state["occupancy"] = occupancy

    res_emoji = RESOURCES.get(resource_key, {}).get("emoji", "📦")
    res_name = get_display_name(resource_key)
    node_name = node_def.get("name", node_key)

    return sector_state, user, f"✅ Collected {res_emoji} {amount} {res_name} from {node_name}."


def auto_collect_on_departure(
    sector_state: dict,
    sector_id: int,
    node_key: str,
    player_id: str,
    user: dict,
) -> Tuple[dict, dict, dict]:
    """
    Auto-collect all pending resources when a player leaves a node.
    Always called before clearing occupancy.
    Returns (updated_sector_state, updated_user, collected_resources_dict)
    """
    key = f"{sector_id}:{node_key.upper()}"
    occupancy = sector_state.get("occupancy", {})

    if key not in occupancy:
        return sector_state, user, {}

    occupant = occupancy[key]
    if occupant.get("player_id") != player_id:
        return sector_state, user, {}

    # Tick first
    sector_state, _ = tick_node_resources(sector_state, sector_id, node_key)
    occupant = sector_state["occupancy"][key]

    pending = occupant.get("pending_resources", 0.0)
    collected = {}

    if pending > 0:
        node_def = get_node(sector_id, node_key)
        resource_key = node_def.get("resource") if node_def else None

        if resource_key:
            amount = int(pending) if not RESOURCES.get(resource_key, {}).get("decimal_allowed") else pending
            user = _add_to_inventory(user, resource_key, amount)
            collected[resource_key] = amount

    # Clear node
    sector_state = clear_node_occupant(sector_state, sector_id, node_key)
    user["current_node"] = None

    return sector_state, user, collected


def loot_abandoned_node(
    sector_state: dict,
    sector_id: int,
    node_key: str,
    attacker_id: str,
    attacker_user: dict,
) -> Tuple[dict, dict, dict]:
    """
    Attacker loots uncollected resources from a node they just won.
    Called after a successful node battle.
    Returns (updated_sector_state, updated_attacker_user, looted_resources_dict)
    """
    key = f"{sector_id}:{node_key.upper()}"
    occupancy = sector_state.get("occupancy", {})

    if key not in occupancy:
        return sector_state, attacker_user, {}

    occupant = occupancy[key]
    pending = occupant.get("pending_resources", 0.0)
    looted = {}

    if pending > 0:
        node_def = get_node(sector_id, node_key)
        resource_key = node_def.get("resource") if node_def else None

        if resource_key:
            amount = int(pending)
            attacker_user = _add_to_inventory(attacker_user, resource_key, amount)
            looted[resource_key] = amount

    return sector_state, attacker_user, looted


# ═══════════════════════════════════════════════════════════════════════════
#  MARCH QUEUE (TIMED TRAVEL TO NODES)
# ═══════════════════════════════════════════════════════════════════════════

def start_march_to_node(
    user: dict,
    sector_id: int,
    node_key: str,
    troops: dict,
    action: str = "occupy",  # "occupy" or "attack"
    speedup_minutes: int = 0,
) -> Tuple[bool, str, dict]:
    """
    Begin a timed march to a node.
    action: "occupy" (take a vacant node) or "attack" (contest an occupied node)

    Returns (success, message, updated_user)
    """
    node_def = get_node(sector_id, node_key)
    if not node_def:
        return False, "❌ Node not found.", user

    travel_seconds = INTRA_SECTOR_TRAVEL_SECONDS - (speedup_minutes * 60)
    travel_seconds = max(30, travel_seconds)  # Minimum 30 seconds even with speedups

    arrival_time = (datetime.utcnow() + timedelta(seconds=travel_seconds)).isoformat()

    march = {
        "sector_id": sector_id,
        "node_key": node_key.upper(),
        "node_name": node_def.get("name", node_key),
        "troops": troops,
        "action": action,
        "started_at": datetime.utcnow().isoformat(),
        "arrival_time": arrival_time,
        "travel_seconds": travel_seconds,
        "speedup_applied_minutes": speedup_minutes,
    }

    if "march_queue" not in user:
        user["march_queue"] = []

    user["march_queue"].append(march)

    mins = travel_seconds // 60
    secs = travel_seconds % 60
    time_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"

    node_name = node_def.get("name", node_key)
    return True, (
        f"⚔️ March started toward *{node_name}*!\n"
        f"⏱️ Arrives in: {time_str}\n"
        f"Troops: {_format_troops(troops)}"
    ), user


def get_arriving_marches(user: dict) -> List[dict]:
    """Get all marches that have completed travel time."""
    queue = user.get("march_queue", [])
    now = datetime.utcnow()
    arrived = []
    for march in queue:
        try:
            arrival = datetime.fromisoformat(march["arrival_time"])
            if now >= arrival:
                arrived.append(march)
        except Exception:
            continue
    return arrived


def remove_march(user: dict, sector_id: int, node_key: str) -> dict:
    """Remove a march from the queue after it resolves."""
    queue = user.get("march_queue", [])
    user["march_queue"] = [
        m for m in queue
        if not (m["sector_id"] == sector_id and m["node_key"] == node_key.upper())
    ]
    return user


def apply_speedup_to_march(
    user: dict,
    sector_id: int,
    node_key: str,
    speedup_minutes: int,
) -> Tuple[bool, str, dict]:
    """
    Apply a speedup item to an active march.
    Returns (success, message, updated_user)
    """
    queue = user.get("march_queue", [])
    for i, march in enumerate(queue):
        if march["sector_id"] == sector_id and march["node_key"] == node_key.upper():
            try:
                current_arrival = datetime.fromisoformat(march["arrival_time"])
                new_arrival = current_arrival - timedelta(minutes=speedup_minutes)
                now = datetime.utcnow()
                if new_arrival < now:
                    new_arrival = now + timedelta(seconds=5)  # Arrives in 5 seconds

                queue[i]["arrival_time"] = new_arrival.isoformat()
                user["march_queue"] = queue
                return True, f"⏩ March sped up by {speedup_minutes} minutes!", user
            except Exception as e:
                return False, f"❌ Speedup failed: {e}", user

    return False, "❌ No active march to that node.", user


# ═══════════════════════════════════════════════════════════════════════════
#  SECTOR MAP DISPLAY
# ═══════════════════════════════════════════════════════════════════════════

def format_sector_map(
    sector_id: int,
    sector_state: dict,
    player_id: str,
    phase_name: str = "Unknown",
    phase_time_remaining: str = "?",
    next_phase_name: str = "?",
    next_phase_warning: str = "",
) -> str:
    """
    Format the full sector map display for a player.
    Shows all nodes, occupancy, and sector status.
    """
    from sectors_system import get_sector_info
    sector_info = get_sector_info(sector_id)
    sector_name = sector_info.get("name", f"Sector {sector_id}")
    sector_emoji = sector_info.get("emoji", "🌍")

    lines = [
        f"{sector_emoji} {'═' * 45}",
        f"   SECTOR {sector_id} — {sector_name.upper()}",
        f"   📡 Phase: *{phase_name}*  [{phase_time_remaining} remaining]",
        f"{'═' * 47}",
    ]

    # Add lore flavor line if available (first two lines of sector description)
    sector_lore = sector_info.get("lore", "")
    if sector_lore:
        # Truncate to one sentence for display
        lore_short = sector_lore.split(".")[0] + "."
        lines.append(f"\n_{lore_short}_\n")

    lines.append("🗺️ *SECTOR NODES:*")

    nodes = SECTOR_NODES.get(sector_id, {})
    occupancy = sector_state.get("occupancy", {})

    for node_key in sorted(nodes.keys()):
        node = nodes[node_key]
        node_type = node.get("type", "")
        type_def = NODE_TYPES.get(node_type, {})
        node_name = node.get("name", node_key)
        node_emoji = type_def.get("emoji", "📍")

        occ_key = f"{sector_id}:{node_key}"
        occupant = occupancy.get(occ_key)

        # Suit requirement indicator
        suit_req = node.get("requires_suit", "")
        suit_indicator = " ⚠️" if suit_req else ""

        if node_type == "base_plot":
            if occupant:
                is_you = occupant["player_id"] == player_id
                marker = "🟡 YOU" if is_you else f"🔴 @{occupant['player_name']}"
                lines.append(f"  [{node_key}] 🏰 {node_name:<28} {marker} [HOME]")
            else:
                lines.append(f"  [{node_key}] 🏰 {node_name:<28} ⚪ UNCLAIMED")
        elif occupant:
            is_you = occupant["player_id"] == player_id
            if is_you:
                pending = occupant.get("pending_resources", 0)
                resource_key = type_def.get("resource", "")
                res_emoji = RESOURCES.get(resource_key, {}).get("emoji", "") if resource_key else ""
                pending_int = int(pending)
                lines.append(
                    f"  [{node_key}] {node_emoji} {node_name:<26}{suit_indicator}"
                    f"  🟡 YOU — {pending_int} {res_emoji} pending"
                )
            else:
                player_name = occupant["player_name"]
                lines.append(
                    f"  [{node_key}] {node_emoji} {node_name:<26}{suit_indicator}"
                    f"  🔴 @{player_name}"
                )
        else:
            lines.append(
                f"  [{node_key}] {node_emoji} {node_name:<26}{suit_indicator}"
                f"  ⚪ VACANT"
            )

    # Roaming players
    roaming = sector_state.get("roaming", {})
    if roaming:
        lines.append("\n👤 *ROAMING COMMANDERS:*")
        for pid, rdata in roaming.items():
            if pid == player_id:
                lines.append(f"  🔵 YOU [roaming — no node]")
            else:
                lines.append(f"  🔵 @{rdata.get('player_name', 'Unknown')} [roaming]")

    # Next phase warning
    if next_phase_warning:
        lines.append(f"\n⚠️ *NEXT PHASE: {next_phase_name}*")
        lines.append(f"   {next_phase_warning}")

    # Actions
    lines.append(f"\n{'─' * 47}")
    lines.append("Actions: `!occupy [A-H]`  `!collect`  `!map`")
    lines.append("`!attack [A-H]`  `!teleport [sector_id]`  `!base`")
    lines.append(f"{'═' * 47}")

    return "\n".join(lines)


def format_dual_dashboard(
    user: dict,
    sector_state: dict,
    home_sector_state: dict,
) -> str:
    """
    Dual dashboard: Field View (current location) + Base View (home sector).
    Shown when commander is away from home sector.
    """
    home_sector_id = get_player_home_sector(user)
    current_sector_id = get_player_sector(user)

    if home_sector_id == current_sector_id:
        # At home — single view
        return format_sector_map(current_sector_id, sector_state, user["user_id"])

    from sectors_system import get_sector_info
    home_info = get_sector_info(home_sector_id) if home_sector_id else {}
    home_name = home_info.get("name", f"Sector {home_sector_id}")
    home_emoji = home_info.get("emoji", "🏠")

    lines = ["📡 *FIELD VIEW* (current location)", "─" * 40]

    # Current location summary
    current_node = get_player_current_node(user)
    if current_node:
        node_name = current_node.get("node_name", "Unknown node")
        lines.append(f"📍 At: *{node_name}* (Sector {current_sector_id})")
    else:
        lines.append(f"📍 Roaming in Sector {current_sector_id}")

    lines.append(f"\n🏠 *BASE VIEW* — {home_emoji} {home_name}")
    lines.append("─" * 40)

    # Shield status
    shield_expires = user.get("shield_expires_at")
    if shield_expires:
        try:
            exp = datetime.fromisoformat(shield_expires)
            if datetime.utcnow() < exp:
                remaining = exp - datetime.utcnow()
                hours = int(remaining.total_seconds() // 3600)
                mins = int((remaining.total_seconds() % 3600) // 60)
                lines.append(f"🛡️ Shield: ACTIVE ({hours}h {mins}m remaining)")
            else:
                lines.append(f"🔓 Shield: *EXPIRED — BASE VULNERABLE*")
        except Exception:
            lines.append(f"🔓 Shield: UNKNOWN")
    else:
        lines.append(f"🔓 Shield: *NONE — BASE VULNERABLE*")

    # Incoming attacks on home
    incoming = home_sector_state.get("incoming_marches", {})
    home_attacks = [m for m in incoming.values()
                    if m.get("target_sector") == home_sector_id]
    if home_attacks:
        lines.append(f"\n🚨 *INCOMING ATTACKS: {len(home_attacks)}*")
        for atk in home_attacks[:3]:
            try:
                arrival = datetime.fromisoformat(atk["arrival_time"])
                remaining = arrival - datetime.utcnow()
                mins = max(0, int(remaining.total_seconds() // 60))
                lines.append(f"  ⚔️ @{atk['attacker_name']} → arrives in {mins}m")
            except Exception:
                continue

    lines.append(f"\nUse `!base` for full base view  `!map` for field map")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
#  PREDATOR SYSTEM
# ═══════════════════════════════════════════════════════════════════════════

# Predator definitions — can spawn on any node during certain sector phases
PREDATORS: Dict[str, dict] = {
    "dust_raider": {
        "name": "Dust Raider",
        "emoji": "👹",
        "hp": 200,
        "damage_per_hit": 5,
        "loot": {"iron": 30, "bronze": 20},
        "sectors": [1, 2, 4],
        "energy_cost": 50,
    },
    "lava_beast": {
        "name": "Lava Beast",
        "emoji": "🐉",
        "hp": 500,
        "damage_per_hit": 15,
        "loot": {"relics": 5, "stone": 40, "iron": 20},
        "sectors": [6],
        "energy_cost": 50,
    },
    "void_wraith": {
        "name": "Void Wraith",
        "emoji": "👻",
        "hp": 800,
        "damage_per_hit": 25,
        "loot": {"relics": 15},
        "sectors": [9],
        "energy_cost": 50,
        "requires_suit": "void_suit",
    },
    "ice_colossus": {
        "name": "Ice Colossus",
        "emoji": "🧊",
        "hp": 600,
        "damage_per_hit": 20,
        "loot": {"stone": 60, "relics": 8},
        "sectors": [5],
        "energy_cost": 50,
    },
    "forest_guardian": {
        "name": "Forest Guardian",
        "emoji": "🌿",
        "hp": 400,
        "damage_per_hit": 12,
        "loot": {"relics": 6, "wood": 50},
        "sectors": [7, 8],
        "energy_cost": 50,
    },
    "crypto_scammer": {
        "name": "Crypto Scammer",
        "emoji": "🦹",
        "hp": 500,
        "damage_per_hit": 0,    # Doesn't deal troop damage — drains resources
        "resource_drain": {"satoshi": 100},
        "loot": {"satoshi": 200, "crypto_dust": 50},
        "sectors": [65],
        "energy_cost": 50,
        "multi_player": True,   # Multiple players can hit simultaneously
    },
}


def hit_predator(
    sector_state: dict,
    sector_id: int,
    node_key: str,
    player_id: str,
    player_name: str,
    user: dict,
    damage: int = 50,
) -> Tuple[dict, dict, str]:
    """
    Player hits the predator on a node.
    Tracks damage contribution per player.
    When predator HP reaches 0, distributes loot proportionally.

    Returns (updated_sector_state, updated_user, message)
    """
    # Check energy
    if not is_unlocked(user, "energy"):
        return sector_state, user, "❌ Research Energy Systems to fight predators."

    energy = user.get("energy", 0)
    energy_cost = 50
    if energy < energy_cost:
        return sector_state, user, f"❌ Not enough energy. Need {energy_cost}, have {energy}."

    pred_key = f"predator:{sector_id}:{node_key.upper()}"
    predators = sector_state.get("active_predators", {})

    if pred_key not in predators:
        return sector_state, user, "❌ No predator at this node right now."

    pred = predators[pred_key]
    pred_def = PREDATORS.get(pred["type"], {})

    # Deduct energy
    user["energy"] = energy - energy_cost

    # Record damage
    if "damage_log" not in pred:
        pred["damage_log"] = {}
    pred["damage_log"][player_id] = pred["damage_log"].get(player_id, 0) + damage
    pred["hp"] = max(0, pred.get("hp", 0) - damage)

    pred_name = pred_def.get("name", "Predator")
    pred_emoji = pred_def.get("emoji", "👾")

    if pred["hp"] <= 0:
        # Predator defeated — distribute loot
        msg, sector_state, user = _distribute_predator_loot(
            sector_state, sector_id, node_key, pred, pred_def, player_id, user
        )
        del predators[pred_key]
        sector_state["active_predators"] = predators
        return sector_state, user, msg
    else:
        predators[pred_key] = pred
        sector_state["active_predators"] = predators
        return sector_state, user, (
            f"⚔️ Hit {pred_emoji} *{pred_name}* for {damage} damage!\n"
            f"HP remaining: {pred['hp']}/{pred_def.get('hp', '?')}\n"
            f"Your contribution: {pred['damage_log'].get(player_id, 0)} total damage"
        )


def _distribute_predator_loot(
    sector_state: dict,
    sector_id: int,
    node_key: str,
    pred: dict,
    pred_def: dict,
    collecting_player_id: str,
    collecting_user: dict,
) -> Tuple[str, dict, dict]:
    """
    Distribute predator loot proportionally by damage contribution.
    Only the triggering player's inventory is updated here.
    Other players' shares are stored in sector_state for them to claim.
    """
    damage_log = pred.get("damage_log", {})
    total_damage = sum(damage_log.values())
    if total_damage == 0:
        return "❌ No damage recorded.", sector_state, collecting_user

    base_loot = pred_def.get("loot", {})
    pred_name = pred_def.get("name", "Predator")
    pred_emoji = pred_def.get("emoji", "👾")

    # Calculate this player's share
    my_damage = damage_log.get(collecting_player_id, 0)
    my_pct = my_damage / total_damage if total_damage > 0 else 0

    my_loot = {}
    for resource, amount in base_loot.items():
        my_share = max(1, int(amount * my_pct))
        my_loot[resource] = my_share
        collecting_user = _add_to_inventory(collecting_user, resource, my_share)

    # Store other players' shares in sector state for them to claim
    if "pending_predator_loot" not in sector_state:
        sector_state["pending_predator_loot"] = {}

    for pid, pdmg in damage_log.items():
        if pid == collecting_player_id:
            continue
        ppct = pdmg / total_damage
        for resource, amount in base_loot.items():
            share = max(1, int(amount * ppct))
            if pid not in sector_state["pending_predator_loot"]:
                sector_state["pending_predator_loot"][pid] = {}
            sector_state["pending_predator_loot"][pid][resource] = (
                sector_state["pending_predator_loot"][pid].get(resource, 0) + share
            )

    loot_str = " ".join([
        f"{RESOURCES.get(r, {}).get('emoji', '📦')}{a}"
        for r, a in my_loot.items()
    ])
    contributors = len(damage_log)

    return (
        f"💀 {pred_emoji} *{pred_name}* DEFEATED!\n"
        f"{contributors} commander(s) contributed.\n"
        f"Your share ({int(my_pct * 100)}% damage): {loot_str}\n"
        f"Other participants notified of their shares."
    ), sector_state, collecting_user


# ═══════════════════════════════════════════════════════════════════════════
#  INTERNAL HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _add_to_inventory(user: dict, resource_key: str, amount) -> dict:
    """Add resources to player's stacked inventory."""
    if "inventory" not in user or not isinstance(user.get("inventory"), dict):
        user["inventory"] = {}

    res = RESOURCES.get(resource_key, {})
    inv = user["inventory"]

    if resource_key in inv:
        inv[resource_key]["qty"] = inv[resource_key].get("qty", 0) + amount
    else:
        inv[resource_key] = {
            "qty": amount,
            "display": res.get("display_name", resource_key.replace("_", " ").title()),
            "emoji": res.get("emoji", "📦"),
            "category": res.get("category", "misc"),
        }

    user["inventory"] = inv
    return user


def _format_troops(troops: dict) -> str:
    """Format troop dict for display."""
    if not troops:
        return "No troops"
    parts = [f"{count} {unit}" for unit, count in troops.items() if count > 0]
    return ", ".join(parts) if parts else "No troops"


def get_node_status_summary(sector_id: int, sector_state: dict) -> dict:
    """
    Get summary of all node occupancy for a sector.
    Used by the PvP outpost holder to see full sector intel.
    """
    nodes = SECTOR_NODES.get(sector_id, {})
    occupancy = sector_state.get("occupancy", {})
    summary = {}

    for node_key, node in nodes.items():
        occ_key = f"{sector_id}:{node_key}"
        occupant = occupancy.get(occ_key)
        node_type_def = NODE_TYPES.get(node["type"], {})
        summary[node_key] = {
            "name": node["name"],
            "type": node["type"],
            "emoji": node_type_def.get("emoji", "📍"),
            "occupied": occupant is not None,
            "occupant_name": occupant["player_name"] if occupant else None,
            "pending_resources": occupant.get("pending_resources", 0) if occupant else 0,
            "resource_type": node_type_def.get("resource"),
        }

    return summary
