# -*- coding: utf-8 -*-
"""
tactical_handlers.py — Phase 1-4 Inline Keyboard Callback Handlers
====================================================================
All callback_query handlers for the new game systems.
Registered as a Router that gets included in main.py's Dispatcher.

HOW TO ADD TO main.py:
  from tactical_handlers import tactical_router
  dp.include_router(tactical_router)

  # Add this line alongside your existing dp.include_router() calls.
  # Place it BEFORE dp.start_polling(bot).

CALLBACK DATA FORMAT:
  "system:action:param1:param2"
  Examples:
    "sector:map:3"
    "node:occupy:3:A"
    "skills:unlock:volt:2"
    "teleport:go:6"
    "research:start:basic_mining"
    "war:room"
    "bounty:board"

TEXT COMMANDS (secondary — players discover these with experience):
  !map, !collect, !teleport, !research, !skills, !war, !bounty
  These are registered at the bottom as @dp.message handlers
  but keyboards are always the primary interaction method.
"""

import asyncio
from datetime import datetime
from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

tactical_router = Router()

# ── Lazy imports (avoid circular imports at module level) ─────────────────
def _db():
    from supabase_db import get_user, save_user, supabase, DB_TABLE, normalize_user
    return get_user, save_user, supabase, DB_TABLE, normalize_user


def _sector_state(sector_id: int):
    """Load sector state from DB."""
    from supabase_db import supabase, DB_TABLE, safe_json
    try:
        r = supabase.table("sector_state").select("*").eq(
            "sector_id", sector_id
        ).execute()
        if r.data:
            state = dict(r.data[0])
            for f in ["occupancy", "roaming", "dominance", "active_predators",
                      "warnings_sent", "pending_notifications"]:
                state[f] = safe_json(state.get(f), default={})
            for f in ["sector_chat", "event_log", "pending_ruler_alerts"]:
                state[f] = safe_json(state.get(f), default=[])
            return state
    except Exception as e:
        print(f"[SECTOR_STATE] load error {sector_id}: {e}")
    return {
        "sector_id": sector_id, "occupancy": {}, "roaming": {},
        "sector_chat": [], "event_log": [], "dominance": {},
        "active_predators": {}, "warnings_sent": {},
    }


def _save_sector_state(sector_id: int, state: dict):
    from supabase_db import supabase
    try:
        state["last_updated"] = datetime.utcnow().isoformat()
        supabase.table("sector_state").upsert(
            {"sector_id": sector_id, **state}
        ).execute()
    except Exception as e:
        print(f"[SECTOR_STATE] save error {sector_id}: {e}")


def _get_alliance(user: dict) -> dict:
    alliance_id = user.get("alliance_id")
    if not alliance_id:
        return {}
    try:
        import json, os
        with open("alliances.json", "r") as f:
            alliances = json.load(f)
        return alliances.get(alliance_id, {})
    except Exception:
        return {}


def _log_event(sector_id: int, state: dict, message: str, **kwargs) -> dict:
    from sector_report import log_sector_event
    return log_sector_event(state, sector_id, message, **kwargs)


# ═══════════════════════════════════════════════════════════════════════════
#  SECTOR CALLBACKS
# ═══════════════════════════════════════════════════════════════════════════

