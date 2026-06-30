# -*- coding: utf-8 -*-
"""
sector_report.py — Sector Event Log System
===========================================
Every meaningful event in a sector is recorded in a rolling log.
Players see this log when they view the sector map or chat.
It makes sectors feel alive — you can read recent history and
understand what's been happening without being present.

EVENTS LOGGED:
  - Phase transitions (system)
  - Player arrivals / departures
  - Node captures and ejections
  - Battle outcomes
  - Predator spawns and kills
  - Jammer activations (anonymised)
  - Ruler changes
  - Resource collections above threshold

LOG STRUCTURE:
  Each sector's log lives in sector_state["event_log"] as a list.
  Max 50 entries, newest first. Entries older than 24h auto-pruned.
  System events are shown in italics. Player events show names.

PHASE WARNING SYSTEM:
  When a phase is within warning_before_secs of ending,
  a warning is inserted into the log AND sent as a DM to all
  players currently in the sector.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple

# ═══════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

MAX_LOG_ENTRIES     = 50
LOG_PRUNE_HOURS     = 24    # Events older than this are removed
LARGE_COLLECT_THRESHOLD = 500   # Resources collected above this are logged


# ═══════════════════════════════════════════════════════════════════════════
#  EVENT LOGGING
# ═══════════════════════════════════════════════════════════════════════════

def log_sector_event(
    sector_state: dict,
    sector_id: int,
    message: str,
    event_type: str = "general",
    player_id: Optional[str] = None,
    player_name: Optional[str] = None,
    is_system: bool = False,
) -> dict:
    """
    Add an event to the sector event log.
    This is the single function every system calls to record something.

    event_type options:
      general, phase_change, arrival, departure, battle, capture,
      eject, predator, jam, ruler_change, collection, warning

    Returns updated sector_state.
    """
    if "event_log" not in sector_state or not isinstance(sector_state.get("event_log"), list):
        sector_state["event_log"] = []

    now = datetime.utcnow()

    entry = {
        "timestamp":   now.isoformat(),
        "time_str":    now.strftime("%H:%M"),
        "message":     message,
        "event_type":  event_type,
        "player_id":   player_id,
        "player_name": player_name,
        "is_system":   is_system,
        "sector_id":   sector_id,
    }

    sector_state["event_log"].insert(0, entry)

    # Prune old entries
    cutoff = now - timedelta(hours=LOG_PRUNE_HOURS)
    sector_state["event_log"] = [
        e for e in sector_state["event_log"][:MAX_LOG_ENTRIES]
        if _parse_ts(e.get("timestamp", "")) > cutoff
    ]

    return sector_state


def log_phase_change(sector_state: dict, sector_id: int, new_phase_name: str, emoji: str) -> dict:
    return log_sector_event(
        sector_state, sector_id,
        f"{emoji} Phase → *{new_phase_name}*",
        event_type="phase_change",
        is_system=True,
    )


def log_player_arrival(
    sector_state: dict, sector_id: int,
    player_name: str, player_id: str, mode: str = "roaming"
) -> dict:
    return log_sector_event(
        sector_state, sector_id,
        f"@{player_name} arrived [{mode}]",
        event_type="arrival",
        player_id=player_id,
        player_name=player_name,
    )


def log_player_departure(
    sector_state: dict, sector_id: int,
    player_name: str, player_id: str, destination: Optional[int] = None
) -> dict:
    dest_str = f" → Sector {destination}" if destination else ""
    return log_sector_event(
        sector_state, sector_id,
        f"@{player_name} departed{dest_str}",
        event_type="departure",
        player_id=player_id,
        player_name=player_name,
    )


def log_node_capture(
    sector_state: dict, sector_id: int,
    player_name: str, player_id: str, node_name: str
) -> dict:
    return log_sector_event(
        sector_state, sector_id,
        f"@{player_name} occupied *{node_name}*",
        event_type="capture",
        player_id=player_id,
        player_name=player_name,
    )


def log_node_battle(
    sector_state: dict, sector_id: int,
    attacker_name: str, defender_name: str,
    node_name: str, attacker_won: bool,
) -> dict:
    result = "defeated" if attacker_won else "repelled by"
    return log_sector_event(
        sector_state, sector_id,
        f"⚔️ @{attacker_name} {result} @{defender_name} at *{node_name}*",
        event_type="battle",
    )


def log_player_ejected(
    sector_state: dict, sector_id: int,
    player_name: str, reason: str = "battle"
) -> dict:
    return log_sector_event(
        sector_state, sector_id,
        f"@{player_name} ejected [{reason}]",
        event_type="eject",
        player_name=player_name,
    )


def log_predator_spawn(
    sector_state: dict, sector_id: int,
    predator_name: str, node_name: str
) -> dict:
    return log_sector_event(
        sector_state, sector_id,
        f"👾 *{predator_name}* spawned at *{node_name}* — fight it with energy!",
        event_type="predator",
        is_system=True,
    )


def log_predator_killed(
    sector_state: dict, sector_id: int,
    predator_name: str, contributors: int
) -> dict:
    return log_sector_event(
        sector_state, sector_id,
        f"💀 *{predator_name}* defeated by {contributors} commander(s). Loot distributed.",
        event_type="predator",
        is_system=True,
    )


def log_sector_jam(sector_state: dict, sector_id: int) -> dict:
    """Log jam without revealing the jammer's identity."""
    return log_sector_event(
        sector_state, sector_id,
        "⚡ *SECTOR JAMMED* — Communications disrupted for 3 minutes.",
        event_type="jam",
        is_system=True,
    )


