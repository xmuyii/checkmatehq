"""
Game State Management: Save, Load, Restore, Reset
==================================================
Handles persistence of player game state with JSON backup fallback.
"""

import json
import pickle
import os
from datetime import datetime
from typing import Dict, Any, Tuple

# ═══════════════════════════════════════════════════════════════════════════
#  GAME STATE BACKUP & RESTORATION
# ═══════════════════════════════════════════════════════════════════════════

BACKUP_DIR = "game_backups"
STATE_FILE = "game_state.json"
TIMESTAMP_FORMAT = "%Y-%m-%d_%H-%M-%S"

def ensure_backup_dir():
    """Create backup directory if it doesn't exist."""
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
        print(f"[BACKUP] Created directory: {BACKUP_DIR}")

def save_game_state(user_id: str, user_data: dict, reason: str = "manual") -> Tuple[bool, str]:
    """
    Save complete game state for a player.
    Creates timestamped backup for restore/rollback.
    
    Args:
        user_id: Player's Telegram user ID
        user_data: Complete user profile data
        reason: Why state is being saved (for logging)
    
    Returns:
        (success: bool, message: str)
    """
    try:
        ensure_backup_dir()
        
        # Create timestamped backup
        timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
        backup_file = os.path.join(
            BACKUP_DIR, 
            f"user_{user_id}_{timestamp}_{reason}.json"
        )
        
        backup_data = {
            "timestamp": timestamp,
            "user_id": user_id,
            "reason": reason,
            "state": user_data
        }
        
        with open(backup_file, 'w') as f:
            json.dump(backup_data, f, indent=2, default=str)
        
        print(f"[SAVE] User {user_id}: State saved to {backup_file}")
        return True, f"✅ State saved ({reason})"
    
    except Exception as e:
        print(f"[ERROR] Failed to save state for {user_id}: {e}")
        return False, f"❌ Save failed: {str(e)}"


def load_game_state(user_id: str, slot: int = None) -> Tuple[bool, dict, str]:
    """
    Load game state for a player.
    Can load most recent backup or specific slot.
    
    Args:
        user_id: Player's Telegram user ID
        slot: Optional slot number (1-5) to load from
    
    Returns:
        (success: bool, state: dict, message: str)
    """
    try:
        ensure_backup_dir()
        
        # Find backups for this user
        backups = []
        for file in os.listdir(BACKUP_DIR):
            if file.startswith(f"user_{user_id}_"):
                path = os.path.join(BACKUP_DIR, file)
                mtime = os.path.getmtime(path)
                backups.append((path, mtime, file))
        
        if not backups:
            return False, {}, "No saved state found"
        
        # Filter by slot if specified
        if slot is not None:
            slot_pattern = f"_slot_{slot}.json"
            slot_backups = [b for b in backups if b[2].endswith(slot_pattern)]
            if not slot_backups:
                return False, {}, f"No save found in slot {slot}"
            backups = slot_backups
        
        # Get most recent
        latest_file, _, filename = sorted(backups, key=lambda x: x[1], reverse=True)[0]
        
        with open(latest_file, 'r') as f:
            backup_data = json.load(f)
        
        state = backup_data.get("state", {})
        reason = backup_data.get("reason", "unknown")
        
        print(f"[LOAD] User {user_id}: Loaded state from {latest_file} (reason: {reason})")
        return True, state, f"Restored from {reason}"
    
    except Exception as e:
        print(f"[ERROR] Failed to load state for {user_id}: {e}")
        return False, {}, f"Load failed: {str(e)}"


def restore_to_checkpoint(user_id: str, checkpoint_name: str = None) -> Tuple[bool, dict, str]:
    """
    Restore player to a specific checkpoint/reason.
    
    Args:
        user_id: Player ID
        checkpoint_name: Specific save reason to restore (e.g., "level_up", "weekly_reset")
                        If None, restores to most recent
    
    Returns:
        (success: bool, state: dict, message: str)
    """
    try:
        ensure_backup_dir()
        
        backups = []
        for file in os.listdir(BACKUP_DIR):
            if file.startswith(f"user_{user_id}_"):
                path = os.path.join(BACKUP_DIR, file)
                mtime = os.path.getmtime(path)
                
                # If checkpoint specified, filter by it
                if checkpoint_name and checkpoint_name not in file:
                    continue
                
                backups.append((path, mtime))
        
        if not backups:
            return False, {}, f"No checkpoint found for '{checkpoint_name}'"
        
        # Get most recent matching backup
        latest_file, _ = sorted(backups, key=lambda x: x[1], reverse=True)[0]
        
        with open(latest_file, 'r') as f:
            backup_data = json.load(f)
        
        state = backup_data.get("state", {})
        timestamp = backup_data.get("timestamp", "")
        reason = backup_data.get("reason", "unknown")
        
        print(f"[RESTORE] User {user_id}: Restored {reason} from {timestamp}")
        return True, state, f"Restored to {reason} checkpoint ({timestamp})"
    
    except Exception as e:
        print(f"[ERROR] Restore failed for {user_id}: {e}")
        return False, {}, f"Restore failed: {str(e)}"