@tactical_router.callback_query(F.data.startswith("sector:"))
async def handle_sector(cb: types.CallbackQuery):
    get_user, save_user, supabase, DB_TABLE, normalize_user = _db()
    u_id = str(cb.from_user.id)
    user = get_user(u_id)
    if not user:
        await cb.answer("Please /start first.", show_alert=True)
        return

    parts  = cb.data.split(":")
    action = parts[1] if len(parts) > 1 else ""
    param  = parts[2] if len(parts) > 2 else ""

    # ── sector:dashboard:3 ────────────────────────────────────────────────
    if action == "dashboard":
        sid          = int(param) if param.isdigit() else user.get("commander_location", {}).get("sector_id", 1)
        sector_state = _sector_state(sid)
        alliance     = _get_alliance(user)

        from sector_report import format_sector_dashboard
        from sector_dominance import kb_sector_dashboard

        text = format_sector_dashboard(sid, sector_state, user, alliance)
        kb   = kb_sector_dashboard(sid, user, sector_state)

        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    # ── sector:map:3 ──────────────────────────────────────────────────────
    elif action == "map":
        sid          = int(param) if param.isdigit() else 1
        sector_state = _sector_state(sid)

        from sector_nodes import format_sector_map
        from sector_cycles import get_current_phase
        from sector_dominance import kb_occupy_node_menu

        phase     = get_current_phase(sid)
        phase_name = phase.get("name", "?")
        remain    = phase.get("time_remaining_str", "?")
        next_ph   = phase.get("next_phase", {})

        text = format_sector_map(
            sid, sector_state, u_id,
            phase_name=phase_name,
            phase_time_remaining=remain,
            next_phase_name=next_ph.get("name", "?"),
            next_phase_warning=next_ph.get("warning_msg", ""),
        )
        kb = kb_occupy_node_menu(sid, sector_state, user)
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    # ── sector:phase:3 ────────────────────────────────────────────────────
    elif action == "phase":
        sid = int(param) if param.isdigit() else 1
        from sector_cycles import format_phase_status, format_full_cycle_view
        from sector_dominance import kb_phase_info
        text = format_phase_status(sid) + "\n\n" + format_full_cycle_view(sid)
        kb   = kb_phase_info(sid)
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    # ── sector:chat:3 ─────────────────────────────────────────────────────
    elif action == "chat":
        sid          = int(param) if param.isdigit() else 1
        sector_state = _sector_state(sid)
        from teleport_system import read_sector_chat
        text = read_sector_chat(sector_state, u_id, user, limit=15)
        kb   = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("« Back to Sector", callback_data=f"sector:dashboard:{sid}")],
        ])
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    # ── sector:cycle_view:3 ───────────────────────────────────────────────
    elif action == "cycle_view":
        sid  = int(param) if param.isdigit() else 1
        from sector_cycles import format_full_cycle_view
        text = format_full_cycle_view(sid)
        kb   = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("« Back", callback_data=f"sector:phase:{sid}")],
        ])
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    # ── sector:dominance:3 ────────────────────────────────────────────────
    elif action == "dominance":
        sid          = int(param) if param.isdigit() else 1
        sector_state = _sector_state(sid)
        from sector_dominance import format_sector_dominance_board
        text = format_sector_dominance_board(sid, sector_state)
        kb   = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("⚔️ Challenge Ruler", callback_data=f"dominance:pretender:{sid}")],
            [InlineKeyboardButton("« Back",            callback_data=f"sector:dashboard:{sid}")],
        ])
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    await cb.answer()


# ═══════════════════════════════════════════════════════════════════════════
#  NODE CALLBACKS
# ═══════════════════════════════════════════════════════════════════════════