def log_ruler_change(
    sector_state: dict, sector_id: int,
    new_ruler_name: str, old_ruler_name: Optional[str] = None
) -> dict:
    if old_ruler_name:
        msg = f"👑 @{new_ruler_name} dethroned @{old_ruler_name} — new Sector Ruler"
    else:
        msg = f"👑 @{new_ruler_name} claimed the Sector Ruler throne"
    return log_sector_event(
        sector_state, sector_id, msg,
        event_type="ruler_change", is_system=True,
    )


def log_large_collection(
    sector_state: dict, sector_id: int,
    player_name: str, player_id: str,
    resource: str, amount: int,
) -> dict:
    """Only log collections above the threshold — avoids log spam."""
    if amount < LARGE_COLLECT_THRESHOLD:
        return sector_state
    from resource_registry import get_emoji, get_display_name
    emoji = get_emoji(resource)
    name  = get_display_name(resource)
    return log_sector_event(
        sector_state, sector_id,
        f"@{player_name} collected {emoji}{amount} {name}",
        event_type="collection",
        player_id=player_id,
        player_name=player_name,
    )


def log_phase_warning(
    sector_state: dict, sector_id: int,
    warning_msg: str,
) -> dict:
    return log_sector_event(
        sector_state, sector_id,
        f"⚠️ {warning_msg}",
        event_type="warning",
        is_system=True,
    )


def log_incoming_march(
    sector_state: dict, sector_id: int,
    attacker_name: str, node_name: str, arrival_mins: int,
) -> dict:
    return log_sector_event(
        sector_state, sector_id,
        f"⚠️ @{attacker_name} marching on *{node_name}* — arrives in {arrival_mins}m",
        event_type="battle",
        player_name=attacker_name,
    )


# ═══════════════════════════════════════════════════════════════════════════
#  PHASE WARNING TRACKER
#  Prevents sending the same warning multiple times per phase
# ═══════════════════════════════════════════════════════════════════════════

