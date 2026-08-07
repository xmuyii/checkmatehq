# -*- coding: utf-8 -*-
"""
private_sector.py — Private Sector Map & Village System
=========================================================
Every geographical sector has two layers:

PUBLIC LAYER (existing):
  - Open node map anyone can see
  - Contested resource nodes, PvP outpost, base plots
  - Visible to all players who teleport in

PRIVATE LAYER (this file):
  - Accessible only to residents (players granted access)
  - Shows named plots, player bases, resource plots, weather
  - Feels like a home territory — players see each other as nodes
  - Protected from environmental hazards (sector buffs still apply)
  - Has its own private chat channel

THE VILLAGE GROWTH LOOP:
  New Settlement (4 plots)
    → Village (8 plots)       — 500 AP contributed
    → Town (16 plots)         — 2000 AP contributed
    → Capital (24 plots)      — 5000 AP contributed

PLOT TYPES (inside private sector):
  base_plot       — A player's permanent home. Shows as named node.
  resource_plot   — Generates resources passively. Hazard-immune.
                    Can be destroyed after full depletion to make room for a base.
  market_plot     — Alliance trade post. Members exchange resources here.
  fortification   — Defensive structure. Reduces siege damage.
  empty_plot      — Unclaimed. New residents or conversions go here.

ENTRY MECHANICS:
  Outsider options when clicking the private sector node:
    1. Request Access  → sends visa to ruler (reveals some base info)
    2. Attack Fortress → siege on the private node (hardest fight)
    3. Observe         → see activity count, resource flow, no names

  Resident view:
    Full private map with named plots, player bases, private chat

  Sector Ruler view:
    Admin panel — set plot prices, manage residents, buffs, banishments
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ═══════════════════════════════════════════════════════════════════════════
#  SETTLEMENT TIERS
# ═══════════════════════════════════════════════════════════════════════════

SETTLEMENT_TIERS = {
    "settlement": {
        "name":         "Settlement",
        "emoji":        "🏕️",
        "max_plots":    4,
        "ap_to_next":   500,
        "next_tier":    "village",
        "description":  "A nascent outpost. Room for 4 plots. Grow it.",
        "fortress_hp":  500,
        "siege_bonus":  0,
    },
    "village": {
        "name":         "Village",
        "emoji":        "🏘️",
        "max_plots":    8,
        "ap_to_next":   2000,
        "next_tier":    "town",
        "description":  "A growing community. 8 plots. Starting to matter.",
        "fortress_hp":  1500,
        "siege_bonus":  10,
    },
    "town": {
        "name":         "Town",
        "emoji":        "🏙️",
        "max_plots":    16,
        "ap_to_next":   5000,
        "next_tier":    "capital",
        "description":  "A proper settlement. 16 plots. Other alliances notice.",
        "fortress_hp":  4000,
        "siege_bonus":  25,
    },
    "capital": {
        "name":         "Capital",
        "emoji":        "🏛️",
        "max_plots":    24,
        "ap_to_next":   None,   # Max tier
        "next_tier":    None,
        "description":  "The pinnacle of sector control. 24 plots. Dominate.",
        "fortress_hp":  10000,
        "siege_bonus":  50,
        "unique_ability": "Can generate sector-wide buffs for all alliance members",
    },
}

# ── Plot type definitions ─────────────────────────────────────────────────
PLOT_TYPES = {
    "base_plot": {
        "emoji":       "🏰",
        "label":       "Base",
        "description": "A player's permanent home. Shows who lives here.",
        "generates":   None,
        "destroyable": False,
        "hazard_immune": True,
    },
    "iron_plot": {
        "emoji":       "⛏️",
        "label":       "Iron Plot",
        "description": "Generates iron passively. Immune to hazards.",
        "generates":   "iron",
        "yield_per_hour": 20,
        "capacity":    500,
        "destroyable": True,
        "hazard_immune": True,
    },
    "stone_plot": {
        "emoji":       "🪨",
        "label":       "Stone Plot",
        "description": "Quarries stone continuously. Hazard-immune.",
        "generates":   "stone",
        "yield_per_hour": 15,
        "capacity":    400,
        "destroyable": True,
        "hazard_immune": True,
    },
    "relic_plot": {
        "emoji":       "🏺",
        "label":       "Relic Plot",
        "description": "Slowly uncovers relics. Rare. Very valuable.",
        "generates":   "relics",
        "yield_per_hour": 3,
        "capacity":    50,
        "destroyable": True,
        "hazard_immune": True,
    },
    "food_plot": {
        "emoji":       "🥫",
        "label":       "Hydroponic Bay",
        "description": "Generates rations for the settlement.",
        "generates":   "food",
        "yield_per_hour": 30,
        "capacity":    1000,
        "destroyable": True,
        "hazard_immune": True,
    },
    "market_plot": {
        "emoji":       "🏪",
        "label":       "Market",
        "description": "Alliance trade post. Members exchange resources here.",
        "generates":   None,
        "destroyable": False,
        "hazard_immune": True,
        "special":     "trade_hub",
    },
    "fortification": {
        "emoji":       "🏯",
        "label":       "Fortification",
        "description": "Defensive structure. Reduces siege damage by 20%.",
        "generates":   None,
        "destroyable": True,
        "hazard_immune": True,
        "defense_bonus_pct": 20,
    },
    "empty_plot": {
        "emoji":       "⬜",
        "label":       "Empty Plot",
        "description": "Unclaimed. Can be developed or given to a new resident.",
        "generates":   None,
        "destroyable": False,
        "hazard_immune": True,
    },
}

# ── Weather effects inside private sector (mirrors sector cycle but gentler) ──
PRIVATE_WEATHER = {
    "calm":        {"emoji": "☀️",  "desc": "Clear skies. All yields normal.",          "yield_mod": 1.0},
    "rain":        {"emoji": "🌧️", "desc": "Rain. Hydroponic Bay plots +50% rations yield.",         "yield_mod": 1.0, "food_mod": 1.5},
    "storm":       {"emoji": "⛈️", "desc": "Storm. Iron plots +30% yield. Visibility reduced.", "yield_mod": 1.0, "iron_mod": 1.3},
    "heatwave":    {"emoji": "🔥",  "desc": "Heatwave. Stone plots +20%. Rations plots -30%.", "stone_mod": 1.2, "food_mod": 0.7, "yield_mod": 1.0},
    "fog":         {"emoji": "🌫️", "desc": "Dense fog. All yields -20%. Stealth enhanced.", "yield_mod": 0.8},
    "aurora":      {"emoji": "🌌",  "desc": "Aurora event. All yields +25% for 30 minutes.", "yield_mod": 1.25, "rare": True},
}


# ═══════════════════════════════════════════════════════════════════════════
#  PRIVATE SECTOR STATE
# ═══════════════════════════════════════════════════════════════════════════

def get_private_sector(sector_state: dict) -> dict:
    """Get the private sector data from sector state."""
    ps = sector_state.get("private_sector", {})
    if not isinstance(ps, dict):
        ps = {}
    return ps


def init_private_sector(sector_id: int, founding_ruler_id: str,
                         founding_ruler_name: str) -> dict:
    """
    Create a new private sector for a geographical sector.
    Called when a sector ruler first establishes a settlement.
    Starts as a Settlement with 4 empty plots.
    """
    now = datetime.utcnow()

    plots = {}
    for i in range(4):
        plot_id = f"plot_{chr(65 + i)}"   # A, B, C, D
        plots[plot_id] = {
            "type":       "empty_plot",
            "owner_id":   None,
            "owner_name": None,
            "name":       f"Plot {chr(65 + i)}",
            "pending_resources": 0.0,
            "last_tick":  now.isoformat(),
            "created_at": now.isoformat(),
        }

    return {
        "sector_id":       sector_id,
        "tier":            "settlement",
        "tier_name":       "Settlement",
        "ap_contributed":  0,
        "ruler_id":        founding_ruler_id,
        "ruler_name":      founding_ruler_name,
        "founding_date":   now.isoformat(),
        "plots":           plots,
        "residents":       {founding_ruler_id: {
            "player_name": founding_ruler_name,
            "joined_at":   now.isoformat(),
            "role":        "ruler",
        }},
        "access_requests": [],
        "fortress_hp":     SETTLEMENT_TIERS["settlement"]["fortress_hp"],
        "fortress_max_hp": SETTLEMENT_TIERS["settlement"]["fortress_hp"],
        "reinforcements":  {},   # {player_id: troop_count}
        "private_chat":    [],
        "weather":         "calm",
        "weather_started": now.isoformat(),
        "buffs":           [],
        "is_open":         False,   # Ruler can open to all alliance members
    }


def is_resident(private_sector: dict, player_id: str) -> bool:
    """Check if a player is a resident of the private sector."""
    residents = private_sector.get("residents", {})
    return player_id in residents


def is_ruler(private_sector: dict, player_id: str) -> bool:
    """Check if a player is the ruler of the private sector."""
    return private_sector.get("ruler_id") == player_id


def get_resident_role(private_sector: dict, player_id: str) -> Optional[str]:
    """Get a resident's role (ruler, member, guest)."""
    residents = private_sector.get("residents", {})
    resident  = residents.get(player_id, {})
    return resident.get("role") if isinstance(resident, dict) else None


