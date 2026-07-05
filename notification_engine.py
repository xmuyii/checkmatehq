# -*- coding: utf-8 -*-
"""
notification_engine.py — Gamemaster Notification System
=========================================================
Pushes DMs to players for every meaningful game event.
Players learn to recognise notification types by their emoji prefix.

PREFIXES (players learn these over time — explained only on first receipt):
  ⚡ Sector Alert      — phase change, predator spawn, node under attack
  🔬 Research/Build    — construction or research completed
  ⚔️ Combat Alert      — incoming march, battle result, bounty
  👑 Dominance         — ruler change, pretender, cycle result
  🌋 Hazard Warning    — suit expiring, about to be ejected
  📋 Alliance          — mission available, war declared, AP earned
  🎁 Daily Reward      — teleports, daily login, gifts ready
  📢 Gamemaster        — server-wide flavour announcements from bot persona
  🟢 Server            — back online, maintenance notices

GAMEMASTER PERSONA:
  The bot speaks as "The Commander" — a strategic AI running the world.
  Never robotic. Always flavour-rich. Reads like a war dispatch.
  Players should feel they are receiving actual orders from a real command.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict

# ── Notification type registry ────────────────────────────────────────────
NOTIFICATION_TYPES = {
    "sector_alert":      {"emoji": "⚡", "label": "Sector Alert"},
    "build_complete":    {"emoji": "🔬", "label": "Construction Complete"},
    "research_complete": {"emoji": "🔬", "label": "Research Complete"},
    "training_complete": {"emoji": "⚔️", "label": "Training Complete"},
    "combat_incoming":   {"emoji": "⚔️", "label": "Combat Alert"},
    "combat_result":     {"emoji": "⚔️", "label": "Battle Report"},
    "bounty":            {"emoji": "⚔️", "label": "Bounty Alert"},
    "dominance":         {"emoji": "👑", "label": "Dominance Event"},
    "hazard_warning":    {"emoji": "🌋", "label": "Hazard Warning"},
    "suit_expiring":     {"emoji": "🌋", "label": "Suit Warning"},
    "alliance_mission":  {"emoji": "📋", "label": "Alliance Mission"},
    "alliance_war":      {"emoji": "📋", "label": "War Alert"},
    "alliance_ap":       {"emoji": "📋", "label": "Alliance Points"},
    "daily_reward":      {"emoji": "🎁", "label": "Daily Reward"},
    "server_online":     {"emoji": "🟢", "label": "Server Status"},
    "server_maintenance":{"emoji": "🔴", "label": "Maintenance"},
    "gamemaster":        {"emoji": "📢", "label": "Gamemaster"},
    "priority_mission":  {"emoji": "🚨", "label": "Priority Order"},
}

# ── First-time explanation text (shown once per type, never again) ────────
FIRST_TIME_EXPLANATIONS = {
    "sector_alert":      "⚡ *Sector Alerts* notify you when something changes in your sector — phase shifts, predators, attacks.",
    "build_complete":    "🔬 *Construction alerts* fire when a building or research finishes. No need to check manually.",
    "research_complete": "🔬 *Research alerts* fire when a technology completes. Your unlocks are ready.",
    "training_complete": "⚔️ *Training alerts* tell you when your troops are ready to deploy.",
    "combat_incoming":   "⚔️ *Combat alerts* warn you when enemy troops are marching on your positions. Act fast.",
    "combat_result":     "⚔️ *Battle reports* summarise the outcome of every fight involving you.",
    "dominance":         "👑 *Dominance events* track your sector rulership — cycles, pretenders, throne changes.",
    "hazard_warning":    "🌋 *Hazard warnings* fire before a lethal sector phase hits. Your signal to suit up or teleport.",
    "suit_expiring":     "🌋 *Suit warnings* fire when your protective suit has 2 minutes or less remaining.",
    "alliance_mission":  "📋 *Alliance missions* are your daily objectives. Complete them to earn Alliance Points.",
    "priority_mission":  "🚨 *Priority Orders* come directly from the Commander. Time-sensitive. High reward.",
    "daily_reward":      "🎁 *Daily rewards* notify you when free teleports and login bonuses are ready to claim.",
    "gamemaster":        "📢 *Gamemaster broadcasts* are server-wide announcements from the Commander. Read them.",
}

# ── Gamemaster voice lines ────────────────────────────────────────────────
# Used for server-wide events. Indexed by event key.
GAMEMASTER_LINES = {
    # Sector phase events
    "void_collapse": [
        "💀 *VOID CANYON HAS FALLEN SILENT.* All commanders expelled. The canyon breathes again. It reopens in {time}.",
        "🌑 *Reality has collapsed in Void Canyon.* The rift closes. Survivors have been returned to their sectors.",
        "⚫ *The void consumed everything.* Commanders in Sector 9 have been scattered. The cycle resets in {time}.",
    ],
    "bull_run_start": [
        "📈 *BULL RUN IN THE CRYPTO WASTES.* Satoshi yields tripled for {time}. Get in before the rug drops.",
        "🐂 *The markets are surging.* Every node in the Crypto Wastes running hot. {time} window. Move.",
        "💹 *Numbers going up.* Everyone's getting rich in Sector 65. For now. {time} remaining.",
    ],
    "rug_pull": [
        "🚨 *RUG PULL IN THE CRYPTO WASTES.* Developers have pulled liquidity. Unprotected Satoshi converting to dust.",
        "📉 *The floor disappeared.* If you're unprotected in Sector 65 right now, your holdings are evaporating.",
        "💀 *They deleted the Discord.* The Crypto Wastes are experiencing a rug pull. Bitcoin Format required to survive.",
    ],
    "predator_spawn": [
        "👾 *{predator} spotted in Sector {sector}.* Node {node} is under occupation. Coordinate your response.",
        "🐉 *A {predator} has emerged in {sector}.* Multi-commander combat recommended. Loot distributed by damage.",
        "⚠️ *Hostile entity detected — {predator} at {node}, Sector {sector}.* All available commanders: respond.",
    ],
    "ruler_change": [
        "👑 *@{new_ruler} has seized control of {sector}.* The previous ruler has been deposed. A new era begins.",
        "🏆 *Throne change in {sector}.* @{new_ruler} now commands this territory. @{old_ruler} dethroned.",
        "⚔️ *The power balance shifts.* @{new_ruler} dominates {sector}. Challengers take note.",
    ],
    "war_declared": [
        "⚔️ *WAR DECLARED.* {alliance_a} has challenged {alliance_b}. Contested sector: {sector}. Duration: 24h.",
        "🚨 *ALL HANDS.* {alliance_a} vs {alliance_b}. The battle for {sector} begins now. Choose your side.",
        "💥 *Conflict initiated.* {alliance_a} and {alliance_b} are now at war over {sector}. Watch the sector feed.",
    ],
    "server_online": [
        "🟢 *Zero Dominus is back online.* Your base is safe. Your queues are running. Welcome back, Commander.",
        "🟢 *Systems restored.* The server is live. All active queues have been preserved. Resume operations.",
        "🟢 *We're back.* The Commander's systems are online. Your base survived the downtime intact.",
    ],
    "server_maintenance": [
        "🔴 *Zero Dominus entering maintenance.* We'll be back shortly. Your base is safe while we're down.",
        "🔴 *Server going offline for updates.* All queues paused and will resume on restart. Stand by.",
        "🔴 *Temporary shutdown initiated.* The Commander will return. Your progress is preserved.",
    ],
    "priority_mission_new": [
        "🚨 *PRIORITY ORDER ISSUED.* A time-sensitive mission is available for all alliance leaders. Check your alliance dashboard.",
        "📋 *The Commander has new orders.* Priority missions available now. High reward. Limited time.",
        "🎯 *Operational directive received.* Alliance leaders: check your mission board. Priority orders active.",
    ],
}

import random

def get_gamemaster_line(event_key: str, **kwargs) -> str:
    """Get a random Gamemaster voice line for an event, with variable substitution."""
    lines = GAMEMASTER_LINES.get(event_key, [f"📢 Event: {event_key}"])
    line  = random.choice(lines)
    try:
        return line.format(**kwargs)
    except KeyError:
        return line


# ═══════════════════════════════════════════════════════════════════════════
#  NOTIFICATION DELIVERY
# ═══════════════════════════════════════════════════════════════════════════

async def send_notification(
    bot,
    player_id: str,
    notification_type: str,
    message: str,
    supabase=None,
    DB_TABLE: str = "players",
    save_notification_seen: bool = True,
) -> bool:
    """
    Send a notification DM to a player.
    Prepends first-time explanation if this is the first of this type.
    Returns True if sent successfully.
    """
    try:
        # Build full message
        type_info    = NOTIFICATION_TYPES.get(notification_type, {"emoji": "📨", "label": "Alert"})
        emoji        = type_info["emoji"]
        label        = type_info["label"]

        full_message = f"{emoji} *{label}*\n{message}"

        # Check if this is first time for this type — add explanation
        if supabase and DB_TABLE:
            first_time = await _is_first_notification(supabase, DB_TABLE, player_id, notification_type)
            if first_time:
                explanation = FIRST_TIME_EXPLANATIONS.get(notification_type, "")
                if explanation:
                    full_message = f"{explanation}\n\n{full_message}"
                await _mark_notification_seen(supabase, DB_TABLE, player_id, notification_type)

        await bot.send_message(
            chat_id=int(player_id),
            text=full_message,
            parse_mode="Markdown"
        )
        return True

    except Exception as e:
        # Player may have blocked the bot — log silently
        print(f"[NOTIF] Failed to send {notification_type} to {player_id}: {e}")
        return False


async def broadcast_gamemaster(
    bot,
    event_key: str,
    supabase,
    DB_TABLE: str,
    active_hours: int = 24,
    **kwargs,
) -> int:
    """
    Send a Gamemaster announcement to all recently active players.
    active_hours: only send to players active within this window.
    Returns count of players reached.
    """
    message = get_gamemaster_line(event_key, **kwargs)
    sent    = 0

    try:
        cutoff = (datetime.utcnow() - timedelta(hours=active_hours)).isoformat()
        result = supabase.table(DB_TABLE).select(
            "user_id, last_active"
        ).gte("last_active", cutoff).execute()

        players = result.data or []

        for player in players:
            uid = player.get("user_id")
            if not uid:
                continue
            ok = await send_notification(
                bot, uid, "gamemaster", message,
                supabase, DB_TABLE, save_notification_seen=False
            )
            if ok:
                sent += 1
            await asyncio.sleep(0.05)  # Rate limit — 20 msgs/sec max

        print(f"[GAMEMASTER] Broadcast '{event_key}' to {sent}/{len(players)} players")

    except Exception as e:
        print(f"[GAMEMASTER] Broadcast error: {e}")

    return sent


async def broadcast_sector(
    bot,
    sector_id: int,
    notification_type: str,
    message: str,
    supabase,
    DB_TABLE: str,
    sector_state: dict,
) -> int:
    """
    Send a notification to all players currently in a specific sector.
    Used for phase warnings, predator spawns, jam alerts.
    """
    from sector_report import get_players_in_sector
    players = get_players_in_sector(sector_state)
    sent    = 0

    for pid in players:
        ok = await send_notification(bot, pid, notification_type, message, supabase, DB_TABLE)
        if ok:
            sent += 1
        await asyncio.sleep(0.03)

    return sent


async def notify_player(
    bot,
    player_id: str,
    notification_type: str,
    message: str,
    supabase=None,
    DB_TABLE: str = "players",
) -> bool:
    """Convenience wrapper — single player notification."""
    return await send_notification(bot, player_id, notification_type, message, supabase, DB_TABLE)


# ── Specific notification builders ───────────────────────────────────────

async def notify_build_complete(bot, player_id: str, building_name: str, level: int,
                                 supabase=None, DB_TABLE="players"):
    msg = (f"*{building_name}* has reached Level {level}.\n"
           f"Your base grows stronger. Check My Base for full details.")
    return await notify_player(bot, player_id, "build_complete", msg, supabase, DB_TABLE)


async def notify_research_complete(bot, player_id: str, research_name: str, unlocks: list,
                                    supabase=None, DB_TABLE="players"):
    unlocks_str = "\n".join(f"  • {u.replace('_',' ').title()}" for u in unlocks[:5])
    msg = (f"*{research_name}* complete.\n"
           f"New capabilities unlocked:\n{unlocks_str}")
    return await notify_player(bot, player_id, "research_complete", msg, supabase, DB_TABLE)


async def notify_training_complete(bot, player_id: str, unit_name: str, count: int,
                                    supabase=None, DB_TABLE="players"):
    msg = (f"*{count}× {unit_name}* ready for deployment.\n"
           f"Your army grows. Open Military to deploy them.")
    return await notify_player(bot, player_id, "training_complete", msg, supabase, DB_TABLE)


async def notify_incoming_march(bot, defender_id: str, attacker_name: str,
                                 node_name: str, arrival_mins: int,
                                 supabase=None, DB_TABLE="players"):
    msg = (f"@{attacker_name} is marching on *{node_name}*.\n"
           f"Arrival in: *{arrival_mins} minutes*\n"
           f"Collect your resources and prepare — or teleport out.")
    return await notify_player(bot, defender_id, "combat_incoming", msg, supabase, DB_TABLE)


async def notify_battle_result(bot, player_id: str, attacker_name: str, defender_name: str,
                                won: bool, node_name: str, looted: dict,
                                supabase=None, DB_TABLE="players"):
    if won:
        loot_str = " ".join(f"+{v} {k}" for k, v in looted.items()) if looted else "no resources"
        msg = (f"Victory at *{node_name}*.\n"
               f"@{defender_name} repelled. Loot: {loot_str}")
    else:
        msg = (f"Defeat at *{node_name}*.\n"
               f"@{attacker_name} held their position. Review your power before next assault.")
    return await notify_player(bot, player_id, "combat_result", msg, supabase, DB_TABLE)


async def notify_hazard_warning(bot, player_id: str, sector_name: str,
                                 hazard_type: str, minutes: int,
                                 supabase=None, DB_TABLE="players"):
    msg = (f"*{sector_name}* entering hazard phase in *{minutes} minutes*.\n"
           f"Hazard: {hazard_type.replace('_',' ').title()}\n"
           f"Equip protective suit or teleport before phase begins.")
    return await notify_player(bot, player_id, "hazard_warning", msg, supabase, DB_TABLE)


async def notify_suit_expiring(bot, player_id: str, suit_name: str, seconds: int,
                                supabase=None, DB_TABLE="players"):
    mins = seconds // 60
    secs = seconds % 60
    msg = (f"*{suit_name}* expires in *{mins}m {secs}s*.\n"
           f"Equip a replacement or teleport to safety now.")
    return await notify_player(bot, player_id, "suit_expiring", msg, supabase, DB_TABLE)


async def notify_dominance_ruler(bot, player_id: str, sector_name: str, score: int,
                                  supabase=None, DB_TABLE="players"):
    msg = (f"You are now the *Ruler of {sector_name}*.\n"
           f"Cycle Score: {score}\n"
           f"You now earn 10% tax on all resources collected in this sector.\n"
           f"Manage your sector from the Ruler Panel.")
    return await notify_player(bot, player_id, "dominance", msg, supabase, DB_TABLE)


async def notify_daily_rewards_ready(bot, player_id: str, teleport_count: int,
                                      supabase=None, DB_TABLE="players"):
    msg = (f"*{teleport_count} free teleport charges* are ready to claim.\n"
           f"Daily login bonus also available.\n"
           f"Unclaimed charges expire at midnight UTC.")
    return await notify_player(bot, player_id, "daily_reward", msg, supabase, DB_TABLE)


async def notify_alliance_mission_available(bot, player_id: str, alliance_name: str,
                                             mission_count: int,
                                             supabase=None, DB_TABLE="players"):
    msg = (f"*{alliance_name}* has {mission_count} active mission(s) ready.\n"
           f"Complete them to earn Alliance Points for your alliance.\n"
           f"Open Alliance → Missions to see your assignments.")
    return await notify_player(bot, player_id, "alliance_mission", msg, supabase, DB_TABLE)


async def notify_priority_mission(bot, player_id: str, mission_name: str,
                                   reward_summary: str, time_limit_hours: int,
                                   supabase=None, DB_TABLE="players"):
    msg = (f"*PRIORITY ORDER: {mission_name}*\n"
           f"Time limit: {time_limit_hours}h\n"
           f"Reward: {reward_summary}\n"
           f"Open Alliance → Priority Missions immediately.")
    return await notify_player(bot, player_id, "priority_mission", msg, supabase, DB_TABLE)


async def notify_server_online(bot, player_id: str, supabase=None, DB_TABLE="players"):
    msg = get_gamemaster_line("server_online")
    return await notify_player(bot, player_id, "server_online", msg, supabase, DB_TABLE)


# ═══════════════════════════════════════════════════════════════════════════
#  NOTIFICATION PREFERENCE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

DEFAULT_PREFERENCES = {
    "sector_alert":      True,
    "build_complete":    True,
    "research_complete": True,
    "training_complete": True,
    "combat_incoming":   True,
    "combat_result":     True,
    "bounty":            True,
    "dominance":         True,
    "hazard_warning":    True,
    "suit_expiring":     True,
    "alliance_mission":  True,
    "alliance_war":      True,
    "daily_reward":      True,
    "gamemaster":        True,
    "priority_mission":  True,
}


def get_notification_preferences(user: dict) -> dict:
    """Get player's notification preferences, filling defaults."""
    prefs = user.get("notification_prefs", {})
    if not isinstance(prefs, dict):
        prefs = {}
    return {**DEFAULT_PREFERENCES, **prefs}


