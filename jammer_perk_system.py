"""
jammer_perk_system.py
─────────────────────
Jammer Perk System: Scramble words to confuse opponents
Anti-Jammer: Reveal jammed words

MECHANICS:
- Jammer Perk: Scrambles player's words so others can't see them
- Anti-Jammer Perk: Reveals scrambled words (counter perk)
- Perks display above player dashboard
- Perks auto-expire after duration or use limit
- Bot edits messages when perks activate/deactivate
"""

from datetime import datetime, timedelta
from supabase_db import get_user, save_user
import random
import string
import json



# ═══════════════════════════════════════════════════════════════════════════
#  PERK DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════

PERK_DEFINITIONS = {
    "jammer": {
        "name": "⚡ SCRAMBLER",
        "description": "Scrambles your words so others can't see them",
        "icon": "⚡",
        "cost": {"bitcoin": 500},
        "duration_seconds": 300,  # 5 minutes
        "max_uses": None,  # Unlimited uses during duration
        "sticker_id": "CAACAgQAAxkBAAFIWdVp8c9pneMXLRNI96oFHiuXKUCkzAACyBwAArhpiVP99S5kIKefXTsE",  # Jammer sticker
    },
    "anti_jammer": {
        "name": "🔓 UNSCRAMBLER",
        "description": "Reveals scrambled words from opponents",
        "icon": "🔓",
        "cost": {"bitcoin": 800},
        "duration_seconds": 300,  # 5 minutes
        "max_uses": 5,  # Can reveal 5 times
        "sticker_id": "CAACAgQAAxkBAAFIWnVp8dQDmTlMxGLsC7QsCWB2VEF83wAC6xwAAkeokVMeUvcw2Uf57DsE",  # Anti-jammer sticker
    }
}


# ═══════════════════════════════════════════════════════════════════════════
#  SCRAMBLING LOGIC
# ═══════════════════════════════════════════════════════════════════════════