# ═══════════════════════════════════════════════════════════════════════════
#  ACCESS CONTROL
# ═══════════════════════════════════════════════════════════════════════════

def request_access(
    private_sector: dict,
    player_id: str,
    player_name: str,
    player_home_sector: Optional[int],
    player_base_name: str,
    troop_count: int,
) -> Tuple[bool, str, dict]:
    """
    Player requests access to a private sector.
    Reveals partial base information to the ruler.
    Returns (success, message_to_player, updated_private_sector)
    """
    if is_resident(private_sector, player_id):
        return False, "✅ You already have access to this settlement.", private_sector

    # Check for existing request
    requests = private_sector.get("access_requests", [])
    if any(r.get("player_id") == player_id for r in requests):
        return False, "⏳ Your access request is pending ruler approval.", private_sector

    request = {
        "player_id":         player_id,
        "player_name":       player_name,
        "home_sector":       player_home_sector,
        "base_name":         player_base_name,
        "troop_count":       troop_count,
        "requested_at":      datetime.utcnow().isoformat(),
        "status":            "pending",
    }
    requests.append(request)
    private_sector["access_requests"] = requests

    tier   = private_sector.get("tier", "settlement")
    t_data = SETTLEMENT_TIERS.get(tier, {})

    return True, (
        f"🛂 *Access request sent to {t_data.get('emoji','')} "
        f"{private_sector.get('tier_name','Settlement')}*\n\n"
        f"The ruler will review your application.\n"
        f"⚠️ *Your home sector has been revealed to the ruler.*\n"
        f"You will be notified when approved or denied."
    ), private_sector


