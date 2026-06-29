# -*- coding: utf-8 -*-
"""
alliance_war.py + bounty_system.py — Combined Phase 3 File
============================================================
Two systems that share a lot of context so kept together.

ALLIANCE WAR:
  Alliance leaders declare war. Members see a War Room dashboard
  inside the bot DM — not in Telegram groups. Communication is
  anonymous (game names only, no Telegram identities revealed).
  Leader issues stream-of-consciousness commands visible to all members.
  War lasts 24h. Winner by score. Loser banned from contested sector 24h.

BOUNTY BOARD:
  Players appear on the bounty board through specific triggers.
  Bounty hunters can claim bounties by defeating the target.
  Home sector is revealed when a bounty is placed on a player.
  Bitcoin Whale tag makes rich players permanently visible.
  The board is the game's newspaper — everyone reads it for intel.

INLINE KEYBOARD PATTERN:
  All interactions use InlineKeyboardMarkup.
  callback_data format: "system:action:param"
  Commands are secondary — keyboards are primary.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import random

# ═══════════════════════════════════════════════════════════════════════════
#  ALLIANCE WAR CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

WAR_DURATION_HOURS    = 24
WAR_DECLARATION_COST  = {"alliance_points": 1000}
WAR_MIN_MEMBERS       = 3      # Alliance needs at least 3 members to declare war
WAR_SCORE_SOURCES     = {
    "node_captured":    100,
    "player_ejected":   50,
    "objective_minor":  150,
    "objective_major":  300,
    "first_blood":      50,
    "outpost_held_30m": 200,
    "sector_controlled": 500,  # Hold 3+ nodes simultaneously
}

OBJECTIVES = [
    {
        "id":        "control_3_nodes",
        "name":      "Control 3 Nodes",
        "desc":      "Hold 3 resource nodes in the contested sector simultaneously",
        "score":     WAR_SCORE_SOURCES["objective_minor"],
        "type":      "major",
        "repeatable": False,
    },
    {
        "id":        "eject_5_enemies",
        "name":      "Eject 5 Enemies",
        "desc":      "Eject 5 enemy alliance members from any sector",
        "score":     WAR_SCORE_SOURCES["objective_major"],
        "type":      "major",
        "repeatable": False,
    },
    {
        "id":        "hold_outpost",
        "name":      "Hold the Outpost",
        "desc":      "Hold the contested sector's PvP outpost for 30 continuous minutes",
        "score":     WAR_SCORE_SOURCES["outpost_held_30m"],
        "type":      "major",
        "repeatable": False,
    },
    {
        "id":        "first_blood",
        "name":      "First Blood",
        "desc":      "Win the first battle of the war",
        "score":     WAR_SCORE_SOURCES["first_blood"],
        "type":      "minor",
        "repeatable": False,
    },
    {
        "id":        "collect_1000",
        "name":      "Resource Run",
        "desc":      "Collect 1000 total resources from the contested sector",
        "score":     WAR_SCORE_SOURCES["objective_minor"],
        "type":      "minor",
        "repeatable": False,
    },
]


# ═══════════════════════════════════════════════════════════════════════════
#  WAR DECLARATION & MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

def declare_war(
    declaring_alliance_id: str,
    declaring_alliance: dict,
    target_alliance_id: str,
    target_alliance_name: str,
    contested_sector_id: int,
    leader_user: dict,
    alliances: dict,
    broadcast_fn,
) -> Tuple[bool, str, dict]:
    """
    Declare war on another alliance.
    Returns (success, message, updated_declaring_alliance)
    """
    role = leader_user.get("alliance_role", "MEMBER")
    if role != "LEADER":
        return False, "❌ Only the alliance leader can declare war.", declaring_alliance

    # Check member count
    members = declaring_alliance.get("members", [])
    if len(members) < WAR_MIN_MEMBERS:
        return False, (
            f"❌ Need at least {WAR_MIN_MEMBERS} members to declare war.\n"
            f"Current members: {len(members)}"
        ), declaring_alliance

    # Check AP cost
    alliance_ap = declaring_alliance.get("alliance_points", 0)
    ap_cost     = WAR_DECLARATION_COST["alliance_points"]
    if alliance_ap < ap_cost:
        return False, (
            f"❌ Need {ap_cost} Alliance Points to declare war.\n"
            f"Current AP: {alliance_ap}"
        ), declaring_alliance

    # Check not already at war
    if declaring_alliance.get("active_war"):
        return False, "❌ Already engaged in an active war.", declaring_alliance

    # Deduct AP
    declaring_alliance["alliance_points"] = alliance_ap - ap_cost

    # Set up war
    war_id      = f"war_{int(datetime.utcnow().timestamp())}_{declaring_alliance_id[:6]}"
    expires_at  = (datetime.utcnow() + timedelta(hours=WAR_DURATION_HOURS)).isoformat()

    war_data = {
        "war_id":             war_id,
        "attacker_id":        declaring_alliance_id,
        "attacker_name":      declaring_alliance.get("name", "Unknown"),
        "defender_id":        target_alliance_id,
        "defender_name":      target_alliance_name,
        "contested_sector":   contested_sector_id,
        "declared_at":        datetime.utcnow().isoformat(),
        "expires_at":         expires_at,
        "status":             "active",
        "attacker_score":     0,
        "defender_score":     0,
        "objectives":         {obj["id"]: {"completed_by": None} for obj in OBJECTIVES},
        "first_blood":        False,
        "command_stream":     [],   # Leader commands shown in war room
        "battle_log":         [],   # All combat events
        "attacker_resources_collected": 0,
        "defender_resources_collected": 0,
        "attacker_ejects":    0,
        "defender_ejects":    0,
    }

    declaring_alliance["active_war"] = war_data

    # Notify target alliance
    target_alliance = alliances.get(target_alliance_id, {})
    target_alliance["active_war"] = {**war_data, "role": "defender"}
    alliances[target_alliance_id] = target_alliance

    from teleport_system import SECTOR_QUICK_INFO
    sector_info  = SECTOR_QUICK_INFO.get(contested_sector_id, {})
    sector_name  = sector_info.get("name", f"Sector {contested_sector_id}")
    sector_emoji = sector_info.get("emoji", "🌍")

    announce = (
        f"⚔️ *WAR DECLARED!*\n"
        f"*{declaring_alliance.get('name')}* vs *{target_alliance_name}*\n"
        f"Contested sector: {sector_emoji} {sector_name}\n"
        f"Duration: {WAR_DURATION_HOURS} hours\n"
        f"All members: check your War Room dashboard."
    )
    broadcast_fn(announce)

    return True, (
        f"⚔️ *War declared on {target_alliance_name}!*\n"
        f"Contested: {sector_emoji} {sector_name}\n"
        f"Duration: {WAR_DURATION_HOURS}h\n"
        f"Open your War Room: tap the button below."
    ), declaring_alliance


def issue_war_command(
    leader_user: dict,
    alliance: dict,
    command_text: str,
    edit_last: bool = False,
) -> Tuple[bool, str, dict]:
    """
    Leader issues a command visible to all alliance members in war room.
    Commands are timestamped and numbered.
    edit_last=True replaces the most recent command (shows EDITED tag).
    """
    role = leader_user.get("alliance_role", "MEMBER")
    if role not in ("LEADER", "OFFICER"):
        return False, "❌ Only leaders and officers can issue war commands.", alliance

    war = alliance.get("active_war")
    if not war or war.get("status") != "active":
        return False, "❌ No active war.", alliance

    stream = war.get("command_stream", [])
    if not isinstance(stream, list):
        stream = []

    now      = datetime.utcnow()
    time_str = now.strftime("%H:%M")

    if edit_last and stream:
        # Edit the last command
        stream[-1]["text"]   = command_text
        stream[-1]["edited"] = True
        stream[-1]["edited_at"] = time_str
        msg = f"✏️ Last command updated."
    else:
        cmd_num = len(stream) + 1
        stream.append({
            "num":        cmd_num,
            "text":       command_text,
            "time_str":   time_str,
            "timestamp":  now.isoformat(),
            "issued_by":  leader_user.get("username", "Leader"),
            "edited":     False,
            "acks":       [],   # Members who acknowledged
        })
        msg = f"📋 Command #{cmd_num} issued."

    war["command_stream"] = stream[-20:]   # Keep last 20 commands
    alliance["active_war"] = war

    return True, msg, alliance


def acknowledge_command(
    member_user: dict,
    alliance: dict,
    cmd_num: int,
) -> Tuple[bool, str, dict]:
    """Member acknowledges receiving a command."""
    war    = alliance.get("active_war")
    if not war:
        return False, "No active war.", alliance

    stream = war.get("command_stream", [])
    for cmd in stream:
        if cmd.get("num") == cmd_num:
            acks = cmd.get("acks", [])
            pid  = member_user.get("user_id")
            if pid not in acks:
                acks.append(pid)
                cmd["acks"] = acks
            alliance["active_war"]["command_stream"] = stream
            return True, f"✅ Command #{cmd_num} acknowledged.", alliance

    return False, f"Command #{cmd_num} not found.", alliance


def record_war_event(
    alliance: dict,
    event_type: str,
    player_name: str,
    detail: str,
    side: str,  # "attacker" or "defender"
) -> dict:
    """Record a combat event in the war log and update scores."""
    war = alliance.get("active_war")
    if not war:
        return alliance

    score    = WAR_SCORE_SOURCES.get(event_type, 0)
    score_key = f"{side}_score"
    war[score_key] = war.get(score_key, 0) + score

    now = datetime.utcnow()
    war["battle_log"].append({
        "time":        now.strftime("%H:%M"),
        "timestamp":   now.isoformat(),
        "event_type":  event_type,
        "player_name": player_name,
        "detail":      detail,
        "side":        side,
        "score_earned": score,
    })
    war["battle_log"] = war["battle_log"][-50:]   # Keep last 50

    # Check objectives
    _check_objectives(war, event_type, player_name, side)

    # First blood
    if event_type in ("node_captured", "player_ejected") and not war.get("first_blood"):
        war["first_blood"] = side
        war[score_key]     += WAR_SCORE_SOURCES["first_blood"]

    alliance["active_war"] = war
    return alliance


def _check_objectives(war: dict, event_type: str, player_name: str, side: str):
    """Check and complete war objectives based on events."""
    objs = war.get("objectives", {})

    if event_type == "player_ejected":
        eject_key = f"{side}_ejects"
        war[eject_key] = war.get(eject_key, 0) + 1
        if war[eject_key] >= 5 and not objs.get("eject_5_enemies", {}).get("completed_by"):
            objs["eject_5_enemies"] = {"completed_by": side, "completed_at": datetime.utcnow().isoformat()}
            score_key = f"{side}_score"
            war[score_key] = war.get(score_key, 0) + WAR_SCORE_SOURCES["objective_major"]

    if not objs.get("first_blood", {}).get("completed_by") and event_type in ("node_captured", "player_ejected"):
        if war.get("first_blood"):
            objs["first_blood"] = {"completed_by": side, "completed_at": datetime.utcnow().isoformat()}

    war["objectives"] = objs


def resolve_war(
    alliance: dict,
    opponent_alliance: dict,
    sector_id: int,
    save_user_fn,
    broadcast_fn,
    log_fn,
) -> Tuple[str, dict, dict]:
    """
    Called when war timer expires. Determines winner, applies penalties.
    Returns (result_message, updated_alliance, updated_opponent)
    """
    war = alliance.get("active_war", {})
    atk_score = war.get("attacker_score", 0)
    def_score = war.get("defender_score", 0)
    atk_name  = war.get("attacker_name", "Attacker")
    def_name  = war.get("defender_name", "Defender")

    if atk_score >= def_score:
        winner_name  = atk_name
        loser_name   = def_name
        loser_alliance = opponent_alliance
    else:
        winner_name  = def_name
        loser_name   = atk_name
        loser_alliance = alliance

    # Loser: all members banned from contested sector 24h
    loser_members = loser_alliance.get("members", [])
    ban_expires   = (datetime.utcnow() + timedelta(hours=24)).isoformat()

    for pid in loser_members:
        user = save_user_fn(pid, None)
        if user:
            if "banishments" not in user or not isinstance(user.get("banishments"), dict):
                user["banishments"] = {}
            user["banishments"][str(sector_id)] = {
                "expires_at":     ban_expires,
                "issued_by_id":   "WAR_SYSTEM",
                "issued_by_name": f"War vs {winner_name}",
                "sector_id":      sector_id,
                "issued_at":      datetime.utcnow().isoformat(),
            }
            user["pending_notification"] = (
                f"⚔️ *War Lost — Sector {sector_id} Banned*\n"
                f"*{loser_name}* lost the war against *{winner_name}*.\n"
                f"You are banned from Sector {sector_id} for 24 hours."
            )
            save_user_fn(pid, user)

    # Winner: alliance AP bonus + trophy
    winner_alliance = opponent_alliance if loser_alliance is alliance else alliance
    bonus_ap = 500
    winner_alliance["alliance_points"] = winner_alliance.get("alliance_points", 0) + bonus_ap

    from teleport_system import SECTOR_QUICK_INFO
    sector_info  = SECTOR_QUICK_INFO.get(sector_id, {})
    sector_name  = sector_info.get("name", f"Sector {sector_id}")
    sector_emoji = sector_info.get("emoji", "🌍")

    result_msg = (
        f"⚔️ *WAR OVER — {sector_emoji} {sector_name}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 WINNER: *{winner_name}*\n"
        f"   Score: {max(atk_score, def_score)}\n\n"
        f"💀 LOSER: *{loser_name}*\n"
        f"   Score: {min(atk_score, def_score)}\n"
        f"   Penalty: 24h ban from {sector_name}\n\n"
        f"*{winner_name}* receives +{bonus_ap} Alliance Points"
    )

    broadcast_fn(result_msg)
    log_fn(sector_id, f"⚔️ War ended — {winner_name} defeated {loser_name}")

    # Clear war data
    alliance["active_war"]          = None
    opponent_alliance["active_war"] = None

    return result_msg, alliance, opponent_alliance


# ═══════════════════════════════════════════════════════════════════════════
#  WAR ROOM DISPLAY & KEYBOARDS
# ═══════════════════════════════════════════════════════════════════════════

def format_war_room(
    user: dict,
    alliance: dict,
    is_leader: bool = False,
) -> str:
    """
    Full war room dashboard. Shown in DM — not in Telegram groups.
    This is the secure command center.
    """
    war       = alliance.get("active_war")
    if not war or war.get("status") != "active":
        return "⚔️ *WAR ROOM*\n\nNo active war. Your alliance is at peace."

    atk_name  = war.get("attacker_name", "?")
    def_name  = war.get("defender_name", "?")
    atk_score = war.get("attacker_score", 0)
    def_score = war.get("defender_score", 0)
    alliance_name = alliance.get("name", "Your Alliance")

    try:
        expires   = datetime.fromisoformat(war["expires_at"])
        remaining = expires - datetime.utcnow()
        hours     = int(remaining.total_seconds() // 3600)
        mins      = int((remaining.total_seconds() % 3600) // 60)
        time_str  = f"{hours}h {mins}m"
    except Exception:
        time_str  = "?"

    # Determine our side
    is_attacker = war.get("attacker_id") == alliance.get("id")
    our_score   = atk_score if is_attacker else def_score
    their_score = def_score if is_attacker else atk_score
    our_name    = atk_name if is_attacker else def_name
    their_name  = def_name if is_attacker else atk_name
    winning     = our_score >= their_score

    from teleport_system import SECTOR_QUICK_INFO
    sector_id   = war.get("contested_sector", 1)
    sector_info = SECTOR_QUICK_INFO.get(sector_id, {})
    sector_name = sector_info.get("name", f"Sector {sector_id}")

    lines = [
        f"⚔️ *WAR ROOM — {alliance_name.upper()}*",
        f"{'═' * 40}",
        f"vs *{their_name}*  |  Ends: {time_str}",
        f"Contested: {sector_info.get('emoji','🌍')} {sector_name}",
        f"",
        f"📊 *SCORE:*",
        f"  {'✅' if winning else '❌'} {our_name}: *{our_score}*",
        f"  {'❌' if winning else '✅'} {their_name}: *{their_score}*",
        f"",
    ]

    # Command stream — last 8 commands
    stream = war.get("command_stream", [])
    if stream:
        lines.append("📋 *COMMAND STREAM:*")
        for cmd in stream[-8:]:
            edited  = " [EDITED]" if cmd.get("edited") else ""
            ack_cnt = len(cmd.get("acks", []))
            lines.append(
                f"  [{cmd.get('time_str','??:??')}] *#{cmd.get('num','?')}*{edited} "
                f"— {cmd.get('text','')}"
                f" ✓{ack_cnt}"
            )
        lines.append("")

    # Objectives
    objectives = war.get("objectives", {})
    lines.append("🎯 *OBJECTIVES:*")
    for obj in OBJECTIVES:
        obj_data = objectives.get(obj["id"], {})
        completed_by = obj_data.get("completed_by")
        if completed_by == ("attacker" if is_attacker else "defender"):
            status = f"✅ WE DID IT (+{obj['score']})"
        elif completed_by:
            status = f"❌ ENEMY COMPLETED"
        else:
            status = f"☐ {obj['desc']}"
        lines.append(f"  {status}")
        if not completed_by:
            lines.append(f"     +{obj['score']} pts")

    lines.append("")

    # Recent battle log (last 5 entries)
    battle_log = war.get("battle_log", [])
    if battle_log:
        lines.append("📜 *RECENT EVENTS:*")
        for entry in battle_log[-5:]:
            side_icon = "🟢" if entry.get("side") == ("attacker" if is_attacker else "defender") else "🔴"
            lines.append(
                f"  {side_icon} [{entry.get('time','?')}] "
                f"@{entry.get('player_name','?')}: {entry.get('detail','')}"
            )

    lines.append(f"{'═' * 40}")
    return "\n".join(lines)


def kb_war_room(alliance: dict, user: dict) -> InlineKeyboardMarkup:
    """War room action keyboard."""
    war       = alliance.get("active_war", {})
    is_leader = user.get("alliance_role") in ("LEADER", "OFFICER")
    buttons   = []

    # Score and status
    buttons.append([
        InlineKeyboardButton("📊 Scores",       callback_data="war:scores"),
        InlineKeyboardButton("📜 Battle Log",   callback_data="war:battle_log"),
    ])

    # Objectives
    buttons.append([
        InlineKeyboardButton("🎯 Objectives",   callback_data="war:objectives"),
        InlineKeyboardButton("📋 Commands",     callback_data="war:commands"),
    ])

    # Leader commands
    if is_leader:
        buttons.append([
            InlineKeyboardButton("📣 Issue Command",  callback_data="war:issue_command"),
            InlineKeyboardButton("✏️ Edit Last",      callback_data="war:edit_last"),
        ])

    # Member actions
    buttons.append([
        InlineKeyboardButton("✅ Ack Command",  callback_data="war:ack_menu"),
        InlineKeyboardButton("🔭 Scout Enemy", callback_data="war:scout"),
    ])

    buttons.append([
        InlineKeyboardButton("🗺️ Contested Sector",
                             callback_data=f"sector:dashboard:{war.get('contested_sector',1)}"),
    ])
    buttons.append([InlineKeyboardButton("« Back to Dashboard", callback_data="base:dashboard")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_issue_command_confirm(command_text: str) -> InlineKeyboardMarkup:
    """Confirm before issuing a war command."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(f"📣 Issue: '{command_text[:30]}...'",
                              callback_data=f"war:cmd_confirm:{command_text[:50]}")],
        [InlineKeyboardButton("✗ Cancel", callback_data="war:room")],
    ])


