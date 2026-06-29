# -*- coding: utf-8 -*-
"""
teleport_system.py — Sector Teleport System
============================================
Manages all inter-sector teleportation mechanics.

MECHANICS:
  - 3 free teleport charges claimable daily (must claim — don't auto-grant)
  - Unclaimed daily charges expire at midnight UTC
  - Extra charges purchasable from store
  - NO cooldown — evasive action must be instant
  - NO gold cost per use — charges are the resource
  - Commander + selected troops teleport; base stays in home sector
  - Auto-collect from current node fires before teleport
  - Pending resources always safe — never lost to teleport
  - Players cannot be attacked mid-teleport (instant transit)

RESTRICTIONS:
  - Cannot teleport to a sector you are banished from
  - Void Canyon (Sector 9) requires void_theory research
  - Crypto Wastes (Sector 65) requires crypto_mining_101 research
  - Hidden sectors (10-59) can be teleported to freely (that's how they're explored)

ALLIANCE SAFE ZONES:
  - Alliance leaders flag sectors as safe
  - Shows prominently in teleport menu for members
  - No mechanical benefit — purely informational/coordination
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from resource_registry import RESOURCES, is_unlocked

# ═══════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

DAILY_FREE_TELEPORTS    = 3
DAILY_RESET_HOUR_UTC    = 0        # Midnight UTC
STORE_COST_PER_CHARGE   = 40       # Gold per extra teleport charge
TELEPORT_COOLDOWN_SECS  = 0        # No cooldown — by design

# Sectors requiring specific research to enter
RESTRICTED_SECTORS: Dict[int, str] = {
    9:  "void_theory",           # Void Canyon
    65: "crypto_mining_101",     # Crypto Wastes
}

# Sector display info (emoji + name) for teleport menu
# Full data lives in sectors_system.py — this is a local quick-lookup
SECTOR_QUICK_INFO: Dict[int, dict] = {
    1:  {"name": "Badlands-8",       "emoji": "🏜️",  "hidden": False},
    2:  {"name": "Crimson Wastes",   "emoji": "🔴",  "hidden": False},
    3:  {"name": "Obsidian Peaks",   "emoji": "⛰️",  "hidden": False},
    4:  {"name": "Shattered Valley", "emoji": "💔",  "hidden": False},
    5:  {"name": "Frozen Abyss",     "emoji": "❄️",  "hidden": False},
    6:  {"name": "Molten Gorge",     "emoji": "🔥",  "hidden": False},
    7:  {"name": "Twilight Marshes", "emoji": "🌙",  "hidden": False},
    8:  {"name": "Silent Forest",    "emoji": "🌲",  "hidden": False},
    9:  {"name": "Void Canyon",      "emoji": "🌑",  "hidden": False, "restricted": "void_theory"},
    65: {"name": "Crypto Wastes",    "emoji": "₿",   "hidden": False, "restricted": "crypto_mining_101"},
    **{i: {"name": f"Hidden Sector {i}", "emoji": "🔒", "hidden": True}
       for i in range(10, 60)},
    60: {"name": "Golden Vault",     "emoji": "🏆",  "hidden": False},
    61: {"name": "Emerald Chamber",  "emoji": "💚",  "hidden": False},
    62: {"name": "Platinum Mines",   "emoji": "⚪",  "hidden": False},
    63: {"name": "Stone Cathedral",  "emoji": "💎",  "hidden": False},
    64: {"name": "Relic Vault",      "emoji": "🏺",  "hidden": False},
}


# ═══════════════════════════════════════════════════════════════════════════
#  DAILY CHARGE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

def get_teleport_charges(user: dict) -> int:
    """Get the player's current teleport charge count (claimed + purchased)."""
    return user.get("teleport_charges", 0)


