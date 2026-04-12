# -*- coding: utf-8 -*-
"""
weapon_system.py — Advanced Combat Weapons & Sabotage Tools
=============================================================
Weapons purchased from shop to use on opponents during word fusion games.
"""

from typing import Dict, Tuple, List
import random

# ═══════════════════════════════════════════════════════════════════════════
#  WEAPON CATALOG
# ═══════════════════════════════════════════════════════════════════════════

WEAPONS = {
    # OFFENSIVE WEAPONS
    "machine_gun_turret": {
        "name": "🔫 MACHINE GUN TURRET",
        "description": "Shoot opponent when they form word of target length. They lose 50% of round points + 100 silver.",
        "category": "offensive",
        "effect": "score_and_silver_damage",
        "damage_points": 0.5,  # 50% of round score
        "damage_silver": 100,
        "cost": {"silver": 1000},
        "charges": 1,  # Uses per week
        "cooldown_hours": 168,  # 1 week
        "rarity": "uncommon",
        "min_level": 5,
    },
    
    "plasma_cannon": {
        "name": "⚡ PLASMA CANNON",
        "description": "Heavy weapon. Opponent loses 75% of round points + 250 silver. 48-hour cooldown.",
        "category": "offensive",
        "effect": "score_and_silver_damage",
        "damage_points": 0.75,
        "damage_silver": 250,
        "cost": {"silver": 2500},
        "charges": 1,
        "cooldown_hours": 48,
        "rarity": "rare",
        "min_level": 15,
    },
    
    "emp_blast": {
        "name": "💥 EMP BLAST",
        "description": "Disrupt opponent's next 3 words. They get 0 points from those words.",
        "category": "offensive",
        "effect": "disable_words",
        "disabled_word_count": 3,
        "cost": {"silver": 800},
        "charges": 2,
        "cooldown_hours": 72,
        "rarity": "uncommon",
        "min_level": 8,
    },
    
    # RESOURCE STEALERS
    "xp_siphon": {
        "name": "🔋 XP SIPHON",
        "description": "Each valid word opponent gets this round: YOU gain their XP instead of them. They get 0 XP.",
        "category": "stealer",
        "effect": "steal_xp",
        "steal_percentage": 1.0,  # 100% of victim's XP
        "cost": {"silver": 1200},
        "charges": 1,
        "cooldown_hours": 24,
        "rarity": "rare",
        "min_level": 12,
    },
    
    "silver_siphon": {
        "name": "💰 SILVER SIPHON",
        "description": "Each valid word opponent gets: YOU gain silver equal to their word value. They get normal XP only.",
        "category": "stealer",
        "effect": "steal_silver",
        "steal_percentage": 1.0,
        "cost": {"silver": 1500},
        "charges": 1,
        "cooldown_hours": 24,
        "rarity": "rare",
        "min_level": 14,
    },
    
    "resource_drain": {
        "name": "🌀 RESOURCE DRAIN",
        "description": "Opponent loses 200 wood + 100 bronze per word they form.",
        "category": "stealer",
        "effect": "drain_resources",
        "drain_amounts": {"wood": 200, "bronze": 100},
        "cost": {"silver": 2000},
        "charges": 1,
        "cooldown_hours": 48,
        "rarity": "rare",
        "min_level": 20,
    },
    
    # RESOURCE STEALERS - VARIANTS
    "wood_extractor": {
        "name": "🌲 WOOD EXTRACTOR",
        "description": "Each word opponent forms: steal 300 wood from their base.",
        "category": "stealer",
        "effect": "steal_resource_type",
        "resource_type": "wood",
        "steal_amount": 300,
        "cost": {"silver": 800},
        "charges": 2,
        "cooldown_hours": 12,
        "rarity": "uncommon",
        "min_level": 7,
    },
    
    "bronze_extractor": {
        "name": "🧱 BRONZE EXTRACTOR",
        "description": "Each word opponent forms: steal 200 bronze from their base.",
        "category": "stealer",
        "effect": "steal_resource_type",
        "resource_type": "bronze",
        "steal_amount": 200,
        "cost": {"silver": 1000},
        "charges": 2,
        "cooldown_hours": 12,
        "rarity": "uncommon",
        "min_level": 10,
    },
    
    "iron_extractor": {
        "name": "⛓️ IRON EXTRACTOR",
        "description": "Each word opponent forms: steal 150 iron from their base.",
        "category": "stealer",
        "effect": "steal_resource_type",
        "resource_type": "iron",
        "steal_amount": 150,
        "cost": {"silver": 1500},
        "charges": 2,
        "cooldown_hours": 12,
        "rarity": "uncommon",
        "min_level": 12,
    },
    
    "diamond_extractor": {
        "name": "💎 DIAMOND EXTRACTOR",
        "description": "Each word opponent forms: steal 50 diamond from their base.",
        "category": "stealer",
        "effect": "steal_resource_type",
        "resource_type": "diamond",
        "steal_amount": 50,
        "cost": {"silver": 3000},
        "charges": 1,
        "cooldown_hours": 24,
        "rarity": "rare",
        "min_level": 25,
    },
}

