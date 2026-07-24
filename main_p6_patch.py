# -*- coding: utf-8 -*-
"""
main_p6_patch.py — Phase 6 Callback Handlers
=============================================
All callback_query and message handlers for Phase 6 systems.

HOW TO ADD TO main.py:
  from main_p6_patch import p6_router
  dp.include_router(p6_router)

  Add alongside existing dp.include_router() calls,
  BEFORE dp.start_polling(bot).

ALSO ADD to scheduler.py start_scheduler() while loop:
  # Phase 6 ticks
  if tick_count % 5 == 0:      # Every 5 minutes
      from main_p6_patch import phase6_tick
      await phase6_tick(bot, supabase, DB_TABLE, GROUP_CHAT_ID)

  if should_publish_chronicle():   # Monday midnight UTC
      from chronicle import publish_chronicle, should_publish_now
      if should_publish_now():
          await publish_chronicle(bot, supabase, DB_TABLE, GROUP_CHAT_ID)

DB_TABLE is "players" throughout this file.
"""

import asyncio
import json
import os
from datetime import datetime
from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

p6_router = Router()
DB_TABLE  = "players"


# ── Shared helpers ────────────────────────────────────────────────────────
def _db():
    from supabase_db import get_user, save_user, supabase
    return get_user, save_user, supabase


def _load_alliance(user: dict) -> dict:
    aid = user.get("alliance_id")
    if not aid:
        return {}
    try:
        with open("alliances.json") as f:
            return json.load(f).get(aid, {})
    except Exception:
        return {}


def _save_alliance(alliance: dict):
    aid = alliance.get("id")
    if not aid:
        return
    try:
        with open("alliances.json") as f:
            alliances = json.load(f)
    except Exception:
        alliances = {}
    alliances[aid] = alliance
    with open("alliances.json", "w") as f:
        json.dump(alliances, f, indent=2)


def _in_hidden_sector(user: dict) -> bool:
    loc = user.get("commander_location", {}) or {}
    sid = loc.get("sector_id", 0)
    return 10 <= sid <= 59


# ═══════════════════════════════════════════════════════════════════════════
#  BOUNTY HUNTER CALLBACKS  (hunter:*)
# ═══════════════════════════════════════════════════════════════════════════

