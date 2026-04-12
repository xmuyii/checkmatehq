# -*- coding: utf-8 -*-
"""
prestige_system.py — Prestige & Level Reset Progression
========================================================
Players reaching level 1000+ can prestige to reset level but keep bonuses.
"""

from typing import Dict, Tuple

# ═══════════════════════════════════════════════════════════════════════════
#  PRESTIGE TIERS
# ═══════════════════════════════════════════════════════════════════════════

PRESTIGE_BONUSES = {
    0: {  # No prestige
        "name": "Commoner",
        "xp_multiplier": 1.0,
        "silver_multiplier": 1.0,
        "resource_multiplier": 1.0,
        "troop_training_speed": 1.0,
        "description": "No prestige yet. Reach level 1000 to prestige.",
    },
    1: {
        "name": "🌟 Initiate",
        "xp_multiplier": 1.1,
        "silver_multiplier": 1.1,
        "resource_multiplier": 1.05,
        "troop_training_speed": 1.05,
        "description": "First prestige. Unlock beginning bonuses.",
    },
    2: {
        "name": "⭐ Ascended",
        "xp_multiplier": 1.25,
        "silver_multiplier": 1.2,
        "resource_multiplier": 1.10,
        "troop_training_speed": 1.15,
        "description": "Second prestige. Power consolidates.",
    },
    3: {
        "name": "👑 Legendary",
        "xp_multiplier": 1.5,
        "silver_multiplier": 1.4,
        "resource_multiplier": 1.20,
        "troop_training_speed": 1.25,
        "description": "Third prestige. You are unstoppable.",
    },
    4: {
        "name": "🔱 Mythic",
        "xp_multiplier": 2.0,
        "silver_multiplier": 1.75,
        "resource_multiplier": 1.50,
        "troop_training_speed": 1.5,
        "description": "Fourth prestige. Reality bends to your will.",
    },
    5: {
        "name": "🌌 Cosmic",
        "xp_multiplier": 3.0,
        "silver_multiplier": 2.5,
        "resource_multiplier": 2.0,
        "troop_training_speed": 2.0,
        "description": "Fifth prestige. You transcend the game.",
    },
}

# ═══════════════════════════════════════════════════════════════════════════
#  PRESTIGE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def can_prestige(level: int, current_prestige: int) -> Tuple[bool, str]:
    """Check if player can prestige."""
    if level < 1000:
        return False, f"You need level 1000+. Currently: {level}"
    
    if current_prestige >= 5:
        return False, "You have reached max prestige (5)."
    
    return True, "OK"


def execute_prestige(user: Dict) -> Dict:
    """Reset player to level 1, increase prestige tier, award bonuses."""
    current_level = user.get("level", 1)
    current_prestige = user.get("prestige", 0)
    
    can_do, error = can_prestige(current_level, current_prestige)
    if not can_do:
        return {"success": False, "message": error}
    
    # Calculate rewards
    new_prestige = current_prestige + 1
    bonus_xp = 50000 * (new_prestige ** 1.5)  # Scaling bonus XP
    bonus_silver = 10000 * new_prestige  # Scaling bonus silver
    bonus_troops = {
        "pawn": 500 * new_prestige,
        "knight": 250 * new_prestige,
    }
    
    # Reset level but keep other data
    user["level"] = 1
    user["prestige"] = new_prestige
    user["xp"] = int(bonus_xp)
    user["silver"] = user.get("silver", 0) + bonus_silver
    
    # Add bonus troops
    military = user.get("military", {})
    military["pawn"] = military.get("pawn", 0) + bonus_troops["pawn"]
    military["knight"] = military.get("knight", 0) + bonus_troops["knight"]
    user["military"] = military
    
    # Reset XP counter (for level tracking)
    user["xp_in_level"] = 0
    
    return {
        "success": True,
        "new_prestige": new_prestige,
        "bonus_xp": int(bonus_xp),
        "bonus_silver": bonus_silver,
        "bonus_troops": bonus_troops,
    }


def get_prestige_tier(prestige_level: int) -> Dict:
    """Get bonuses for prestige tier."""
    return PRESTIGE_BONUSES.get(prestige_level, PRESTIGE_BONUSES[0])


def format_prestige_status(level: int, prestige: int) -> str:
    """Format prestige display in profile."""
    tier = get_prestige_tier(prestige)
    
    message = f"👑 PRESTIGE TIER: {tier['name']}\n"
    message += f"Current Level: {level}/1000\n"
    message += f"Progress: {(level/1000)*100:.1f}%\n\n"
    
    if level >= 1000:
        message += "✅ READY TO PRESTIGE!\n"
        message += "Use !prestige to reset level and gain bonuses.\n\n"
    else:
        levels_left = 1000 - level
        message += f"Levels until prestige: {levels_left}\n\n"
    
    message += f"*Prestige Bonuses (Tier {prestige}):*\n"
    message += f"  XP: ×{tier['xp_multiplier']}\n"
    message += f"  Silver: ×{tier['silver_multiplier']}\n"
    message += f"  Resources: ×{tier['resource_multiplier']}\n"
    message += f"  Training Speed: ×{tier['troop_training_speed']}\n"
    
    return message


def format_prestige_confirmation(current_prestige: int, bonus_xp: int, bonus_silver: int) -> str:
    """Format prestige confirmation message."""
    next_tier = get_prestige_tier(current_prestige + 1)
    
    message = f"""🌟 PRESTIGE CONFIRMATION

Your level has been reset to 1.

*New Prestige Tier:* {next_tier['name']}
{next_tier['description']}

*Rewards:*
  ✅ +{bonus_xp:,} XP
  ✅ +{bonus_silver:,} Silver
  ✅ +Bonus Troops
  ✅ All permanent bonuses carry over

*New Multipliers:*
  XP: ×{next_tier['xp_multiplier']}
  Silver: ×{next_tier['silver_multiplier']}
  Resources: ×{next_tier['resource_multiplier']}
  Training: ×{next_tier['troop_training_speed']}

Your journey continues... 🔱
"""
    return message


def get_prestige_multiplier(user: Dict, multiplier_type: str) -> float:
    """Get active multiplier for prestige tier."""
    prestige = user.get("prestige", 0)
    tier = get_prestige_tier(prestige)
    
    return tier.get(f"{multiplier_type}_multiplier", 1.0)