def generate_scramble_pattern(word_length: int) -> str:
    """Generate a consistent scramble pattern for a word."""
    # Use Unicode block characters for variety
    patterns = [
        "░█░█▒█▒░░",  # Default
        "█████████",  # Full block
        "$&%#$@!",    # Symbols
        "▓▒░▒▓░▒░",   # Varied blocks
        "███▓▓░░░",   # Mixed density
    ]
    
    # If word is longer, pad the pattern
    base_pattern = random.choice(patterns)
    if len(base_pattern) < word_length:
        pattern = (base_pattern * ((word_length // len(base_pattern)) + 1))[:word_length]
    else:
        pattern = base_pattern[:word_length]
    
    return pattern


def scramble_word(word: str) -> str:
    """Scramble a word into unreadable characters."""
    return generate_scramble_pattern(len(word))


# ═══════════════════════════════════════════════════════════════════════════
#  PERK ACTIVATION/DEACTIVATION
# ═══════════════════════════════════════════════════════════════════════════

def activate_perk(user_id: str, perk_type: str) -> dict:
    """
    Activate a perk for a player.
    
    Args:
        user_id: Player's Telegram ID
        perk_type: "jammer" or "anti_jammer"
    
    Returns:
        {"ok": bool, "msg": str, "perk_data": dict or None}
    """
    if perk_type not in PERK_DEFINITIONS:
        return {"ok": False, "msg": f"Unknown perk: {perk_type}"}
    
    user = get_user(user_id)
    if not user:
        return {"ok": False, "msg": "User not found"}
    
    perk_def = PERK_DEFINITIONS[perk_type]
    
    # Check cost
    for resource, amount in perk_def["cost"].items():
        if user.get(resource, 0) < amount:
            return {"ok": False, "msg": f"Insufficient {resource}. Need {amount}, have {user.get(resource, 0)}"}
    
    # Deduct cost
    for resource, amount in perk_def["cost"].items():
        user[resource] = user.get(resource, 0) - amount
    
    # Initialize perks dict if needed
    if "active_perks" not in user:
        user["active_perks"] = {}
    
    # Ensure it's a dict (in case of corruption)
    if not isinstance(user["active_perks"], dict):
        user["active_perks"] = {}
    
    # Activate perk
    try:
        expiration = datetime.utcnow() + timedelta(seconds=perk_def["duration_seconds"])
        user["active_perks"][perk_type] = {
            "activated_at": datetime.utcnow().isoformat(),
            "expires_at": expiration.isoformat(),
            "uses_remaining": perk_def["max_uses"],
            "active": True
        }
    except Exception as e:
        return {"ok": False, "msg": f"Error activating perk: {e}"}
    
    save_user(user_id, user)
    
    return {
        "ok": True,
        "msg": f"✅ Activated {perk_def['name']}!",
        "perk_data": user["active_perks"][perk_type]
    }


def deactivate_perk(user_id: str, perk_type: str) -> dict:
    """Deactivate a perk for a player."""
    user = get_user(user_id)
    if not user:
        return {"ok": False, "msg": "User not found"}
    
    if "active_perks" not in user:
        return {"ok": False, "msg": f"No active perks"}
    
    if perk_type not in user["active_perks"]:
        return {"ok": False, "msg": f"{perk_type} is not active"}
    
    user["active_perks"][perk_type]["active"] = False
    save_user(user_id, user)
    
    return {"ok": True, "msg": f"Deactivated {perk_type}"}


import json

def check_and_cleanup_expired_perks(user_id):
    user = get_user(user_id)
    if not user or "active_perks" not in user:
        return

    perks = user["active_perks"]

    # FIX: If the database returned a string, convert it to a dictionary
    if isinstance(perks, str):
        try:
            # Handle empty strings or 'none' placeholders
            if not perks or perks.lower() == "none":
                perks = {}
            else:
                perks = json.loads(perks)
        except Exception:
            perks = {}

    # Now .items() will work because 'perks' is a dictionary
    expired_found = False
    for perk_type, perk_data in perks.items():
        # ... (your existing expiration logic) ...
        pass


# ═══════════════════════════════════════════════════════════════════════════
#  PERK STATUS QUERIES
# ═══════════════════════════════════════════════════════════════════════════

def is_perk_active(user_id: str, perk_type: str) -> bool:
    """Check if a perk is currently active."""
    check_and_cleanup_expired_perks(user_id)
    
    user = get_user(user_id)
    if not user or "active_perks" not in user:
        return False
    
    if perk_type not in user["active_perks"]:
        return False
    
    perk = user["active_perks"][perk_type]
    return perk.get("active", False)


def get_active_perks(user_id: str) -> dict:
    """Get all active perks for a player."""
    check_and_cleanup_expired_perks(user_id)
    
    user = get_user(user_id)
    if not user or "active_perks" not in user:
        return {}
    
    active = {}
    for perk_type, perk_data in user["active_perks"].items():
        if perk_data.get("active"):
            active[perk_type] = perk_data
    
    return active


def format_active_perks(user_id: str) -> str:
    """Format active perks for display in dashboard."""
    try:
        active_perks = get_active_perks(user_id)
        
        if not active_perks:
            return ""
        
        lines = ["🔥 <b>ACTIVE PERKS:</b>"]
        
        for perk_type, perk_data in active_perks.items():
            try:
                perk_def = PERK_DEFINITIONS.get(perk_type, {})
                icon = perk_def.get("icon", "⚡")
                name = perk_def.get("name", perk_type)
                
                # Calculate time remaining
                try:
                    expires_at = datetime.fromisoformat(perk_data["expires_at"])
                    remaining = (expires_at - datetime.utcnow()).total_seconds()
                    if remaining > 0:
                        minutes = int(remaining // 60)
                        seconds = int(remaining % 60)
                        time_str = f"{minutes}m {seconds}s"
                    else:
                        time_str = "Expired"
                except Exception as te:
                    time_str = "?"
                
                # Show uses remaining if applicable
                if perk_data.get("uses_remaining") is not None:
                    lines.append(f"{icon} {name} ({perk_data['uses_remaining']} uses) — {time_str}")
                else:
                    lines.append(f"{icon} {name} — {time_str}")
            except Exception as pe:
                print(f"[ERROR] Formatting perk {perk_type}: {pe}")
                continue
        
        return "\n".join(lines)
    except Exception as e:
        print(f"[ERROR] format_active_perks: {e}")
        return ""


def use_anti_jammer(user_id: str) -> dict:
    """
    Use one charge of anti-jammer.
    
    Returns:
        {"ok": bool, "msg": str, "uses_remaining": int or None}
    """
    user = get_user(user_id)
    if not user:
        return {"ok": False, "msg": "User not found"}
    
    if "active_perks" not in user or "anti_jammer" not in user["active_perks"]:
        return {"ok": False, "msg": "Anti-Jammer not active"}
    
    perk_data = user["active_perks"]["anti_jammer"]
    
    if not perk_data.get("active"):
        return {"ok": False, "msg": "Anti-Jammer is not active"}
    
    # Decrement uses
    if perk_data.get("uses_remaining") is not None:
        if perk_data["uses_remaining"] <= 0:
            perk_data["active"] = False
            save_user(user_id, user)
            return {"ok": False, "msg": "Anti-Jammer depleted"}
        
        perk_data["uses_remaining"] -= 1
    
    save_user(user_id, user)
    
    return {
        "ok": True,
        "msg": "🔓 Word revealed!",
        "uses_remaining": perk_data.get("uses_remaining")
    }


def get_players_with_jammer(chat_id: str) -> dict:
    """
    Get all players in current round who have jammer active.
    This helps anti-jammer users know who to target.
    
    Args:
        chat_id: Telegram chat ID
    
    Returns:
        {"jammers": [list of player names with jammer active]}
    """
    # This would need integration with the game engine
    # For now, return empty - will be populated by main.py
    return {"jammers": []}


# ═══════════════════════════════════════════════════════════════════════════
#  FORMATTING FOR GAME MASTER RESPONSES
# ═══════════════════════════════════════════════════════════════════════════

def format_scrambled_validation(word: str, is_valid: bool = True) -> str:
    """Format the Game Master response when a scrambled word is validated."""
    scrambled = scramble_word(word)
    
    if is_valid:
        responses = [
            f"⚡ SCRAMBLER ACTIVE\n✅ {scrambled} IS VALID.",
            f"[GHOST_MODE_ACTIVE]\n__________________________\n✅ {scrambled} (Uplink Success)\n--------------------------\nTRANSACTION ID: [REDACTED]",
            f"💀 GHOST UPLINK 💀\n--------------------------\n✅ {scrambled} (Data Secure)\n--------------------------\n//[ALERT]// Connection Unstable.",
            f"🔐 ENCRYPTION ACTIVE\n✅ {scrambled} — Message Locked\n━━━━━━━━━━━━━━━━━━\n[SECURE TRANSMISSION]",
        ]
        return random.choice(responses)
    else:
        responses = [
            f"⚡ SCRAMBLER ACTIVE\n❌ {scrambled} INVALID.",
            f"[GHOST_MODE_ACTIVE]\n__________________________\n❌ {scrambled} (Uplink Failed)\n--------------------------\nTRANSACTION ID: [REDACTED]",
        ]
        return random.choice(responses)