def get_daily_claim_status(user: dict) -> dict:
    """
    Check if the player can claim their daily free teleports.

    Returns dict with:
      can_claim:       bool
      claimed_today:   bool
      charges_pending: int (how many unclaimed remain from today)
      resets_in:       str (time until next reset)
      last_claim_date: str
    """
    now       = datetime.utcnow()
    today_str = now.strftime("%Y-%m-%d")

    last_claim = user.get("teleport_daily_claimed_date", "")
    claimed_today = last_claim == today_str

    # Calculate time until next reset (midnight UTC)
    tomorrow  = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    resets_in = tomorrow - now
    hours     = int(resets_in.total_seconds() // 3600)
    minutes   = int((resets_in.total_seconds() % 3600) // 60)

    return {
        "can_claim":       not claimed_today,
        "claimed_today":   claimed_today,
        "charges_pending": DAILY_FREE_TELEPORTS if not claimed_today else 0,
        "resets_in":       f"{hours}h {minutes}m",
        "last_claim_date": last_claim,
        "free_amount":     DAILY_FREE_TELEPORTS,
    }


def claim_daily_teleports(user: dict) -> Tuple[bool, str, dict]:
    """
    Claim today's free teleport charges.
    Must be called explicitly — charges do not auto-grant.
    Unclaimed charges from yesterday are gone.

    Returns (success, message, updated_user)
    """
    status = get_daily_claim_status(user)

    if not status["can_claim"]:
        resets = status["resets_in"]
        charges = get_teleport_charges(user)
        return False, (
            f"✅ Already claimed today's teleports.\n"
            f"You have *{charges}* charge(s) remaining.\n"
            f"Next claim available in: *{resets}*"
        ), user

    # Grant charges
    now       = datetime.utcnow()
    today_str = now.strftime("%Y-%m-%d")

    current   = user.get("teleport_charges", 0)
    user["teleport_charges"]             = current + DAILY_FREE_TELEPORTS
    user["teleport_daily_claimed_date"]  = today_str
    user["teleport_last_claim_ts"]       = now.isoformat()

    return True, (
        f"🌀 *Daily teleports claimed!*\n"
        f"+{DAILY_FREE_TELEPORTS} teleport charges added.\n"
        f"Total charges: *{current + DAILY_FREE_TELEPORTS}*\n"
        f"Expires: midnight UTC tonight (use them or lose them tomorrow)"
    ), user


def purchase_teleport_charges(
    user: dict,
    quantity: int,
) -> Tuple[bool, str, dict]:
    """
    Purchase extra teleport charges from the store using gold.

    Returns (success, message, updated_user)
    """
    if quantity <= 0 or quantity > 20:
        return False, "❌ Can purchase 1–20 charges at a time.", user

    total_cost = quantity * STORE_COST_PER_CHARGE
    inv        = user.get("inventory", {})
    gold_held  = inv.get("gold", {}).get("qty", 0)

    if gold_held < total_cost:
        return False, (
            f"❌ Not enough gold.\n"
            f"Need: {total_cost} 🪙  |  Have: {gold_held} 🪙\n"
            f"({quantity} charges × {STORE_COST_PER_CHARGE} 🪙 each)"
        ), user

    # Deduct gold
    inv["gold"]["qty"] = gold_held - total_cost
    if inv["gold"]["qty"] <= 0:
        del inv["gold"]
    user["inventory"] = inv

    # Add charges
    user["teleport_charges"] = user.get("teleport_charges", 0) + quantity

    return True, (
        f"🌀 Purchased *{quantity}* teleport charge(s)!\n"
        f"Cost: {total_cost} 🪙\n"
        f"Total charges: *{user['teleport_charges']}*"
    ), user


# ═══════════════════════════════════════════════════════════════════════════
#  TELEPORT EXECUTION
# ═══════════════════════════════════════════════════════════════════════════

def can_teleport_to(
    user: dict,
    target_sector_id: int,
) -> Tuple[bool, str]:
    """
    Validate whether a player can teleport to a sector.
    Checks: charges, research gates, banishment.

    Returns (can_teleport: bool, reason_if_not: str)
    """
    # Check charges
    charges = get_teleport_charges(user)
    if charges <= 0:
        status = get_daily_claim_status(user)
        if status["can_claim"]:
            return False, (
                "❌ No teleport charges.\n"
                "Claim your free daily charges: `!teleport claim`"
            )
        return False, (
            f"❌ No teleport charges.\n"
            f"Daily charges reset in: {status['resets_in']}\n"
            f"Buy extra: `!store teleport`"
        )

    # Check research restriction
    restriction = RESTRICTED_SECTORS.get(target_sector_id)
    if restriction:
        from research_tree import is_feature_unlocked
        if not is_feature_unlocked(user, f"sector_{target_sector_id}_access"):
            from research_tree import RESEARCH_TREE
            research = RESEARCH_TREE.get(restriction, {})
            name     = research.get("name", restriction)
            return False, (
                f"🔒 Sector {target_sector_id} requires research.\n"
                f"Research *{name}* to unlock access.\n"
                f"`!research {restriction}`"
            )

    # Check banishment
    banishments = user.get("banishments", {})
    ban         = banishments.get(str(target_sector_id))
    if ban:
        try:
            ban_expires = datetime.fromisoformat(ban["expires_at"])
            if datetime.utcnow() < ban_expires:
                remaining    = ban_expires - datetime.utcnow()
                hours        = int(remaining.total_seconds() // 3600)
                mins         = int((remaining.total_seconds() % 3600) // 60)
                issued_by    = ban.get("issued_by_name", "the Sector Ruler")
                sector_info  = SECTOR_QUICK_INFO.get(target_sector_id, {})
                sector_name  = sector_info.get("name", f"Sector {target_sector_id}")
                return False, (
                    f"🚫 *Banished from {sector_name}*\n"
                    f"Issued by: @{issued_by}\n"
                    f"Expires in: {hours}h {mins}m\n"
                    f"(Lifted if @{issued_by} loses sector rulership)"
                )
        except Exception:
            pass
        # Expired banishment — remove it
        del banishments[str(target_sector_id)]
        user["banishments"] = banishments

    return True, "OK"


def execute_teleport(
    user: dict,
    target_sector_id: int,
    troops_to_bring: dict,
    sector_state: dict,             # Current sector state (for auto-collect)
    log_sector_event_fn,            # callable(sector_id, event_str)
    home_sector_state: dict = None, # Home sector state if different
) -> Tuple[bool, str, dict, dict]:
    """
    Execute a teleport to a target sector.

    Steps:
      1. Validate can teleport
      2. Auto-collect from current node
      3. Leave current sector (update sector state)
      4. Consume teleport charge
      5. Move commander to target sector
      6. Log events in both sectors

    Returns (success, message, updated_user, updated_sector_state)
    """
    ok, reason = can_teleport_to(user, target_sector_id)
    if not ok:
        return False, reason, user, sector_state

    player_id    = user.get("user_id", "")
    player_name  = user.get("username", "Commander")
    from_sector  = user.get("commander_location", {}).get("sector_id")
    current_node = user.get("current_node")

    # ── Step 1: Auto-collect from current node ────────────────────────────
    auto_collected = {}
    if current_node:
        node_key   = current_node.get("node_key", "")
        node_name  = current_node.get("node_name", "")
        node_sector = current_node.get("sector_id", from_sector)

        from sector_nodes import auto_collect_on_departure
        sector_state, user, auto_collected = auto_collect_on_departure(
            sector_state, node_sector, node_key, player_id, user
        )

    # ── Step 2: Remove from current sector roaming ────────────────────────
    if from_sector:
        roaming = sector_state.get("roaming", {})
        roaming.pop(player_id, None)
        sector_state["roaming"] = roaming

        if from_sector != target_sector_id:
            log_sector_event_fn(
                from_sector,
                f"@{player_name} teleported OUT → Sector {target_sector_id}"
            )

    # ── Step 3: Consume teleport charge ───────────────────────────────────
    user["teleport_charges"] = max(0, user.get("teleport_charges", 0) - 1)

    # Record teleport in history
    if "teleport_history" not in user:
        user["teleport_history"] = []
    user["teleport_history"].insert(0, {
        "from_sector": from_sector,
        "to_sector":   target_sector_id,
        "timestamp":   datetime.utcnow().isoformat(),
    })
    user["teleport_history"] = user["teleport_history"][:20]  # Keep last 20

    # ── Step 4: Move commander ────────────────────────────────────────────
    user["commander_location"] = {
        "sector_id":    target_sector_id,
        "arrived_at":   datetime.utcnow().isoformat(),
        "status":       "roaming",
    }
    user["current_node"] = None

    # ── Step 5: Log arrival in target sector ──────────────────────────────
    log_sector_event_fn(
        target_sector_id,
        f"@{player_name} teleported INTO sector [roaming]"
    )

    # ── Build response message ─────────────────────────────────────────────
    target_info  = SECTOR_QUICK_INFO.get(target_sector_id, {})
    target_name  = target_info.get("name", f"Sector {target_sector_id}")
    target_emoji = target_info.get("emoji", "🌍")
    charges_left = user.get("teleport_charges", 0)

    msg_lines = [
        f"🌀 *Teleported to {target_emoji} {target_name}!*",
        f"Charges remaining: *{charges_left}*",
    ]

    if auto_collected:
        from resource_registry import RESOURCES as RES
        parts = [
            f"{RES.get(k,{}).get('emoji','📦')}{v}"
            for k, v in auto_collected.items() if v > 0
        ]
        if parts:
            msg_lines.append(f"📦 Auto-collected on departure: {' '.join(parts)}")

    if troops_to_bring and sum(troops_to_bring.values()) > 0:
        troop_str = ", ".join(
            f"{v} {k}" for k, v in troops_to_bring.items() if v > 0
        )
        msg_lines.append(f"👥 Troops with you: {troop_str}")

    msg_lines.append(f"\nUse `!map` to see sector nodes.")

    return True, "\n".join(msg_lines), user, sector_state


# ═══════════════════════════════════════════════════════════════════════════
#  ROAMING PLAYER MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

def register_roaming(
    sector_state: dict,
    sector_id: int,
    player_id: str,
    player_name: str,
    troops: dict,
) -> dict:
    """
    Register a player as roaming in a sector (not on a node).
    Called after teleport or when player leaves a node without teleporting.
    """
    if "roaming" not in sector_state:
        sector_state["roaming"] = {}

    sector_state["roaming"][player_id] = {
        "player_name":  player_name,
        "troops":       troops,
        "arrived_at":   datetime.utcnow().isoformat(),
        "sector_id":    sector_id,
    }
    return sector_state


def get_roaming_players(sector_state: dict) -> dict:
    """Get all players currently roaming in a sector (not on a node)."""
    return sector_state.get("roaming", {})


def attack_roaming_player(
    attacker_user: dict,
    target_player_id: str,
    target_player_name: str,
    sector_state: dict,
    sector_id: int,
    log_sector_event_fn,
) -> Tuple[bool, str, dict, dict]:
    """
    Attack a roaming commander directly.
    No node involved — pure commander duel.
    Travel time still applies (handled via march_queue with target=roaming).
    This resolves the outcome when the attacker arrives.

    Returns (success, message, updated_attacker_user, updated_sector_state)
    """
    roaming = sector_state.get("roaming", {})

    if target_player_id not in roaming:
        return False, (
            f"❌ @{target_player_name} is no longer roaming in this sector.\n"
            f"They may have occupied a node or teleported away."
        ), attacker_user, sector_state

    target_data     = roaming[target_player_id]
    target_troops   = target_data.get("troops", {})
    attacker_troops = attacker_user.get("military", {})

    # Calculate duel outcome
    import random
    from march_queue import _calc_power, _apply_casualties, _subtract_losses

    atk_power = _calc_power(attacker_troops)
    def_power = _calc_power(target_troops)
    atk_roll  = atk_power * random.uniform(0.85, 1.15)
    def_roll  = def_power * random.uniform(0.85, 1.15)
    atk_wins  = atk_roll > def_roll

    atk_losses = _apply_casualties(attacker_troops, 0.06 if atk_wins else 0.22)
    def_losses = _apply_casualties(target_troops,   0.18 if atk_wins else 0.05)

    attacker_troops = _subtract_losses(attacker_troops, atk_losses)
    target_troops   = _subtract_losses(target_troops,   def_losses)

    attacker_user["military"] = attacker_troops
    attacker_name = attacker_user.get("username", "Unknown")

    if atk_wins:
        # Target ejected from sector
        roaming.pop(target_player_id, None)
        sector_state["roaming"] = roaming
        attacker_user["wins"] = attacker_user.get("wins", 0) + 1

        # Store result for target player notification
        if "pending_notifications" not in sector_state:
            sector_state["pending_notifications"] = {}
        sector_state["pending_notifications"][target_player_id] = {
            "type":           "roaming_defeat",
            "attacker_name":  attacker_name,
            "sector_id":      sector_id,
            "timestamp":      datetime.utcnow().isoformat(),
            "message": (
                f"🚨 *COMMANDER DUEL LOST*\n"
                f"@{attacker_name} defeated you in Sector {sector_id}.\n"
                f"You have been expelled from the sector.\n"
                f"Losses: {', '.join(f'{v} {k}' for k,v in def_losses.items() if v>0)}"
            )
        }

        log_sector_event_fn(
            sector_id,
            f"⚔️ @{attacker_name} defeated @{target_player_name} [roaming duel] — target expelled"
        )
        return True, (
            f"✅ *DUEL VICTORY*\n"
            f"@{target_player_name} has been expelled from Sector {sector_id}.\n"
            f"Your losses: {', '.join(f'{v} {k}' for k,v in atk_losses.items() if v>0) or 'none'}"
        ), attacker_user, sector_state

    else:
        # Attacker repelled
        attacker_user["losses"] = attacker_user.get("losses", 0) + 1
        log_sector_event_fn(
            sector_id,
            f"⚔️ @{attacker_name} failed duel against @{target_player_name} [roaming]"
        )
        return True, (
            f"❌ *DUEL DEFEAT*\n"
            f"@{target_player_name} repelled your attack.\n"
            f"Your losses: {', '.join(f'{v} {k}' for k,v in atk_losses.items() if v>0) or 'none'}"
        ), attacker_user, sector_state


# ═══════════════════════════════════════════════════════════════════════════
#  BANISHMENT SYSTEM
# ═══════════════════════════════════════════════════════════════════════════

def issue_banishment(
    ruler_user: dict,
    target_player_id: str,
    target_player_name: str,
    sector_id: int,
    sector_state: dict,
    save_user_fn,
) -> Tuple[bool, str, dict]:
    """
    Sector Ruler issues a banishment scroll against a player.
    Consumes one banishment_scroll from ruler's inventory.
    Target cannot re-enter the sector for 48 hours.

    Returns (success, message, updated_ruler_user)
    """
    # Check ruler status
    dominance    = sector_state.get("dominance", {})
    current_ruler = dominance.get("ruler_id")
    ruler_id      = ruler_user.get("user_id", "")

    if current_ruler != ruler_id:
        return False, "❌ Only the Sector Ruler can issue banishments.", ruler_user

    # Check scroll in inventory
    inv          = ruler_user.get("inventory", {})
    scroll_qty   = inv.get("banishment_scroll", {}).get("qty", 0)
    if scroll_qty < 1:
        return False, (
            "❌ No Banishment Scrolls in inventory.\n"
            "Purchase from `!store` or alliance shop."
        ), ruler_user

    # Check target is actually in sector
    roaming  = sector_state.get("roaming", {})
    occupancy = sector_state.get("occupancy", {})
    in_sector = (
        target_player_id in roaming or
        any(occ.get("player_id") == target_player_id
            for occ in occupancy.values())
    )
    if not in_sector:
        return False, (
            f"❌ @{target_player_name} is not currently in this sector.\n"
            "Banishment can only be issued to players present in your sector."
        ), ruler_user

    # Consume scroll
    inv["banishment_scroll"]["qty"] -= 1
    if inv["banishment_scroll"]["qty"] <= 0:
        del inv["banishment_scroll"]
    ruler_user["inventory"] = inv

    # Apply banishment to target
    expires_at   = (datetime.utcnow() + timedelta(hours=48)).isoformat()
    ruler_name   = ruler_user.get("username", "Unknown")

    # Load target user and apply
    target_user  = save_user_fn(target_player_id, None)  # getter pattern
    if target_user:
        if "banishments" not in target_user:
            target_user["banishments"] = {}
        target_user["banishments"][str(sector_id)] = {
            "expires_at":      expires_at,
            "issued_by_id":    ruler_id,
            "issued_by_name":  ruler_name,
            "sector_id":       sector_id,
            "issued_at":       datetime.utcnow().isoformat(),
        }

        # Force teleport target home
        home = target_user.get("home_sector", 1)
        target_user["commander_location"] = {"sector_id": home}
        target_user["current_node"] = None

        # Remove from sector
        roaming.pop(target_player_id, None)
        for occ_key in list(occupancy.keys()):
            if occupancy[occ_key].get("player_id") == target_player_id:
                del occupancy[target_player_id]
        sector_state["roaming"]    = roaming
        sector_state["occupancy"]  = occupancy

        # Notification for target
        target_user["pending_notification"] = (
            f"🚫 *BANISHED*\n"
            f"@{ruler_name} (Ruler of Sector {sector_id}) has banished you.\n"
            f"You cannot return for 48 hours.\n"
            f"(Lifted if @{ruler_name} loses sector control)"
        )

        save_user_fn(target_player_id, target_user)

    sector_info  = SECTOR_QUICK_INFO.get(sector_id, {})
    sector_name  = sector_info.get("name", f"Sector {sector_id}")

    return True, (
        f"📜 *@{target_player_name} banished from {sector_name}!*\n"
        f"Duration: 48 hours\n"
        f"Banishment lifts if you lose sector rulership."
    ), ruler_user


def lift_banishments_on_ruler_change(
    old_ruler_id: str,
    sector_id: int,
    all_banished_player_ids: List[str],
    save_user_fn,
) -> int:
    """
    When a ruler loses control, lift all their issued banishments.
    Returns count of banishments lifted.
    """
    lifted = 0
    for pid in all_banished_player_ids:
        user = save_user_fn(pid, None)  # getter
        if user:
            bans = user.get("banishments", {})
            ban  = bans.get(str(sector_id))
            if ban and ban.get("issued_by_id") == old_ruler_id:
                del bans[str(sector_id)]
                user["banishments"] = bans
                user["pending_notification"] = (
                    f"✅ *Banishment Lifted*\n"
                    f"Your banishment from Sector {sector_id} has been lifted.\n"
                    f"The ruler who issued it has lost control of the sector."
                )
                save_user_fn(pid, user)
                lifted += 1
    return lifted


# ═══════════════════════════════════════════════════════════════════════════
#  ALLIANCE SAFE ZONES
# ═══════════════════════════════════════════════════════════════════════════

def set_alliance_safe_sector(
    leader_user: dict,
    sector_id: int,
    alliance: dict,
    safe: bool = True,
) -> Tuple[bool, str, dict]:
    """
    Alliance leader flags a sector as safe (or removes flag).
    Only informational — no mechanical immunity granted.

    Returns (success, message, updated_alliance)
    """
    role = leader_user.get("alliance_role", "MEMBER")
    if role != "LEADER":
        return False, "❌ Only the alliance leader can set safe sectors.", alliance

    if "safe_sectors" not in alliance:
        alliance["safe_sectors"] = []

    sector_info = SECTOR_QUICK_INFO.get(sector_id, {})
    sector_name = sector_info.get("name", f"Sector {sector_id}")
    sector_emoji = sector_info.get("emoji", "🌍")

    if safe:
        if sector_id not in alliance["safe_sectors"]:
            alliance["safe_sectors"].append(sector_id)
        msg = (
            f"✅ *{sector_emoji} {sector_name}* flagged as alliance safe zone.\n"
            f"Members will see this in their teleport menu."
        )
    else:
        if sector_id in alliance["safe_sectors"]:
            alliance["safe_sectors"].remove(sector_id)
        msg = f"❌ Safe zone flag removed from {sector_emoji} {sector_name}."

    return True, msg, alliance


def get_alliance_safe_sectors(alliance: dict) -> List[int]:
    """Get list of sectors flagged as safe by the alliance."""
    return alliance.get("safe_sectors", [])


# ═══════════════════════════════════════════════════════════════════════════
#  TELEPORT MENU DISPLAY
# ═══════════════════════════════════════════════════════════════════════════

def format_teleport_menu(
    user: dict,
    alliance: dict = None,
) -> str:
    """
    Format the full teleport destination menu.
    Shows: charge count, daily claim status, safe zones, all sectors.
    """
    charges = get_teleport_charges(user)
    status  = get_daily_claim_status(user)

    lines = [
        "🌀 *TELEPORT*",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"Charges: *{charges}* 🌀",
    ]

    if status["can_claim"]:
        lines.append(
            f"📬 *{status['free_amount']} free charges available!*  `!teleport claim`"
        )
    else:
        lines.append(
            f"Next free charges: {status['resets_in']}  |  Buy more: `!teleport buy [qty]`"
        )

    # Alliance safe zones
    safe_sectors = []
    if alliance:
        safe_sectors = get_alliance_safe_sectors(alliance)
        if safe_sectors:
            lines.append(f"\n🟢 *ALLIANCE SAFE ZONES:*")
            for sid in safe_sectors:
                info = SECTOR_QUICK_INFO.get(sid, {})
                lines.append(
                    f"  🟢 {info.get('emoji', '🌍')} {info.get('name', f'Sector {sid}')} "
                    f"— `!teleport {sid}`"
                )

    # Public sectors
    lines.append(f"\n🌍 *SECTORS:*")
    public = [1, 2, 3, 4, 5, 6, 7, 8, 9, 60, 61, 62, 63, 64, 65]

    for sid in public:
        info        = SECTOR_QUICK_INFO.get(sid, {})
        name        = info.get("name", f"Sector {sid}")
        emoji       = info.get("emoji", "🌍")
        restriction = info.get("restricted")
        is_safe     = sid in safe_sectors

        safe_tag    = " 🟢" if is_safe else ""
        lock_tag    = ""

        if restriction:
            from research_tree import is_feature_unlocked
            if not is_feature_unlocked(user, f"sector_{sid}_access"):
                lock_tag = " 🔒"

        lines.append(f"  {emoji} S{sid}: {name}{safe_tag}{lock_tag}  `!teleport {sid}`")

    lines.append(
        f"\n🔒 Hidden sectors 10–59 accessible by trial (no lock)."
    )
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(
        "Syntax: `!teleport [sector_id]` | `!teleport claim` | `!teleport buy [n]`"
    )

    return "\n".join(lines)


def format_charge_status(user: dict) -> str:
    """Compact charge display for dashboard."""
    charges = get_teleport_charges(user)
    status  = get_daily_claim_status(user)

    if status["can_claim"]:
        return f"🌀 Teleports: *{charges}* (+{DAILY_FREE_TELEPORTS} unclaimed) `!teleport claim`"
    return f"🌀 Teleports: *{charges}* (resets in {status['resets_in']})"


# ═══════════════════════════════════════════════════════════════════════════
#  VISA SYSTEM
#  Sector rulers can require visas from players based on their home sector.
#  Getting a visa reveals the applicant's home sector to the ruler.
#  Rulers can also impose 24-hour visa bans on entire home sectors.
# ═══════════════════════════════════════════════════════════════════════════

# Geopolitical flavour — what rulers call different home sectors
SECTOR_REPUTATION: Dict[int, str] = {
    1:  "desert drifter",
    2:  "crimson marauder",
    3:  "peak dweller",
    4:  "valley raider",
    5:  "frozen wanderer",
    6:  "lava runner",
    7:  "marsh phantom",
    8:  "forest ghost",
    9:  "void walker",
    65: "crypto rat",
}


def check_visa_required(
    user: dict,
    target_sector_id: int,
    sector_state: dict,
) -> Tuple[bool, str]:
    """
    Check if this player needs a visa to enter a sector.
    Returns (visa_required: bool, message: str)

    Visa is required when:
      - The sector ruler has enabled visa mode
      - The player's home sector is in the restricted list
      - The player does not already hold a valid visa
    """
    dominance = sector_state.get("dominance", {})
    visa_policy = dominance.get("visa_policy", {})

    if not visa_policy.get("enabled", False):
        return False, "OK"

    home_sector = user.get("home_sector")
    if home_sector is None:
        return False, "OK"

    restricted_homes = visa_policy.get("restricted_home_sectors", [])
    if home_sector not in restricted_homes:
        return False, "OK"

    # Check if player already has a valid visa
    visas = user.get("visas", {})
    visa  = visas.get(str(target_sector_id))
    if visa:
        try:
            expires = datetime.fromisoformat(visa["expires_at"])
            if datetime.utcnow() < expires:
                return False, "OK"   # Valid visa
        except Exception:
            pass

    # Visa required and not held
    ruler_name   = dominance.get("ruler_name", "the Sector Ruler")
    sector_info  = SECTOR_QUICK_INFO.get(target_sector_id, {})
    sector_name  = sector_info.get("name", f"Sector {target_sector_id}")
    home_info    = SECTOR_QUICK_INFO.get(home_sector, {})
    home_name    = home_info.get("name", f"Sector {home_sector}")
    reputation   = SECTOR_REPUTATION.get(home_sector, "outsider")

    return True, (
        f"🛂 *VISA REQUIRED*\n"
        f"@{ruler_name} has restricted entry to {sector_name}\n"
        f"for {reputation}s from {home_name}.\n\n"
        f"Apply with `!visa apply {target_sector_id}`\n"
        f"⚠️ *Warning:* Applying reveals your home sector ({home_name}) "
        f"to @{ruler_name} permanently."
    )


def apply_for_visa(
    user: dict,
    target_sector_id: int,
    sector_state: dict,
    save_user_fn,
) -> Tuple[bool, str, dict]:
    """
    Player applies for a visa. Reveals home sector to ruler.
    Ruler must approve — until then player cannot enter.
    Returns (success, message, updated_user)
    """
    dominance    = sector_state.get("dominance", {})
    ruler_id     = dominance.get("ruler_id")
    ruler_name   = dominance.get("ruler_name", "Unknown")
    player_name  = user.get("username", "Unknown")
    home_sector  = user.get("home_sector")
    home_info    = SECTOR_QUICK_INFO.get(home_sector, {})
    home_name    = home_info.get("name", f"Sector {home_sector}")
    sector_info  = SECTOR_QUICK_INFO.get(target_sector_id, {})
    sector_name  = sector_info.get("name", f"Sector {target_sector_id}")

    # Record application in player data
    if "visa_applications" not in user:
        user["visa_applications"] = {}

    user["visa_applications"][str(target_sector_id)] = {
        "sector_id":   target_sector_id,
        "sector_name": sector_name,
        "ruler_id":    ruler_id,
        "ruler_name":  ruler_name,
        "applied_at":  datetime.utcnow().isoformat(),
        "status":      "pending",
        "home_revealed": True,
    }

    # Notify ruler — store in their pending actions
    if ruler_id:
        ruler_user = save_user_fn(ruler_id, None)   # getter
        if ruler_user:
            if "visa_queue" not in ruler_user:
                ruler_user["visa_queue"] = []
            ruler_user["visa_queue"].append({
                "applicant_id":    user.get("user_id"),
                "applicant_name":  player_name,
                "home_sector":     home_sector,
                "home_name":       home_name,
                "target_sector":   target_sector_id,
                "applied_at":      datetime.utcnow().isoformat(),
            })
            ruler_user["pending_notification"] = (
                f"🛂 *VISA APPLICATION*\n"
                f"@{player_name} (from {home_name}) wants entry to {sector_name}.\n"
                f"Their home sector: *{home_name}* (Sector {home_sector})\n"
                f"Approve: `!visa approve {user.get('user_id')}`\n"
                f"Deny:    `!visa deny {user.get('user_id')}`"
            )
            save_user_fn(ruler_id, ruler_user)

    reputation = SECTOR_REPUTATION.get(home_sector, "outsider")
    return True, (
        f"🛂 Visa application sent to @{ruler_name}.\n"
        f"Your home sector (*{home_name}*) has been revealed to them.\n"
        f"You are now known as a *{reputation}* to this ruler.\n"
        f"Awaiting approval — you will be notified."
    ), user


def approve_visa(
    ruler_user: dict,
    applicant_id: str,
    target_sector_id: int,
    sector_state: dict,
    save_user_fn,
    duration_hours: int = 24,
) -> Tuple[bool, str]:
    """
    Ruler approves a visa application. Grants 24-hour entry.
    Returns (success, message)
    """
    dominance = sector_state.get("dominance", {})
    ruler_id  = dominance.get("ruler_id")

    if ruler_user.get("user_id") != ruler_id:
        return False, "❌ Only the Sector Ruler can approve visas."

    applicant = save_user_fn(applicant_id, None)   # getter
    if not applicant:
        return False, "❌ Applicant not found."

    expires_at = (datetime.utcnow() + timedelta(hours=duration_hours)).isoformat()

    if "visas" not in applicant:
        applicant["visas"] = {}

    applicant["visas"][str(target_sector_id)] = {
        "sector_id":    target_sector_id,
        "granted_by":   ruler_user.get("username", "Unknown"),
        "granted_at":   datetime.utcnow().isoformat(),
        "expires_at":   expires_at,
        "duration_hrs": duration_hours,
    }

    sector_info = SECTOR_QUICK_INFO.get(target_sector_id, {})
    sector_name = sector_info.get("name", f"Sector {target_sector_id}")

    applicant["pending_notification"] = (
        f"✅ *VISA APPROVED*\n"
        f"@{ruler_user.get('username','Ruler')} has approved your entry to {sector_name}.\n"
        f"Valid for {duration_hours} hours. Welcome — but behave."
    )
    save_user_fn(applicant_id, applicant)

    # Remove from visa queue
    queue = ruler_user.get("visa_queue", [])
    ruler_user["visa_queue"] = [q for q in queue if q.get("applicant_id") != applicant_id]
    save_user_fn(ruler_user["user_id"], ruler_user)

    return True, (
        f"✅ Visa granted to @{applicant.get('username','Unknown')}.\n"
        f"Entry valid for {duration_hours} hours.\n"
        f"Their home sector remains on your intelligence record."
    )


def set_visa_policy(
    ruler_user: dict,
    target_sector_id: int,
    sector_state: dict,
    restricted_home_sectors: List[int],
    enabled: bool = True,
) -> Tuple[bool, str, dict]:
    """
    Ruler configures visa policy — which home sectors must apply for entry.
    Returns (success, message, updated_sector_state)
    """
    dominance = sector_state.get("dominance", {})
    ruler_id  = dominance.get("ruler_id")

    if ruler_user.get("user_id") != ruler_id:
        return False, "❌ Only the Sector Ruler can set visa policy.", sector_state

    sector_info  = SECTOR_QUICK_INFO.get(target_sector_id, {})
    sector_name  = sector_info.get("name", f"Sector {target_sector_id}")

    dominance["visa_policy"] = {
        "enabled":                 enabled,
        "restricted_home_sectors": restricted_home_sectors,
        "set_at":                  datetime.utcnow().isoformat(),
        "set_by":                  ruler_user.get("username", "Unknown"),
    }
    sector_state["dominance"] = dominance

    if not enabled:
        return True, f"✅ Visa restrictions lifted for {sector_name}.", sector_state

    restricted_names = [
        SECTOR_QUICK_INFO.get(s, {}).get("name", f"Sector {s}")
        for s in restricted_home_sectors
    ]
    reputations = [SECTOR_REPUTATION.get(s, f"sector {s} player") for s in restricted_home_sectors]

    return True, (
        f"🛂 Visa policy set for {sector_name}.\n"
        f"Restricted: {', '.join(restricted_names)}\n"
        f"These players ({', '.join(reputations)}) must apply before entering.\n"
        f"Their home base is revealed to you when they apply."
    ), sector_state


# ═══════════════════════════════════════════════════════════════════════════
#  SECTOR CHAT SYSTEM
#  Each sector has its own rolling chat log visible only to players in it.
#  Players feel they've arrived somewhere new — they see local chatter.
#  Stealth players (jammers, bounty hunters) can observe without posting.
#  Observing chat is intelligence — reveals who is in the sector and active.
# ═══════════════════════════════════════════════════════════════════════════

SECTOR_CHAT_MAX_MESSAGES = 30    # Rolling window per sector
SECTOR_CHAT_MESSAGE_MAX_LEN = 200


def post_sector_chat(
    sector_state: dict,
    player_id: str,
    player_name: str,
    message: str,
    is_system: bool = False,
) -> Tuple[dict, str]:
    """
    Post a message to the sector's local chat.
    System messages (phase changes, arrivals) use is_system=True.
    Jammed sectors suppress player messages but show the jam notice.
    Returns (updated_sector_state, formatted_message)
    """
    # Check if sector is jammed
    jam = sector_state.get("active_jam")
    if jam and not is_system:
        try:
            jam_expires = datetime.fromisoformat(jam["expires_at"])
            if datetime.utcnow() < jam_expires:
                return sector_state, (
                    "📡 *[TRANSMISSION BLOCKED]*\n"
                    "Sector communications are jammed. Your message was not sent.\n"
                    f"Jam expires in: {_format_jam_remaining(jam)}"
                )
        except Exception:
            pass

    if "sector_chat" not in sector_state:
        sector_state["sector_chat"] = []

    # Truncate
    message = message[:SECTOR_CHAT_MESSAGE_MAX_LEN]
    now     = datetime.utcnow()

    entry = {
        "player_id":   player_id if not is_system else "SYSTEM",
        "player_name": player_name if not is_system else "⚙️ SECTOR",
        "message":     message,
        "timestamp":   now.isoformat(),
        "time_str":    now.strftime("%H:%M"),
        "is_system":   is_system,
    }

    sector_state["sector_chat"].insert(0, entry)
    sector_state["sector_chat"] = sector_state["sector_chat"][:SECTOR_CHAT_MAX_MESSAGES]

    formatted = f"[{entry['time_str']}] *{entry['player_name']}*: {message}"
    return sector_state, formatted


def read_sector_chat(
    sector_state: dict,
    player_id: str,
    user: dict,
    limit: int = 15,
    stealth_mode: bool = False,
) -> str:
    """
    Display the sector chat log.
    stealth_mode: True for jammers/bounty hunters observing without revealing presence.
    Reading chat in stealth does NOT add a system message about the reader.

    Returns formatted chat string.
    """
    chat = sector_state.get("sector_chat", [])
    if not chat:
        return "📡 *SECTOR CHAT*\n━━━━━━━━━━━━━━━━\n_No messages yet. Be the first to speak._"

    # Check jam status
    jam = sector_state.get("active_jam")
    jam_notice = ""
    if jam:
        try:
            jam_expires = datetime.fromisoformat(jam["expires_at"])
            if datetime.utcnow() < jam_expires:
                jam_notice = f"\n⚡ *[SECTOR JAMMED — {_format_jam_remaining(jam)} remaining]*\n"
        except Exception:
            pass

    lines = [f"📡 *SECTOR CHAT*{jam_notice}", "━━━━━━━━━━━━━━━━"]

    displayed = chat[:limit]
    displayed.reverse()   # Show oldest first

    for entry in displayed:
        time_str    = entry.get("time_str", "??:??")
        player_name = entry.get("player_name", "Unknown")
        message     = entry.get("message", "")
        is_system   = entry.get("is_system", False)

        if is_system:
            lines.append(f"  _{time_str} — {message}_")
        else:
            # Highlight if message is from current player
            is_me = entry.get("player_id") == player_id
            name_display = f"*{player_name}*" if not is_me else f"*{player_name} (you)*"
            lines.append(f"  [{time_str}] {name_display}: {message}")

    lines.append("━━━━━━━━━━━━━━━━")
    if stealth_mode:
        lines.append("👁️ _Observing in stealth — your presence is hidden_")
        lines.append("`!chat [message]` — breaks stealth  |  `!scout [node]` — remain hidden")
    else:
        lines.append("`!chat [message]` to reply")

    return "\n".join(lines)


def get_sector_intelligence_from_chat(
    sector_state: dict,
    limit: int = 30,
) -> dict:
    """
    Extract intelligence from sector chat — who is talking, when, how recently.
    Used by scouts and bounty hunters observing a sector before entering.
    Returns dict of active players with last seen timestamp.
    """
    chat = sector_state.get("sector_chat", [])
    intel: Dict[str, dict] = {}

    for entry in chat[:limit]:
        pid  = entry.get("player_id")
        name = entry.get("player_name")
        ts   = entry.get("timestamp")

        if pid and pid != "SYSTEM" and pid not in intel:
            try:
                last_seen = datetime.fromisoformat(ts)
                minutes_ago = int((datetime.utcnow() - last_seen).total_seconds() / 60)
            except Exception:
                minutes_ago = 999

            intel[pid] = {
                "player_name":  name,
                "last_message_mins_ago": minutes_ago,
                "active": minutes_ago < 30,
            }

    return intel


def format_sector_arrival_view(
    sector_id: int,
    sector_state: dict,
    player_id: str,
    user: dict,
    alliance: dict = None,
) -> str:
    """
    Full arrival view when a player teleports into a new sector.
    Combines: sector banner, phase status, node map summary, sector chat, safe zone flag.
    This is what makes every sector feel like arriving somewhere new.
    """
    from sectors_system import get_sector_info
    sector_info  = get_sector_info(sector_id)
    sector_name  = sector_info.get("name", f"Sector {sector_id}")
    sector_emoji = sector_info.get("emoji", "🌍")
    lore         = sector_info.get("lore", "")

    # Phase info
    phase_name    = sector_state.get("current_phase", {}).get("name", "Unknown")
    phase_emoji   = sector_state.get("current_phase", {}).get("emoji", "")
    phase_remaining = sector_state.get("current_phase", {}).get("time_remaining_str", "?")

    # Alliance safe zone flag
    safe_tag = ""
    if alliance:
        safe_sectors = get_alliance_safe_sectors(alliance)
        if sector_id in safe_sectors:
            safe_tag = "  🟢 *[ALLIANCE SAFE ZONE]*"

    # Visa policy warning
    dominance    = sector_state.get("dominance", {})
    ruler_name   = dominance.get("ruler_name")
    visa_policy  = dominance.get("visa_policy", {})
    visa_warning = ""
    if visa_policy.get("enabled"):
        visa_warning = (
            f"\n🛂 *Visa policy active* — @{ruler_name} restricts some home sectors."
        )

    # Sector chat preview (last 5 messages)
    chat       = sector_state.get("sector_chat", [])
    chat_lines = []
    if chat:
        recent = list(reversed(chat[:5]))
        for entry in recent:
            t    = entry.get("time_str", "??:??")
            name = entry.get("player_name", "?")
            msg  = entry.get("message", "")
            is_sys = entry.get("is_system", False)
            if is_sys:
                chat_lines.append(f"  _{t} — {msg}_")
            else:
                chat_lines.append(f"  [{t}] *{name}*: {msg}")

    # Who is here
    roaming   = sector_state.get("roaming", {})
    occupancy = sector_state.get("occupancy", {})
    others_here = []
    for pid, rdata in roaming.items():
        if pid != player_id:
            others_here.append(f"@{rdata['player_name']} [roaming]")
    for occ_key, odata in occupancy.items():
        if odata.get("player_id") != player_id:
            others_here.append(f"@{odata['player_name']} [{occ_key.split(':')[1]}]")

    lines = [
        f"{sector_emoji} {'═' * 43}",
        f"  ARRIVED: {sector_name.upper()}{safe_tag}",
        f"{'═' * 45}",
    ]

    if lore:
        lore_short = lore.split(".")[0] + "."
        lines.append(f"\n_{lore_short}_")

    lines.append(
        f"\n📡 Phase: *{phase_emoji} {phase_name}*  [{phase_remaining} remaining]"
    )

    if ruler_name:
        lines.append(f"👑 Ruler: @{ruler_name}")

    lines.append(visa_warning)

    if others_here:
        lines.append(f"\n👥 *{len(others_here)} commander(s) present:*")
        for o in others_here[:5]:
            lines.append(f"  {o}")
        if len(others_here) > 5:
            lines.append(f"  ... and {len(others_here) - 5} more")
    else:
        lines.append("\n👤 *You are alone in this sector.*")

    # Chat preview
    if chat_lines:
        lines.append(f"\n📡 *SECTOR CHAT [recent]:*")
        lines.extend(chat_lines)
        lines.append(f"  `!chat` to read more  |  `!chat [msg]` to speak")
    else:
        lines.append(f"\n📡 *Sector chat is quiet.* `!chat [msg]` to open comms.")

    lines.append(f"\n`!map` — node map  |  `!occupy [A-H]` — claim node")
    lines.append(f"`!scout [@player]` — gather intel  |  `!base` — view home")
    lines.append(f"{'═' * 45}")

    return "\n".join(filter(lambda x: x is not None, lines))


# ═══════════════════════════════════════════════════════════════════════════
#  JAM SYSTEM (teleport_system owns the jam state)
# ═══════════════════════════════════════════════════════════════════════════

JAM_DURATION_SECONDS = 180     # 3 minutes
JAM_COOLDOWN_SECONDS = 21600   # 6 hours between uses


def activate_sector_jam(
    user: dict,
    sector_id: int,
    sector_state: dict,
    log_sector_event_fn,
) -> Tuple[bool, str, dict, dict]:
    """
    Volt Tier 5 ability — jam the entire sector's comms for 3 minutes.
    Requires sector_jamming research to be completed.
    Returns (success, message, updated_user, updated_sector_state)
    """
    from research_tree import is_feature_unlocked
    if not is_feature_unlocked(user, "jam_sector_action"):
        from research_tree import get_locked_message
        return False, get_locked_message("jam_sector_action"), user, sector_state

    # Check cooldown
    last_jam = user.get("last_jam_at")
    if last_jam:
        try:
            last = datetime.fromisoformat(last_jam)
            elapsed = (datetime.utcnow() - last).total_seconds()
            if elapsed < JAM_COOLDOWN_SECONDS:
                remaining = JAM_COOLDOWN_SECONDS - elapsed
                h = int(remaining // 3600)
                m = int((remaining % 3600) // 60)
                return False, (
                    f"⚡ Jammer on cooldown.\n"
                    f"Available in: {h}h {m}m"
                ), user, sector_state
        except Exception:
            pass

    # Check already jammed
    existing_jam = sector_state.get("active_jam")
    if existing_jam:
        try:
            exp = datetime.fromisoformat(existing_jam["expires_at"])
            if datetime.utcnow() < exp:
                jammer = existing_jam.get("jammer_name", "someone")
                return False, (
                    f"⚡ Sector already jammed by @{jammer}.\n"
                    f"Remaining: {_format_jam_remaining(existing_jam)}"
                ), user, sector_state
        except Exception:
            pass

    expires_at = (datetime.utcnow() + timedelta(seconds=JAM_DURATION_SECONDS)).isoformat()
    player_id   = user.get("user_id", "")
    player_name = user.get("username", "Unknown")

    sector_state["active_jam"] = {
        "jammer_id":   player_id,
        "jammer_name": player_name,
        "started_at":  datetime.utcnow().isoformat(),
        "expires_at":  expires_at,
        "sector_id":   sector_id,
    }

    user["last_jam_at"] = datetime.utcnow().isoformat()

    # Post system message to sector chat — the ONLY thing visible during jam
    sector_state, _ = post_sector_chat(
        sector_state, "SYSTEM", "SYSTEM",
        f"⚡ SECTOR JAMMED — Communications disrupted for {JAM_DURATION_SECONDS // 60} minutes.",
        is_system=True
    )

    # Ruler gets an alert
    dominance  = sector_state.get("dominance", {})
    ruler_id   = dominance.get("ruler_id")
    if ruler_id and ruler_id != player_id:
        if "pending_ruler_alerts" not in sector_state:
            sector_state["pending_ruler_alerts"] = []
        sector_state["pending_ruler_alerts"].append({
            "type":     "jam_detected",
            "sector":   sector_id,
            "timestamp": datetime.utcnow().isoformat(),
            "message": (
                f"⚡ *JAM DETECTED — Sector {sector_id}*\n"
                f"An unknown commander is jamming your sector.\n"
                f"Use `!locate` to find them (60% success).\n"
                f"Use `!banish` with a scroll to expel them."
            )
        })

    log_sector_event_fn(
        sector_id,
        f"⚡ SECTOR JAM ACTIVATED [{JAM_DURATION_SECONDS // 60}min] — source unknown"
    )

    return True, (
        f"⚡ *SECTOR JAM ACTIVE*\n"
        f"Duration: {JAM_DURATION_SECONDS // 60} minutes\n"
        f"All sector chat and reports blacked out.\n"
        f"Your movements in this window leave no trace.\n"
        f"⚠️ The Sector Ruler has been alerted."
    ), user, sector_state


def get_jam_status(sector_state: dict) -> Optional[dict]:
    """Get active jam info, or None if no jam / expired."""
    jam = sector_state.get("active_jam")
    if not jam:
        return None
    try:
        exp = datetime.fromisoformat(jam["expires_at"])
        if datetime.utcnow() >= exp:
            sector_state.pop("active_jam", None)
            return None
    except Exception:
        return None
    return jam


def _format_jam_remaining(jam: dict) -> str:
    try:
        exp       = datetime.fromisoformat(jam["expires_at"])
        remaining = max(0, (exp - datetime.utcnow()).total_seconds())
        m = int(remaining // 60)
        s = int(remaining % 60)
        return f"{m}m {s}s"
    except Exception:
        return "?"


# ═══════════════════════════════════════════════════════════════════════════
#  INVENTORY MIGRATION WIRING
#  Called from supabase_db.get_user() to silently convert old format
# ═══════════════════════════════════════════════════════════════════════════

def on_user_load(user: dict) -> dict:
    """
    Hook called every time a user is loaded from the database.
    Handles all silent migrations and passive updates:
      1. Inventory format migration (list → stacked dict)
      2. Energy regeneration tick
      3. Research queue completion check
      4. Suit expiry check
      5. Teleport charge daily reset detection
    Returns updated user dict (must be saved back).
    """
    # 1. Inventory migration
    from resource_registry import migrate_inventory
    user = migrate_inventory(user)

    # 2. Energy regen
    from resource_registry import apply_energy_regen
    user = apply_energy_regen(user)

    # 3. Research completion
    from research_tree import check_and_complete_research
    user, completed = check_and_complete_research(user)
    if completed:
        # Queue notifications for the player
        if "pending_notification" not in user:
            user["pending_notification"] = ""
        notif = "\n".join([f"🔬 Research complete: *{name}*" for name in completed])
        user["pending_notification"] = notif + "\n" + user.get("pending_notification", "")

    # 4. Suit expiry check — clear expired suit silently
    active_suit = user.get("active_suit")
    if active_suit:
        try:
            expires = datetime.fromisoformat(active_suit["expires_at"])
            if datetime.utcnow() >= expires:
                user.pop("active_suit", None)
                # Note expiry for next dashboard render
                user["suit_just_expired"] = True
        except Exception:
            user.pop("active_suit", None)

    # 5. Shield expiry check
    shield_exp = user.get("shield_expires_at")
    if shield_exp:
        try:
            exp = datetime.fromisoformat(shield_exp)
            if datetime.utcnow() >= exp:
                user["base_shielded"]    = False
                user["shield_just_expired"] = True
        except Exception:
            pass

    return user


def get_pending_notification(user: dict) -> Optional[str]:
    """
    Pop and return any pending notification for the player.
    Clears it after retrieval so it only shows once.
    """
    notif = user.get("pending_notification", "").strip()
    if notif:
        user["pending_notification"] = ""
    return notif if notif else None
