"""
revenge_system.py — Blood Debt & Scout Command
Implements:
  - Revenge tracking: When player is raided, they get a 24h window to revenge with 1.5x attack buff
  - Scout command: Cost silver, 30% fail chance, reveals enemy army size
"""

import os
from datetime import datetime, timedelta
from typing import Tuple
from supabase_db import get_user, save_user
import random

# ═══════════════════════════════════════════════════════════════════════════
#  REVENGE SYSTEM - Blood Debt Mechanics
# ═══════════════════════════════════════════════════════════════════════════

def set_revenge_target(defender_id: str, attacker_id: str, attacker_name: str):
    """
    When attacker successfully raids defender, set revenge_target on defender.
    Defender gets 1.5x attack buff for 24 hours against specific attacker.
    """
    user = get_user(defender_id)
    if not user:
        return False
    
    buffs = user.get("buffs", {})
    buffs["revenge_target"] = attacker_id
    buffs["revenge_target_name"] = attacker_name
    buffs["revenge_expires"] = (datetime.utcnow() + timedelta(hours=24)).isoformat()
    user["buffs"] = buffs
    save_user(defender_id, user)
    return True


def get_revenge_info(user_id: str) -> dict:
    """Check if player has an active revenge debt. Returns {'active': bool, 'target_id': str, ...}"""
    user = get_user(user_id)
    if not user:
        return {"active": False}
    
    buffs = user.get("buffs", {})
    target_id = buffs.get("revenge_target")
    expires = buffs.get("revenge_expires")
    
    if not target_id or not expires:
        return {"active": False}
    
    try:
        exp_time = datetime.fromisoformat(expires)
        if datetime.utcnow() > exp_time:
            # Expired - clear it
            buffs.pop("revenge_target", None)
            buffs.pop("revenge_target_name", None)
            buffs.pop("revenge_expires", None)
            user["buffs"] = buffs
            save_user(user_id, user)
            return {"active": False}
    except:
        pass
    
    return {
        "active": True,
        "target_id": target_id,
        "target_name": buffs.get("revenge_target_name", "Unknown"),
        "expires": expires
    }


def clear_revenge(user_id: str):
    """Clear revenge debt after successful revenge attack."""
    user = get_user(user_id)
    if not user:
        return
    
    buffs = user.get("buffs", {})
    buffs.pop("revenge_target", None)
    buffs.pop("revenge_target_name", None)
    buffs.pop("revenge_expires", None)
    user["buffs"] = buffs
    save_user(user_id, user)


def get_revenge_multiplier(user_id: str, target_id: str) -> float:
    """Get attack multiplier if player is avenging. Default 1.0, revenge gives 1.5x."""
    revenge = get_revenge_info(user_id)
    if revenge["active"] and revenge["target_id"] == target_id:
        return 1.5
    return 1.0


# ═══════════════════════════════════════════════════════════════════════════
#  SCOUT SYSTEM - Intelligence Gathering
# ═══════════════════════════════════════════════════════════════════════════

def scout_player(scout_id: str, target_id: str, target_name: str) -> Tuple[bool, dict]:
    """
    Scout a target player.
    Cost: 100 Silver
    Success Rate: 70% (30% chance scout gets spotted and fails)
    Returns: (success, scout_result)
    
    scout_result = {
        'success': bool,
        'message': str,
        'army': {units} (if success),
        'traps': {traps} (if success),
    }
    """
    scout_user = get_user(scout_id)
    target_user = get_user(target_id)
    
    if not scout_user or not target_user:
        return False, {"message": "Player not found"}
    
    # Cost check
    scout_silver = scout_user.get("silver", 0)
    if scout_silver < 100:
        return False, {
            "message": f"Scout costs 100 Silver. You have {scout_silver}."
        }
    
    # Roll for success
    if random.random() > 0.7:  # 30% fail chance
        # Scout failed - cost the silver but reveal nothing
        scout_user["silver"] = scout_silver - 100
        save_user(scout_id, scout_user)
        return False, {
            "success": False,
            "message": f"⚠️ Scout was spotted by {target_name}'s sentries and fled! Lost 100 Silver.",
        }
    
    # Scout succeeded - deduct silver and reveal army
    scout_user["silver"] = scout_silver - 100
    save_user(scout_id, scout_user)
    
    # Get target's army
    military = target_user.get("military", {})
    traps = target_user.get("traps", {})
    
    return True, {
        "success": True,
        "message": f"✅ Scout successfully infiltrated {target_name}'s base!",
        "army": military,
        "traps": traps,
        "total_troops": sum(military.values()) if military else 0,
        "total_traps": sum(traps.values()) if traps else 0,
    }


def format_scout_report(result: dict) -> str:
    """Format scout result into readable report."""
    if not result.get("success"):
        return result.get("message", "Scout failed")
    
    lines = [result.get("message", "")]
    lines.append("\n🛰️ *INTELLIGENCE REPORT*")
    lines.append("=" * 50)
    
    army = result.get("army", {})
    if army:
        lines.append("\n⚔️ *ENEMY ARMY*")
        for unit_type, count in army.items():
            emoji_map = {
                "footmen": "👹", "archers": "🏹", "lancers": "🗡️",
                "castellans": "🏰", "pawns": "👹"
            }
            emoji = emoji_map.get(unit_type, "?")
            lines.append(f"├─ {emoji} {unit_type.capitalize()}: {count}")
    
    traps = result.get("traps", {})
    if traps:
        lines.append("\n🔱 *DEFENSIVE TRAPS*")
        for trap_type, count in traps.items():
            emoji_map = {
                "spike_pit": "🕳️", "arrow_tower": "🏹", "cannon": "🔫",
                "tesla_tower": "⚡", "inferno": "🔥"
            }
            emoji = emoji_map.get(trap_type, "?")
            lines.append(f"├─ {emoji} {trap_type.replace('_', ' ').title()}: {count}")
    
    lines.append(f"\n📊 *SUMMARY*: {result.get('total_troops', 0)} troops, {result.get('total_traps', 0)} traps")
    lines.append("=" * 50)
    
    return "\n".join(lines)