@p6_router.callback_query(F.data.startswith("hunter:"))
async def handle_hunter(cb: types.CallbackQuery):
    get_user, save_user, supabase = _db()
    u_id = str(cb.from_user.id)
    user = get_user(u_id)
    if not user:
        await cb.answer("Please /start first.", show_alert=True)
        return

    parts  = cb.data.split(":")
    action = parts[1] if len(parts) > 1 else ""
    param  = parts[2] if len(parts) > 2 else ""
    param2 = parts[3] if len(parts) > 3 else ""

    from bounty_hunter import (
        is_bounty_hunter, activate_hunter_career, format_hunter_profile,
        format_bounty_board, kb_bounty_board, kb_hunter_profile,
        kb_place_bounty_amount, should_appear_on_board, place_bounty,
        claim_bounty, remove_self_from_board, use_free_hunter_teleport,
        get_hunter_tier, BOUNTY_MIN_REWARD,
    )

    is_hunter = is_bounty_hunter(user)

    # ── hunter:board ──────────────────────────────────────────────────────
    if action == "board":
        try:
            r = supabase.table("bounty_board").select("*").eq(
                "status", "active"
            ).execute()
            bounties = r.data or []
        except Exception:
            bounties = []

        # Auto-visible players
        try:
            from supabase_db import normalize_user
            r2 = supabase.table(DB_TABLE).select(
                "user_id, username, base_shielded, shield_expires_at, "
                "inventory, home_sector, last_active"
            ).execute()
            auto_vis = []
            for p in (r2.data or []):
                p = normalize_user(p)
                on_board, reason = should_appear_on_board(p)
                if on_board and p.get("user_id") != u_id:
                    p["board_reason"] = reason
                    auto_vis.append(p)
        except Exception:
            auto_vis = []

        text = format_bounty_board(bounties, auto_vis[:8], user, is_hunter)
        kb   = kb_bounty_board(bounties, user, is_hunter)
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    # ── hunter:profile ────────────────────────────────────────────────────
    elif action == "profile":
        text = format_hunter_profile(user)
        kb   = kb_hunter_profile(user)
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    # ── hunter:activate ───────────────────────────────────────────────────
    elif action == "activate":
        text = (
            f"💀 *BECOME A BOUNTY HUNTER*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Cost: *{BOUNTY_MIN_REWARD * 10} 🪙*\n\n"
            f"*5 hunter tiers* — Tracker → Shadow → Infiltrator → Ghost → Assassin\n\n"
            f"*Abilities unlock as you kill:*\n"
            f"  🔭 Tier 1 — See target home sectors\n"
            f"  🌑 Tier 2 — Free daily teleport to target sector\n"
            f"  🕵️ Tier 3 — Remote scout across sectors\n"
            f"  👻 Tier 4 — Arrive in sectors undetected\n"
            f"  💀 Tier 5 — +30% power vs bounty targets\n\n"
            f"Your base, troops, and alliance are unaffected."
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="💀 Activate (500 🪙)",
                callback_data="hunter:activate_confirm"
            )],
            [InlineKeyboardButton("✗ Cancel", callback_data="hunter:board")],
        ])
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    # ── hunter:activate_confirm ───────────────────────────────────────────
    elif action == "activate_confirm":
        ok, msg, user = activate_hunter_career(user)
        if ok:
            save_user(u_id, user)
        await cb.answer(msg[:200], show_alert=True)
        if ok:
            text = format_hunter_profile(user)
            kb   = kb_hunter_profile(user)
            try:
                await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
            except Exception:
                pass

    # ── hunter:place_bounty ───────────────────────────────────────────────
    elif action == "place_bounty":
        await cb.answer(
            "To place a bounty, find the player and tap Place Bounty on their profile.\n"
            "Or use: !bounty @username [amount]",
            show_alert=True
        )

    # ── hunter:place_confirm:target_id:amount ────────────────────────────
    elif action == "place_confirm":
        target_id  = param
        try:
            amount = int(param2)
        except ValueError:
            amount = BOUNTY_MIN_REWARD

        # Get target info
        try:
            r = supabase.table(DB_TABLE).select(
                "user_id, username, home_sector"
            ).eq("user_id", target_id).execute()
            if not r.data:
                await cb.answer("Target not found.", show_alert=True)
                return
            target     = r.data[0]
            tname      = target.get("username", "?")
            home_sector = target.get("home_sector")
        except Exception:
            await cb.answer("Error loading target.", show_alert=True)
            return

        ok, msg, user = place_bounty(
            user, target_id, tname, home_sector, amount,
            "Bounty placed via board", supabase, DB_TABLE
        )
        if ok:
            save_user(u_id, user)
        await cb.answer(msg[:200], show_alert=True)

    # ── hunter:view_bounty:bounty_id ─────────────────────────────────────
    elif action == "view_bounty":
        bid = param
        try:
            r = supabase.table("bounty_board").select("*").eq(
                "bounty_id", bid
            ).execute()
            bounty = r.data[0] if r.data else None
        except Exception:
            bounty = None

        if not bounty:
            await cb.answer("Bounty not found.", show_alert=True)
            return

        from teleport_system import SECTOR_QUICK_INFO
        home_sid  = bounty.get("target_home_sector")
        home_str  = ""
        if is_hunter and home_sid:
            hi       = SECTOR_QUICK_INFO.get(home_sid, {})
            home_str = f"\n🏠 Home: {hi.get('emoji','')} {hi.get('name', f'S{home_sid}')}"

        text = (
            f"🎯 *BOUNTY TARGET*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Target: *@{bounty.get('target_name','?')}*\n"
            f"Reward: *{bounty.get('reward_gold',0)} 🪙*\n"
            f"Rank: {bounty.get('rank','C')}\n"
            f"Reason: {bounty.get('reason','?')}\n"
            f"Posted by: @{bounty.get('posted_by_name','?')}"
            f"{home_str}\n\n"
            f"_Defeat them in battle then use `!claim {bid}` within 5 minutes._"
        )

        buttons = []
        if is_hunter and home_sid:
            buttons.append([InlineKeyboardButton(
                text=f"🌀 Teleport to their sector",
                callback_data=f"teleport:go:{home_sid}"
            )])
            # Shadow teleport (tier 2)
            from bounty_hunter import has_hunter_ability, use_free_hunter_teleport
            if has_hunter_ability(user, 2):
                buttons.append([InlineKeyboardButton(
                    text="🌑 Shadow Teleport (free)",
                    callback_data=f"hunter:shadow_tp:{home_sid}"
                )])

        buttons.append([InlineKeyboardButton("⬅️ Board", callback_data="hunter:board")])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)

        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    # ── hunter:shadow_tp:sector_id ───────────────────────────────────────
    elif action == "shadow_tp":
        try:
            target_sid = int(param)
        except ValueError:
            await cb.answer("Invalid sector.", show_alert=True)
            return

        ok, msg, user = use_free_hunter_teleport(user)
        if not ok:
            await cb.answer(msg[:200], show_alert=True)
            return

        # Execute teleport (no charge consumed)
        from teleport_system import execute_teleport
        from supabase_db import safe_json

        def _load_ss(sid):
            try:
                r = supabase.table("sector_state").select("*").eq(
                    "sector_id", sid
                ).execute()
                if r.data:
                    s = dict(r.data[0])
                    for f in ["occupancy", "roaming", "dominance"]:
                        s[f] = safe_json(s.get(f), default={})
                    for f in ["sector_chat", "event_log"]:
                        s[f] = safe_json(s.get(f), default=[])
                    return s
            except Exception:
                pass
            return {"sector_id": sid, "occupancy": {}, "roaming": {},
                    "sector_chat": [], "event_log": [], "dominance": {}}

        from_sid     = user.get("commander_location", {}).get("sector_id", 1)
        sector_state = _load_ss(from_sid)

        # Ghost arrival — don't log if tier 4
        from bounty_hunter import has_hunter_ability
        ghost_arrival = has_hunter_ability(user, 4)

        def log_fn(sid, msg_txt):
            if ghost_arrival and sid == target_sid:
                return  # Ghost — no log on arrival
            pass  # Normal log handled elsewhere

        ok2, msg2, user, sector_state = execute_teleport(
            user, target_sid, {}, sector_state, log_fn
        )

        if ok2:
            save_user(u_id, user)
            await cb.answer(f"🌑 Shadow Teleport activated! {msg}", show_alert=True)
        else:
            await cb.answer(msg2[:200], show_alert=True)

    # ── hunter:remove_self ────────────────────────────────────────────────
    elif action == "remove_self":
        ok, msg, user = remove_self_from_board(user, supabase, DB_TABLE)
        if ok:
            save_user(u_id, user)
        await cb.answer(msg[:200], show_alert=True)

    await cb.answer()


