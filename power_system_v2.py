# -*- coding: utf-8 -*-
"""
power_system_v2.py — Complete Power Calculation System
=======================================================
Pulls from every game system to produce the definitive power number.
The display satisfies analytical players who want to understand
exactly where their power comes from and how to optimise it.

POWER SOURCES (in order of display):
  1.  Commander Level & XP
  2.  Buildings & their levels
  3.  Military units (by type, including stationed troops)
  4.  Traps deployed
  5.  Research completed
  6.  Commander Skill Tree (per path, per tier)
  7.  Sector Buffs (current phase multiplier + node type)
  8.  Alliance Buffs (tier bonus + active task buffs)
  9.  Personal Buffs/Debuffs (active items, suits)
  10. Shield Status
  11. Prestige Tier multiplier
  12. Resources on hand (every 1,000 = 1 power)
  13. Dominance Score (contribution from sector control)
  14. Equipped Commander Items

Each source is itemised. Nothing is hidden.
The goal: a player at level 100 with 100 skill points distributed
optimally should have a dramatically different power number to
a player at level 100 who spent their points randomly.
"""

from datetime import datetime
from typing import Dict, Optional, Tuple

# ═══════════════════════════════════════════════════════════════════════════
#  POWER CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

# Per-level power
POWER_PER_LEVEL = 100

# Building power per level
POWER_PER_BUILDING_LEVEL = 50

# Troop power values
TROOP_POWER = {
    "pawns":       1,
    "footmen":     2,
    "archers":     6,
    "lancers":     16,
    "castellans":  30,
    "knights":     20,
}

# Trap power
POWER_PER_TRAP = 10

# Research power (per completed research, stored on user as research_power)
# Already accumulated by research_tree.py — just read the field

# Skill tree power — read from commander_skills.get_skill_power_total()

# Alliance tier bonuses
ALLIANCE_TIER_POWER = {
    0: 0,
    1: 200,
    2: 500,
    3: 900,
    4: 1400,
    5: 2000,
}

# Prestige multipliers
PRESTIGE_MULTIPLIERS = {
    0: 1.00,
    1: 1.10,
    2: 1.25,
    3: 1.50,
    4: 2.00,
    5: 3.00,
}

# Sector phase multipliers applied to total power (not individual sources)
PHASE_POWER_BONUS = {
    "surge":       0.15,   # +15% total power during surge phases
    "calm":        0.00,
    "hazard":      0.00,
    "predator":    0.05,
    "lockdown":    0.00,
}

# Shield status power
SHIELD_ACTIVE_POWER    = 300
SHIELD_INACTIVE_DEBUFF = -200   # Penalty for being unshielded

# Suit power
SUIT_POWER = {
    "basic_suit":     100,
    "hazmat_suit":    250,
    "void_suit":      500,
    "bitcoin_format": 200,
    "cold_wallet":    400,
}

# Dominance contribution
POWER_PER_DOMINANCE_POINT = 0.5   # 1000 dominance = 500 power


# ═══════════════════════════════════════════════════════════════════════════
#  POWER BREAKDOWN CALCULATION
# ═══════════════════════════════════════════════════════════════════════════

