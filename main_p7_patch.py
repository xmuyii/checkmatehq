# -*- coding: utf-8 -*-
"""
main_p7_patch.py — Phase 7 Callbacks & Main.py Fix Instructions
================================================================
Handles: prestige:*, treasury:*, and the main.py double-edit bug fix.

HOW TO WIRE INTO main.py:
  from main_p7_patch import p7_router
  dp.include_router(p7_router)

  Also add ALL phase routers at once — paste this block after line 454
  (after dp.include_router(base_router)):

    from store_system    import store_router
    from main_p5_patch   import p5_router
    from main_p6_patch   import p6_router
    from main_p7_patch   import p7_router
    dp.include_router(store_router)
    dp.include_router(p5_router)
    dp.include_router(p6_router)
    dp.include_router(p7_router)

  And in the main() function before dp.start_polling:
    from server_lifecycle import on_startup, on_shutdown
    asyncio.create_task(on_startup(bot, supabase, "players"))
    dp.shutdown.register(lambda: asyncio.create_task(
        on_shutdown(bot, supabase, "players")
    ))

  And add wiring hooks to cmd_start and every callback:
    from wiring_hooks import on_user_action
    on_user_action(u_id, supabase)

DB_TABLE = "players" throughout.
"""

import json
from datetime import datetime
from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

p7_router = Router()
DB_TABLE  = "players"


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


# ═══════════════════════════════════════════════════════════════════════════
#  PRESTIGE CALLBACKS  (prestige:*)
# ═══════════════════════════════════════════════════════════════════════════

@p7_router.callback_query(F.data.startswith("prestige:"))
async def handle_prestige(cb: types.CallbackQuery):
    get_user, save_user, supabase = _db()
    u_id = str(cb.from_user.id)
    user = get_user(u_id)
    if not user:
        await cb.answer("Please /start first.", show_alert=True)
        return

    from wiring_hooks import on_user_action
    on_user_action(u_id, supabase, DB_TABLE)

    from prestige_system import (
        can_prestige, execute_prestige, get_prestige_tier,
        format_prestige_status, format_prestige_confirm,
        kb_prestige_status, kb_prestige_confirm,
    )

    parts  = cb.data.split(":")
    action = parts[1] if len(parts) > 1 else "status"

    if action == "status":
        text = format_prestige_status(user)
        kb   = kb_prestige_status(user)
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    elif action == "confirm":
        level    = user.get("level", 1)
        prestige = get_prestige_tier(user)
        can, msg = can_prestige(level, prestige)
        if not can:
            await cb.answer(msg[:200], show_alert=True)
            return
        text = format_prestige_confirm(user)
        kb   = kb_prestige_confirm()
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    elif action == "execute":
        level    = user.get("level", 1)
        prestige = get_prestige_tier(user)
        can, msg = can_prestige(level, prestige)
        if not can:
            await cb.answer(msg[:200], show_alert=True)
            return

        old_tier = prestige
        user     = execute_prestige(user)
        save_user(u_id, user)

        new_tier  = get_prestige_tier(user)
        from prestige_system import PRESTIGE_BONUSES
        bonus     = PRESTIGE_BONUSES[new_tier]

        # Server-wide notification
        try:
            from wiring_hooks import on_prestige
            from initiation import CHECKMATE_HQ_GROUP_ID
            await on_prestige(cb.bot, user, new_tier, supabase, DB_TABLE, CHECKMATE_HQ_GROUP_ID)
        except Exception:
            pass

        text = (
            f"👑 *PRESTIGE {new_tier} ACHIEVED!*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{bonus['emoji']} *{bonus['name']}*\n\n"
            f"Power multiplier: ×{bonus['multiplier']}\n"
            f"Gold reward: +{bonus['gold_reward']:,} 🪙\n\n"
            f"_{bonus['description']}_\n\n"
            f"You have been reset to Level 1.\n"
            f"The server knows what you've done."
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("⚡ View Power",   callback_data="base:power")],
            [InlineKeyboardButton("🏠 Dashboard",    callback_data="menu_back")],
        ])
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    await cb.answer()


# ═══════════════════════════════════════════════════════════════════════════
#  TREASURY CALLBACKS  (treasury:*)
# ═══════════════════════════════════════════════════════════════════════════

