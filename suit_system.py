# -*- coding: utf-8 -*-
"""
suit_system.py — Protective Suit & Item System
===============================================
Manages all consumable protective items — suits, formats, wallets.

MECHANICS:
  - Suits are consumed on equip (one-time use)
  - Timer starts the moment a suit is equipped — no pausing
  - Dashboard shows countdown prominently
  - When suit expires in a hazardous phase → unprotected penalties begin
  - Multiple suit types for different hazards
  - Research required before purchase (enforced here and in store)
  - Alliance leaders can stock suits in alliance shop for members

SUIT TIERS:
  Tier 1: Basic Radiation Suit  — 10 min — lethal_heat, toxic_gas
  Tier 2: Hazmat Suit           — 20 min — + void_radiation
  Tier 2: Bitcoin Format        — 20 min — crypto hazards
  Tier 3: Void Suit             — 15 min — void_radiation only
  Tier 3: Cold Wallet           — 45 min — all crypto hazards

PENALTY SYSTEM (when unprotected in hazardous phase):
  Every 30 seconds without a suit in a lethal zone:
    - Troops at node take casualties
    - Pending resources drain/convert
    - After N ticks → auto-eject from sector
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from resource_registry import RESOURCES, is_unlocked, get_display_name, get_emoji

# ═══════════════════════════════════════════════════════════════════════════
#  SUIT CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

# All suit/protective items — pulled from resource_registry
SUIT_KEYS = [
    "basic_suit",
    "hazmat_suit",
    "void_suit",
    "bitcoin_format",
    "cold_wallet",
]

# Hazard types and which suits protect against them
HAZARD_PROTECTION = {
    "lethal_heat":          ["basic_suit", "hazmat_suit"],
    "toxic_gas":            ["basic_suit", "hazmat_suit"],
    "void_radiation":       ["hazmat_suit", "void_suit"],
    "reality_distortion":   ["void_suit"],
    "rug_pull":             ["bitcoin_format", "cold_wallet"],
    "crypto_scammer":       ["bitcoin_format", "cold_wallet"],
    "market_crash":         ["cold_wallet"],
    "51_percent_attack":    ["cold_wallet"],
}

# Penalty per tick (every 30 seconds) when unprotected
HAZARD_PENALTIES: Dict[str, dict] = {
    "lethal_heat": {
        "troop_loss_pct":     0.05,   # 5% of node troops die
        "resource_drain_pct": 0.10,   # 10% of pending resources destroyed
        "eject_after_ticks":  4,      # Auto-eject after 2 minutes unprotected
        "warning":            "🌋 The heat is killing your troops! Equip a Hazmat Suit or teleport NOW.",
        "eject_message":      "💀 Your troops couldn't survive the heat. Sector forces expelled your commander.",
    },
    "void_radiation": {
        "troop_loss_pct":     0.10,
        "resource_drain_pct": 0.15,
        "eject_after_ticks":  2,      # Only 1 minute — void is merciless
        "warning":            "🌑 Void radiation is corrupting your troops. Void Suit required or teleport.",
        "eject_message":      "💀 Reality collapsed around your position. Your forces were scattered.",
    },
    "reality_distortion": {
        "troop_loss_pct":     0.15,
        "resource_drain_pct": 0.20,
        "eject_after_ticks":  2,
        "warning":            "🌀 Reality is distorting. Only a Void Suit protects you here.",
        "eject_message":      "💀 The distortion shredded your formation. You were expelled.",
    },
    "toxic_gas": {
        "troop_loss_pct":     0.03,
        "resource_drain_pct": 0.05,
        "eject_after_ticks":  6,      # 3 minutes — slower, more forgiving
        "warning":            "☠️ Toxic gas is poisoning your troops slowly. Equip a suit or teleport.",
        "eject_message":      "💀 Your troops succumbed to the toxins. You were dragged to safety.",
    },
    "rug_pull": {
        "troop_loss_pct":     0.0,    # No troop deaths — digital hazard
        "resource_drain_pct": 0.0,
        "satoshi_convert_pct": 0.10,  # 10% of satoshi → crypto_dust per tick
        "eject_after_ticks":  4,
        "warning":            "🚨 Rug pull in progress! Your Satoshi is converting to Crypto Dust. Bitcoin Format required.",
        "eject_message":      "💀 The rug was pulled. Your holdings became worthless dust. You were expelled.",
    },
    "crypto_scammer": {
        "troop_loss_pct":     0.0,
        "resource_drain_pct": 0.0,
        "satoshi_drain_flat": 100,    # Flat 100 satoshi stolen per tick
        "eject_after_ticks":  3,
        "warning":            "⚠️ A crypto scammer is draining your wallet! Bitcoin Format required.",
        "eject_message":      "💀 The scammer drained your wallet completely. You were expelled.",
    },
    "market_crash": {
        "troop_loss_pct":     0.0,
        "resource_drain_pct": 0.50,   # 50% of ALL pending resources destroyed instantly
        "eject_after_ticks":  2,
        "warning":            "📉 MARKET CRASH! Only Cold Wallet holders survive. Teleport or equip NOW.",
        "eject_message":      "💀 The market wiped your holdings. You were liquidated and expelled.",
    },
}

PENALTY_TICK_SECONDS = 30   # Penalty applied every 30 seconds


# ═══════════════════════════════════════════════════════════════════════════
#  EQUIP A SUIT
# ═══════════════════════════════════════════════════════════════════════════

def equip_suit(user: dict, suit_key: str) -> Tuple[bool, str, dict]:
    """
    Equip a protective suit from the player's inventory.
    Consumes one unit of the suit item.
    Starts the suit timer immediately.

    Returns (success, message, updated_user)
    """
    # Check research gate
    if not is_unlocked(user, suit_key):
        res = RESOURCES.get(suit_key, {})
        required = res.get("research_required", "unknown")
        return False, (
            f"🔒 *{get_display_name(suit_key)}* is locked.\n"
            f"Research `{required}` to unlock it."
        ), user

    if suit_key not in SUIT_KEYS:
        return False, f"❌ {suit_key} is not a protective suit.", user

    # Check inventory
    inv = user.get("inventory", {})
    if suit_key not in inv or inv[suit_key].get("qty", 0) < 1:
        return False, (
            f"❌ You don't have a *{get_display_name(suit_key)}* in your backpack.\n"
            f"Buy one with `!store` or from the alliance shop."
        ), user

    # Check if already wearing a suit
    active = get_active_suit(user)
    if active:
        existing_name = get_display_name(active["suit_key"])
        return False, (
            f"⚠️ Already wearing *{existing_name}* ({_format_remaining(active)}  remaining).\n"
            f"You cannot stack protective suits."
        ), user

    # Consume from inventory
    inv[suit_key]["qty"] -= 1
    if inv[suit_key]["qty"] <= 0:
        del inv[suit_key]
    user["inventory"] = inv

    # Record active suit
    res = RESOURCES.get(suit_key, {})
    duration_minutes = res.get("duration_minutes", 10)
    expires_at = (datetime.utcnow() + timedelta(minutes=duration_minutes)).isoformat()

    user["active_suit"] = {
        "suit_key":       suit_key,
        "display_name":   get_display_name(suit_key),
        "emoji":          get_emoji(suit_key),
        "equipped_at":    datetime.utcnow().isoformat(),
        "expires_at":     expires_at,
        "duration_minutes": duration_minutes,
        "protects_against": res.get("protects_against", []),
        "hazard_ticks":   0,    # Count of unprotected ticks (reset on equip)
    }

    suit_emoji = get_emoji(suit_key)
    suit_name  = get_display_name(suit_key)

    return True, (
        f"{suit_emoji} *{suit_name}* equipped!\n"
        f"⏱️ Protection: *{duration_minutes} minutes*\n"
        f"🛡️ Protects against: {', '.join(res.get('protects_against', []))}\n"
        f"Timer runs continuously — it won't pause."
    ), user


def get_active_suit(user: dict) -> Optional[dict]:
    """
    Get the player's currently active suit, if any.
    Returns None if no suit is active or it has expired.
    Clears expired suits automatically.
    """
    active = user.get("active_suit")
    if not active:
        return None

    try:
        expires = datetime.fromisoformat(active["expires_at"])
        if datetime.utcnow() >= expires:
            # Expired — clear it
            user.pop("active_suit", None)
            return None
    except Exception:
        user.pop("active_suit", None)
        return None

    return active


def is_protected_against(user: dict, hazard_type: str) -> bool:
    """
    Check if the player is currently protected against a specific hazard.
    Returns True if active suit covers this hazard.
    """
    active = get_active_suit(user)
    if not active:
        return False
    return hazard_type in active.get("protects_against", [])


def get_suit_time_remaining(user: dict) -> Optional[int]:
    """
    Get seconds remaining on active suit.
    Returns None if no suit active.
    """
    active = get_active_suit(user)
    if not active:
        return None
    try:
        expires = datetime.fromisoformat(active["expires_at"])
        remaining = (expires - datetime.utcnow()).total_seconds()
        return max(0, int(remaining))
    except Exception:
        return None


def format_suit_status(user: dict) -> str:
    """
    Format suit status for dashboard display.
    Shows countdown if active, warning if unprotected.
    """
    active = get_active_suit(user)
    if active:
        remaining = get_suit_time_remaining(user)
        suit_emoji = active.get("emoji", "🧪")
        suit_name  = active.get("display_name", "Suit")
        time_str   = _format_remaining_seconds(remaining or 0)

        # Warning color based on time left
        if remaining and remaining < 120:    # Under 2 minutes
            urgency = "🚨"
        elif remaining and remaining < 300:  # Under 5 minutes
            urgency = "⚠️"
        else:
            urgency = "✅"

        return f"{urgency} {suit_emoji} *{suit_name}*: {time_str} remaining"
    else:
        return "🔓 No suit equipped"


# ═══════════════════════════════════════════════════════════════════════════
#  HAZARD PENALTY SYSTEM
# ═══════════════════════════════════════════════════════════════════════════

def apply_hazard_penalty(
    user: dict,
    sector_state: dict,
    sector_id: int,
    node_key: str,
    hazard_type: str,
) -> Tuple[dict, dict, str, bool]:
    """
    Apply one tick of hazard penalty to an unprotected player.
    Called every PENALTY_TICK_SECONDS when player is unprotected in a hazard phase.

    Returns:
        (updated_user, updated_sector_state, message, was_ejected)
    """
    penalty = HAZARD_PENALTIES.get(hazard_type)
    if not penalty:
        return user, sector_state, "", False

    occ_key   = f"{sector_id}:{node_key.upper()}"
    occupancy = sector_state.get("occupancy", {})
    occupant  = occupancy.get(occ_key, {})

    # Increment tick counter
    ticks = occupant.get("hazard_ticks", 0) + 1
    occupant["hazard_ticks"] = ticks

    messages = []

    # ── Troop losses ──────────────────────────────────────────────────────
    troop_loss_pct = penalty.get("troop_loss_pct", 0)
    if troop_loss_pct > 0:
        troops    = occupant.get("troops", {})
        total_lost = 0
        for unit in list(troops.keys()):
            lost = max(1, int(troops[unit] * troop_loss_pct))
            troops[unit] = max(0, troops[unit] - lost)
            total_lost += lost
        occupant["troops"] = troops
        if total_lost > 0:
            messages.append(f"💀 {total_lost} troops lost to {hazard_type.replace('_', ' ')}")

    # ── Resource drain ────────────────────────────────────────────────────
    drain_pct = penalty.get("resource_drain_pct", 0)
    if drain_pct > 0:
        pending = occupant.get("pending_resources", 0)
        drained = pending * drain_pct
        occupant["pending_resources"] = max(0, pending - drained)
        if drained > 0:
            messages.append(f"📉 {int(drained)} pending resources destroyed")

    # ── Satoshi conversion (rug pull) ─────────────────────────────────────
    satoshi_conv_pct = penalty.get("satoshi_convert_pct", 0)
    if satoshi_conv_pct > 0:
        inv = user.get("inventory", {})
        satoshi_held = inv.get("satoshi", {}).get("qty", 0)
        convert_amt  = int(satoshi_held * satoshi_conv_pct)
        if convert_amt > 0:
            # Deduct satoshi
            inv["satoshi"]["qty"] = max(0, satoshi_held - convert_amt)
            # Add crypto_dust
            dust_gained = convert_amt // 10   # 10 satoshi → 1 dust
            if "crypto_dust" in inv:
                inv["crypto_dust"]["qty"] = inv["crypto_dust"].get("qty", 0) + dust_gained
            else:
                inv["crypto_dust"] = {"qty": dust_gained, "display": "Crypto Dust",
                                       "emoji": "✨", "category": "crypto"}
            user["inventory"] = inv
            messages.append(f"⚡₿ {convert_amt} Satoshi converted to {dust_gained} Crypto Dust")

    # ── Satoshi flat drain (scammer) ──────────────────────────────────────
    satoshi_drain = penalty.get("satoshi_drain_flat", 0)
    if satoshi_drain > 0:
        inv = user.get("inventory", {})
        satoshi_held = inv.get("satoshi", {}).get("qty", 0)
        drained = min(satoshi_held, satoshi_drain)
        if drained > 0:
            inv["satoshi"]["qty"] = satoshi_held - drained
            user["inventory"] = inv
            messages.append(f"🦹 Scammer stole {drained} Satoshi from your wallet")

    # Update occupancy
    occupancy[occ_key] = occupant
    sector_state["occupancy"] = occupancy

    # ── Check for eject ───────────────────────────────────────────────────
    eject_after = penalty.get("eject_after_ticks", 4)
    was_ejected = False

    if ticks >= eject_after:
        was_ejected = True
        eject_msg   = penalty.get("eject_message", "💀 You were expelled from the sector.")

        # Auto-collect remaining resources before ejecting
        from sector_nodes import auto_collect_on_departure
        sector_state, user, collected = auto_collect_on_departure(
            sector_state, sector_id, node_key, user.get("user_id", ""), user
        )

        # Force teleport home
        home_sector = user.get("home_sector", 1)
        user["commander_location"] = {"sector_id": home_sector}
        user["current_node"] = None

        # Record the eject
        if "eject_log" not in user:
            user["eject_log"] = []
        user["eject_log"].append({
            "sector_id":   sector_id,
            "node_key":    node_key,
            "hazard":      hazard_type,
            "ticks":       ticks,
            "ejected_at":  datetime.utcnow().isoformat(),
        })

        collected_str = ""
        if collected:
            from resource_registry import RESOURCES as RES
            parts = [f"{RES.get(k,{}).get('emoji','📦')}{v}" for k, v in collected.items()]
            collected_str = f"\nAuto-collected before ejection: {' '.join(parts)}"

        return user, sector_state, (
            f"{eject_msg}{collected_str}\n"
            f"You have been returned to Sector {home_sector}."
        ), True

    # Warning message
    warning = penalty.get("warning", f"⚠️ Hazard active: {hazard_type}")
    ticks_left = eject_after - ticks
    messages.insert(0, warning)
    messages.append(f"⏳ {ticks_left} tick(s) until forced ejection. "
                    f"Equip a suit or `!teleport` NOW.")

    return user, sector_state, "\n".join(filter(None, messages)), False


def check_suit_expiry_warning(user: dict) -> Optional[str]:
    """
    Returns a warning message if suit is about to expire (< 2 minutes).
    Returns None if suit has plenty of time or no suit active.
    """
    remaining = get_suit_time_remaining(user)
    if remaining is None:
        return None

    active = user.get("active_suit", {})
    suit_name = active.get("display_name", "Suit")

    if remaining <= 0:
        return f"🚨 *{suit_name}* has expired! You are now unprotected."
    elif remaining <= 60:
        return f"🚨 *{suit_name}* expires in {remaining}s! Equip another or teleport."
    elif remaining <= 120:
        return f"⚠️ *{suit_name}* expires in {remaining // 60}m {remaining % 60}s!"

    return None


# ═══════════════════════════════════════════════════════════════════════════
#  ALLIANCE SUIT STOCKING
# ═══════════════════════════════════════════════════════════════════════════

def alliance_stock_suit(
    leader_user: dict,
    suit_key: str,
    quantity: int,
    alliances: dict,
    alliance_id: str,
) -> Tuple[bool, str]:
    """
    Alliance leader stocks suits in alliance shop.
    Leader pays from their own inventory.

    Returns (success, message)
    """
    # Must be leader or officer
    role = leader_user.get("alliance_role", "MEMBER")
    if role not in ("LEADER", "OFFICER"):
        return False, "❌ Only alliance leaders and officers can stock the alliance shop."

    if suit_key not in SUIT_KEYS:
        return False, f"❌ {suit_key} is not a stockable protective item."

    # Check leader has researched the suit
    if not is_unlocked(leader_user, suit_key):
        return False, (
            f"🔒 You haven't researched *{get_display_name(suit_key)}* yet. "
            f"Members also need to have researched it before purchasing."
        )

    # Check leader inventory
    inv = leader_user.get("inventory", {})
    have = inv.get(suit_key, {}).get("qty", 0)
    if have < quantity:
        return False, f"❌ You only have {have} × {get_display_name(suit_key)}. Need {quantity}."

    # Deduct from leader inventory
    inv[suit_key]["qty"] -= quantity
    if inv[suit_key]["qty"] <= 0:
        del inv[suit_key]
    leader_user["inventory"] = inv

    # Add to alliance shop
    alliance = alliances.get(alliance_id, {})
    if "shop_stock" not in alliance:
        alliance["shop_stock"] = {}

    current_stock = alliance["shop_stock"].get(suit_key, {})
    res = RESOURCES.get(suit_key, {})

    alliance["shop_stock"][suit_key] = {
        "qty":          current_stock.get("qty", 0) + quantity,
        "display_name": get_display_name(suit_key),
        "emoji":        get_emoji(suit_key),
        "price_gold":   int(res.get("shop_cost", {}).get("gold", 999) * 0.8),  # 20% discount vs store
        "research_required": res.get("research_required"),
    }
    alliances[alliance_id] = alliance

    suit_emoji = get_emoji(suit_key)
    return True, (
        f"{suit_emoji} Stocked {quantity} × *{get_display_name(suit_key)}* "
        f"in the alliance shop.\n"
        f"Members can buy at 20% discount (research still required)."
    )


def alliance_buy_suit(
    buyer_user: dict,
    suit_key: str,
    alliance: dict,
) -> Tuple[bool, str, dict]:
    """
    Member buys a suit from the alliance shop.
    Requires: same alliance, research completed, gold payment.

    Returns (success, message, updated_buyer_user)
    """
    # Check research
    if not is_unlocked(buyer_user, suit_key):
        res = RESOURCES.get(suit_key, {})
        required = res.get("research_required", "unknown")
        return False, (
            f"🔒 Research *{required}* before purchasing "
            f"*{get_display_name(suit_key)}* from the alliance shop."
        ), buyer_user

    shop = alliance.get("shop_stock", {})
    if suit_key not in shop or shop[suit_key].get("qty", 0) < 1:
        return False, (
            f"❌ *{get_display_name(suit_key)}* is out of stock in the alliance shop.\n"
            f"Ask your alliance leader to restock."
        ), buyer_user

    stock     = shop[suit_key]
    price     = stock.get("price_gold", 999)

    # Check gold
    inv        = buyer_user.get("inventory", {})
    gold_held  = inv.get("gold", {}).get("qty", 0)
    if gold_held < price:
        return False, (
            f"❌ Not enough gold. Need {price} 🪙, have {gold_held} 🪙."
        ), buyer_user

    # Deduct gold
    inv["gold"]["qty"] = gold_held - price
    if inv["gold"]["qty"] <= 0:
        del inv["gold"]

    # Add suit to buyer inventory
    res = RESOURCES.get(suit_key, {})
    if suit_key in inv:
        inv[suit_key]["qty"] += 1
    else:
        inv[suit_key] = {
            "qty":      1,
            "display":  get_display_name(suit_key),
            "emoji":    get_emoji(suit_key),
            "category": "protective_item",
        }

    buyer_user["inventory"] = inv

    # Deduct from shop stock
    shop[suit_key]["qty"] -= 1
    if shop[suit_key]["qty"] <= 0:
        del shop[suit_key]
    alliance["shop_stock"] = shop

    suit_emoji = get_emoji(suit_key)
    suit_name  = get_display_name(suit_key)
    duration   = RESOURCES.get(suit_key, {}).get("duration_minutes", "?")

    return True, (
        f"{suit_emoji} Purchased *{suit_name}* from alliance shop!\n"
        f"Cost: {price} 🪙  |  Duration: {duration} minutes\n"
        f"Equip with `!equip {suit_key}`"
    ), buyer_user


def format_alliance_shop_suits(alliance: dict, buyer_user: dict) -> str:
    """Format the alliance shop's suit inventory for display."""
    shop = alliance.get("shop_stock", {})
    suit_items = {k: v for k, v in shop.items() if k in SUIT_KEYS}

    if not suit_items:
        return "🏪 *Alliance Shop — Suits*\nNo suits currently stocked."

    lines = [
        "🏪 *ALLIANCE SHOP — PROTECTIVE SUITS*",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    for suit_key, stock in suit_items.items():
        researched = is_unlocked(buyer_user, suit_key)
        lock_icon  = "✅" if researched else "🔒"
        res        = RESOURCES.get(suit_key, {})
        duration   = res.get("duration_minutes", "?")
        protects   = ", ".join(res.get("protects_against", []))
        emoji      = stock.get("emoji", "🧪")
        name       = stock.get("display_name", suit_key)
        price      = stock.get("price_gold", "?")
        qty        = stock.get("qty", 0)
        req        = stock.get("research_required", "")

        lines.append(
            f"{lock_icon} {emoji} *{name}*\n"
            f"   🪙 {price} gold  |  ⏱️ {duration} min  |  📦 Stock: {qty}\n"
            f"   Protects: {protects}"
        )
        if not researched and req:
            lines.append(f"   🔒 Research `{req}` first")
        lines.append("")

    lines.append("Buy: `!alliance buy [suit_key]`")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
#  SUIT DISPLAY HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def format_suit_inventory(user: dict) -> str:
    """List all suits a player currently owns in their backpack."""
    inv = user.get("inventory", {})
    suit_items = [(k, inv[k]) for k in SUIT_KEYS if k in inv and inv[k].get("qty", 0) > 0]

    if not suit_items:
        return "🧪 No protective suits in backpack."

    lines = ["🧪 *PROTECTIVE SUITS IN BACKPACK:*"]
    for suit_key, data in suit_items:
        res        = RESOURCES.get(suit_key, {})
        emoji      = data.get("emoji", "🧪")
        name       = data.get("display", get_display_name(suit_key))
        qty        = data.get("qty", 0)
        duration   = res.get("duration_minutes", "?")
        protects   = ", ".join(res.get("protects_against", []))
        researched = is_unlocked(user, suit_key)
        lock       = "" if researched else " 🔒"

        lines.append(
            f"  {emoji} *{name}* ×{qty}{lock}\n"
            f"     ⏱️ {duration} min  |  🛡️ {protects}"
        )

    active = get_active_suit(user)
    if active:
        remaining = get_suit_time_remaining(user)
        lines.append(f"\n*Currently equipped:* {format_suit_status(user)}")

    lines.append("\nEquip: `!equip [suit_key]`")
    return "\n".join(lines)


def get_required_suit_for_node(sector_id: int, node_key: str) -> Optional[str]:
    """Return the required suit key for a node, or None if no suit needed."""
    from sector_nodes import get_node
    node = get_node(sector_id, node_key)
    if not node:
        return None
    return node.get("requires_suit")


def can_enter_node(user: dict, sector_id: int, node_key: str) -> Tuple[bool, str]:
    """
    Check if a player can enter/occupy a specific node.
    Validates suit requirement and research.
    Returns (can_enter, reason_if_not)
    """
    required_suit = get_required_suit_for_node(sector_id, node_key)
    if not required_suit:
        return True, "OK"

    # Check if player has the suit equipped
    if is_protected_against_suit_key(user, required_suit):
        return True, "OK"

    # Not protected — check if they own one
    inv        = user.get("inventory", {})
    own_qty    = inv.get(required_suit, {}).get("qty", 0)
    suit_name  = get_display_name(required_suit)

    if own_qty > 0:
        return False, (
            f"⚠️ *{suit_name}* required for this node.\n"
            f"You have {own_qty} in your backpack — equip it first: `!equip {required_suit}`"
        )
    else:
        return False, (
            f"🔒 *{suit_name}* required for this node. You don't have one.\n"
            f"Buy from `!store` or alliance shop."
        )


def is_protected_against_suit_key(user: dict, suit_key: str) -> bool:
    """Check if the active suit IS the required suit key (or higher tier)."""
    active = get_active_suit(user)
    if not active:
        return False

    active_key = active.get("suit_key")

    # Tier hierarchy — higher tier suits satisfy lower tier requirements
    TIER_ORDER = {
        "basic_suit":     1,
        "bitcoin_format": 2,
        "hazmat_suit":    2,
        "void_suit":      3,
        "cold_wallet":    3,
    }

    active_tier   = TIER_ORDER.get(active_key, 0)
    required_tier = TIER_ORDER.get(suit_key, 0)

    # Same hazard family check (crypto vs physical)
    CRYPTO_SUITS   = {"bitcoin_format", "cold_wallet"}
    PHYSICAL_SUITS = {"basic_suit", "hazmat_suit", "void_suit"}

    active_family   = "crypto" if active_key in CRYPTO_SUITS else "physical"
    required_family = "crypto" if suit_key in CRYPTO_SUITS else "physical"

    if active_family != required_family:
        return False   # Can't use physical suit for crypto hazard and vice versa

    return active_tier >= required_tier


# ═══════════════════════════════════════════════════════════════════════════
#  INTERNAL HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _format_remaining(active: dict) -> str:
    """Format time remaining on active suit."""
    try:
        expires   = datetime.fromisoformat(active["expires_at"])
        remaining = max(0, (expires - datetime.utcnow()).total_seconds())
        return _format_remaining_seconds(int(remaining))
    except Exception:
        return "?"


def _format_remaining_seconds(seconds: int) -> str:
    """Format seconds into M:SS or H:MM:SS."""
    if seconds <= 0:
        return "0s"
    elif seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        m = seconds // 60
        s = seconds % 60
        return f"{m}m {s}s"
    else:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h}h {m}m"
