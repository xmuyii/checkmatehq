"""
research_system.py — Science Laboratory Research & Tech Tree
============================================================
Players research new technologies to unlock items, abilities, and base sections.
Research requires: Silver + Resources, and takes time (async completion).
"""

# ══════════════════════════════════════════════════════════════════════════
#  RESEARCH CATALOG — Tech trees with costs, times, and unlocks
# ══════════════════════════════════════════════════════════════════════════

RESEARCH_TYPES = {
    # ─── TIER 1: BASIC TECH (Level 1-3) ───────────────────────────────────
    "iron_working": {
        "name": "⛏️ Iron Working",
        "description": "Learn to forge stronger weapons and armor",
        "category": "warfare",
        "tier": 1,
        "min_level": 1,
        "cost": {
            "silver": 300,
            "wood": 0,
            "bronze": 50,
            "iron": 0,
        },
        "time": 300,  # 5 minutes
        "unlocks": {
            "items": ["iron_sword", "iron_armor"],
            "weapons": ["iron_claymore"],
            "abilities": ["fortified_stance"],
            "base_sections": [],
        },
    },
    
    "agriculture": {
        "name": "🌾 Agriculture",
        "description": "Improve farming techniques to grow more food",
        "category": "economy",
        "tier": 1,
        "min_level": 1,
        "cost": {
            "silver": 200,
            "wood": 100,
            "bronze": 0,
            "iron": 0,
        },
        "time": 240,  # 4 minutes
        "unlocks": {
            "items": ["grain_silo", "fertilizer"],
            "weapons": [],
            "abilities": ["harvest_bonus"],
            "base_sections": ["farm_extension"],
        },
    },
    
    "bronze_casting": {
        "name": "🔔 Bronze Casting",
        "description": "Master the art of bronze metalwork",
        "category": "warfare",
        "tier": 1,
        "min_level": 2,
        "cost": {
            "silver": 400,
            "wood": 0,
            "bronze": 100,
            "iron": 20,
        },
        "time": 360,  # 6 minutes
        "unlocks": {
            "items": ["bronze_shield", "bronze_gauntlets"],
            "weapons": ["bronze_axe", "bronze_spear"],
            "abilities": ["shield_wall"],
            "base_sections": [],
        },
    },
    
    # ─── TIER 2: ADVANCED TECH (Level 3-5) ─────────────────────────────────
    "siege_engineering": {
        "name": "🏰 Siege Engineering",
        "description": "Learn to build and use siege weapons",
        "category": "warfare",
        "tier": 2,
        "min_level": 3,
        "cost": {
            "silver": 800,
            "wood": 200,
            "bronze": 100,
            "iron": 100,
        },
        "time": 600,  # 10 minutes
        "unlocks": {
            "items": ["siege_tower", "battering_ram", "catapult"],
            "weapons": ["siege_catapult", "ballista"],
            "abilities": ["breach_defenses"],
            "base_sections": ["siege_workshop"],
        },
    },
    
    "alchemy": {
        "name": "🧪 Alchemy",
        "description": "Discover potions and magical enhancements",
        "category": "magic",
        "tier": 2,
        "min_level": 4,
        "cost": {
            "silver": 1000,
            "wood": 50,
            "bronze": 50,
            "iron": 150,
        },
        "time": 720,  # 12 minutes
        "unlocks": {
            "items": ["strength_potion", "invisibility_potion", "healing_potion"],
            "weapons": ["alchemist_bomb"],
            "abilities": ["potion_crafting"],
            "base_sections": ["alchemist_tower"],
        },
    },
    
    "cavalry_tactics": {
        "name": "🐎 Cavalry Tactics",
        "description": "Master fast-moving mounted combat",
        "category": "warfare",
        "tier": 2,
        "min_level": 4,
        "cost": {
            "silver": 900,
            "wood": 100,
            "bronze": 200,
            "iron": 50,
        },
        "time": 540,  # 9 minutes
        "unlocks": {
            "items": ["war_horse", "cavalry_saddle"],
            "weapons": ["cavalry_lance", "war_hammer"],
            "abilities": ["charge_attack"],
            "base_sections": ["stable"],
        },
    },
    
    # ─── TIER 3: ELITE TECH (Level 5+) ─────────────────────────────────────
    "dragon_lore": {
        "name": "🐉 Dragon Lore",
        "description": "Unlock ancient knowledge of dragons",
        "category": "magic",
        "tier": 3,
        "min_level": 5,
        "cost": {
            "silver": 2000,
            "wood": 0,
            "bronze": 500,
            "iron": 500,
        },
        "time": 1200,  # 20 minutes
        "unlocks": {
            "items": ["dragon_egg", "dragon_scale_armor"],
            "weapons": ["dragon_breath", "dragon_claw_gauntlets"],
            "abilities": ["summon_dragon", "dragon_fire"],
            "base_sections": ["dragon_sanctum"],
        },
    },
    
    "dimensional_gateway": {
        "name": "🌌 Dimensional Gateway",
        "description": "Open portals to alternate dimensions",
        "category": "magic",
        "tier": 3,
        "min_level": 6,
        "cost": {
            "silver": 3000,
            "wood": 200,
            "bronze": 300,
            "iron": 500,
        },
        "time": 1800,  # 30 minutes
        "unlocks": {
            "items": ["dimensional_key", "void_stone"],
            "weapons": ["void_ripper", "dimensional_blade"],
            "abilities": ["teleport_anywhere", "summon_shadow_clone"],
            "base_sections": ["dimensional_lab", "obelisk_chamber"],
        },
    },
    
    "legendary_forging": {
        "name": "⚔️ Legendary Forging",
        "description": "Create legendary weapons and artifacts",
        "category": "warfare",
        "tier": 3,
        "min_level": 7,
        "cost": {
            "silver": 5000,
            "wood": 0,
            "bronze": 1000,
            "iron": 1000,
        },
        "time": 2400,  # 40 minutes
        "unlocks": {
            "items": ["excalibur", "mjolnir", "infinity_stone"],
            "weapons": ["excalibur_blade", "godly_hammer", "soul_reaper"],
            "abilities": ["legendary_strike", "god_form"],
            "base_sections": ["legendary_forge", "artifact_vault"],
        },
    },
    
    # ─── SPECIAL RESEARCH ───────────────────────────────────────────────────
    "assassination": {
        "name": "🗡️ Assassination",
        "description": "Deadly silent strike techniques",
        "category": "warfare",
        "tier": 2,
        "min_level": 5,
        "cost": {
            "silver": 1500,
            "wood": 50,
            "bronze": 0,
            "iron": 200,
        },
        "time": 900,  # 15 minutes
        "unlocks": {
            "items": ["assassin_dagger", "poison_vial", "smoke_bomb"],
            "weapons": ["shadow_strike", "poison_blade"],
            "abilities": ["instant_kill", "fade_into_darkness"],
            "base_sections": ["assassin_guild"],
        },
    },
    
    "defensive_magic": {
        "name": "🛡️ Defensive Magic",
        "description": "Master protective spells and wards",
        "category": "magic",
        "tier": 2,
        "min_level": 3,
        "cost": {
            "silver": 600,
            "wood": 100,
            "bronze": 50,
            "iron": 100,
        },
        "time": 480,  # 8 minutes
        "unlocks": {
            "items": ["protection_amulet", "ward_ring"],
            "weapons": ["shield_spell", "force_field"],
            "abilities": ["barrier_shield", "damage_reflection"],
            "base_sections": [],
        },
    },
}

