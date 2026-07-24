# -*- coding: utf-8 -*-
"""
main_p5_patch.py — Phase 5 Callback Handlers
=============================================
All new callback_query handlers for Phase 5 systems.
Register as a Router included in main.py's Dispatcher.

HOW TO ADD TO main.py:
  from main_p5_patch import p5_router
  dp.include_router(p5_router)

  # Add alongside existing dp.include_router() calls.
  # Place BEFORE dp.start_polling(bot).

ALSO ADD TO main.py startup (inside async def main()):
  from server_lifecycle import on_startup, on_shutdown
  asyncio.create_task(on_startup(bot, supabase, DB_TABLE))
  dp.shutdown.register(lambda: asyncio.create_task(
      on_shutdown(bot, supabase, DB_TABLE)
  ))

ALSO ADD to cmd_start and every callback, near the top:
  from server_lifecycle import check_maintenance_mode, maintenance_response
  if await check_maintenance_mode(supabase):
      await maintenance_response(message)
      return

CALLBACK DATA FORMAT:
  "ps:action:sector_id[:param]"     — private sector
  "mission:action[:param]"          — alliance missions
  "notif_toggle:type"               — notification settings
  "notif_all_on / notif_all_off"    — bulk notification toggle
"""

import asyncio
import json
from datetime import datetime, timedelta
from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

p5_router = Router()


# ── DB helpers ────────────────────────────────────────────────────────────
def _db():
    from supabase_db import get_user, save_user, supabase, DB_TABLE
    return get_user, save_user, supabase, DB_TABLE


def _load_sector_state(sector_id: int) -> dict:
    from supabase_db import supabase, safe_json
    try:
        r = supabase.table("sector_state").select("*").eq(
            "sector_id", sector_id
        ).execute()
        if r.data:
            state = dict(r.data[0])
            for f in ["occupancy", "roaming", "dominance", "private_sector"]:
                state[f] = safe_json(state.get(f), default={})
            for f in ["sector_chat", "event_log"]:
                state[f] = safe_json(state.get(f), default=[])
            return state
    except Exception as e:
        print(f"[PS] load sector_state error {sector_id}: {e}")
    return {"sector_id": sector_id, "occupancy": {}, "roaming": {},
            "sector_chat": [], "event_log": [], "dominance": {},
            "private_sector": {}}


def _save_sector_state(sector_id: int, state: dict):
    from supabase_db import supabase
    # Strip non-DB fields
    ALLOWED = {
        "sector_id", "occupancy", "roaming", "sector_chat", "active_predators",
        "active_jam", "dominance", "pending_ruler_alerts", "pending_predator_loot",
        "pending_notifications", "incoming_marches", "last_phase_name",
        "last_updated", "event_log", "warnings_sent", "private_sector",
    }
    clean = {k: v for k, v in state.items() if k in ALLOWED}
    clean["last_updated"] = datetime.utcnow().isoformat()
    try:
        supabase.table("sector_state").upsert(
            {"sector_id": sector_id, **clean}
        ).execute()
    except Exception as e:
        print(f"[PS] save sector_state error {sector_id}: {e}")


def _load_alliance(user: dict) -> dict:
    aid = user.get("alliance_id")
    if not aid:
        return {}
    try:
        with open("alliances.json", "r") as f:
            return json.load(f).get(aid, {})
    except Exception:
        return {}


def _save_alliance(alliance: dict):
    aid = alliance.get("id")
    if not aid:
        return
    try:
        with open("alliances.json", "r") as f:
            alliances = json.load(f)
    except Exception:
        alliances = {}
    alliances[aid] = alliance
    with open("alliances.json", "w") as f:
        json.dump(alliances, f, indent=2)


def _get_current_priority_mission():
    """Load server-wide priority mission from sector_meta or a JSON file."""
    try:
        with open("priority_mission.json", "r") as f:
            return json.load(f)
    except Exception:
        return None


def _save_priority_mission(mission: dict):
    with open("priority_mission.json", "w") as f:
        json.dump(mission, f, indent=2)


# ═══════════════════════════════════════════════════════════════════════════
#  PRIVATE SECTOR CALLBACKS  (ps:*)
# ═══════════════════════════════════════════════════════════════════════════