def approve_access(
    private_sector: dict,
    ruler_id: str,
    applicant_id: str,
    role: str = "member",
) -> Tuple[bool, str, dict, Optional[str]]:
    """
    Ruler approves an access request.
    Returns (success, ruler_message, updated_ps, applicant_notification)
    """
    if not is_ruler(private_sector, ruler_id):
        return False, "❌ Only the ruler can approve access.", private_sector, None

    requests = private_sector.get("access_requests", [])
    applicant = None
    for r in requests:
        if r.get("player_id") == applicant_id and r.get("status") == "pending":
            applicant = r
            r["status"] = "approved"
            break

    if not applicant:
        return False, "❌ Request not found.", private_sector, None

    # Add to residents
    if "residents" not in private_sector:
        private_sector["residents"] = {}
    private_sector["residents"][applicant_id] = {
        "player_name": applicant["player_name"],
        "joined_at":   datetime.utcnow().isoformat(),
        "role":        role,
        "home_sector": applicant.get("home_sector"),
    }

    tier_data = SETTLEMENT_TIERS.get(private_sector.get("tier", "settlement"), {})
    tier_name = private_sector.get("tier_name", "Settlement")
    tier_emoji = tier_data.get("emoji", "🏕️")

    notif = (
        f"✅ *Access Granted!*\n"
        f"You have been admitted to {tier_emoji} *{tier_name}* "
        f"in Sector {private_sector.get('sector_id', '?')}.\n"
        f"You are now a resident. Open the sector map to enter."
    )

    return True, (
        f"✅ @{applicant['player_name']} admitted as {role}."
    ), private_sector, notif


def deny_access(
    private_sector: dict,
    ruler_id: str,
    applicant_id: str,
    reason: str = "Request denied by ruler",
) -> Tuple[bool, str, dict, Optional[str]]:
    """Ruler denies an access request."""
    if not is_ruler(private_sector, ruler_id):
        return False, "❌ Only the ruler can deny access.", private_sector, None

    requests = private_sector.get("access_requests", [])
    applicant_name = "Unknown"
    for r in requests:
        if r.get("player_id") == applicant_id and r.get("status") == "pending":
            r["status"] = "denied"
            applicant_name = r.get("player_name", "Unknown")
            break

    notif = (
        f"❌ *Access Denied*\n"
        f"Your request to enter the private sector was denied.\n"
        f"Reason: {reason}"
    )
    return True, f"❌ @{applicant_name}'s request denied.", private_sector, notif


def evict_resident(
    private_sector: dict,
    ruler_id: str,
    resident_id: str,
) -> Tuple[bool, str, dict, Optional[str]]:
    """Ruler removes a resident from the private sector."""
    if not is_ruler(private_sector, ruler_id):
        return False, "❌ Only the ruler can evict residents.", private_sector, None

    if resident_id == ruler_id:
        return False, "❌ Cannot evict yourself.", private_sector, None

    residents = private_sector.get("residents", {})
    if resident_id not in residents:
        return False, "❌ Player is not a resident.", private_sector, None

    resident_name = residents[resident_id].get("player_name", "Unknown")
    del residents[resident_id]
    private_sector["residents"] = residents

    # Reclaim their base plot if they have one
    plots = private_sector.get("plots", {})
    for plot_id, plot in plots.items():
        if plot.get("owner_id") == resident_id:
            plot["owner_id"]   = None
            plot["owner_name"] = None
            plot["type"]       = "empty_plot"
            plots[plot_id]     = plot

    private_sector["plots"] = plots

    notif = (
        f"🚫 *You have been evicted*\n"
        f"The sector ruler has removed your residency.\n"
        f"Your base plot has been reclaimed."
    )
    return True, f"✅ @{resident_name} evicted.", private_sector, notif


# ═══════════════════════════════════════════════════════════════════════════
#  PLOT MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

def claim_plot(
    private_sector: dict,
    player_id: str,
    player_name: str,
    plot_id: str,
    plot_type: str = "base_plot",
) -> Tuple[bool, str, dict]:
    """
    Resident claims an empty plot.
    Base plots become the player's permanent home in this sector.
    """
    if not is_resident(private_sector, player_id):
        return False, "❌ You are not a resident of this settlement.", private_sector

    plots = private_sector.get("plots", {})
    if plot_id not in plots:
        return False, f"❌ Plot {plot_id} does not exist.", private_sector

    plot = plots[plot_id]
    if plot.get("type") != "empty_plot" or plot.get("owner_id"):
        return False, f"❌ Plot {plot_id} is already occupied.", private_sector

    if plot_type not in PLOT_TYPES:
        return False, f"❌ Unknown plot type: {plot_type}", private_sector

    plot["type"]       = plot_type
    plot["owner_id"]   = player_id
    plot["owner_name"] = player_name
    plot["claimed_at"] = datetime.utcnow().isoformat()
    plot["last_tick"]  = datetime.utcnow().isoformat()
    plot["pending_resources"] = 0.0
    plots[plot_id]     = plot
    private_sector["plots"] = plots

    ptype_data = PLOT_TYPES[plot_type]
    return True, (
        f"✅ *{plot_id} claimed as {ptype_data['label']}*\n"
        f"{ptype_data['description']}"
    ), private_sector


