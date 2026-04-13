# -*- coding: utf-8 -*-
"""
save_system.py — Save/Load/Reset Game Progression
==================================================
Players can save their current game, load from previous saves, or reset with limits.

Features:
- 5 save slots per player
- Full game state snapshots (Level, XP, Silver, Buildings, Military, Resources, etc.)
- Keep prestige tier and unlocked weapons on reset
- Once-per-day reset limit
- Automatic save management (cleanup of old saves beyond 5 slots)
"""

from typing import Dict, List, Tuple
from datetime import datetime, timedelta
import json

# ═══════════════════════════════════════════════════════════════════════════
#  SAVE STRUCTURE
# ═══════════════════════════════════════════════════════════════════════════

SAVE_FIELDS = [
    'level', 'xp', 'silver',  # Core progression
    'buildings', 'military', 'inventory',  # Game state
    'base_resources', 'buffs',  # Resources and buffs
    'all_time_points', 'weekly_points',  # Points
    'total_words', 'weapons',  # Stats and unlocked weapons
]

RESET_KEEP_FIELDS = [
    'prestige',  # Keep prestige tier
    'username', 'base_name',  # Identity
]

# ═══════════════════════════════════════════════════════════════════════════
#  SAVE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

def create_save_snapshot(user: Dict) -> Dict:
    """Create a snapshot of current game state."""
    snapshot = {
        'timestamp': datetime.utcnow().isoformat(),
        'level': user.get('level', 1),
        'xp': user.get('xp', 0),
        'silver': user.get('silver', 0),
        'buildings': user.get('buildings', {}),
        'military': user.get('military', {}),
        'inventory': user.get('inventory', []),
        'base_resources': user.get('base_resources', {}),
        'buffs': user.get('buffs', {}),
        'all_time_points': user.get('all_time_points', 0),
        'weekly_points': user.get('weekly_points', 0),
        'total_words': user.get('total_words', 0),
        'weapons': user.get('weapons', {}),
    }
    return snapshot


def save_game(user_id: str, user: Dict, slot: int = 1) -> Tuple[bool, str]:
    """
    Save current game state to a slot (1-5).
    Returns (success, message)
    """
    if not 1 <= slot <= 5:
        return False, "Invalid save slot! Use slots 1-5."
    
    # Get or initialize saves
    saves = user.get('game_saves', {})
    if not isinstance(saves, dict):
        saves = {}
    
    # Create snapshot
    snapshot = create_save_snapshot(user)
    snapshot['slot'] = slot
    
    # Store in slot
    saves[str(slot)] = snapshot
    user['game_saves'] = saves
    
    # Format timestamp for display
    ts = datetime.fromisoformat(snapshot['timestamp'])
    date_str = ts.strftime('%b %d %H:%M')
    
    message = (
        f"✅ GAME SAVED\n"
        f"Slot {slot}\n"
        f"{date_str}\n"
        f"Level {snapshot['level']} | Silver {snapshot['silver']}"
    )
    
    return True, message


def load_game(user: Dict, slot: int = 1) -> Tuple[bool, str, Dict]:
    """
    Load game state from a save slot.
    Returns (success, message, restored_user_data)
    """
    if not 1 <= slot <= 5:
        return False, "Invalid save slot! Use slots 1-5.", user
    
    saves = user.get('game_saves', {})
    slot_key = str(slot)
    
    if slot_key not in saves:
        return False, f"❌ No save in slot {slot}.", user
    
    snapshot = saves[slot_key]
    
    # Preserve these fields from current user
    preserved = {k: user.get(k) for k in RESET_KEEP_FIELDS if k in user}
    
    # Restore from snapshot
    for field in SAVE_FIELDS:
        user[field] = snapshot.get(field, user.get(field))
    
    # Re-apply preserved fields
    user.update(preserved)
    
    # Format timestamp for display
    ts = datetime.fromisoformat(snapshot['timestamp'])
    date_str = ts.strftime('%b %d %H:%M')
    
    message = (
        f"✅ GAME LOADED\n"
        f"Slot {slot}\n"
        f"{date_str}\n"
        f"Level {snapshot['level']} | Silver {snapshot['silver']}"
    )
    
    return True, message, user