@p5_router.callback_query(F.data.startswith("ps:"))
async def handle_private_sector(cb: types.CallbackQuery):
    get_user, save_user, supabase, DB_TABLE = _db()
    u_id = str(cb.from_user.id)
    user = get_user(u_id)
    if not user:
        await cb.answer("Please /start first.", show_alert=True)
        return

    parts     = cb.data.split(":")
    action    = parts[1] if len(parts) > 1 else ""
    sector_id = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1
    extra     = parts[3] if len(parts) > 3 else ""
    extra2    = parts[4] if len(parts) > 4 else ""

    ss = _load_sector_state(sector_id)
    ps = ss.get("private_sector", {})

    from private_sector import (
        is_resident, is_ruler, init_private_sector,
        format_private_sector_map, format_outsider_view,
        format_access_queue, get_fortress_status,
        request_access, approve_access, deny_access,
        evict_resident, claim_plot, collect_plot_resources,
        destroy_resource_plot, attack_fortress, reinforce_fortress,
        contribute_ap_to_settlement, expand_settlement,
        post_private_chat, tick_resource_plots, tick_weather,
        kb_private_sector_outsider, kb_private_sector_resident,
        kb_ruler_admin, kb_plot_actions, SETTLEMENT_TIERS,
    )

    player_name = user.get("username", "Commander")
    home_sector = user.get("home_sector")
    base_name   = user.get("base_name", "Base")

    # ── ps:enter:3 ────────────────────────────────────────────────────────
    if action == "enter" or action == "map":
        if not ps:
            # No private sector exists yet
            dom = ss.get("dominance", {})
            ruler_id = dom.get("ruler_id")
            if ruler_id == u_id:
                # Ruler can establish the settlement
                ps = init_private_sector(sector_id, u_id, player_name)
                ss["private_sector"] = ps
                _save_sector_state(sector_id, ss)
                text = (
                    f"🏕️ *Settlement Established!*\n\n"
                    f"You have founded a settlement in Sector {sector_id}.\n"
                    f"It starts with 4 empty plots.\n"
                    f"Invite members, claim plots, and grow it into a Capital.\n\n"
                    + format_private_sector_map(ps, u_id)
                )
                kb = kb_private_sector_resident(sector_id, u_id, ps)
            else:
                text = (
                    f"🔒 *No Private Settlement*\n\n"
                    f"This sector has no private settlement yet.\n"
                    f"The Sector Ruler can establish one."
                )
                kb = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton("⬅️ Back", callback_data=f"sector:dashboard:{sector_id}")
                ]])
        elif is_resident(ps, u_id):
            # Tick resources and weather before showing
            ps = tick_resource_plots(ps)
            ps, weather_msg = tick_weather(ps)
            ss["private_sector"] = ps
            _save_sector_state(sector_id, ss)

            text = format_private_sector_map(ps, u_id)
            if weather_msg:
                text = f"{weather_msg}\n\n{text}"
            kb = kb_private_sector_resident(sector_id, u_id, ps)
        else:
            # Outsider view
            text = format_outsider_view(ps)
            kb   = kb_private_sector_outsider(sector_id, ps)

        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    # ── ps:observe:3 ──────────────────────────────────────────────────────
    elif action == "observe":
        if not ps:
            await cb.answer("No settlement exists here.", show_alert=True)
            return
        text = format_outsider_view(ps)
        kb   = kb_private_sector_outsider(sector_id, ps)
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    # ── ps:request:3 ──────────────────────────────────────────────────────
    elif action == "request":
        if not ps:
            await cb.answer("No settlement exists here.", show_alert=True)
            return
        if is_resident(ps, u_id):
            await cb.answer("You already have access.", show_alert=True)
            return

        military    = user.get("military", {}) or {}
        troop_count = sum(v for v in military.values() if isinstance(v, int))

        ok, msg, ps = request_access(
            ps, u_id, player_name, home_sector, base_name, troop_count
        )
        ss["private_sector"] = ps
        _save_sector_state(sector_id, ss)

        # Notify ruler
        if ok and ps.get("ruler_id"):
            try:
                from notification_engine import notify_player
                from teleport_system import SECTOR_QUICK_INFO
                sinfo = SECTOR_QUICK_INFO.get(sector_id, {})
                sname = sinfo.get("name", f"Sector {sector_id}")
                await notify_player(
                    cb.bot, ps["ruler_id"], "dominance",
                    f"🛂 *Access Request*\n@{player_name} wants entry to your settlement in {sname}.\n"
                    f"Home: Sector {home_sector}  |  Army: {troop_count} troops\n"
                    f"Open Private Sector → Access Queue to respond.",
                    supabase, DB_TABLE
                )
            except Exception:
                pass

        await cb.answer(msg[:200], show_alert=True)

    # ── ps:access_queue:3 ─────────────────────────────────────────────────
    elif action == "access_queue":
        if not is_ruler(ps, u_id):
            await cb.answer("Ruler access only.", show_alert=True)
            return
        text = format_access_queue(ps)
        requests = [r for r in ps.get("access_requests", []) if r.get("status") == "pending"]
        buttons  = []
        for r in requests[:5]:
            pid  = r.get("player_id", "")
            name = r.get("player_name", "?")
            buttons.append([
                InlineKeyboardButton(f"✅ Approve @{name}", callback_data=f"ps:approve:{sector_id}:{pid}"),
                InlineKeyboardButton(f"❌ Deny @{name}",    callback_data=f"ps:deny:{sector_id}:{pid}"),
            ])
        buttons.append([InlineKeyboardButton("⬅️ Back", callback_data=f"ps:ruler_panel:{sector_id}")])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    # ── ps:approve:3:player_id ────────────────────────────────────────────
    elif action == "approve":
        applicant_id = extra
        ok, msg, ps, notif = approve_access(ps, u_id, applicant_id)
        if ok:
            ss["private_sector"] = ps
            _save_sector_state(sector_id, ss)
            if notif:
                try:
                    await cb.bot.send_message(int(applicant_id), notif, parse_mode="Markdown")
                except Exception:
                    pass
        await cb.answer(msg[:200], show_alert=True)

    # ── ps:deny:3:player_id ───────────────────────────────────────────────
    elif action == "deny":
        applicant_id = extra
        ok, msg, ps, notif = deny_access(ps, u_id, applicant_id)
        if ok:
            ss["private_sector"] = ps
            _save_sector_state(sector_id, ss)
            if notif:
                try:
                    await cb.bot.send_message(int(applicant_id), notif, parse_mode="Markdown")
                except Exception:
                    pass
        await cb.answer(msg[:200], show_alert=True)

    # ── ps:plots:3 ────────────────────────────────────────────────────────
    elif action == "plots":
        if not is_resident(ps, u_id):
            await cb.answer("Residents only.", show_alert=True)
            return
        plots   = ps.get("plots", {})
        buttons = []
        for plot_id, plot in sorted(plots.items()):
            from private_sector import PLOT_TYPES
            ptype  = plot.get("type", "empty_plot")
            pdata  = PLOT_TYPES.get(ptype, {})
            emoji  = pdata.get("emoji", "⬜")
            label  = pdata.get("label", "Plot")
            owner  = plot.get("owner_name", "")
            pending = int(plot.get("pending_resources", 0))
            suffix = f" [{pending}⏳]" if pending > 0 else ""
            owner_tag = f" @{owner}" if owner else " (empty)"
            buttons.append([InlineKeyboardButton(
                text=f"{emoji} [{plot_id}] {label}{owner_tag}{suffix}",
                callback_data=f"ps:plot_detail:{sector_id}:{plot_id}"
            )])
        buttons.append([InlineKeyboardButton("⬅️ Back", callback_data=f"ps:map:{sector_id}")])
        text = f"🗺️ *Settlement Plots — Sector {sector_id}*\n{len(plots)} total plots"
        kb   = InlineKeyboardMarkup(inline_keyboard=buttons)
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    # ── ps:plot_detail:3:A ────────────────────────────────────────────────
    elif action == "plot_detail":
        plot_id = extra
        if not is_resident(ps, u_id):
            await cb.answer("Residents only.", show_alert=True)
            return
        plots = ps.get("plots", {})
        plot  = plots.get(plot_id, {})
        if not plot:
            await cb.answer("Plot not found.", show_alert=True)
            return
        from private_sector import PLOT_TYPES
        ptype  = plot.get("type", "empty_plot")
        pdata  = PLOT_TYPES.get(ptype, {})
        text   = (
            f"{pdata.get('emoji','⬜')} *Plot {plot_id} — {pdata.get('label','?')}*\n"
            f"{pdata.get('description','')}\n\n"
            f"Owner: {plot.get('owner_name', 'Unclaimed') or 'Unclaimed'}\n"
            f"Pending: {int(plot.get('pending_resources',0))}"
        )
        kb = kb_plot_actions(sector_id, plot_id, plot, u_id)
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    # ── ps:claim_plot:3:A:base_plot ───────────────────────────────────────
    elif action == "claim_plot":
        plot_id   = extra
        plot_type = extra2 or "base_plot"
        ok, msg, ps = claim_plot(ps, u_id, player_name, plot_id, plot_type)
        if ok:
            ss["private_sector"] = ps
            _save_sector_state(sector_id, ss)
        await cb.answer(msg[:200], show_alert=True)

    # ── ps:claim_menu:3:A ─────────────────────────────────────────────────
    elif action == "claim_menu":
        plot_id = extra
        buttons = [
            [InlineKeyboardButton("🏰 Base Plot",    callback_data=f"ps:claim_plot:{sector_id}:{plot_id}:base_plot")],
            [InlineKeyboardButton("⛏️ Iron Plot",    callback_data=f"ps:claim_plot:{sector_id}:{plot_id}:iron_plot")],
            [InlineKeyboardButton("🪨 Stone Plot",   callback_data=f"ps:claim_plot:{sector_id}:{plot_id}:stone_plot")],
            [InlineKeyboardButton("🏺 Relic Plot",   callback_data=f"ps:claim_plot:{sector_id}:{plot_id}:relic_plot")],
            [InlineKeyboardButton("🥫 Hydroponic Bay Plot",    callback_data=f"ps:claim_plot:{sector_id}:{plot_id}:food_plot")],
            [InlineKeyboardButton("⬅️ Back",         callback_data=f"ps:plot_detail:{sector_id}:{plot_id}")],
        ]
        try:
            await cb.message.edit_text(
                f"Choose plot type for *Plot {plot_id}*:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
                parse_mode="Markdown"
            )
        except Exception:
            pass

    # ── ps:collect:3:A ────────────────────────────────────────────────────
    elif action == "collect":
        plot_id = extra
        ps = tick_resource_plots(ps)
        ok, msg, ps, user = collect_plot_resources(ps, u_id, plot_id, user)
        if ok:
            save_user(u_id, user)
            ss["private_sector"] = ps
            _save_sector_state(sector_id, ss)
        await cb.answer(msg[:200], show_alert=True)

    # ── ps:collect_all:3 ──────────────────────────────────────────────────
    elif action == "collect_all":
        if not is_resident(ps, u_id):
            await cb.answer("Residents only.", show_alert=True)
            return
        ps     = tick_resource_plots(ps)
        plots  = ps.get("plots", {})
        total  = {}
        for plot_id, plot in plots.items():
            if plot.get("owner_id") == u_id and plot.get("pending_resources", 0) > 0:
                ok, _, ps, user = collect_plot_resources(ps, u_id, plot_id, user)
        save_user(u_id, user)
        ss["private_sector"] = ps
        _save_sector_state(sector_id, ss)
        await cb.answer("✅ All plot resources collected!", show_alert=True)

    # ── ps:attack_fortress:3 ──────────────────────────────────────────────
    elif action == "attack_fortress":
        if not ps:
            await cb.answer("No fortress to attack.", show_alert=True)
            return
        if is_resident(ps, u_id):
            await cb.answer("❌ You cannot attack a fortress you're a resident of.", show_alert=True)
            return

        try:
            from power_system_v2 import get_total_power
            power = get_total_power(user)
        except Exception:
            power = user.get("level", 1) * 100

        ps, fell, report = attack_fortress(ps, u_id, player_name, power)
        ss["private_sector"] = ps
        _save_sector_state(sector_id, ss)

        # Notify residents
        residents = ps.get("residents", {})
        for rid in residents:
            if rid != u_id:
                try:
                    from notification_engine import notify_player
                    await notify_player(
                        cb.bot, rid, "combat_incoming", report, supabase, DB_TABLE
                    )
                except Exception:
                    pass

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("⚔️ Attack Again", callback_data=f"ps:attack_fortress:{sector_id}")],
            [InlineKeyboardButton("⬅️ Back",         callback_data=f"sector:dashboard:{sector_id}")],
        ])
        try:
            await cb.message.edit_text(report, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(report, reply_markup=kb, parse_mode="Markdown")

    # ── ps:reinforce:3 ────────────────────────────────────────────────────
    elif action == "reinforce":
        military = user.get("military", {}) or {}
        troops   = sum(v for v in military.values() if isinstance(v, int))
        if troops < 10:
            await cb.answer("❌ Need at least 10 troops to reinforce.", show_alert=True)
            return
        send     = min(troops // 4, 50)  # Send 25% of army, max 50
        ok, msg, ps = reinforce_fortress(ps, u_id, player_name, send)
        if ok:
            # Deduct troops from user
            first_unit = next((k for k, v in military.items() if v >= send), None)
            if first_unit:
                military[first_unit] = max(0, military[first_unit] - send)
                user["military"] = military
                save_user(u_id, user)
            ss["private_sector"] = ps
            _save_sector_state(sector_id, ss)
        await cb.answer(msg[:200], show_alert=True)

    # ── ps:chat:3 ─────────────────────────────────────────────────────────
    elif action == "chat":
        if not is_resident(ps, u_id):
            await cb.answer("Residents only.", show_alert=True)
            return
        chat = ps.get("private_chat", [])
        lines = ["💬 *SETTLEMENT PRIVATE CHAT*\n━━━━━━━━━━━━━━━━━━"]
        if not chat:
            lines.append("_No messages yet. Be the first to speak._")
        else:
            for entry in list(reversed(chat[:15])):
                t    = entry.get("time_str", "?")
                name = entry.get("player_name", "?")
                msg  = entry.get("message", "")
                is_sys = entry.get("is_system", False)
                if is_sys:
                    lines.append(f"  _{t} {msg}_")
                else:
                    lines.append(f"  [{t}] *{name}*: {msg}")
        lines.append("━━━━━━━━━━━━━━━━━━")
        lines.append("_Type your message as a reply to this message._")
        text = "\n".join(lines)
        kb   = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("⬅️ Back", callback_data=f"ps:map:{sector_id}")]
        ])
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    # ── ps:ruler_panel:3 ──────────────────────────────────────────────────
    elif action == "ruler_panel":
        if not is_ruler(ps, u_id):
            await cb.answer("Ruler access only.", show_alert=True)
            return
        fortress = get_fortress_status(ps)
        tier     = ps.get("tier", "settlement")
        tdata    = SETTLEMENT_TIERS.get(tier, {})
        ap_total = ps.get("ap_contributed", 0)
        ap_need  = tdata.get("ap_to_next", 0) or 0
        text = (
            f"👑 *RULER ADMIN PANEL*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Settlement: {tdata.get('emoji','')} *{tdata.get('name','')}*\n"
            f"Residents: {len(ps.get('residents', {}))}\n"
            f"Fortress HP: {fortress['pct']}%\n"
            f"AP Progress: {ap_total}/{ap_need or '∞'}\n"
            f"Pending requests: {sum(1 for r in ps.get('access_requests',[]) if r.get('status')=='pending')}"
        )
        try:
            await cb.message.edit_text(text, reply_markup=kb_ruler_admin(sector_id), parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb_ruler_admin(sector_id), parse_mode="Markdown")

    # ── ps:upgrade:3 ──────────────────────────────────────────────────────
    elif action == "upgrade":
        if not is_ruler(ps, u_id):
            await cb.answer("Ruler access only.", show_alert=True)
            return
        ok, msg, ps = expand_settlement(ps, u_id)
        if ok:
            ss["private_sector"] = ps
            _save_sector_state(sector_id, ss)
            # Notify all residents
            for rid in ps.get("residents", {}):
                if rid != u_id:
                    try:
                        await cb.bot.send_message(int(rid), f"🎉 {msg}", parse_mode="Markdown")
                    except Exception:
                        pass
        await cb.answer(msg[:200], show_alert=True)

    # ── ps:residents:3 ────────────────────────────────────────────────────
    elif action == "residents":
        if not is_ruler(ps, u_id):
            await cb.answer("Ruler access only.", show_alert=True)
            return
        residents = ps.get("residents", {})
        lines     = [f"👥 *RESIDENTS ({len(residents)})*\n━━━━━━━━━━━━━━━━━━"]
        buttons   = []
        for pid, rdata in residents.items():
            name = rdata.get("player_name", "?") if isinstance(rdata, dict) else "?"
            role = rdata.get("role", "member") if isinstance(rdata, dict) else "member"
            lines.append(f"  {'👑' if role=='ruler' else '👤'} @{name} — {role}")
            if pid != u_id:
                buttons.append([InlineKeyboardButton(
                    f"🚫 Evict @{name}",
                    callback_data=f"ps:evict:{sector_id}:{pid}"
                )])
        buttons.append([InlineKeyboardButton("⬅️ Back", callback_data=f"ps:ruler_panel:{sector_id}")])
        text = "\n".join(lines)
        kb   = InlineKeyboardMarkup(inline_keyboard=buttons)
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    # ── ps:evict:3:player_id ─────────────────────────────────────────────
    elif action == "evict":
        target_id = extra
        ok, msg, ps, notif = evict_resident(ps, u_id, target_id)
        if ok:
            ss["private_sector"] = ps
            _save_sector_state(sector_id, ss)
            if notif:
                try:
                    await cb.bot.send_message(int(target_id), notif, parse_mode="Markdown")
                except Exception:
                    pass
        await cb.answer(msg[:200], show_alert=True)

    await cb.answer()