# ═══════════════════════════════════════════════════════════════════════════
#  SECTOR WAR CALLBACKS  (war:*)
# ═══════════════════════════════════════════════════════════════════════════

@p6_router.callback_query(F.data.startswith("war:"))
async def handle_sector_war(cb: types.CallbackQuery):
    get_user, save_user, supabase = _db()
    u_id     = str(cb.from_user.id)
    user     = get_user(u_id)
    if not user:
        await cb.answer("Please /start first.", show_alert=True)
        return

    parts  = cb.data.split(":")
    action = parts[1] if len(parts) > 1 else ""

    from sector_war import (
        get_active_war, format_war_scoreboard, kb_war_scoreboard,
        is_in_war, get_war_side,
    )

    war       = get_active_war()
    alliance  = _load_alliance(user)
    alliance_id = alliance.get("id") if alliance else None

    # ── war:status ────────────────────────────────────────────────────────
    if action == "status" or action == "scores":
        if not war:
            text = (
                "⚔️ *SECTOR WAR*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "_No active Sector War._\n\n"
                "Wars trigger automatically when an alliance controls "
                f"3+ sectors simultaneously."
            )
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton("📰 Chronicle", callback_data="chronicle:view")],
                [InlineKeyboardButton("⬅️ Back",      callback_data="menu_back")],
            ])
        else:
            text = format_war_scoreboard(war, alliance_id)
            kb   = kb_war_scoreboard(war, alliance_id)

        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    # ── war:events ────────────────────────────────────────────────────────
    elif action == "events":
        if not war:
            await cb.answer("No active war.", show_alert=True)
            return

        events = war.get("events", [])[-20:]
        lines  = ["📜 *WAR EVENT LOG*\n━━━━━━━━━━━━━━━━━━"]
        side   = get_war_side(alliance_id) if alliance_id else None

        for e in reversed(events):
            t      = e.get("time", "?")
            pname  = e.get("player_name", "?")
            detail = e.get("detail", "")
            score  = e.get("score", 0)
            e_side = e.get("side", "?")
            icon   = "🟢" if (side and e_side == side) else "🔴"
            lines.append(f"{icon} [{t}] @{pname}: {detail} (+{score})")

        text = "\n".join(lines)
        kb   = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("⬅️ War Status", callback_data="war:status")]
        ])
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    # ── war:objectives ────────────────────────────────────────────────────
    elif action == "objectives":
        if not war:
            await cb.answer("No active war.", show_alert=True)
            return

        side    = get_war_side(alliance_id) if alliance_id else None
        my_objs = war.get(f"objectives_{side}", {}) if side else {}
        them    = "b" if side == "a" else "a"
        them_objs = war.get(f"objectives_{them}", {}) if side else {}

        from sector_war import WAR_OBJECTIVES
        lines = ["🎯 *WAR OBJECTIVES*\n━━━━━━━━━━━━━━━━━━"]
        for obj in WAR_OBJECTIVES:
            oid      = obj["id"]
            my_done  = my_objs.get(oid, False)
            th_done  = them_objs.get(oid, False)
            icon     = "✅" if my_done else ("❌" if th_done else "☐")
            lines.append(
                f"{icon} *{obj['name']}* (+{obj['score']})\n"
                f"   {obj['desc']}"
            )

        text = "\n".join(lines)
        kb   = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("⬅️ War Status", callback_data="war:status")]
        ])
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    await cb.answer()


