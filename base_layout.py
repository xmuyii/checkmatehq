"""
base_layout.py — Spatial Base Grid System
==========================================
Anchors buildings to specific coordinates/slots on a player's base map.
Provides visual matrix rendering and sequential menu navigation.
"""

from typing import Dict, Optional, Tuple

# ═══════════════════════════════════════════════════════════════════════════
#  GRID CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

GRID_ROWS = 4
GRID_COLS = 5

TOTAL_SLOTS = GRID_ROWS * GRID_COLS  # 12 slots

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
    "empty": "⬜",
    "building": "🚧",  # Under construction
}

# ═══════════════════════════════════════════════════════════════════════════
#  DEFAULT BASE LAYOUT
# ═══════════════════════════════════════════════════════════════════════════

def get_default_base_layout() -> Dict[str, dict]:
    """
    Return the default base layout grid.
    Each slot is keyed by "slot_N" and contains coordinate, type, level, and status.
    Coordinates are (row, col) from top-left (0,0) to bottom-right.
    """
    return {
        "slot_1": {"coord": (0, 0), "type": "base_hq", "level": 1, "status": "idle"},
        "slot_2": {"coord": (0, 1), "type": "empty", "level": 0, "status": "empty"},
        "slot_3": {"coord": (0, 2), "type": "empty", "level": 0, "status": "empty"},
        "slot_4": {"coord": (0, 3), "type": "empty", "level": 0, "status": "empty"},
        "slot_5": {"coord": (0, 4), "type": "empty", "level": 0, "status": "empty"},
        "slot_6": {"coord": (1, 0), "type": "empty", "level": 0, "status": "empty"},
        "slot_7": {"coord": (1, 1), "type": "empty", "level": 0, "status": "empty"},
        "slot_8": {"coord": (1, 2), "type": "empty", "level": 0, "status": "empty"},
        "slot_9": {"coord": (1, 3), "type": "empty", "level": 0, "status": "empty"},
        "slot_10": {"coord": (1, 4), "type": "empty", "level": 0, "status": "empty"},
        "slot_11": {"coord": (2, 0), "type": "empty", "level": 0, "status": "empty"},
        "slot_12": {"coord": (2, 1), "type": "empty", "level": 0, "status": "empty"},
        "slot_13": {"coord": (2, 2), "type": "empty", "level": 0, "status": "empty"},
        "slot_14": {"coord": (2, 3), "type": "empty", "level": 0, "status": "empty"},
        "slot_15": {"coord": (2, 4), "type": "empty", "level": 0, "status": "empty"},
        "slot_16": {"coord": (3, 0), "type": "empty", "level": 0, "status": "empty"},
        "slot_17": {"coord": (3, 1), "type": "empty", "level": 0, "status": "empty"},
        "slot_18": {"coord": (3, 2), "type": "empty", "level": 0, "status": "empty"},
        "slot_19": {"coord": (3, 3), "type": "empty", "level": 0, "status": "empty"},
        "slot_20": {"coord": (3, 4), "type": "empty", "level": 0, "status": "empty"}
    }


def initialize_user_base_layout(user: dict) -> dict:
    """Initialize base layout if user doesn't have one."""
    if "base_layout" not in user:
        user["base_layout"] = get_default_base_layout()
    return user


# ═══════════════════════════════════════════════════════════════════════════
#  MATRIX RENDERING
# ═══════════════════════════════════════════════════════════════════════════

def render_base_matrix(base_layout: dict) -> str:
    """
    Render the base layout as a visual text grid for Telegram display.
    Returns a formatted string showing the matrix.
    """
    # Initialize grid filled with empty emojis
    grid = [[EMOJI_MAPPING["empty"] for _ in range(GRID_COLS)] for _ in range(GRID_ROWS)]
    
    # Place building emojis at their coordinates
    for slot_id, slot_info in base_layout.items():
        row, col = slot_info["coord"]
        building_type = slot_info["type"]
        
        # Show construction icon if building
        if slot_info["status"] == "building":
            icon = EMOJI_MAPPING["building"]
        else:
            icon = EMOJI_MAPPING.get(building_type, EMOJI_MAPPING["empty"])
        
        grid[row][col] = icon
    
    # Format into a visual box
    hud = "╔════════════════════════════════════╗\n"
    hud += "║       🏰 *MY BASE MAP* 🏰          ║\n"
    hud += "║                                    ║\n"
    
    for row_idx, row_cells in enumerate(grid, start=1):
        hud += f"║  Row {row_idx}:  "
        for cell in row_cells:
            hud += f"[ {cell} ]  "
        hud += "║\n"
    
    hud += "║                                    ║\n"
    hud += "╚════════════════════════════════════╝\n"
    
    return hud