@tactical_router.callback_query(F.data.startswith("node:"))
async def handle_node(cb: types.CallbackQuery):
    get_user, save_user, supabase, DB_TABLE, normalize_user = _db()
    u_id = str(cb.from_user.id)
    user = get_user(u_id)
    if not user:
        await cb.answer("Please /start first.", show_alert=True)
        return

    parts    = cb.data.split(":")
    action   = parts[1] if len(parts) > 1 else ""
    sid      = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1
    node_key = parts[3].upper() if len(parts) > 3 else ""

    sector_state = _sector_state(sid)

    # ── node:occupy:3:A ───────────────────────────────────────────────────
    if action == "occupy":
        from sector_nodes import get_node, is_node_vacant
        from suit_system import can_enter_node
        from march_queue import create_march

        node_def = get_node(sid, node_key)
        if not node_def:
            await cb.answer("Node not found.", show_alert=True)
            return

        # Check suit
        can, reason = can_enter_node(user, sid, node_key)
        if not can:
            await cb.answer(reason, show_alert=True)
            return

        # Check vacant
        if not is_node_vacant(sector_state, sid, node_key):
            await cb.answer(
                f"⚔️ Node {node_key} is occupied. Use Attack instead.",
                show_alert=True
            )
            return

        node_name = node_def.get("name", node_key)

        # Check if player has any troops to send
        military = user.get("military", {})
        if not isinstance(military, dict) or sum(military.values()) == 0:
            await cb.answer(
                "❌ No troops to send. Train troops in your Military menu first.",
                show_alert=True
            )
            return

        # Send all available troops (simple default)
        troops_to_send = {k: v for k, v in military.items() if v > 0}

        ok, msg, user = create_march(
            user, "occupy", sid, node_key, node_name, troops_to_send
        )

        if ok:
            save_user(u_id, user)
            sector_state = _log_event(
                sid, sector_state,
                f"@{user.get('username','?')} marching to *{node_name}* [Node {node_key}]",
                event_type="arrival"
            )
            _save_sector_state(sid, sector_state)

        await cb.answer(msg[:200], show_alert=True)

    # ── node:attack:3:A ───────────────────────────────────────────────────
    elif action == "attack":
        from sector_nodes import get_node, get_node_occupant
        from march_queue import create_march
        from research_tree import is_feature_unlocked
        from march_queue import format_march_alert

        if not is_feature_unlocked(user, "node_attack"):
            await cb.answer("🔒 Research Siege Tactics to unlock node attacks.", show_alert=True)
            return

        node_def = get_node(sid, node_key)
        if not node_def:
            await cb.answer("Node not found.", show_alert=True)
            return

        occupant = get_node_occupant(sector_state, sid, node_key)
        if not occupant:
            await cb.answer("Node is now vacant — use Occupy instead.", show_alert=True)
            return

        node_name  = node_def.get("name", node_key)
        military   = user.get("military", {})
        troops     = {k: v for k, v in military.items() if v > 0}

        if not troops:
            await cb.answer("❌ No troops available.", show_alert=True)
            return

        ok, msg, user = create_march(
            user, "attack", sid, node_key, node_name, troops
        )

        if ok:
            save_user(u_id, user)
            alert = format_march_alert(user["march_queue"][-1])
            sector_state = _log_event(
                sid, sector_state,
                f"⚔️ @{user.get('username','?')} marching on *{node_name}* [attack]",
                event_type="battle"
            )
            _save_sector_state(sid, sector_state)

        await cb.answer(msg[:200], show_alert=True)

    # ── node:collect:3 or node:collect:3:A ───────────────────────────────
    elif action == "collect":
        current_node = user.get("current_node")
        if not current_node:
            await cb.answer("You're not occupying any node.", show_alert=True)
            return

        actual_node_key = node_key or current_node.get("node_key", "")
        actual_sid      = current_node.get("sector_id", sid)

        from sector_nodes import collect_node_resources
        from sector_cycles import get_resource_multiplier

        mult         = get_resource_multiplier(actual_sid)
        sector_state = _sector_state(actual_sid)

        sector_state, user, msg = collect_node_resources(
            sector_state, actual_sid, actual_node_key, u_id, user
        )
        save_user(u_id, user)

        from sector_report import log_large_collection
        node_def = user.get("current_node", {})
        _save_sector_state(actual_sid, sector_state)

        await cb.answer(msg[:200], show_alert=True)

    # ── node:leave:3 ──────────────────────────────────────────────────────
    elif action == "leave":
        current_node = user.get("current_node")
        if not current_node:
            await cb.answer("You're not on a node.", show_alert=True)
            return

        leave_sid      = current_node.get("sector_id", sid)
        leave_node_key = current_node.get("node_key", "")
        leave_name     = current_node.get("node_name", leave_node_key)
        leave_state    = _sector_state(leave_sid)

        from sector_nodes import auto_collect_on_departure
        leave_state, user, collected = auto_collect_on_departure(
            leave_state, leave_sid, leave_node_key, u_id, user
        )
        save_user(u_id, user)
        leave_state = _log_event(
            leave_sid, leave_state,
            f"@{user.get('username','?')} left *{leave_name}*",
            event_type="departure"
        )
        _save_sector_state(leave_sid, leave_state)

        collect_str = ""
        if collected:
            from resource_registry import RESOURCES
            parts_c = [
                f"{RESOURCES.get(k,{}).get('emoji','📦')}{v}"
                for k, v in collected.items()
            ]
            collect_str = f"\nAuto-collected: {' '.join(parts_c)}"

        await cb.answer(f"✅ Left {leave_name}.{collect_str}", show_alert=True)

    # ── node:suit_info:3:A ────────────────────────────────────────────────
    elif action == "suit_info":
        from sector_nodes import get_node
        from suit_system import get_required_suit_for_node
        from resource_registry import get_display_name

        node_def      = get_node(sid, node_key)
        required_suit = get_required_suit_for_node(sid, node_key)
        node_name     = node_def.get("name", node_key) if node_def else node_key
        suit_name     = get_display_name(required_suit) if required_suit else "None"

        await cb.answer(
            f"🔒 *{node_name}* requires:\n{suit_name}\n"
            f"Buy from Store or Alliance Shop, then equip.",
            show_alert=True
        )

    await cb.answer()


# ═══════════════════════════════════════════════════════════════════════════
#  TELEPORT CALLBACKS
# ═══════════════════════════════════════════════════════════════════════════