# ═══════════════════════════════════════════════════════════════════════════
#  MISSION CALLBACKS  (mission:*)
# ═══════════════════════════════════════════════════════════════════════════

@p5_router.callback_query(F.data.startswith("mission:"))
async def handle_missions(cb: types.CallbackQuery):
    get_user, save_user, supabase, DB_TABLE = _db()
    u_id     = str(cb.from_user.id)
    user     = get_user(u_id)
    if not user:
        await cb.answer("Please /start first.", show_alert=True)
        return

    parts    = cb.data.split(":")
    action   = parts[1] if len(parts) > 1 else ""
    param    = parts[2] if len(parts) > 2 else ""

    alliance  = _load_alliance(user)
    is_leader = user.get("alliance_role") in ("LEADER", "OFFICER")

    from alliance_missions import (
        get_or_generate_today_missions, get_active_missions,
        leader_select_missions, format_mission_pool, format_member_missions,
        format_priority_mission, claim_ap_rewards,
        accept_priority_mission, generate_priority_mission,
        kb_mission_hub, kb_leader_mission_select, kb_priority_mission,
    )

    # ── mission:hub ───────────────────────────────────────────────────────
    if action == "hub":
        if not alliance:
            await cb.answer("You need to be in an alliance.", show_alert=True)
            return
        pending = alliance.get("pending_ap_rewards", {})
        my_ap   = pending.get(u_id, 0) if isinstance(pending, dict) else 0
        text    = (
            f"📋 *MISSION CENTER*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Alliance: *{alliance.get('name','?')}*\n"
            f"Alliance Points: *{alliance.get('alliance_points',0)} AP*\n"
            f"Your pending AP: *{my_ap}*\n\n"
            f"Complete missions to earn AP for your alliance.\n"
            f"AP unlocks alliance shop items and upgrades."
        )
        kb = kb_mission_hub(user, alliance)
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    # ── mission:member_view ───────────────────────────────────────────────
    elif action == "member_view":
        if not alliance:
            await cb.answer("Join an alliance first.", show_alert=True)
            return
        # Ensure pool is generated
        get_or_generate_today_missions(alliance)
        text = format_member_missions(alliance)
        kb   = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("💰 Claim AP", callback_data="mission:claim_ap")],
            [InlineKeyboardButton("⬅️ Mission Hub", callback_data="mission:hub")],
        ])
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    # ── mission:leader_pool ───────────────────────────────────────────────
    elif action == "leader_pool":
        if not is_leader:
            await cb.answer("Leaders only.", show_alert=True)
            return
        if not alliance:
            await cb.answer("No alliance.", show_alert=True)
            return
        get_or_generate_today_missions(alliance)
        text = format_mission_pool(alliance, is_leader=True)
        kb   = kb_leader_mission_select(alliance)
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    # ── mission:toggle:mission_id ─────────────────────────────────────────
    elif action == "toggle":
        if not is_leader:
            await cb.answer("Leaders only.", show_alert=True)
            return
        mission_id = param
        pool       = alliance.get("mission_pool", {})
        selected   = pool.get("selected_ids", [])

        if mission_id in selected:
            selected.remove(mission_id)
        else:
            if len(selected) >= 3:
                await cb.answer("❌ Already selected 3 missions. Deselect one first.", show_alert=True)
                return
            selected.append(mission_id)

        pool["selected_ids"]   = selected
        alliance["mission_pool"] = pool
        _save_alliance(alliance)

        kb = kb_leader_mission_select(alliance)
        try:
            await cb.message.edit_reply_markup(reply_markup=kb)
        except Exception:
            pass
        await cb.answer(f"{'Selected' if mission_id in selected else 'Deselected'}.")

    # ── mission:confirm_selection ─────────────────────────────────────────
    elif action == "confirm_selection":
        if not is_leader:
            await cb.answer("Leaders only.", show_alert=True)
            return
        pool     = alliance.get("mission_pool", {})
        selected = pool.get("selected_ids", [])
        ok, msg, alliance = leader_select_missions(alliance, user, selected)
        _save_alliance(alliance)

        # Notify all members
        members = alliance.get("members", [])
        for mid in members:
            if mid != u_id:
                try:
                    from notification_engine import notify_player
                    await notify_player(
                        cb.bot, mid, "alliance_mission",
                        f"*{alliance.get('name','Alliance')}* has assigned today's missions.\n"
                        f"Open Alliance → Missions to see your tasks.",
                        supabase, DB_TABLE
                    )
                except Exception:
                    pass

        await cb.answer(msg[:200], show_alert=True)
        # Refresh view
        text = format_member_missions(alliance)
        kb   = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("⬅️ Mission Hub", callback_data="mission:hub")]
        ])
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass

    # ── mission:claim_ap ──────────────────────────────────────────────────
    elif action == "claim_ap":
        if not alliance:
            await cb.answer("No alliance.", show_alert=True)
            return
        ap, user, alliance = claim_ap_rewards(alliance, u_id, user)
        if ap > 0:
            save_user(u_id, user)
            _save_alliance(alliance)
            await cb.answer(f"✅ Claimed {ap} Alliance Points!", show_alert=True)
        else:
            await cb.answer("No AP ready to claim.", show_alert=True)

    # ── mission:priority ──────────────────────────────────────────────────
    elif action == "priority":
        active_pm = alliance.get("active_priority_mission") if alliance else None
        if not active_pm:
            server_pm = _get_current_priority_mission()
        else:
            server_pm = active_pm

        text = format_priority_mission(server_pm) if server_pm else (
            "🚨 *PRIORITY MISSIONS*\n\n"
            "_No priority mission active right now._\n"
            "The Commander issues these periodically. Check back soon."
        )
        kb = kb_priority_mission(alliance or {}, user)
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    # ── mission:accept_priority ───────────────────────────────────────────
    elif action == "accept_priority":
        if not is_leader:
            await cb.answer("Leaders only.", show_alert=True)
            return
        pm = _get_current_priority_mission()
        if not pm:
            await cb.answer("No priority mission available.", show_alert=True)
            return
        ok, msg, alliance = accept_priority_mission(alliance, user, pm)
        if ok:
            _save_alliance(alliance)
            # Notify members
            members = alliance.get("members", [])
            for mid in members:
                if mid != u_id:
                    try:
                        from notification_engine import notify_priority_mission
                        await notify_priority_mission(
                            cb.bot, mid,
                            pm["name"], f"+{pm['ap_reward']} AP",
                            pm["time_hours"], supabase, DB_TABLE
                        )
                    except Exception:
                        pass
        await cb.answer(msg[:200], show_alert=True)

    await cb.answer()


