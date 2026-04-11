"""Game Engine - Autonomous systems for training, construction, food, raids"""

import test_supabase_db as db
from game_systems import *
from datetime import datetime, timedelta
import asyncio

# ============= TRAINING QUEUE =============

def add_to_training_queue(player_id: str, unit_tier: int, quantity: int) -> dict:
    """Add units to training queue"""
    user = db.get_user(player_id)
    if not user:
        return {"ok": False, "msg": "User not found"}
    
    if unit_tier not in UNIT_TIERS:
        return {"ok": False, "msg": "Invalid unit tier"}
    
    unit = UNIT_TIERS[unit_tier]
    
    # Check resources
    silver_cost = unit["cost"]["silver"] * quantity
    food_cost = unit["cost"]["food"] * quantity
    
    if user.get("silver", 0) < silver_cost:
        return {"ok": False, "msg": f"Need {silver_cost} silver, have {user.get('silver', 0)}"}
    
    if user.get("food", 0) < food_cost:
        return {"ok": False, "msg": f"Need {food_cost} food, have {user.get('food', 0)}"}
    
    # Deduct resources
    user["silver"] -= silver_cost
    user["food"] -= food_cost
    
    # Add to training queue
    if "training_queue" not in user:
        user["training_queue"] = []
    
    training_item = {
        "unit_tier": unit_tier,
        "quantity": quantity,
        "start_time": datetime.now().isoformat(),
        "completion_time": (datetime.now() + timedelta(seconds=unit["training_time"] * quantity)).isoformat(),
        "completed": False,
    }
    user["training_queue"].append(training_item)
    
    db.save_user(player_id, user)
    
    return {
        "ok": True,
        "msg": f"Training {quantity}x {unit['name']} queued",
        "completion_time": training_item["completion_time"],
    }


def process_training_queue(player_id: str) -> dict:
    """Process completed training items"""
    user = db.get_user(player_id)
    if not user:
        return {"ok": False, "msg": "User not found"}
    
    queue = user.get("training_queue", [])
    completed = []
    now = datetime.now()
    
    for item in queue:
        if not item.get("completed"):
            completion_time = datetime.fromisoformat(item["completion_time"])
            if now >= completion_time:
                # Training complete!
                unit_tier = item["unit_tier"]
                quantity = item["quantity"]
                
                military = user.get("military", {})
                military[str(unit_tier)] = military.get(str(unit_tier), 0) + quantity
                user["military"] = military
                
                item["completed"] = True
                completed.append(f"{quantity}x {UNIT_TIERS[unit_tier]['name']}")
    
    if completed:
        user["training_queue"] = queue
        db.save_user(player_id, user)
    
    return {"ok": True, "completed": completed}


# ============= CONSTRUCTION QUEUE =============

def add_to_construction_queue(player_id: str, building_key: str) -> dict:
    """Queue up building upgrade"""
    user = db.get_user(player_id)
    if not user:
        return {"ok": False, "msg": "User not found"}
    
    if building_key not in BASE_BUILDINGS:
        return {"ok": False, "msg": "Invalid building"}
    
    building = BASE_BUILDINGS[building_key]
    
    # Check resources
    silver_cost = building["cost"]["silver"]
    xp_cost = building["cost"]["xp"]
    
    if user.get("silver", 0) < silver_cost:
        return {"ok": False, "msg": f"Need {silver_cost} silver"}
    
    # Deduct resources
    user["silver"] -= silver_cost
    user["xp"] = user.get("xp", 0) - xp_cost if user.get("xp", 0) >= xp_cost else 0
    
    # Add to construction queue
    if "construction_queue" not in user:
        user["construction_queue"] = []
    
    construction_time = 30  # 30 seconds for testing (real: minutes/hours)
    
    construction_item = {
        "building_key": building_key,
        "start_time": datetime.now().isoformat(),
        "completion_time": (datetime.now() + timedelta(seconds=construction_time)).isoformat(),
        "completed": False,
    }
    user["construction_queue"].append(construction_item)
    
    db.save_user(player_id, user)
    
    return {
        "ok": True,
        "msg": f"Upgrading {building['name']}",
        "completion_time": construction_item["completion_time"],
    }


def process_construction_queue(player_id: str) -> dict:
    """Process completed constructions"""
    user = db.get_user(player_id)
    if not user:
        return {"ok": False, "msg": "User not found"}
    
    queue = user.get("construction_queue", [])
    completed = []
    now = datetime.now()
    
    for item in queue:
        if not item.get("completed"):
            completion_time = datetime.fromisoformat(item["completion_time"])
            if now >= completion_time:
                # Construction complete!
                building_key = item["building_key"]
                
                buildings = user.get("base_buildings", {})
                if building_key not in buildings:
                    buildings[building_key] = {"level": 1}
                
                buildings[building_key]["level"] = buildings[building_key].get("level", 1) + 1
                user["base_buildings"] = buildings
                
                item["completed"] = True
                completed.append(f"{BASE_BUILDINGS[building_key]['name']} → LVL {buildings[building_key]['level']}")
    
    if completed:
        user["construction_queue"] = queue
        db.save_user(player_id, user)
    
    return {"ok": True, "completed": completed}