def should_send_warning(sector_state: dict, sector_id: int, phase_name: str) -> bool:
    """
    Check if a phase warning has already been sent this phase.
    Returns True if the warning should be sent (first time).
    Updates state to record it was sent.
    """
    warnings_sent = sector_state.get("warnings_sent", {})
    if not isinstance(warnings_sent, dict):
        warnings_sent = {}

    key = f"{sector_id}:{phase_name}"
    if key in warnings_sent:
        return False

    warnings_sent[key] = datetime.utcnow().isoformat()

    # Prune old warning records (keep last 20)
    if len(warnings_sent) > 20:
        sorted_keys = sorted(warnings_sent.items(), key=lambda x: x[1])
        warnings_sent = dict(sorted_keys[-20:])

    sector_state["warnings_sent"] = warnings_sent
    return True


def clear_phase_warning(sector_state: dict, sector_id: int, phase_name: str) -> dict:
    """Clear warning record when phase changes — so next phase can warn."""
    warnings_sent = sector_state.get("warnings_sent", {})
    if isinstance(warnings_sent, dict):
        key = f"{sector_id}:{phase_name}"
        warnings_sent.pop(key, None)
        sector_state["warnings_sent"] = warnings_sent
    return sector_state


# ═══════════════════════════════════════════════════════════════════════════
#  DISPLAY FORMATTERS
# ═══════════════════════════════════════════════════════════════════════════

