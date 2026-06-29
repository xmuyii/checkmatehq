"""
power_system.py — Player Power Calculation System
==================================================
Calculates total power for a player based on:
  - XP level
  - Buildings and their levels
  - Military units (troops, commanders)
  - Weapons and equipment
  - Traps deployed
  - Prestige/Status
  
Power is used to calculate battle outcomes and matchmaking.
"""

from build_system import BUILDING_TYPES, get_base_level
from training_system import UNITS
from weapon_system import WEAPONS
from trap_system import TRAP_TYPES

# ═══════════════════════════════════════════════════════════════════════════
#  POWER CALCULATION
# ═══════════════════════════════════════════════════════════════════════════

def calculate_player_power(user: dict) -> int:
    """
    Calculate total power for a player.
    Returns integer power value used for battles and matchmaking.
    """
    power = 0
    
    # 1. Base XP Power (100 points per XP level)
    xp = user.get('xp', 0)
    xp_level = 1 + (xp // 1000)
    power += xp_level * 100
    
    # 2. Building Power (each building level adds power)
    buildings = user.get('buildings', {})
    # Defensive: handle case where buildings is stored as JSON string
    if isinstance(buildings, str):
        try:
            import json
            buildings = json.loads(buildings)
        except:
            buildings = {}
    if isinstance(buildings, dict):
        for building_id, level in buildings.items():
            if building_id in BUILDING_TYPES:
                # Each building level adds 50 power (500 power per max level building)
                power += level * 50
    
    # 3. Military Power (troops are power)
    military = user.get('military', {})
    if isinstance(military, str):
        try:
            import json
            military = json.loads(military)
        except:
            military = {}
    if isinstance(military, dict):
        for military_id, count in military.items:
            if military_id in UNITS:
                power += (count * 2)  # Each soldier = 2 power
    
    # 4. Weapons Power
    weapons = user.get('weapons', {})
    if isinstance(weapons, dict):
        for weapon_id, data in weapons.items():
            if weapon_id in WEAPONS:
                level = data.get('level', 0)
                power += level * 30  # Each weapon level = 30 power
            else:
                # If it's just a number (level)
                power += data * 30 if isinstance(data, int) else 0
    
    # 5. Traps Power
    traps = user.get('traps', {})
    for trap_id, count in traps.items():
        if trap_id in TRAP_TYPES:
            power += count * 10  # Each trap = 10 power
    
    # 6. Prestige Power (if applicable)
    prestige_level = user.get('prestige_level', 0)
    power += prestige_level * 200
    
    # 7. Base Resources Power (having resources stocked up adds slight power)
    base_res = user.get('base_resources', {})
    resources = base_res.get('resources', {})
    total_resources = sum(resources.values()) if isinstance(resources, dict) else 0
    power += (total_resources // 1000)  # Every 1000 resources = 1 power
    
    
    return max(1, power)  # Minimum 1 power


def get_power_breakdown(user: dict) -> dict:
    """
    Return detailed power breakdown for a player.
    Useful for showing power composition in UI.
    """
    xp = user.get('xp', 0)
    xp_level = 1 + (xp // 1000)
    
    buildings = user.get('buildings', {})
    building_power = sum(level * 50 for level in buildings.values())
    
    military = user.get('military', {})
    military_power = (military.get('soldiers', 0) * 2) + (military.get('commanders', 0) * 500)
    
    weapons = user.get('weapons', {})
    weapon_power = 0
    if isinstance(weapons, dict):
        for weapon_id, data in weapons.items():
            if isinstance(data, dict):
                weapon_power += data.get('level', 0) * 30
            else:
                weapon_power += (data * 30) if isinstance(data, int) else 0
    
    traps = user.get('traps', {})
    trap_power = sum(count * 10 for count in traps.values())
    
    prestige_level = user.get('prestige_level', 0)
    prestige_power = prestige_level * 200
    
    base_res = user.get('base_resources', {})
    resources = base_res.get('resources', {})
    total_resources = sum(resources.values()) if isinstance(resources, dict) else 0
    resource_power = (total_resources // 1000)
    
    inventory = user.get('inventory', {})
    inventory_power = (len(inventory) * 25) if isinstance(inventory, dict) else 0
    
    return {
        'xp_power': xp_level * 100,
        'building_power': building_power,
        'military_power': military_power,
        'weapon_power': weapon_power,
        'trap_power': trap_power,
        'prestige_power': prestige_power,
        'resource_power': resource_power,
        'inventory_power': inventory_power,
        'total_power': calculate_player_power(user),
    }


def format_power_display(user: dict) -> str:
    """
    Format power info for display in game UI.
    """
    total_power = calculate_player_power(user)
    breakdown = get_power_breakdown(user)
    
    msg = f"⚡ *POWER LEVEL: {total_power:,}*\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"🎖️ XP Power:      {breakdown['xp_power']:>6}\n"
    msg += f"🏗️ Building:      {breakdown['building_power']:>6}\n"
    msg += f"⚔️ Military:       {breakdown['military_power']:>6}\n"
    msg += f"🗡️ Weapons:        {breakdown['weapon_power']:>6}\n"
    msg += f"🔱 Traps:         {breakdown['trap_power']:>6}\n"
    msg += f"👑 Prestige:      {breakdown['prestige_power']:>6}\n"
    msg += f"💰 Resources:     {breakdown['resource_power']:>6}\n"
    msg += f"🎒 Inventory:     {breakdown['inventory_power']:>6}\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    
    return msg


def calculate_battle_outcome(attacker_user: dict, defender_user: dict) -> dict:
    """
    Calculate battle outcome based on player powers.
    Returns: {'winner': 'attacker'|'defender', 'attacker_power': int, 'defender_power': int}
    """
    attacker_power = calculate_player_power(attacker_user)
    defender_power = calculate_player_power(defender_user)
    
    # Base winner is who has more power
    winner = 'attacker' if attacker_power > defender_power else 'defender'
    
    # Add randomness (±20% swing)
    import random
    swing = random.randint(-20, 20) / 100
    
    attacker_adjusted = attacker_power * (1 + swing)
    defender_adjusted = defender_power * (1 - swing)
    
    winner = 'attacker' if attacker_adjusted > defender_adjusted else 'defender'
    
    return {
        'winner': winner,
        'attacker_power': attacker_power,
        'defender_power': defender_power,
        'attacker_adjusted': int(attacker_adjusted),
        'defender_adjusted': int(defender_adjusted),
        'power_difference': abs(attacker_power - defender_power),
    }


def get_power_tier(power: int) -> str:
    """
    Classify player into power tier.
    """
    if power < 1000:
        return "🟤 Novice"
    elif power < 5000:
        return "🟢 Recruit"
    elif power < 10000:
        return "🔵 Soldier"
    elif power < 25000:
        return "🟣 Commander"
    elif power < 50000:
        return "🟠 Warlord"
    elif power < 100000:
        return "🔴 Emperor"
    else:
        return "⚫ Immortal"
