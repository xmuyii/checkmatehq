# -*- coding: utf-8 -*-
"""
sector_dominance.py — Sector Rulership & Dominance System
==========================================================
Tracks who controls each geographical sector.
Ruler earns passive tax, controls visa policy, can banish.
Pretenders can challenge publicly — forces confrontation.
24-hour cycle resets and redistributes tax income.

INLINE KEYBOARD PATTERN:
  All player interactions use InlineKeyboardMarkup.
  Text commands exist as shortcuts but are never required.
  Follows the same callback_data pattern as main.py.

DOMINANCE SCORE SOURCES:
  +1/min   — occupying any resource node in sector
  +3/min   — holding the PvP outpost node
  +50      — winning a node battle in sector
  +30      — ejecting a player from sector
  +20      — collecting >500 resources from sector in one session
  +15      — sector jamming (Volt skill)
  ×2.0     — surge phase multiplier on all sources
  ×3.0     — holding outpost during surge
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ═══════════════════════════════════════════════════════════════════════════
#  DOMINANCE CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

DOMINANCE_PER_MIN_NODE      = 1
DOMINANCE_PER_MIN_OUTPOST   = 3
DOMINANCE_BATTLE_WIN        = 50
DOMINANCE_EJECT_PLAYER      = 30
DOMINANCE_LARGE_COLLECT     = 20
DOMINANCE_JAM               = 15
DOMINANCE_CYCLE_HOURS       = 24    # Ruler determined every 24h
RULER_TAX_RATE              = 0.10  # 10% of all resources collected in sector
PRETENDER_WINDOW_HOURS      = 48    # Hours pretender has to beat ruler score


# ═══════════════════════════════════════════════════════════════════════════
#  DOMINANCE SCORING
# ═══════════════════════════════════════════════════════════════════════════

def add_dominance(
    user: dict,
    sector_id: int,
    amount: int,
    source: str,
    phase_multiplier: float = 1.0,
) -> dict:
    """Add dominance points for a sector to a player's record."""
    if "dominance_scores" not in user or not isinstance(user.get("dominance_scores"), dict):
        user["dominance_scores"] = {}

    sid_key    = str(sector_id)
    current    = user["dominance_scores"].get(sid_key, 0)
    earned     = int(amount * phase_multiplier)
    user["dominance_scores"][sid_key] = current + earned

    # Track total dominance for power display
    user["dominance_total"] = user.get("dominance_total", 0) + earned
    return user


def get_dominance(user: dict, sector_id: int) -> int:
    """Get a player's dominance score for a specific sector."""
    scores = user.get("dominance_scores", {})
    if isinstance(scores, str):
        return 0
    return scores.get(str(sector_id), 0)


def tick_node_dominance(
    user: dict,
    sector_id: int,
    node_type: str,
    minutes_elapsed: float,
    phase_multiplier: float = 1.0,
) -> dict:
    """
    Award dominance for time spent occupying a node.
    Called during resource tick — happens passively.
    """
    if node_type == "pvp_node":
        base_rate = DOMINANCE_PER_MIN_OUTPOST
    elif node_type == "base_plot":
        base_rate = 0    # Home base doesn't earn dominance
    else:
        base_rate = DOMINANCE_PER_MIN_NODE

    if base_rate == 0:
        return user

    earned = base_rate * minutes_elapsed * phase_multiplier
    return add_dominance(user, sector_id, int(earned), "node_occupation", 1.0)


# ═══════════════════════════════════════════════════════════════════════════
#  SECTOR STATE — RULER MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

def get_sector_ruler(sector_state: dict) -> Optional[dict]:
    """Get current ruler info from sector state."""
    dom = sector_state.get("dominance", {})
    if not dom.get("ruler_id"):
        return None
    return {
        "ruler_id":         dom.get("ruler_id"),
        "ruler_name":       dom.get("ruler_name"),
        "ruled_since":      dom.get("ruled_since"),
        "cycle_score":      dom.get("cycle_score", 0),
        "total_tax_earned": dom.get("total_tax_earned", 0),
    }


