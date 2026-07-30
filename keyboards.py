# keyboards.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from sector_nodes import SECTOR_NODES, NODE_TYPES

def build_sector_map_keyboard(sector_id: int, sector_state: dict, player_id: str) -> InlineKeyboardMarkup:
    """
    Generates a grid of inline buttons for each node in a sector.
    """
    nodes = SECTOR_NODES.get(sector_id, {})
    occupancy = sector_state.get("occupancy", {})
    keyboard = []
    row = []

    for node_key, node in sorted(nodes.items()):
        node_type = NODE_TYPES.get(node["type"], {})
        emoji = node_type.get("emoji", "📍")
        
        # Check occupancy status
        occ_key = f"{sector_id}:{node_key}"
        occupant = occupancy.get(occ_key)
        
        status_symbol = "⚪"  # Vacant
        if occupant:
            status_symbol = "🟡" if str(occupant.get("player_id")) == str(player_id) else "🔴"

        # Button label e.g., "A: ⛏️ 🟡"
        button_text = f"{node_key}: {emoji} {status_symbol}"
        callback_data = f"node_view:{sector_id}:{node_key}"
        
        row.append(InlineKeyboardButton(button_text, callback_data=callback_data))
        
        # 3 buttons per row
        if len(row) == 3:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    # Action Row at the Bottom
    keyboard.append([
        InlineKeyboardButton("🔄 Refresh Map", callback_data=f"sec_refresh:{sector_id}"),
        InlineKeyboardButton("📥 Collect All", callback_data=f"sec_collect_all:{sector_id}")
    ])
    
    return InlineKeyboardMarkup(keyboard)


def build_node_action_keyboard(sector_id: int, node_key: str, is_occupied_by_me: bool, is_vacant: bool) -> InlineKeyboardMarkup:
    """
    Generates contextual action buttons when a player taps a specific node.
    """
    keyboard = []
    
    if is_occupied_by_me:
        keyboard.append([InlineKeyboardButton("📥 Collect Resources", callback_data=f"node_collect:{sector_id}:{node_key}")])
        keyboard.append([InlineKeyboardButton("🚪 Leave Node", callback_data=f"node_leave:{sector_id}:{node_key}")])
    elif is_vacant:
        keyboard.append([InlineKeyboardButton("⚔️ March & Occupy", callback_data=f"node_occupy:{sector_id}:{node_key}")])
    else: # Occupied by enemy
        keyboard.append([InlineKeyboardButton("🔥 March & Attack", callback_data=f"node_attack:{sector_id}:{node_key}")])

    keyboard.append([InlineKeyboardButton("⬅️ Back to Map", callback_data=f"sec_map:{sector_id}")])
    
    return InlineKeyboardMarkup(keyboard)