# ═══════════════════════════════════════════════════════════════════════════
#  CHRONICLE CALLBACKS  (chronicle:*)
# ═══════════════════════════════════════════════════════════════════════════

@p6_router.callback_query(F.data.startswith("chronicle:"))
async def handle_chronicle(cb: types.CallbackQuery):
    parts  = cb.data.split(":")
    action = parts[1] if len(parts) > 1 else ""

    from chronicle import get_last_chronicle, format_chronicle_preview

    if action == "view":
        last = get_last_chronicle()
        if not last:
            text = (
                "📰 *THE COMMANDER'S CHRONICLE*\n\n"
                "_No Chronicle published yet._\n"
                "Published every Monday at midnight UTC."
            )
        else:
            text = last

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("⬅️ Back", callback_data="menu_back")]
        ])
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            # Chronicle may be too long — send as new message
            await cb.message.answer(text[:4000], parse_mode="Markdown", reply_markup=kb)

    elif action == "preview":
        text = format_chronicle_preview()
        kb   = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("📰 Read Full", callback_data="chronicle:view")],
            [InlineKeyboardButton("⬅️ Back",      callback_data="menu_back")],
        ])
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    await cb.answer()


# ═══════════════════════════════════════════════════════════════════════════
#  CRAFTING CALLBACKS  (craft:*)
# ═══════════════════════════════════════════════════════════════════════════