@tactical_router.callback_query(F.data.startswith("teleport:"))
async def handle_teleport(cb: types.CallbackQuery):
    get_user, save_user, supabase, DB_TABLE, normalize_user = _db()
    u_id  = str(cb.from_user.id)
    user  = get_user(u_id)
    if not user:
        await cb.answer("Please /start first.", show_alert=True)
        return

    parts  = cb.data.split(":")
    action = parts[1] if len(parts) > 1 else ""

    # ── teleport:menu ─────────────────────────────────────────────────────
    if action == "menu":
        from teleport_system import format_teleport_menu
        from sector_dominance import kb_teleport_sector_list
        alliance = _get_alliance(user)
        text     = format_teleport_menu(user, alliance)
        kb       = kb_teleport_sector_list(user, alliance)
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    # ── teleport:claim ────────────────────────────────────────────────────
    elif action == "claim":
        from teleport_system import claim_daily_teleports
        from sector_dominance import kb_teleport_sector_list
        ok, msg, user = claim_daily_teleports(user)
        save_user(u_id, user)
        kb = kb_teleport_sector_list(user, _get_alliance(user))
        await cb.answer(msg[:200], show_alert=True)
        try:
            await cb.message.edit_reply_markup(reply_markup=kb)
        except Exception:
            pass

    # ── teleport:go:6 ─────────────────────────────────────────────────────
    elif action == "go":
        target_sid   = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1
        from_sid     = user.get("commander_location", {}).get("sector_id", 1)
        sector_state = _sector_state(from_sid)

        from teleport_system import execute_teleport, format_sector_arrival_view
        from sector_report import log_player_departure, log_player_arrival
        from sector_dominance import kb_sector_dashboard

        ok, msg, user, sector_state = execute_teleport(
            user, target_sid, {}, sector_state,
            lambda sid, evt: _log_event(sid, _sector_state(sid), evt),
        )

        if ok:
            save_user(u_id, user)
            sector_state = log_player_departure(
                sector_state, from_sid,
                user.get("username", "?"), u_id, target_sid
            )
            _save_sector_state(from_sid, sector_state)

            new_state = _sector_state(target_sid)
            new_state = log_player_arrival(
                new_state, target_sid,
                user.get("username", "?"), u_id, "roaming"
            )
            # Register as roaming in new sector
            from teleport_system import register_roaming
            new_state = register_roaming(
                new_state, target_sid,
                u_id, user.get("username", "?"),
                user.get("military", {})
            )
            _save_sector_state(target_sid, new_state)

            alliance = _get_alliance(user)
            arrival_text = format_sector_arrival_view(
                target_sid, new_state, u_id, user, alliance
            )
            kb = kb_sector_dashboard(target_sid, user, new_state)
            try:
                await cb.message.edit_text(arrival_text, reply_markup=kb, parse_mode="Markdown")
            except Exception:
                await cb.message.answer(arrival_text, reply_markup=kb, parse_mode="Markdown")
        else:
            await cb.answer(msg[:200], show_alert=True)

    # ── teleport:buy_menu ─────────────────────────────────────────────────
    elif action == "buy_menu":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("Buy 1 charge (40🪙)",  callback_data="teleport:buy:1")],
            [InlineKeyboardButton("Buy 5 charges (180🪙)", callback_data="teleport:buy:5")],
            [InlineKeyboardButton("Buy 10 charges (350🪙)", callback_data="teleport:buy:10")],
            [InlineKeyboardButton("« Back", callback_data="teleport:menu")],
        ])
        try:
            await cb.message.edit_text(
                "🌀 *Purchase Teleport Charges*\n\n"
                "Each charge: 40 🪙\n5-pack: 180 🪙 (save 20)\n10-pack: 350 🪙 (save 50)",
                reply_markup=kb, parse_mode="Markdown"
            )
        except Exception:
            pass

    elif action == "buy":
        qty = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1
        from teleport_system import purchase_teleport_charges
        ok, msg, user = purchase_teleport_charges(user, qty)
        if ok:
            save_user(u_id, user)
        await cb.answer(msg[:200], show_alert=True)

    elif action == "locked":
        sid = int(parts[2]) if len(parts) > 2 else 0
        from teleport_system import SECTOR_QUICK_INFO
        info = SECTOR_QUICK_INFO.get(sid, {})
        restrict = info.get("restricted", "unknown_research")
        await cb.answer(
            f"🔒 Sector {sid} is locked.\nComplete research: {restrict}",
            show_alert=True
        )

    await cb.answer()


# ═══════════════════════════════════════════════════════════════════════════
#  RESEARCH CALLBACKS
# ═══════════════════════════════════════════════════════════════════════════

