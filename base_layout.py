"""
base_layout.py — Tactical Compass-Based Defense Grid System
===========================================================
Transforms base layout into a strategic 3×3 compass-mapped grid with visual roads.
Attacker must breach perimeter sectors to reach deep valuables.
Roads (═, ║, ╬) show physical connectivity for pathfinding during raids.
"""

from typing import Dict, Optional, Tuple, List

# ═══════════════════════════════════════════════════════════════════════════
#  COMPASS GRID CONFIGURATION & INFRASTRUCTURE
# ═══════════════════════════════════════════════════════════════════════════

# 3×3 Tactical grid with fixed road infrastructure connecting 9 directional sectors
COMPASS_GEOMETRY = [
    [" NW ", "═══", "  N ", "═══", " NE "],
    [" ║  ", "   ", " ║  ", "   ", " ║  "],
    ["  W ", "═══", "  C  ", "═══", "  E  "],
    [" ║  ", "   ", " ║  ", "   ", " ║  "],
    [" SW ", "═══", "  S  ", "═══", " SE "]
]

# All valid compass sector coordinates
COMPASS_SECTORS = ["NW", "N", "NE", "W", "C", "E", "SW", "S", "SE"]

# Adjacency graph: Which sectors protect/block access to each other
COMPASS_NETWORK = {
    "NW": ["N", "W", "C"],        # NW is only entry point accessible from N, W, or through C
    "N":  ["NW", "NE", "C"],      # North road connects NW, NE, and Center
    "NE": ["N", "E", "C"],        # NE vault protected by North and East roads
    "W":  ["NW", "C", "SW"],      # West road connects NW, SW, and Center
    "C":  ["N", "S", "E", "W"],   # Center core connects all cardinal directions
    "E":  ["NE", "C", "SE"],      # East road connects NE, SE, and Center
    "SW": ["W", "S", "C"],        # SW is only entry point from W, S, or through C
    "S":  ["SW", "SE", "C"],      # South road (MAIN ENTRY) connects SW, SE, and Center
    "SE": ["S", "E", "C"]         # SE connects South and East roads
}

# Sector threat importance (for defense prioritization)
SECTOR_THREAT_LEVEL = {
    "S":  5,   # Main entrance - highest threat
    "N":  4,   # Secondary entrance
    "W":  3,   # Flanking route
    "E":  3,   # Flanking route
    "C":  5,   # Core - highest value target
    "NW": 2,   # Corner sector
    "NE": 2,   # Corner sector
    "SW": 2,   # Corner sector
    "SE": 2    # Corner sector
}

# Emoji map for building types (matches BUILDING_TYPES keys from build_system.py)
EMOJI_MAPPING = {
    "base_hq": "🏰",
    "training_grounds": "⚔️",
    "cemetery": "⚰️",
    "barracks": "🏕️",
    "armory": "🛡️",
    "war_room": "🗺️",
    "infirmary": "🏥",
    "storage": "🏦",
    "mine": "⛏️",
    "farm": "🌾",
    "trap_factory": "🔩",
    "walls": "🧱",
    "gatehouse": "🚪",
    "shield_gen": "🛡️",
    "empty": "⬜",
    "building": "🚧",  # Under construction
}

# ═══════════════════════════════════════════════════════════════════════════
#  DEFAULT BASE LAYOUT
# ═══════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════
#  DEFAULT BASE LAYOUT
# ═══════════════════════════════════════════════════════════════════════════