@p7_router.callback_query(F.data.startswith("treasury:"))
async def handle_treasury(cb: types.CallbackQuery):
    get_user, save_user, supabase = _db()
    u_id     = str(cb.from_user.id)
    user     = get_user(u_id)
    if not user:
        await cb.answer("Please /start first.", show_alert=True)
        return

    on_user_action_safe(u_id, supabase)

    alliance = _load_alliance(user)
    if not alliance:
        await cb.answer("❌ You need to be in an alliance.", show_alert=True)
        return

    from alliance_treasury import (
        format_treasury, format_alliance_shop,
        deposit_gold, deposit_resources, spend_treasury,
        buy_from_alliance_shop, kb_treasury, kb_spend_menu,
        kb_alliance_shop, TREASURY_SPEND_OPTIONS,
    )

    parts  = cb.data.split(":")
    action = parts[1] if len(parts) > 1 else ""
    param  = parts[2] if len(parts) > 2 else ""
    is_leader = user.get("alliance_role") in ("LEADER", "OFFICER")

    # ── treasury:view ─────────────────────────────────────────────────────
    if action == "view":
        text = format_treasury(alliance, is_leader)
        kb   = kb_treasury(alliance, user)
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    # ── treasury:deposit_gold ─────────────────────────────────────────────
    elif action == "deposit_gold":
        inv  = user.get("inventory", []) or []
        gold = next((i.get("qty", 0) for i in inv if i.get("key") == "gold"), 0)    
        amounts = [50, 100, 250, 500, 1000]
        buttons = []
        row     = []
        for amt in amounts:
            if gold >= amt:
                row.append(InlineKeyboardButton(
                    text=f"{amt}🪙",
                    callback_data=f"treasury:deposit_gold_confirm:{amt}"
                ))
                if len(row) == 3:
                    buttons.append(row)
                    row = []
        if row:
            buttons.append(row)
        if not buttons:
            await cb.answer(f"❌ Not enough gold. You have {gold} 🪙.", show_alert=True)
            return
        buttons.append([InlineKeyboardButton("✗ Cancel", callback_data="treasury:view")])
        try:
            await cb.message.edit_text(
                f"💰 *Deposit Gold to Treasury*\nYou have: {gold} 🪙",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
                parse_mode="Markdown"
            )
        except Exception:
            pass

    # ── treasury:deposit_gold_confirm:amount ──────────────────────────────
    elif action == "deposit_gold_confirm":
        try:
            amount = int(param)
        except ValueError:
            await cb.answer("Invalid amount.", show_alert=True)
            return
        ok, msg, user, alliance = deposit_gold(alliance, user, amount)
        if ok:
            save_user(u_id, user)
            _save_alliance(alliance)
        await cb.answer(msg[:200], show_alert=True)
        if ok:
            text = format_treasury(alliance, is_leader)
            kb   = kb_treasury(alliance, user)
            try:
                await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
            except Exception:
                pass

    # ── treasury:deposit_res ──────────────────────────────────────────────
    elif action == "deposit_res":
        base_res  = user.get("base_resources", {}) or {}
        resources = base_res.get("resources", {}) or {}
        have      = {k: v for k, v in resources.items() if v > 0}
        if not have:
            await cb.answer("No resources to deposit.", show_alert=True)
            return
        buttons = []
        for rkey, qty in list(have.items())[:6]:
            donate = max(1, qty // 4)
            buttons.append([InlineKeyboardButton(
                text=f"Donate {donate} {rkey} (have {qty})",
                callback_data=f"treasury:donate_res:{rkey}:{donate}"
            )])
        buttons.append([InlineKeyboardButton("✗ Cancel", callback_data="treasury:view")])
        try:
            await cb.message.edit_text(
                "📦 *Donate Resources to Treasury:*",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
                parse_mode="Markdown"
            )
        except Exception:
            pass

    # ── treasury:donate_res:iron:100 ──────────────────────────────────────
    elif action == "donate_res":
        rkey   = param
        amount = int(parts[3]) if len(parts) > 3 else 0
        ok, msg, user, alliance = deposit_resources(alliance, user, rkey, amount)
        if ok:
            save_user(u_id, user)
            _save_alliance(alliance)
        await cb.answer(msg[:200], show_alert=True)

    # ── treasury:spend_menu ───────────────────────────────────────────────
    elif action == "spend_menu":
        if not is_leader:
            await cb.answer("Leaders only.", show_alert=True)
            return
        from alliance_treasury import get_treasury
        treasury = get_treasury(alliance)
        text = (
            f"💸 *TREASURY SPENDING*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Available: {treasury.get('gold',0):,} 🪙\n"
            f"AP: {alliance.get('alliance_points',0):,}\n\n"
            f"Select an action:"
        )
        kb = kb_spend_menu()
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    # ── treasury:spend:war_bonus ──────────────────────────────────────────
    elif action == "spend":
        if not is_leader:
            await cb.answer("Leaders only.", show_alert=True)
            return
        spend_key = param
        ok, msg, alliance = spend_treasury(
            alliance, user, spend_key, supabase, DB_TABLE, cb.bot
        )
        if ok:
            _save_alliance(alliance)
        await cb.answer(msg[:200], show_alert=True)
        if ok:
            text = format_treasury(alliance, is_leader)
            kb   = kb_treasury(alliance, user)
            try:
                await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
            except Exception:
                pass

    # ── treasury:shop ─────────────────────────────────────────────────────
    elif action == "shop":
        text = format_alliance_shop(alliance)
        kb   = kb_alliance_shop(alliance)
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    # ── treasury:buy:item_key ─────────────────────────────────────────────
    elif action == "buy":
        item_key = param
        ok, msg, user, alliance = buy_from_alliance_shop(alliance, user, item_key)
        if ok:
            save_user(u_id, user)
            _save_alliance(alliance)
        await cb.answer(msg[:200], show_alert=True)

    await cb.answer()


# ═══════════════════════════════════════════════════════════════════════════
#  NOTIFICATION SETTINGS (routed here since p5 handles notif_toggle)
#  Add to menu_account keyboard
# ═══════════════════════════════════════════════════════════════════════════

@p7_router.callback_query(F.data == "account:notifications")
async def handle_account_notif(cb: types.CallbackQuery):
    get_user, save_user, supabase = _db()
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
#  SAFE HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def on_user_action_safe(user_id: str, supabase, DB_TABLE_: str = "players"):
    """Non-crashing wrapper for on_user_action."""
    try:
        from wiring_hooks import on_user_action
        on_user_action(str(user_id), supabase, DB_TABLE_)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════
#  SQL MIGRATION — run in Supabase SQL Editor before deploying Phase 7
# ═══════════════════════════════════════════════════════════════════════════

PHASE_7_SQL = """
-- Phase 7 SQL — run in Supabase SQL Editor
-- Safe to run multiple times (IF NOT EXISTS / DO NOTHING guards)

-- Training queue column (fixes Railway restart data loss)
ALTER TABLE players ADD COLUMN IF NOT EXISTS training_queue      jsonb   DEFAULT '[]'::jsonb;

-- Prestige columns
ALTER TABLE players ADD COLUMN IF NOT EXISTS prestige            integer DEFAULT 0;
ALTER TABLE players ADD COLUMN IF NOT EXISTS prestige_multiplier float   DEFAULT 1.0;
ALTER TABLE players ADD COLUMN IF NOT EXISTS prestige_title      text    DEFAULT NULL;
ALTER TABLE players ADD COLUMN IF NOT EXISTS prestige_emoji      text    DEFAULT NULL;
ALTER TABLE players ADD COLUMN IF NOT EXISTS prestige_date       text    DEFAULT NULL;
ALTER TABLE players ADD COLUMN IF NOT EXISTS prestige_history    jsonb   DEFAULT '[]'::jsonb;
ALTER TABLE players ADD COLUMN IF NOT EXISTS prestige_bonus_teleport boolean DEFAULT false;

-- Black market / echo columns (Phase 6)
ALTER TABLE players ADD COLUMN IF NOT EXISTS ghost_cloak_expires   text  DEFAULT NULL;
ALTER TABLE players ADD COLUMN IF NOT EXISTS scammer_active_expires text  DEFAULT NULL;
ALTER TABLE players ADD COLUMN IF NOT EXISTS echo_expires          text  DEFAULT NULL;
ALTER TABLE players ADD COLUMN IF NOT EXISTS echo_original_skills  jsonb DEFAULT '{}'::jsonb;
ALTER TABLE players ADD COLUMN IF NOT EXISTS board_removal_expires text  DEFAULT NULL;

-- Bounty hunter columns (Phase 6)
ALTER TABLE players ADD COLUMN IF NOT EXISTS is_bounty_hunter    boolean DEFAULT false;
ALTER TABLE players ADD COLUMN IF NOT EXISTS hunter_xp           integer DEFAULT 0;
ALTER TABLE players ADD COLUMN IF NOT EXISTS hunter_tier         integer DEFAULT 0;
ALTER TABLE players ADD COLUMN IF NOT EXISTS hunter_kills        integer DEFAULT 0;
ALTER TABLE players ADD COLUMN IF NOT EXISTS hunter_earnings     integer DEFAULT 0;
ALTER TABLE players ADD COLUMN IF NOT EXISTS hunter_activated_at text    DEFAULT NULL;
ALTER TABLE players ADD COLUMN IF NOT EXISTS hunter_free_teleport_used_date text DEFAULT NULL;

-- Crafting columns (Phase 6)
ALTER TABLE players ADD COLUMN IF NOT EXISTS craft_queue         jsonb   DEFAULT '[]'::jsonb;
ALTER TABLE players ADD COLUMN IF NOT EXISTS discovered_recipes  jsonb   DEFAULT '[]'::jsonb;

-- Notification columns (Phase 5)
ALTER TABLE players ADD COLUMN IF NOT EXISTS last_active         text    DEFAULT NULL;
ALTER TABLE players ADD COLUMN IF NOT EXISTS notifications_seen  jsonb   DEFAULT '{}'::jsonb;
ALTER TABLE players ADD COLUMN IF NOT EXISTS notification_prefs  jsonb   DEFAULT '{}'::jsonb;

-- Credits column (from supabase_db_additions)
ALTER TABLE players ADD COLUMN IF NOT EXISTS credits             integer DEFAULT 0;
ALTER TABLE players ADD COLUMN IF NOT EXISTS last_daily_credit_claim text DEFAULT NULL;

-- Private sector / settlement columns
ALTER TABLE players ADD COLUMN IF NOT EXISTS teleport_charges              integer DEFAULT 0;
ALTER TABLE players ADD COLUMN IF NOT EXISTS teleport_daily_claimed_date   text    DEFAULT NULL;
ALTER TABLE players ADD COLUMN IF NOT EXISTS home_sector                   integer DEFAULT NULL;

-- sector_state: add private_sector column if not present
ALTER TABLE sector_state ADD COLUMN IF NOT EXISTS private_sector jsonb DEFAULT '{}'::jsonb;
ALTER TABLE sector_state ADD COLUMN IF NOT EXISTS event_log      jsonb DEFAULT '[]'::jsonb;
ALTER TABLE sector_state ADD COLUMN IF NOT EXISTS warnings_sent  jsonb DEFAULT '{}'::jsonb;

-- Bounty board table (Phase 3 / Phase 6)
CREATE TABLE IF NOT EXISTS bounty_board (
    bounty_id        text PRIMARY KEY,
    target_id        text NOT NULL,
    target_name      text NOT NULL,
    target_home_sector integer DEFAULT NULL,
    posted_by_id     text NOT NULL,
    posted_by_name   text NOT NULL,
    reward_gold      integer DEFAULT 0,
    reason           text DEFAULT 'open bounty',
    rank             text DEFAULT 'C',
    posted_at        text NOT NULL,
    expires_at       text NOT NULL,
    claimed_by_id    text DEFAULT NULL,
    claimed_by_name  text DEFAULT NULL,
    claimed_at       text DEFAULT NULL,
    status           text DEFAULT 'active'
);

-- Server meta table (Phase 5)
CREATE TABLE IF NOT EXISTS server_meta (
    key        text PRIMARY KEY,
    value      text NOT NULL DEFAULT 'online',
    updated_at text
);
INSERT INTO server_meta (key, value)
VALUES ('server_status', 'online')
ON CONFLICT (key) DO NOTHING;

-- Fix any NULL jsonb columns
UPDATE players SET training_queue     = '[]'::jsonb WHERE training_queue IS NULL;
UPDATE players SET craft_queue        = '[]'::jsonb WHERE craft_queue IS NULL;
UPDATE players SET discovered_recipes = '[]'::jsonb WHERE discovered_recipes IS NULL;
UPDATE players SET notifications_seen = '{}'::jsonb WHERE notifications_seen IS NULL;
UPDATE players SET notification_prefs = '{}'::jsonb WHERE notification_prefs IS NULL;
UPDATE players SET prestige_history   = '[]'::jsonb WHERE prestige_history IS NULL;
UPDATE players SET credits            = 0           WHERE credits IS NULL;
UPDATE players SET prestige           = 0           WHERE prestige IS NULL;
UPDATE players SET teleport_charges   = 0           WHERE teleport_charges IS NULL;
"""
