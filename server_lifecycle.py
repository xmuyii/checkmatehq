# -*- coding: utf-8 -*-
"""
server_lifecycle.py — Server Up/Down Lifecycle Management
==========================================================
Handles bot startup and shutdown gracefully.

ON STARTUP:
  1. Sends "back online" notification to all recently active players
  2. Resumes any queues that were interrupted
  3. Updates server_status flag in DB

ON SHUTDOWN (graceful):
  1. Sets server_status = "maintenance" in DB
  2. Players who message during downtime get a maintenance screen

MAINTENANCE SCREEN:
  When maintenance_mode = True in bot state,
  every /start and callback returns a maintenance card
  instead of normal content.

HOW TO WIRE INTO main.py:
  

  # In your main() function, before dp.start_polling:

  # Register shutdown:

  # In cmd_start, at the very top before anything else:
  
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Key used to store server status in a dedicated table or user meta
SERVER_STATUS_KEY = "server_status"
MAINTENANCE_TABLE = "server_meta"

# How recent a player must be to receive the back-online notification
NOTIFY_ACTIVE_WITHIN_HOURS = 48


# ═══════════════════════════════════════════════════════════════════════════
#  STARTUP
# ═══════════════════════════════════════════════════════════════════════════

async def on_startup(bot, supabase, DB_TABLE: str):
    """
    Called once when the bot connects to Telegram polling.
    Sends back-online DMs, resumes interrupted queues.
    """
    print("[LIFECYCLE] Bot startup sequence starting...")

    # 1. Mark server as online
    await _set_server_status(supabase, "online")

    # 2. Small delay — let the bot fully connect before broadcasting
    await asyncio.sleep(3)

    # 3. Send back-online notification to recently active players
    sent = await _broadcast_back_online(bot, supabase, DB_TABLE)
    print(f"[LIFECYCLE] Back-online notification sent to {sent} players")

    # 4. Resume any building/training/research queues that were mid-progress
    # Queues are time-based so they self-correct on next user load
    # Just log so operators know
    print("[LIFECYCLE] Queue timers are time-based — self-correcting on next player load")
    print("[LIFECYCLE] Startup complete ✅")


async def on_shutdown(bot, supabase, DB_TABLE: str):
    """
    Called when the bot is gracefully shutting down (Railway redeploy).
    Attempts to notify active players before going offline.
    """
    print("[LIFECYCLE] Shutdown sequence starting...")

    # 1. Mark server as maintenance
    await _set_server_status(supabase, "maintenance")

    # 2. Try to send maintenance warnings to very recently active players
    # Only last 2 hours — don't spam everyone
    try:
        cutoff = (datetime.utcnow() - timedelta(hours=2)).isoformat()
        result = supabase.table(DB_TABLE).select(
            "user_id"
        ).gte("last_active", cutoff).execute()
        players = result.data or []

        from notification_engine import get_gamemaster_line
        msg = get_gamemaster_line("server_maintenance")

        sent = 0
        for player in players[:50]:  # Cap at 50 — shutdown is time-limited
            uid = player.get("user_id")
            if not uid:
                continue
            try:
                await bot.send_message(
                    int(uid), msg, parse_mode="Markdown"
                )
                sent += 1
            except Exception:
                pass
            await asyncio.sleep(0.05)

        print(f"[LIFECYCLE] Maintenance notice sent to {sent} players")
    except Exception as e:
        print(f"[LIFECYCLE] Shutdown notification error: {e}")

    print("[LIFECYCLE] Shutdown complete")


# ═══════════════════════════════════════════════════════════════════════════
#  MAINTENANCE MODE CHECK
# ═══════════════════════════════════════════════════════════════════════════

# In-memory cache — avoids DB hit on every message during normal operation
_maintenance_cache: dict = {"status": "online", "checked_at": None}
_CACHE_TTL_SECONDS = 30


async def check_maintenance_mode(supabase) -> bool:
    """
    Returns True if the server is in maintenance mode.
    Cached for 30 seconds to avoid DB hammering.
    """
    global _maintenance_cache
    now = datetime.utcnow()

    # Use cache if fresh
    if (_maintenance_cache["checked_at"] and
            (now - _maintenance_cache["checked_at"]).total_seconds() < _CACHE_TTL_SECONDS):
        return _maintenance_cache["status"] == "maintenance"

    # Refresh from DB
    try:
        result = supabase.table(MAINTENANCE_TABLE).select(
            "value"
        ).eq("key", SERVER_STATUS_KEY).execute()

        if result.data:
            status = result.data[0].get("value", "online")
        else:
            status = "online"

        _maintenance_cache = {"status": status, "checked_at": now}
        return status == "maintenance"
    except Exception:
        # If DB unreachable, assume online (fail open)
        return False


async def maintenance_response(message_or_callback, is_callback: bool = False):
    """
    Send the maintenance screen to a player who messaged during downtime.
    Works for both Message and CallbackQuery.
    """
    text = (
        "🔴 *Zero Dominus — Maintenance*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "The Commander's systems are undergoing maintenance.\n\n"
        "⏱️ *Expected downtime:* A few minutes\n"
        "🏰 *Your base:* Safe and preserved\n"
        "⚙️ *Your queues:* Paused and will resume\n\n"
        "_You will receive a notification the moment we're back online._\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔄 Try Again", callback_data="menu_back")
    ]])

    try:
        if is_callback:
            await message_or_callback.message.edit_text(
                text, parse_mode="Markdown", reply_markup=kb
            )
        else:
            await message_or_callback.answer(text, parse_mode="Markdown", reply_markup=kb)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════
#  BACK-ONLINE BROADCAST
# ═══════════════════════════════════════════════════════════════════════════

async def _broadcast_back_online(bot, supabase, DB_TABLE: str) -> int:
    """
    Send "back online" DM to all players active in last NOTIFY_ACTIVE_WITHIN_HOURS.
    """
    from notification_engine import notify_server_online

    try:
        cutoff = (
            datetime.utcnow() - timedelta(hours=NOTIFY_ACTIVE_WITHIN_HOURS)
        ).isoformat()

        result = supabase.table(DB_TABLE).select(
            "user_id"
        ).gte("last_active", cutoff).execute()

        players = result.data or []
        sent    = 0

        for player in players:
            uid = player.get("user_id")
            if not uid:
                continue
            ok = await notify_server_online(bot, uid, supabase, DB_TABLE)
            if ok:
                sent += 1
            await asyncio.sleep(0.05)  # 20/sec rate limit

        return sent

    except Exception as e:
        print(f"[LIFECYCLE] Back-online broadcast error: {e}")
        return 0


async def _set_server_status(supabase, status: str):
    """Write server status to the server_meta table."""
    try:
        supabase.table(MAINTENANCE_TABLE).upsert({
            "key":        SERVER_STATUS_KEY,
            "value":      status,
            "updated_at": datetime.utcnow().isoformat(),
        }).execute()
    except Exception as e:
        print(f"[LIFECYCLE] Could not set server status: {e}")


# ═══════════════════════════════════════════════════════════════════════════
#  SQL TO RUN IN SUPABASE — server_meta table
# ═══════════════════════════════════════════════════════════════════════════

SERVER_META_SQL = """
-- Run this once in Supabase SQL Editor


"""

# ═══════════════════════════════════════════════════════════════════════════
#  HOW TO ADD TO main.py — exact code to paste
# ═══════════════════════════════════════════════════════════════════════════

MAIN_PY_PATCH = '''
# ── PASTE 1: Add to imports at top of main.py ─────────────────────────

# ── PASTE 2: Add to cmd_start, at the very top of the private chat block ──
# (after "if message.chat.type != 'private': return")
if await check_maintenance_mode(supabase):
    await maintenance_response(message)
    return

# ── PASTE 3: Add to every callback handler, at top after getting user ──
# (add a helper so you don't repeat this everywhere)
async def _check_maintenance(callback):
    """Returns True if in maintenance — handler should return early."""
    if await check_maintenance_mode(supabase):
        await maintenance_response(callback, is_callback=True)
        return True
    return False

# ── PASTE 4: In your main() async function, before dp.start_polling ───
asyncio.create_task(on_startup(bot, supabase, DB_TABLE))
dp.shutdown.register(lambda: asyncio.create_task(
    on_shutdown(bot, supabase, DB_TABLE)
))
'''