def render_buildings_directory(base_layout: dict) -> str:
    """Render a text directory listing all slots with their contents."""
    from build_system import BUILDING_TYPES
    
    msg = "📋 *BUILDINGS DIRECTORY:*\n"
    msg += "────────────────────────\n"
    
    for slot_id, info in sorted(base_layout.items()):
        slot_num = slot_id.split("_")[1]
        
        if info["type"] == "empty":
            msg += f"Slot {slot_num.rjust(2)}: ⬜ *Empty Plot*\n"
        else:
            building_data = BUILDING_TYPES.get(info["type"], {})
            building_name = building_data.get("name", info["type"].replace("_", " ").title())
            icon = EMOJI_MAPPING.get(info["type"], "❓")
            
            if info["status"] == "building":
                msg += f"Slot {slot_num.rjust(2)}: {icon} {building_name} 🚧 *UPGRADING*\n"
            else:
                msg += f"Slot {slot_num.rjust(2)}: {icon} {building_name} Lv.{info['level']}\n"
    
    return msg


# ═══════════════════════════════════════════════════════════════════════════
#  SLOT OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════

def get_slot_by_id(base_layout: dict, slot_id: str) -> Optional[dict]:
    """Get a single slot's data."""
    return base_layout.get(slot_id)


def get_empty_slots(base_layout: dict) -> list:
    """Return list of all empty slot IDs."""
    return [
        slot_id for slot_id, info in base_layout.items()
        if info["type"] == "empty"
    ]


def get_building_slot(base_layout: dict, building_type: str) -> Optional[str]:
    """Find if a building type exists on the map, return its slot_id or None."""
    for slot_id, info in base_layout.items():
        if info["type"] == building_type and info["type"] != "empty":
            return slot_id
    return None


def place_building_in_slot(
    base_layout: dict, slot_id: str, building_type: str, level: int = 1
) -> Tuple[bool, str]:
    """
    Place a building in an empty slot.
    Returns (success, message).
    """
    if slot_id not in base_layout:
        return False, f"Slot {slot_id} does not exist."
    
    slot_info = base_layout[slot_id]
    
    if slot_info["type"] != "empty":
        return False, f"Slot {slot_id} is already occupied."
    
    base_layout[slot_id] = {
        "coord": slot_info["coord"],
        "type": building_type,
        "level": level,
        "status": "idle",
    }
    
    return True, f"Building {building_type} placed in {slot_id}."


def upgrade_building_in_slot(base_layout: dict, slot_id: str) -> Tuple[bool, str]:
    """Increment a building's level (marks as building status)."""
    if slot_id not in base_layout:
        return False, f"Slot {slot_id} does not exist."
    
    slot_info = base_layout[slot_id]
    
    if slot_info["type"] == "empty":
        return False, f"Slot {slot_id} is empty."
    
    slot_info["status"] = "building"
    return True, f"Slot {slot_id} now upgrading."


def complete_upgrade_in_slot(base_layout: dict, slot_id: str) -> Tuple[bool, str]:
    """Complete an upgrade by incrementing level and marking idle."""
    if slot_id not in base_layout:
        return False, f"Slot {slot_id} does not exist."
    
    slot_info = base_layout[slot_id]
    
    if slot_info["type"] == "empty":
        return False, f"Slot {slot_id} is empty."
    
    slot_info["level"] += 1
    slot_info["status"] = "idle"
    return True, f"Upgrade complete! {slot_id} is now level {slot_info['level']}."


def destroy_building_in_slot(base_layout: dict, slot_id: str) -> Tuple[bool, str]:
    """Remove a building and mark slot as empty."""
    if slot_id not in base_layout:
        return False, f"Slot {slot_id} does not exist."
    
    slot_info = base_layout[slot_id]
    building_name = slot_info["type"]
    
    base_layout[slot_id] = {
        "coord": slot_info["coord"],
        "type": "empty",
        "level": 0,
        "status": "empty",
    }
    
    return True, f"{building_name} demolished. Slot {slot_id} is now empty."


# ═══════════════════════════════════════════════════════════════════════════
#  MENU NAVIGATION HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def parse_callback_data(callback_data: str) -> dict:
    """
    Parse structured callback_data strings like 'base:view_slot_3' or 'base:build_slot_3'.
    Returns dict with keys: action, context, slot_id (if applicable).
    """
    parts = callback_data.split(":")
    
    if len(parts) < 2:
        return {"action": callback_data, "context": None, "slot_id": None}
    
    context = parts[0]  # e.g., "base"
    action_and_slot = parts[1]  # e.g., "view_slot_3"
    
    if "_" in action_and_slot:
        action, slot_id = action_and_slot.rsplit("_", 1)  # rsplit to handle "slot_3"
        return {"action": action, "context": context, "slot_id": f"slot_{slot_id}"}
    else:
        return {"action": action_and_slot, "context": context, "slot_id": None}


def generate_slot_buttons(base_layout: dict, per_row: int = 3) -> list:
    """
    Generate inline keyboard buttons for all slots.
    Returns list of button rows.
    """
    from aiogram.types import InlineKeyboardButton
    
    buttons = []
    row = []
    
    for slot_id in sorted(base_layout.keys(), key=lambda x: int(x.split("_")[1])):
        slot_num = slot_id.split("_")[1]
        button = InlineKeyboardButton(
            text=f"Slot {slot_num}",
            callback_data=f"base:view_{slot_id}"
        )
        row.append(button)
        
        if len(row) == per_row:
            buttons.append(row)
            row = []
    
    # Add remaining buttons to a partial row
    if row:
        buttons.append(row)
    
    return buttons