def tick_resource_plots(private_sector: dict, phase_multiplier: float = 1.0) -> dict:
    """
    Tick all resource plots — accumulate resources based on time elapsed.
    Called by scheduler every 60 seconds.
    Resource plots are hazard-immune but still benefit from sector phase buffs.
    """
    now   = datetime.utcnow()
    plots = private_sector.get("plots", {})

    for plot_id, plot in plots.items():
        plot_type = plot.get("type", "empty_plot")
        ptype_data = PLOT_TYPES.get(plot_type, {})

        yield_per_hour = ptype_data.get("yield_per_hour", 0)
        capacity       = ptype_data.get("capacity", 0)
        if yield_per_hour == 0 or capacity == 0:
            continue

        last_tick_str = plot.get("last_tick")
        if last_tick_str:
            try:
                last_tick    = datetime.fromisoformat(last_tick_str)
                hours_elapsed = (now - last_tick).total_seconds() / 3600
            except Exception:
                hours_elapsed = 0
        else:
            hours_elapsed = 0

        if hours_elapsed <= 0:
            continue

        # Apply weather modifier
        weather     = private_sector.get("weather", "calm")
        weather_data = PRIVATE_WEATHER.get(weather, {})
        resource    = ptype_data.get("generates", "")

        # Base yield mod
        yield_mod = weather_data.get("yield_mod", 1.0)

        # Resource-specific mod
        resource_mod_key = f"{resource}_mod"
        resource_mod     = weather_data.get(resource_mod_key, 1.0)

        earned   = yield_per_hour * hours_elapsed * yield_mod * resource_mod * phase_multiplier
        pending  = plot.get("pending_resources", 0.0)
        space    = capacity - pending
        plot["pending_resources"] = pending + min(earned, space)
        plot["last_tick"]         = now.isoformat()
        plots[plot_id]            = plot

    private_sector["plots"] = plots
    return private_sector


def collect_plot_resources(
    private_sector: dict,
    player_id: str,
    plot_id: str,
    user: dict,
) -> Tuple[bool, str, dict, dict]:
    """
    Player collects accumulated resources from their plot.
    Returns (success, message, updated_ps, updated_user)
    """
    plots = private_sector.get("plots", {})
    if plot_id not in plots:
        return False, "❌ Plot not found.", private_sector, user

    plot = plots[plot_id]
    if plot.get("owner_id") != player_id:
        return False, "❌ This is not your plot.", private_sector, user

    pending  = plot.get("pending_resources", 0.0)
    if pending <= 0:
        return False, "📭 Nothing to collect yet.", private_sector, user

    plot_type  = plot.get("type", "empty_plot")
    ptype_data = PLOT_TYPES.get(plot_type, {})
    resource   = ptype_data.get("generates")
    if not resource:
        return False, "❌ This plot type generates no resources.", private_sector, user

    amount = int(pending)
    plot["pending_resources"] = 0.0
    plots[plot_id]            = plot
    private_sector["plots"]   = plots

    # Add to user inventory
    inv = user.get("inventory", {})
    if not isinstance(inv, dict):
        inv = {}
    if resource in inv:
        inv[resource]["qty"] = inv[resource].get("qty", 0) + amount
    else:
        inv[resource] = {"qty": amount, "display": resource.title(),
                         "emoji": "📦", "category": "basic"}
    user["inventory"] = inv

    from resource_registry import get_emoji, get_display_name
    try:
        emoji = get_emoji(resource)
        rname = get_display_name(resource)
    except Exception:
        emoji = "📦"
        rname = resource

    return True, (
        f"✅ Collected {emoji} *{amount} {rname}* from {plot_id}."
    ), private_sector, user


def destroy_resource_plot(
    private_sector: dict,
    ruler_id: str,
    plot_id: str,
) -> Tuple[bool, str, dict]:
    """
    Ruler destroys a depleted resource plot to create an empty plot.
    Allows a new resident base to be placed here.
    """
    if not is_ruler(private_sector, ruler_id):
        return False, "❌ Only the ruler can convert plots.", private_sector

    plots = private_sector.get("plots", {})
    if plot_id not in plots:
        return False, f"❌ Plot {plot_id} not found.", private_sector

    plot      = plots[plot_id]
    plot_type = plot.get("type", "")
    ptype     = PLOT_TYPES.get(plot_type, {})

    if not ptype.get("destroyable", False):
        return False, f"❌ {ptype.get('label','Plot')} cannot be converted.", private_sector

    pending = plot.get("pending_resources", 0)
    if pending > 50:
        return False, (
            f"❌ Plot still has {int(pending)} resources pending.\n"
            f"Collect first or wait for it to deplete."
        ), private_sector

    plot["type"]       = "empty_plot"
    plot["owner_id"]   = None
    plot["owner_name"] = None
    plot["pending_resources"] = 0.0
    plots[plot_id]     = plot
    private_sector["plots"] = plots

    return True, (
        f"✅ *{plot_id}* converted to empty plot.\n"
        f"A new resident can now claim it."
    ), private_sector