def reset_game(user: Dict) -> Tuple[bool, str, Dict]:
    """
    Reset game to level 1, clear all progress except prestige/weapons.
    Returns (success, message, reset_user_data)
    """
    # Check daily reset limit
    last_reset = user.get('last_reset_date')
    today = datetime.utcnow().strftime('%Y-%m-%d')
    
    if last_reset and last_reset >= today:
        return False, "❌ Already reset today! Try again tomorrow.", user
    
    # Preserve important fields
    preserved = {
        'user_id': user.get('user_id'),
        'username': user.get('username'),
        'base_name': user.get('base_name'),
        'prestige': user.get('prestige', 0),
        'weapons': user.get('weapons', {}),  # Keep unlocked weapons
        'game_saves': user.get('game_saves', {}),  # Keep saves
    }
    
    # Reset core progression
    reset_user = {
        **preserved,
        'level': 1,
        'xp': 0,
        'silver': 0,
        'buildings': {},
        'military': {},
        'inventory': [],
        'unclaimed_items': [],
        'base_resources': {
            'resources': {'wood': 0, 'bronze': 0, 'iron': 0, 'diamond': 0, 'relics': 0},
            'food': 0,
            'current_streak': 0
        },
        'buffs': {},
        'all_time_points': 0,
        'weekly_points': 0,
        'total_words': 0,
        'last_reset_date': today,
    }
    
    # Copy over other fields not explicitly reset
    for k, v in user.items():
        if k not in reset_user and k not in ['level', 'xp', 'silver', 'buildings', 'military', 'inventory', 'unclaimed_items', 'base_resources', 'buffs', 'all_time_points', 'weekly_points', 'total_words']:
            reset_user[k] = v
    
    message = (
        f"✅ GAME RESET\n"
        f"Level reset to 1\n"
        f"Silver and XP cleared\n"
        f"Buildings and inventory cleared\n\n"
        f"PRESERVED:\n"
        f"Prestige Tier {reset_user.get('prestige', 0)}\n"
        f"All weapons\n"
        f"All saves"
    )
    
    return True, message, reset_user


def list_saves(user: Dict) -> str:
    """Show all available save slots."""
    saves = user.get('game_saves', {})
    
    if not saves:
        return "❌ No saves yet. Use /save 1 to save your first game!"
    
    msg = "💾 YOUR SAVED GAMES\n\n"
    
    for slot in range(1, 6):
        slot_key = str(slot)
        if slot_key in saves:
            save = saves[slot_key]
            ts = datetime.fromisoformat(save['timestamp'])
            date_str = ts.strftime('%b %d %H:%M')
            level = save.get('level', '?')
            silver = save.get('silver', 0)
            
            msg += (
                f"📍 Slot {slot}\n"
                f"   📅 {date_str}\n"
                f"   📊 Level {level} | 💰 {silver}\n\n"
            )
        else:
            msg += f"📍 Slot {slot} — Empty\n\n"
    
    msg += "Use /load [slot] to restore a saved game.\n"
    msg += "Use /save [slot] to save to a slot."
    
    return msg


def format_reset_status(user: Dict) -> str:
    """Show reset status and when player can reset again."""
    last_reset = user.get('last_reset_date')
    today = datetime.utcnow().strftime('%Y-%m-%d')
    
    msg = "🔄 RESET & RESTART\n\n"
    
    if last_reset and last_reset >= today:
        msg += "⏰ Already reset today!\n"
        msg += "Try again tomorrow.\n\n"
        msg += "KEPT ON RESET:\n"
        msg += f"👑 Prestige Tier {user.get('prestige', 0)}\n"
        msg += "🎯 Unlocked weapons\n"
        msg += "💾 All save slots\n\n"
        msg += "You can reset once per day."
    else:
        msg += "✅ Ready to reset!\n\n"
        msg += "WARNING: This will:\n"
        msg += "• Reset level to 1\n"
        msg += "• Clear all XP\n"
        msg += "• Clear silver\n"
        msg += "• Remove all buildings, military, inventory\n\n"
        msg += "YOU'LL KEEP:\n"
        msg += f"👑 Prestige Tier {user.get('prestige', 0)}\n"
        msg += "🎯 All unlocked weapons\n"
        msg += "💾 All save slots\n\n"
        msg += "Type /reset confirm to reset everything."
    
    return msg