# ============= FOOD SYSTEM =============

def calculate_food_production(farm_level: int) -> float:
    """Calculate food produced per hour"""
    return FOOD_PRODUCTION.get(f"farm_level_{farm_level}", 5)


def calculate_food_upkeep(player_id: str) -> float:
    """Calculate total food cost per hour"""
    user = db.get_user(player_id)
    if not user:
        return 0
    
    military = user.get("military", {})
    strength = calculate_army_strength([(int(k), v) for k, v in military.items()])
    return strength["food_upkeep_per_hour"]


def process_food_tick(player_id: str, hours_passed: float = 1):
    """Process food production/consumption over time"""
    user = db.get_user(player_id)
    if not user:
        return
    
    farm_level = user.get("base_buildings", {}).get("farm", {}).get("level", 1)
    production = calculate_food_production(farm_level) * hours_passed
    upkeep = calculate_food_upkeep(player_id) * hours_passed
    
    current_food = user.get("food", 0)
    new_food = max(0, current_food + production - upkeep)
    
    # Track starvation
    if new_food <= 0 and upkeep > 0:
        if not user.get("starvation_start"):
            user["starvation_start"] = datetime.now().isoformat()
    else:
        user["starvation_start"] = None
    
    user["food"] = new_food
    db.save_user(player_id, user)


def apply_starvation_penalties(player_id: str):
    """Apply penalties if army is starving"""
    user = db.get_user(player_id)
    if not user:
        return {"ok": False}
    
    if not user.get("starvation_start"):
        return {"ok": True, "starving": False}
    
    starvation_start = datetime.fromisoformat(user["starvation_start"])
    hours_starving = (datetime.now() - starvation_start).total_seconds() / 3600
    
    military = user.get("military", {})
    penalty_severity = "NONE"
    health_penalty = 0
    
    if hours_starving >= 24:
        # Disband entire army
        user["military"] = {}
        penalty_severity = "DISBANDED"
        health_penalty = 1.0  # 100% loss
    elif hours_starving >= 8:
        penalty_severity = "CRITICAL"
        health_penalty = 0.5  # 50% loss
        # Apply penalty: remove 50% of units
        for unit_tier in military:
            military[unit_tier] = max(1, int(military[unit_tier] * 0.5))
    elif hours_starving >= 4:
        penalty_severity = "SEVERE"
        health_penalty = 0.2
        # Apply penalty: remove 20% of units
        for unit_tier in military:
            military[unit_tier] = max(1, int(military[unit_tier] * 0.8))
    elif hours_starving >= 1:
        penalty_severity = "WARNING"
        health_penalty = 0.05
    
    if health_penalty > 0:
        user["military"] = military
        user["last_starvation_penalty"] = {
            "severity": penalty_severity,
            "units_lost": health_penalty,
            "timestamp": datetime.now().isoformat(),
        }
        db.save_user(player_id, user)
    
    return {"ok": True, "starving": hours_starving > 0, "severity": penalty_severity, "hours": hours_starving}


# ============= DEBUG COMMANDS =============

def get_full_status(player_id: str) -> dict:
    """Get complete player state (for debugging)"""
    user = db.get_user(player_id)
    if not user:
        return None
    
    training_queue = user.get("training_queue", [])
    construction_queue = user.get("construction_queue", [])
    military = user.get("military", {})
    buildings = user.get("base_buildings", {})
    
    return {
        "player_id": player_id,
        "name": user.get("name"),
        "silver": user.get("silver", 0),
        "food": user.get("food", 0),
        "xp": user.get("xp", 0),
        "military": military,
        "buildings": buildings,
        "training_queue": training_queue,
        "construction_queue": construction_queue,
        "starvation_start": user.get("starvation_start"),
    }


def add_test_resources(player_id: str, silver: int = 5000, food: int = 2000, xp: int = 1000):
    """Add resources for testing"""
    user = db.get_user(player_id)
    if not user:
        return False
    
    user["silver"] = user.get("silver", 0) + silver
    user["food"] = user.get("food", 0) + food
    user["xp"] = user.get("xp", 0) + xp
    
    db.save_user(player_id, user)
    return True


if __name__ == "__main__":
    print("Game Engine Module - Autonomous game systems")
    print("- Training queue")
    print("- Construction queue")
    print("- Food production/consumption")
    print("- Starvation penalties")
    print("- Debug utilities")
