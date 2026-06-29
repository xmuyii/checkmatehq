# -*- coding: utf-8 -*-
"""
march_queue.py — Timed Troop March System
==========================================
Manages all timed troop movements in the game.
Mirrors the building_queue.py pattern but for military marches.

MARCH TYPES:
  occupy   — Move troops to claim a vacant node
  attack   — March on an occupied node (triggers battle on arrival)
  reinforce— Send additional troops to a node you already hold
  recall   — Pull troops back to home base

MECHANICS:
  - All node movement takes time (no instant teleportation of troops)
  - Commanders teleport, troops march
  - Attacker march is visible to sector report immediately
  - Defender sees incoming march and has time to react
  - Speedup items reduce march time
  - Troops left at home base always stay unless explicitly marched

DISTANCE:
  - Same-sector node: 2 minutes base
  - Reinforcement cross-sector: 15 minutes base
  - Speedups reduce travel time but minimum is 30 seconds
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json

# ═══════════════════════════════════════════════════════════════════════════
#  MARCH CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

MARCH_TYPES = {
    "occupy":    {"label": "Occupation",    "emoji": "🚶"},
    "attack":    {"label": "Attack",        "emoji": "⚔️"},
    "reinforce": {"label": "Reinforcement", "emoji": "🛡️"},
    "recall":    {"label": "Recall",        "emoji": "🏠"},
}

# Base travel times in seconds
TRAVEL_TIME = {
    "same_sector":   120,   # 2 min — marching to a node in current sector
    "cross_sector":  900,   # 15 min — reinforcing from home to another sector
    "recall":        120,   # 2 min — pulling troops back
}

MINIMUM_TRAVEL_SECONDS = 30   # Floor — speedups cannot go below this

# How much each speedup item reduces march time
SPEEDUP_REDUCTION = {
    "speedup_5m":  300,    # 5 minutes
    "speedup_30m": 1800,   # 30 minutes
}

# Unit power values (imported from attack_system context)
UNIT_POWER = {
    "footmen":    1,
    "archers":    3,
    "lancers":    8,
    "castellans": 15,
    "pawns":      1,
    "knights":    10,
}

# ═══════════════════════════════════════════════════════════════════════════
#  MARCH CREATION
# ═══════════════════════════════════════════════════════════════════════════

def create_march(
    user: dict,
    march_type: str,
    sector_id: int,
    node_key: str,
    node_name: str,
    troops: dict,
    travel_mode: str = "same_sector",
    speedup_items_used: List[str] = None,
) -> Tuple[bool, str, dict]:
    """
    Create a new march entry in the player's march queue.

    Args:
        user:               Player data dict
        march_type:         "occupy" | "attack" | "reinforce" | "recall"
        sector_id:          Target sector
        node_key:           Target node key (A-H)
        node_name:          Display name of node
        troops:             {"footmen": 100, "archers": 50, ...}
        travel_mode:        "same_sector" | "cross_sector" | "recall"
        speedup_items_used: List of speedup item keys consumed

    Returns:
        (success, message, updated_user)
    """
    if march_type not in MARCH_TYPES:
        return False, f"❌ Invalid march type: {march_type}", user

    # Validate troops
    ok, msg = _validate_troops(user, troops, march_type)
    if not ok:
        return False, msg, user

    # Check research gate for attacks
    if march_type == "attack":
        from research_tree import is_feature_unlocked
        if not is_feature_unlocked(user, "node_attack"):
            from research_tree import get_locked_message
            return False, get_locked_message("node_attack"), user

    # Calculate travel time
    base_time = TRAVEL_TIME.get(travel_mode, TRAVEL_TIME["same_sector"])
    speedup_reduction = 0

    if speedup_items_used:
        for item_key in speedup_items_used:
            reduction = SPEEDUP_REDUCTION.get(item_key, 0)
            speedup_reduction += reduction
            # Consume item from inventory
            user = _consume_inventory_item(user, item_key)

    travel_seconds = max(MINIMUM_TRAVEL_SECONDS, base_time - speedup_reduction)
    arrival_time = (datetime.utcnow() + timedelta(seconds=travel_seconds)).isoformat()

    # Deduct troops from available garrison
    user = _deduct_troops(user, troops)

    march = {
        "march_id":          f"march_{int(datetime.utcnow().timestamp())}_{user.get('user_id', 'x')[-4:]}",
        "march_type":        march_type,
        "sector_id":         sector_id,
        "node_key":          node_key.upper(),
        "node_name":         node_name,
        "troops":            troops,
        "travel_mode":       travel_mode,
        "base_travel_secs":  base_time,
        "speedup_secs":      speedup_reduction,
        "travel_seconds":    travel_seconds,
        "started_at":        datetime.utcnow().isoformat(),
        "arrival_time":      arrival_time,
        "status":            "marching",   # marching | arrived | cancelled | defeated
        "attacker_name":     user.get("username", "Unknown"),
        "attacker_id":       user.get("user_id", ""),
    }

    if "march_queue" not in user:
        user["march_queue"] = []
    user["march_queue"].append(march)

    time_str = _format_seconds(travel_seconds)
    march_emoji = MARCH_TYPES[march_type]["emoji"]
    march_label = MARCH_TYPES[march_type]["label"]

    msg_lines = [
        f"{march_emoji} *{march_label} MARCH STARTED*",
        f"🎯 Target: *{node_name}* (Sector {sector_id}, Node {node_key.upper()})",
        f"⏱️ Arrives in: *{time_str}*",
        f"👥 Troops: {_format_troops(troops)}",
    ]

    if speedup_reduction > 0:
        msg_lines.append(f"⏩ Speedup applied: -{_format_seconds(speedup_reduction)}")

    return True, "\n".join(msg_lines), user


def cancel_march(
    user: dict,
    march_id: str,
) -> Tuple[bool, str, dict]:
    """
    Cancel an active march and return troops to garrison.
    Can only cancel before arrival.
    """
    queue = user.get("march_queue", [])
    target = None
    for m in queue:
        if m.get("march_id") == march_id and m.get("status") == "marching":
            target = m
            break

    if not target:
        return False, "❌ March not found or already arrived.", user

    # Check if it has arrived
    try:
        arrival = datetime.fromisoformat(target["arrival_time"])
        if datetime.utcnow() >= arrival:
            return False, "❌ March has already arrived — cannot cancel.", user
    except Exception:
        pass

    # Return troops
    user = _return_troops(user, target["troops"])

    # Remove from queue
    user["march_queue"] = [m for m in queue if m.get("march_id") != march_id]

    return True, (
        f"🏠 March to *{target['node_name']}* cancelled.\n"
        f"Troops returned to garrison."
    ), user


def apply_speedup_to_march(
    user: dict,
    march_id: str,
    speedup_item_key: str,
) -> Tuple[bool, str, dict]:
    """
    Apply a speedup item to an in-progress march.
    Consumes the item from inventory.
    """
    from resource_registry import RESOURCES
    if speedup_item_key not in RESOURCES:
        return False, f"❌ Unknown speedup item: {speedup_item_key}", user

    # Check player has item
    inv = user.get("inventory", {})
    if speedup_item_key not in inv or inv[speedup_item_key].get("qty", 0) < 1:
        return False, f"❌ You don't have any {speedup_item_key}.", user

    reduction = SPEEDUP_REDUCTION.get(speedup_item_key, 0)
    if reduction == 0:
        return False, f"❌ {speedup_item_key} is not a speedup item.", user

    queue = user.get("march_queue", [])
    for i, m in enumerate(queue):
        if m.get("march_id") == march_id and m.get("status") == "marching":
            try:
                current_arrival = datetime.fromisoformat(m["arrival_time"])
                new_arrival = current_arrival - timedelta(seconds=reduction)
                floor_arrival = datetime.utcnow() + timedelta(seconds=MINIMUM_TRAVEL_SECONDS)
                if new_arrival < floor_arrival:
                    new_arrival = floor_arrival

                queue[i]["arrival_time"] = new_arrival.isoformat()
                queue[i]["speedup_secs"] = queue[i].get("speedup_secs", 0) + reduction
                user["march_queue"] = queue

                # Consume item
                user = _consume_inventory_item(user, speedup_item_key)

                remaining = (new_arrival - datetime.utcnow()).total_seconds()
                return True, (
                    f"⏩ Speedup applied to march on *{m['node_name']}*!\n"
                    f"New arrival: *{_format_seconds(int(remaining))}*"
                ), user
            except Exception as e:
                return False, f"❌ Speedup failed: {e}", user

    return False, f"❌ No active march with ID {march_id}.", user


# ═══════════════════════════════════════════════════════════════════════════
#  MARCH RESOLUTION — Called when arrival time is reached
# ═══════════════════════════════════════════════════════════════════════════

def get_arrived_marches(user: dict) -> List[dict]:
    """
    Get all marches that have completed their travel time.
    Call this on every user action to process arrivals.
    """
    queue = user.get("march_queue", [])
    now = datetime.utcnow()
    arrived = []

    for m in queue:
        if m.get("status") != "marching":
            continue
        try:
            arrival = datetime.fromisoformat(m["arrival_time"])
            if now >= arrival:
                arrived.append(m)
        except Exception:
            continue

    return arrived


def resolve_march_arrival(
    user: dict,
    march: dict,
    sector_state: dict,
    all_users_fn,       # callable(player_id) -> user dict — injected to avoid circular import
    save_user_fn,       # callable(player_id, user_data) -> None
    log_sector_event_fn,# callable(sector_id, event_str) -> None
) -> Tuple[dict, dict, str]:
    """
    Resolve what happens when a march arrives at its target node.

    Handles:
      - occupy:    Claim vacant node, start resource accumulation
      - attack:    Battle existing occupant, loot pending resources on win
      - reinforce: Add troops to existing occupation
      - recall:    Return troops to home base

    Returns (updated_user, updated_sector_state, result_message)
    """
    from sector_nodes import (
        get_node, is_node_vacant, get_node_occupant,
        set_node_occupant, clear_node_occupant,
        auto_collect_on_departure, loot_abandoned_node,
        NODE_TYPES,
    )

    march_type  = march.get("march_type")
    sector_id   = march.get("sector_id")
    node_key    = march.get("node_key")
    node_name   = march.get("node_name")
    troops      = march.get("troops", {})
    attacker_id = march.get("attacker_id")

    node_def = get_node(sector_id, node_key)
    if not node_def:
        user = _mark_march_done(user, march["march_id"], "error")
        return user, sector_state, f"❌ Node {node_key} in Sector {sector_id} not found."

    # ── OCCUPY ────────────────────────────────────────────────────────────
    if march_type == "occupy":
        if not is_node_vacant(sector_state, sector_id, node_key):
            # Node was taken while marching — convert to attack
            _troops = troops
            user = _mark_march_done(user, march["march_id"], "redirected")
            msg = (
                f"⚠️ *{node_name}* was occupied while your troops were marching.\n"
                f"March converted to attack. Battle will resolve now."
            )
            # Fall through to attack logic
            march_type = "attack"
            troops = _troops
        else:
            sector_state = set_node_occupant(
                sector_state, sector_id, node_key,
                attacker_id, march.get("attacker_name", "Unknown"), troops
            )
            user["current_node"] = {
                "sector_id": sector_id,
                "node_key":  node_key,
                "node_name": node_name,
            }
            user = _mark_march_done(user, march["march_id"], "arrived")

            log_sector_event_fn(
                sector_id,
                f"@{march.get('attacker_name')} occupied {node_name} [Node {node_key}]"
            )

            node_emoji = NODE_TYPES.get(node_def.get("type", ""), {}).get("emoji", "📍")
            return user, sector_state, (
                f"✅ *Troops arrived at {node_name}!*\n"
                f"{node_emoji} Now occupying Node {node_key} in Sector {sector_id}.\n"
                f"Resources accumulating. Use `!collect` to gather them."
            )

    # ── ATTACK ────────────────────────────────────────────────────────────
    if march_type == "attack":
        occupant = get_node_occupant(sector_state, sector_id, node_key)

        if not occupant:
            # Node vacated before arrival — claim it
            sector_state = set_node_occupant(
                sector_state, sector_id, node_key,
                attacker_id, march.get("attacker_name", "Unknown"), troops
            )
            user["current_node"] = {
                "sector_id": sector_id,
                "node_key":  node_key,
                "node_name": node_name,
            }
            user = _mark_march_done(user, march["march_id"], "arrived")
            log_sector_event_fn(sector_id,
                f"@{march.get('attacker_name')} claimed {node_name} (vacated before arrival)")
            return user, sector_state, (
                f"✅ *{node_name}* was vacated before your troops arrived.\n"
                f"Node claimed without conflict."
            )

        # Battle!
        defender_id   = occupant["player_id"]
        defender_name = occupant["player_name"]
        defender_troops = occupant.get("troops", {})

        attacker_power = _calc_power(troops)
        defender_power = _calc_power(defender_troops)

        import random
        atk_roll = attacker_power * random.uniform(0.85, 1.15)
        def_roll = defender_power * random.uniform(0.85, 1.15)

        attacker_wins = atk_roll > def_roll

        # Casualties (5–20% of losing side, 3–8% of winning side)
        if attacker_wins:
            atk_losses = _apply_casualties(troops, 0.06)
            def_losses = _apply_casualties(defender_troops, 0.18)
        else:
            atk_losses = _apply_casualties(troops, 0.22)
            def_losses = _apply_casualties(defender_troops, 0.05)

        # Apply losses
        troops            = _subtract_losses(troops, atk_losses)
        defender_troops   = _subtract_losses(defender_troops, def_losses)

        looted = {}
        if attacker_wins:
            # Auto-collect defender's pending resources → give to attacker
            sector_state, user, looted = loot_abandoned_node(
                sector_state, sector_id, node_key, attacker_id, user
            )
            # Eject defender
            sector_state = clear_node_occupant(sector_state, sector_id, node_key)

            # Update defender troops
            defender_user = all_users_fn(defender_id)
            if defender_user:
                defender_user = _return_troops(defender_user, defender_troops)
                defender_user["losses"] = defender_user.get("losses", 0) + 1
                defender_user["current_node"] = None
                save_user_fn(defender_id, defender_user)

            # Attacker takes node
            sector_state = set_node_occupant(
                sector_state, sector_id, node_key,
                attacker_id, march.get("attacker_name", "Unknown"), troops
            )
            user["current_node"] = {
                "sector_id": sector_id,
                "node_key":  node_key,
                "node_name": node_name,
            }
            user["wins"] = user.get("wins", 0) + 1

        else:
            # Attacker defeated — return surviving troops
            user = _return_troops(user, troops)
            user["losses"] = user.get("losses", 0) + 1

            # Defender keeps node with reduced troops
            sector_state["occupancy"][f"{sector_id}:{node_key}"]["troops"] = defender_troops

        user = _mark_march_done(user, march["march_id"], "won" if attacker_wins else "defeated")

        # Build battle report
        report = _format_node_battle_report(
            attacker_name=march.get("attacker_name", "Unknown"),
            defender_name=defender_name,
            node_name=node_name,
            sector_id=sector_id,
            node_key=node_key,
            attacker_power=int(atk_roll),
            defender_power=int(def_roll),
            attacker_wins=attacker_wins,
            atk_losses=atk_losses,
            def_losses=def_losses,
            looted=looted,
        )

        log_sector_event_fn(
            sector_id,
            f"⚔️ @{march.get('attacker_name')} {'defeated' if attacker_wins else 'failed to take'} "
            f"@{defender_name} at {node_name} [{'W' if attacker_wins else 'L'}]"
        )

        return user, sector_state, report

    # ── REINFORCE ─────────────────────────────────────────────────────────
    if march_type == "reinforce":
        occ_key = f"{sector_id}:{node_key}"
        occupancy = sector_state.get("occupancy", {})
        occupant = occupancy.get(occ_key)

        if not occupant or occupant["player_id"] != attacker_id:
            # Can't reinforce a node you don't hold
            user = _return_troops(user, troops)
            user = _mark_march_done(user, march["march_id"], "failed")
            return user, sector_state, (
                f"❌ Cannot reinforce *{node_name}* — you no longer hold this node.\n"
                f"Troops returned to garrison."
            )

        # Merge troops
        existing = occupant.get("troops", {})
        for unit, count in troops.items():
            existing[unit] = existing.get(unit, 0) + count
        occupant["troops"] = existing
        occupancy[occ_key] = occupant
        sector_state["occupancy"] = occupancy

        user = _mark_march_done(user, march["march_id"], "arrived")
        return user, sector_state, (
            f"🛡️ *Reinforcements arrived at {node_name}!*\n"
            f"Additional troops: {_format_troops(troops)}"
        )

    # ── RECALL ────────────────────────────────────────────────────────────
    if march_type == "recall":
        user = _return_troops(user, troops)
        user["current_node"] = None
        user = _mark_march_done(user, march["march_id"], "arrived")
        return user, sector_state, (
            f"🏠 *Troops recalled from {node_name}.*\n"
            f"Troops returned: {_format_troops(troops)}"
        )

    user = _mark_march_done(user, march["march_id"], "error")
    return user, sector_state, "❌ Unknown march type."


# ═══════════════════════════════════════════════════════════════════════════
#  SECTOR REPORT NOTIFICATION
#  Returns a formatted string to be broadcast to sector when march starts
# ═══════════════════════════════════════════════════════════════════════════

def format_march_alert(march: dict) -> str:
    """
    Format a public sector alert when an attack march starts.
    This is visible to all players in the sector immediately —
    giving defenders time to react.
    """
    march_type  = march.get("march_type", "march")
    attacker    = march.get("attacker_name", "Unknown")
    node_name   = march.get("node_name", "Unknown node")
    sector_id   = march.get("sector_id", "?")
    node_key    = march.get("node_key", "?")
    arrival     = march.get("arrival_time", "")

    try:
        arr_dt    = datetime.fromisoformat(arrival)
        remaining = (arr_dt - datetime.utcnow()).total_seconds()
        time_str  = _format_seconds(int(max(0, remaining)))
    except Exception:
        time_str  = "Unknown"

    if march_type == "attack":
        return (
            f"⚠️ *INCOMING MARCH DETECTED*\n"
            f"⚔️ @{attacker} is marching on *{node_name}* [Node {node_key}]\n"
            f"⏱️ Arrives in: *{time_str}*\n"
            f"Defender: collect resources and prepare — or teleport out."
        )
    elif march_type == "occupy":
        return (
            f"📡 *MARCH DETECTED*\n"
            f"🚶 @{attacker} marching to *{node_name}* [Node {node_key}]\n"
            f"⏱️ Arrives in: *{time_str}*"
        )
    else:
        return (
            f"📡 @{attacker} marching to {node_name} [{time_str}]"
        )


# ═══════════════════════════════════════════════════════════════════════════
#  MARCH QUEUE DISPLAY
# ═══════════════════════════════════════════════════════════════════════════

def format_march_queue_display(user: dict) -> str:
    """Format all active marches for display on dashboard."""
    queue = user.get("march_queue", [])
    active = [m for m in queue if m.get("status") == "marching"]

    if not active:
        return ""

    lines = ["\n⚔️ *ACTIVE MARCHES*\n━━━━━━━━━━━━━━━━━━"]

    for m in active:
        march_type  = m.get("march_type", "march")
        node_name   = m.get("node_name", "Unknown")
        sector_id   = m.get("sector_id", "?")
        node_key    = m.get("node_key", "?")
        troops      = m.get("troops", {})
        arrival     = m.get("arrival_time", "")
        march_id    = m.get("march_id", "")

        try:
            arr_dt    = datetime.fromisoformat(arrival)
            remaining = max(0, (arr_dt - datetime.utcnow()).total_seconds())
            pct       = 100 - (remaining / m.get("travel_seconds", 120)) * 100
            pct       = max(0, min(100, pct))
            time_str  = _format_seconds(int(remaining))
        except Exception:
            pct      = 0
            time_str = "?"

        emoji = MARCH_TYPES.get(march_type, {}).get("emoji", "⚔️")
        label = MARCH_TYPES.get(march_type, {}).get("label", march_type.title())

        bar_len = 15
        filled  = int(bar_len * pct / 100)
        bar     = "█" * filled + "░" * (bar_len - filled)

        lines.append(
            f"{emoji} {label} → *{node_name}* [S{sector_id}-{node_key}]\n"
            f"  [{bar}] {int(pct)}% — {time_str} remaining\n"
            f"  Troops: {_format_troops(troops)}\n"
            f"  ID: `{march_id}`  |  `!speedup {march_id}` to accelerate"
        )

    lines.append("━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def format_march_history(user: dict, limit: int = 5) -> str:
    """Format recent completed marches."""
    queue = user.get("march_queue", [])
    done  = [m for m in queue if m.get("status") not in ("marching",)]
    done  = sorted(done, key=lambda x: x.get("started_at", ""), reverse=True)[:limit]

    if not done:
        return "📜 No recent march history."

    lines = ["📜 *RECENT MARCHES*\n━━━━━━━━━━━━━━━━━━"]
    for m in done:
        status    = m.get("status", "?")
        node_name = m.get("node_name", "?")
        march_type = m.get("march_type", "?")
        emoji     = {"won": "✅", "defeated": "❌", "arrived": "🏁",
                     "cancelled": "🚫", "failed": "⚠️"}.get(status, "❓")
        lines.append(f"{emoji} {march_type.title()} → {node_name} [{status}]")

    lines.append("━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
#  INTERNAL HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _validate_troops(user: dict, troops: dict, march_type: str) -> Tuple[bool, str]:
    """Validate the player has the requested troops available."""
    if not troops or sum(troops.values()) == 0:
        return False, "❌ Must send at least 1 troop."

    military = user.get("military", {})
    for unit, count in troops.items():
        if count <= 0:
            continue
        available = military.get(unit, 0)
        if available < count:
            return False, f"❌ Not enough {unit}. Have {available}, need {count}."

    return True, "OK"


def _deduct_troops(user: dict, troops: dict) -> dict:
    """Remove marching troops from available garrison."""
    military = user.get("military", {})
    for unit, count in troops.items():
        military[unit] = max(0, military.get(unit, 0) - count)
    user["military"] = military
    return user


def _return_troops(user: dict, troops: dict) -> dict:
    """Return troops to garrison (recall or cancelled march)."""
    military = user.get("military", {})
    for unit, count in troops.items():
        if count > 0:
            military[unit] = military.get(unit, 0) + count
    user["military"] = military
    return user


def _consume_inventory_item(user: dict, item_key: str, qty: int = 1) -> dict:
    """Remove one or more of an item from stacked inventory."""
    inv = user.get("inventory", {})
    if item_key in inv:
        inv[item_key]["qty"] = max(0, inv[item_key].get("qty", 0) - qty)
        if inv[item_key]["qty"] == 0:
            del inv[item_key]
    user["inventory"] = inv
    return user


def _calc_power(troops: dict) -> int:
    """Calculate total troop power."""
    total = 0
    for unit, count in troops.items():
        total += UNIT_POWER.get(unit, 1) * count
    return max(1, total)


def _apply_casualties(troops: dict, rate: float) -> dict:
    """Calculate casualties at given rate. Returns losses dict."""
    return {
        unit: max(1, int(count * rate))
        for unit, count in troops.items()
        if count > 0
    }


def _subtract_losses(troops: dict, losses: dict) -> dict:
    """Subtract losses from troop dict."""
    result = {}
    for unit, count in troops.items():
        result[unit] = max(0, count - losses.get(unit, 0))
    return result


def _mark_march_done(user: dict, march_id: str, status: str) -> dict:
    """Update a march's status in the queue."""
    queue = user.get("march_queue", [])
    for m in queue:
        if m.get("march_id") == march_id:
            m["status"] = status
            m["resolved_at"] = datetime.utcnow().isoformat()
            break
    user["march_queue"] = queue
    return user