@p6_router.callback_query(F.data.startswith("craft:"))
async def handle_craft(cb: types.CallbackQuery):
    get_user, save_user, supabase = _db()
    u_id = str(cb.from_user.id)
    user = get_user(u_id)
    if not user:
        await cb.answer("Please /start first.", show_alert=True)
        return

    # Complete any finished crafts first
    from crafting_system import (
        check_and_complete_crafts, format_craft_menu, format_recipe_detail,
        start_craft, apply_speedup_to_craft, kb_craft_menu,
        kb_recipe_list, kb_recipe_detail, RECIPES, CATEGORY_LABELS,
    )

    user, completed = check_and_complete_crafts(user)
    if completed:
        save_user(u_id, user)
        for name in completed:
            try:
                from notification_engine import notify_player
                await notify_player(
                    cb.bot, u_id, "build_complete",
                    f"⚗️ *{name}* crafted successfully! Check your backpack.",
                    supabase, DB_TABLE
                )
            except Exception:
                pass

    parts  = cb.data.split(":")
    action = parts[1] if len(parts) > 1 else ""
    param  = parts[2] if len(parts) > 2 else ""
    param2 = parts[3] if len(parts) > 3 else ""

    # ── craft:menu ────────────────────────────────────────────────────────
    if action == "menu":
        text = format_craft_menu(user)
        kb   = kb_craft_menu(user)
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    # ── craft:cat:military ────────────────────────────────────────────────
    elif action == "cat":
        category = param
        if category not in CATEGORY_LABELS:
            await cb.answer("Unknown category.", show_alert=True)
            return
        text = format_craft_menu(user, category=category)
        kb   = kb_recipe_list(user, category)
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    # ── craft:detail:recipe_key ───────────────────────────────────────────
    elif action == "detail":
        recipe_key = param
        text = format_recipe_detail(recipe_key, user)
        kb   = kb_recipe_detail(recipe_key, user)
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    # ── craft:start:recipe_key ────────────────────────────────────────────
    elif action == "start":
        recipe_key = param
        ok, msg, user = start_craft(user, recipe_key)
        if ok:
            save_user(u_id, user)
        await cb.answer(msg[:200], show_alert=True)
        if ok:
            recipe = RECIPES.get(recipe_key, {})
            cat    = recipe.get("category", "consumable")
            text   = format_craft_menu(user, category=cat)
            kb     = kb_recipe_list(user, cat)
            try:
                await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
            except Exception:
                pass

    # ── craft:speedup_menu:recipe_key ────────────────────────────────────
    elif action == "speedup_menu":
        recipe_key = param
        inv        = user.get("inventory", []) or []
        speedups   = [(k, v) for k, v in inv.items()
                      if "speedup" in k and isinstance(v, dict) and v.get("qty", 0) > 0]
        if not speedups:
            await cb.answer("No speedup items in inventory.", show_alert=True)
            return

        buttons = []
        for skey, sdata in speedups:
            label = f"{sdata.get('emoji','⏩')} {sdata.get('display', skey)} ×{sdata.get('qty',0)}"
            buttons.append([InlineKeyboardButton(
                text=label,
                callback_data=f"craft:speedup:{recipe_key}:{skey}"
            )])
        buttons.append([InlineKeyboardButton("✗ Cancel",
                        callback_data=f"craft:detail:{recipe_key}")])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        try:
            await cb.message.edit_text(
                "⏩ *Choose a speedup item:*",
                reply_markup=kb, parse_mode="Markdown"
            )
        except Exception:
            pass

    # ── craft:speedup:recipe_key:speedup_item ────────────────────────────
    elif action == "speedup":
        recipe_key   = param
        speedup_item = param2
        ok, msg, user = apply_speedup_to_craft(user, recipe_key, speedup_item)
        if ok:
            save_user(u_id, user)
        await cb.answer(msg[:200], show_alert=True)

    await cb.answer()


# ═══════════════════════════════════════════════════════════════════════════
#  BLACK MARKET CALLBACKS  (market:*)
# ═══════════════════════════════════════════════════════════════════════════