def format_event_log(
    sector_state: dict,
    limit: int = 10,
    player_id: Optional[str] = None,
    filter_type: Optional[str] = None,
) -> str:
    """
    Format the sector event log for display.

    player_id: highlight events involving this player
    filter_type: only show events of this type (e.g., "battle")
    """
    log = sector_state.get("event_log", [])
    if not isinstance(log, list):
        log = []

    if filter_type:
        log = [e for e in log if e.get("event_type") == filter_type]

    if not log:
        return "📜 *Sector Report*\n━━━━━━━━━━━━━━━━\n_No events recorded yet._"

    lines = ["📜 *SECTOR REPORT*", "━━━━━━━━━━━━━━━━"]

    for entry in log[:limit]:
        time_str   = entry.get("time_str", "??:??")
        message    = entry.get("message", "")
        is_system  = entry.get("is_system", False)
        evt_player = entry.get("player_id")

        # Highlight events involving the viewing player
        is_mine = player_id and evt_player == player_id

        if is_system:
            lines.append(f"  _{time_str} {message}_")
        elif is_mine:
            lines.append(f"  [{time_str}] 👤 {message}")
        else:
            lines.append(f"  [{time_str}] {message}")

    if len(log) > limit:
        lines.append(f"  _... {len(log) - limit} earlier events_")

    lines.append("━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def format_sector_dashboard(
    sector_id: int,
    sector_state: dict,
    user: dict,
    alliance: Optional[dict] = None,
) -> str:
    """
    Full sector dashboard combining:
    - Current phase status
    - Node map summary  
    - Recent event log (last 6 entries)
    - Active alerts
    """
    from sector_cycles import get_current_phase, format_phase_status
    from sector_nodes import SECTOR_NODES, NODE_TYPES
    from teleport_system import SECTOR_QUICK_INFO, get_alliance_safe_sectors

    player_id   = user.get("user_id", "")
    sector_info = SECTOR_QUICK_INFO.get(sector_id, {})
    sector_name = sector_info.get("name", f"Sector {sector_id}")
    sector_emoji = sector_info.get("emoji", "🌍")

    # Safe zone tag
    safe_sectors = get_alliance_safe_sectors(alliance) if alliance else []
    safe_tag     = "  🟢 ALLIANCE SAFE" if sector_id in safe_sectors else ""

    # Phase
    phase         = get_current_phase(sector_id)
    phase_name    = phase.get("name", "?")
    phase_emoji   = phase.get("emoji", "")
    phase_remain  = phase.get("time_remaining_str", "?")
    phase_mult    = phase.get("resource_multiplier", 1.0)
    phase_hazard  = phase.get("hazard")
    next_phase    = phase.get("next_phase", {})

    lines = [
        f"{sector_emoji} *{sector_name.upper()}*{safe_tag}",
        f"{'─' * 36}",
        f"📡 *{phase_emoji} {phase_name}* — {phase_remain} left",
    ]

    if phase_mult != 1.0:
        lines.append(f"   Yield: ×{phase_mult:.1f}")
    if phase_hazard:
        lines.append(f"   ⚠️ Hazard: {phase_hazard.replace('_', ' ').title()}")

    lines.append(f"   Next: {next_phase.get('emoji','')} {next_phase.get('name','?')}")

    # Ruler
    dom        = sector_state.get("dominance", {})
    ruler_name = dom.get("ruler_name")
    if ruler_name:
        lines.append(f"👑 Ruler: @{ruler_name}")

    # Node summary (compact)
    lines.append(f"\n🗺️ *NODES:*")
    nodes     = SECTOR_NODES.get(sector_id, {})
    occupancy = sector_state.get("occupancy", {})
    roaming   = sector_state.get("roaming", {})

    for node_key in sorted(nodes.keys()):
        node      = nodes[node_key]
        node_type = node.get("type", "")
        if node_type == "base_plot":
            continue
        type_def  = NODE_TYPES.get(node_type, {})
        emoji     = type_def.get("emoji", "📍")
        node_name = node.get("name", node_key)
        occ_key   = f"{sector_id}:{node_key}"
        occupant  = occupancy.get(occ_key)

        if occupant:
            is_you = occupant.get("player_id") == player_id
            marker = "🟡 YOU" if is_you else f"🔴 @{occupant['player_name']}"
            pending = int(occupant.get("pending_resources", 0))
            suffix  = f" [{pending}⏳]" if is_you and pending > 0 else ""
            lines.append(f"  [{node_key}]{emoji} {node_name[:18]:<18} {marker}{suffix}")
        else:
            suit_tag = " ⚠️" if node.get("requires_suit") else ""
            lines.append(f"  [{node_key}]{emoji} {node_name[:18]:<18} ⚪ Vacant{suit_tag}")

    # Roaming players
    roaming_others = {pid: d for pid, d in roaming.items() if pid != player_id}
    if roaming_others:
        names = [f"@{d.get('player_name','?')}" for d in list(roaming_others.values())[:3]]
        lines.append(f"\n👤 Roaming: {', '.join(names)}")

    # Recent events (last 5)
    log     = sector_state.get("event_log", [])
    if isinstance(log, list) and log:
        lines.append(f"\n📜 *RECENT:*")
        for entry in log[:5]:
            t   = entry.get("time_str", "?")
            msg = entry.get("message", "")
            is_sys = entry.get("is_system", False)
            if is_sys:
                lines.append(f"  _{t} {msg}_")
            else:
                lines.append(f"  [{t}] {msg}")

    # Active jam
    jam = sector_state.get("active_jam")
    if jam:
        try:
            from datetime import datetime
            exp = datetime.fromisoformat(jam["expires_at"])
            rem = max(0, (exp - datetime.utcnow()).total_seconds())
            lines.append(f"\n⚡ *JAMMED* — {int(rem//60)}m {int(rem%60)}s remaining")
        except Exception:
            pass

    lines.append(f"{'─' * 36}")
    return "\n".join(lines)


def get_players_in_sector(sector_state: dict) -> Dict[str, dict]:
    """
    Get all players currently in a sector (node occupants + roaming).
    Returns dict of {player_id: {player_name, location}}
    """
    players   = {}
    occupancy = sector_state.get("occupancy", {})
    roaming   = sector_state.get("roaming", {})

    for occ_key, occ_data in occupancy.items():
        if isinstance(occ_data, dict):
            pid  = occ_data.get("player_id")
            name = occ_data.get("player_name", "Unknown")
            if pid:
                node_key = occ_key.split(":")[-1] if ":" in occ_key else "?"
                players[pid] = {"player_name": name, "location": f"node_{node_key}"}

    for pid, data in roaming.items():
        if isinstance(data, dict):
            players[pid] = {
                "player_name": data.get("player_name", "Unknown"),
                "location": "roaming",
            }

    return players


def _parse_ts(ts: str) -> datetime:
    """Safe timestamp parser."""
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return datetime.min