# ═══════════════════════════════════════════════════════════════════════════
#  NOTIFICATION SETTING CALLBACKS
# ═══════════════════════════════════════════════════════════════════════════

@p5_router.callback_query(F.data.startswith("notif_toggle:"))
async def handle_notif_toggle(cb: types.CallbackQuery):
    get_user, save_user, supabase, DB_TABLE = _db()
    u_id  = str(cb.from_user.id)
    user  = get_user(u_id)
    if not user:
        await cb.answer()
        return

    ntype = cb.data.replace("notif_toggle:", "")
    from notification_engine import (
        get_notification_preferences, set_notification_preference,
        format_notification_settings, kb_notification_settings
    )

    prefs   = get_notification_preferences(user)
    current = prefs.get(ntype, True)
    user    = set_notification_preference(user, ntype, not current)
    save_user(u_id, user)

    text = format_notification_settings(user)
    kb   = kb_notification_settings(user)
    try:
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        pass
    await cb.answer(f"{'Enabled' if not current else 'Disabled'} {ntype.replace('_',' ')}")


@p5_router.callback_query(F.data.in_({"notif_all_on", "notif_all_off"}))
async def handle_notif_all(cb: types.CallbackQuery):
    get_user, save_user, supabase, DB_TABLE = _db()
    u_id    = str(cb.from_user.id)
    user    = get_user(u_id)
    if not user:
        await cb.answer()
        return

    enable = cb.data == "notif_all_on"
    from notification_engine import (
        DEFAULT_PREFERENCES, set_notification_preference,
        format_notification_settings, kb_notification_settings
    )

    for ntype in DEFAULT_PREFERENCES:
        user = set_notification_preference(user, ntype, enable)
    save_user(u_id, user)

    text = format_notification_settings(user)
    kb   = kb_notification_settings(user)
    try:
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        pass
    await cb.answer("All notifications " + ("enabled" if enable else "disabled"))


