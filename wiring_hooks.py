# -*- coding: utf-8 -*-
"""
wiring_hooks.py — System Integration Hooks
============================================
Every system built in Phases 1-6 has functions that should be called
when specific events happen. None of those calls existed in main.py.
This file centralises them all.

HOW TO USE:
  Import the relevant hook at the top of the handler that triggers it.
  Each hook is a single async function call — add one line per trigger.

  Example — after build completes:
    from wiring_hooks import on_build_complete
    await on_build_complete(bot, user, building_name, new_level, supabase)

  Example — on every user action:
    from wiring_hooks import on_user_action
    on_user_action(user_id, supabase)   # sync — no await needed

HOOKS PROVIDED:
  on_user_action(user_id, supabase)
    → updates last_active column
    → checks Commander's Echo expiry
    → processes completed training queue items

  on_build_complete(bot, user, building_name, level, supabase)
    → sends 🔬 build complete notification

  on_research_complete(bot, user, research_name, unlocks, supabase)
    → sends 🔬 research complete notification

  on_training_complete(bot, user, completed_dict, supabase)
    → sends ⚔️ training complete notification for each unit type

  on_battle_won(bot, attacker, defender_id, node_name, loot, supabase)
    → sends combat result notification to both parties
    → records war event if attacker is in a sector war

  on_resource_collected(user, resource_key, amount, alliance, supabase)
    → records alliance mission progress

  on_player_ejected(user, ejected_by_id, sector_id, supabase)
    → records war event

  on_sector_phase_warning(bot, sector_id, sector_state, warning_msg, supabase)
    → sends hazard warning to all players in sector

  on_craft_complete(bot, user, item_name, supabase)
    → sends craft complete notification

  on_prestige(bot, user, new_tier, supabase)
    → sends prestige notification + server-wide gamemaster line

WIRING CHECKLIST — add these one-liners to main.py:

  1. Every callback/message handler — top of handler after get_user():
       on_user_action(u_id, supabase)

  2. Inside check_and_complete_buildings() when a building completes:
       await on_build_complete(bot, user, building_name, new_level, supabase)

  3. Inside check_and_complete_research() when research completes:
       await on_research_complete(bot, user, research_name, unlocks, supabase)

  4. Inside process_training_queue() (in training_system.py) when training completes:
       — training_system.py doesn't have bot access, so check in scheduler instead:
       In scheduler.py phase_tick, after process_training_queue():
         for uid, completed in completed_map.items():
             user = get_user(uid)
             await on_training_complete(bot, user, completed, supabase)

  5. Inside battle resolution (attack_system.py or main.py battle handler):
       await on_battle_won(bot, attacker_user, defender_id, node_name, loot, supabase)

  6. Inside collect_node_resources() return path:
       on_resource_collected(user, resource_key, amount, alliance, supabase)

  7. Inside phase_tick in scheduler.py when a player is ejected:
       await on_player_ejected(user, "HAZARD", sector_id, supabase)
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from supabase_db import supabase as supabase_client

# ═══════════════════════════════════════════════════════════════════════════
#  SYNC HOOKS — call without await
# ═══════════════════════════════════════════════════════════════════════════

def on_user_action(user_id: str, supabase=supabase_client, DB_TABLE: str = "players"):
    """
    Call at the top of every handler after get_user().
    Updates last_active (needed for Chronicle + back-online blast).
    Checks Commander's Echo expiry.
    Does NOT process training — that's done by the scheduler.
    """
    try:
        supabase_client.table(DB_TABLE).update({
            "last_active": datetime.utcnow().isoformat()
        }).eq("user_id", str(user_id)).execute()
    except Exception as e:
        print(f"[HOOK] last_active update failed for {user_id}: {e}")

    # Check echo expiry inline — load, check, save if changed
    try:
        r = supabase_client.table(DB_TABLE).select(
            "user_id, echo_expires, echo_original_skills, skill_points_spent, pending_notification"
        ).eq("user_id", str(user_id)).execute()
        if r.data:
            from supabase_db import normalize_user
            from black_market import check_echo_expiry
            user = normalize_user(r.data[0])
            if user.get("echo_expires"):
                updated = check_echo_expiry(user)
                if not updated.get("echo_expires"):
                    supabase_client.table(DB_TABLE).update({
                        "skill_points_spent":  updated.get("skill_points_spent", {}),
                        "echo_expires":        None,
                        "echo_original_skills": {},
                        "pending_notification": updated.get("pending_notification", ""),
                    }).eq("user_id", str(user_id)).execute()
    except Exception:
        pass   # Non-critical — don't crash the handler


def on_resource_collected(
    user: dict,
    resource_key: str,
    amount: int,
    alliance: Optional[dict],
    DB_TABLE: str = "players",
) -> Optional[dict]:
    """
    Record alliance mission progress when a resource is collected.
    Returns updated alliance dict if changed, else None.
    """
    if not alliance:
        return None
    try:
        from alliance_missions import record_mission_progress
        alliance, completed = record_mission_progress(
            alliance, user.get("user_id", ""),
            "collect_resource", amount, resource=resource_key
        )
        if completed:
            from wiring_hooks import _save_alliance
            _save_alliance(alliance)
            return alliance
    except Exception:
        pass
    return None


def _save_alliance(alliance: dict):
    import json
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
#  ASYNC HOOKS — call with await
# ═══════════════════════════════════════════════════════════════════════════

async def on_build_complete(
    bot,
    user: dict,
    building_name: str,
    new_level: int,
    DB_TABLE: str = "players",
):
    """Send 🔬 build complete DM."""
    try:
        from notification_engine import notify_build_complete
        uid = user.get("user_id", "")
        if uid and bot:
            await notify_build_complete(bot, uid, building_name, new_level, DB_TABLE)
    except Exception as e:
        print(f"[HOOK] on_build_complete error: {e}")


async def on_research_complete(
    bot,
    user: dict,
    research_name: str,
    unlocks: List[str],
    DB_TABLE: str = "players",
):
    """Send 🔬 research complete DM."""
    try:
        from notification_engine import notify_research_complete
        uid = user.get("user_id", "")
        if uid and bot:
            await notify_research_complete(bot, uid, research_name, unlocks, DB_TABLE)
    except Exception as e:
        print(f"[HOOK] on_research_complete error: {e}")


async def on_training_complete(
    bot,
    user: dict,
    completed: Dict[str, int],
    DB_TABLE: str = "players",
):
    """Send ⚔️ training complete DM for each finished unit batch."""
    try:
        from notification_engine import notify_training_complete
        from training_system import UNITS
        uid = user.get("user_id", "")
        if not uid or not bot:
            return
        for unit_type, count in completed.items():
            unit_name = UNITS.get(unit_type, {}).get("name", unit_type)
            await notify_training_complete(bot, uid, unit_name, count, DB_TABLE)
    except Exception as e:
        print(f"[HOOK] on_training_complete error: {e}")


async def on_battle_won(
    bot,
    attacker: dict,
    defender_id: str,
    node_name: str,
    loot: dict,
    DB_TABLE: str = "players",
    alliance_id: str = None,
):
    """
    Called when attacker wins a battle.
    1. Sends battle report to both parties.
    2. Records sector war event if applicable.
    3. Records alliance mission progress.
    """
    attacker_id   = attacker.get("user_id", "")
    attacker_name = attacker.get("username", "?")

    # 1. Notify attacker (won)
    try:
        from notification_engine import notify_battle_result
        await notify_battle_result(
            bot, attacker_id, attacker_name, "defender", True,
            node_name, loot, DB_TABLE
        )
    except Exception:
        pass

    # 2. Notify defender (lost)
    try:
        from notification_engine import notify_battle_result
        await notify_battle_result(
            bot, defender_id, attacker_name, "You", False,
            node_name, {}, DB_TABLE
        )
    except Exception:
        pass

    # 3. Record war event
    if alliance_id:
        try:
            from sector_war import record_war_event, is_in_war
            if is_in_war(alliance_id):
                record_war_event(
                    alliance_id, "node_captured", attacker_name,
                    f"Captured {node_name}"
                )
        except Exception:
            pass

    # 4. Alliance mission progress (win_battles)
    try:
        import json
        with open("alliances.json") as f:
            alliances = json.load(f)
        if alliance_id and alliance_id in alliances:
            from alliance_missions import record_mission_progress
            alliance, completed = record_mission_progress(
                alliances[alliance_id], attacker_id, "win_battles", 1
            )
            if completed:
                alliances[alliance_id] = alliance
                with open("alliances.json", "w") as f:
                    json.dump(alliances, f, indent=2)
    except Exception:
        pass


async def on_player_ejected(
    bot,
    user: dict,
    ejected_by: str,
    sector_id: int,
    DB_TABLE: str = "players",
    alliance_id: str = None,
):
    """Called when a player is ejected from a sector node."""
    uid  = user.get("user_id", "")
    name = user.get("username", "?")

    # Notify the ejected player
    try:
        from notification_engine import notify_player
        from teleport_system import SECTOR_QUICK_INFO
        info  = SECTOR_QUICK_INFO.get(sector_id, {})
        sname = info.get("name", f"Sector {sector_id}")
        await notify_player(
            bot, uid, "sector_alert",
            f"🌋 You were ejected from *{sname}*.\nReason: {ejected_by}",
            
            DB_TABLE
        )
    except Exception:
        pass

    # Record war event
    if alliance_id:
        try:
            from sector_war import record_war_event, is_in_war
            if is_in_war(alliance_id):
                record_war_event(alliance_id, "player_ejected", name, f"Ejected from Sector {sector_id}")
        except Exception:
            pass


async def on_sector_phase_warning(
    bot,
    sector_id: int,
    sector_state: dict,
    warning_msg: str,
    DB_TABLE: str = "players",
):
    """Send hazard warnings to all players currently in a sector."""
    try:
        from notification_engine import broadcast_sector
        await broadcast_sector(
            bot, sector_id, "hazard_warning",
            warning_msg, DB_TABLE, sector_state
        )
    except Exception as e:
        print(f"[HOOK] phase_warning error: {e}")


async def on_craft_complete(
    bot,
    user: dict,
    item_name: str,
    DB_TABLE: str = "players",
):
    """Send craft complete notification."""
    try:
        from notification_engine import notify_player
        uid = user.get("user_id", "")
        if uid and bot:
            await notify_player(
                bot, uid, "build_complete",
                f"⚗️ *{item_name}* crafted successfully! Check your backpack.",
                DB_TABLE
            )
    except Exception as e:
        print(f"[HOOK] on_craft_complete error: {e}")


async def on_dominance_ruler_change(
    bot,
    new_ruler: dict,
    sector_id: int,
    score: int,
    DB_TABLE: str = "players",
    group_chat_id: int = None,
):
    """Called when sector ruler changes. Notifies new ruler + server broadcast."""
    uid  = new_ruler.get("user_id", "")
    name = new_ruler.get("username", "?")

    try:
        from notification_engine import notify_dominance_ruler, broadcast_gamemaster
        from teleport_system import SECTOR_QUICK_INFO
        info  = SECTOR_QUICK_INFO.get(sector_id, {})
        sname = info.get("name", f"Sector {sector_id}")
        await notify_dominance_ruler(bot, uid, sname, score, DB_TABLE)
        if group_chat_id:
            await broadcast_gamemaster(
                bot, "ruler_change", DB_TABLE, active_hours=48,
                new_ruler=name, sector=sname, old_ruler="the previous ruler"
            )
    except Exception as e:
        print(f"[HOOK] ruler_change error: {e}")


async def on_prestige(
    bot,
    user: dict,
    new_tier: int,
    DB_TABLE: str = "players",
    group_chat_id: int = None,
):
    """Called when a player prestiges."""
    uid  = user.get("user_id", "")
    name = user.get("username", "?")

    try:
        from notification_engine import notify_player, broadcast_gamemaster
        await notify_player(
            bot, uid, "dominance",
            f"👑 *Prestige {new_tier} achieved!*\n"
            f"Your power multiplier has increased.\n"
            f"The server has been notified.",
            DB_TABLE
        )
        if group_chat_id:
            await broadcast_gamemaster(
                bot, "ruler_change", DB_TABLE, active_hours=48,
                new_ruler=name, sector=f"Prestige {new_tier}",
                old_ruler="the limits of power"
            )
    except Exception as e:
        print(f"[HOOK] on_prestige error: {e}")


# ═══════════════════════════════════════════════════════════════════════════
#  SCHEDULER HOOK — add to phase_tick in scheduler.py
# ═══════════════════════════════════════════════════════════════════════════

async def tick_training_notifications(bot, supabase=supabase_client, DB_TABLE: str = "players", *args):
    """
    Check all players' training queues. For any that just completed,
    send a notification. Called by scheduler every 60 seconds.

    Add to scheduler.py start_scheduler() while loop:
        from wiring_hooks import tick_training_notifications
        await tick_training_notifications(bot, supabase, DB_TABLE)
    """
    try:
        now    = datetime.utcnow().isoformat()
        result = supabase_client.table(DB_TABLE).select(
            "user_id, training_queue, username"
        ).not_.is_("training_queue", "null").execute()

        for row in (result.data or []):
            uid   = row.get("user_id")
            queue = row.get("training_queue") or []
            if not isinstance(queue, list) or not queue:
                continue

            done = [item for item in queue if item.get("completes_at", "9999") <= now]
            if not done:
                continue

            # Process via training_system
            from training_system import process_training_queue
            completed_result = process_training_queue(uid)
            completed        = completed_result.get("completed", {})

            if completed and bot:
                from supabase_db import normalize_user
                r2   = supabase_client.table(DB_TABLE).select("*").eq("user_id", uid).execute()
                user = normalize_user(r2.data[0]) if r2.data else {"user_id": uid, "username": row.get("username","?")}
                await on_training_complete(bot, user, completed, DB_TABLE)

    except Exception as e:
        print(f"[HOOK] tick_training_notifications error: {e}")


SCHEDULER_WIRING = """
# ── ADD TO scheduler.py start_scheduler() while loop ──────────────────────

from wiring_hooks import on_user_action, tick_training_notifications

# Every 60s tick — check completed training and notify
await tick_training_notifications(bot, supabase, DB_TABLE)
"""

MAIN_PY_WIRING = """
# ── ADD TO main.py — one line at the top of cmd_start and every callback ──

from wiring_hooks import on_user_action

# Inside cmd_start, after u_id = str(message.from_user.id):
on_user_action(u_id, supabase)

# Inside every @dp.callback_query handler, after u_id and user = get_user():
on_user_action(u_id, supabase)

# ── ADD TO menu_shop callback — replace the broken double-edit_text ────────
# Replace cb_menu_shop entirely with store_system.py's store_router

# ── ADD TO the routers section (after line 454) ───────────────────────────
from store_system import store_router
from main_p5_patch import p5_router
from main_p6_patch import p6_router
dp.include_router(store_router)
dp.include_router(p5_router)
dp.include_router(p6_router)
"""
