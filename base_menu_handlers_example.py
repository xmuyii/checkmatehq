"""
EXAMPLE: Sequential Base Menu Navigation with Spatial Layout
=============================================================

This shows how to integrate the base_layout.py spatial system into main.py callbacks
using sequential menu rewrites (no new messages, just edit_text() updates).

PATTERN:
- Use callback_data like "base:action_slot_id" to encode context
- Parse with parse_callback_data() to extract action and slot_id
- Edit existing message with new text + updated keyboard
- Use markup= argument to show next-level action buttons

IMPLEMENTATION WORKFLOW:
1. User clicks "⚡ Buildings" from HUD
   → Shows base_menu() with matrix + slot buttons
2. User clicks specific slot
   → Shows show_slot_details() with building info + actions
3. User clicks "Upgrade" or "Build"
   → Shows confirmation dialog with cost/time info
4. User confirms
   → Executes action, shows completion message
5. User clicks "◀️ Back"
   → Rewrites to previous menu level
"""

from aiogram import Router, F, types
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from base_layout import (
    render_base_matrix, render_buildings_directory, get_slot_by_id,
    place_building_in_slot, upgrade_building_in_slot, complete_upgrade_in_slot,
    parse_callback_data, get_empty_slots, initialize_user_base_layout,
    generate_slot_buttons, EMOJI_MAPPING
)
from build_system import BUILDING_TYPES, get_available_buildings
from supabase_db import get_user, save_user

router = Router()


# ═══════════════════════════════════════════════════════════════════════════
#  LEVEL 1: Main Base Menu (Shows Matrix + Slot Buttons)
# ═══════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "base:main")
@router.callback_query(F.data == "buildings_menu")
async def show_base_menu(callback: CallbackQuery):
    """
    Display the physical base matrix grid.
    Shows visual map + clickable slot buttons.
    """
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    
    if not user:
        await callback.answer("User not found", show_alert=True)
        return
    
    # Ensure user has a base layout
    user = initialize_user_base_layout(user)
    save_user(u_id, user)
    
    base_layout = user.get("base_layout", {})
    
    # Render the visual matrix
    matrix_display = render_base_matrix(base_layout)
    buildings_dir = render_buildings_directory(base_layout)
    
    text_hud = (
        f"*🏰 YOUR BASE MAP 🏰*\n\n"
        f"{matrix_display}\n"
        f"{buildings_dir}\n"
        f"Click a slot to view or build."
    )
    
    # Generate slot buttons (3 per row, organized by slot number)
    slot_buttons = generate_slot_buttons(base_layout, per_row=3)
    
    # Add back button
    slot_buttons.append([
        InlineKeyboardButton(text="◀️ Back", callback_data="menu_back")
    ])
    
    kb = InlineKeyboardMarkup(inline_keyboard=slot_buttons)
    
    await callback.message.edit_text(
        text=text_hud,
        parse_mode="Markdown",
        reply_markup=kb
    )
    await callback.answer()


# ═══════════════════════════════════════════════════════════════════════════
#  LEVEL 2: Slot Details (Shows Building Info + Actions)
# ═══════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("base:view_"))
async def show_slot_details(callback: CallbackQuery):
    """
    Show details for a specific slot.
    If empty: show build options
    If occupied: show upgrade/destroy options
    """
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    
    if not user:
        await callback.answer("User not found", show_alert=True)
        return
    
    # Parse callback to extract slot_id
    parsed = parse_callback_data(callback.data)
    slot_id = parsed.get("slot_id")  # e.g., "slot_3"
    
    base_layout = user.get("base_layout", {})
    slot_info = get_slot_by_id(base_layout, slot_id)
    
    if not slot_info:
        await callback.answer("Slot not found", show_alert=True)
        return
    
    # Build detail text based on slot state
    if slot_info["type"] == "empty":
        # Show available buildings to place here
        text = (
            f"*📍 {slot_id.upper().replace('_', ' ')}*\n"
            f"Status: ⬜ *Empty Plot*\n\n"
            f"This plot is ready for construction.\n"
            f"Select a building to place:\n"
        )
        
        available_buildings = get_available_buildings(user.get("level", 1))
        
        # Create buttons for each available building
        action_buttons = []
        for bid in available_buildings:
            bdata = BUILDING_TYPES.get(bid, {})
            icon = EMOJI_MAPPING.get(bid, "❓")
            name = bdata.get("name", bid)
            action_buttons.append([
                InlineKeyboardButton(
                    text=f"{icon} {name}",
                    callback_data=f"base:build_{slot_id}_{bid}"
                )
            ])
    else:
        # Occupied slot
        building_data = BUILDING_TYPES.get(slot_info["type"], {})
        building_name = building_data.get("name", slot_info["type"])
        icon = EMOJI_MAPPING.get(slot_info["type"], "❓")
        
        text = (
            f"*{icon} {building_name}*\n"
            f"Location: {slot_id.upper().replace('_', ' ')}\n"
            f"Current Level: **{slot_info['level']}**\n"
            f"Status: {slot_info['status'].upper()}\n\n"
        )
        
        if slot_info["status"] == "building":
            text += "⏳ This building is currently upgrading."
            action_buttons = []
        else:
            max_level = building_data.get("max_level", 10)
            if slot_info["level"] < max_level:
                text += f"Ready for upgrade! (Max Level: {max_level})\n"
                action_buttons = [
                    [InlineKeyboardButton(
                        text="⚡ Upgrade Building",
                        callback_data=f"base:upgrade_{slot_id}"
                    )],
                    [InlineKeyboardButton(
                        text="🗑️ Demolish",
                        callback_data=f"base:destroy_{slot_id}"
                    )],
                ]
            else:
                text += f"Maximum level {max_level} reached!"
                action_buttons = [
                    [InlineKeyboardButton(
                        text="🗑️ Demolish",
                        callback_data=f"base:destroy_{slot_id}"
                    )],
                ]
    
    # Always add back button
    action_buttons.append([
        InlineKeyboardButton(text="◀️ Back to Map", callback_data="base:main")
    ])
    
    kb = InlineKeyboardMarkup(inline_keyboard=action_buttons)
    
    await callback.message.edit_text(
        text=text,
        parse_mode="Markdown",
        reply_markup=kb
    )
    await callback.answer()


