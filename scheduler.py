# -*- coding: utf-8 -*-
"""
scheduler.py — Background Scheduled Tasks
==========================================
All periodic tasks that run automatically while the bot is live.

HOW TO ADD TO main.py:
  from scheduler import start_scheduler
  
  async def main():
      ...
      asyncio.create_task(start_scheduler(bot, dp))
      await dp.start_polling(bot)

WHERE grant_daily_teleports AND grant_daily_shields LIVE:
  They were previously inline in main.py as async functions
  called by aioschedule or apscheduler. Move them here.
  This file is the single home for all scheduled tasks.

TASKS:
  grant_daily_teleports()  — Runs at midnight UTC
  grant_daily_shields()    — Runs at midnight UTC  
  phase_tick()             — Runs every 60 seconds
  warn_phase_transitions() — Runs every 30 seconds
  purge_old_bounties()     — Runs every 6 hours
  dominance_cycle_reset()  — Runs every 24 hours
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional
from wiring_hooks import on_user_action, tick_training_notifications
from supabase_db import global_weekly_reset, _current_week_key, supabase  # Adjust based on your actual export names
# ── DB columns that actually exist in sector_state table ─────────────────
# Any key NOT in this set is computed/transient and must be stripped before save
SECTOR_STATE_DB_COLUMNS = {
    "sector_id", "occupancy", "roaming", "sector_chat", "active_predators",
    "active_jam", "dominance", "pending_ruler_alerts", "pending_predator_loot",
    "pending_notifications", "incoming_marches", "last_phase_name",
    "last_updated", "event_log", "warnings_sent",
}


def _save_sector_state_safe(supabase, sector_id: int, state: dict) -> None:
    """
    Save sector state to DB, stripping any computed fields that don't
    exist as actual columns (e.g. current_phase, time_remaining_str).
    """
    import json
    clean = {}
    for k, v in state.items():
        if k not in SECTOR_STATE_DB_COLUMNS:
            continue
        # Ensure JSON-serialisable
        if isinstance(v, (dict, list)):
            clean[k] = v
        elif v is None or isinstance(v, (str, int, float, bool)):
            clean[k] = v
        else:
            try:
                clean[k] = json.loads(json.dumps(v, default=str))
            except Exception:
                pass

    clean["last_updated"] = datetime.utcnow().isoformat()
    try:
        supabase.table("sector_state").upsert(
            {"sector_id": sector_id, **clean}
        ).execute()
    except Exception as e:
        print(f"[SECTOR_STATE] save error S{sector_id}: {e}")

# ═══════════════════════════════════════════════════════════════════════════
#  DAILY GRANTS — These replace your existing grant functions in main.py
# ══════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════
#  PHASE TICK — Runs every 60 seconds
#  Checks sector phases, applies hazard penalties, pushes warnings
# ═══════════════════════════════════════════════════════════════════════════

async def phase_tick(supabase, DB_TABLE: str, bot, GROUP_CHAT_ID: int):
    """
    Main game loop tick. Runs every 60 seconds.
    
    1. For each active sector, get current phase
    2. Check if phase has changed since last tick
    3. If changed: process_phase_transition
    4. Apply hazard penalties to unprotected players in sector
    5. Push warnings to players approaching phase change
    """
    try:
        from sector_cycles import (
            get_current_phase, get_phase_warning,
            process_phase_transition, is_hazardous,
            should_force_eject_all
        )
        from suit_system import apply_hazard_penalty, is_protected_against

        # Load all sector states
        sector_result = supabase.table("sector_state").select("*").execute()
        sectors       = sector_result.data or []

        for sector_row in sectors:
            sector_id = sector_row.get("sector_id")
            if not sector_id:
                continue

            # Normalize sector state JSON fields
            from supabase_db import safe_json
            sector_state = dict(sector_row)
            for field in ["occupancy", "roaming", "dominance", "active_predators"]:
                sector_state[field] = safe_json(sector_state.get(field), default={})
            for field in ["sector_chat", "pending_ruler_alerts"]:
                sector_state[field] = safe_json(sector_state.get(field), default=[])

            now          = datetime.utcnow()
            current_phase = get_current_phase(sector_id, now)
            phase_name    = current_phase.get("name")
            last_phase    = sector_state.get("last_phase_name")

            # ── Phase transition ──────────────────────────────────────────
            if phase_name != last_phase and last_phase is not None:
                def log_event(sid, msg):
                    _append_sector_chat(sector_state, msg, is_system=True)

                def broadcast(msg):
                    if bot and GROUP_CHAT_ID:
                        asyncio.create_task(
                            bot.send_message(GROUP_CHAT_ID, msg, parse_mode="Markdown")
                        )

                sector_state, notify_pids = process_phase_transition(
                    sector_id, last_phase, current_phase, sector_state,
                    log_event, broadcast,
                    lambda sid, ss: _get_players_in_sector(supabase, DB_TABLE, sid, ss),
                    lambda pid, ud: supabase.table(DB_TABLE).update(ud).eq("user_id", pid).execute(),
                )

                # Notify ejected players
                for pid in notify_pids:
                    try:
                        user_row = supabase.table(DB_TABLE).select(
                            "pending_notification"
                        ).eq("user_id", pid).execute()
                        if user_row.data:
                            notif = user_row.data[0].get("pending_notification", "")
                            if notif and bot:
                                asyncio.create_task(
                                    bot.send_message(int(pid), notif, parse_mode="Markdown")
                                )
                    except Exception:
                        pass

            # ── Hazard penalty tick for unprotected players ───────────────
            hazardous, hazard_type = is_hazardous(sector_id, now)
            if hazardous and not should_force_eject_all(sector_id, now):
                occupancy = sector_state.get("occupancy", {})
                
                for occ_key, occupant in list(occupancy.items()):
                    if not occ_key.startswith(str(sector_id)):
                        continue
                    
                    player_id = occupant.get("player_id")
                    if not player_id:
                        continue

                    try:
                        user_result = supabase.table(DB_TABLE).select("*").eq(
                            "user_id", player_id
                        ).execute()
                        if not user_result.data:
                            continue

                        from supabase_db import normalize_user
                        user = normalize_user(user_result.data[0])

                        # Check suit protection
                        from suit_system import is_protected_against, get_active_suit
                        protected = is_protected_against(user, hazard_type)

                        if not protected:
                            node_key = occ_key.split(":")[1] if ":" in occ_key else ""
                            user, sector_state, penalty_msg, ejected = apply_hazard_penalty(
                                user, sector_state, sector_id, node_key, hazard_type
                            )

                            # Send warning/eject message via bot DM
                            if (penalty_msg or ejected) and bot:
                                asyncio.create_task(
                                    bot.send_message(
                                        int(player_id), penalty_msg, parse_mode="Markdown"
                                    )
                                )

                            supabase.table(DB_TABLE).update(user).eq(
                                "user_id", player_id
                            ).execute()

                    except Exception as e:
                        print(f"[TICK] Penalty error for {player_id}: {e}")

            # ── Phase warning push ────────────────────────────────────────
            warning = get_phase_warning(sector_id, now)
            if warning:
                _send_sector_warning(
                    supabase, DB_TABLE, bot, sector_id, sector_state, warning
                )

            # Save updated sector state
            # Strip computed/transient fields that don't exist as DB columns
            sector_state["last_phase_name"] = phase_name
            sector_state["last_updated"]    = now.isoformat()
            _save_sector_state_safe(supabase, sector_id, sector_state)

    except Exception as e:
        print(f"[ERROR] phase_tick: {e}")
        import traceback
        traceback.print_exc()


# ═══════════════════════════════════════════════════════════════════════════
#  DOMINANCE CYCLE RESET — Runs every 24 hours at midnight UTC
# ═══════════════════════════════════════════════════════════════════════════

async def dominance_cycle_reset(supabase, DB_TABLE: str, bot, GROUP_CHAT_ID: int):
    """
    End the current dominance cycle for all sectors.
    Determines new rulers, distributes tax, resets scores.
    """
    try:
        from sector_dominance import process_dominance_cycle
        from supabase_db import safe_json

        sector_result = supabase.table("sector_state").select("*").execute()
        sectors       = sector_result.data or []

        for sector_row in sectors:
            sector_id    = sector_row.get("sector_id")
            sector_state = dict(sector_row)
            
            for field in ["occupancy", "roaming", "dominance"]:
                sector_state[field] = safe_json(sector_state.get(field), default={})

            dom = sector_state.get("dominance", {})
            if not dom.get("cycle_player_scores"):
                continue   # Nobody active this cycle

            def save_fn(pid, data):
                if data is None:
                    r = supabase.table(DB_TABLE).select("*").eq("user_id", pid).execute()
                    return r.data[0] if r.data else None
                supabase.table(DB_TABLE).update(data).eq("user_id", pid).execute()
                return None

            def log_fn(sid, msg):
                print(f"[DOMINANCE] S{sid}: {msg}")

            def broadcast_fn(msg):
                if bot and GROUP_CHAT_ID:
                    asyncio.create_task(
                        bot.send_message(GROUP_CHAT_ID, msg, parse_mode="Markdown")
                    )

            sector_state, announce = process_dominance_cycle(
                sector_id, sector_state,
                [], save_fn, log_fn, broadcast_fn
            )

            _save_sector_state_safe(supabase, sector_id, sector_state)

        print(f"[DOMINANCE] 24h cycle reset complete for {len(sectors)} sectors")

    except Exception as e:
        print(f"[ERROR] dominance_cycle_reset: {e}")


# ═══════════════════════════════════════════════════════════════════════════
#  BOUNTY EXPIRY — Runs every 6 hours
# ═══════════════════════════════════════════════════════════════════════════

async def purge_old_bounties(supabase):
    """Mark expired bounties as expired in the bounty_board table."""
    try:
        now    = datetime.utcnow().isoformat()
        result = supabase.table("bounty_board").update(
            {"status": "expired"}
        ).eq("status", "active").lt("expires_at", now).execute()
        print(f"[BOUNTIES] Expired old bounties")
    except Exception as e:
        print(f"[ERROR] purge_old_bounties: {e}")


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN SCHEDULER — Add one call to main.py
# ═══════════════════════════════════════════════════════════════════════════
async def start_scheduler(bot, supabase, DB_TABLE: str, GROUP_CHAT_ID: int):
    """
    Start all background tasks with persistence catch-up mechanics.
    """
    print("[SCHEDULER] Starting background tasks...")
    
    # 1. Run daily teleports immediately on startup if it's a new day
    await tick_training_notifications(bot, supabase, DB_TABLE)
    
    tick_count = 0

    while True:
        try:
            now = datetime.utcnow()
            today_str = now.strftime("%Y-%m-%d")
            
            # Use Python's calendar system to get a reliable ISO week string (e.g., "2026-W28")
            current_year, current_week_num, current_day = now.isocalendar()
            current_week_str = f"{current_year}-W{current_week_num}"

            # ── Every 60 seconds: core game mechanics tick ─────────────────
            await phase_tick(supabase, DB_TABLE, bot, GROUP_CHAT_ID)

            # ── Every 6 hours: purge old bounties ──────────────────────────
            if tick_count % 360 == 0:
                await purge_old_bounties(supabase)

            # ── CRITICAL: PERSISTENT TIMELINE CATCH-UP MECHANISM ───────────
            # Fetch global system state to see when resets last actually ran
            # (Create a simple 'system_state' table with 1 row to track execution logs)
            try:
                state_res = supabase.table("system_state").select("*").eq("id", 1).execute()
                sys_state = state_res.data[0] if state_res.data else {}
            except Exception as e:
                print(f"[SCHEDULER WARNING] Could not fetch system state table: {e}")
                sys_state = {}

            last_daily_run = sys_state.get("last_daily_reset_date")   # e.g. "2026-07-09"
            last_weekly_run = sys_state.get("last_weekly_reset_week") # e.g. "2026-W27"
            
            # ── A. Check Daily Reset (Triggers if a new day has arrived or was missed) ──
            if last_daily_run != today_str:
                print(f"[TIMELINE] New day detected ({today_str}). Running daily cycles...")
                await dominance_cycle_reset(supabase, DB_TABLE, bot, GROUP_CHAT_ID)
                
                # Persist that daily reset completed successfully for this date
                supabase.table("system_state").upsert({
                    "id": 1, 
                    "last_daily_reset_date": today_str
                }).execute()

            # ── B. Check Weekly Reset (Triggers if a new week has arrived or was missed) ──
            # ISO weeks roll over precisely at Monday 00:00:00
            if last_weekly_run != current_week_str:
                print(f"[TIMELINE] New week detected ({current_week_str}). Running weekly cleanups...")
                
                # 1. Announce last week's winners BEFORE wiping data
                # (You can call your announcement function here or inside global_weekly_reset)
                
                # 2. Hard reset all weekly points globally
                reset_success = global_weekly_reset()
                
                if reset_success:
                    # Persist that weekly reset completed for this ISO week
                    supabase.table("system_state").upsert({
                        "id": 1, 
                        "last_weekly_reset_week": current_week_str
                    }).execute()

            # ── C. Check Hourly Gift Grant (Triggers if a new hour has arrived or was missed) ──
            current_hour_str = now.strftime("%Y-%m-%dT%H")  # e.g. "2026-07-17T14"
            last_gift_hour = sys_state.get("last_gift_grant_hour")

            if last_gift_hour != current_hour_str:
                print(f"[TIMELINE] New hour detected ({current_hour_str}). Granting gifts...")
                from gift_system import grant_hourly_gifts_to_all
                granted = grant_hourly_gifts_to_all(supabase, DB_TABLE)
                print(f"[GIFTS] Granted to {granted} players")

                supabase.table("system_state").upsert({
                    "id": 1,
                    "last_gift_grant_hour": current_hour_str
                }).execute()

            tick_count += 1
            await asyncio.sleep(60)

        except asyncio.CancelledError:
            print("[SCHEDULER] Stopped.")
            break
        except Exception as e:
            print(f"[SCHEDULER ERROR] {e}")
            await asyncio.sleep(60)


# ═══════════════════════════════════════════════════════════════════════════
#  INTERNAL HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _append_sector_chat(sector_state: dict, message: str, is_system: bool = False):
    """Append a system message to sector chat in the state dict."""
    if "sector_chat" not in sector_state or not isinstance(sector_state["sector_chat"], list):
        sector_state["sector_chat"] = []

    now = datetime.utcnow()
    sector_state["sector_chat"].insert(0, {
        "player_id":   "SYSTEM",
        "player_name": "⚙️ SECTOR",
        "message":     message,
        "timestamp":   now.isoformat(),
        "time_str":    now.strftime("%H:%M"),
        "is_system":   True,
    })
    sector_state["sector_chat"] = sector_state["sector_chat"][:30]


def _get_players_in_sector(supabase, DB_TABLE: str, sector_id: int, sector_state: dict) -> list:
    """Get all player dicts currently in a sector (occupying or roaming)."""
    occupancy = sector_state.get("occupancy", {})
    roaming   = sector_state.get("roaming", {})
    
    player_ids = set()
    for occ in occupancy.values():
        if isinstance(occ, dict):
            pid = occ.get("player_id")
            if pid:
                player_ids.add(pid)
    for pid in roaming:
        player_ids.add(pid)

    players = []
    for pid in player_ids:
        try:
            r = supabase.table(DB_TABLE).select("*").eq("user_id", pid).execute()
            if r.data:
                from supabase_db import normalize_user
                players.append(normalize_user(r.data[0]))
        except Exception:
            pass
    return players


def _send_sector_warning(
    supabase, DB_TABLE: str, bot, sector_id: int,
    sector_state: dict, warning_msg: str
):
    """Send phase warning to all players currently in the sector."""
    if not bot:
        return

    occupancy  = sector_state.get("occupancy", {})
    roaming    = sector_state.get("roaming", {})
    player_ids = set()

    for occ in occupancy.values():
        if isinstance(occ, dict):
            pid = occ.get("player_id")
            if pid:
                player_ids.add(pid)
    for pid in roaming:
        player_ids.add(pid)

    for pid in player_ids:
        try:
            asyncio.create_task(
                bot.send_message(int(pid), warning_msg, parse_mode="Markdown")
            )
        except Exception:
            pass