# ═══════════════════════════════════════════════════════════════════════════
#  BOUNTY BOARD SYSTEM
# ═══════════════════════════════════════════════════════════════════════════

BOUNTY_DURATION_HOURS    = 48
BOUNTY_MIN_REWARD        = 50    # Gold minimum
BITCOIN_WHALE_THRESHOLD  = 0.01  # BTC — above this = Bitcoin Whale tag
SHIELD_DOWN_HOURS        = 4     # Hours unshielded before appearing on board


def should_appear_on_bounty_board(user: dict) -> Tuple[bool, str]:
    """
    Determine if a player should appear on the bounty board.
    Returns (should_appear, reason)
    """
    # Unshielded for too long
    shield_exp = user.get("shield_expires_at")
    if shield_exp:
        try:
            exp = datetime.fromisoformat(shield_exp)
            if datetime.utcnow() > exp:
                hours_down = (datetime.utcnow() - exp).total_seconds() / 3600
                if hours_down >= SHIELD_DOWN_HOURS:
                    return True, f"unshielded_{int(hours_down)}h"
        except Exception:
            pass
    elif not user.get("base_shielded"):
        # Never had a shield — always visible
        return True, "never_shielded"

    # Bitcoin Whale
    inv = user.get("inventory", {})
    if isinstance(inv, dict):
        btc = inv.get("bitcoin", {})
        if isinstance(btc, dict) and btc.get("qty", 0) >= BITCOIN_WHALE_THRESHOLD:
            return True, "bitcoin_whale"

    # Sector Ruler (always visible)
    # This is checked separately in the board formatter

    return False, ""


