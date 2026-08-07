import math
import logging
from datetime import datetime, timedelta, timezone

from aiogram import Router, F, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.keyboard import InlineKeyboardBuilder

import sector_nodes as sn
from wiring_hooks import on_user_action
from supabase_db import get_user, save_user, get_sector_state, save_sector_state, supabase
# ── ROUTER DEFINITION ────────────────────────────────────────────────────────
router = Router()

TELEPORT_ITEM_ID = "teleport_scroll"
GRID_SIZE = 8  # 8x8 Grid representing 64 Sectors


# ── GRID DISTANCE UTILITIES ──────────────────────────────────────────────────
def sector_to_coords(sector_id: int) -> tuple[int, int]:
    """Maps sector_id (1 to 64) to (x, y) grid coordinates. Sector 1 is (0,0)."""
    idx = max(1, min(64, sector_id)) - 1
    x = idx % GRID_SIZE
    y = idx // GRID_SIZE
    return x, y


def calculate_distance(from_sector: int, to_sector: int) -> float:
    """Calculates Euclidean distance between two sector coordinates."""
    x1, y1 = sector_to_coords(from_sector)
    x2, y2 = sector_to_coords(to_sector)
    return math.hypot(x2 - x1, y2 - y1)


def calculate_travel_time(from_sector: int, to_sector: int, speed_per_unit: int = 45) -> int:
    """Calculates travel time in seconds. Default 45s per distance unit (min 15s)."""
    if from_sector == to_sector:
        return 0
    dist = calculate_distance(from_sector, to_sector)
    return max(15, int(dist * speed_per_unit))