# ═══════════════════════════════════════════════════════════════════════════
#  WEAPON FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def get_available_weapons(player_level: int) -> List[str]:
    """Return list of weapons player can buy at their level."""
    return [
        weapon_id for weapon_id, weapon_data in WEAPONS.items()
        if weapon_data["min_level"] <= player_level
    ]


def can_buy_weapon(weapon_id: str, player_level: int, player_silver: int) -> Tuple[bool, str]:
    """Check if player can buy a weapon."""
    if weapon_id not in WEAPONS:
        return False, "Unknown weapon"
    
    weapon = WEAPONS[weapon_id]
    
    if player_level < weapon["min_level"]:
        return False, f"Requires level {weapon['min_level']}"
    
    cost = weapon["cost"].get("silver", 0)
    if player_silver < cost:
        return False, f"Need {cost} silver (you have {player_silver})"
    
    return True, "OK"


def format_weapons_shop(player_level: int, player_silver: int) -> str:
    """Display weapon shop menu."""
    available = get_available_weapons(player_level)
    
    menu = f"""🔫 WEAPONS SHOP

Available for Level {player_level}:

"""
    for weapon_id in sorted(available):
        weapon = WEAPONS[weapon_id]
        can_afford = player_silver >= weapon["cost"].get("silver", 0)
        affordability = "✅" if can_afford else "❌"
        
        menu += f"{affordability} {weapon['name']}\n"
        menu += f"   {weapon['description']}\n"
        menu += f"   Cost: {weapon['cost'].get('silver', 0)} silver | Charges: {weapon['charges']}\n\n"
    
    menu += f"Buy: !buy_weapon [weapon_name]\n"
    menu += f"Your silver: {player_silver}"
    
    return menu


def add_weapon_to_inventory(player_weapons: Dict, weapon_id: str) -> Dict:
    """Add weapon to player's inventory."""
    if not player_weapons:
        player_weapons = {}
    
    # Each weapon purchase increases charges
    weapon = WEAPONS[weapon_id]
    current_charges = player_weapons.get(weapon_id, {}).get("charges_remaining", 0)
    
    player_weapons[weapon_id] = {
        "charges_remaining": current_charges + weapon["charges"],
        "cooldown_until": 0,  # No cooldown initially
        "last_used": None,
    }
    
    return player_weapons


def can_use_weapon(player_weapons: Dict, weapon_id: str) -> Tuple[bool, str]:
    """Check if player can use weapon (not on cooldown, has charges)."""
    if weapon_id not in player_weapons:
        return False, "You don't own this weapon"
    
    weapon_status = player_weapons[weapon_id]
    
    if weapon_status["charges_remaining"] <= 0:
        return False, "No charges remaining"
    
    if weapon_status["cooldown_until"] > 0:
        # Would need timestamp check in real implementation
        return False, "Weapon on cooldown"
    
    return True, "OK"


def use_weapon_on_target(attacker_id: str, target_id: str, weapon_id: str, 
                         attacker_weapons: Dict, target_data: Dict) -> Dict:
    """Execute weapon effect on target. Returns results dict."""
    if weapon_id not in WEAPONS:
        return {"success": False, "message": "Unknown weapon"}
    
    weapon = WEAPONS[weapon_id]
    can_use, error = can_use_weapon(attacker_weapons, weapon_id)
    if not can_use:
        return {"success": False, "message": error}
    
    result = {
        "success": True,
        "weapon_id": weapon_id,
        "weapon_name": weapon["name"],
        "effect_type": weapon["effect"],
        "target_id": target_id,
    }
    
    # Reduce charges
    attacker_weapons[weapon_id]["charges_remaining"] -= 1
    
    # Set cooldown (in production, use actual timestamp)
    attacker_weapons[weapon_id]["cooldown_until"] = weapon["cooldown_hours"]
    
    return result


def format_weapon_activation(weapon_id: str, target_name: str) -> str:
    """Format message when weapon is activated."""
    weapon = WEAPONS[weapon_id]
    return f"💥 {weapon['name']} activated on {target_name}!"


def format_weapon_damage_notification(weapon_id: str, attacker_name: str, damage_details: Dict) -> str:
    """Format damage notification to victim."""
    weapon = WEAPONS[weapon_id]
    message = f"⚠️ ATTACK: {attacker_name} used {weapon['name']} on you!\n\n"
    
    if "points_lost" in damage_details:
        message += f"Lost {damage_details['points_lost']} points\n"
    
    if "silver_lost" in damage_details:
        message += f"Lost {damage_details['silver_lost']} silver\n"
    
    if "resources_lost" in damage_details:
        for res, amount in damage_details["resources_lost"].items():
            message += f"Lost {amount} {res}\n"
    
    if "xp_stolen" in damage_details:
        message += f"Attacker stole {damage_details['xp_stolen']} XP from you!\n"
    
    if "words_disabled" in damage_details:
        message += f"Your next {damage_details['words_disabled']} words are DISABLED (0 points)!\n"
    
    return message