def place_bounty(
    poster_user: dict,
    target_id: str,
    target_name: str,
    target_home_sector: Optional[int],
    reward_gold: int,
    reason: str,
    save_bounty_fn,  # callable(bounty_data) stores to bounty_board table
) -> Tuple[bool, str, dict]:
    """
    Player manually places a bounty on another player.
    Costs the poster the reward amount. Reveals target home sector.
    Returns (success, message, updated_poster_user)
    """
    if reward_gold < BOUNTY_MIN_REWARD:
        return False, f"❌ Minimum bounty is {BOUNTY_MIN_REWARD} 🪙.", poster_user

    inv        = poster_user.get("inventory", {})
    gold_held  = inv.get("gold", {}).get("qty", 0) if isinstance(inv, dict) else 0

    if gold_held < reward_gold:
        return False, f"❌ Not enough gold. Have {gold_held} 🪙, need {reward_gold} 🪙.", poster_user

    # Deduct gold
    if isinstance(inv, dict):
        if "gold" in inv:
            inv["gold"]["qty"] = gold_held - reward_gold
        poster_user["inventory"] = inv

    bounty_id  = f"bounty_{int(datetime.utcnow().timestamp())}_{target_id[-4:]}"
    expires_at = (datetime.utcnow() + timedelta(hours=BOUNTY_DURATION_HOURS)).isoformat()

    bounty = {
        "bounty_id":          bounty_id,
        "target_id":          target_id,
        "target_name":        target_name,
        "target_home_sector": target_home_sector,
        "posted_by_id":       poster_user.get("user_id"),
        "posted_by_name":     poster_user.get("username", "Unknown"),
        "reward_gold":        reward_gold,
        "reason":             reason,
        "posted_at":          datetime.utcnow().isoformat(),
        "expires_at":         expires_at,
        "claimed_by_id":      None,
        "claimed_at":         None,
        "status":             "active",
    }

    save_bounty_fn(bounty)

    return True, (
        f"🎯 *Bounty posted on @{target_name}!*\n"
        f"Reward: {reward_gold} 🪙\n"
        f"Reason: {reason}\n"
        f"Expires: {BOUNTY_DURATION_HOURS}h\n"
        f"{'Home sector revealed to all hunters.' if target_home_sector else ''}"
    ), poster_user