def process_dominance_cycle(
    sector_id: int,
    sector_state: dict,
    all_players_in_sector: List[dict],
    save_user_fn,
    log_fn,
    broadcast_fn,
) -> Tuple[dict, str]:
    """
    Run at the end of each 24-hour cycle.
    Determines new ruler, distributes tax, resets cycle scores.
    Returns (updated_sector_state, announcement_message)
    """
    dom = sector_state.get("dominance", {})

    # Find player with highest dominance in this sector this cycle
    cycle_scores = dom.get("cycle_player_scores", {})

    if not cycle_scores:
        return sector_state, ""

    # Winner = highest score this cycle
    winner_id   = max(cycle_scores, key=lambda k: cycle_scores[k].get("score", 0))
    winner_data = cycle_scores[winner_id]
    winner_score = winner_data.get("score", 0)
    winner_name  = winner_data.get("name", "Unknown")

    old_ruler_id   = dom.get("ruler_id")
    old_ruler_name = dom.get("ruler_name", "None")
    is_new_ruler   = winner_id != old_ruler_id

    # Distribute accumulated tax to old ruler before changeover
    tax_pool = dom.get("tax_pool", {})
    if old_ruler_id and tax_pool:
        old_ruler = save_user_fn(old_ruler_id, None)   # getter
        if old_ruler:
            inv = old_ruler.get("inventory", {})
            if not isinstance(inv, dict):
                inv = {}
            for resource, amount in tax_pool.items():
                if resource in inv:
                    inv[resource]["qty"] = inv[resource].get("qty", 0) + amount
                else:
                    inv[resource] = {
                        "qty":     amount,
                        "display": resource.replace("_", " ").title(),
                        "emoji":   "📦",
                        "category": "basic",
                    }
            old_ruler["inventory"] = inv
            old_ruler["pending_notification"] = (
                f"👑 *Cycle ended — Sector {sector_id} tax collected!*\n"
                + "\n".join(
                    f"  {v.get('emoji','📦')} {k}: +{amt}"
                    for k, amt in tax_pool.items()
                )
            )
            save_user_fn(old_ruler_id, old_ruler)

    # Lift old ruler's banishments if ruler changed
    if is_new_ruler and old_ruler_id:
        banished = dom.get("banished_players", [])
        from teleport_system import lift_banishments_on_ruler_change
        lifted = lift_banishments_on_ruler_change(
            old_ruler_id, sector_id, banished, save_user_fn
        )
        if lifted:
            log_fn(sector_id, f"✅ {lifted} banishment(s) lifted — ruler changed")

    # Set new ruler
    dom["ruler_id"]        = winner_id
    dom["ruler_name"]      = winner_name
    dom["ruled_since"]     = datetime.utcnow().isoformat()
    dom["cycle_score"]     = winner_score
    dom["total_tax_earned"] = dom.get("total_tax_earned", 0)
    dom["tax_pool"]        = {}   # Reset tax pool
    dom["cycle_player_scores"] = {}   # Reset cycle scores
    dom["pretenders"]      = []   # Clear pretenders on new cycle
    dom["banished_players"] = dom.get("banished_players", [])
    sector_state["dominance"] = dom

    from teleport_system import SECTOR_QUICK_INFO
    sector_info  = SECTOR_QUICK_INFO.get(sector_id, {})
    sector_name  = sector_info.get("name", f"Sector {sector_id}")
    sector_emoji = sector_info.get("emoji", "🌍")

    if is_new_ruler:
        msg = (
            f"👑 *NEW RULER — {sector_emoji} {sector_name}*\n"
            f"@{winner_name} has claimed the throne!\n"
            f"Dominance Score: {winner_score}\n"
            f"Dethroned: @{old_ruler_name}\n\n"
            f"@{winner_name} now controls:\n"
            f"  • 10% tax on all sector resources\n"
            f"  • Ruler's Reserve node\n"
            f"  • Visa policy control\n"
            f"  • Banishment authority"
        )
        broadcast_fn(msg)
    else:
        msg = (
            f"👑 @{winner_name} retains control of {sector_emoji} {sector_name}\n"
            f"Cycle Score: {winner_score}"
        )

    log_fn(sector_id, f"👑 Cycle ended. Ruler: @{winner_name} ({winner_score} pts)")
    return sector_state, msg