def expand_settlement(
    private_sector: dict,
    ruler_id: str,
) -> Tuple[bool, str, dict]:
    """
    Upgrade settlement tier when enough AP has been contributed.
    Adds new plot slots.
    """
    if not is_ruler(private_sector, ruler_id):
        return False, "❌ Only the ruler can upgrade the settlement.", private_sector

    current_tier = private_sector.get("tier", "settlement")
    tier_data    = SETTLEMENT_TIERS.get(current_tier, {})
    ap_needed    = tier_data.get("ap_to_next")
    next_tier    = tier_data.get("next_tier")

    if not next_tier or not ap_needed:
        return False, "🏛️ This settlement has reached maximum tier (Capital).", private_sector

    ap_contributed = private_sector.get("ap_contributed", 0)
    if ap_contributed < ap_needed:
        return False, (
            f"❌ Need {ap_needed} AP contributed. Currently: {ap_contributed}.\n"
            f"Need {ap_needed - ap_contributed} more AP."
        ), private_sector

    # Upgrade tier
    next_data  = SETTLEMENT_TIERS[next_tier]
    old_max    = tier_data["max_plots"]
    new_max    = next_data["max_plots"]
    new_plots  = new_max - old_max

    private_sector["tier"]      = next_tier
    private_sector["tier_name"] = next_data["name"]
    private_sector["fortress_hp"]     = next_data["fortress_hp"]
    private_sector["fortress_max_hp"] = next_data["fortress_hp"]

    # Add new empty plots
    plots    = private_sector.get("plots", {})
    now      = datetime.utcnow().isoformat()
    existing = len(plots)
    for i in range(new_plots):
        idx      = existing + i
        plot_id  = f"plot_{chr(65 + idx)}" if idx < 26 else f"plot_{idx}"
        plots[plot_id] = {
            "type": "empty_plot", "owner_id": None, "owner_name": None,
            "name": f"Plot {chr(65 + idx) if idx < 26 else str(idx)}",
            "pending_resources": 0.0,
            "last_tick": now, "created_at": now,
        }
    private_sector["plots"] = plots

    return True, (
        f"🎉 *Settlement upgraded to {next_data['emoji']} {next_data['name']}!*\n"
        f"{next_data['description']}\n"
        f"+{new_plots} new plots available."
    ), private_sector


def contribute_ap_to_settlement(
    private_sector: dict,
    player_id: str,
    ap_amount: int,
) -> Tuple[dict, bool, Optional[str]]:
    """
    Player contributes AP to grow the settlement.
    Returns (updated_ps, tier_upgraded, upgrade_message)
    """
    private_sector["ap_contributed"] = private_sector.get("ap_contributed", 0) + ap_amount

    current_tier = private_sector.get("tier", "settlement")
    tier_data    = SETTLEMENT_TIERS.get(current_tier, {})
    ap_needed    = tier_data.get("ap_to_next")
    ap_total     = private_sector["ap_contributed"]

    if ap_needed and ap_total >= ap_needed and tier_data.get("next_tier"):
        # Auto-upgrade
        _, msg, private_sector = expand_settlement(
            private_sector, private_sector.get("ruler_id", player_id)
        )
        return private_sector, True, msg

    return private_sector, False, None


# ═══════════════════════════════════════════════════════════════════════════
#  FORTRESS SIEGE MECHANICS
# ═══════════════════════════════════════════════════════════════════════════

def get_fortress_status(private_sector: dict) -> dict:
    """Get the current fortress HP and defense status."""
    hp      = private_sector.get("fortress_hp", 500)
    max_hp  = private_sector.get("fortress_max_hp", 500)
    tier    = private_sector.get("tier", "settlement")
    tdata   = SETTLEMENT_TIERS.get(tier, {})
    siege_bonus = tdata.get("siege_bonus", 0)

    # Count fortification plots
    plots = private_sector.get("plots", {})
    fort_count = sum(
        1 for p in plots.values()
        if p.get("type") == "fortification"
    )
    fort_bonus = fort_count * 20  # Each fortification adds 20% reduction

    # Count reinforcing troops
    reinforcements = private_sector.get("reinforcements", {})
    total_troops   = sum(reinforcements.values())

    pct = max(0, min(100, int(hp / max(max_hp, 1) * 100)))
    bar_filled = pct // 5
    hp_bar = "█" * bar_filled + "░" * (20 - bar_filled)

    return {
        "hp":              hp,
        "max_hp":          max_hp,
        "pct":             pct,
        "hp_bar":          hp_bar,
        "siege_bonus_pct": siege_bonus + fort_bonus,
        "fort_count":      fort_count,
        "troop_count":     total_troops,
        "tier":            tier,
    }