def claim_bounty(
    hunter_user: dict,
    bounty_id: str,
    target_user: dict,
    sector_id: int,
    get_bounty_fn,
    save_bounty_fn,
    save_user_fn,
    log_fn,
) -> Tuple[bool, str, dict]:
    """
    Hunter claims a bounty after defeating the target.
    Target must be in same sector as hunter and have been defeated.
    """
    bounty = get_bounty_fn(bounty_id)
    if not bounty:
        return False, "❌ Bounty not found or expired.", hunter_user

    if bounty.get("status") != "active":
        return False, "❌ Bounty already claimed or expired.", hunter_user

    if bounty.get("target_id") != target_user.get("user_id"):
        return False, "❌ Wrong target.", hunter_user

    # Verify target was just defeated (check battle was recent — within 5 minutes)
    # In practice this is called right after a successful battle
    reward = bounty.get("reward_gold", 0)
    inv    = hunter_user.get("inventory", {})
    if not isinstance(inv, dict):
        inv = {}

    if "gold" in inv:
        inv["gold"]["qty"] = inv["gold"].get("qty", 0) + reward
    else:
        inv["gold"] = {"qty": reward, "display": "Gold", "emoji": "🪙", "category": "premium"}

    hunter_user["inventory"] = inv

    # Mark bounty claimed
    bounty["status"]       = "claimed"
    bounty["claimed_by_id"] = hunter_user.get("user_id")
    bounty["claimed_at"]   = datetime.utcnow().isoformat()
    save_bounty_fn(bounty)

    # Notify target
    target_user["pending_notification"] = (
        f"🎯 *BOUNTY CLAIMED ON YOU*\n"
        f"@{hunter_user.get('username','Unknown')} collected a bounty after defeating you.\n"
        f"Bounty value: {reward} 🪙"
    )
    save_user_fn(target_user.get("user_id"), target_user)

    log_fn(sector_id, f"🎯 @{hunter_user.get('username','?')} claimed bounty on @{target_user.get('username','?')}")

    return True, (
        f"🎯 *BOUNTY CLAIMED!*\n"
        f"Target: @{target_user.get('username','Unknown')}\n"
        f"Reward: +{reward} 🪙 added to your inventory.\n"
        f"Well hunted."
    ), hunter_user


