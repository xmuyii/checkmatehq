"""
TACTICAL BASE DEFENSE SYSTEM - Handler Examples
================================================

This shows how to integrate the compass-based tactical defense system into main.py.
Uses sequential menu rewrites (edit_text, no new messages) for smooth UX.

PATTERN:
- Callback format: "base:action_SECTOR" (e.g., "base:view_NE", "base:attack_S")
- Parse with parse_callback_data() to extract action and sector
- Edit existing message with tactical display + updated keyboard
- Sectors are: NW, N, NE, W, C, E, SW, S, SE (3×3 compass grid)

MENU HIERARCHY:
1. User clicks "🏰 Defend Base" 
   → show_tactical_map() displays grid with road infrastructure
2. User clicks a sector (e.g., "NE 🔴")
   → show_sector_details() shows building info and action options
3. User clicks "Build", "Upgrade", or "Attack"
   → Shows confirmation with costs/paths/damage calculations
4. User confirms
   → Executes action, updates base_layout, shows result
5. User clicks "◀️ Back"
   → Rewrites to previous menu level (no extra messages)
"""

from aiogram import Router, F, types
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from base_layout import (
    render_tactical_map, render_scouting_intel, get_sector_by_id,
    place_building_in_sector, upgrade_building_in_sector, complete_upgrade_in_sector,
    parse_callback_data, initialize_user_base_layout,
    generate_sector_buttons, COMPASS_SECTORS, EMOJI_MAPPING, SECTOR_THREAT_LEVEL
)
from build_system import BUILDING_TYPES, get_available_buildings, calculate_building_cost, get_build_time
from supabase_db import get_user, save_user

router = Router()


# ═══════════════════════════════════════════════════════════════════════════
#  LEVEL 1: Main Tactical Map Display
# ═══════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "base:main")
@router.callback_query(F.data == "defend_base")
async def show_tactical_map(callback: CallbackQuery):
    """
    Display the 3×3 compass grid with visual roads and sector status.
    Shows clickable buttons arranged in 3×3 formation.
    """
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    
    if not user:
        await callback.answer("User not found", show_alert=True)
        return
    
    # Ensure user has tactical base layout
    user = initialize_user_base_layout(user)
    save_user(u_id, user)
    
    base_layout = user.get("base_layout", {})
    
    # Render the tactical map with roads
    map_display = render_tactical_map(base_layout)
    intel_display = render_scouting_intel(base_layout)
    
    text_hud = (
        f"*🏰 YOUR TACTICAL BASE 🏰*\n\n"
        f"{map_display}\n"
        f"{intel_display}\n\n"
        f"Click a sector to view or defend."
    )
    
    # Generate 3×3 grid of sector buttons
    sector_buttons = generate_sector_buttons(base_layout)
    sector_buttons.append([
        InlineKeyboardButton(text="◀️ Back", callback_data="menu_back")
    ])
    
    kb = InlineKeyboardMarkup(inline_keyboard=sector_buttons)
    
    await callback.message.edit_text(
        text=text_hud,
        parse_mode="Markdown",
        reply_markup=kb
    )
    await callback.answer()


