"""
Save System - Wrapper for Game State Management
================================================
This module provides game save/load/reset functionality.
It wraps game_state.py to provide the interface expected by main.py.
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, Tuple, List
from game_state import (
    save_game_state,
    load_game_state,
    restore_to_checkpoint,
    reset_player_progress,
    BACKUP_DIR,
)

# ═══════════════════════════════════════════════════════════════════════════
#  PUBLIC API - Aliases and wrappers for game_state functions
# ═══════════════════════════════════════════════════════════════════════════

def save_game(user_id: str, user_data: dict, reason: str = "manual", slot: int = None) -> Tuple[bool, str]:
    """
    Save complete game state for a player.
    
    Args:
        user_id: Player's Telegram user ID
        user_data: Complete user profile data
        reason: Why state is being saved (for logging)
        slot: Optional save slot (1-5) for manual saves
    
    Returns:
        (success: bool, message: str)
    """
    # If slot is provided, use it as the reason
    if slot is not None:
        reason = f"slot_{slot}"
    
    success, msg = save_game_state(user_id, user_data, reason)
    
    # Format message
    if slot:
        return (success, f"Game saved to slot {slot}" if success else f"Failed to save to slot {slot}: {msg}")
    else:
        return (success, msg)

def load_game(user_id_or_dict, slot: int = None) -> Tuple[bool, dict, str]:
    """
    Load game state for a player.
    Can load most recent backup or specific slot.
    
    Args:
        user_id_or_dict: Player's Telegram user ID (string) or user dict
        slot: Optional save slot to load from (1-5)
    
    Returns:
        (success: bool, state: dict, message: str)
    """
    # Handle both user_id string and user dict
    if isinstance(user_id_or_dict, dict):
        # Prioritize 'user_id' (Telegram ID) over 'id' (database row ID)
        user_id = str(user_id_or_dict.get('user_id', user_id_or_dict.get('id', '')))
    else:
        user_id = str(user_id_or_dict)
    
    success, state, msg = load_game_state(user_id, slot=slot)
    
    # Format message
    if slot and success:
        return (success, state, f"Game loaded from slot {slot}")
    else:
        return (success, state, msg)

def reset_game(user_id_or_dict, reset_level: str = "hard", slot: int = None) -> Tuple[bool, dict, str]:
    """
    Reset player progress to a specific level.
    
    Args:
        user_id_or_dict: Player's Telegram user ID (string) or user dict
        reset_level: "soft", "hard", or "weekly"
        slot: Optional save slot parameter (for compatibility)
    
    Returns:
        (success: bool, new_state: dict, message: str)
    """
    # Handle both user_id string and user dict
    if isinstance(user_id_or_dict, dict):
        # Prioritize 'user_id' (Telegram ID) over 'id' (database row ID)
        user_id = str(user_id_or_dict.get('user_id', user_id_or_dict.get('id', '')))
    else:
        user_id = str(user_id_or_dict)
    
    return reset_player_progress(user_id, reset_level)

def restore_game(user_id_or_dict, checkpoint_name: str = "") -> Tuple[bool, dict, str]:
    """
    Restore to a specific checkpoint or most recent backup.
    
    Args:
        user_id_or_dict: Player's Telegram user ID (string) or user dict
        checkpoint_name: Specific checkpoint to restore to (optional)
    
    Returns:
        (success: bool, state: dict, message: str)
    """
    # Handle both user_id string and user dict
    if isinstance(user_id_or_dict, dict):
        # Prioritize 'user_id' (Telegram ID) over 'id' (database row ID)
        user_id = str(user_id_or_dict.get('user_id', user_id_or_dict.get('id', '')))
    else:
        user_id = str(user_id_or_dict)
    
    return restore_to_checkpoint(user_id, checkpoint_name)

def list_saves(user_id: str) -> List[str]:
    """
    List all available backups for a player.
    
    Args:
        user_id: Player's Telegram user ID
    
    Returns:
        List of backup file paths
    """
    if not os.path.exists(BACKUP_DIR):
        return []
    
    saves = []
    for filename in os.listdir(BACKUP_DIR):
        if filename.startswith(f"user_{user_id}_") and filename.endswith(".json"):
            saves.append(os.path.join(BACKUP_DIR, filename))
    
    return sorted(saves, reverse=True)  # Most recent first

def list_checkpoints(user_id: str) -> List[Dict[str, Any]]:
    """
    List all checkpoints for a player with metadata.
    
    Args:
        user_id: Player's Telegram user ID
    
    Returns:
        List of checkpoint info dicts
    """
    saves = list_saves(user_id)
    checkpoints = []
    
    for save_file in saves:
        try:
            filename = os.path.basename(save_file)
            # Parse filename: user_{id}_{YYYY-MM-DD}_{HH-MM-SS}_{reason}.json
            filename_no_ext = filename.replace(".json", "")
            
            # Strip the prefix: user_{user_id}_
            prefix = f"user_{user_id}_"
            if not filename_no_ext.startswith(prefix):
                continue
            
            rest = filename_no_ext[len(prefix):]
            
            # rest is now: YYYY-MM-DD_HH-MM-SS_reason
            # Split on underscore with maxsplit=2 to separate date, time, and reason
            parts = rest.split("_", 2)
            
            if len(parts) >= 3:
                # parts[0] = YYYY-MM-DD
                # parts[1] = HH-MM-SS
                # parts[2] = reason (may contain underscores like "slot_1")
                timestamp = f"{parts[0]}_{parts[1]}"
                reason = parts[2]
                
                checkpoint_info = {
                    "file": save_file,
                    "reason": reason,
                    "timestamp": timestamp,
                    "file_size": os.path.getsize(save_file)
                }
                checkpoints.append(checkpoint_info)
        except Exception as e:
            print(f"[ERROR] Failed to parse checkpoint {save_file}: {e}")
    
    return checkpoints

def format_reset_status(user_id: str, reset_level: str, success: bool, message: str) -> str:
    """
    Format a reset operation status message for display.
    
    Args:
        user_id: Player's Telegram user ID
        reset_level: Reset level used
        success: Whether reset succeeded
        message: Status message from reset operation
    
    Returns:
        Formatted status string
    """
    if success:
        emoji = "✅"
        level_name = {
            "soft": "Battle Stats",
            "hard": "Complete",
            "weekly": "Weekly Stats"
        }.get(reset_level, reset_level)
        return f"{emoji} *Reset Successful*\n*Type:* {level_name}\n*Details:* {message}"
    else:
        return f"❌ *Reset Failed*\n*Reason:* {message}"

def format_checkpoint_display(checkpoint: Dict[str, Any]) -> str:
    """
    Format a checkpoint info for display in chat.
    
    Args:
        checkpoint: Checkpoint info dict from list_checkpoints()
    
    Returns:
        Formatted checkpoint display string
    """
    reason = checkpoint.get("reason", "unknown")
    timestamp = checkpoint.get("timestamp", "unknown")
    file_size = checkpoint.get("file_size", 0)
    
    # Convert bytes to KB
    size_kb = file_size / 1024
    
    return f"💾 `{reason}` - {timestamp} ({size_kb:.1f} KB)"

# ═══════════════════════════════════════════════════════════════════════════
#  QUICK SAVE/LOAD HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def quick_save(user_id: str, user_data: dict) -> bool:
    """Quick save without reason tracking."""
    success, msg = save_game(user_id, user_data, "quick_save")
    return success

def quick_load(user_id: str) -> dict:
    """Quick load, returns empty dict if failed."""
    success, state, msg = load_game(user_id)
    return state if success else {}

def has_saves(user_id: str) -> bool:
    """Check if player has any backups."""
    return len(list_saves(user_id)) > 0

# ═══════════════════════════════════════════════════════════════════════════
#  DEBUG UTILITIES
# ═══════════════════════════════════════════════════════════════════════════

def print_save_info(user_id: str):
    """Print all save information for a player (for debugging)."""
    saves = list_saves(user_id)
    checkpoints = list_checkpoints(user_id)
    
    print(f"\n[SAVE_INFO] Player {user_id}")
    print(f"[SAVE_INFO] Total saves: {len(saves)}")
    
    for cp in checkpoints:
        print(f"  {format_checkpoint_display(cp)}")
    
    if not saves:
        print(f"  (no backups found)")
    
    print()

if __name__ == "__main__":
    # Test the module
    print("[TEST] Save system loaded successfully")
    print(f"[TEST] Backup directory: {BACKUP_DIR}")
