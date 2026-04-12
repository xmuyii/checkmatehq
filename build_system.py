# -*- coding: utf-8 -*-
"""
build_system.py — Base Building & Internal Structures
Players build training grounds, laboratories, medical centers, etc.
Each structure provides bonuses and uses resources.
"""

from typing import Dict, Tuple
import json

# ═══════════════════════════════════════════════════════════════════════════
#  BUILDING TYPES & PROPERTIES
# ═══════════════════════════════════════════════════════════════════════════

BUILDING_TYPES = {
    "training_ground": {
        "name": "🎖️ TRAINING GROUND",
        "description": "Speed up unit training by 25%",
        "bonus": {"training_speed": 0.25},
        "cost": {"wood": 200, "bronze": 100},
        "min_level": 1,
        "unlock_time": "Level 1",
    },
    "medical_center": {
        "name": "⚕️ MEDICAL CENTER",
        "description": "Heal casualties during war. +20% troop recovery",
        "bonus": {"troop_recovery": 0.20},
        "cost": {"wood": 300, "bronze": 150, "iron": 50},
        "min_level": 3,
        "unlock_time": "Level 3",
    },
    "science_lab": {
        "name": "🔬 SCIENCE LAB",
        "description": "Unlock advanced research. +50% research speed",
        "bonus": {"research_speed": 0.50},
        "cost": {"wood": 400, "bronze": 250, "iron": 100, "diamond": 10},
        "min_level": 5,
        "unlock_time": "Level 5",
    },
    "treasury": {
        "name": "💰 TREASURY",
        "description": "Increase resource storage +30%",
        "bonus": {"resource_storage": 0.30},
        "cost": {"wood": 500, "bronze": 300, "iron": 150},
        "min_level": 2,
        "unlock_time": "Level 2",
    },
    "defense_wall": {
        "name": "🛡️ DEFENSE WALL",
        "description": "Reduce incoming trap damage by 15%",
        "bonus": {"defense_reduction": 0.15},
        "cost": {"wood": 600, "iron": 300, "bronze": 200},
        "min_level": 4,
        "unlock_time": "Level 4",
    },
    "command_center": {
        "name": "🎖️ COMMAND CENTER",
        "description": "Lead larger armies. +10 unit capacity",
        "bonus": {"unit_capacity": 10},
        "cost": {"wood": 700, "iron": 400, "bronze": 300, "diamond": 20},
        "min_level": 6,
        "unlock_time": "Level 6",
    },
    "barracks": {
        "name": "🏘️ BARRACKS",
        "description": "Train units 40% faster. More military efficiency",
        "bonus": {"training_speed": 0.40},
        "cost": {"wood": 800, "bronze": 500, "iron": 200},
        "min_level": 3,
        "unlock_time": "Level 3",
    },
    "spy_lodge": {
        "name": "🕵️ SPY LODGE",
        "description": "Scout enemies for 50 silver instead of 100",
        "bonus": {"scout_cost_reduction": 50},
        "cost": {"wood": 400, "iron": 200, "bronze": 250},
        "min_level": 5,
        "unlock_time": "Level 5",
    },
    "forge": {
        "name": "🔨 FORGE",
        "description": "Craft rare items. Unlock secret recipes",
        "bonus": {"crafting_available": True},
        "cost": {"iron": 500, "diamond": 50, "bronze": 400},
        "min_level": 7,
        "unlock_time": "Level 7",
    },
    "ritual_chamber": {
        "name": "🌑 RITUAL CHAMBER",
        "description": "Gain cosmic bonuses. +100% XP from sector battles",
        "bonus": {"sector_xp_boost": 1.0},
        "cost": {"diamond": 100, "iron": 600, "bronze": 500},
        "min_level": 9,
        "unlock_time": "Level 9",
    },
}

# ═══════════════════════════════════════════════════════════════════════════
#  BUILDING SYSTEM
# ═══════════════════════════════════════════════════════════════════════════

def get_available_buildings(base_level: int) -> list:
    """Get all buildings available at this base level."""
    available = []
    for building_id, building_info in BUILDING_TYPES.items():
        if building_info["min_level"] <= base_level:
            available.append(building_id)
    return available


def can_build_building(building_type: str, base_level: int) -> Tuple[bool, str]:
    """Check if a building can be constructed at this base level."""
    if building_type not in BUILDING_TYPES:
        return False, f"❌ Unknown building: {building_type}"
    
    building = BUILDING_TYPES[building_type]
    if building["min_level"] > base_level:
        return False, f"❌ Base level {base_level} too low. Need level {building['min_level']} to build {building['name']}"
    
    return True, "✅ Can build"


def calculate_building_cost(building_type: str, base_level: int) -> Dict[str, int]:
    """Calculate adjusted cost based on level (upgrades cost more)."""
    if building_type not in BUILDING_TYPES:
        return {}
    
    building = BUILDING_TYPES[building_type]
    base_cost = dict(building["cost"])
    
    # Upgrades cost 50% more per level
    level_multiplier = 1.0 + (base_level - building["min_level"]) * 0.5
    
    adjusted_cost = {}
    for resource, amount in base_cost.items():
        adjusted_cost[resource] = int(amount * level_multiplier)
    
    return adjusted_cost


def format_buildings_menu(base_level: int, current_buildings: Dict[str, int]) -> str:
    """Format menu of available buildings."""
    available = get_available_buildings(base_level)
    
    menu = f"""
╔════════════════════════════════════════════════════════════════╗
║        🏰  BASE CONSTRUCTION MENU  🏰                         ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║  Base Level: {base_level}                                             ║
║  Upgrade buildings to unlock more bonuses                      ║
║                                                                ║
╠════════════════════════════════════════════════════════════════╣
║  AVAILABLE STRUCTURES:                                         ║
║
"""
    
    for building_id in available:
        building = BUILDING_TYPES[building_id]
        current_level = current_buildings.get(building_id, 0)
        
        # Cost for next level
        cost = calculate_building_cost(building_id, current_level + 1)
        cost_str = " + ".join([f"{amt}{res[0].upper()}" for res, amt in cost.items()])
        
        bonus_desc = building["description"]
        
        menu += f"║  {building['name']:<25} | Level: {current_level}\n"
        menu += f"║    {bonus_desc}\n"
        menu += f"║    Cost: {cost_str}\n"
        menu += f"║\n"
    
    menu += """║                                                                ║
║  Build: !build [building_name]                               ║
║  Example: !build training_ground                             ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
"""
    return menu


def apply_building_bonuses(buildings: Dict[str, int]) -> Dict[str, float]:
    """Calculate total bonuses from all buildings."""
    bonuses = {
        "training_speed": 0,
        "troop_recovery": 0,
        "research_speed": 0,
        "resource_storage": 0,
        "defense_reduction": 0,
        "unit_capacity": 0,
        "scout_cost_reduction": 0,
        "crafting_available": False,
        "sector_xp_boost": 0,
    }
    
    for building_type, level in buildings.items():
        if building_type not in BUILDING_TYPES or level == 0:
            continue
        
        building = BUILDING_TYPES[building_type]
        for bonus_key, bonus_value in building["bonus"].items():
            if isinstance(bonus_value, bool):
                bonuses[bonus_key] = bonus_value
            else:
                bonuses[bonus_key] += bonus_value * level  # Scale by level
    
    return bonuses
