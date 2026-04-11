"""
attack_system.py — Full raid mechanics with resource theft

Mechanics:
  - Attacker's army fights defender's army
  - Success = steal 50% of defender's resources
  - Attacker's troop count determines carrying capacity
  - Victim gets instant DM notification
  - Revenge debt set on defender
"""

import random
from datetime import datetime
from typing import Tuple, Dict
from supabase_db import get_user, save_user
from revenge_system import set_revenge_target, get_revenge_multiplier

# ═══════════════════════════════════════════════════════════════════════════
#  ARMY STRENGTH CALCULATION
# ═══════════════════════════════════════════════════════════════════════════

UNIT_POWER = {
    "footmen": 1,
    "archers": 3,
    "lancers": 8,
    "castellans": 15,
    "pawns": 1,
}

CARRYING_CAPACITY = {
    "footmen": 50,      # 1 Footman can carry 50 resources
    "archers": 40,      # Archers travel light
    "lancers": 100,     # Heavy unit, carries more
    "castellans": 150,  # Tanks, armored for loot
    "pawns": 50,
}


def calculate_army_strength(military: Dict[str, int]) -> int:
    """Calculate total power of an army based on unit types."""
    if not military:
        return 0
    
    total_power = 0
    for unit_type, count in military.items():
        power = UNIT_POWER.get(unit_type, 1)
        total_power += power * count
    
    return total_power


def calculate_carrying_capacity(military: Dict[str, int]) -> int:
    """Calculate how much loot an army can carry back."""
    if not military:
        return 0
    
    total_capacity = 0
    for unit_type, count in military.items():
        capacity = CARRYING_CAPACITY.get(unit_type, 50)
        total_capacity += capacity * count
    
    return total_capacity


# ═══════════════════════════════════════════════════════════════════════════
#  BATTLE CALCULATION
# ═══════════════════════════════════════════════════════════════════════════

def calculate_battle_outcome(
    attacker_id: str, 
    defender_id: str,
    revenge_multiplier: float = 1.0
) -> Tuple[bool, Dict]:
    """
    Execute a raid.
    
    Returns (success, result_dict) where result_dict contains:
    - success: bool
    - attacker_losses: count of troops killed
    - defender_losses: count of troops killed
    - resources_stolen: dict of stolen resources
    - total_loot_value: number
    - message: str with battle description
    """
    
    attacker = get_user(attacker_id)
    defender = get_user(defender_id)
    
    if not attacker or not defender:
        return False, {"message": "One or both players not found"}
    
    # Get armies
    attacker_army = attacker.get("military", {})
    defender_army = defender.get("military", {})
    
    # Get resources to steal
    defender_resources = defender.get("base_resources", {}).get("resources", {})
    
    # Calculate army strengths
    attacker_power = calculate_army_strength(attacker_army)
    defender_power = calculate_army_strength(defender_army)
    
    # Apply revenge multiplier to attacker if active
    if revenge_multiplier > 1.0:
        attacker_power = int(attacker_power * revenge_multiplier)
    
    # Add chaos factor (0.8 to 1.2) for suspense
    attacker_roll = attacker_power * random.uniform(0.8, 1.2)
    defender_roll = defender_power * random.uniform(0.8, 1.2)
    
    # Determine winner
    attacker_wins = attacker_roll > defender_roll
    
    # Calculate casualties
    if attacker_wins:
        # Attacker wins - defender loses 20% troops
        casualty_rate = 0.2
        defender_losses = {unit: int(count * casualty_rate) for unit, count in defender_army.items()}
        attacker_losses = {unit: int(count * 0.05) for unit, count in attacker_army.items()}  # Attacker takes 5% casualty
    else:
        # Defender wins - attacker loses 30% troops
        casualty_rate = 0.3
        attacker_losses = {unit: int(count * casualty_rate) for unit, count in attacker_army.items()}
        defender_losses = {unit: int(count * 0.05) for unit, count in defender_army.items()}  # Defender takes minimal casualty
    
    # If attacker wins, steal resources
    resources_stolen = {}
    total_loot_value = 0
    
    if attacker_wins:
        # Calculate carrying capacity
        carrying_capacity = calculate_carrying_capacity(attacker_army)
        
        # Steal 50% of each resource type (up to carrying capacity)
        for resource_type, amount in defender_resources.items():
            steal_amount = int(amount * 0.5)  # 50% of each resource
            if steal_amount > 0:
                resources_stolen[resource_type] = steal_amount
                total_loot_value += steal_amount
        
        # Cap by carrying capacity - if too much loot, steal only what can be carried
        if total_loot_value > carrying_capacity:
            # Proportionally reduce what can be carried
            ratio = carrying_capacity / total_loot_value
            resources_stolen = {res: int(amount * ratio) for res, amount in resources_stolen.items()}
            total_loot_value = carrying_capacity
    
    # Apply changes to both players
    if attacker_wins:
        # Attacker gets resources
        attacker_resources = attacker.get("base_resources", {}).get("resources", {})
        for resource, amount in resources_stolen.items():
            attacker_resources[resource] = attacker_resources.get(resource, 0) + amount
        attacker_base_res = attacker.get("base_resources", {})
        attacker_base_res["resources"] = attacker_resources
        attacker["base_resources"] = attacker_base_res
        
        # Defender loses resources
        defender_base_res = defender.get("base_resources", {})
        defender_resources_new = defender_base_res.get("resources", {})
        for resource, amount in resources_stolen.items():
            defender_resources_new[resource] = max(0, defender_resources_new.get(resource, 0) - amount)
        defender_base_res["resources"] = defender_resources_new
        defender["base_resources"] = defender_base_res
    
    # Apply casualties to both armies
    attacker_army_new = {}
    for unit_type, count in attacker_army.items():
        losses = attacker_losses.get(unit_type, 0)
        attacker_army_new[unit_type] = max(0, count - losses)
    attacker["military"] = attacker_army_new
    
    defender_army_new = {}
    for unit_type, count in defender_army.items():
        losses = defender_losses.get(unit_type, 0)
        defender_army_new[unit_type] = max(0, count - losses)
    defender["military"] = defender_army_new
    
    # Update win/loss records
    if attacker_wins:
        attacker["wins"] = attacker.get("wins", 0) + 1
        defender["losses"] = defender.get("losses", 0) + 1
    else:
        attacker["losses"] = attacker.get("losses", 0) + 1
        defender["wins"] = defender.get("wins", 0) + 1
    
    # Save both players
    save_user(attacker_id, attacker)
    save_user(defender_id, defender)
    
    # If attacker won, set revenge debt on defender
    if attacker_wins:
        set_revenge_target(defender_id, attacker_id, attacker.get("username", "Unknown"))
    
    # Format result
    result = {
        "success": attacker_wins,
        "attacker_losses": attacker_losses,
        "defender_losses": defender_losses,
        "resources_stolen": resources_stolen if attacker_wins else {},
        "total_loot_value": total_loot_value if attacker_wins else 0,
        "attacker_power": int(attacker_roll),
        "defender_power": int(defender_roll),
    }
    
    return attacker_wins, result