# ══════════════════════════════════════════════════════════════════════════
#  UTILITY FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════

def get_available_research(user_level: int) -> dict:
    """Get all research options available at user's level."""
    available = {}
    for research_id, research in RESEARCH_TYPES.items():
        if user_level >= research.get("min_level", 1):
            available[research_id] = research
    return available


def get_research_by_tier(tier: int, user_level: int) -> dict:
    """Get research options by tier."""
    result = {}
    for research_id, research in RESEARCH_TYPES.items():
        if research.get("tier") == tier and user_level >= research.get("min_level", 1):
            result[research_id] = research
    return result


def format_research_info(research_id: str) -> str:
    """Format research info for display (truncated for Telegram byte limits)."""
    if research_id not in RESEARCH_TYPES:
        return "❌ Unknown research type"
    
    research = RESEARCH_TYPES[research_id]
    
    text = f"""<b>{research['name']}</b>

📖 {research['description']}

<b>Details:</b>
⏱️ Time: {research['time']}s ({research['time']//60}m)
📊 Tier: {research['tier']}
🎖️ Min Level: {research['min_level']}

<b>Cost:</b>"""
    for res_type, amount in research['cost'].items():
        if amount > 0:
            text += f"\n• {amount} {res_type.upper()}"
    
    text += "\n\n<b>Unlocks (First 2):</b>"
    
    unlocks = research['unlocks']
    if unlocks.get('items'):
        items_list = ', '.join(unlocks['items'][:2])
        if len(unlocks['items']) > 2:
            items_list += f" +{len(unlocks['items'])-2} more"
        text += f"\n📦 {items_list}"
    if unlocks.get('weapons'):
        weapons_list = ', '.join(unlocks['weapons'][:2])
        if len(unlocks['weapons']) > 2:
            weapons_list += f" +{len(unlocks['weapons'])-2} more"
        text += f"\n⚔️ {weapons_list}"
    if unlocks.get('abilities'):
        abilities_list = ', '.join(unlocks['abilities'][:2])
        if len(unlocks['abilities']) > 2:
            abilities_list += f" +{len(unlocks['abilities'])-2} more"
        text += f"\n✨ {abilities_list}"
    if unlocks.get('base_sections'):
        sections_list = ', '.join(unlocks['base_sections'][:2])
        if len(unlocks['base_sections']) > 2:
            sections_list += f" +{len(unlocks['base_sections'])-2} more"
        text += f"\n🏗️ {sections_list}"
    
    return text


