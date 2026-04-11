"""
revenge_system.py — Blood Debt, Scout & Combat Engine
=======================================================
Every attack is a STORY. Every revenge is PERSONAL.
GameMaster narrates with psychological weight.

Mechanics:
  - Revenge window: 24h after being raided → 1.5× attack buff vs raider
  - Scout: 5-min travel, 30% lie chance, mousetraps, firewall defence
  - PvP combat: troop stats + sector buffs + revenge multiplier
  - GameMaster commentary on every battle outcome
"""

import os
import random
import uuid
from datetime import datetime, timedelta
from typing import Tuple, Dict, Optional
from supabase_db import get_user, save_user
from formatting import (
    divider, thin_divider, double_divider,
    battle_opener, battle_result as fmt_battle_result,
    revenge_notification, attack_decision_screen,
    format_scout_report_display, gamemaster_says,
    UNIT_EMOJIS, RESOURCE_EMOJIS,
)

# ══════════════════════════════════════════════════════════════════
#  COMBAT ENGINE — Troop stat-based battle simulation
# ══════════════════════════════════════════════════════════════════

UNIT_STATS = {
    "pawns":        {"attack": 2,  "defense": 1,  "health": 10},
    "footmen":      {"attack": 5,  "defense": 3,  "health": 20},
    "archers":      {"attack": 8,  "defense": 2,  "health": 15},
    "lancers":      {"attack": 15, "defense": 8,  "health": 45},
    "castellans":   {"attack": 12, "defense": 25, "health": 100},
    "warlords":     {"attack": 60, "defense": 40, "health": 300},
    # Legacy names
    "militia":      {"attack": 3,  "defense": 2,  "health": 12},
    "soldier":      {"attack": 10, "defense": 6,  "health": 35},
    "knight":       {"attack": 20, "defense": 14, "health": 80},
    "paladin":      {"attack": 35, "defense": 25, "health": 160},
    "warlord":      {"attack": 60, "defense": 40, "health": 300},
}

def calculate_army_power(military: dict) -> Dict[str, int]:
    """Calculate total attack, defense, and health of an army."""
    total_attack = 0
    total_defense = 0
    total_health = 0
    total_upkeep = 0.0

    for unit_type, count in military.items():
        if count <= 0:
            continue
        stats = UNIT_STATS.get(unit_type.lower(), {"attack": 5, "defense": 3, "health": 20})
        total_attack  += stats["attack"]  * count
        total_defense += stats["defense"] * count
        total_health  += stats["health"]  * count

    return {
        "attack": total_attack,
        "defense": total_defense,
        "health": total_health,
        "total_troops": sum(military.values()),
    }

def calculate_wall_bonus(base_buildings: dict) -> float:
    """Wall levels provide a defense multiplier."""
    wall_level = base_buildings.get("wall", {}).get("level", 0)
    return 1.0 + (wall_level * 0.30)