@tactical_router.callback_query(F.data.startswith("research:"))
async def handle_research(cb: types.CallbackQuery):
    get_user, save_user, supabase, DB_TABLE, normalize_user = _db()
    u_id  = str(cb.from_user.id)
    user  = get_user(u_id)
    if not user:
        await cb.answer("Please /start first.", show_alert=True)
        return

    parts  = cb.data.split(":")
    action = parts[1] if len(parts) > 1 else ""
    key    = parts[2] if len(parts) > 2 else ""

    from research_tree import (
        format_research_menu, format_research_detail,
        start_research, RESEARCH_TREE
    )

    # ── research:menu ─────────────────────────────────────────────────────
    if action == "menu":
        text = format_research_menu(user)
        kb   = _kb_research_menu(user)
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    # ── research:info:basic_mining ─────────────────────────────────────────
    elif action == "info":
        text = format_research_detail(key, user)
        kb   = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(f"🔬 Start Research", callback_data=f"research:start:{key}")],
            [InlineKeyboardButton("« Back",             callback_data="research:menu")],
        ])
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    # ── research:start:basic_mining ────────────────────────────────────────
    elif action == "start":
        ok, msg, user = start_research(user, key)
        if ok:
            save_user(u_id, user)
        await cb.answer(msg[:200], show_alert=True)
        if ok:
            # Refresh research menu
            text = format_research_menu(user)
            kb   = _kb_research_menu(user)
            try:
                await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
            except Exception:
                pass

    await cb.answer()


def _kb_research_menu(user: dict) -> InlineKeyboardMarkup:
    """Build research menu keyboard grouped by tier."""
    from research_tree import RESEARCH_TREE, is_researched, get_prerequisites_met, is_in_progress
    buttons = []

    for tier in [1, 2, 3, 4]:
        tier_items = [(k, v) for k, v in RESEARCH_TREE.items() if v.get("tier") == tier]
        for key, research in sorted(tier_items):
            name = research.get("name", key)
            if is_researched(user, key):
                label = f"✅ {name}"
            elif is_in_progress(user, key):
                label = f"⏳ {name}"
            else:
                prereqs_met, _ = get_prerequisites_met(user, key)
                label = f"📖 {name}" if prereqs_met else f"🔒 {name}"
            buttons.append([InlineKeyboardButton(label, callback_data=f"research:info:{key}")])

    buttons.append([InlineKeyboardButton("« Back", callback_data="base:dashboard")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ═══════════════════════════════════════════════════════════════════════════
#  SKILL TREE CALLBACKS
# ═══════════════════════════════════════════════════════════════════════════

@tactical_router.callback_query(F.data.startswith("skills:"))
async def handle_skills(cb: types.CallbackQuery):
    get_user, save_user, supabase, DB_TABLE, normalize_user = _db()
    u_id  = str(cb.from_user.id)
    user  = get_user(u_id)
    if not user:
        await cb.answer("Please /start first.", show_alert=True)
        return

    parts  = cb.data.split(":")
    action = parts[1] if len(parts) > 1 else ""

    from commander_skills import (
        format_skill_tree_summary, format_path_detail, format_tier_info,
        kb_skill_tree_main, kb_skill_path_detail, kb_reset_confirm,
        kb_unlock_confirm, allocate_skill_points, reset_skill_points,
        SKILL_PATHS
    )

    if action == "menu" or action == "summary":
        text = format_skill_tree_summary(user)
        kb   = kb_skill_tree_main(user)
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    elif action == "path":
        path = parts[2] if len(parts) > 2 else ""
        text = format_path_detail(user, path)
        kb   = kb_skill_path_detail(user, path)
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    elif action == "tier_info":
        path     = parts[2] if len(parts) > 2 else ""
        tier_num = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 1
        text     = format_tier_info(path, tier_num)
        cost     = SKILL_PATHS.get(path, {}).get("tiers", [{}] * tier_num)[tier_num - 1].get("cost", 0) if path in SKILL_PATHS else 0
        kb       = kb_unlock_confirm(path, tier_num, cost) if path in SKILL_PATHS else InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton("« Back", callback_data=f"skills:path:{path}")]])
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    elif action == "unlock":
        path     = parts[2] if len(parts) > 2 else ""
        tier_num = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 1
        cost     = SKILL_PATHS.get(path, {}).get("tiers", [{}] * tier_num)[tier_num - 1].get("cost", 0) if path in SKILL_PATHS else 0
        kb       = kb_unlock_confirm(path, tier_num, cost)
        tier_name = SKILL_PATHS.get(path, {}).get("tiers", [{}] * tier_num)[tier_num - 1].get("name", "?") if path in SKILL_PATHS else "?"
        try:
            await cb.message.edit_text(
                f"Confirm unlock:\n*{tier_name}* — {cost} skill points",
                reply_markup=kb, parse_mode="Markdown"
            )
        except Exception:
            pass

    elif action == "unlock_confirm":
        path     = parts[2] if len(parts) > 2 else ""
        tier_num = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 1
        ok, msg, user = allocate_skill_points(user, path, tier_num)
        if ok:
            save_user(u_id, user)
        await cb.answer(msg[:200], show_alert=True)
        if ok:
            text = format_path_detail(user, path)
            kb   = kb_skill_path_detail(user, path)
            try:
                await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
            except Exception:
                pass

    elif action == "reset_confirm":
        kb = kb_reset_confirm()
        try:
            await cb.message.edit_text(
                "🔄 *Reset all skill points?*\nThis is free and can be done anytime.\nAll points return to your pool.",
                reply_markup=kb, parse_mode="Markdown"
            )
        except Exception:
            pass

    elif action == "reset_execute":
        ok, msg, user = reset_skill_points(user)
        if ok:
            save_user(u_id, user)
        await cb.answer(msg[:200], show_alert=True)
        text = format_skill_tree_summary(user)
        kb   = kb_skill_tree_main(user)
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass

    await cb.answer()