def can_research(user: dict, research_id: str) -> tuple[bool, str]:
    """Check if user can start research. Returns (can_research, reason)."""
    research = RESEARCH_TYPES.get(research_id)
    if not research:
        return False, "Unknown research"
    
    # Check level
    if user.get('level', 1) < research.get('min_level', 1):
        required = research['min_level']
        return False, f"Requires level {required}"
    
    # Check if already researching this
    research_progress = user.get('research_progress', {})
    if research_id in research_progress and research_progress[research_id].get('status') == 'in_progress':
        return False, f"Already researching {research['name']}"
    
    # Check if already researched
    research_completed = user.get('research_completed', [])
    if research_id in research_completed:
        return False, f"Already researched {research['name']}"
    
    # Check resources
    base_res = user.get('base_resources', {})
    resources = base_res.get('resources', {})
    
    for res_type, cost in research['cost'].items():
        if cost > 0:
            available = resources.get(res_type, 0) if res_type != 'food' else base_res.get('food', 0)
            if available < cost:
                return False, f"Need {cost} {res_type.upper()}, have {available}"
    
    return True, "Can research"


def start_research(user_id: str, user: dict, research_id: str, db_module) -> tuple[bool, str]:
    """Start a new research project. Returns (success, message)."""
    can_do, reason = can_research(user, research_id)
    if not can_do:
        return False, reason
    
    research = RESEARCH_TYPES[research_id]
    
    # Deduct resources
    base_res = user.get('base_resources', {})
    resources = base_res.get('resources', {})
    
    for res_type, cost in research['cost'].items():
        if cost > 0:
            resources[res_type] = resources.get(res_type, 0) - cost
    
    # Initialize research progress
    import time
    if 'research_progress' not in user:
        user['research_progress'] = {}
    
    completion_time = int(time.time()) + research['time']
    user['research_progress'][research_id] = {
        'status': 'in_progress',
        'started_at': int(time.time()),
        'completes_at': completion_time,
        'time_remaining': research['time'],
    }
    
    # Update user
    base_res['resources'] = resources
    user['base_resources'] = base_res
    
    from supabase_db import save_user
    save_user(user_id, user)
    
    return True, f"✅ Research {research['name']} started!\nCompletion: {research['time']}s"


def check_research_complete(user_id: str, user: dict) -> list:
    """Check if any research is complete. Returns list of completed research IDs."""
    import time
    current_time = int(time.time())
    completed = []
    
    research_progress = user.get('research_progress', {})
    for research_id, progress in list(research_progress.items()):
        if progress.get('status') == 'in_progress':
            if current_time >= progress.get('completes_at', 0):
                # Mark as complete
                progress['status'] = 'complete'
                completed.append(research_id)
                
                # Add to completed list
                if 'research_completed' not in user:
                    user['research_completed'] = []
                if research_id not in user['research_completed']:
                    user['research_completed'].append(research_id)
    
    # Save if changes made
    if completed:
        from supabase_db import save_user
        save_user(user_id, user)
    
    return completed


def apply_research_unlocks(user: dict, research_id: str):
    """Apply all unlocks from completed research."""
    if research_id not in RESEARCH_TYPES:
        return
    
    research = RESEARCH_TYPES[research_id]
    unlocks = research['unlocks']
    
    # Add items
    if unlocks.get('items'):
        if 'inventory' not in user:
            user['inventory'] = {}
        for item in unlocks['items']:
            user['inventory'][item] = user['inventory'].get(item, 0) + 1
    
    # Add weapons (give 1 charge)
    if unlocks.get('weapons'):
        if 'weapons' not in user:
            user['weapons'] = {}
        for weapon in unlocks['weapons']:
            if weapon not in user['weapons']:
                user['weapons'][weapon] = {'charges_remaining': 1}
    
    # Add abilities
    if unlocks.get('abilities'):
        if 'abilities' not in user:
            user['abilities'] = []
        for ability in unlocks['abilities']:
            if ability not in user['abilities']:
                user['abilities'].append(ability)
    
    # Add base sections
    if unlocks.get('base_sections'):
        if 'base_sections' not in user:
            user['base_sections'] = []
        for section in unlocks['base_sections']:
            if section not in user['base_sections']:
                user['base_sections'].append(section)
    
    return user