# ── 1. SECTOR MAP & NAVIGATION HANDLER ──────────────────────────────────────
@router.callback_query(F.data.startswith("sec_map:"))
async def cb_sector_map(callback: types.CallbackQuery):
    """Displays the interactive grid of nodes for a given sector."""
    await callback.answer()

    try:
        u_id = str(callback.from_user.id)
        on_user_action(u_id, supabase)

        user = get_user(u_id)
        if not user:
            await callback.answer("User record not found.", show_alert=True)
            return

        # Parse target sector ID
        _, sector_id_str = callback.data.split(":")
        sector_id = int(sector_id_str)

        # Fetch sector state safely from DB
        sector_state = get_sector_state(sector_id) or {}

        builder = InlineKeyboardBuilder()

        # Support both int and string dictionary keys in SECTOR_NODES
        nodes = sn.SECTOR_NODES.get(sector_id) or sn.SECTOR_NODES.get(str(sector_id)) or {}
        occupancy = sector_state.get("occupancy", {})

        # Build node grid (3 per row)
        for node_key, node in sorted(nodes.items()):
            node_type = sn.NODE_TYPES.get(node.get("type"), {})
            emoji = node_type.get("emoji", "📍")

            occ_key = f"{sector_id}:{node_key}"
            occupant = occupancy.get(occ_key)

            if occupant:
                status = "🟡" if str(occupant.get("player_id")) == u_id else "🔴"
            else:
                status = "⚪"

            btn_text = f"{node_key}: {status}"
            builder.button(text=btn_text, callback_data=f"node_inspect:{sector_id}:{node_key}")

        builder.adjust(3)

        # Navigation row (capped between 1 and 64)
        prev_sec = max(1, sector_id - 1)
        next_sec = min(64, sector_id + 1)

        builder.row(
            types.InlineKeyboardButton(text="⬅️ Prev Sector", callback_data=f"sec_map:{prev_sec}"),
            types.InlineKeyboardButton(text="🔄 Refresh", callback_data=f"sec_map:{sector_id}"),
            types.InlineKeyboardButton(text="Next Sector ➡️", callback_data=f"sec_map:{next_sec}")
            [
                       
                    ],  
        )
        builder.row(
            types.InlineKeyboardButton(text="[ 🕯 Sector 1 ]", callback_data="menu_fusion_info"),
            types.InlineKeyboardButton(text="[ 🪬 Sector 2 ]", callback_data="menu_trivia_info"),
            types.InlineKeyboardButton(text="⬅️ Main Menu", callback_data="menu_back"))

        caption = sn.format_sector_map(
            sector_id=sector_id,
            sector_state=sector_state,
            player_id=u_id
        )

        await callback.message.edit_text(
            text=caption,
            parse_mode="Markdown",
            reply_markup=builder.as_markup()
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise e
    except Exception as e:
        logging.error(f"Error executing cb_sector_map: {e}", exc_info=True)


# ── 2. NODE INSPECTION & CROSS-SECTOR MOVEMENT HANDLER ────────────────────────
from private_sector import (
    get_private_sector, 
    is_resident, 
    format_private_sector_map, 
    format_outsider_view,
    kb_private_sector_resident,
    kb_private_sector_outsider
)
 
@router.callback_query(F.data.startswith("node_inspect:"))
async def cb_node_inspect(callback: types.CallbackQuery):
    """Inspects a node & handles Private Sector hub vs Standard Nodes."""
    await callback.answer()

    try:
        u_id = str(callback.from_user.id)
        on_user_action(u_id, supabase)

        user = get_user(u_id)
        if not user:
            await callback.answer("User record not found.", show_alert=True)
            return

        _, target_sector_str, node_key = callback.data.split(":")
        target_sector = int(target_sector_str)
        commander_sector = user.get("commander_location", 1)

        # 🏰 --- PRIVATE SECTOR NODE INTERACTION ---
        if node_key == "G":  # Node G is reserved for Private Sector hubs
            sector_state = get_sector_state(target_sector) or {}
            private_sector = get_private_sector(sector_state)

            if is_resident(private_sector, u_id):
                text = format_private_sector_map(private_sector, viewer_id=u_id)
                kb = kb_private_sector_resident(target_sector, u_id, private_sector)
            else:
                text = format_outsider_view(private_sector)
                kb = kb_private_sector_outsider(target_sector, private_sector)

            await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
            return
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        # Check if already in transit
        in_transit_until = user.get("travel_arrival")
        if in_transit_until:
            arrival_dt = datetime.fromisoformat(in_transit_until)
            now = datetime.now(timezone.utc)
            if now < arrival_dt:
                remaining = int((arrival_dt - now).total_seconds())
                await callback.answer(f"⏳ Commander is already traveling! {remaining}s remaining.", show_alert=True)
                return

        # ── SAFE INVENTORY EXTRACTION (Handles list OR dict) ──
        inventory_data = user.get("inventory", {})
        if isinstance(inventory_data, dict):
            teleport_scrolls = inventory_data.get(TELEPORT_ITEM_ID, 0)
        elif isinstance(inventory_data, list):
            teleport_scrolls = sum(
                1 for item in inventory_data 
                if (isinstance(item, dict) and item.get("id") == TELEPORT_ITEM_ID) or item == TELEPORT_ITEM_ID
            )
        else:
            teleport_scrolls = 0

        builder = InlineKeyboardBuilder()

        # Target is in a different sector -> Offer March / Teleport
        if commander_sector != target_sector:
            travel_seconds = calculate_travel_time(commander_sector, target_sector)
            dist = round(calculate_distance(commander_sector, target_sector), 1)

            caption = (
                f"🌐 *CROSS-SECTOR MOVEMENT* 🌐\n\n"
                f"📍 **Current Location:** Sector {commander_sector}\n"
                f"🎯 **Target Destination:** Sector {target_sector} (Node `{node_key}`)\n"
                f"📏 **Distance:** `{dist} Units`\n\n"
                f"How would you like to move your Commander?\n"
                f"• 🚶 **Normal March:** Takes `{travel_seconds} seconds`\n"
                f"• ⚡ **Instant Teleport:** Costs `1x Teleport Scroll` (Owned: {teleport_scrolls})"
            )

            builder.button(
                text=f"🚶 March ({travel_seconds}s)",
                callback_data=f"move_start:march:{target_sector}:{node_key}"
            )
            builder.button(
                text=f"⚡ Instant Teleport ({teleport_scrolls} Left)",
                callback_data=f"move_start:teleport:{target_sector}:{node_key}"
            )
            builder.button(text="⬅️ Back to Map", callback_data=f"sec_map:{target_sector}")
            builder.adjust(1)

        # Commander is already in sector -> Standard Actions
        else:
            sector_state = get_sector_state(target_sector) or {}
            node_def = sn.get_node(target_sector, node_key) if hasattr(sn, 'get_node') else {}
            occupancy = sector_state.get("occupancy", {})
            occupant = occupancy.get(f"{target_sector}:{node_key}")

            is_me = occupant and str(occupant.get("player_id")) == u_id
            is_vacant = occupant is None

            if is_me:
                builder.button(text="📥 Collect Yield", callback_data=f"node_act:collect:{target_sector}:{node_key}")
                builder.button(text="🚪 Abandon Node", callback_data=f"node_act:leave:{target_sector}:{node_key}")
            elif is_vacant:
                builder.button(text="⚔️ March & Occupy", callback_data=f"node_act:occupy:{target_sector}:{node_key}")
            else:
                builder.button(text="🔥 March & Attack", callback_data=f"node_act:attack:{target_sector}:{node_key}")

            builder.button(text="⬅️ Back to Map", callback_data=f"sec_map:{target_sector}")
            builder.adjust(1)

            desc = node_def.get('description', 'No details available.').replace('_', ' ').replace('*', '')

            caption = (
                f"📍 *NODE {node_key}* (Sector {target_sector})\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"**Type:** {node_def.get('type', 'Standard')}\n"
                f"*{desc}*\n\n"
                f"**Status:** {'🟡 Occupied by you' if is_me else ('⚪ Vacant' if is_vacant else '🔴 Enemy Occupied')}\n"
                f"━━━━━━━━━━━━━━━━━"
            )

        await callback.message.edit_text(caption, parse_mode="Markdown", reply_markup=builder.as_markup())
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise e
    except Exception as e:
        logging.error(f"Error executing cb_node_inspect: {e}", exc_info=True)
# ── 3. EXECUTE MOVEMENT (MARCH VS TELEPORT) HANDLER ──────────────────────────
@router.callback_query(F.data.startswith("move_start:"))
async def cb_move_start(callback: types.CallbackQuery):
    """Executes the chosen movement mode (instant teleport vs timed march)."""
    await callback.answer()

    try:
        u_id = str(callback.from_user.id)
        on_user_action(u_id, supabase)

        user = get_user(u_id)
        _, mode, target_sector_str, node_key = callback.data.split(":")
        target_sector = int(target_sector_str)
        commander_sector = user.get("sector", 1)

        # MODE A: INSTANT TELEPORT
        if mode == "teleport":
            inventory = user.get("inventory", {})
            scrolls = inventory.get(TELEPORT_ITEM_ID, 0)

            if scrolls < 1:
                await callback.answer("❌ You don't have any Teleport Scrolls!", show_alert=True)
                return

            inventory[TELEPORT_ITEM_ID] -= 1
            user["inventory"] = inventory
            user["sector"] = target_sector
            save_user(u_id, user)

            await callback.answer("⚡ Teleported instantly!", show_alert=True)
            await cb_node_inspect(callback)

        # MODE B: NORMAL MARCH
        elif mode == "march":
            travel_seconds = calculate_travel_time(commander_sector, target_sector)
            arrival_time = datetime.now(timezone.utc) + timedelta(seconds=travel_seconds)

            user["travel_arrival"] = arrival_time.isoformat()
            user["travel_target_sector"] = target_sector
            save_user(u_id, user)

            # Record march in target sector's state
            sector_state = get_sector_state(target_sector) or {}
            incoming = sector_state.get("incoming_marches", {})
            incoming[u_id] = {
                "type": "relocate",
                "from_sector": commander_sector,
                "target_node": node_key,
                "eta": arrival_time.isoformat()
            }
            sector_state["incoming_marches"] = incoming
            save_sector_state(target_sector, sector_state)

            builder = InlineKeyboardBuilder()
            builder.button(text="🔄 Check March Status", callback_data=f"node_inspect:{target_sector}:{node_key}")
            builder.button(text="🗺️ View Map", callback_data=f"sec_map:{target_sector}")
            builder.adjust(1)

            await callback.message.edit_text(
                f"🚶 *COMMANDER ON THE MARCH* 🚶\n\n"
                f"Your commander has left **Sector {commander_sector}** marching towards **Sector {target_sector}**.\n\n"
                f"⏱️ **Arrival Time:** `{travel_seconds} seconds`\n"
                f"📍 Target Node: `{node_key}`",
                parse_mode="Markdown",
                reply_markup=builder.as_markup()
            )
    except Exception as e:
        logging.error(f"Error executing cb_move_start: {e}", exc_info=True)