@p5_router.callback_query(F.data == "menu_notifications")
async def handle_notif_menu(cb: types.CallbackQuery):
    get_user, save_user, supabase, DB_TABLE = _db()
    u_id = str(cb.from_user.id)
    user = get_user(u_id)
    if not user:
        await cb.answer()
        return

    from notification_engine import format_notification_settings, kb_notification_settings
    text = format_notification_settings(user)
    kb   = kb_notification_settings(user)
    try:
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")
    await cb.answer()


# ═══════════════════════════════════════════════════════════════════════════
#  GAMEMASTER BROADCAST — Admin command in main group
#  Usage: !gm [event_key] in group, bot account only
# ═══════════════════════════════════════════════════════════════════════════

@p5_router.message(F.text.startswith("!gm "))
async def handle_gamemaster_broadcast(message: types.Message):
    """Admin-only Gamemaster broadcast command."""
    from supabase_db import supabase, DB_TABLE
    # Only allow from specific admin IDs — replace with your Telegram user ID
    ADMIN_IDS = []   # Add your user ID here: e.g. [123456789]
    u_id = str(message.from_user.id)
    if int(u_id) not in ADMIN_IDS:
        return  # Silently ignore non-admins

    event_key = message.text.replace("!gm ", "").strip()
    from notification_engine import broadcast_gamemaster, get_gamemaster_line

    # Preview the message first
    preview = get_gamemaster_line(event_key)
    await message.reply(f"📢 *Preview:*\n{preview}\n\n_Broadcasting..._", parse_mode="Markdown")

    sent = await broadcast_gamemaster(
        message.bot, event_key, supabase, DB_TABLE, active_hours=48
    )
    await message.reply(f"✅ Broadcast sent to {sent} players.")