def attack_fortress(
    private_sector: dict,
    attacker_id: str,
    attacker_name: str,
    attacker_power: int,
) -> Tuple[dict, bool, str]:
    """
    Attacker assaults the private sector fortress.
    Defenders get a bonus from fortifications and reinforcing troops.
    Returns (updated_ps, fortress_fell, battle_report)
    """
    import random

    status       = get_fortress_status(private_sector)
    current_hp   = status["hp"]
    defense_mult = 1.0 - (status["siege_bonus_pct"] / 100)
    defense_mult = max(0.3, defense_mult)  # Min 30% of damage goes through

    # Troop reinforcements add to effective defense power
    troop_defense = status["troop_count"] * 2
    effective_defense = int(current_hp * 0.1) + troop_defense  # HP-based + troops

    # Roll
    atk_roll = attacker_power * random.uniform(0.8, 1.2)
    def_roll  = effective_defense * random.uniform(0.8, 1.2) / defense_mult

    damage_dealt = max(10, int(atk_roll * 0.3 * defense_mult))
    new_hp       = max(0, current_hp - damage_dealt)

    private_sector["fortress_hp"] = new_hp
    fortress_fell = new_hp <= 0

    # Log in private sector chat
    now = datetime.utcnow()
    ps_chat = private_sector.get("private_chat", [])
    ps_chat.insert(0, {
        "player_id":   "SYSTEM",
        "player_name": "⚙️ FORTRESS",
        "message":     f"⚔️ @{attacker_name} assaulted the fortress! HP: {new_hp}/{status['max_hp']}",
        "timestamp":   now.isoformat(),
        "time_str":    now.strftime("%H:%M"),
        "is_system":   True,
    })
    private_sector["private_chat"] = ps_chat[:30]

    if fortress_fell:
        # Fortress captured — attacker becomes new ruler
        old_ruler   = private_sector.get("ruler_name", "Unknown")
        private_sector["ruler_id"]   = attacker_id
        private_sector["ruler_name"] = attacker_name
        private_sector["fortress_hp"] = private_sector["fortress_max_hp"] // 2  # Reset to 50%
        private_sector["reinforcements"] = {}

        report = (
            f"💥 *FORTRESS CAPTURED!*\n"
            f"@{attacker_name} has breached the defenses!\n"
            f"@{old_ruler} has been deposed.\n"
            f"@{attacker_name} is now the new ruler.\n\n"
            f"Damage dealt: {damage_dealt}"
        )
    else:
        pct_remain = int(new_hp / max(status["max_hp"], 1) * 100)
        report = (
            f"⚔️ *FORTRESS UNDER ATTACK*\n"
            f"@{attacker_name} struck the fortress!\n"
            f"Damage: {damage_dealt}  |  HP remaining: {pct_remain}%\n"
            f"[{status['hp_bar']}]\n"
            f"The fortress held — for now."
        )

    return private_sector, fortress_fell, report


def reinforce_fortress(
    private_sector: dict,
    player_id: str,
    player_name: str,
    troop_count: int,
) -> Tuple[bool, str, dict]:
    """
    Any alliance member or friendly player can send troops to reinforce the fortress.
    Troops stay until the fortress falls or they are recalled.
    """
    reinforcements = private_sector.get("reinforcements", {})
    if not isinstance(reinforcements, dict):
        reinforcements = {}

    reinforcements[player_id] = reinforcements.get(player_id, 0) + troop_count
    private_sector["reinforcements"] = reinforcements

    total = sum(reinforcements.values())
    return True, (
        f"🛡️ *{troop_count} troops sent to reinforce the fortress!*\n"
        f"Total garrison: {total} troops"
    ), private_sector


# ═══════════════════════════════════════════════════════════════════════════
#  PRIVATE SECTOR CHAT
# ═══════════════════════════════════════════════════════════════════════════

def post_private_chat(
    private_sector: dict,
    player_id: str,
    player_name: str,
    message: str,
    is_system: bool = False,
) -> Tuple[dict, str]:
    """Post a message to the private sector chat. Residents only."""
    if "private_chat" not in private_sector or not isinstance(private_sector.get("private_chat"), list):
        private_sector["private_chat"] = []

    message = message[:200]
    now     = datetime.utcnow()

    entry = {
        "player_id":   player_id if not is_system else "SYSTEM",
        "player_name": player_name if not is_system else "⚙️ SECTOR",
        "message":     message,
        "timestamp":   now.isoformat(),
        "time_str":    now.strftime("%H:%M"),
        "is_system":   is_system,
    }

    private_sector["private_chat"].insert(0, entry)
    private_sector["private_chat"] = private_sector["private_chat"][:30]

    return private_sector, f"[{entry['time_str']}] *{entry['player_name']}*: {message}"


# ═══════════════════════════════════════════════════════════════════════════
#  WEATHER SYSTEM
# ═══════════════════════════════════════════════════════════════════════════

def tick_weather(private_sector: dict) -> Tuple[dict, Optional[str]]:
    """
    Advance weather in the private sector.
    Weather changes every 30-90 minutes. Rare aurora event possible.
    Returns (updated_ps, weather_change_message or None)
    """
    import random

    now           = datetime.utcnow()
    started_str   = private_sector.get("weather_started", now.isoformat())
    try:
        started       = datetime.fromisoformat(started_str)
        elapsed_mins  = (now - started).total_seconds() / 60
    except Exception:
        elapsed_mins  = 999

    current = private_sector.get("weather", "calm")
    # Change weather every 30-90 minutes
    change_after = 30 + (hash(started_str) % 60)

    if elapsed_mins < change_after:
        return private_sector, None

    # Pick new weather (aurora is rare — 5% chance)
    weather_pool = ["calm", "rain", "storm", "heatwave", "fog"]
    if random.random() < 0.05:
        new_weather = "aurora"
    else:
        options = [w for w in weather_pool if w != current]
        new_weather = random.choice(options)

    private_sector["weather"]         = new_weather
    private_sector["weather_started"] = now.isoformat()

    wdata  = PRIVATE_WEATHER.get(new_weather, {})
    emoji  = wdata.get("emoji", "🌍")
    desc   = wdata.get("desc", "")

    msg = f"{emoji} *Weather changed:* {desc}"
    return private_sector, msg


# ═══════════════════════════════════════════════════════════════════════════
#  DISPLAY FORMATTERS
# ═══════════════════════════════════════════════════════════════════════════