def get_default_base_layout() -> Dict[str, dict]:
    """
    Return the default compass-based base layout.
    Each sector is keyed by compass direction (NW, N, NE, etc.)
    Contains building type, level, HP (structural integrity), and construction status.
    
    Sector arrangement creates natural defensibility:
    - S (South) is the main entrance/weakest point
    - C (Center) is the HQ and core value
    - Corners are remote but valuable for strategic placement
    """
    return {
        # Perimeter Sectors (Front Line Defense)
        "S":  {"type": "gatehouse", "level": 1, "hp": 3000, "max_hp": 3000, "status": "idle"},
        "N":  {"type": "empty",     "level": 0, "hp": 0,    "max_hp": 0,    "status": "empty"},
        "E":  {"type": "empty",     "level": 0, "hp": 0,    "max_hp": 0,    "status": "empty"},
        "W":  {"type": "empty",     "level": 0, "hp": 0,    "max_hp": 0,    "status": "empty"},
        
        # Corner Sectors (Strategic Placement)
        "NW": {"type": "empty",     "level": 0, "hp": 0,    "max_hp": 0,    "status": "empty", "shelter": True},
        "NE": {"type": "empty",     "level": 0, "hp": 0,    "max_hp": 0,    "status": "empty"},
        "SW": {"type": "empty",     "level": 0, "hp": 0,    "max_hp": 0,    "status": "empty"},
        "SE": {"type": "empty",     "level": 0, "hp": 0,    "max_hp": 0,    "status": "empty"},
        
        # Center (Core Value - The HQ)
        "C":  {"type": "base_hq",   "level": 1, "hp": 10000, "max_hp": 10000, "status": "idle"},
    }




def initialize_user_base_layout(user: dict) -> dict:
    """Initialize compass-based layout if user doesn't have one. Ensures all 9 sectors exist."""
    if "base_layout" not in user or not user["base_layout"]:
        user["base_layout"] = get_default_base_layout()
    else:
        # Ensure all 9 sectors exist (fill in missing sectors from default)
        default = get_default_base_layout()
        for sector in COMPASS_SECTORS:
            if sector not in user["base_layout"]:
                user["base_layout"][sector] = default[sector]
    return user


# ═══════════════════════════════════════════════════════════════════════════
#  MATRIX RENDERING
# ═══════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════
#  TACTICAL MAP RENDERING
# ═══════════════════════════════════════════════════════════════════════════

def render_tactical_map(base_layout: dict) -> str:
    """
    Render the base as a simple, readable 3x3 plot board.
    Shows an explicit role label per sector (HQ, Front Gate, Outpost) and
    indicates if a sector is marked as an alliance shelter/safe spot.
    """
    from build_system import BUILDING_TYPES

    ROLE_MAP = {
        "C": "HQ Core",
        "S": "Front Gate",
        "N": "North Approach",
        "E": "East Flank",
        "W": "West Flank",
        "NW": "Outpost NW",
        "NE": "Outpost NE",
        "SW": "Outpost SW",
        "SE": "Outpost SE",
    }

    def get_sector_display(sector_key: str) -> str:
        sector_data = base_layout.get(sector_key, {})
        building_type = sector_data.get("type", "empty")

        # Resolve name for building or empty
        if building_type == "empty":
            building_name = "Empty Plot"
        else:
            building_name = BUILDING_TYPES.get(building_type, {}).get("name", building_type.replace("_", " ").title())

        # Icon decision
        if sector_data.get("status") == "building":
            icon = EMOJI_MAPPING["building"]
        else:
            icon = EMOJI_MAPPING.get(building_type, EMOJI_MAPPING["empty"])

        # Role label (HQ, Gate, etc.)
        role = ROLE_MAP.get(sector_key, sector_key)

        # Shelter / alliance-safe indicator
        shelter = " 🏠 Shelter" if sector_data.get("shelter") or sector_data.get("alliance_safe") or sector_data.get("safe_spot") else ""

        # Compose small multi-piece label for the HUD
        return f"{icon}{sector_key} {role}{shelter}\n  {building_name}"

    hud = "```\n"
    hud += "  🏰 TACTICAL BASE PLOT\n\n"
    hud += "      NW                N                NE\n"
    hud += f"    {get_sector_display('NW'):20} {get_sector_display('N'):20} {get_sector_display('NE'):20}\n"
    hud += "   ──────────────────────────────────────────────\n"
    hud += f"    {get_sector_display('W'):20} {get_sector_display('C'):20} {get_sector_display('E'):20}\n"
    hud += "   ──────────────────────────────────────────────\n"
    hud += f"    {get_sector_display('SW'):20} {get_sector_display('S'):20} {get_sector_display('SE'):20}\n"
    hud += "```"

    return hud