# ═══════════════════════════════════════════════════════════════════════════
#  POWER CALLBACKS
# ═══════════════════════════════════════════════════════════════════════════

@tactical_router.callback_query(F.data.startswith("power:") | (F.data == "base:power"))
async def handle_power(cb: types.CallbackQuery):
    get_user, save_user, supabase, DB_TABLE, normalize_user = _db()
    u_id  = str(cb.from_user.id)
    user  = get_user(u_id)
    if not user:
        await cb.answer("Please /start first.", show_alert=True)
        return

    from power_system_v2 import format_power_display
    sid          = user.get("commander_location", {}).get("sector_id")
    sector_state = _sector_state(sid) if sid else None
    alliance     = _get_alliance(user)

    text = format_power_display(user, sid, sector_state, alliance, compact=False)
    kb   = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("🌟 Skill Tree",   callback_data="skills:menu")],
        [InlineKeyboardButton("🔬 Research",     callback_data="research:menu")],
        [InlineKeyboardButton("« Back",          callback_data="base:dashboard")],
    ])
    try:
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    await cb.answer()


# ═══════════════════════════════════════════════════════════════════════════
#  SUIT CALLBACKS
# ═══════════════════════════════════════════════════════════════════════════

@tactical_router.callback_query(F.data.startswith("suit:") | (F.data == "player:suit_menu"))
async def handle_suit(cb: types.CallbackQuery):
    get_user, save_user, supabase, DB_TABLE, normalize_user = _db()
    u_id  = str(cb.from_user.id)
    user  = get_user(u_id)
    if not user:
        await cb.answer("Please /start first.", show_alert=True)
        return

    from suit_system import format_suit_inventory, equip_suit, format_suit_status, SUIT_KEYS

    parts  = cb.data.split(":")
    action = parts[1] if len(parts) > 1 else "menu"

    if action == "menu" or cb.data == "player:suit_menu":
        text = format_suit_inventory(user)
        kb   = InlineKeyboardMarkup(inline_keyboard=[
            *[[InlineKeyboardButton(f"🧪 Equip {sk.replace('_',' ').title()}",
                                    callback_data=f"suit:equip:{sk}")]
              for sk in SUIT_KEYS
              if user.get("inventory", {}).get(sk, {}).get("qty", 0) > 0],
            [InlineKeyboardButton("« Back", callback_data="player:inventory")],
        ])
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    elif action == "equip":
        suit_key     = parts[2] if len(parts) > 2 else ""
        ok, msg, user = equip_suit(user, suit_key)
        if ok:
            save_user(u_id, user)
        await cb.answer(msg[:200], show_alert=True)

    await cb.answer()


# ═══════════════════════════════════════════════════════════════════════════
#  WAR ROOM CALLBACKS
# ═══════════════════════════════════════════════════════════════════════════

@tactical_router.callback_query(F.data.startswith("war:"))
async def handle_war(cb: types.CallbackQuery):
    get_user, save_user, supabase, DB_TABLE, normalize_user = _db()
    u_id  = str(cb.from_user.id)
    user  = get_user(u_id)
    if not user:
        await cb.answer("Please /start first.", show_alert=True)
        return

    alliance = _get_alliance(user)
    parts    = cb.data.split(":")
    action   = parts[1] if len(parts) > 1 else ""

    from alliance_war_bounty import format_war_room, kb_war_room

    if action == "room" or action == "scores" or action == "objectives":
        is_leader = user.get("alliance_role") in ("LEADER", "OFFICER")
        text      = format_war_room(user, alliance, is_leader)
        kb        = kb_war_room(alliance, user)
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    elif action == "issue_command":
        await cb.answer(
            "📣 Type your command:\nSend it as a message starting with !war cmd [your command]",
            show_alert=True
        )

    elif action == "ack_menu":
        war    = alliance.get("active_war", {})
        stream = war.get("command_stream", [])
        if not stream:
            await cb.answer("No commands to acknowledge.", show_alert=True)
            return
        latest = stream[-1]
        cmd_num = latest.get("num", 1)
        from alliance_war_bounty import acknowledge_command
        ok, msg, alliance = acknowledge_command(user, alliance, cmd_num)
        await cb.answer(msg[:200], show_alert=True)

    await cb.answer()