# ═══════════════════════════════════════════════════════════════════════════
#  SCHEDULER ADDITIONS FOR PHASE 5
#  Add these tasks to scheduler.py's start_scheduler function
# ═══════════════════════════════════════════════════════════════════════════

async def phase5_tick(bot, supabase, DB_TABLE: str):
    """
    Phase 5 scheduler tick — runs every 5 minutes.
    1. Tick private sector resource plots
    2. Check suit expiry warnings
    3. Issue priority missions (once per 6h randomly)
    4. Send daily reward notifications at midnight UTC
    """
    import random

    # 1. Tick all private sector resource plots
    try:
        sector_result = supabase.table("sector_state").select(
            "sector_id, private_sector"
        ).execute()

        for row in (sector_result.data or []):
            sid = row.get("sector_id")
            ps_raw = row.get("private_sector")
            if not ps_raw:
                continue

            from supabase_db import safe_json
            ps = safe_json(ps_raw, default={})
            if not ps or not ps.get("plots"):
                continue

            from private_sector import tick_resource_plots, tick_weather
            ps = tick_resource_plots(ps)
            ps, weather_msg = tick_weather(ps)

            if weather_msg:
                # Notify residents of weather change
                residents = ps.get("residents", {})
                for rid in residents:
                    try:
                        from notification_engine import notify_player
                        await notify_player(
                            bot, rid, "sector_alert",
                            f"Sector {sid} — {weather_msg}", supabase, DB_TABLE
                        )
                    except Exception:
                        pass

            supabase.table("sector_state").update({
                "private_sector": ps
            }).eq("sector_id", sid).execute()

    except Exception as e:
        print(f"[P5_TICK] Private sector tick error: {e}")

    # 2. Suit expiry warnings
    try:
        now    = datetime.utcnow()
        warn_before = now + timedelta(minutes=2)

        result = supabase.table(DB_TABLE).select(
            "user_id, active_suit"
        ).not_.is_("active_suit", "null").execute()

        from supabase_db import safe_json
        from notification_engine import notify_suit_expiring

        for row in (result.data or []):
            uid  = row.get("user_id")
            suit = safe_json(row.get("active_suit"), default={})
            if not suit:
                continue
            try:
                exp = datetime.fromisoformat(suit.get("expires_at", ""))
                if now < exp <= warn_before:
                    remaining = int((exp - now).total_seconds())
                    suit_name = suit.get("display_name", "Suit")
                    await notify_suit_expiring(bot, uid, suit_name, remaining, supabase, DB_TABLE)
            except Exception:
                pass

    except Exception as e:
        print(f"[P5_TICK] Suit warning error: {e}")

    # 3. Issue priority mission periodically (every 6h, random chance)
    try:
        import os
        last_pm_file = "last_priority_mission.txt"
        issue_new    = False

        if os.path.exists(last_pm_file):
            with open(last_pm_file) as f:
                last_str = f.read().strip()
            try:
                last_dt  = datetime.fromisoformat(last_str)
                if (datetime.utcnow() - last_dt).total_seconds() > 21600:  # 6h
                    issue_new = random.random() < 0.3   # 30% chance per tick
            except Exception:
                issue_new = True
        else:
            issue_new = True

        if issue_new:
            from alliance_missions import generate_priority_mission
            pm = generate_priority_mission()
            _save_priority_mission(pm)

            with open(last_pm_file, "w") as f:
                f.write(datetime.utcnow().isoformat())

            from notification_engine import broadcast_gamemaster
            await broadcast_gamemaster(
                bot, "priority_mission_new", supabase, DB_TABLE, active_hours=48
            )
            print(f"[P5_TICK] Priority mission issued: {pm['name']}")

    except Exception as e:
        print(f"[P5_TICK] Priority mission error: {e}")


SCHEDULER_PATCH = """
# ── ADD TO scheduler.py start_scheduler(), inside the while True loop ──────

# Phase 5 tick (every 5 minutes = every 5 loop iterations of 60s)
if tick_count % 5 == 0:
    from main_p5_patch import phase5_tick
    await phase5_tick(bot, supabase, DB_TABLE)
"""
