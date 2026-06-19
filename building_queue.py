"""
building_queue.py — Building Queue & Timer System
==================================================
Manages building construction timers, prerequisites, and progress.
Buildings take time to build and show progress on user interface.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple
import json

# ═══════════════════════════════════════════════════════════════════════════
#  BUILDING PREREQUISITES
# ═══════════════════════════════════════════════════════════════════════════

BUILDING_PREREQUISITES = {
    # Base HQ has no prerequisites
    "base_hq": [],
    
    # Military buildings
    "training_grounds": ["base_hq"],
    "cemetery": ["training_grounds"],
    "barracks": ["training_grounds"],
    "armory": ["barracks"],
    "war_room": ["armory"],
    "infirmary": ["barracks"],
    
    # Resource buildings
    "storage": ["base_hq"],
    "mine": ["base_hq"],
    "farm": ["base_hq"],
    
    # Defence buildings
    "trap_factory": ["storage"],
    "walls": ["base_hq"],
}

BUILD_TIMES = {
    # Base HQ - 10 seconds for testing, change to hours for production
    "base_hq": 5 * 60,  # 5 minutes base
    
    # Military - 5 minutes each
    "training_grounds": 5 * 60,
    "cemetery": 5 * 60,
    "barracks": 5 * 60,
    "armory": 5 * 60,
    "war_room": 5 * 60,
    "infirmary": 5 * 60,
    
    # Resources - 5 minutes each
    "storage": 5 * 60,
    "mine": 5 * 60,
    "farm": 5 * 60,
    
    # Defence - 5 minutes each
    "trap_factory": 5 * 60,
    "walls": 5 * 60,
}

# ═══════════════════════════════════════════════════════════════════════════
#  BUILD QUEUE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def can_build_prerequisite(building_id: str, current_buildings: dict) -> Tuple[bool, str]:
    """
    Check if all prerequisites for a building are met.
    Returns (can_build, error_message)
    """
    prerequisites = BUILDING_PREREQUISITES.get(building_id, [])
    
    if not prerequisites:
        return True, "OK"
    
    for prereq in prerequisites:
        if prereq == "base_hq":
            # Base HQ must exist (level 1+)
            if current_buildings.get("base_hq", 1) < 1:
                return False, f"Requires Base HQ to be built"
        else:
            # Other buildings must be at same level or built
            if current_buildings.get(prereq, 0) < 1:
                return False, f"Requires {prereq.replace('_', ' ').title()} to be built first"
    
    return True, "OK"


def get_base_hq_level(user: dict) -> int:
    """Get the Base HQ level (upgraded by building all structures to that level)."""
    return user.get("base_hq_level", 1)


def check_base_hq_upgrade(user: dict) -> bool:
    """
    Check if Base HQ can be upgraded.
    Base HQ level = minimum level of ALL buildings.
    Returns True if all buildings are at next level.
    """
    current_buildings = user.get("buildings", {})
    # Defensive: handle case where buildings is stored as JSON string
    if isinstance(current_buildings, str):
        try:
            current_buildings = json.loads(current_buildings)
        except:
            current_buildings = {}
    
    if not current_buildings:
        return False
    
    # Get current HQ level
    hq_level = get_base_hq_level(user)
    
    # Check if all buildings are at least hq_level + 1
    if isinstance(current_buildings, dict):
        for building_id, level in current_buildings.items():
            if level <= hq_level:
                return False
    
    return True


def start_building(building_id: str, current_level: int, user: dict) -> dict:
    """
    Start building a structure.
    Returns updated user dict with building_queue entry.
    """
    # Ensure buildings dict exists and is a dict (not JSON string)
    if "buildings" not in user:
        user["buildings"] = {}
    elif isinstance(user["buildings"], str):
        try:
            user["buildings"] = json.loads(user["buildings"])
        except:
            user["buildings"] = {}
    
    # Ensure building_queue dict exists and is a dict (not JSON string)
    if "building_queue" not in user:
        user["building_queue"] = {}
    elif isinstance(user["building_queue"], str):
        try:
            user["building_queue"] = json.loads(user["building_queue"])
        except:
            user["building_queue"] = {}
    
    build_time_secs = BUILD_TIMES.get(building_id, 300)  # Default 5 min
    completion_time = (datetime.utcnow() + timedelta(seconds=build_time_secs)).isoformat()
    user["building_queue"][building_id] = {
        "target_level": current_level + 1,
        "completion_time": completion_time,
        "started_at": datetime.utcnow().isoformat(),
        "build_time_secs": build_time_secs,
    }
    
    return user


def get_building_progress(user: dict, building_id: str) -> Optional[dict]:
    """
    Get the progress of a building currently being built.
    Returns dict with progress info or None if not building.
    """
    queue = user.get("building_queue", {})
    if building_id not in queue:
        return None
    
    build_info = queue[building_id]
    completion_time_str = build_info["completion_time"]
    completion_time = datetime.fromisoformat(completion_time_str)
    now = datetime.utcnow()
    
    if now >= completion_time:
        return None  # Already complete
    
    total_secs = build_info["build_time_secs"]
    elapsed = (now - datetime.fromisoformat(build_info["started_at"])).total_seconds()
    remaining = total_secs - elapsed
    progress_pct = (elapsed / total_secs) * 100 if total_secs > 0 else 0
    
    return {
        "building_id": building_id,
        "target_level": build_info["target_level"],
        "total_time": total_secs,
        "build_time_secs": total_secs,  # Backward compatibility
        "elapsed_time": elapsed,
        "remaining_time": remaining,
        "progress_pct": progress_pct,
        "completion_time": completion_time,
    }


def get_all_building_progress(user: dict) -> list:
    """Get all buildings currently being constructed."""
    queue = user.get("building_queue", {})
    progress_list = []
    
    for building_id in queue:
        prog = get_building_progress(user, building_id)
        if prog:
            progress_list.append(prog)
    
    return progress_list


def complete_building(user: dict, building_id: str) -> dict:
    """
    Complete a building construction.
    Returns updated user dict, or unchanged user if not building.
    """
    # Ensure buildings dict is a dict (not JSON string)
    buildings = user.get("buildings", {})
    if isinstance(buildings, str):
        try:
            buildings = json.loads(buildings)
        except:
            buildings = {}
    user["buildings"] = buildings
    
    # Ensure building_queue dict is a dict (not JSON string)
    queue = user.get("building_queue", {})
    if isinstance(queue, str):
        try:
            queue = json.loads(queue)
        except:
            queue = {}
    user["building_queue"] = queue
    
    if building_id not in queue:
        return user
    
    build_info = queue.get(building_id, {})
    target_level = build_info.get("target_level", 1)
    
    # Update buildings
    buildings[building_id] = target_level
    
    # Remove from queue
    if building_id in queue:
        del queue[building_id]
    
    # Check if Base HQ should be upgraded
    # Base HQ level = minimum level of all buildings
    if check_base_hq_upgrade(user):
        current_hq_level = get_base_hq_level(user)
        user["base_hq_level"] = current_hq_level + 1
    
    return user


def format_build_progress_bar(progress: dict) -> str:
    """Format a nice progress bar for building display."""
    pct = progress.get("progress_pct", 0)
    remaining = progress.get("remaining_time", 0)
    
    # Convert seconds to HH:MM:SS
    hours = int(remaining // 3600)
    minutes = int((remaining % 3600) // 60)
    seconds = int(remaining % 60)
    
    if hours > 0:
        time_str = f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        time_str = f"{minutes}m {seconds}s"
    else:
        time_str = f"{seconds}s"
    
    # Build the bar
    bar_length = 20
    filled = int(bar_length * pct / 100)
    bar = "█" * filled + "░" * (bar_length - filled)
    
    return f"[{bar}] {pct:.1f}% — {time_str} remaining"


def format_building_queue_display(user: dict) -> str:
    """Format all building timers for display on main menu."""
    progress_list = get_all_building_progress(user)
    
    if not progress_list:
        return ""
    
    msg = "\n🏗️ *BUILDINGS IN PROGRESS*\n"
    msg += "━━━━━━━━━━━━━━━━━━\n"
    
    for prog in progress_list:
        from build_system import BUILDING_TYPES
        building_id = prog.get("building_id", "unknown")
        target_level = prog.get("target_level", 1)
        building = BUILDING_TYPES.get(building_id, {})
        building_name = building.get("name", building_id.replace("_", " ").title())
        
        msg += f"{building_name} → Lv{target_level}\n"
        msg += f"{format_build_progress_bar(prog)}\n\n"
    
    msg += "━━━━━━━━━━━━━━━━━━━\n"
    return msg


def format_completed_buildings(user: dict) -> str:
    """Format completed buildings with their levels for display."""
    buildings = user.get("buildings", {})
    
    # Defensive: handle case where buildings is stored as JSON string
    if isinstance(buildings, str):
        try:
            import json
            buildings = json.loads(buildings)
        except:
            buildings = {}
    
    if not buildings:
        return ""
    
    from build_system import BUILDING_TYPES
    
    msg = "🏗️ *COMPLETED BUILDINGS:*\n"
    for building_id, level in sorted(buildings.items()):
        building = BUILDING_TYPES.get(building_id, {})
        building_name = building.get("name", building_id.replace("_", " ").title())
        msg += f"  • {building_name}: **Level {level}**\n"
    
    return msg
