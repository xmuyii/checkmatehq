"""Game Systems - Military, Base Building, Food/Upkeep"""

# MILITARY SYSTEM
UNIT_TIERS = {
    1: {
        "name": "Militia",
        "cost": {"silver": 100, "food": 10},
        "attack": 5,
        "defense": 3,
        "health": 20,
        "training_time": 60,  # seconds
    },
    2: {
        "name": "Soldier",
        "cost": {"silver": 250, "food": 25},
        "attack": 12,
        "defense": 8,
        "health": 50,
        "training_time": 120,
    },
    3: {
        "name": "Knight",
        "cost": {"silver": 500, "food": 50},
        "attack": 25,
        "defense": 15,
        "health": 100,
        "training_time": 240,
    },
    4: {
        "name": "Paladin",
        "cost": {"silver": 1000, "food": 100},
        "attack": 50,
        "defense": 30,
        "health": 200,
        "training_time": 480,
    },
    5: {
        "name": "Warlord",
        "cost": {"silver": 2500, "food": 250},
        "attack": 100,
        "defense": 60,
        "health": 400,
        "training_time": 960,
    },
}

# BASE BUILDING SYSTEM
BASE_BUILDINGS = {
    "barracks": {
        "name": "🏛️ Barracks",
        "level": 1,
        "max_level": 10,
        "cost": {"silver": 500, "xp": 100},
        "effect": "Train military units. +1 unit capacity per level.",
        "capacity_base": 5,
    },
    "warehouse": {
        "name": "📦 Warehouse",
        "level": 1,
        "max_level": 10,
        "cost": {"silver": 300, "xp": 50},
        "effect": "Store resources. +500 capacity per level.",
        "capacity_base": 1000,
    },
    "farm": {
        "name": "🌾 Farm",
        "level": 1,
        "max_level": 10,
        "cost": {"silver": 200, "xp": 30},
        "effect": "Generate food. +5 food/hour per level.",
        "production_base": 5,
    },
    "wall": {
        "name": "🧱 Wall",
        "level": 1,
        "max_level": 5,
        "cost": {"silver": 1000, "xp": 200},
        "effect": "Defend against raids. +30% defense per level.",
        "defense_bonus": 0.30,
    },
    "watchtower": {
        "name": "🏯 Watchtower",
        "level": 1,
        "max_level": 3,
        "cost": {"silver": 2000, "xp": 300},
        "effect": "Early warning system. -30% surprise attack damage.",
        "warning_bonus": 0.30,
    },
}

# FOOD & UPKEEP SYSTEM
FOOD_UPKEEP = {
    "militia": 0.5,      # food/hour per unit
    "soldier": 1.0,
    "knight": 2.0,
    "paladin": 4.0,
    "warlord": 8.0,
}

FOOD_PRODUCTION = {
    "farm_level_1": 5,    # food/hour
    "farm_level_2": 10,
    "farm_level_3": 15,
    "farm_level_4": 20,
    "farm_level_5": 25,
}

STARVATION_PENALTIES = {
    "no_food_1h": 0.95,      # 5% army damage per hour
    "no_food_4h": 0.80,      # 20% cumulative after 4 hours
    "no_food_8h": 0.50,      # 50% cumulative after 8 hours
    "no_food_24h": 0.0,      # Army disbanded after 1 day
}


# MILITARY OPERATIONS
def train_unit(player_id: str, unit_tier: int, quantity: int = 1) -> dict:
    """Train military units"""
    if unit_tier not in UNIT_TIERS:
        return {"ok": False, "msg": "Invalid unit tier"}
    
    unit = UNIT_TIERS[unit_tier]
    total_cost = {
        "silver": unit["cost"]["silver"] * quantity,
        "food": unit["cost"]["food"] * quantity,
    }
    total_training_time = unit["training_time"] * quantity
    
    return {
        "ok": True,
        "unit_name": unit["name"],
        "quantity": quantity,
        "cost": total_cost,
        "training_time_seconds": total_training_time,
    }


def calculate_army_strength(units: list) -> dict:
    """Calculate total army stats"""
    total_attack = 0
    total_defense = 0
    total_health = 0
    total_upkeep = 0
    
    for unit_type, count in units:
        if unit_type in [1, 2, 3, 4, 5]:
            tier = UNIT_TIERS[unit_type]
            total_attack += tier["attack"] * count
            total_defense += tier["defense"] * count
            total_health += tier["health"] * count
            unit_name = tier["name"].lower()
            total_upkeep += FOOD_UPKEEP.get(unit_name, 0) * count
    
    return {
        "attack": total_attack,
        "defense": total_defense,
        "health": total_health,
        "food_upkeep_per_hour": total_upkeep,
    }


def check_starvation(player_id: str, current_food: int, upkeep_rate: float, hours_without_food: int) -> dict:
    """Check if army is starving"""
    if current_food <= 0 and hours_without_food > 0:
        if hours_without_food >= 24:
            return {"starving": True, "severity": "ARMY_DISBANDED", "health_penalty": 0.0}
        elif hours_without_food >= 8:
            return {"starving": True, "severity": "CRITICAL", "health_penalty": 0.5}
        elif hours_without_food >= 4:
            return {"starving": True, "severity": "SEVERE", "health_penalty": 0.2}
        elif hours_without_food >= 1:
            return {"starving": True, "severity": "WARNING", "health_penalty": 0.05}
    
    return {"starving": False, "severity": "NONE", "health_penalty": 0.0}


# RAID SYSTEM (for later)
def calculate_raid_damage(attacker_army: dict, defender_army: dict, defender_walls: int = 0) -> dict:
    """Calculate damage in a raid"""
    # Attacker advantage
    attacker_damage = attacker_army["attack"] * 1.2
    
    # Defender gets wall bonus
    defender_defense = defender_army["defense"]
    if defender_walls > 0:
        defender_defense *= (1 + (defender_walls * 0.3))
    
    # Mitigation
    damage_taken = max(0, attacker_damage - defender_defense)
    resources_stolen = 0  # TODO: calculate based on warehouse
    
    return {
        "damage_dealt": damage_taken,
        "resources_stolen": resources_stolen,
        "attacker_losses_percent": min(100, (defender_defense / attacker_damage) * 100),
    }


if __name__ == "__main__":
    # Test the systems
    print("Testing Military System...")
    result = train_unit("test_user", 3, 2)
    print(result)
    
    print("\nTesting Army Strength...")
    units = [(1, 5), (2, 3)]  # 5 militia, 3 soldiers
    strength = calculate_army_strength(units)
    print(strength)
    
    print("\nTesting Starvation Check...")
    starvation = check_starvation("test_user", 0, 10, 5)
    print(starvation)