def format_private_sector_map(
    private_sector: dict,
    viewer_id: str,
) -> str:
    """
    Full private sector map for a resident.
    Shows plots, owners, resources, weather, fortress status.
    """
    tier      = private_sector.get("tier", "settlement")
    tdata     = SETTLEMENT_TIERS.get(tier, {})
    tier_name = tdata.get("name", "Settlement")
    tier_emoji = tdata.get("emoji", "🏕️")
    ruler_name = private_sector.get("ruler_name", "Unknown")
    sector_id  = private_sector.get("sector_id", "?")
    weather    = private_sector.get("weather", "calm")
    wdata      = PRIVATE_WEATHER.get(weather, {})
    w_emoji    = wdata.get("emoji", "☀️")
    w_desc     = wdata.get("desc", "")

    plots      = private_sector.get("plots", {})
    residents  = private_sector.get("residents", {})
    fortress   = get_fortress_status(private_sector)
    ap_total   = private_sector.get("ap_contributed", 0)
    ap_needed  = tdata.get("ap_to_next", 0) or 0

    lines = [
        f"{tier_emoji} *{tier_name}* — Sector {sector_id}",
        f"👑 Ruler: @{ruler_name}  |  👥 {len(residents)} residents",
        f"{w_emoji} *Weather:* {w_desc}",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    # Fortress status
    hp_pct = fortress["pct"]
    lines.append(
        f"🏯 *Fortress:* {hp_pct}% HP  [{fortress['hp_bar']}]\n"
        f"   Defense bonus: {fortress['siege_bonus_pct']}%  "
        f"Troops: {fortress['troop_count']}"
    )

    # AP progress to next tier
    if ap_needed:
        ap_pct    = min(100, int(ap_total / ap_needed * 100))
        ap_filled = ap_pct // 10
        ap_bar    = "█" * ap_filled + "░" * (10 - ap_filled)
        lines.append(
            f"\n📈 *Growth:* [{ap_bar}] {ap_total}/{ap_needed} AP\n"
            f"   Next tier: {SETTLEMENT_TIERS.get(tdata.get('next_tier',''),'{}').get('name','Max tier')}"
        )

    lines.append(f"\n🗺️ *PLOTS:*")

    # Sort plots — base plots first, then resource, then empty
    def plot_sort_key(item):
        ptype = item[1].get("type", "empty_plot")
        order = {"base_plot": 0, "fortification": 1, "market_plot": 2,
                 "iron_plot": 3, "stone_plot": 3, "relic_plot": 3,
                 "food_plot": 3, "empty_plot": 9}
        return order.get(ptype, 5)

    for plot_id, plot in sorted(plots.items(), key=plot_sort_key):
        plot_type  = plot.get("type", "empty_plot")
        ptype_data = PLOT_TYPES.get(plot_type, {})
        emoji      = ptype_data.get("emoji", "⬜")
        label      = ptype_data.get("label", "Plot")
        owner_id   = plot.get("owner_id")
        owner_name = plot.get("owner_name", "")
        pending    = int(plot.get("pending_resources", 0))
        generates  = ptype_data.get("generates")

        is_mine = owner_id == viewer_id

        if plot_type == "empty_plot":
            lines.append(f"  {emoji} [{plot_id}] *Empty* — Available")
        elif owner_id:
            mine_tag    = " 🟡 YOU" if is_mine else f" @{owner_name}"
            pending_str = f"  [{pending}⏳]" if generates and pending > 0 else ""
            lines.append(f"  {emoji} [{plot_id}] *{label}*{mine_tag}{pending_str}")
        else:
            lines.append(f"  {emoji} [{plot_id}] *{label}*")

    # Private chat preview
    chat = private_sector.get("private_chat", [])
    if chat:
        lines.append(f"\n💬 *SETTLEMENT CHAT:*")
        for entry in list(reversed(chat[:4])):
            t    = entry.get("time_str", "?")
            name = entry.get("player_name", "?")
            msg  = entry.get("message", "")
            is_sys = entry.get("is_system", False)
            if is_sys:
                lines.append(f"  _{t} {msg}_")
            else:
                lines.append(f"  [{t}] *{name}*: {msg}")

    lines.append(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def format_outsider_view(private_sector: dict) -> str:
    """
    What an outsider sees when they click the private sector node.
    No names, no specifics — just enough to be intriguing.
    """
    tier      = private_sector.get("tier", "settlement")
    tdata     = SETTLEMENT_TIERS.get(tier, {})
    tier_name = tdata.get("name", "Settlement")
    tier_emoji = tdata.get("emoji", "🏕️")
    residents = private_sector.get("residents", {})
    plots     = private_sector.get("plots", {})
    fortress  = get_fortress_status(private_sector)

    occupied_plots = sum(1 for p in plots.values() if p.get("owner_id"))
    resource_plots = sum(1 for p in plots.values()
                         if PLOT_TYPES.get(p.get("type",""), {}).get("generates"))

    return (
        f"{tier_emoji} *Private {tier_name}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 *Residents:* {len(residents)}\n"
        f"🗺️ *Plots:* {occupied_plots}/{len(plots)} occupied\n"
        f"⛏️ *Resource operations:* {resource_plots} active\n"
        f"🏯 *Fortress:* {fortress['pct']}% integrity\n\n"
        f"_Entry is restricted. Request access or take it by force._\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━"
    )


def format_access_queue(private_sector: dict) -> str:
    """Format pending access requests for ruler review."""
    requests = [r for r in private_sector.get("access_requests", [])
                if r.get("status") == "pending"]

    if not requests:
        return "📋 *Access Queue*\n\n_No pending requests._"

    from teleport_system import SECTOR_QUICK_INFO
    lines = [f"📋 *ACCESS REQUESTS ({len(requests)} pending)*\n━━━━━━━━━━━━━━━━━━━━━━━━"]

    for r in requests:
        name        = r.get("player_name", "?")
        home_sid    = r.get("home_sector")
        base_name   = r.get("base_name", "Unknown Base")
        troops      = r.get("troop_count", 0)
        pid         = r.get("player_id", "")

        home_str = ""
        if home_sid:
            hi = SECTOR_QUICK_INFO.get(home_sid, {})
            home_str = f"\n  🏠 Home: {hi.get('emoji','')} {hi.get('name', f'S{home_sid}')}"

        lines.append(
            f"\n👤 *@{name}*{home_str}\n"
            f"  Base: {base_name}  |  Army: {troops} troops\n"
            f"  `!approve {pid}` or `!deny {pid}`"
        )

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
#  INLINE KEYBOARDS
# ═══════════════════════════════════════════════════════════════════════════

def kb_private_sector_outsider(sector_id: int, private_sector: dict,  user: dict) -> InlineKeyboardMarkup:
    """Keyboard shown to outsiders clicking the private sector node."""
    tier      = private_sector.get("tier", "settlement")
    tdata     = SETTLEMENT_TIERS.get(tier, {})
    tier_emoji = tdata.get("emoji", "🏕️")
    
    sector = user.get("commander_location", "unknown")

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"🛂 Request Access to {tier_emoji} {tdata.get('name','Settlement')}",
            callback_data=f"ps:request:{sector_id}"
        )],
        [InlineKeyboardButton(
            text="⚔️ Attack the Fortress",
            callback_data=f"ps:attack_fortress:{sector_id}"
        )],
        [InlineKeyboardButton(
            text="👁️ Observe (no access needed)",
            callback_data=f"ps:observe:{sector_id}"
        )],
        [InlineKeyboardButton(
            text="🛡️ Reinforce Fortress",
            callback_data=f"ps:reinforce:{sector_id}"
        )],
        [InlineKeyboardButton(text="⬅️ Back to Sector", callback_data=f"sec_map:{sector}")],
    ])


