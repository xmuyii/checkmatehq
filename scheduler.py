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

# ═══════════════════════════════════════════════════════════════════════════
#  DAILY GRANTS — These replace your existing grant functions in main.py
# ═══════════════════════════════════════════════════════════════════════════

async def grant_daily_teleports(supabase, DB_TABLE: str, bot=None):
    """
    Grant 3 free teleport charges to every player daily.
    Uses the teleport_charges integer column directly — never touches inventory.
    This fixes the 'str object has no attribute append' crash.
    
    Previously this was appending to inventory list — wrong approach.
    Teleport charges are their own integer column now.
    """
    today   = datetime.utcnow().strftime("%Y-%m-%d")
    granted = 0
    failed  = 0

    try:
        # Only fetch the columns we need — faster, less data
        result = supabase.table(DB_TABLE).select(
            "user_id, teleport_charges, teleport_daily_claimed_date"
        ).execute()
        
        users = result.data or []

        for user in users:
            try:
                uid = user.get("user_id")
                if not uid:
                    continue

                # Skip if already claimed today
                if user.get("teleport_daily_claimed_date") == today:
                    continue

                current = user.get("teleport_charges") or 0

                supabase.table(DB_TABLE).update({
                    "teleport_charges":              current + 3,
                    "teleport_daily_claimed_date":   today,
                    "teleport_last_claim_ts":        datetime.utcnow().isoformat(),
                }).eq("user_id", uid).execute()

                granted += 1

            except Exception as e:
                failed += 1
                print(f"[WARN] Could not grant teleports to {user.get('user_id','?')}: {e}")

        print(f"[TELEPORTS] Granted 3 charges to {granted} players ({failed} failed)")

    except Exception as e:
        print(f"[ERROR] grant_daily_teleports: {e}")


async def grant_daily_shields(supabase, DB_TABLE: str, bot=None):
    """
    Grant a basic shield to every player who is currently unshielded.
    Uses base_shielded boolean + shield_expires_at text column.
    Never appends to inventory.
    
    Shield duration: 8 hours.
    Only granted if player has no active shield.
    """
    shield_hours = 8
    granted      = 0
    failed       = 0

    try:
        result = supabase.table(DB_TABLE).select(
            "user_id, base_shielded, shield_expires_at"
        ).execute()
        
        users = result.data or []
        now   = datetime.utcnow()

        for user in users:
            try:
                uid = user.get("user_id")
                if not uid:
                    continue

                # Check if already shielded
                already_shielded = False
                if user.get("base_shielded"):
                    exp_str = user.get("shield_expires_at")
                    if exp_str:
                        try:
                            exp = datetime.fromisoformat(exp_str)
                            already_shielded = now < exp
                        except Exception:
                            pass

                if already_shielded:
                    continue

                expires = (now + timedelta(hours=shield_hours)).isoformat()

                supabase.table(DB_TABLE).update({
                    "base_shielded":    True,
                    "shield_expires_at": expires,
                }).eq("user_id", uid).execute()

                granted += 1

            except Exception as e:
                failed += 1
                print(f"[WARN] Could not grant shield to {user.get('user_id','?')}: {e}")

        print(f"[SHIELDS] Granted 8h shield to {granted} players ({failed} failed)")

    except Exception as e:
        print(f"[ERROR] grant_daily_shields: {e}")


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
            sector_state["last_phase_name"] = phase_name
            sector_state["last_updated"]    = now.isoformat()
            supabase.table("sector_state").update(sector_state).eq(
                "sector_id", sector_id
            ).execute()

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

            supabase.table("sector_state").update(sector_state).eq(
                "sector_id", sector_id
            ).execute()

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
    Start all background tasks.
    Call this once from main() before dp.start_polling().
    
    Usage in main.py:
        from scheduler import start_scheduler
        
        async def main():
            bot = Bot(token=TOKEN)
            ...
            asyncio.create_task(
                start_scheduler(bot, supabase, DB_TABLE, GROUP_CHAT_ID)
            )
            await dp.start_polling(bot)
    """
    print("[SCHEDULER] Starting background tasks...")
    
    # Run daily grants immediately on startup for any missed players
    await grant_daily_teleports(supabase, DB_TABLE, bot)
    await grant_daily_shields(supabase, DB_TABLE, bot)

    tick_count = 0

    while True:
        try:
            now  = datetime.utcnow()
            secs = (now - now.replace(hour=0, minute=0, second=0)).total_seconds()

            # ── Every 60 seconds: phase tick ─────────────────────────────
            await phase_tick(supabase, DB_TABLE, bot, GROUP_CHAT_ID)

            # ── Every 6 hours: purge bounties (tick 0, 360, 720, 1080) ──
            if tick_count % 360 == 0:
                await purge_old_bounties(supabase)

            # ── Midnight UTC: daily grants + dominance reset ──────────────
            if 0 <= secs < 65:   # Within first 65 seconds of midnight
                if tick_count % 10 == 0:  # Throttle — only run once per minute window
                    await grant_daily_teleports(supabase, DB_TABLE, bot)
                    await grant_daily_shields(supabase, DB_TABLE, bot)
                    await dominance_cycle_reset(supabase, DB_TABLE, bot, GROUP_CHAT_ID)

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