def collect_resource_tax(
    sector_id: int,
    sector_state: dict,
    resource_key: str,
    amount: int,
    collector_id: str,
) -> Tuple[dict, int]:
    """
    When a player collects resources, ruler takes RULER_TAX_RATE cut.
    Only applies if there IS a ruler and collector is NOT the ruler.
    Returns (updated_sector_state, tax_amount_taken)
    """
    dom = sector_state.get("dominance", {})
    ruler_id = dom.get("ruler_id")

    if not ruler_id or ruler_id == collector_id:
        return sector_state, 0

    tax = int(amount * RULER_TAX_RATE)
    if tax <= 0:
        return sector_state, 0

    # Add to tax pool for end-of-cycle distribution
    tax_pool = dom.get("tax_pool", {})
    if not isinstance(tax_pool, dict):
        tax_pool = {}
    tax_pool[resource_key] = tax_pool.get(resource_key, 0) + tax
    dom["tax_pool"]        = tax_pool
    sector_state["dominance"] = dom

    return sector_state, tax


def update_cycle_score(
    sector_state: dict,
    player_id: str,
    player_name: str,
    points: int,
) -> dict:
    """Record dominance points in the cycle leaderboard."""
    dom = sector_state.get("dominance", {})
    cycle_scores = dom.get("cycle_player_scores", {})
    if not isinstance(cycle_scores, dict):
        cycle_scores = {}

    if player_id not in cycle_scores:
        cycle_scores[player_id] = {"name": player_name, "score": 0}
    cycle_scores[player_id]["score"] = cycle_scores[player_id].get("score", 0) + points
    cycle_scores[player_id]["name"]  = player_name

    dom["cycle_player_scores"] = cycle_scores
    sector_state["dominance"]  = dom
    return sector_state


# ═══════════════════════════════════════════════════════════════════════════
#  PRETENDER MECHANIC
# ═══════════════════════════════════════════════════════════════════════════

def declare_pretender(
    user: dict,
    sector_id: int,
    sector_state: dict,
    log_fn,
    broadcast_fn,
) -> Tuple[bool, str, dict]:
    """
    Player publicly challenges the current ruler.
    Commitment: must beat ruler's score within 48h or looks foolish.
    Returns (success, message, updated_sector_state)
    """
    player_id   = user.get("user_id")
    player_name = user.get("username", "Unknown")
    dom         = sector_state.get("dominance", {})
    ruler_id    = dom.get("ruler_id")
    ruler_name  = dom.get("ruler_name", "None")

    if ruler_id == player_id:
        return False, "❌ You are already the ruler.", sector_state

    pretenders = dom.get("pretenders", [])
    if not isinstance(pretenders, list):
        pretenders = []

    # Check already a pretender
    if any(p.get("player_id") == player_id for p in pretenders):
        return False, (
            "⚠️ You have already declared yourself a pretender.\n"
            "Focus on building your dominance score."
        ), sector_state

    expires_at = (datetime.utcnow() + timedelta(hours=PRETENDER_WINDOW_HOURS)).isoformat()
    pretender_entry = {
        "player_id":    player_id,
        "player_name":  player_name,
        "declared_at":  datetime.utcnow().isoformat(),
        "expires_at":   expires_at,
        "score_at_declaration": get_dominance(user, sector_id),
    }
    pretenders.append(pretender_entry)
    dom["pretenders"]      = pretenders
    sector_state["dominance"] = dom

    from teleport_system import SECTOR_QUICK_INFO
    sector_info  = SECTOR_QUICK_INFO.get(sector_id, {})
    sector_name  = sector_info.get("name", f"Sector {sector_id}")
    sector_emoji = sector_info.get("emoji", "🌍")

    announce = (
        f"⚔️ *THRONE CHALLENGED!*\n"
        f"@{player_name} has declared their intent to rule "
        f"{sector_emoji} {sector_name}!\n"
        f"They have {PRETENDER_WINDOW_HOURS}h to build enough dominance "
        f"to dethrone @{ruler_name}.\n"
        f"@{ruler_name}: Defend your throne."
    )
    broadcast_fn(announce)
    log_fn(sector_id, f"⚔️ @{player_name} declared as Pretender to {sector_name}")

    return True, (
        f"⚔️ *Pretender status declared!*\n"
        f"You have {PRETENDER_WINDOW_HOURS}h to beat @{ruler_name}'s dominance score.\n"
        f"The whole server now knows your intention.\n"
        f"Don't back down."
    ), sector_state


def check_pretender_expiry(
    sector_state: dict,
    log_fn,
) -> dict:
    """Remove expired pretender declarations."""
    dom        = sector_state.get("dominance", {})
    pretenders = dom.get("pretenders", [])
    if not isinstance(pretenders, list):
        pretenders = []

    now     = datetime.utcnow()
    active  = []
    expired = []

    for p in pretenders:
        try:
            exp = datetime.fromisoformat(p["expires_at"])
            if now < exp:
                active.append(p)
            else:
                expired.append(p)
        except Exception:
            continue

    if expired:
        for p in expired:
            log_fn(
                sector_state.get("sector_id", 0),
                f"⌛ @{p['player_name']}'s pretender claim expired without success."
            )

    dom["pretenders"]      = active
    sector_state["dominance"] = dom
    return sector_state