def _format_seconds(seconds: int) -> str:
    """Format seconds to human-readable string."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        m = seconds // 60
        s = seconds % 60
        return f"{m}m {s}s" if s else f"{m}m"
    else:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h}h {m}m"


def _format_troops(troops: dict) -> str:
    """Format troop dict for display."""
    if not troops:
        return "none"
    parts = [f"{count} {unit}" for unit, count in troops.items() if count > 0]
    return ", ".join(parts) if parts else "none"


def _format_node_battle_report(
    attacker_name: str,
    defender_name: str,
    node_name: str,
    sector_id: int,
    node_key: str,
    attacker_power: int,
    defender_power: int,
    attacker_wins: bool,
    atk_losses: dict,
    def_losses: dict,
    looted: dict,
) -> str:
    """Format the full battle report for node conflict."""
    from resource_registry import RESOURCES

    lines = [
        f"⚔️ *NODE BATTLE REPORT*",
        f"📍 {node_name} — Sector {sector_id}, Node {node_key}",
        f"{'═' * 44}",
        f"🛰️ Attacker: @{attacker_name}",
        f"🛡️ Defender: @{defender_name}",
        f"💪 Power: {attacker_power} vs {defender_power}",
        f"",
        f"{'✅ ATTACKER VICTORY' if attacker_wins else '❌ DEFENDER HELD'}",
        f"",
        f"💀 *CASUALTIES:*",
    ]

    if atk_losses:
        loss_str = ", ".join(f"{v} {k}" for k, v in atk_losses.items() if v > 0)
        lines.append(f"  Attacker: -{loss_str}")

    if def_losses:
        loss_str = ", ".join(f"{v} {k}" for k, v in def_losses.items() if v > 0)
        lines.append(f"  Defender: -{loss_str}")

    if looted and attacker_wins:
        lines.append(f"\n💎 *RESOURCES SEIZED:*")
        for res, amt in looted.items():
            emoji = RESOURCES.get(res, {}).get("emoji", "📦")
            name  = RESOURCES.get(res, {}).get("display_name", res)
            lines.append(f"  {emoji} {name}: +{amt}")

    lines.append(f"{'═' * 44}")

    if attacker_wins:
        lines.append(f"@{attacker_name} now controls {node_name}.")
        lines.append(f"@{defender_name} has been ejected. 📩 Defender notified.")
    else:
        lines.append(f"@{defender_name} successfully defended {node_name}.")
        lines.append(f"@{attacker_name}'s troops were repelled.")

    return "\n".join(lines)


def get_march_by_id(user: dict, march_id: str) -> Optional[dict]:
    """Retrieve a specific march by ID."""
    for m in user.get("march_queue", []):
        if m.get("march_id") == march_id:
            return m
    return None


def get_active_marches(user: dict) -> List[dict]:
    """Get all marches currently in flight."""
    return [m for m in user.get("march_queue", []) if m.get("status") == "marching"]


def purge_old_marches(user: dict, keep_last: int = 20) -> dict:
    """
    Clean up old completed marches to prevent queue bloat.
    Keeps the most recent N completed entries for history.
    """
    queue = user.get("march_queue", [])
    active   = [m for m in queue if m.get("status") == "marching"]
    complete = [m for m in queue if m.get("status") != "marching"]
    complete = sorted(complete, key=lambda x: x.get("resolved_at", ""), reverse=True)
    user["march_queue"] = active + complete[:keep_last]
    return user
