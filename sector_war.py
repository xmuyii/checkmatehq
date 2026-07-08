# -*- coding: utf-8 -*-
"""
sector_war.py — Sector War Events
===================================
Server-wide timed conflicts between the two most dominant alliances.
Declared automatically when one alliance holds 3+ sectors simultaneously.

WAR TRIGGER:
  When any alliance controls the dominant position in 3 or more sectors
  at the same time, a Sector War is automatically declared against
  the second-highest dominant alliance. Server-wide announcement fires.

WAR MECHANICS:
  - Duration: 48 hours
  - Contested: all sectors where either alliance has presence
  - Scoring: node captures, player ejections, predator kills, objectives
  - Winner: higher war score at end of 48h
  - Loser penalty: all members banned from contested sectors for 24h
              + lose 50% of accumulated AP
  - Winner reward: sector tax doubled for 72h + 2000 AP + Chronicle mention

SECTOR WAR vs ALLIANCE WAR:
  Alliance War (Phase 3): declared manually, 24h, one sector contested
  Sector War (this file): triggered automatically, 48h, multiple sectors,
                          much higher stakes, server-wide event
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import random

# ═══════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

WAR_DURATION_HOURS      = 48
WAR_TRIGGER_SECTORS     = 3      # Sectors controlled to trigger war
WAR_FILE                = "sector_war.json"

WAR_SCORE_EVENTS = {
    "node_captured":      150,
    "node_held_10m":      50,
    "player_ejected":     75,
    "predator_kill":      100,
    "pvp_outpost_held":   200,
    "sector_dominated":   500,   # End a dominance cycle as top alliance
    "fortress_attacked":  125,
    "fortress_captured":  400,
}

WAR_OBJECTIVES = [
    {
        "id":    "first_blood",
        "name":  "First Blood",
        "desc":  "Win the first player battle of the war.",
        "score": 100,
        "once":  True,
    },
    {
        "id":    "hold_3_nodes",
        "name":  "Triple Grip",
        "desc":  "Hold 3 resource nodes simultaneously in a single sector.",
        "score": 300,
        "once":  True,
    },
    {
        "id":    "eject_10",
        "name":  "Mass Expulsion",
        "desc":  "Eject 10 enemy players across all sectors.",
        "score": 400,
        "once":  True,
    },
    {
        "id":    "survive_void",
        "name":  "Void Runners",
        "desc":  "Have 2 members survive a full Void Canyon phase without ejection.",
        "score": 350,
        "once":  True,
    },
    {
        "id":    "crypto_extract",
        "name":  "Crypto Heist",
        "desc":  "Extract 10,000 Satoshi from the Crypto Wastes.",
        "score": 300,
        "once":  True,
    },
    {
        "id":    "capture_fortress",
        "name":  "Castle Breaker",
        "desc":  "Capture an enemy private sector fortress.",
        "score": 500,
        "once":  True,
    },
]

GAMEMASTER_WAR_LINES = [
    "⚔️ *SECTOR WAR DECLARED* — {a} vs {b}\n"
    "The battle for dominance begins now. 48 hours. No mercy.",

    "🚨 *ALL COMMANDERS MOBILISE* — {a} and {b} are at war.\n"
    "Every sector is contested. Every node is a battlefield.",

    "💥 *THE GREAT WAR HAS STARTED* — {a} challenges {b}.\n"
    "Control the sectors. Break the enemy. 48 hours on the clock.",
]

GAMEMASTER_WAR_END_WIN = [
    "🏆 *{winner} HAS WON THE SECTOR WAR.*\n"
    "Their dominance is absolute. The enemy licks its wounds.",

    "👑 *VICTORY — {winner}.*\n"
    "48 hours of warfare ends with one alliance standing tall.",

    "⚔️ *THE WAR IS OVER. {winner} PREVAILS.*\n"
    "The Chronicle will record this. The defeated will not forget.",
]

GAMEMASTER_WAR_END_LOSS = [
    "💀 *{loser} has fallen in the Sector War.*\n"
    "Their members are banned. Their AP stripped. Regroup.",

    "🔴 *DEFEAT — {loser}.*\n"
    "The sectors belong to the enemy. For now.",
]


# ═══════════════════════════════════════════════════════════════════════════
#  WAR STATE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

def get_active_war() -> Optional[dict]:
    """Load active sector war from file. Returns None if no war active."""
    import json, os
    if not os.path.exists(WAR_FILE):
        return None
    try:
        with open(WAR_FILE) as f:
            war = json.load(f)
        if not war or war.get("status") != "active":
            return None
        # Check expiry
        try:
            exp = datetime.fromisoformat(war["expires_at"])
            if datetime.utcnow() > exp:
                war["status"] = "expired"
                _save_war(war)
                return None
        except Exception:
            pass
        return war
    except Exception:
        return None


def _save_war(war: dict):
    import json
    with open(WAR_FILE, "w") as f:
        json.dump(war, f, indent=2)


def declare_sector_war(
    alliance_a: dict,
    alliance_b: dict,
    contested_sector_ids: List[int],
    bot=None,
    supabase=None,
    DB_TABLE: str = "players",
) -> Tuple[bool, str, dict]:
    """
    Declare a Sector War between two alliances.
    Returns (success, announcement, war_state)
    """
    existing = get_active_war()
    if existing:
        return False, "A Sector War is already in progress.", {}

    now        = datetime.utcnow()
    expires_at = (now + timedelta(hours=WAR_DURATION_HOURS)).isoformat()

    war = {
        "status":           "active",
        "declared_at":      now.isoformat(),
        "expires_at":       expires_at,
        "alliance_a_id":    alliance_a.get("id"),
        "alliance_a_name":  alliance_a.get("name", "Alliance A"),
        "alliance_b_id":    alliance_b.get("id"),
        "alliance_b_name":  alliance_b.get("name", "Alliance B"),
        "contested_sectors": contested_sector_ids,
        "score_a":          0,
        "score_b":          0,
        "events":           [],
        "objectives_a":     {o["id"]: False for o in WAR_OBJECTIVES},
        "objectives_b":     {o["id"]: False for o in WAR_OBJECTIVES},
        "ejects_a":         0,
        "ejects_b":         0,
        "nodes_captured_a": 0,
        "nodes_captured_b": 0,
        "winner":           None,
    }

    _save_war(war)

    a_name = alliance_a.get("name", "?")
    b_name = alliance_b.get("name", "?")
    line   = random.choice(GAMEMASTER_WAR_LINES).format(a=a_name, b=b_name)

    return True, line, war


def record_war_event(
    alliance_id: str,
    event_type: str,
    player_name: str,
    detail: str,
    extra_score: int = 0,
) -> Optional[dict]:
    """
    Record a scoring event in the active war.
    Returns updated war state or None if no war.
    """
    war = get_active_war()
    if not war:
        return None

    base_score = WAR_SCORE_EVENTS.get(event_type, 0) + extra_score
    now        = datetime.utcnow()

    side = None
    if alliance_id == war.get("alliance_a_id"):
        side = "a"
    elif alliance_id == war.get("alliance_b_id"):
        side = "b"

    if side:
        war[f"score_{side}"] = war.get(f"score_{side}", 0) + base_score
        key = {"node_captured": f"nodes_captured_{side}",
               "player_ejected": f"ejects_{side}"}.get(event_type)
        if key:
            war[key] = war.get(key, 0) + 1

    war["events"].append({
        "time":         now.strftime("%H:%M"),
        "timestamp":    now.isoformat(),
        "alliance_id":  alliance_id,
        "side":         side or "?",
        "event_type":   event_type,
        "player_name":  player_name,
        "detail":       detail,
        "score":        base_score,
    })
    war["events"] = war["events"][-100:]

    # Check objectives
    _check_war_objectives(war, alliance_id, side, event_type)

    _save_war(war)
    return war


def _check_war_objectives(war: dict, alliance_id: str, side: Optional[str], event_type: str):
    """Check and complete war objectives based on events."""
    if not side:
        return

    obj_key = f"objectives_{side}"
    objs    = war.get(obj_key, {})

    if event_type == "player_ejected":
        ejects = war.get(f"ejects_{side}", 0)
        if ejects >= 10 and not objs.get("eject_10"):
            objs["eject_10"] = True
            war[f"score_{side}"] = war.get(f"score_{side}", 0) + 400

    if event_type == "node_captured":
        if not objs.get("first_blood"):
            if war.get("events") and len(war["events"]) <= 3:
                objs["first_blood"] = True
                war[f"score_{side}"] = war.get(f"score_{side}", 0) + 100

    if event_type == "fortress_captured" and not objs.get("capture_fortress"):
        objs["capture_fortress"] = True
        war[f"score_{side}"] = war.get(f"score_{side}", 0) + 500

    war[obj_key] = objs


def check_war_trigger(
    all_sector_states: List[dict],
    all_alliances: dict,
) -> Optional[Tuple[dict, dict, List[int]]]:
    """
    Check if a Sector War should be triggered.
    Returns (alliance_a, alliance_b, contested_sectors) or None.
    """
    if get_active_war():
        return None   # War already active

    # Count sectors dominated by each alliance
    alliance_sector_count: Dict[str, List[int]] = {}

    for ss in all_sector_states:
        sector_id = ss.get("sector_id")
        dom       = ss.get("dominance", {})
        ruler_id  = dom.get("ruler_id")
        if not ruler_id or not sector_id:
            continue

        # Find which alliance this ruler belongs to
        for aid, alliance in all_alliances.items():
            members = alliance.get("members", [])
            if ruler_id in members:
                if aid not in alliance_sector_count:
                    alliance_sector_count[aid] = []
                alliance_sector_count[aid].append(sector_id)
                break

    # Find alliances with WAR_TRIGGER_SECTORS or more
    qualified = {
        aid: sectors
        for aid, sectors in alliance_sector_count.items()
        if len(sectors) >= WAR_TRIGGER_SECTORS
    }

    if len(qualified) < 1:
        return None

    # Sort by sector count descending
    sorted_q = sorted(qualified.items(), key=lambda x: len(x[1]), reverse=True)

    if len(sorted_q) >= 2:
        a_id, a_sectors = sorted_q[0]
        b_id, b_sectors = sorted_q[1]
    elif len(sorted_q) == 1:
        # Top alliance vs second-highest overall
        a_id, a_sectors = sorted_q[0]
        # Find second alliance
        remaining = {
            aid: cnt
            for aid, cnt in alliance_sector_count.items()
            if aid != a_id
        }
        if not remaining:
            return None
        b_id = max(remaining, key=lambda k: len(remaining[k]))
        b_sectors = remaining[b_id]
    else:
        return None

    if a_id == b_id:
        return None

    a_alliance = all_alliances.get(a_id, {"id": a_id, "name": "Alliance A"})
    b_alliance = all_alliances.get(b_id, {"id": b_id, "name": "Alliance B"})
    contested  = list(set(a_sectors + b_sectors))

    return a_alliance, b_alliance, contested


def resolve_war(
    supabase,
    DB_TABLE: str = "players",
    all_alliances: dict = None,
    save_alliance_fn=None,
    broadcast_fn=None,
) -> Optional[dict]:
    """
    Resolve the active war. Called by scheduler when timer expires.
    Returns final war state or None.
    """
    war = get_active_war()
    if not war:
        return None

    score_a = war.get("score_a", 0)
    score_b = war.get("score_b", 0)
    a_name  = war.get("alliance_a_name", "Alliance A")
    b_name  = war.get("alliance_b_name", "Alliance B")
    a_id    = war.get("alliance_a_id")
    b_id    = war.get("alliance_b_id")

    if score_a >= score_b:
        winner_id, winner_name = a_id, a_name
        loser_id,  loser_name  = b_id, b_name
    else:
        winner_id, winner_name = b_id, b_name
        loser_id,  loser_name  = a_id, a_name

    war["status"] = "completed"
    war["winner"] = winner_id
    war["resolved_at"] = datetime.utcnow().isoformat()
    _save_war(war)

    # Apply penalties to loser's members
    if all_alliances and save_alliance_fn:
        loser_alliance = all_alliances.get(loser_id, {})
        loser_members  = loser_alliance.get("members", [])
        ban_expires    = (datetime.utcnow() + timedelta(hours=24)).isoformat()

        for pid in loser_members:
            try:
                r = supabase.table(DB_TABLE).select("*").eq("user_id", pid).execute()
                if not r.data:
                    continue
                from supabase_db import normalize_user
                puser = normalize_user(r.data[0])

                # Ban from contested sectors
                bans = puser.get("banishments", {}) or {}
                for sid in war.get("contested_sectors", []):
                    bans[str(sid)] = {
                        "expires_at":     ban_expires,
                        "issued_by_id":   "WAR_SYSTEM",
                        "issued_by_name": f"Sector War vs {winner_name}",
                        "sector_id":      sid,
                        "issued_at":      datetime.utcnow().isoformat(),
                    }
                puser["banishments"] = bans

                # Strip 50% AP
                current_ap   = puser.get("alliance_points", 0)
                puser["alliance_points"] = current_ap // 2

                puser["pending_notification"] = (
                    f"💀 *SECTOR WAR LOST*\n"
                    f"{loser_name} was defeated by {winner_name}.\n"
                    f"You are banned from contested sectors for 24h.\n"
                    f"Alliance Points reduced by 50%."
                )

                supabase.table(DB_TABLE).update(puser).eq("user_id", pid).execute()
            except Exception as e:
                print(f"[WAR] Penalty error for {pid}: {e}")

        # Winner: double tax for 72h + 2000 AP
        winner_alliance = all_alliances.get(winner_id, {})
        winner_alliance["alliance_points"] = (
            winner_alliance.get("alliance_points", 0) + 2000
        )
        winner_alliance["war_tax_bonus_expires"] = (
            datetime.utcnow() + timedelta(hours=72)
        ).isoformat()
        if save_alliance_fn:
            save_alliance_fn(winner_alliance)

    # Broadcast result
    if broadcast_fn:
        win_line  = random.choice(GAMEMASTER_WAR_END_WIN).format(winner=winner_name)
        loss_line = random.choice(GAMEMASTER_WAR_END_LOSS).format(loser=loser_name)
        broadcast_fn(f"{win_line}\n\n{loss_line}")

    return war


def is_in_war(alliance_id: str) -> bool:
    """Check if an alliance is currently in a Sector War."""
    war = get_active_war()
    if not war:
        return False
    return alliance_id in (war.get("alliance_a_id"), war.get("alliance_b_id"))


def get_war_side(alliance_id: str) -> Optional[str]:
    """Returns 'a', 'b', or None."""
    war = get_active_war()
    if not war:
        return None
    if alliance_id == war.get("alliance_a_id"):
        return "a"
    if alliance_id == war.get("alliance_b_id"):
        return "b"
    return None


# ═══════════════════════════════════════════════════════════════════════════
#  DISPLAY FORMATTERS
# ═══════════════════════════════════════════════════════════════════════════

def format_war_scoreboard(war: dict, alliance_id: str = None) -> str:
    """Format the live war scoreboard."""
    if not war:
        return "⚔️ No active Sector War."

    a_name  = war.get("alliance_a_name", "Alliance A")
    b_name  = war.get("alliance_b_name", "Alliance B")
    score_a = war.get("score_a", 0)
    score_b = war.get("score_b", 0)
    a_id    = war.get("alliance_a_id")

    my_side    = get_war_side(alliance_id) if alliance_id else None
    leading    = "a" if score_a >= score_b else "b"

    try:
        exp      = datetime.fromisoformat(war["expires_at"])
        rem      = exp - datetime.utcnow()
        hours    = max(0, int(rem.total_seconds() // 3600))
        mins     = max(0, int((rem.total_seconds() % 3600) // 60))
        time_str = f"{hours}h {mins}m"
    except Exception:
        time_str = "?"

    # Score bar
    total    = max(score_a + score_b, 1)
    a_pct    = int(score_a / total * 20)
    b_pct    = 20 - a_pct
    bar      = "█" * a_pct + "░" * b_pct

    lines = [
        f"⚔️ *SECTOR WAR*",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"{'🏆' if leading=='a' else '  '} *{a_name}*: {score_a:,}",
        f"[{bar}]",
        f"{'🏆' if leading=='b' else '  '} *{b_name}*: {score_b:,}",
        f"\n⏱️ Ends in: *{time_str}*",
    ]

    # Contested sectors
    sectors = war.get("contested_sectors", [])
    if sectors:
        from teleport_system import SECTOR_QUICK_INFO
        sector_names = []
        for sid in sectors[:5]:
            info = SECTOR_QUICK_INFO.get(sid, {})
            sector_names.append(f"{info.get('emoji','🌍')} {info.get('name', f'S{sid}')}")
        lines.append(f"\n🗺️ Contested: {', '.join(sector_names)}")

    # Objectives
    if my_side:
        my_objs   = war.get(f"objectives_{my_side}", {})
        them_side = "b" if my_side == "a" else "a"
        them_objs = war.get(f"objectives_{them_side}", {})
        lines.append(f"\n🎯 *OBJECTIVES:*")
        for obj in WAR_OBJECTIVES:
            oid       = obj["id"]
            my_done   = my_objs.get(oid, False)
            them_done = them_objs.get(oid, False)
            icon      = "✅" if my_done else ("❌" if them_done else "☐")
            lines.append(f"  {icon} {obj['name']} (+{obj['score']}) — {obj['desc']}")

    # Recent events
    events = war.get("events", [])[-8:]
    if events:
        lines.append(f"\n📜 *RECENT EVENTS:*")
        for e in reversed(events):
            t     = e.get("time", "?")
            pname = e.get("player_name", "?")
            detail = e.get("detail", "")
            score  = e.get("score", 0)
            side   = e.get("side", "?")
            icon   = "🟢" if (my_side and side == my_side) else "🔴"
            lines.append(f"  {icon} [{t}] @{pname}: {detail} (+{score})")

    lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def format_war_history(war: dict) -> str:
    """Format a completed war for the Chronicle."""
    if not war:
        return ""

    a_name  = war.get("alliance_a_name", "?")
    b_name  = war.get("alliance_b_name", "?")
    score_a = war.get("score_a", 0)
    score_b = war.get("score_b", 0)
    winner  = war.get("winner")
    a_id    = war.get("alliance_a_id")

    winner_name = a_name if winner == a_id else b_name
    loser_name  = b_name if winner == a_id else a_name
    winner_score = max(score_a, score_b)
    loser_score  = min(score_a, score_b)

    declared = war.get("declared_at", "")[:10]

    return (
        f"⚔️ *Sector War* — {declared}\n"
        f"🏆 {winner_name} defeated {loser_name}\n"
        f"Score: {winner_score:,} vs {loser_score:,}"
    )


# ═══════════════════════════════════════════════════════════════════════════
#  INLINE KEYBOARDS
# ═══════════════════════════════════════════════════════════════════════════

def kb_war_scoreboard(war: dict, alliance_id: str = None) -> InlineKeyboardMarkup:
    """War scoreboard keyboard."""
    my_side = get_war_side(alliance_id) if alliance_id else None
    buttons = [
        [
            InlineKeyboardButton(text="📊 Full Scores",   callback_data="war:scores"),
            InlineKeyboardButton(text="📜 Event Log",     callback_data="war:events"),
        ],
        [
            InlineKeyboardButton(text="🎯 Objectives",    callback_data="war:objectives"),
        ],
    ]

    if my_side:
        contested = war.get("contested_sectors", [])
        for sid in contested[:3]:
            from teleport_system import SECTOR_QUICK_INFO
            info = SECTOR_QUICK_INFO.get(sid, {})
            name = info.get("name", f"S{sid}")
            buttons.append([InlineKeyboardButton(
                text=f"🌍 Go to {name}",
                callback_data=f"teleport:go:{sid}"
            )])

    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="menu_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