@p6_router.callback_query(F.data.startswith("market:"))
async def handle_market(cb: types.CallbackQuery):
    get_user, save_user, supabase = _db()
    u_id = str(cb.from_user.id)
    user = get_user(u_id)
    if not user:
        await cb.answer("Please /start first.", show_alert=True)
        return

    parts  = cb.data.split(":")
    action = parts[1] if len(parts) > 1 else ""
    param  = parts[2] if len(parts) > 2 else ""

    from black_market import (
        get_active_listings, create_listing, purchase_listing,
        cancel_listing, format_market_board, format_exclusive_catalog,
        kb_market_main, kb_listing_actions, EXCLUSIVE_ITEMS,
    )

    in_hidden = _in_hidden_sector(user)

    # ── market:browse:all ─────────────────────────────────────────────────
    if action == "browse":
        cat      = param if param != "all" else None
        listings = get_active_listings(category=cat)
        text     = format_market_board(listings, u_id, in_hidden)
        kb       = kb_market_main(in_hidden)
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    # ── market:exclusives ─────────────────────────────────────────────────
    elif action == "exclusives":
        text = format_exclusive_catalog()
        kb   = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("🏪 Browse Listings", callback_data="market:browse:all")],
            [InlineKeyboardButton("⬅️ Back",            callback_data="market:browse:all")],
        ])
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    # ── market:my_listings ────────────────────────────────────────────────
    elif action == "my_listings":
        listings = get_active_listings(seller_id=u_id)
        if not listings:
            text = "🏪 *My Listings*\n\n_No active listings._"
            kb   = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton("🏷️ List an Item", callback_data="market:list_item")],
                [InlineKeyboardButton("⬅️ Back",         callback_data="market:browse:all")],
            ])
        else:
            text = format_market_board(listings, u_id, in_hidden)
            buttons = []
            for l in listings[:5]:
                lid  = l.get("listing_id", "")
                name = l.get("item_name", "?")
                buttons.append([InlineKeyboardButton(
                    text=f"🗑️ Cancel: {name}",
                    callback_data=f"market:cancel:{lid}"
                )])
            buttons.append([InlineKeyboardButton(
                "⬅️ Back", callback_data="market:browse:all"
            )])
            kb = InlineKeyboardMarkup(inline_keyboard=buttons)

        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    # ── market:list_item ──────────────────────────────────────────────────
    elif action == "list_item":
        if not in_hidden:
            await cb.answer(
                "❌ Must be in a hidden sector (10-59) to list items.",
                show_alert=True
            )
            return
        # Show listable inventory items
        inv     = user.get("inventory", []) or []
        buttons = []
        for i in inv:
            if not isinstance(i, dict) or i.get("qty", 0) <= 0:
                continue
            emoji = i.get("emoji", "📦")
            name  = i.get("display", i.get("key"))
            qty   = i.get("qty", 0)
            buttons.append([InlineKeyboardButton(
                text=f"{emoji} {name} ×{qty}",
                callback_data=f"market:list_select:{i.get('key')}"
            )])

        if not buttons:
            await cb.answer("No items to list.", show_alert=True)
            return

        buttons.append([InlineKeyboardButton("✗ Cancel", callback_data="market:browse:all")])
        try:
            await cb.message.edit_text(
                "🏷️ *Select item to list:*",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
                parse_mode="Markdown"
            )
        except Exception:
            pass

    # ── market:list_select:item_key ───────────────────────────────────────
    elif action == "list_select":
        item_key = param
        inv      = user.get("inventory", []) or []
        item     = next((i for i in inv if i.get("key") == item_key), {})
        if not isinstance(item, dict) or item.get("qty", 0) <= 0:
            await cb.answer("Item not available.", show_alert=True)
            return

        # Show price options
        prices   = [50, 100, 200, 500, 1000, 2000]
        buttons  = []
        row      = []
        for price in prices:
            row.append(InlineKeyboardButton(
                text=f"{price}🪙",
                callback_data=f"market:list_confirm:{item_key}:{price}"
            ))
            if len(row) == 3:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        buttons.append([InlineKeyboardButton("✗ Cancel", callback_data="market:list_item")])

        emoji = item.get("emoji", "📦")
        name  = item.get("display", item_key)
        try:
            await cb.message.edit_text(
                f"💰 *Set price for {emoji} {name}:*",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
                parse_mode="Markdown"
            )
        except Exception:
            pass

    # ── market:list_confirm:item_key:price ───────────────────────────────
    elif action == "list_confirm":
        item_key = param
        try:
            price = int(parts[3]) if len(parts) > 3 else 100
        except ValueError:
            price = 100

        sector_id = user.get("commander_location", {}).get("sector_id", 0)
        ok, msg, user = create_listing(user, item_key, 1, price, sector_id)
        if ok:
            save_user(u_id, user)
        await cb.answer(msg[:200], show_alert=True)
        if ok:
            listings = get_active_listings()
            text     = format_market_board(listings, u_id, in_hidden)
            kb       = kb_market_main(in_hidden)
            try:
                await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
            except Exception:
                pass

    # ── market:buy:listing_id ────────────────────────────────────────────
    elif action == "buy":
        lid = param
        if not in_hidden:
            await cb.answer(
                "❌ Must be in a hidden sector (10-59) to buy.",
                show_alert=True
            )
            return
        ok, msg, user = purchase_listing(user, lid, supabase, DB_TABLE)
        if ok:
            save_user(u_id, user)
        await cb.answer(msg[:200], show_alert=True)

    # ── market:cancel:listing_id ─────────────────────────────────────────
    elif action == "cancel":
        lid = param
        ok, msg, user = cancel_listing(user, lid)
        if ok:
            save_user(u_id, user)
        await cb.answer(msg[:200], show_alert=True)

    # ── market:need_hidden ────────────────────────────────────────────────
    elif action == "need_hidden":
        await cb.answer(
            "Teleport to any hidden sector (10-59) to buy or sell.\n"
            "Use !teleport [10-59] to get there.",
            show_alert=True
        )

    await cb.answer()