def kb_private_sector_resident(sector_id: int, viewer_id: str,
                                 private_sector: dict) -> InlineKeyboardMarkup:
    """Keyboard for residents inside the private sector."""
    is_r = is_ruler(private_sector, viewer_id)
    buttons = [
        [
            InlineKeyboardButton(text="🗺️ View Plots",    callback_data=f"ps:plots:{sector_id}"),
            InlineKeyboardButton(text="💬 Private Chat",  callback_data=f"ps:chat:{sector_id}"),
        ],
        [
            InlineKeyboardButton(text="📦 Collect All",  callback_data=f"ps:collect_all:{sector_id}"),
            InlineKeyboardButton(text="🛡️ Reinforce",    callback_data=f"ps:reinforce:{sector_id}"),
        ],
    ]

    if is_r:
        buttons.append([
            InlineKeyboardButton(text="👑 Ruler Admin",   callback_data=f"ps:ruler_panel:{sector_id}"),
            InlineKeyboardButton(text="📋 Access Queue",  callback_data=f"ps:access_queue:{sector_id}"),
        ])
        buttons.append([
            InlineKeyboardButton(text="📈 Upgrade Settlement", callback_data=f"ps:upgrade:{sector_id}"),
        ])

    buttons.append([InlineKeyboardButton(text="⬅️ Sector", callback_data=f"sector:dashboard:{sector_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_ruler_admin(sector_id: int) -> InlineKeyboardMarkup:
    """Ruler admin panel keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Access Queue",  callback_data=f"ps:access_queue:{sector_id}"),
            InlineKeyboardButton(text="👥 Residents",     callback_data=f"ps:residents:{sector_id}"),
        ],
        [
            InlineKeyboardButton(text="🗺️ Convert Plot",  callback_data=f"ps:convert_plot:{sector_id}"),
            InlineKeyboardButton(text="🌍 Sector Buffs",  callback_data=f"ps:buffs:{sector_id}"),
        ],
        [
            InlineKeyboardButton(text="📜 Banish Member", callback_data=f"ps:banish:{sector_id}"),
            InlineKeyboardButton(text="🔓 Open/Close",    callback_data=f"ps:toggle_open:{sector_id}"),
        ],
        [InlineKeyboardButton(text="⬅️ Back", callback_data=f"ps:map:{sector_id}")],
    ])


def kb_plot_actions(sector_id: int, plot_id: str, plot: dict,
                     viewer_id: str) -> InlineKeyboardMarkup:
    """Actions for a specific plot."""
    plot_type  = plot.get("type", "empty_plot")
    owner_id   = plot.get("owner_id")
    is_mine    = owner_id == viewer_id
    generates  = PLOT_TYPES.get(plot_type, {}).get("generates")
    pending    = int(plot.get("pending_resources", 0))

    buttons = []

    if plot_type == "empty_plot":
        buttons.append([InlineKeyboardButton(
            text="🏰 Claim as Base",
            callback_data=f"ps:claim_plot:{sector_id}:{plot_id}:base_plot"
        )])
        buttons.append([InlineKeyboardButton(
            text="⛏️ Claim as Resource Plot",
            callback_data=f"ps:claim_menu:{sector_id}:{plot_id}"
        )])
    elif is_mine and generates and pending > 0:
        buttons.append([InlineKeyboardButton(
            text=f"📦 Collect ({pending} pending)",
            callback_data=f"ps:collect:{sector_id}:{plot_id}"
        )])

    buttons.append([InlineKeyboardButton(text="⬅️ Back", callback_data=f"ps:map:{sector_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