# ═══════════════════════════════════════════════════════════════════════════
#  LEVEL 2: Sector Details (View Building / Place / Upgrade / Attack)
# ═══════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("base:view_"))
async def show_sector_details(callback: CallbackQuery):
    """
    Show details for a specific compass sector.
    If empty: show build options
    If occupied: show upgrade/attack options
    """
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    
    if not user:
        await callback.answer("User not found", show_alert=True)
        return
    
    # Parse callback to extract sector (e.g., "NE" from "base:view_NE")
    parsed = parse_callback_data(callback.data)
    sector = parsed.get("sector")
    
    if not sector or sector not in COMPASS_SECTORS:
        await callback.answer("Invalid sector", show_alert=True)
        return
    
    # Ensure user has all 9 sectors initialized
    user = initialize_user_base_layout(user)
    save_user(u_id, user)
    
    base_layout = user.get("base_layout", {})
    sector_info = get_sector_by_id(base_layout, sector)
    
    if not sector_info:
        await callback.answer("Sector not found", show_alert=True)
        return
    
    # Build detail text based on sector state
    threat_level = SECTOR_THREAT_LEVEL.get(sector, 0)
    threat_emoji = "🔴" if threat_level >= 4 else "🟠" if threat_level >= 3 else "🟡" if threat_level >= 2 else "🟢"
    
    if sector_info["type"] == "empty":
        # Empty sector - show build options
        text = (
            f"*📍 {sector.upper()} SECTOR*\n"
            f"Status: ⬜ *Empty Plot*\n"
            f"Threat Level: {threat_emoji} ({threat_level}/5)\n\n"
            f"This sector is ready for construction.\n"
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
                    callback_data=f"base:build_{sector}_{bid}"
                )
            ])
    else:
        # Occupied sector - show status and actions
        building_data = BUILDING_TYPES.get(sector_info["type"], {})
        building_name = building_data.get("name", sector_info["type"])
        icon = EMOJI_MAPPING.get(sector_info["type"], "❓")
        
        hp = sector_info.get("hp", 0)
        max_hp = sector_info.get("max_hp", 1)
        level = sector_info.get("level", 0)
        status = sector_info.get("status", "idle")
        hp_pct = (hp / max_hp * 100) if max_hp > 0 else 0
        
        text = (
            f"*{icon} {building_name}*\n"
            f"Location: {sector.upper()} sector\n"
            f"Level: **{level}** | HP: **{hp:,}/{max_hp:,}** ({hp_pct:.0f}%)\n"
            f"Status: {status.upper()}\n"
            f"Threat Level: {threat_emoji} ({threat_level}/5)\n\n"
        )
        
        action_buttons = []
        
        if status == "building":
            text += "⏳ This building is currently upgrading."
        else:
            max_level = building_data.get("max_level", 10)
            if level < max_level:
                text += f"Ready for upgrade! (Max Level: {max_level})\n\n"
                action_buttons = [
                    [InlineKeyboardButton(
                        text="⚡ Upgrade Building",
                        callback_data=f"base:upgrade_{sector}"
                    )],
                ]
            else:
                text += f"Maximum level {max_level} reached!"
                action_buttons = []
            
            if sector != "C":  # Can't demolish HQ
                action_buttons.append([
                    InlineKeyboardButton(
                        text="🗑️ Demolish",
                        callback_data=f"base:destroy_{sector}"
                    )
                ])
    
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
    
    # Ensure user has all 9 sectors initialized
    user = initialize_user_base_layout(user)
    save_user(u_id, user)
    
    # Parse: base:build_NE_training_grounds
    parts = callback.data.split("_")
    sector = parts[2]  # NE
    building_id = "_".join(parts[3:])  # training_grounds
    
    base_layout = user.get("base_layout", {})
    sector_info = get_sector_by_id(base_layout, sector)
    
    if not sector_info or sector_info["type"] != "empty":
        await callback.answer("Sector is not empty", show_alert=True)
        return
    
    building_data = BUILDING_TYPES.get(building_id, {})
    if not building_data:
        await callback.answer("Building not found", show_alert=True)
        return
    
    # Calculate costs for level 1
    costs = calculate_building_cost(building_id, 1)
    build_time_secs = get_build_time(building_id, 1, user.get("buildings", {}))
    
    icon = EMOJI_MAPPING.get(building_id, "❓")
    name = building_data.get("name", building_id)
    
    text = (
        f"*BUILD CONFIRMATION*\n\n"
        f"{icon} **{name}** at {sector} sector\n\n"
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
                callback_data=f"base:exec_build_{sector}_{building_id}"
            ),
            InlineKeyboardButton(
                text="❌ Cancel",
                callback_data=f"base:view_{sector}"
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
#  LEVEL 4: Execute Build
# ═══════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("base:exec_build_"))
async def execute_build(callback: CallbackQuery):
    """Execute building placement in sector."""
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    
    if not user:
        await callback.answer("User not found", show_alert=True)
        return
    
    # Ensure user has all 9 sectors initialized
    user = initialize_user_base_layout(user)
    
    # Parse: base:exec_build_NE_training_grounds
    parts = callback.data.split("_")
    sector = parts[3]
    building_id = "_".join(parts[4:])
    
    base_layout = user.get("base_layout", {})
    
    # Place building in sector
    success, message = place_building_in_sector(base_layout, sector, building_id, level=1)
    
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
        f"Location: {sector} sector\n\n"
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
#  UPGRADE BUILDING
# ═══════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("base:upgrade_"))
async def confirm_upgrade(callback: CallbackQuery):
    """Show upgrade confirmation."""
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    sector = parse_callback_data(callback.data).get("sector")
    
    if not user or not sector:
        await callback.answer("Error loading data", show_alert=True)
        return
    
    # Ensure user has all 9 sectors initialized
    user = initialize_user_base_layout(user)
    save_user(u_id, user)
    
    base_layout = user.get("base_layout", {})
    sector_info = get_sector_by_id(base_layout, sector)
    
    if not sector_info or sector_info["type"] == "empty":
        await callback.answer("Sector is empty", show_alert=True)
        return
    
    building_id = sector_info["type"]
    current_level = sector_info.get("level", 1)
    next_level = current_level + 1
    
    building_data = BUILDING_TYPES.get(building_id, {})
    costs = calculate_building_cost(building_id, next_level)
    build_time_secs = get_build_time(building_id, next_level, user.get("buildings", {}))
    
    icon = EMOJI_MAPPING.get(building_id, "❓")
    name = building_data.get("name", building_id)
    
    text = (
        f"*UPGRADE CONFIRMATION*\n\n"
        f"{icon} **{name}** ({sector})\n"
        f"Upgrade: Level {current_level} → **{next_level}**\n\n"
        f"*Resources Required:*\n"
    )
    
    for resource, amount in costs.items():
        text += f"  • {resource.capitalize()}: {amount}\n"
    
    text += f"\n*Build Time:* {build_time_secs} seconds\n\n"
    text += "Proceed?"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Confirm",
                callback_data=f"base:exec_upgrade_{sector}"
            ),
            InlineKeyboardButton(
                text="❌ Cancel",
                callback_data=f"base:view_{sector}"
            ),
        ]
    ])
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("base:exec_upgrade_"))
async def execute_upgrade(callback: CallbackQuery):
    """Execute upgrade."""
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    sector = parse_callback_data(callback.data).get("sector")
    
    # Ensure user has all 9 sectors initialized
    user = initialize_user_base_layout(user)
    
    base_layout = user.get("base_layout", {})
    success, message = upgrade_building_in_sector(base_layout, sector)
    
    if not success:
        await callback.answer(f"Error: {message}", show_alert=True)
        return
    
    save_user(u_id, user)
    
    text = f"✅ *UPGRADE STARTED!*\n\n{message}\n\nBack to base map"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏰 Back to Base", callback_data="base:main")]
    ])
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
    await callback.answer("Upgrade queued!")