def calculate_full_power(
    user: dict,
    sector_id: Optional[int] = None,
    sector_state: Optional[dict] = None,
    alliance: Optional[dict] = None,
) -> dict:
    """
    Calculate complete power breakdown for a player.

    Args:
        user:         Full player dict
        sector_id:    Current sector (for phase buffs)
        sector_state: Current sector state (for node type)
        alliance:     Player's alliance dict (for alliance buffs)

    Returns dict with all components and total.
    """
    breakdown = {}

    # ── 1. Commander Level ────────────────────────────────────────────────
    level          = user.get("level", 1)
    xp             = user.get("xp", 0)
    level_power    = level * POWER_PER_LEVEL
    breakdown["commander_level"] = {
        "label":  f"Commander Level {level}",
        "value":  level_power,
        "detail": f"Level {level} × {POWER_PER_LEVEL} = {level_power:,}",
        "emoji":  "🎖️",
    }

    # ── 2. Buildings ──────────────────────────────────────────────────────
    buildings = user.get("buildings", {})
    if not isinstance(buildings, dict):
        buildings = {}

    building_power  = 0
    building_detail = []
    try:
        from build_system import BUILDING_TYPES
        btype_names = {k: v.get("name", k) for k, v in BUILDING_TYPES.items()}
    except ImportError:
        btype_names = {}

    for bld_id, lvl in buildings.items():
        bld_name = btype_names.get(bld_id, bld_id.replace("_", " ").title())
        bp       = lvl * POWER_PER_BUILDING_LEVEL
        building_power += bp
        building_detail.append(f"  {bld_name} Lv{lvl}: +{bp}")

    hq_level = user.get("base_hq_level", 1)
    hq_power = hq_level * POWER_PER_BUILDING_LEVEL
    building_power += hq_power
    building_detail.insert(0, f"  Base HQ Lv{hq_level}: +{hq_power}")

    breakdown["buildings"] = {
        "label":  "Buildings",
        "value":  building_power,
        "detail": "\n".join(building_detail) if building_detail else "  No buildings",
        "emoji":  "🏗️",
    }

    # ── 3. Military ───────────────────────────────────────────────────────
    military = user.get("military", {})
    if not isinstance(military, dict):
        military = {}

    military_power  = 0
    military_detail = []

    # Home garrison
    for unit, count in military.items():
        if count <= 0:
            continue
        pwr = TROOP_POWER.get(unit, 1) * count
        military_power += pwr
        military_detail.append(f"  {unit.capitalize()} ×{count}: +{pwr}")

    # Troops stationed at a node (counted separately for clarity)
    current_node = user.get("current_node")
    if current_node and sector_state:
        node_key = current_node.get("node_key", "")
        sid      = current_node.get("sector_id", sector_id)
        occ_key  = f"{sid}:{node_key}"
        occupant = sector_state.get("occupancy", {}).get(occ_key, {})
        stationed = occupant.get("troops", {})
        if stationed:
            stationed_power = 0
            for unit, count in stationed.items():
                if count > 0:
                    pwr = TROOP_POWER.get(unit, 1) * count
                    stationed_power += pwr
            military_detail.append(f"  [Stationed at Node {node_key}]: +{stationed_power}")
            military_power += stationed_power

    breakdown["military"] = {
        "label":  "Military",
        "value":  military_power,
        "detail": "\n".join(military_detail) if military_detail else "  No troops",
        "emoji":  "⚔️",
    }

    # ── 4. Traps ──────────────────────────────────────────────────────────
    traps = user.get("traps", {})
    if not isinstance(traps, dict):
        traps = {}

    trap_power  = 0
    trap_detail = []
    for trap_id, count in traps.items():
        if count <= 0:
            continue
        tp = count * POWER_PER_TRAP
        trap_power += tp
        trap_detail.append(f"  {trap_id.replace('_',' ').title()} ×{count}: +{tp}")

    breakdown["traps"] = {
        "label":  "Traps",
        "value":  trap_power,
        "detail": "\n".join(trap_detail) if trap_detail else "  No traps built",
        "emoji":  "🔱",
    }

    # ── 5. Research ───────────────────────────────────────────────────────
    research_power = user.get("research_power", 0)
    researches     = user.get("researches", {})
    if not isinstance(researches, dict):
        researches = {}
    r_count = len([k for k, v in researches.items() if v])

    breakdown["research"] = {
        "label":  f"Research ({r_count} completed)",
        "value":  research_power,
        "detail": f"  {r_count} technologies researched: +{research_power}",
        "emoji":  "🔬",
    }

    # ── 6. Commander Skills ───────────────────────────────────────────────
    try:
        from commander_skills import (
            get_skill_power_total, get_spent_points,
            get_highest_unlocked_tier, SKILL_PATHS
        )
        skill_power  = get_skill_power_total(user)
        spent        = get_spent_points(user)
        skill_detail = []

        for path_key, path_data in SKILL_PATHS.items():
            path_spent   = spent.get(path_key, 0)
            highest      = get_highest_unlocked_tier(user, path_key)
            emoji        = path_data["color_emoji"]
            name         = path_data["name"]
            if highest > 0:
                # Sum power values for unlocked tiers
                path_power = sum(
                    t["power_value"] for t in path_data["tiers"]
                    if t["tier"] <= highest
                )
                skill_detail.append(
                    f"  {emoji} {name} — Tier {highest}: +{path_power}"
                )

    except ImportError:
        skill_power  = 0
        skill_detail = ["  Skill tree not available"]

    breakdown["skills"] = {
        "label":  "Commander Skills",
        "value":  skill_power,
        "detail": "\n".join(skill_detail) if skill_detail else "  No skills unlocked",
        "emoji":  "🌟",
    }

    # ── 7. Sector Buffs ───────────────────────────────────────────────────
    sector_power = 0
    sector_detail = []

    if sector_id:
        try:
            from sector_cycles import get_current_phase
            phase = get_current_phase(sector_id)
            phase_type = phase.get("type", "calm")
            phase_bonus_pct = PHASE_POWER_BONUS.get(phase_type, 0)
            phase_name = phase.get("name", "Unknown")
            res_mult   = phase.get("resource_multiplier", 1.0)

            if phase_bonus_pct != 0:
                # Apply to subtotal so far
                subtotal_so_far = sum(b["value"] for b in breakdown.values())
                sector_power    = int(subtotal_so_far * phase_bonus_pct)
                sector_detail.append(
                    f"  Phase: {phase_name} ({phase_type}) +{int(phase_bonus_pct*100)}%"
                    f" of base: +{sector_power}"
                )
            else:
                sector_detail.append(f"  Phase: {phase_name} — No power bonus")

            if res_mult != 1.0:
                sector_detail.append(
                    f"  Resource Multiplier: ×{res_mult:.1f} (yield only)"
                )

        except ImportError:
            sector_detail.append("  Phase data unavailable")

    # Node type bonus
    if current_node and sector_state:
        node_key  = current_node.get("node_key", "")
        sid       = current_node.get("sector_id", sector_id)
        occ_key   = f"{sid}:{node_key}"
        occupant  = sector_state.get("occupancy", {}).get(occ_key, {})
        node_name = current_node.get("node_name", "")

        if node_key:
            try:
                from sector_nodes import get_node, NODE_TYPES
                node_def  = get_node(sid, node_key)
                node_type = node_def.get("type", "") if node_def else ""
                if node_type == "pvp_node":
                    pvp_bonus = 500
                    sector_power  += pvp_bonus
                    sector_detail.append(f"  Outpost Control ({node_name}): +{pvp_bonus}")
            except ImportError:
                pass

    breakdown["sector_buffs"] = {
        "label":  "Sector Buffs",
        "value":  sector_power,
        "detail": "\n".join(sector_detail) if sector_detail else "  Not in a sector",
        "emoji":  "🌍",
    }

    # ── 8. Alliance Buffs ─────────────────────────────────────────────────
    alliance_power  = 0
    alliance_detail = []

    if alliance and isinstance(alliance, dict):
        # Alliance tier
        tier     = alliance.get("tier", 0)
        tier_pwr = ALLIANCE_TIER_POWER.get(tier, 0)
        if tier_pwr:
            alliance_power += tier_pwr
            alliance_detail.append(f"  Alliance Tier {tier}: +{tier_pwr}")

        # Active task buffs
        active_buffs = alliance.get("active_buffs", {})
        if isinstance(active_buffs, dict):
            for buff_name, buff_val in active_buffs.items():
                if isinstance(buff_val, (int, float)) and buff_val > 0:
                    alliance_power += int(buff_val)
                    alliance_detail.append(
                        f"  {buff_name.replace('_', ' ').title()}: +{int(buff_val)}"
                    )

        # Alliance points contribution
        alliance_ap  = alliance.get("alliance_points", 0)
        ap_power     = alliance_ap // 100   # 100 AP = 1 power
        if ap_power:
            alliance_power += ap_power
            alliance_detail.append(f"  Alliance Points ({alliance_ap} AP): +{ap_power}")

    breakdown["alliance"] = {
        "label":  "Alliance",
        "value":  alliance_power,
        "detail": "\n".join(alliance_detail) if alliance_detail else "  No alliance",
        "emoji":  "👥",
    }

    # ── 9. Personal Buffs & Suit ──────────────────────────────────────────
    personal_power  = 0
    personal_detail = []

    # Active suit
    active_suit = user.get("active_suit")
    if active_suit and isinstance(active_suit, dict):
        suit_key  = active_suit.get("suit_key", "")
        suit_name = active_suit.get("display_name", "Suit")
        suit_pwr  = SUIT_POWER.get(suit_key, 0)
        if suit_pwr:
            personal_power += suit_pwr
            try:
                exp      = datetime.fromisoformat(active_suit["expires_at"])
                rem_secs = max(0, (exp - datetime.utcnow()).total_seconds())
                rem_str  = f"{int(rem_secs//60)}m {int(rem_secs%60)}s"
            except Exception:
                rem_str = "?"
            personal_detail.append(
                f"  {suit_name} ({rem_str} remaining): +{suit_pwr}"
            )

    # Personal buffs dict
    buffs = user.get("buffs", {})
    if isinstance(buffs, dict):
        for buff_name, buff_val in buffs.items():
            if buff_name in ("firewall_active",):
                continue   # Non-power buffs
            if isinstance(buff_val, (int, float)) and buff_val > 0:
                personal_power += int(buff_val)
                personal_detail.append(
                    f"  {buff_name.replace('_', ' ').title()}: +{int(buff_val)}"
                )

    # Energy level contribution
    energy     = user.get("energy", 0)
    energy_pwr = energy // 10   # 10 energy = 1 power, max 50
    if energy_pwr:
        personal_power += energy_pwr
        personal_detail.append(f"  Energy ({energy}): +{energy_pwr}")

    breakdown["personal_buffs"] = {
        "label":  "Personal Buffs",
        "value":  personal_power,
        "detail": "\n".join(personal_detail) if personal_detail else "  No active buffs",
        "emoji":  "✨",
    }

    # ── 10. Shield Status ─────────────────────────────────────────────────
    shield_power  = 0
    shield_detail = []

    base_shielded = user.get("base_shielded", False)
    shield_exp    = user.get("shield_expires_at")
    shield_active = False

    if base_shielded and shield_exp:
        try:
            exp           = datetime.fromisoformat(shield_exp)
            shield_active = datetime.utcnow() < exp
            if shield_active:
                rem      = exp - datetime.utcnow()
                hours    = int(rem.total_seconds() // 3600)
                mins     = int((rem.total_seconds() % 3600) // 60)
                shield_power = SHIELD_ACTIVE_POWER
                shield_detail.append(
                    f"  🛡️ Active ({hours}h {mins}m remaining): +{SHIELD_ACTIVE_POWER}"
                )
            else:
                shield_power = SHIELD_INACTIVE_DEBUFF
                shield_detail.append(
                    f"  🔓 Expired — Base UNSHIELDED: {SHIELD_INACTIVE_DEBUFF}"
                )
        except Exception:
            pass
    elif not base_shielded:
        shield_power = SHIELD_INACTIVE_DEBUFF
        shield_detail.append(
            f"  🔓 No shield — Base VULNERABLE: {SHIELD_INACTIVE_DEBUFF}"
        )

    breakdown["shield"] = {
        "label":  "Shield Status",
        "value":  shield_power,
        "detail": "\n".join(shield_detail),
        "emoji":  "🛡️",
    }

    # ── 11. Prestige ──────────────────────────────────────────────────────
    prestige          = user.get("prestige", 0)
    prestige_mult     = PRESTIGE_MULTIPLIERS.get(prestige, 1.0)
    prestige_detail   = []

    try:
        from prestige_system import PRESTIGE_BONUSES
        tier_info   = PRESTIGE_BONUSES.get(prestige, {})
        tier_name   = tier_info.get("name", f"Prestige {prestige}")
        prestige_detail.append(f"  {tier_name}: ×{prestige_mult}")
    except ImportError:
        prestige_detail.append(f"  Prestige {prestige}: ×{prestige_mult}")

    breakdown["prestige"] = {
        "label":         "Prestige",
        "value":         0,          # Applied as multiplier at the end
        "multiplier":    prestige_mult,
        "detail":        "\n".join(prestige_detail),
        "emoji":         "👑",
        "is_multiplier": True,
    }

    # ── 12. Resources on Hand ─────────────────────────────────────────────
    base_res     = user.get("base_resources", {})
    resources    = base_res.get("resources", {}) if isinstance(base_res, dict) else {}
    total_res    = sum(v for v in resources.values() if isinstance(v, (int, float)))

    # Also count inventory resources
    inv = user.get("inventory", {})
    if isinstance(inv, dict):
        for item_key, item_data in inv.items():
            if isinstance(item_data, dict):
                qty = item_data.get("qty", 0)
                if isinstance(qty, (int, float)):
                    total_res += qty

    res_power = int(total_res // 1000)

    breakdown["resources"] = {
        "label":  "Resources on Hand",
        "value":  res_power,
        "detail": f"  {int(total_res):,} total resources (÷1,000): +{res_power}",
        "emoji":  "💰",
    }

    # ── 13. Dominance Score ───────────────────────────────────────────────
    dom_scores    = user.get("dominance_scores", {})
    if not isinstance(dom_scores, dict):
        dom_scores = {}

    total_dom    = sum(v for v in dom_scores.values() if isinstance(v, (int, float)))
    dom_power    = int(total_dom * POWER_PER_DOMINANCE_POINT)
    dom_detail   = []

    for sid_key, score in sorted(dom_scores.items(), key=lambda x: x[1], reverse=True)[:5]:
        try:
            from teleport_system import SECTOR_QUICK_INFO
            info = SECTOR_QUICK_INFO.get(int(sid_key), {})
            name = info.get("name", f"Sector {sid_key}")
        except Exception:
            name = f"Sector {sid_key}"
        dom_detail.append(f"  {name}: {int(score)} pts")

    breakdown["dominance"] = {
        "label":  "Sector Dominance",
        "value":  dom_power,
        "detail": "\n".join(dom_detail) if dom_detail else "  No dominance earned yet",
        "emoji":  "🏆",
    }

    # ── FINAL CALCULATION ─────────────────────────────────────────────────
    # Sum all non-multiplier sources
    base_total = sum(
        b["value"] for b in breakdown.values()
        if not b.get("is_multiplier", False)
    )

    # Apply prestige multiplier
    prestige_mult  = breakdown["prestige"]["multiplier"]
    final_power    = max(1, int(base_total * prestige_mult))

    breakdown["_totals"] = {
        "base_total":    base_total,
        "prestige_mult": prestige_mult,
        "final_power":   final_power,
    }

    return breakdown


def get_total_power(
    user: dict,
    sector_id: Optional[int] = None,
    sector_state: Optional[dict] = None,
    alliance: Optional[dict] = None,
) -> int:
    """Quick power calculation — returns integer only."""
    bd = calculate_full_power(user, sector_id, sector_state, alliance)
    return bd["_totals"]["final_power"]


# ═══════════════════════════════════════════════════════════════════════════
#  DISPLAY FORMATTERS
# ═══════════════════════════════════════════════════════════════════════════

def format_power_display(
    user: dict,
    sector_id: Optional[int] = None,
    sector_state: Optional[dict] = None,
    alliance: Optional[dict] = None,
    compact: bool = False,
) -> str:
    """
    Full power breakdown display.
    compact=True for the dashboard summary line.
    compact=False for the detailed power screen.
    """
    bd     = calculate_full_power(user, sector_id, sector_state, alliance)
    totals = bd["_totals"]

    if compact:
        return (
            f"⚡ *{totals['final_power']:,}* power  "
            f"({get_power_tier(totals['final_power'])})"
        )

    # Full display
    lines = [
        f"⚡ *TOTAL POWER: {totals['final_power']:,}*",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    # Group by category for cleaner display
    categories = [
        ("Commander",  ["commander_level"]),
        ("Base",       ["buildings", "traps", "shield"]),
        ("Military",   ["military"]),
        ("Growth",     ["research", "skills", "prestige"]),
        ("Field",      ["sector_buffs", "personal_buffs"]),
        ("Collective", ["alliance", "dominance"]),
        ("Economy",    ["resources"]),
    ]

    for cat_name, keys in categories:
        cat_power = sum(
            bd[k]["value"] for k in keys if k in bd and not bd[k].get("is_multiplier")
        )
        if cat_power == 0:
            # Still show if it's prestige or shield (even when 0)
            if not any(k in ("prestige", "shield") for k in keys):
                continue

        lines.append(f"\n*{cat_name}* — {cat_power:+,}")

        for key in keys:
            if key not in bd:
                continue
            item   = bd[key]
            emoji  = item.get("emoji", "")
            label  = item.get("label", key)
            value  = item.get("value", 0)
            mult   = item.get("multiplier")

            if item.get("is_multiplier"):
                lines.append(f"  {emoji} {label}: ×{mult}")
            else:
                sign = "+" if value >= 0 else ""
                lines.append(f"  {emoji} {label}: {sign}{value:,}")

            # Show detail lines (indented further)
            detail = item.get("detail", "")
            if detail:
                for dline in detail.split("\n"):
                    if dline.strip():
                        lines.append(f"  {dline}")

    # Prestige multiplier line
    if totals["prestige_mult"] != 1.0:
        lines.append(
            f"\n  × Prestige Multiplier: ×{totals['prestige_mult']}"
            f"  →  {totals['base_total']:,} × {totals['prestige_mult']}"
            f" = {totals['final_power']:,}"
        )

    lines.append(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"⚡ *FINAL: {totals['final_power']:,}*  {get_power_tier(totals['final_power'])}")

    return "\n".join(lines)


def get_power_tier(power: int) -> str:
    """Classify power into a tier label."""
    if power < 1_000:
        return "🟤 Novice"
    elif power < 5_000:
        return "🟢 Recruit"
    elif power < 15_000:
        return "🔵 Soldier"
    elif power < 40_000:
        return "🟣 Commander"
    elif power < 100_000:
        return "🟠 Warlord"
    elif power < 250_000:
        return "🔴 Emperor"
    elif power < 500_000:
        return "⚫ Immortal"
    else:
        return "🌟 Ascendant"


def format_power_comparison(user_a: dict, user_b: dict) -> str:
    """Compare two players' power for battle preview."""
    pa = get_total_power(user_a)
    pb = get_total_power(user_b)

    tier_a = get_power_tier(pa)
    tier_b = get_power_tier(pb)

    diff    = abs(pa - pb)
    pct     = int((diff / max(pa, pb, 1)) * 100)
    favours = "You" if pa > pb else f"@{user_b.get('username','Defender')}"

    return (
        f"⚡ *POWER COMPARISON*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🛰️ You ({user_a.get('username','?')}): {pa:,}  {tier_a}\n"
        f"🛡️ @{user_b.get('username','?')}: {pb:,}  {tier_b}\n"
        f"\nAdvantage: *{favours}* by {diff:,} ({pct}%)\n"
        f"{'✅ Victory likely' if pa > pb else '⚠️ Defeat likely — consider scouting first'}"
    )