# ═══════════════════════════════════════════════════════════════════════════
#  LEVEL 3: Build Confirmation
# ═══════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("base:build_"))
async def confirm_build(callback: CallbackQuery):
    """Show build confirmation with cost and time."""
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    
    if not user:
        await callback.answer("User not found", show_alert=True)
        return
    
    # Parse: base:build_slot_3_training_grounds
    parts = callback.data.split("_")
    slot_id = f"slot_{parts[2]}"  # slot_3
    building_id = "_".join(parts[3:])  # training_grounds (handles multi-word)
    
    base_layout = user.get("base_layout", {})
    slot_info = get_slot_by_id(base_layout, slot_id)
    
    if not slot_info or slot_info["type"] != "empty":
        await callback.answer("Slot is not empty", show_alert=True)
        return
    
    building_data = BUILDING_TYPES.get(building_id, {})
    if not building_data:
        await callback.answer("Building not found", show_alert=True)
        return
    
    # Calculate costs for level 1
    from build_system import calculate_building_cost, get_build_time
    costs = calculate_building_cost(building_id, 1)
    build_time_secs = get_build_time(building_id, 1, user.get("buildings", {}))
    
    icon = EMOJI_MAPPING.get(building_id, "❓")
    name = building_data.get("name", building_id)
    
    text = (
        f"*BUILD CONFIRMATION*\n\n"
        f"{icon} **{name}** at {slot_id.upper().replace('_', ' ')}\n\n"
        f"*Resources Required:*\n"
    )
    
    for resource, amount in costs.items():
        text += f"  • {resource.capitalize()}: {amount}\n"
    
    text += f"\n*Build Time:* {build_time_secs} seconds\n\n"
    text += "Proceed with construction?"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Confirm",
                callback_data=f"base:exec_build_{slot_id}_{building_id}"
            ),
            InlineKeyboardButton(
                text="❌ Cancel",
                callback_data=f"base:view_{slot_id}"
            ),
        ]
    ])
    
    await callback.message.edit_text(
        text=text,
        parse_mode="Markdown",
        reply_markup=kb
    )
    await callback.answer()


# ═══════════════════════════════════════════════════════════════════════════
#  LEVEL 4: Execute Action (Build/Upgrade/Destroy)
# ═══════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("base:exec_build_"))
async def execute_build(callback: CallbackQuery):
    """Execute building placement in slot."""
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    
    if not user:
        await callback.answer("User not found", show_alert=True)
        return
    
    # Parse: base:exec_build_slot_3_training_grounds
    parts = callback.data.split("_")
    slot_id = f"slot_{parts[3]}"
    building_id = "_".join(parts[4:])
    
    base_layout = user.get("base_layout", {})
    
    # Place building in slot
    success, message = place_building_in_slot(base_layout, slot_id, building_id, level=1)
    
    if not success:
        await callback.answer(f"Error: {message}", show_alert=True)
        return
    
    # Save and show confirmation
    save_user(u_id, user)
    
    building_data = BUILDING_TYPES.get(building_id, {})
    icon = EMOJI_MAPPING.get(building_id, "❓")
    
    text = (
        f"✅ *CONSTRUCTION STARTED!*\n\n"
        f"{icon} **{building_data.get('name', building_id)}**\n"
        f"Location: {slot_id.upper().replace('_', ' ')}\n\n"
        f"The foundation is being laid...\n"
        f"Check back to view your growing base!"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏰 Back to Base", callback_data="base:main")]
    ])
    
    await callback.message.edit_text(
        text=text,
        parse_mode="Markdown",
        reply_markup=kb
    )
    await callback.answer("Building placed successfully!")


# ═══════════════════════════════════════════════════════════════════════════
#  IMPLEMENT IN main.py
# ═══════════════════════════════════════════════════════════════════════════

"""
To use this in main.py, add to your router registration:

    from base_menu_handlers import router as base_router
    
    dp.include_router(base_router)

Then add a button to your main HUD menu:
    [InlineKeyboardButton(text="🏗️ Base Map", callback_data="base:main")]

That's it! The sequential menu system handles all transitions smoothly.
"""
