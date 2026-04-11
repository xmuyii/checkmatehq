"""
training_system.py — Military training with timers and progress bars

Mechanics:
  - !train [unit] [amount] — Queue units for training
  - Training takes time (configurable per unit)
  - Progress bar shows remaining time
  - Troops available once timer completes
"""

import json
from datetime import datetime, timedelta
from supabase_db import get_user, save_user

# Training times (in seconds)
TRAINING_TIMES = {
    "footmen": 30,      # 30 seconds for testing/demo
    "archers": 45,
    "lancers": 60,
    "castellans": 90,
    "pawns": 20,
}

# Unit costs
UNIT_COSTS = {
    "footmen": {"wood": 5},
    "archers": {"wood": 8, "bronze": 2},
    "lancers": {"bronze": 10, "iron": 3},
    "castellans": {"iron": 15, "diamond": 2},
    "pawns": {"wood": 2},
}

UNIT_NAMES = {
    "footmen": "👹 Footmen",
    "archers": "🏹 Archers",
    "lancers": "🗡️ Lancers",
    "castellans": "🏰 Castellans",
    "pawns": "👹 Pawns",
}


def add_to_training_queue(user_id: str, unit_type: str, amount: int) -> tuple[bool, str]:
    """
    Add units to training queue.
    Returns (success, message)
    """
    user = get_user(user_id)
    if not user:
        return False, "User not found"
    
    # Validate unit type
    if unit_type not in UNIT_COSTS:
        return False, f"Unknown unit type: {unit_type}"
    
    if amount <= 0:
        return False, "Amount must be > 0"
    
    # Check resources
    cost = UNIT_COSTS[unit_type]
    base_res = user.get("base_resources", {})
    resources = base_res.get("resources", {})
    
    total_cost = {res: amount * cost_amt for res, cost_amt in cost.items()}
    
    for res, needed in total_cost.items():
        have = resources.get(res, 0)
        if have < needed:
            return False, f"Need {needed} {res}, have {have}"
    
    # Deduct resources
    for res, needed in total_cost.items():
        resources[res] = resources.get(res, 0) - needed
    
    # Add to training queue
    queue = user.get("training_queue", [])
    
    # Calculate completion time
    training_time = TRAINING_TIMES.get(unit_type, 30)
    completes_at = (datetime.utcnow() + timedelta(seconds=training_time * amount)).isoformat()
    
    queue_item = {
        "unit_type": unit_type,
        "amount": amount,
        "started_at": datetime.utcnow().isoformat(),
        "completes_at": completes_at,
    }
    queue.append(queue_item)
    
    user["training_queue"] = queue
    base_res["resources"] = resources
    user["base_resources"] = base_res
    save_user(user_id, user)
    
    return True, f"✅ Queued {amount}x {UNIT_NAMES.get(unit_type, unit_type)}\nCompletes in {training_time * amount}s"


def get_training_status(user_id: str) -> dict:
    """Get current training queue status."""
    user = get_user(user_id)
    if not user:
        return {"queue": []}
    
    queue = user.get("training_queue", [])
    now = datetime.utcnow()
    
    # Process completed trainings
    completed_items = []
    remaining_queue = []
    
    for item in queue:
        try:
            completes = datetime.fromisoformat(item["completes_at"])
            if now >= completes:
                completed_items.append(item)
            else:
                remaining_queue.append(item)
        except:
            continue
    
    # Apply completed trainings to military
    if completed_items:
        military = user.get("military", {})
        for item in completed_items:
            unit_type = item["unit_type"]
            military[unit_type] = military.get(unit_type, 0) + item["amount"]
        user["military"] = military
        user["training_queue"] = remaining_queue
        save_user(user_id, user)
    
    return {
        "queue": remaining_queue,
        "completed": len(completed_items),
    }


def format_training_status(user_id: str) -> str:
    """Format training queue as readable message with progress bars."""
    status = get_training_status(user_id)
    
    if not status["queue"]:
        return "✅ No troops in training queue"
    
    lines = ["⚔️ *TRAINING QUEUE*\n"]
    
    now = datetime.utcnow()
    
    for idx, item in enumerate(status["queue"], 1):
        unit_type = item["unit_type"]
        amount = item["amount"]
        
        try:
            started = datetime.fromisoformat(item["started_at"])
            completes = datetime.fromisoformat(item["completes_at"])
        except:
            continue
        
        total_time = (completes - started).total_seconds()
        elapsed = (now - started).total_seconds()
        remaining = max(0, (completes - now).total_seconds())
        
        progress = min(100, int((elapsed / total_time) * 100)) if total_time > 0 else 0
        
        # ASCII progress bar
        bar_length = 10
        filled = int((progress / 100) * bar_length)
        bar = "█" * filled + "░" * (bar_length - filled)
        
        lines.append(f"{idx}. {amount}x {UNIT_NAMES.get(unit_type, unit_type)}")
        lines.append(f"   [{bar}] {progress}% — {int(remaining)}s remaining\n")
    
    if status["completed"] > 0:
        lines.append(f"\n✅ {status['completed']} training(s) completed!")
    
    return "\n".join(lines)


def complete_all_trainings(user_id: str) -> dict:
    """Complete all trainings (force, for testing)."""
    user = get_user(user_id)
    if not user:
        return {"success": False}
    
    queue = user.get("training_queue", [])
    military = user.get("military", {})
    
    for item in queue:
        unit_type = item["unit_type"]
        amount = item["amount"]
        military[unit_type] = military.get(unit_type, 0) + amount
    
    user["military"] = military
    user["training_queue"] = []
    save_user(user_id, user)
    
    return {
        "success": True,
        "units_trained": sum(item["amount"] for item in queue),
    }