# ═══════════════════════════════════════════════════════════════════════════
#  DEMOLISH BUILDING
# ═══════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("base:destroy_"))
async def confirm_destroy(callback: CallbackQuery):
    """Confirm demolition."""
    u_id = str(callback.from_user.id)
    sector = parse_callback_data(callback.data).get("sector")
    
    user = get_user(u_id)
    
    # Ensure user has all 9 sectors initialized
    user = initialize_user_base_layout(user)
    save_user(u_id, user)
    
    base_layout = user.get("base_layout", {})
    sector_info = get_sector_by_id(base_layout, sector)
    
    icon = EMOJI_MAPPING.get(sector_info["type"], "❓")
    name = sector_info["type"].replace("_", " ").title()
    
    text = (
        f"*DEMOLITION CONFIRMATION*\n\n"
        f"{icon} **{name}** in {sector} sector\n\n"
        f"⚠️ This cannot be undone!\n"
        f"Are you sure?"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Yes, Demolish", callback_data=f"base:exec_destroy_{sector}"),
            InlineKeyboardButton(text="❌ Cancel", callback_data=f"base:view_{sector}"),
        ]
    ])
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("base:exec_destroy_"))
async def execute_destroy(callback: CallbackQuery):
    """Execute demolition."""
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    sector = parse_callback_data(callback.data).get("sector")
    
    base_layout = user.get("base_layout", {})
    from base_layout import destroy_building_in_sector
    success, message = destroy_building_in_sector(base_layout, sector)
    
    if not success:
        await callback.answer(message, show_alert=True)
        return
    
    save_user(u_id, user)
    
    text = f"✅ {message}\n\nSector {sector} is now empty."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏰 Back to Base", callback_data="base:main")]
    ])
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
    await callback.answer("Building demolished!")


# ═══════════════════════════════════════════════════════════════════════════
#  IMPLEMENTATION NOTES
# ═══════════════════════════════════════════════════════════════════════════

"""
To use this in main.py, add:

    from tactical_base_handlers import router as base_router
    
    dp.include_router(base_router)

Then add button to main HUD menu:
    [InlineKeyboardButton(text="🏰 Defend Base", callback_data="base:main")]

The sequential menu system handles all transitions automatically with edit_text().
No message spam - just smooth menu rewrites!
"""