def format_battle_report(
    attacker_name: str,
    defender_name: str,
    result: Dict,
    is_revenge: bool = False
) -> str:
    """Format battle result as tactical report."""
    
    lines = []
    
    if is_revenge:
        lines.append("🩸 **BLOOD DEBT SETTLED**")
    else:
        lines.append("⚔️ **BATTLE REPORT**")
    
    lines.append("=" * 60)
    lines.append(f"\n🛰️ *ATTACKER:* {attacker_name}")
    lines.append(f"🛡️ *DEFENDER:* {defender_name}")
    lines.append(f"\n💪 Power Roll: {result.get('attacker_power', 0)} vs {result.get('defender_power', 0)}")
    
    if result.get("success"):
        lines.append("\n✅ **VICTORY**")
        lines.append("\n💀 *CASUALTIES:*")
        
        attacker_losses = result.get("attacker_losses", {})
        if attacker_losses:
            lines.append("├─ 🏃 Attacker Losses:")
            for unit, count in attacker_losses.items():
                if count > 0:
                    lines.append(f"│  ├─ {unit.capitalize()}: {count}")
        
        defender_losses = result.get("defender_losses", {})
        if defender_losses:
            lines.append("├─ 🏃 Defender Losses:")
            for unit, count in defender_losses.items():
                if count > 0:
                    lines.append(f"│  ├─ {unit.capitalize()}: {count}")
        
        # Loot
        resources_stolen = result.get("resources_stolen", {})
        if resources_stolen:
            lines.append("\n💎 *PLUNDER:*")
            for resource, amount in resources_stolen.items():
                if amount > 0:
                    emoji_map = {
                        "wood": "🌲",
                        "bronze": "🧱",
                        "iron": "⛓️",
                        "diamond": "💎",
                        "relics": "🏺"
                    }
                    emoji = emoji_map.get(resource, "?")
                    lines.append(f"├─ {emoji} {resource.capitalize()}: {amount}")
            
            lines.append(f"\n📊 *Total Loot:* {result.get('total_loot_value', 0)} resources")
    else:
        lines.append("\n❌ **DEFEAT**")
        lines.append("\n💀 *CASUALTIES:*")
        
        attacker_losses = result.get("attacker_losses", {})
        if attacker_losses:
            lines.append("├─ 🏃 Your Losses:")
            for unit, count in attacker_losses.items():
                if count > 0:
                    lines.append(f"│  ├─ {unit.capitalize()}: {count}")
        
        defender_losses = result.get("defender_losses", {})
        if defender_losses:
            lines.append("├─ 🏃 Defender's Losses:")
            for unit, count in defender_losses.items():
                if count > 0:
                    lines.append(f"│  ├─ {unit.capitalize()}: {count}")
    
    lines.append("\n" + "=" * 60)
    
    return "\n".join(lines)


def format_raid_notification(
    attacker_name: str,
    defender_name: str,
    result: Dict
) -> str:
    """Format notification for defender (victim)."""
    
    lines = []
    lines.append("🚨 **INCOMING RAID!**\n")
    lines.append(f"Lord {attacker_name} has breached your defenses!\n")
    
    if result.get("success"):
        resources_stolen = result.get("resources_stolen", {})
        lines.append("*You have sustained losses:*\n")
        
        defender_losses = result.get("defender_losses", {})
        for unit, count in defender_losses.items():
            if count > 0:
                lines.append(f"• {unit.capitalize()}: -{count} troops\n")
        
        if resources_stolen:
            lines.append("\n*Resources Stolen:*\n")
            emoji_map = {
                "wood": "🌲",
                "bronze": "🧱",
                "iron": "⛓️",
                "diamond": "💎",
                "relics": "🏺"
            }
            for resource, amount in resources_stolen.items():
                if amount > 0:
                    emoji = emoji_map.get(resource, "?")
                    lines.append(f"• {emoji} {resource.capitalize()}: -{amount}\n")
        
        lines.append(f"\n⏰ *You have 24 hours to take !revenge with a 1.5x damage multiplier.*")
    else:
        lines.append("✅ Your defenses held! The attacker was defeated.\n")
        
        defender_losses = result.get("defender_losses", {})
        if defender_losses:
            lines.append("*Losses Inflicted:*\n")
            for unit, count in defender_losses.items():
                if count > 0:
                    lines.append(f"• {unit.capitalize()}: -{count}")
    
    return "".join(lines)