def render_scouting_intel(base_layout: dict) -> str:
    """Render detailed intel report for scouts - shows HP and threat levels."""
    from build_system import BUILDING_TYPES
    
    msg = "📋 *SECTOR INTELLIGENCE REPORT:*\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    
    for sector in ["S", "N", "E", "W", "C", "NW", "NE", "SW", "SE"]:
        info = base_layout.get(sector, {})
        building_type = info.get("type", "empty")
        
        if building_type == "empty":
            threat = "⚠️" if sector in ["S", "C"] else "⚡"
            msg += f"**{sector}**: ⬜ *Empty* {threat}\n"
        else:
            building_data = BUILDING_TYPES.get(building_type, {})
            building_name = building_data.get("name", building_type.replace("_", " ").title())
            icon = EMOJI_MAPPING.get(building_type, "❓")
            hp = info.get("hp", 0)
            level = info.get("level", 0)
            
            if info.get("status") == "building":
                msg += f"**{sector}**: {icon} {building_name} Lv.{level} 🚧 HP: {hp:,}\n"
            else:
                threat_emoji = "🔴" if SECTOR_THREAT_LEVEL.get(sector, 0) >= 4 else "🟡" if SECTOR_THREAT_LEVEL.get(sector, 0) >= 3 else "🟢"
                msg += f"**{sector}**: {building_name} Lv.{level} {threat_emoji} HP: {hp:,}\n"
    
    return msg


# ═══════════════════════════════════════════════════════════════════════════
#  SECTOR OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════

def get_sector_by_id(base_layout: dict, sector: str) -> Optional[dict]:
    """Get a single sector's data."""
    return base_layout.get(sector)


def get_empty_sectors(base_layout: dict) -> List[str]:
    """Return list of all empty sector IDs."""
    return [
        sector for sector, info in base_layout.items()
        if info.get("type") == "empty"
    ]


def get_building_sector(base_layout: dict, building_type: str) -> Optional[str]:
    """Find if a building type exists on the map, return its sector or None."""
    for sector, info in base_layout.items():
        if info.get("type") == building_type and building_type != "empty":
            return sector
    return None


def place_building_in_sector(
    base_layout: dict, sector: str, building_type: str, level: int = 1
) -> Tuple[bool, str]:
    """
    Place a building in an empty sector.
    Returns (success, message).
    """
    if sector not in COMPASS_SECTORS:
        return False, f"Sector {sector} does not exist."
    
    sector_info = base_layout.get(sector, {})
    
    if sector_info.get("type") != "empty":
        return False, f"Sector {sector} is already occupied by {sector_info.get('type')}."
    
    # Calculate max HP based on building type and level
    from build_system import BUILDING_TYPES
    building_data = BUILDING_TYPES.get(building_type, {})
    
    # Base HP calculation: level * 500 + building modifier
    base_hp = 1000 + (level * 500)
    if building_type in ["walls", "gatehouse"]:
        base_hp = 2000 + (level * 800)  # Defensive structures have more HP
    elif building_type == "base_hq":
        base_hp = 10000
    
    base_layout[sector] = {
        "type": building_type,
        "level": level,
        "hp": base_hp,
        "max_hp": base_hp,
        "status": "idle",
    }
    
    return True, f"Building {building_type} placed in {sector} sector."


def upgrade_building_in_sector(base_layout: dict, sector: str) -> Tuple[bool, str]:
    """Mark a building as upgrading (under construction)."""
    if sector not in COMPASS_SECTORS:
        return False, f"Sector {sector} does not exist."
    
    sector_info = base_layout.get(sector, {})
    
    if sector_info.get("type") == "empty":
        return False, f"Sector {sector} is empty."
    
    sector_info["status"] = "building"
    return True, f"Sector {sector} now upgrading."


def complete_upgrade_in_sector(base_layout: dict, sector: str) -> Tuple[bool, str]:
    """Complete an upgrade by incrementing level and marking idle."""
    if sector not in COMPASS_SECTORS:
        return False, f"Sector {sector} does not exist."
    
    sector_info = base_layout.get(sector, {})
    
    if sector_info.get("type") == "empty":
        return False, f"Sector {sector} is empty."
    
    sector_info["level"] += 1
    sector_info["status"] = "idle"
    
    # Increase HP with each upgrade
    old_hp = sector_info.get("max_hp", 1000)
    new_hp = old_hp + (old_hp * 0.25)  # +25% per level
    sector_info["max_hp"] = int(new_hp)
    sector_info["hp"] = int(new_hp)
    
    return True, f"Upgrade complete! {sector} is now level {sector_info['level']}."