# ═══════════════════════════════════════════════════════════════════════════
#  BOUNTY BOARD CALLBACKS
# ═══════════════════════════════════════════════════════════════════════════

@tactical_router.callback_query(F.data.startswith("bounty:"))
async def handle_bounty(cb: types.CallbackQuery):
    get_user, save_user, supabase, DB_TABLE, normalize_user = _db()
    u_id  = str(cb.from_user.id)
    user  = get_user(u_id)
    if not user:
        await cb.answer("Please /start first.", show_alert=True)
        return

    parts  = cb.data.split(":")
    action = parts[1] if len(parts) > 1 else ""

    from alliance_war_bounty import (
        format_bounty_board, kb_bounty_board,
        should_appear_on_bounty_board, kb_place_bounty_amount
    )

    if action == "board":
        try:
            result   = supabase.table("bounty_board").select("*").eq(
                "status", "active"
            ).execute()
            bounties = result.data or []
        except Exception:
            bounties = []

        # Auto-visible players
        try:
            all_users = supabase.table(DB_TABLE).select(
                "user_id, username, base_shielded, shield_expires_at, inventory, home_sector"
            ).execute()
            auto_vis = []
            for pu in (all_users.data or []):
                pu = normalize_user(pu)
                on_board, reason = should_appear_on_bounty_board(pu)
                if on_board and pu.get("user_id") != u_id:
                    pu["board_reason"] = reason
                    auto_vis.append(pu)
        except Exception:
            auto_vis = []

        text = format_bounty_board(bounties, auto_vis[:10], user)
        kb   = kb_bounty_board(bounties, user)
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    elif action == "place":
        await cb.answer(
            "🎯 To place a bounty:\nUse !bounty @username [amount]\nMin 50 🪙",
            show_alert=True
        )

    elif action == "view":
        bid = parts[2] if len(parts) > 2 else ""
        try:
            r       = supabase.table("bounty_board").select("*").eq("bounty_id", bid).execute()
            bounty  = r.data[0] if r.data else None
        except Exception:
            bounty  = None

        if not bounty:
            await cb.answer("Bounty not found.", show_alert=True)
            return

        target_name = bounty.get("target_name", "?")
        reward      = bounty.get("reward_gold", 0)
        reason      = bounty.get("reason", "?")
        home_sid    = bounty.get("target_home_sector")

        from teleport_system import SECTOR_QUICK_INFO
        home_str = ""
        if home_sid:
            hi       = SECTOR_QUICK_INFO.get(home_sid, {})
            home_str = f"\n🏠 Home: {hi.get('emoji','')} {hi.get('name', f'Sector {home_sid}')}"

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(f"🌀 Teleport to Hunt", callback_data=f"teleport:go:{home_sid or 1}")],
            [InlineKeyboardButton("« Board",             callback_data="bounty:board")],
        ])
        try:
            await cb.message.edit_text(
                f"🎯 *BOUNTY: @{target_name}*\n"
                f"Reward: {reward} 🪙\nReason: {reason}{home_str}\n\n"
                f"Teleport to their sector and defeat them to claim.",
                reply_markup=kb, parse_mode="Markdown"
            )
        except Exception:
            pass

    await cb.answer()


# ═══════════════════════════════════════════════════════════════════════════
#  DOMINANCE CALLBACKS
# ═══════════════════════════════════════════════════════════════════════════