def reset_player_progress(user_id: str, reset_level: str = "soft") -> Tuple[bool, dict, str]:
    """
    Reset player progress with configurable depth.
    
    Args:
        user_id: Player ID
        reset_level: "soft" (keep base), "hard" (reset everything), "weekly" (weekly reset)
    
    Returns:
        (success: bool, new_state: dict, message: str)
    """
    try:
        from supabase_db import get_user, save_user
        
        user = get_user(user_id)
        if not user:
            return False, {}, "User not found"
        
        # First save current state before reset
        save_game_state(user_id, user, f"pre_reset_{reset_level}")
        
        if reset_level == "soft":
            # Keep base, reset battle stats only
            user["weekly_points"] = 0
            user["wins"] = 0
            user["losses"] = 0
            user["war_points"] = 0
            msg = "🔄 Soft reset: Battle stats cleared, base preserved"
        
        elif reset_level == "hard":
            # Complete reset to new player state
            user["xp"] = 0
            user["level"] = 1
            user["bitcoin"] = 100
            user["weekly_points"] = 0
            user["all_time_points"] = user.get("all_time_points", 0)  # Keep all-time for history
            user["military"] = {"pawn": 5}
            user["wins"] = 0
            user["losses"] = 0
            user["traps"] = {}
            user["unclaimed_items"] = []
            user["inventory"] = []
            user["weapons"] = []
            user["base_resources"] = {
                "resources": {"wood": 20, "bronze": 10, "iron": 0, "diamond": 0, "relics": 0},
                "food": 50,
                "current_streak": 0
            }
            msg = "⚠️ HARD RESET: All progress cleared, starting fresh"
        
        elif reset_level == "weekly":
            # Reset weekly/temporary stats only
            user["weekly_points"] = 0
            user["current_streak"] = 0
            user["buffs"] = {}
            msg = "📅 Weekly reset: Points and buffs cleared"
        
        else:
            return False, {}, f"Unknown reset level: {reset_level}"
        
        # Save reset state
        save_user(user_id, user)
        save_game_state(user_id, user, f"reset_{reset_level}")
        
        print(f"[RESET] User {user_id}: {reset_level} reset executed")
        return True, user, msg
    
    except Exception as e:
        print(f"[ERROR] Reset failed for {user_id}: {e}")
        return False, {}, f"Reset failed: {str(e)}"


def list_checkpoints(user_id: str) -> list:
    """List all available checkpoints/backups for a player."""
    try:
        ensure_backup_dir()
        
        backups = []
        for file in os.listdir(BACKUP_DIR):
            if file.startswith(f"user_{user_id}_"):
                path = os.path.join(BACKUP_DIR, file)
                mtime = os.path.getmtime(path)
                
                # Parse filename
                parts = file.split("_")
                timestamp = "_".join(parts[2:4])  # Y-M-D_H-M-S
                reason = "_".join(parts[5:]).replace(".json", "")
                
                backups.append({
                    "file": file,
                    "timestamp": timestamp,
                    "reason": reason,
                    "mtime": mtime
                })
        
        # Sort by time, newest first
        backups.sort(key=lambda x: x["mtime"], reverse=True)
        return backups
    
    except Exception as e:
        print(f"[ERROR] Failed to list checkpoints: {e}")
        return []


def format_checkpoint_display(checkpoints: list) -> str:
    """Format checkpoint list for display."""
    if not checkpoints:
        return "📂 No backups found"
    
    txt = "📂 *SAVED CHECKPOINTS*\n━━━━━━━━━━━━━━━━━━━\n\n"
    for i, cp in enumerate(checkpoints[:10], 1):  # Show last 10
        txt += f"{i}. `{cp['timestamp']}`\n"
        txt += f"   Reason: *{cp['reason']}*\n"
        txt += f"   File: `{cp['file']}`\n\n"
    
    if len(checkpoints) > 10:
        txt += f"... and {len(checkpoints) - 10} older backups"
    
    return txt


# ═══════════════════════════════════════════════════════════════════════════
# EXPORT FOR USE IN OTHER MODULES
# ═══════════════════════════════════════════════════════════════════════════

__all__ = [
    'save_game_state',
    'load_game_state',
    'restore_to_checkpoint',
    'reset_player_progress',
    'list_checkpoints',
    'format_checkpoint_display',
    'ensure_backup_dir'
]