def damage_sector(base_layout: dict, sector: str, damage: int) -> Tuple[bool, str, bool]:
    """
    Damage a sector building. Returns (success, message, destroyed).
    destroyed=True if building is fully destroyed.
    """
    if sector not in COMPASS_SECTORS:
        return False, f"Sector {sector} does not exist.", False
    
    sector_info = base_layout.get(sector, {})
    
    if sector_info.get("type") == "empty":
        return False, f"Sector {sector} is empty.", False
    
    old_hp = sector_info.get("hp", 0)
    new_hp = max(0, old_hp - damage)
    sector_info["hp"] = new_hp
    
    destroyed = new_hp <= 0
    
    if destroyed:
        building_name = sector_info.get("type")
        sector_info["type"] = "empty"
        sector_info["level"] = 0
        sector_info["hp"] = 0
        sector_info["max_hp"] = 0
        sector_info["status"] = "empty"
        return True, f"⚔️ {building_name} in {sector} sector DESTROYED!", True
    else:
        return True, f"💥 {sector} sector damaged. HP: {new_hp:,}/{sector_info.get('max_hp'):,}", False


def destroy_building_in_sector(base_layout: dict, sector: str) -> Tuple[bool, str]:
    """Remove a building and mark sector as empty."""
    if sector not in COMPASS_SECTORS:
        return False, f"Sector {sector} does not exist."
    
    sector_info = base_layout.get(sector, {})
    building_name = sector_info.get("type", "empty")
    
    if building_name == "empty":
        return False, f"Sector {sector} is already empty."
    
    base_layout[sector] = {
        "type": "empty",
        "level": 0,
        "hp": 0,
        "max_hp": 0,
        "status": "empty",
    }
    
    return True, f"{building_name} demolished. Sector {sector} is now empty."


# ═══════════════════════════════════════════════════════════════════════════
#  MENU NAVIGATION HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def parse_callback_data(callback_data: str) -> dict:
    """
    Parse structured callback_data strings like 'base:view_NE' or 'base:attack_NE'.
    Returns dict with keys: action, context, sector (if applicable).
    """
    parts = callback_data.split(":")
    
    if len(parts) < 2:
        return {"action": callback_data, "context": None, "sector": None}
    
    context = parts[0]  # e.g., "base"
    action_and_sector = parts[1]  # e.g., "view_NE"
    
    if "_" in action_and_sector:
        action, sector = action_and_sector.rsplit("_", 1)
        return {"action": action, "context": context, "sector": sector}
    else:
        return {"action": action_and_sector, "context": context, "sector": None}


def generate_sector_buttons(base_layout: dict) -> list:
    """
    Generate inline keyboard buttons for all compass sectors in a 3×3 grid layout.
    Returns list of button rows arranged as:
    [NW] [N] [NE]
    [W]  [C] [E]
    [SW] [S] [SE]
    """
    from aiogram.types import InlineKeyboardButton
    
    # Sector arrangement matches the compass grid
    rows = [
        ["NW", "N", "NE"],
        ["W", "C", "E"],
        ["SW", "S", "SE"]
    ]
    
    buttons = []
    for row_sectors in rows:
        button_row = []
        for sector in row_sectors:
            sector_data = base_layout.get(sector, {})
            building_type = sector_data.get("type", "empty")
            
            # Show a threat indicator for occupied sectors
            threat_icon = "🔴" if building_type != "empty" else "⚪"
            
            button = InlineKeyboardButton(
                text=f"{sector} {threat_icon}",
                callback_data=f"base:view_{sector}"
            )
            button_row.append(button)
        
        buttons.append(button_row)
    
    return buttons


def get_sector_status_brief(base_layout: dict, sector: str) -> str:
    """Get a single-line status for a sector."""
    info = base_layout.get(sector, {})
    building_type = info.get("type", "empty")
    
    if building_type == "empty":
        return f"{sector}: ⬜ Empty"
    else:
        level = info.get("level", 0)
        hp = info.get("hp", 0)
        max_hp = info.get("max_hp", 1)
        status = "🚧" if info.get("status") == "building" else "✅"
        return f"{sector}: {EMOJI_MAPPING.get(building_type, '❓')} {building_type.title()} Lv.{level} {status} ({hp}/{max_hp} HP)"