# ═══════════════════════════════════════════════════════════════════════════
#  INLINE KEYBOARD BUILDERS
#  All follow the callback_data pattern: "action:param1:param2"
# ═══════════════════════════════════════════════════════════════════════════

def kb_sector_dashboard(sector_id: int, user: dict, sector_state: dict) -> InlineKeyboardMarkup:
    """
    Main sector action keyboard — shown when player is in a sector.
    Context-aware: shows different buttons based on player state.
    """
    buttons = []
    current_node = user.get("current_node")
    ruler_info   = get_sector_ruler(sector_state)
    player_id    = user.get("user_id")
    is_ruler     = ruler_info and ruler_info.get("ruler_id") == player_id

    # Row 1 — Navigation
    buttons.append([
        InlineKeyboardButton("🗺️ Sector Map",     callback_data=f"sector:map:{sector_id}"),
        InlineKeyboardButton("📡 Sector Chat",    callback_data=f"sector:chat:{sector_id}"),
    ])

    # Row 2 — Node actions
    if current_node and current_node.get("sector_id") == sector_id:
        buttons.append([
            InlineKeyboardButton("📦 Collect",   callback_data=f"node:collect:{sector_id}"),
            InlineKeyboardButton("🏠 Leave Node",callback_data=f"node:leave:{sector_id}"),
        ])
    else:
        buttons.append([
            InlineKeyboardButton("⛏️ Occupy Node", callback_data=f"sector:occupy_menu:{sector_id}"),
            InlineKeyboardButton("⚔️ Attack Node",  callback_data=f"sector:attack_menu:{sector_id}"),
        ])

    # Row 3 — Travel
    buttons.append([
        InlineKeyboardButton("🌀 Teleport",       callback_data="teleport:menu"),
        InlineKeyboardButton("🏠 View Base",      callback_data="base:view"),
    ])

    # Row 4 — Intelligence
    buttons.append([
        InlineKeyboardButton("🔭 Scout",          callback_data=f"sector:scout_menu:{sector_id}"),
        InlineKeyboardButton("🔄 Phase Info",     callback_data=f"sector:phase:{sector_id}"),
    ])

    # Row 5 — Ruler actions (only if ruler)
    if is_ruler:
        buttons.append([
            InlineKeyboardButton("👑 Ruler Panel",   callback_data=f"ruler:panel:{sector_id}"),
            InlineKeyboardButton("📜 Banish",        callback_data=f"ruler:banish_menu:{sector_id}"),
        ])

    # Row 6 — Pretender button (if not ruler and dominance researched)
    from research_tree import is_feature_unlocked
    if not is_ruler and is_feature_unlocked(user, "dominance_score_tracking"):
        buttons.append([
            InlineKeyboardButton("⚔️ Challenge Ruler", callback_data=f"dominance:pretender:{sector_id}"),
        ])

    buttons.append([
        InlineKeyboardButton("« Back to Base", callback_data="base:dashboard"),
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_occupy_node_menu(sector_id: int, sector_state: dict, user: dict) -> InlineKeyboardMarkup:
    """Show available nodes to occupy in this sector."""
    from sector_nodes import SECTOR_NODES, NODE_TYPES
    from suit_system import can_enter_node

    nodes     = SECTOR_NODES.get(sector_id, {})
    occupancy = sector_state.get("occupancy", {})
    buttons   = []

    for node_key in sorted(nodes.keys()):
        node      = nodes[node_key]
        node_type = node.get("type", "")
        if node_type == "base_plot":
            continue   # Can't occupy someone else's base plot

        occ_key   = f"{sector_id}:{node_key}"
        occupant  = occupancy.get(occ_key)
        node_name = node.get("name", node_key)
        type_def  = NODE_TYPES.get(node_type, {})
        emoji     = type_def.get("emoji", "📍")

        if occupant:
            if occupant.get("player_id") == user.get("user_id"):
                label = f"{emoji} {node_name} [YOURS]"
                cb    = f"node:collect:{sector_id}:{node_key}"
            else:
                label = f"⚔️ {node_name} [@{occupant['player_name']}]"
                cb    = f"node:attack:{sector_id}:{node_key}"
        else:
            can, reason = can_enter_node(user, sector_id, node_key)
            if can:
                label = f"{emoji} {node_name} — Occupy"
                cb    = f"node:occupy:{sector_id}:{node_key}"
            else:
                label = f"🔒 {node_name} [Suit Required]"
                cb    = f"node:suit_info:{sector_id}:{node_key}"

        buttons.append([InlineKeyboardButton(label, callback_data=cb)])

    buttons.append([InlineKeyboardButton("« Back", callback_data=f"sector:dashboard:{sector_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_ruler_panel(sector_id: int, sector_state: dict) -> InlineKeyboardMarkup:
    """Ruler control panel keyboard."""
    dom = sector_state.get("dominance", {})
    visa_enabled = dom.get("visa_policy", {}).get("enabled", False)
    visa_label   = "🛂 Disable Visa Gate" if visa_enabled else "🛂 Enable Visa Gate"

    buttons = [
        [
            InlineKeyboardButton("📊 Cycle Scores",  callback_data=f"ruler:scores:{sector_id}"),
            InlineKeyboardButton("👁️ Full Vision",   callback_data=f"ruler:vision:{sector_id}"),
        ],
        [
            InlineKeyboardButton(visa_label,          callback_data=f"ruler:visa_toggle:{sector_id}"),
            InlineKeyboardButton("📋 Visa Queue",     callback_data=f"ruler:visa_queue:{sector_id}"),
        ],
        [
            InlineKeyboardButton("🚫 Reserve Node",  callback_data=f"ruler:reserve:{sector_id}"),
            InlineKeyboardButton("💰 Tax Pool",      callback_data=f"ruler:tax:{sector_id}"),
        ],
        [
            InlineKeyboardButton("📜 Banish Player", callback_data=f"ruler:banish_menu:{sector_id}"),
        ],
        [InlineKeyboardButton("« Sector", callback_data=f"sector:dashboard:{sector_id}")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_pretender_confirm(sector_id: int) -> InlineKeyboardMarkup:
    """Confirm pretender declaration — make sure player knows it's public."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton("⚔️ Yes — Declare Publicly", callback_data=f"dominance:pretender_confirm:{sector_id}"),
        ],
        [
            InlineKeyboardButton("✗ Cancel", callback_data=f"sector:dashboard:{sector_id}"),
        ],
    ])


def kb_teleport_sector_list(user: dict, alliance: dict = None) -> InlineKeyboardMarkup:
    """Teleport destination keyboard — main sectors + safe zones highlighted."""
    from teleport_system import get_alliance_safe_sectors, SECTOR_QUICK_INFO
    from research_tree import is_feature_unlocked

    safe_sectors  = get_alliance_safe_sectors(alliance) if alliance else []
    public_sectors = [1, 2, 3, 4, 5, 6, 7, 8, 9, 65, 60, 61, 62, 63, 64]
    buttons       = []

    # Claim button if available
    from teleport_system import get_daily_claim_status
    status = get_daily_claim_status(user)
    if status["can_claim"]:
        buttons.append([
            InlineKeyboardButton(
                f"📬 Claim {status['free_amount']} Free Teleports",
                callback_data="teleport:claim"
            )
        ])

    # Sectors in rows of 2
    row = []
    for sid in public_sectors:
        info    = SECTOR_QUICK_INFO.get(sid, {})
        name    = info.get("name", f"S{sid}")
        emoji   = info.get("emoji", "🌍")
        restrict = info.get("restricted")
        locked  = restrict and not is_feature_unlocked(user, f"sector_{sid}_access")
        safe    = sid in safe_sectors

        if locked:
            label = f"🔒 S{sid}"
        elif safe:
            label = f"🟢 {emoji} S{sid}"
        else:
            label = f"{emoji} S{sid}"

        cb = f"teleport:go:{sid}" if not locked else f"teleport:locked:{sid}"
        row.append(InlineKeyboardButton(label, callback_data=cb))

        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([
        InlineKeyboardButton("🔢 Buy Charges", callback_data="teleport:buy_menu"),
        InlineKeyboardButton("« Back",         callback_data="base:dashboard"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_phase_info(sector_id: int) -> InlineKeyboardMarkup:
    """Phase info with full cycle view option."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton("🔄 Full Cycle", callback_data=f"sector:cycle_view:{sector_id}"),
            InlineKeyboardButton("⏰ Set Warning", callback_data=f"sector:set_warning:{sector_id}"),
        ],
        [InlineKeyboardButton("« Back", callback_data=f"sector:dashboard:{sector_id}")],
    ])


# ═══════════════════════════════════════════════════════════════════════════
#  DISPLAY FORMATTERS
# ═══════════════════════════════════════════════════════════════════════════

def format_sector_dominance_board(sector_id: int, sector_state: dict) -> str:
    """Show current cycle leaderboard for a sector."""
    dom          = sector_state.get("dominance", {})
    ruler_id     = dom.get("ruler_id")
    ruler_name   = dom.get("ruler_name", "None")
    cycle_scores = dom.get("cycle_player_scores", {})
    pretenders   = dom.get("pretenders", [])
    tax_pool     = dom.get("tax_pool", {})

    from teleport_system import SECTOR_QUICK_INFO
    info        = SECTOR_QUICK_INFO.get(sector_id, {})
    sector_name = info.get("name", f"Sector {sector_id}")
    sector_emoji = info.get("emoji", "🌍")

    lines = [
        f"{sector_emoji} *{sector_name.upper()} — DOMINANCE*",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"👑 Current Ruler: @{ruler_name}",
    ]

    if tax_pool:
        from resource_registry import RESOURCES
        tax_parts = [
            f"{RESOURCES.get(k,{}).get('emoji','📦')}{v}"
            for k, v in tax_pool.items()
        ]
        lines.append(f"💰 Tax Pool: {' '.join(tax_parts)}")

    if cycle_scores:
        sorted_scores = sorted(
            cycle_scores.items(),
            key=lambda x: x[1].get("score", 0),
            reverse=True
        )
        lines.append(f"\n📊 *CYCLE LEADERBOARD:*")
        medals = ["🥇", "🥈", "🥉"]
        for i, (pid, data) in enumerate(sorted_scores[:10]):
            medal  = medals[i] if i < 3 else f"{i+1}."
            marker = " 👑" if pid == ruler_id else ""
            lines.append(f"  {medal} @{data.get('name','?')}: {data.get('score',0)}{marker}")

    if pretenders:
        lines.append(f"\n⚔️ *PRETENDERS ({len(pretenders)}):*")
        for p in pretenders:
            try:
                exp = datetime.fromisoformat(p["expires_at"])
                hours_left = max(0, int((exp - datetime.utcnow()).total_seconds() // 3600))
                lines.append(f"  ⚔️ @{p['player_name']} — {hours_left}h remaining")
            except Exception:
                continue

    lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def format_ruler_vision(sector_id: int, sector_state: dict) -> str:
    """
    Full sector vision for the ruler — shows all node owners including hidden base plots.
    The one power that makes ruling genuinely worth the target on your back.
    """
    from sector_nodes import SECTOR_NODES, NODE_TYPES

    nodes     = SECTOR_NODES.get(sector_id, {})
    occupancy = sector_state.get("occupancy", {})
    roaming   = sector_state.get("roaming", {})

    lines = ["👁️ *RULER VISION — FULL SECTOR*", "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]

    for node_key in sorted(nodes.keys()):
        node      = nodes[node_key]
        node_name = node.get("name", node_key)
        node_type = node.get("type", "")
        type_def  = NODE_TYPES.get(node_type, {})
        emoji     = type_def.get("emoji", "📍")
        occ_key   = f"{sector_id}:{node_key}"
        occupant  = occupancy.get(occ_key)

        if node_type == "base_plot":
            if occupant:
                pending = occupant.get("pending_resources", 0)
                lines.append(
                    f"  🏰 [{node_key}] {node_name}\n"
                    f"       👤 @{occupant['player_name']} [HOME BASE]"
                )
            else:
                lines.append(f"  🏰 [{node_key}] {node_name} — vacant")
        elif occupant:
            pending = int(occupant.get("pending_resources", 0))
            resource = type_def.get("resource", "")
            lines.append(
                f"  {emoji} [{node_key}] {node_name}\n"
                f"       @{occupant['player_name']} — {pending} {resource} pending"
            )
        else:
            lines.append(f"  {emoji} [{node_key}] {node_name} — vacant")

    if roaming:
        lines.append(f"\n👤 *ROAMING ({len(roaming)}):*")
        for pid, data in roaming.items():
            lines.append(f"  @{data.get('player_name','?')} [no node]")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)