@tactical_router.callback_query(F.data.startswith("dominance:"))
async def handle_dominance(cb: types.CallbackQuery):
    get_user, save_user, supabase, DB_TABLE, normalize_user = _db()
    u_id  = str(cb.from_user.id)
    user  = get_user(u_id)
    if not user:
        await cb.answer("Please /start first.", show_alert=True)
        return

    parts  = cb.data.split(":")
    action = parts[1] if len(parts) > 1 else ""
    sid    = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1

    if action == "pretender":
        from sector_dominance import kb_pretender_confirm
        sector_state  = _sector_state(sid)
        dom           = sector_state.get("dominance", {})
        ruler_name    = dom.get("ruler_name", "Unknown")
        from teleport_system import SECTOR_QUICK_INFO
        info          = SECTOR_QUICK_INFO.get(sid, {})
        sector_name   = info.get("name", f"Sector {sid}")
        kb            = kb_pretender_confirm(sid)
        try:
            await cb.message.edit_text(
                f"⚔️ *Declare yourself Pretender to {sector_name}?*\n\n"
                f"Current Ruler: @{ruler_name}\n"
                f"You have 48h to build more dominance than them.\n"
                f"This declaration is *public* — the whole server will know.",
                reply_markup=kb, parse_mode="Markdown"
            )
        except Exception:
            pass

    elif action == "pretender_confirm":
        from sector_dominance import declare_pretender
        sector_state = _sector_state(sid)
        from initiation import CHECKMATE_HQ_GROUP_ID
        ok, msg, sector_state = declare_pretender(
            user, sid, sector_state,
            lambda s, m: _log_event(s, _sector_state(s), m),
            lambda m: asyncio.create_task(
                cb.bot.send_message(CHECKMATE_HQ_GROUP_ID, m, parse_mode="Markdown")
            ),
        )
        _save_sector_state(sid, sector_state)
        await cb.answer(msg[:200], show_alert=True)

    await cb.answer()


# ═══════════════════════════════════════════════════════════════════════════
#  RULER CALLBACKS
# ═══════════════════════════════════════════════════════════════════════════

@tactical_router.callback_query(F.data.startswith("ruler:"))
async def handle_ruler(cb: types.CallbackQuery):
    get_user, save_user, supabase, DB_TABLE, normalize_user = _db()
    u_id  = str(cb.from_user.id)
    user  = get_user(u_id)
    if not user:
        await cb.answer("Please /start first.", show_alert=True)
        return

    parts  = cb.data.split(":")
    action = parts[1] if len(parts) > 1 else ""
    sid    = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1

    sector_state = _sector_state(sid)
    dom          = sector_state.get("dominance", {})

    if dom.get("ruler_id") != u_id:
        await cb.answer("❌ You are not the Sector Ruler.", show_alert=True)
        return

    if action == "panel":
        from sector_dominance import kb_ruler_panel, format_sector_dominance_board
        text = format_sector_dominance_board(sid, sector_state)
        kb   = kb_ruler_panel(sid, sector_state)
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    elif action == "vision":
        from sector_dominance import format_ruler_vision
        text = format_ruler_vision(sid, sector_state)
        kb   = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("« Ruler Panel", callback_data=f"ruler:panel:{sid}")]
        ])
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    elif action == "tax":
        dom      = sector_state.get("dominance", {})
        tax_pool = dom.get("tax_pool", {})
        if not tax_pool:
            await cb.answer("Tax pool is empty. Collect more resources in your sector.", show_alert=True)
            return
        from resource_registry import RESOURCES
        parts_t = [f"{RESOURCES.get(k,{}).get('emoji','📦')}{v}" for k, v in tax_pool.items()]
        await cb.answer(f"💰 Pending tax: {' '.join(parts_t)}\n(Distributed at cycle end)", show_alert=True)

    elif action == "scores":
        from sector_dominance import format_sector_dominance_board
        text = format_sector_dominance_board(sid, sector_state)
        kb   = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("« Panel", callback_data=f"ruler:panel:{sid}")]
        ])
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass

    await cb.answer()


# ═══════════════════════════════════════════════════════════════════════════
#  BASE DASHBOARD CALLBACK (extends existing /start)
# ═══════════════════════════════════════════════════════════════════════════

@tactical_router.callback_query(F.data == "base:dashboard")
async def handle_base_dashboard(cb: types.CallbackQuery):
    """Refresh the main dashboard. Triggers /start equivalent."""
    await cb.answer()
    await cb.message.answer(
        "🏠 Tap /start to open your full dashboard.",
    )


@tactical_router.callback_query(F.data == "player:notification")
async def handle_notification(cb: types.CallbackQuery):
    get_user, save_user, supabase, DB_TABLE, normalize_user = _db()
    u_id = str(cb.from_user.id)
    user = get_user(u_id)
    if not user:
        await cb.answer()
        return
    from teleport_system import get_pending_notification
    notif = get_pending_notification(user)
    if notif:
        user["pending_notification"] = ""
        user["suit_just_expired"]    = False
        user["shield_just_expired"]  = False
        save_user(u_id, user)
        await cb.answer(notif[:200], show_alert=True)
    else:
        await cb.answer("No new notifications.", show_alert=True)