# ═══════════════════════════════════════════════════════════════════════════
#  PHASE 6 SCHEDULER TICK
# ═══════════════════════════════════════════════════════════════════════════

async def phase6_tick(bot, supabase, DB_TABLE_: str, group_chat_id: int):
    """
    Phase 6 background tick — runs every 5 minutes via scheduler.
    1. Check Sector War trigger conditions
    2. Check Sector War expiry and resolve
    3. Expire Commander's Echo items
    4. Check Chronicle publish schedule
    """

    # 1. Check war trigger
    try:
        from sector_war import check_war_trigger, declare_sector_war, get_active_war

        if not get_active_war():
            rs = supabase.table("sector_state").select(
                "sector_id, dominance"
            ).execute()
            sector_states = []
            for row in (rs.data or []):
                from supabase_db import safe_json
                ss = dict(row)
                ss["dominance"] = safe_json(ss.get("dominance"), default={})
                sector_states.append(ss)

            try:
                with open("alliances.json") as f:
                    all_alliances = json.load(f)
            except Exception:
                all_alliances = {}

            result = check_war_trigger(sector_states, all_alliances)
            if result:
                a_alliance, b_alliance, contested = result
                ok, announce, war = declare_sector_war(
                    a_alliance, b_alliance, contested, bot, supabase, DB_TABLE_
                )
                if ok and announce:
                    from notification_engine import broadcast_gamemaster
                    # Use war_declared key with alliance names
                    try:
                        await bot.send_message(
                            group_chat_id, announce, parse_mode="Markdown"
                        )
                    except Exception:
                        pass
                    print(f"[WAR] Sector War declared: {announce[:60]}")

    except Exception as e:
        print(f"[P6_TICK] War trigger error: {e}")

    # 2. Check war expiry
    try:
        from sector_war import get_active_war, resolve_war

        war = get_active_war()
        if war:
            from datetime import datetime
            exp = datetime.fromisoformat(war.get("expires_at", "2099-01-01"))
            if datetime.utcnow() > exp:
                try:
                    with open("alliances.json") as f:
                        all_alliances = json.load(f)
                except Exception:
                    all_alliances = {}

                def save_a(a):
                    aid = a.get("id")
                    if aid:
                        all_alliances[aid] = a
                        with open("alliances.json", "w") as f:
                            json.dump(all_alliances, f, indent=2)

                def broadcast(msg):
                    asyncio.create_task(
                        bot.send_message(group_chat_id, msg, parse_mode="Markdown")
                    )

                resolve_war(
                    supabase, DB_TABLE_, all_alliances, save_a, broadcast
                )
                print("[WAR] Sector War resolved")

    except Exception as e:
        print(f"[P6_TICK] War expiry error: {e}")

    # 3. Expire Commander's Echo
    try:
        from datetime import datetime
        r = supabase.table(DB_TABLE_).select(
            "user_id, echo_expires, echo_original_skills"
        ).not_.is_("echo_expires", "null").execute()

        for row in (r.data or []):
            uid = row.get("user_id")
            exp_str = row.get("echo_expires", "")
            if not exp_str:
                continue
            try:
                exp = datetime.fromisoformat(exp_str)
                if datetime.utcnow() >= exp:
                    from black_market import check_echo_expiry
                    from supabase_db import normalize_user
                    user = normalize_user(supabase.table(DB_TABLE_).select(
                        "*"
                    ).eq("user_id", uid).execute().data[0])
                    user = check_echo_expiry(user)
                    supabase.table(DB_TABLE_).update(user).eq("user_id", uid).execute()
            except Exception:
                pass

    except Exception as e:
        print(f"[P6_TICK] Echo expiry error: {e}")

    # 4. Chronicle publish check
    try:
        from chronicle import should_publish_now, publish_chronicle
        if should_publish_now():
            await publish_chronicle(bot, supabase, DB_TABLE_, group_chat_id)
            print("[CHRONICLE] Weekly Chronicle published")
    except Exception as e:
        print(f"[P6_TICK] Chronicle error: {e}")