def is_notification_enabled(user: dict, notification_type: str) -> bool:
    """Check if a player has a notification type enabled."""
    prefs = get_notification_preferences(user)
    return prefs.get(notification_type, True)


def set_notification_preference(user: dict, notification_type: str, enabled: bool) -> dict:
    """Update a single notification preference."""
    prefs = get_notification_preferences(user)
    prefs[notification_type] = enabled
    user["notification_prefs"] = prefs
    return user


def format_notification_settings(user: dict) -> str:
    """Format notification preferences for display."""
    prefs  = get_notification_preferences(user)
    lines  = ["🔔 *NOTIFICATION SETTINGS*\n━━━━━━━━━━━━━━━━━━━━━━━━"]

    for ntype, info in NOTIFICATION_TYPES.items():
        if ntype in ("server_online", "server_maintenance"):
            continue  # Always on — not configurable
        emoji   = info["emoji"]
        label   = info["label"]
        enabled = prefs.get(ntype, True)
        status  = "✅" if enabled else "❌"
        lines.append(f"  {status} {emoji} {label}")

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("Toggle: tap button below or `!notify [type] on/off`")
    return "\n".join(lines)


def kb_notification_settings(user: dict):
    """Inline keyboard for notification settings."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    prefs   = get_notification_preferences(user)
    buttons = []

    toggleable = [
        ("sector_alert", "⚡ Sector"),
        ("build_complete", "🔬 Build"),
        ("combat_incoming", "⚔️ Combat"),
        ("hazard_warning", "🌋 Hazard"),
        ("alliance_mission", "📋 Alliance"),
        ("daily_reward", "🎁 Daily"),
        ("gamemaster", "📢 Gamemaster"),
        ("priority_mission", "🚨 Priority"),
    ]

    row = []
    for ntype, label in toggleable:
        enabled = prefs.get(ntype, True)
        icon    = "✅" if enabled else "❌"
        row.append(InlineKeyboardButton(
            text=f"{icon} {label}",
            callback_data=f"notif_toggle:{ntype}"
        ))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([InlineKeyboardButton(
        text="✅ Enable All", callback_data="notif_all_on"
    ), InlineKeyboardButton(
        text="❌ Disable All", callback_data="notif_all_off"
    )])
    buttons.append([InlineKeyboardButton(text="⬅️ Back", callback_data="menu_account")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ═══════════════════════════════════════════════════════════════════════════
#  INTERNAL HELPERS
# ═══════════════════════════════════════════════════════════════════════════

async def _is_first_notification(supabase, DB_TABLE: str,
                                   player_id: str, notification_type: str) -> bool:
    """Check if this is the first time a player receives this notification type."""
    try:
        result = supabase.table(DB_TABLE).select(
            "notifications_seen"
        ).eq("user_id", player_id).execute()
        if not result.data:
            return True
        seen = result.data[0].get("notifications_seen") or {}
        if isinstance(seen, str):
            import json
            try:
                seen = json.loads(seen)
            except Exception:
                seen = {}
        return notification_type not in seen
    except Exception:
        return False


async def _mark_notification_seen(supabase, DB_TABLE: str,
                                    player_id: str, notification_type: str):
    """Record that a player has seen a notification type for the first time."""
    try:
        result = supabase.table(DB_TABLE).select(
            "notifications_seen"
        ).eq("user_id", player_id).execute()
        seen = {}
        if result.data:
            raw = result.data[0].get("notifications_seen") or {}
            if isinstance(raw, str):
                import json
                try:
                    raw = json.loads(raw)
                except Exception:
                    raw = {}
            seen = raw if isinstance(raw, dict) else {}

        seen[notification_type] = datetime.utcnow().isoformat()
        supabase.table(DB_TABLE).update({
            "notifications_seen": seen
        }).eq("user_id", player_id).execute()
    except Exception:
        pass


def update_last_active(supabase, DB_TABLE: str, player_id: str):
    """Update last_active timestamp for a player. Call on every user action."""
    try:
        supabase.table(DB_TABLE).update({
            "last_active": datetime.utcnow().isoformat()
        }).eq("user_id", player_id).execute()
    except Exception:
        pass