def simulate_pvp_battle(
    attacker_id: str,
    defender_id: str,
) -> Dict:
    """
    Full PvP battle simulation.
    Returns detailed outcome with loot calculations.
    """
    attacker = get_user(attacker_id)
    defender = get_user(defender_id)

    if not attacker or not defender:
        return {"ok": False, "message": "Player not found"}

    attacker_name = attacker.get("username", "Attacker")
    defender_name = defender.get("username", "Defender")

    # Army power
    att_military = attacker.get("military", {})
    def_military = defender.get("military", {})

    att_power = calculate_army_power(att_military)
    def_power = calculate_army_power(def_military)

    # Revenge multiplier
    revenge_mult = get_revenge_multiplier(attacker_id, defender_id)
    att_effective_attack = int(att_power["attack"] * revenge_mult)

    # Wall defense bonus
    def_buildings = defender.get("base_buildings", {})
    wall_mult = calculate_wall_bonus(def_buildings)
    def_effective_defense = int(def_power["defense"] * wall_mult)

    # Watchtower reduces attacker's surprise advantage
    watchtower_level = def_buildings.get("watchtower", {}).get("level", 0)
    surprise_reduction = watchtower_level * 0.30
    att_effective_attack = int(att_effective_attack * (1 - min(0.6, surprise_reduction)))

    # Battle simulation (round-based)
    att_hp = att_power["health"]
    def_hp = def_power["health"]
    rounds = 0
    max_rounds = 15

    battle_log = []

    while rounds < max_rounds and att_hp > 0 and def_hp > 0:
        # Attacker strikes
        att_dmg = max(1, int(att_effective_attack * random.uniform(0.75, 1.25)))
        def_hp -= att_dmg

        # Defender strikes back
        if def_hp > 0:
            def_dmg = max(1, int(def_effective_defense * random.uniform(0.6, 1.0)))
            att_hp -= def_dmg
        else:
            def_dmg = 0

        rounds += 1
        if rounds <= 3 or rounds == max_rounds:
            battle_log.append(
                f"  Round {rounds}: ⚔️ -{att_dmg} to defender | 🛡️ -{def_dmg} to attacker"
            )

    attacker_won = def_hp <= 0

    # ── Loot calculation ──
    loot = {}
    troop_losses_pct = 0

    if attacker_won:
        # Steal 25-40% of defender's resources
        steal_pct = random.uniform(0.25, 0.40)
        def_resources = defender.get("base_resources", {}).get("resources", {})
        for res, amt in def_resources.items():
            stolen = int(amt * steal_pct)
            if stolen > 0:
                loot[res] = stolen

        # Also steal some silver
        def_silver = defender.get("silver", 0)
        loot["silver"] = int(def_silver * random.uniform(0.10, 0.25))

        # Apply loot to attacker
        att_base = attacker.get("base_resources", {})
        att_res = att_base.get("resources", {})
        for res, amt in loot.items():
            if res == "silver":
                attacker["silver"] = attacker.get("silver", 0) + amt
            else:
                att_res[res] = att_res.get(res, 0) + amt
                def_resources[res] = max(0, def_resources.get(res, 0) - amt)
        att_base["resources"] = att_res
        attacker["base_resources"] = att_base

        # Reduce defender silver
        defender["silver"] = max(0, def_silver - loot.get("silver", 0))
        def_base = defender.get("base_resources", {})
        def_base["resources"] = def_resources
        defender["base_resources"] = def_base

        # Attacker loses some troops (~10-20%)
        att_loss_pct = random.uniform(0.10, 0.20)
        troop_losses_pct = att_loss_pct
        for utype in att_military:
            att_military[utype] = max(0, int(att_military[utype] * (1 - att_loss_pct)))
        attacker["military"] = att_military

        # Defender loses 30-50% of their troops
        def_loss_pct = random.uniform(0.30, 0.50)
        for utype in def_military:
            def_military[utype] = max(0, int(def_military[utype] * (1 - def_loss_pct)))
        defender["military"] = def_military

        # XP reward for attacker
        xp_gain = max(20, int(def_power["total_troops"] * 2) + 50)
        attacker["xp"] = attacker.get("xp", 0) + xp_gain
        attacker["level"] = 1 + (attacker["xp"] // 100)

    else:
        # Defender wins — attacker loses 40-60% of army
        att_loss_pct = random.uniform(0.40, 0.60)
        troop_losses_pct = att_loss_pct
        for utype in att_military:
            att_military[utype] = max(0, int(att_military[utype] * (1 - att_loss_pct)))
        attacker["military"] = att_military

        # XP consolation for defender
        xp_gain = max(10, int(att_power["total_troops"]) + 20)
        defender["xp"] = defender.get("xp", 0) + xp_gain
        defender["level"] = 1 + (defender["xp"] // 100)

    # Set revenge target on defender if attacker won
    if attacker_won:
        set_revenge_target(defender_id, attacker_id, attacker_name)

    # Clear revenge if this was a revenge attack
    if revenge_mult > 1.0:
        clear_revenge(attacker_id)

    # Save both
    save_user(attacker_id, attacker)
    save_user(defender_id, defender)

    return {
        "ok": True,
        "attacker_won": attacker_won,
        "attacker_name": attacker_name,
        "defender_name": defender_name,
        "rounds": rounds,
        "loot": loot,
        "attacker_power": att_power,
        "defender_power": def_power,
        "revenge_multiplier": revenge_mult,
        "wall_bonus": wall_mult,
        "battle_log": battle_log,
        "troop_loss_pct": troop_losses_pct,
        "xp_gained": xp_gain if attacker_won else 0,
    }


def format_full_battle_report(result: Dict, is_attacker: bool = True) -> str:
    """
    Full narrative battle report for both attacker and defender.
    """
    if not result.get("ok"):
        return "❌ Battle data unavailable."

    attacker_name = result["attacker_name"]
    defender_name = result["defender_name"]
    won = result["attacker_won"]
    rounds = result["rounds"]
    loot = result["loot"]
    revenge_mult = result.get("revenge_multiplier", 1.0)

    # Perspective: who is reading this
    if is_attacker:
        victory = won
        perspective_name = attacker_name
        enemy_name = defender_name
    else:
        victory = not won
        perspective_name = defender_name
        enemy_name = attacker_name

    lines = [
        "⚔️ *BATTLE REPORT*",
        double_divider(),
        f"🔴 *{attacker_name}* ↗️ attacks ↙️ 🔵 *{defender_name}*",
        thin_divider(),
    ]

    # Log snippet
    for log_line in result.get("battle_log", [])[:3]:
        lines.append(f"_{log_line.strip()}_")

    lines.append(thin_divider())

    if victory:
        lines += [
            f"🏆 *VICTORY — {perspective_name.upper()}*",
            "",
        ]
        if is_attacker and loot:
            lines.append("💰 *PLUNDER SEIZED:*")
            for res, amt in loot.items():
                emoji = RESOURCE_EMOJIS.get(res, "📦")
                lines.append(f"  {emoji} {amt:,} {res.capitalize()}")
        if revenge_mult > 1.0:
            lines.append(f"\n⚡ *Revenge bonus ×{revenge_mult:.1f} applied — Blood debt satisfied.*")
        xp = result.get("xp_gained", 0)
        if xp:
            lines.append(f"✨ +{xp:,} XP earned")
    else:
        lines += [
            f"💀 *DEFEAT — {perspective_name.upper()}*",
            "",
            f"_{enemy_name} overpowered your defenses._",
        ]
        if not is_attacker:
            lines += [
                "",
                "💢 *REVENGE WINDOW: 24 HOURS*",
                f"⚡ Attack *{enemy_name}* with 1.5× power — use `!attack @{enemy_name}`",
                "🛡️ Activate your shield now — `!shield`",
            ]

    lines += [
        "",
        f"⏱️ _Battle duration: {rounds} rounds_",
        f"📉 _Troop losses: ~{int(result.get('troop_loss_pct', 0)*100)}%_",
        double_divider(),
        gamemaster_says(
            _gm_battle_comment(victory, rounds),
            mood="impressed" if victory else "cryptic"
        ),
    ]

    return "\n".join(lines)


def _gm_battle_comment(won: bool, rounds: int) -> str:
    if won and rounds <= 5:
        return random.choice([
            "Swift. Surgical. A predator's patience rewarded.",
            "They never had a chance. Impressive.",
            "Dominance achieved before they could blink.",
        ])
    elif won:
        return random.choice([
            "A hard-fought victory. The worthy always prevail.",
            "Bruised, but unbroken. That is what power looks like.",
            "They made you work for it. Good. Easy victories breed weakness.",
        ])
    elif rounds <= 5:
        return random.choice([
            "Obliterated. You underestimated them gravely.",
            "Your hubris was your shield — and it shattered instantly.",
            "Routed before the battle began. Embarrassing.",
        ])
    else:
        return random.choice([
            "You fought with heart. But heart alone doesn't win wars.",
            "Close. Dangerously close. Rebuild. Train. Return.",
            "They are stronger than you. For now.",
        ])


# ══════════════════════════════════════════════════════════════════
#  REVENGE SYSTEM — Blood Debt Mechanics
# ══════════════════════════════════════════════════════════════════

def set_revenge_target(defender_id: str, attacker_id: str, attacker_name: str) -> bool:
    """Set the revenge target on the defender after they've been raided."""
    user = get_user(defender_id)
    if not user:
        return False
    buffs = user.get("buffs", {})
    buffs["revenge_target"] = attacker_id
    buffs["revenge_target_name"] = attacker_name
    buffs["revenge_expires"] = (datetime.utcnow() + timedelta(hours=24)).isoformat()
    user["buffs"] = buffs
    save_user(defender_id, user)
    return True


def get_revenge_info(user_id: str) -> Dict:
    """Return active revenge info, or {'active': False}."""
    user = get_user(user_id)
    if not user:
        return {"active": False}

    buffs = user.get("buffs", {})
    target_id = buffs.get("revenge_target")
    expires = buffs.get("revenge_expires")

    if not target_id or not expires:
        return {"active": False}

    try:
        exp_time = datetime.fromisoformat(expires)
        if datetime.utcnow() > exp_time:
            # Expired — clean up
            buffs.pop("revenge_target", None)
            buffs.pop("revenge_target_name", None)
            buffs.pop("revenge_expires", None)
            user["buffs"] = buffs
            save_user(user_id, user)
            return {"active": False}
    except Exception:
        return {"active": False}

    hours_left = (datetime.fromisoformat(expires) - datetime.utcnow()).total_seconds() / 3600
    return {
        "active": True,
        "target_id": target_id,
        "target_name": buffs.get("revenge_target_name", "Unknown"),
        "expires": expires,
        "hours_left": round(hours_left, 1),
    }


def clear_revenge(user_id: str):
    """Clear revenge debt after successful revenge attack."""
    user = get_user(user_id)
    if not user:
        return
    buffs = user.get("buffs", {})
    buffs.pop("revenge_target", None)
    buffs.pop("revenge_target_name", None)
    buffs.pop("revenge_expires", None)
    user["buffs"] = buffs
    save_user(user_id, user)


def get_revenge_multiplier(user_id: str, target_id: str) -> float:
    """Return 1.5 if attacking the revenge target, else 1.0."""
    info = get_revenge_info(user_id)
    if info["active"] and info["target_id"] == target_id:
        return 1.5
    return 1.0


def format_revenge_status(user_id: str) -> str:
    """Display current revenge status for the player."""
    info = get_revenge_info(user_id)
    if not info["active"]:
        return (
            "💚 *No Blood Debt Active*\n"
            "_You haven't been raided recently._"
        )
    return revenge_notification(info["target_name"], info["hours_left"])


# ══════════════════════════════════════════════════════════════════
#  SCOUT SYSTEM — Intelligence Gathering with Deception
# ══════════════════════════════════════════════════════════════════

# In-memory scout missions (lost on restart — acceptable for 5-min window)
ACTIVE_SCOUTS: Dict[str, list] = {}

SCOUT_COST_SILVER = 75

def scout_player(scout_id: str, target_id: str, target_name: str) -> Dict:
    """
    Launch a scout rat toward the target.
    5-minute travel time, 30% chance of lying, mousetraps, firewall.
    """
    scout_user = get_user(scout_id)
    target_user = get_user(target_id)

    if not scout_user:
        return {"success": False, "message": "❌ Scout not found"}
    if not target_user:
        return {"success": False, "message": f"❌ Player '{target_name}' not found"}

    # Cost check
    if scout_user.get("silver", 0) < SCOUT_COST_SILVER:
        have = scout_user.get("silver", 0)
        return {
            "success": False,
            "message": (
                f"❌ *Scouting costs {SCOUT_COST_SILVER} silver.*\n"
                f"You have {have:,}. Earn more by playing rounds."
            )
        }

    # Deduct silver
    scout_user["silver"] -= SCOUT_COST_SILVER
    save_user(scout_id, scout_user)

    # Check firewall
    target_buffs = target_user.get("buffs", {})
    has_firewall = target_buffs.get("firewall_active", False)

    mission_id = str(uuid.uuid4())[:8]
    now = datetime.utcnow()
    returns_at = now + timedelta(minutes=5)

    mission = {
        "id":           mission_id,
        "scout_id":     scout_id,
        "target_id":    target_id,
        "target_name":  target_name,
        "started_at":   now.isoformat(),
        "returns_at":   returns_at.isoformat(),
        "status":       "pending",
        "will_lie":     random.random() < 0.30,
        "firewall_hit": has_firewall and (random.random() < 0.50),
    }

    if scout_id not in ACTIVE_SCOUTS:
        ACTIVE_SCOUTS[scout_id] = []
    ACTIVE_SCOUTS[scout_id].append(mission)

    # Notify target (incoming scout list)
    if "incoming_scouts" not in target_user:
        target_user["incoming_scouts"] = []
    target_user["incoming_scouts"].append({
        "scout_id": scout_id,
        "scout_name": scout_user.get("username", "Unknown"),
        "arrives_at": returns_at.isoformat(),
        "mission_id": mission_id,
    })
    save_user(target_id, target_user)

    return {
        "success":    True,
        "mission_id": mission_id,
        "message": (
            f"🐀 *Scout dispatched to {target_name}'s base!*\n"
            f"⏱️ Returns in 5 minutes.\n"
            f"💸 -{SCOUT_COST_SILVER} silver\n\n"
            f"_Use_ `!scoutcheck {mission_id}` _when ready._\n"
            f"\n"
            f"{gamemaster_says('Your rat scurries into the dark. Whether it returns... is another matter.', 'cryptic')}"
        ),
        "returns_at": returns_at.isoformat(),
    }


def check_scout_return(scout_id: str, mission_id: str) -> Dict:
    """Check if a scout mission has returned and get results."""
    missions = ACTIVE_SCOUTS.get(scout_id, [])
    mission = next((m for m in missions if m["id"] == mission_id), None)

    if not mission:
        return {
            "success": False,
            "message": "❌ Mission not found. It may have expired or already been retrieved."
        }

    # Time check
    try:
        returns_at = datetime.fromisoformat(mission["returns_at"])
    except Exception:
        return {"success": False, "message": "❌ Invalid mission data."}

    if datetime.utcnow() < returns_at:
        remaining = (returns_at - datetime.utcnow()).total_seconds()
        mins = int(remaining // 60)
        secs = int(remaining % 60)
        return {
            "success": False,
            "status":  "pending",
            "message": f"⏳ *Scout still en route.*\nReturns in {mins}m {secs}s.",
        }

    # Remove from active
    ACTIVE_SCOUTS[scout_id] = [m for m in missions if m["id"] != mission_id]

    target_id = mission["target_id"]
    target_user = get_user(target_id)

    if not target_user:
        return {"success": False, "message": "❌ Target account no longer exists."}

    # Firewall kill
    if mission.get("firewall_hit"):
        return {
            "success": False,
            "status":  "killed",
            "message": (
                f"💀 *SCOUT INCINERATED!*\n"
                f"{thin_divider()}\n"
                f"Your scout was obliterated by {mission['target_name']}'s FIREBALL defense.\n"
                f"Their base is heavily protected.\n\n"
                f"{gamemaster_says('A smear on the doorstep. That is all that remains of your rat.', 'angry')}"
            ),
        }

    # Mousetrap check
    target_traps = target_user.get("traps", {})
    if target_traps.get("mousetrap", 0) > 0:
        if random.random() >= 0.70:  # 30% caught
            target_traps["mousetrap"] = max(0, target_traps["mousetrap"] - 1)
            target_user["traps"] = target_traps
            save_user(target_id, target_user)
            return {
                "success": False,
                "status":  "trapped",
                "message": (
                    f"🪤 *SCOUT TRAPPED!*\n"
                    f"{thin_divider()}\n"
                    f"Your spy rat was caught in a mousetrap at {mission['target_name']}'s base!\n"
                    f"One of their traps has been spent.\n\n"
                    f"{gamemaster_says('It snapped shut so fast it barely had time to squeak.', 'neutral')}"
                ),
            }

    # Scout succeeded — build report
    military = target_user.get("military", {})
    resources = target_user.get("base_resources", {}).get("resources", {})
    level = target_user.get("level", 1)
    shield = target_user.get("shield_status", "UNPROTECTED")

    lied = mission.get("will_lie", False)

    # Check player-set fake stats
    fake_stats = target_user.get("displayed_stats", {})
    if fake_stats.get("active") and not lied and random.random() < fake_stats.get("deception_chance", 0.8):
        reported_data = fake_stats.get("fake_data", {})
        military = reported_data.get("military", military)
        resources = reported_data.get("resources", resources)
        level = reported_data.get("level", level)
        shield = reported_data.get("shield", shield)
        fake_used = True
    elif lied:
        military, resources, level, shield = _generate_false_intel(military, resources, level)
        fake_used = False
    else:
        fake_used = False

    report = format_scout_report_display(
        target_name=mission["target_name"],
        military=military,
        resources=resources,
        level=level,
        shield=shield,
        lied=lied,
    )

    gm_comment = gamemaster_says(
        "Your rat returned. Whether it tells the truth is... debatable." if lied
        else "Intelligence acquired. Use it wisely.",
        mood="cryptic" if lied else "neutral"
    )

    return {
        "success":      True,
        "status":       "completed",
        "message":      report + f"\n\n{gm_comment}",
        "intelligence": {
            "military": military,
            "resources": resources,
            "level": level,
            "shield": shield,
        },
        "lied": lied,
    }


def _generate_false_intel(military: dict, resources: dict, level: int):
    """Generate plausible-but-wrong intel."""
    false_mil = {u: max(0, int(c * random.uniform(0.5, 1.6)))
                 for u, c in military.items()}
    false_res = {r: max(0, int(a * random.uniform(0.4, 1.8)))
                 for r, a in resources.items()}
    false_lvl = max(1, level + random.randint(-3, 4))
    false_shield = random.choice(["ACTIVE", "UNPROTECTED", "DISRUPTED"])
    return false_mil, false_res, false_lvl, false_shield


# ══════════════════════════════════════════════════════════════════
#  DEFENSIVE TOOLS — Mousetraps & Firewalls
# ══════════════════════════════════════════════════════════════════

def set_mousetraps(player_id: str, trap_count: int) -> Tuple[bool, str]:
    user = get_user(player_id)
    if not user:
        return False, "Player not found"
    if trap_count < 0 or trap_count > 10:
        return False, "Trap count must be 0-10"
    traps = user.get("traps", {})
    traps["mousetrap"] = trap_count
    user["traps"] = traps
    save_user(player_id, user)
    return True, f"🪤 *{trap_count} mousetrap(s) set.*\n_Incoming scouts have a 30% chance of getting caught._"


def activate_firewall(player_id: str) -> Tuple[bool, str]:
    user = get_user(player_id)
    if not user:
        return False, "Player not found"
    buffs = user.get("buffs", {})
    buffs["firewall_active"] = True
    buffs["firewall_expires"] = (datetime.utcnow() + timedelta(hours=1)).isoformat()
    user["buffs"] = buffs
    save_user(player_id, user)
    return True, (
        "🔥 *FIREBALL DEFENSE ACTIVATED*\n"
        "_Lasts 1 hour. Incoming scouts have a 50% chance of being incinerated._"
    )


def deactivate_firewall(player_id: str) -> Tuple[bool, str]:
    user = get_user(player_id)
    if not user:
        return False, "Player not found"
    buffs = user.get("buffs", {})
    buffs.pop("firewall_active", None)
    buffs.pop("firewall_expires", None)
    user["buffs"] = buffs
    save_user(player_id, user)
    return True, "🔥 Firewall deactivated."


def check_incoming_scouts(player_id: str) -> str:
    """Show any incoming scouts targeting this player."""
    user = get_user(player_id)
    if not user:
        return "Player not found"
    incoming = user.get("incoming_scouts", [])
    if not incoming:
        return "👁️ *No incoming scouts detected.*"

    now = datetime.utcnow()
    lines = ["⚠️ *INCOMING SCOUT ALERT*", thin_divider()]
    active = []
    for scout in incoming:
        try:
            arrives = datetime.fromisoformat(scout["arrives_at"])
            if arrives > now:
                remaining = (arrives - now).total_seconds()
                mins = int(remaining // 60)
                active.append(
                    f"  🐀 From: *{scout.get('scout_name', 'Unknown')}* — arrives in {mins}m"
                )
        except Exception:
            pass

    if active:
        lines.extend(active)
        lines.append(thin_divider())
        lines.append("*COUNTER-INTEL OPTIONS:*")
        lines.append("  🔥 `!firewall on` — 50% incinerate their scout")
        lines.append("  🪤 `!traps [n]` — Set mousetraps (30% catch rate)")
        lines.append("  💭 `!fakestats` — Show fake data to the scout")
    else:
        return "👁️ *All scouts have already arrived.*"

    # Clean up old entries
    user["incoming_scouts"] = [
        s for s in incoming
        if datetime.fromisoformat(s["arrives_at"]) > now
    ]
    save_user(player_id, user)

    return "\n".join(lines)


def set_displayed_stats(player_id: str, fake_data: dict) -> Tuple[bool, str]:
    """Set fake stats to deceive incoming scouts."""
    user = get_user(player_id)
    if not user:
        return False, "Player not found"
    user["displayed_stats"] = {
        "active":           True,
        "fake_data":        fake_data,
        "deception_chance": fake_data.get("deception_chance", 0.80),
        "set_at":           datetime.utcnow().isoformat(),
    }
    save_user(player_id, user)
    return True, "💭 *Fake stats activated.* Scouts will see your decoy data."


def clear_displayed_stats(player_id: str) -> bool:
    user = get_user(player_id)
    if not user:
        return False
    user.pop("displayed_stats", None)
    save_user(player_id, user)
    return True