def format_bounty_board(
    active_bounties: List[dict],
    auto_visible_players: List[dict],   # Players auto-appearing (unshielded, rulers, whales)
    viewing_user: dict,
) -> str:
    """
    Format the bounty board display.
    This is the game's newspaper — everyone reads it for intel.
    """
    lines = [
        "🎯 *BOUNTY BOARD*",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    # Auto-visible players (system-generated entries, no reward)
    if auto_visible_players:
        lines.append("\n👁️ *VISIBLE TARGETS* (no bounty — intel only)")
        for player in auto_visible_players[:5]:
            reason         = player.get("board_reason", "")
            home_sector    = player.get("home_sector")
            home_info      = {}
            if home_sector:
                from teleport_system import SECTOR_QUICK_INFO
                home_info = SECTOR_QUICK_INFO.get(home_sector, {})

            name       = player.get("username", "Unknown")
            home_str   = f"  🏠 {home_info.get('emoji','')} {home_info.get('name',f'S{home_sector}')}" if home_sector else ""

            if "bitcoin_whale" in reason:
                inv    = player.get("inventory", {})
                btc    = inv.get("bitcoin", {}).get("qty", 0) if isinstance(inv, dict) else 0
                tag    = f"₿ BITCOIN WHALE ({btc:.4f} BTC)"
                lines.append(f"  💰 @{name} — {tag}{home_str}")
            elif "unshielded" in reason:
                hrs  = reason.split("_")[1].replace("h","") if "_" in reason else "?"
                tag  = f"🔓 UNSHIELDED ({hrs}h)"
                lines.append(f"  🔓 @{name} — {tag}{home_str}")
            elif reason == "never_shielded":
                lines.append(f"  🔓 @{name} — NEVER SHIELDED{home_str}")
            else:
                lines.append(f"  📍 @{name} — {reason}{home_str}")

    # Active bounties (with gold rewards)
    if active_bounties:
        lines.append("\n💰 *ACTIVE BOUNTIES*")
        for b in sorted(active_bounties, key=lambda x: x.get("reward_gold", 0), reverse=True):
            target_name   = b.get("target_name", "Unknown")
            reward        = b.get("reward_gold", 0)
            reason        = b.get("reason", "")
            home_sector   = b.get("target_home_sector")
            poster        = b.get("posted_by_name", "Anonymous")

            try:
                exp         = datetime.fromisoformat(b["expires_at"])
                hours_left  = max(0, int((exp - datetime.utcnow()).total_seconds() // 3600))
                exp_str     = f"{hours_left}h"
            except Exception:
                exp_str     = "?"

            home_str = ""
            if home_sector:
                from teleport_system import SECTOR_QUICK_INFO
                hi       = SECTOR_QUICK_INFO.get(home_sector, {})
                home_str = f"  🏠 {hi.get('emoji','')} {hi.get('name',f'S{home_sector}')}"

            lines.append(
                f"\n  🎯 @{target_name}\n"
                f"     💰 {reward} 🪙  |  Expires: {exp_str}\n"
                f"     Reason: {reason}\n"
                f"     Posted by: @{poster}{home_str}\n"
                f"     `!claim {b.get('bounty_id','?')}`"
            )

    if not active_bounties and not auto_visible_players:
        lines.append("\n_No targets on the board today._\n_The sector is quiet._")

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("Post a bounty: tap below | Min reward: 50 🪙")

    return "\n".join(lines)


def kb_bounty_board(active_bounties: List[dict], viewing_user: dict) -> InlineKeyboardMarkup:
    """Bounty board keyboard — place bounty, view details, claim."""
    buttons = []

    # Top bounties as quick-claim buttons
    for b in active_bounties[:3]:
        target = b.get("target_name", "?")
        reward = b.get("reward_gold", 0)
        bid    = b.get("bounty_id", "")
        buttons.append([
            InlineKeyboardButton(
                f"🎯 Hunt @{target} ({reward}🪙)",
                callback_data=f"bounty:view:{bid}"
            )
        ])

    buttons.append([
        InlineKeyboardButton("💰 Place Bounty",  callback_data="bounty:place"),
        InlineKeyboardButton("🔄 Refresh",       callback_data="bounty:board"),
    ])
    buttons.append([
        InlineKeyboardButton("« Back",           callback_data="base:dashboard"),
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_place_bounty_amount(target_id: str, target_name: str) -> InlineKeyboardMarkup:
    """Quick amount selection for placing a bounty."""
    amounts = [50, 100, 250, 500, 1000]
    buttons = []
    row     = []

    for amt in amounts:
        row.append(InlineKeyboardButton(
            f"{amt}🪙",
            callback_data=f"bounty:place_confirm:{target_id}:{amt}"
        ))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([InlineKeyboardButton("✗ Cancel", callback_data="bounty:board")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_main_dashboard_with_alerts(user: dict, alliance: dict = None) -> InlineKeyboardMarkup:
    """
    The primary /start keyboard — extended with Phase 3 systems.
    Adds war room, bounty board, sector buttons alongside existing base menu.
    Follows the pattern from main.py — adds rows, doesn't replace.
    """
    has_war      = alliance and alliance.get("active_war")
    notification = user.get("pending_notification", "")
    has_notif    = bool(notification)
    suit_exp     = user.get("suit_just_expired", False)
    shield_exp   = user.get("shield_just_expired", False)

    current_sector = user.get("commander_location", {}).get("sector_id", 1)
    home_sector    = user.get("home_sector")
    away_from_home = home_sector and current_sector != home_sector

    buttons = []

    # Alert row — shown only when there's something urgent
    alerts = []
    if has_notif:
        alerts.append(InlineKeyboardButton("🔔 Notification", callback_data="player:notification"))
    if suit_exp:
        alerts.append(InlineKeyboardButton("🧪 Suit Expired!", callback_data="player:suit_menu"))
    if shield_exp:
        alerts.append(InlineKeyboardButton("🔓 Shield Down!", callback_data="base:shields"))
    if alerts:
        buttons.append(alerts)

    # War room — prominent if active
    if has_war:
        war    = alliance["active_war"]
        atk_sc = war.get("attacker_score", 0)
        def_sc = war.get("defender_score", 0)
        buttons.append([
            InlineKeyboardButton(
                f"⚔️ WAR ROOM [{atk_sc} vs {def_sc}]",
                callback_data="war:room"
            )
        ])

    # Sector row
    from teleport_system import SECTOR_QUICK_INFO
    cur_info = SECTOR_QUICK_INFO.get(current_sector, {})
    cur_emoji = cur_info.get("emoji", "🌍")
    cur_name  = cur_info.get("name", f"S{current_sector}")

    if away_from_home:
        buttons.append([
            InlineKeyboardButton(f"{cur_emoji} Field: {cur_name}", callback_data=f"sector:dashboard:{current_sector}"),
            InlineKeyboardButton("🏠 Base View",                    callback_data="base:view"),
        ])
    else:
        buttons.append([
            InlineKeyboardButton(f"{cur_emoji} {cur_name}",    callback_data=f"sector:dashboard:{current_sector}"),
            InlineKeyboardButton("🌀 Teleport",               callback_data="teleport:menu"),
        ])

    # Standard base buttons (these mirror what's already in main.py)
    buttons.append([
        InlineKeyboardButton("⚡ Power",           callback_data="base:power"),
        InlineKeyboardButton("🔬 Research",        callback_data="research:menu"),
    ])
    buttons.append([
        InlineKeyboardButton("🎒 Backpack",        callback_data="player:inventory"),
        InlineKeyboardButton("🏗️ Buildings",      callback_data="base:buildings"),
    ])
    buttons.append([
        InlineKeyboardButton("⚔️ Military",        callback_data="base:military"),
        InlineKeyboardButton("👥 Alliance",        callback_data="alliance:menu"),
    ])
    buttons.append([
        InlineKeyboardButton("🎯 Bounty Board",    callback_data="bounty:board"),
        InlineKeyboardButton("🏆 Leaderboard",     callback_data="base:leaderboard"),
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)
