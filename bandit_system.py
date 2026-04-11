"""
🎭 BANDIT SYSTEM - Strategic Enemy Encounters
==============================================
Random CPU bandits attack player bases in different sectors.
Each sector has unique enemies, storylines, and atmospheric narratives.
Only level 6+ can experience bandit attacks.
Players must strategically defend their bases using items and troops.
"""

import random
from datetime import datetime, timedelta

# ═══════════════════════════════════════════════════════════════════════════
#  SECTOR-SPECIFIC BANDIT NARRATIVES & ENEMIES
# ═══════════════════════════════════════════════════════════════════════════

SECTOR_NARRATIVES = {
    1: {
        "name": "Badlands-8",
        "atmosphere": "🏜️ DESOLATE & LAWLESS",
        "mood": "⚰️ gritty, survival-focused, harsh",
        "story_intro": "Welcome to the Badlands. A place where the weak perish and only the ruthless survive.",
        "bandit_types": ["Sand Raider", "Dust Bandit", "Dune Scavenger"],
        "narrative_samples": [
            "💨 A dust storm swirls... *Sand Raiders emerge from the haze, hungry for spoils*",
            "🏜️ The ground trembles... *Dune Scavengers circle your base, eyeing your resources*",
            "⚠️ *'Your weaknesses are like gold to us,'* whispers the Sand Raider Leader",
            "🌪️ The Badlands demand tribute. Will you pay with blood or resources?"
        ],
        "reason_for_attack": "They were here first. The Badlands belong to them.",
        "defeat_consequence": "Your base is ransacked. Resources scattered across the dunes.",
        "victory_reward": "You prove yourself worthy of the Badlands' harsh respect.",
    },
    2: {
        "name": "Crimson Wastes",
        "atmosphere": "🔴 FIERY & AGGRESSIVE",
        "mood": "🔥 fast-paced, dangerous, high-stakes",
        "story_intro": "The Crimson Wastes burn with territorial rage. These are the lands of the Fire Clans.",
        "bandit_types": ["Fire Clan Warrior", "Ash Zealot", "Flame Marauder"],
        "narrative_samples": [
            "🔥 The ground turns red-hot... *Fire Clan Warriors charge with blazing fury*",
            "🌋 *'Interloper! This is OUR domain!'* roars the Flame Marauder",
            "⚡ Ash Zealots chant ancient war songs as they close in on your defenses",
            "💢 The attack is VIOLENT. They want blood AND your resources.",
        ],
        "reason_for_attack": "You dare mine in their sacred wasteland? Unforgivable.",
        "defeat_consequence": "Your base BURNS. Structures crumble. Pride shattered.",
        "victory_reward": "The Fire Clans acknowledge your strength. Temporary peace granted.",
    },
    3: {
        "name": "Obsidian Peaks",
        "atmosphere": "⛰️ ISOLATING & TREACHEROUS",
        "mood": "❄️ unforgiving, brutal, merciless",
        "story_intro": "The Obsidian Peaks are home to the most ruthless bandits. Few survive encounters here.",
        "bandit_types": ["Peak Assassin", "Stone Guard", "Apex Predator"],
        "narrative_samples": [
            "⛰️ Snow slides down... *Peak Assassins strike with surgical precision*",
            "💀 A shadow moves. This is NOT a fair fight.",
            "🎯 *'You're prey here,'* hisses the Apex Predator stalking your perimeter",
            "⚔️ The battle is INTENSE. These enemies know every weak point of your defense.",
        ],
        "reason_for_attack": "Your presence taints their sacred peaks. They will reclaim it in blood.",
        "defeat_consequence": "Your entire operation is dismantled. You barely escape with your life.",
        "victory_reward": "Legend status among the peaks. You are no longer easy prey.",
    },
    4: {
        "name": "Shattered Valley",
        "atmosphere": "💔 CHAOTIC & UNPREDICTABLE",
        "mood": "😈 cunning, deceptive, volatile",
        "story_intro": "The Valley is a warzone. Multiple factions clash for supremacy. Trust NO ONE.",
        "bandit_types": ["Valley Thug", "Chaos Cultist", "Shadow Operative"],
        "narrative_samples": [
            "💔 The ground splits... *Rivals emerge from ALL directions*",
            "🤐 They use TRICKS. Deception. Psychological warfare.",
            "😈 *'Hahahaha! You thought you were safe here?'* laughs the Chaos Cultist",
            "⚡ This is not honor. This is pure survival of the fittest.",
        ],
        "reason_for_attack": "In the Shattered Valley, EVERYONE is your enemy. Nowhere is safe.",
        "defeat_consequence": "You're left with nothing. In this valley, defeat means exile.",
        "victory_reward": "You've earned respect among the lawless. Few achieve this.",
    },
    5: {
        "name": "Frozen Abyss",
        "atmosphere": "❄️ DESOLATE & ADDICTIVE",
        "mood": "😰 desperate, survival-horror, compelling",
        "story_intro": "The Abyss calls to you. A place of beautiful danger and addictive peril.",
        "bandit_types": ["Frost Wraith", "Ice Cultist", "Frozen Soul"],
        "narrative_samples": [
            "❄️ Your breath freezes mid-air... *Frost Wraiths materialize from the ice*",
            "🧊 They're not entirely... alive? But they fight with obsessive determination",
            "😶 *'Join us in the cold embrace,'* whispers the Ice Cultist with haunting beauty",
            "🌬️ The battle feels eternal. Time itself seems frozen.",
        ],
        "reason_for_attack": "You intrude on cursed lands. The Abyss demands its due.",
        "defeat_consequence": "You're left frozen, trapped in a nightmare you can't wake from.",
        "victory_reward": "You may return. The Abyss develops a twisted respect for you.",
    },
    6: {
        "name": "Molten Gorge",
        "atmosphere": "🔥 EPIC & OVERWHELMING",
        "mood": "👑 legendary, apocalyptic, ultimate-test",
        "story_intro": "Only the TRUE legends reach the Gorge. The strongest bandits make their home here.",
        "bandit_types": ["Lava Lord", "Inferno Knight", "Magma Overlord"],
        "narrative_samples": [
            "🌋 EVERYTHING BURNS... *The Lava Lord rises from molten depths*",
            "☠️ This is NOT a normal battle. This is your TRIAL BY FIRE.",
            "👑 *'Few reach me. FEWER survive,'* declares the Magma Overlord",
            "⚔️ The ground itself becomes your enemy as battle rages.",
        ],
        "reason_for_attack": "To rule the Gorge, you must first SURVIVE the Gorge.",
        "defeat_consequence": "You are incinerated. Your base is slag. Legend ends.",
        "victory_reward": "You become a LEGEND. The Gorge bows before you.",
    },
    7: {
        "name": "Twilight Marshes",
        "atmosphere": "🌙 MYSTERIOUS & ADDICTIVE",
        "mood": "👻 eerie, hypnotic, deeply-compelling",
        "story_intro": "Lost souls wander these marshes. The line between life and death blurs here.",
        "bandit_types": ["Marsh Phantom", "Cursed Wisp", "Specter Knight"],
        "narrative_samples": [
            "🌙 Moonlight distorts reality... *Phantoms drift through your defenses like smoke*",
            "👻 They're beautiful. And terrifying. And you can't look away.",
            "🔮 *'Stay with us. Forever,'* the Specter Knight offers with hypnotic charm",
            "😵 The battle feels dreamlike. Are you awake?",
        ],
        "reason_for_attack": "You've ventured into their dream realm. Now you belong to them.",
        "defeat_consequence": "You're caught between worlds. Half-alive, half-ghost.",
        "victory_reward": "You master the twilight between worlds.",
    },
    8: {
        "name": "Silent Forest",
        "atmosphere": "🌲 ALIVE & REWARDING",
        "mood": "🦁 wild, fair, respect-based",
        "story_intro": "The Forest is alive. Its guardians are fierce but honorable.",
        "bandit_types": ["Beast Guardian", "Forest Warden", "Primal Avenger"],
        "narrative_samples": [
            "🌲 The trees whisper... *Forest Wardens emerge with noble purpose*",
            "🦁 *'You have intruded on sacred ground. Prove your worth,'* growls the Beast Guardian",
            "⚔️ This battle feels FAIR. Honorable. Like a test of character.",
            "🏆 If you win, you earn the Forest's blessing.",
        ],
        "reason_for_attack": "Respect the Forest, or the Forest demands recompense.",
        "defeat_consequence": "You're exiled. The Forest shuns you.",
        "victory_reward": "The Forest accepts you. Unique rewards and blessings await.",
    },
    9: {
        "name": "Void Canyon",
        "atmosphere": "🌑 COSMIC & LEGENDARY",
        "mood": "👽 transcendent, reality-bending, mind-shattering",
        "story_intro": "Welcome to NOTHINGNESS. Here, only the most legendary warriors exist.",
        "bandit_types": ["Void Entity", "Cosmic Horror", "Eldritch Titan"],
        "narrative_samples": [
            "🌑 Reality CRACKS... *A Void Entity materializes with unknowable power*",
            "👾 *'You are a mote of dust. We are INFINITY,'* echoes the Cosmic Horror",
            "☠️ This is not a battle. This is EXISTENCE versus NON-EXISTENCE.",
            "💫 Victory here means you've transcended mortality.",
        ],
        "reason_for_attack": "Your very existence disturbs the Void. You must prove yourself cosmic-worthy.",
        "defeat_consequence": "You're erased. As if you never existed.",
        "victory_reward": "You BECOME legend. Among legends. Eternal glory.",
    }
}

# ═══════════════════════════════════════════════════════════════════════════
#  BANDIT ENEMY TIERS & STATS
# ═══════════════════════════════════════════════════════════════════════════

BANDIT_STATS = {
    # Tier 1 (Badlands - Level 6+)
    "Sand Raider": {"hp": 30, "attack": 8, "loot": {"wood": 15, "bronze": 5}, "threat": "🟢 LOW"},
    "Dust Bandit": {"hp": 25, "attack": 6, "loot": {"wood": 20, "bronze": 8}, "threat": "🟢 LOW"},
    "Dune Scavenger": {"hp": 28, "attack": 7, "loot": {"bronze": 12}, "threat": "🟢 LOW"},
    
    # Tier 2 (Crimson Wastes - Level 8+)
    "Fire Clan Warrior": {"hp": 50, "attack": 15, "loot": {"bronze": 20, "iron": 10}, "threat": "🟡 MEDIUM"},
    "Ash Zealot": {"hp": 45, "attack": 18, "loot": {"iron": 15}, "threat": "🟡 MEDIUM"},
    "Flame Marauder": {"hp": 55, "attack": 20, "loot": {"bronze": 25, "iron": 12}, "threat": "🟡 MEDIUM"},
    
    # Tier 3 (Obsidian Peaks - Level 10+)
    "Peak Assassin": {"hp": 70, "attack": 25, "loot": {"iron": 20, "diamond": 5}, "threat": "🔴 HIGH"},
    "Stone Guard": {"hp": 80, "attack": 22, "loot": {"iron": 30}, "threat": "🔴 HIGH"},
    "Apex Predator": {"hp": 90, "attack": 28, "loot": {"iron": 25, "diamond": 8}, "threat": "🔴 HIGH"},
    
    # Tier 4 (Shattered Valley - Level 11+)
    "Valley Thug": {"hp": 60, "attack": 20, "loot": {"iron": 15, "bronze": 10}, "threat": "🟡 MEDIUM"},
    "Chaos Cultist": {"hp": 65, "attack": 23, "loot": {"iron": 20, "bronze": 15}, "threat": "🟡 MEDIUM"},
    "Shadow Operative": {"hp": 70, "attack": 26, "loot": {"iron": 25, "diamond": 5}, "threat": "🔴 HIGH"},
    
    # Tier 5 (Frozen Abyss - Level 13+)
    "Frost Wraith": {"hp": 85, "attack": 28, "loot": {"diamond": 10, "iron": 20}, "threat": "🔴 HIGH"},
    "Ice Cultist": {"hp": 95, "attack": 32, "loot": {"diamond": 15, "iron": 25}, "threat": "🔴 HIGH"},
    "Frozen Soul": {"hp": 100, "attack": 35, "loot": {"diamond": 20}, "threat": "🔴 CRITICAL"},
    
    # Tier 6 (Molten Gorge - Level 15+)
    "Lava Lord": {"hp": 120, "attack": 45, "loot": {"diamond": 30, "relics": 5}, "threat": "💀 DEADLY"},
    "Inferno Knight": {"hp": 130, "attack": 50, "loot": {"diamond": 35, "relics": 8}, "threat": "💀 DEADLY"},
    "Magma Overlord": {"hp": 150, "attack": 60, "loot": {"diamond": 50, "relics": 10}, "threat": "💀 DEADLY"},
    
    # Tier 7 (Twilight Marshes - Level 14+)
    "Marsh Phantom": {"hp": 110, "attack": 38, "loot": {"relics": 8, "diamond": 15}, "threat": "🔴 HIGH"},
    "Cursed Wisp": {"hp": 105, "attack": 40, "loot": {"relics": 10, "diamond": 20}, "threat": "🔴 HIGH"},
    "Specter Knight": {"hp": 125, "attack": 48, "loot": {"relics": 15, "diamond": 30}, "threat": "💀 DEADLY"},
    
    # Tier 8 (Silent Forest - Level 12+)
    "Beast Guardian": {"hp": 75, "attack": 24, "loot": {"wood": 30, "diamond": 8}, "threat": "🟡 MEDIUM"},
    "Forest Warden": {"hp": 85, "attack": 28, "loot": {"wood": 40, "diamond": 12}, "threat": "🔴 HIGH"},
    "Primal Avenger": {"hp": 95, "attack": 32, "loot": {"wood": 50, "diamond": 15}, "threat": "🔴 HIGH"},
    
    # Tier 9 (Void Canyon - Level 20+)
    "Void Entity": {"hp": 200, "attack": 70, "loot": {"relics": 50, "diamond": 100}, "threat": "☠️ GODLIKE"},
    "Cosmic Horror": {"hp": 220, "attack": 80, "loot": {"relics": 75, "diamond": 120}, "threat": "☠️ GODLIKE"},
    "Eldritch Titan": {"hp": 250, "attack": 100, "loot": {"relics": 100, "diamond": 150}, "threat": "☠️ GODLIKE"},
}

# ═══════════════════════════════════════════════════════════════════════════
#  BANDIT SYSTEM FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def get_sector_narrative(sector_id: int) -> dict:
    """Get narrative info for a sector."""
    return SECTOR_NARRATIVES.get(sector_id, {})

def pick_random_narrative(sector_id: int) -> str:
    """Pick a random narrative line from sector."""
    narrative = get_sector_narrative(sector_id)
    samples = narrative.get("narrative_samples", [])
    return random.choice(samples) if samples else "A bandit emerges..."

def should_trigger_bandit_attack(player_level: int, sector_id: int) -> tuple[bool, str]:
    """
    Determine if a bandit should attack.
    Returns (should_attack, reason)
    
    Rules:
    - Only trigger for level 6+
    - Each sector has minimum level requirement
    - Random chance increases with level
    """
    if player_level < 6:
        return False, "Level too low - bandits ignore you"
    
    # Sector-based minimum level requirements
    sector_min_levels = {
        1: 6,      # Badlands
        2: 8,
        3: 10,
        4: 11,
        5: 13,
        6: 15,     # Molten Gorge
        7: 14,     # Twilight Marshes
        8: 12,     # Silent Forest
        9: 20,     # Void Canyon
    }
    
    min_level = sector_min_levels.get(sector_id, 6)
    
    if player_level < min_level:
        return False, f"You're too weak for this sector's bandits"
    
    # Calculate attack probability
    # Higher level = higher attack chance (bandits get more ambitious)
    level_above_min = player_level - min_level
    base_chance = 0.15  # 15% base chance
    increased_chance = level_above_min * 0.05  # +5% per level
    total_chance = min(0.75, base_chance + increased_chance)  # Cap at 75%
    
    if random.random() < total_chance:
        return True, f"Bandits sense weakness in Sector {sector_id}"
    
    return False, "Bandits are dormant"

def generate_bandit_encounter(sector_id: int, player_level: int) -> dict:
    """Generate a unique bandit encounter for this sector."""
    narrative = get_sector_narrative(sector_id)
    
    # Pick appropriate bandit for this sector/level
    bandit_types = narrative.get("bandit_types", ["Bandit"])
    bandit_name = random.choice(bandit_types)
    bandit_stats = BANDIT_STATS.get(bandit_name, {"hp": 50, "attack": 15, "loot": {}, "threat": "🟡 MEDIUM"})
    
    # Slightly randomize stats based on player level
    adjusted_hp = int(bandit_stats["hp"] * (1 + (player_level / 50)))
    adjusted_attack = int(bandit_stats["attack"] * (1 + (player_level / 100)))
    
    encounter = {
        "sector_id": sector_id,
        "sector_name": narrative.get("name", "Unknown Sector"),
        "bandit_name": bandit_name,
        "bandit_type": "Enemy",
        "threat_level": bandit_stats.get("threat", "🟡 MEDIUM"),
        "hp": adjusted_hp,
        "attack": adjusted_attack,
        "original_loot": bandit_stats.get("loot", {}),
        "narrative": pick_random_narrative(sector_id),
        "reason": narrative.get("reason_for_attack", "They were here first"),
        "atmosphere": narrative.get("atmosphere", "🌍 Unknown"),
        "mood": narrative.get("mood", "Unknown"),
    }
    
    return encounter

def format_bandit_encounter(encounter: dict) -> str:
    """Format bandit encounter message for player."""
    txt = f"\n{'='*50}\n"
    txt += f"⚔️  *BANDIT ENCOUNTER* ⚔️\n"
    txt += f"{'='*50}\n\n"
    
    # Atmosphere & Mood
    txt += f"{encounter['atmosphere']}\n"
    txt += f"_{encounter['mood']}_\n\n"
    
    # Narrative
    txt += f"{encounter['narrative']}\n\n"
    
    # Enemy Info
    txt += f"*ENEMY:* {encounter['threat_level']} {encounter['bandit_name']}\n"
    txt += f"*SECTOR:* {encounter['sector_name']}\n"
    txt += f"*POWER:* {encounter['attack']} ATK | {encounter['hp']} HP\n\n"
    
    # Reason for Attack
    txt += f"*WHY THEY ATTACK:*\n_{encounter['reason']}_\n\n"
    
    # What's at Stake
    txt += f"*AT STAKE:*\n"
    txt += f"💰 Your base resources\n"
    txt += f"🛡️ Your defensive structures\n"
    txt += f"⚔️ Your reputation\n\n"
    
    txt += f"{'='*50}\n"
    txt += f"*ACTION REQUIRED:*\n"
    txt += f"🛡️ DEFEND - Activate shields & troops\n"
    txt += f"💨 FLEE - Abandon sector (take losses)\n"
    txt += f"⚔️ COUNTER - Prepare for battle\n"
    txt += f"{'='*50}\n"
    
    return txt

def calculate_defense_strength(user: dict) -> int:
    """Calculate player's total defensive power."""
    strength = 0
    
    # Troops count
    military = user.get("military", {})
    troop_count = sum(military.values())
    strength += troop_count * 2  # Each troop = 2 DEF
    
    # Active shield
    if user.get("shield_status") == "ACTIVE":
        strength += 50  # Shield = 50 DEF
    
    # Items/buffs
    buffs = user.get("buffs", {})
    if buffs.get("defensive_item"):
        strength += 30
    
    return max(strength, 1)

def calculate_battle_outcome_vs_bandit(player_defense: int, bandit_attack: int) -> dict:
    """
    Simulate battle between player defense and bandit attack.
    Returns battle result.
    """
    player_health = player_defense * 2
    bandit_health = bandit_attack * 3
    
    rounds = 0
    max_rounds = 10
    
    while rounds < max_rounds and player_health > 0 and bandit_health > 0:
        # Player attacks
        player_damage = random.randint(int(player_defense * 0.7), player_defense)
        bandit_health -= player_damage
        
        # Bandit attacks
        if bandit_health > 0:
            bandit_damage = random.randint(int(bandit_attack * 0.7), bandit_attack)
            player_health -= bandit_damage
        
        rounds += 1
    
    player_won = bandit_health <= 0
    
    return {
        "player_won": player_won,
        "rounds": rounds,
        "player_health_remaining": max(0, player_health),
        "bandit_health_remaining": max(0, bandit_health),
    }

def format_battle_description(user: dict, encounter: dict, result: dict) -> str:
    """Format the battle outcome narrative."""
    victory = result["player_won"]
    sector_narrative = get_sector_narrative(encounter["sector_id"])
    
    txt = f"\n⚔️ *BATTLE REPORT* ⚔️\n"
    txt += f"*{encounter['bandit_name']}* vs *{user.get('username', 'You')}*\n\n"
    
    if victory:
        txt += f"🏆 *VICTORY!*\n\n"
        txt += f"You've defeated the {encounter['bandit_name']}!\n"
        txt += f"_{sector_narrative.get('victory_reward', 'You've proven yourself.')}_\n\n"
        txt += f"💎 *Spoils of War:*\n"
        for res, amount in encounter["original_loot"].items():
            txt += f"  +{amount} {res.upper()}\n"
    else:
        txt += f"💀 *DEFEAT!*\n\n"
        txt += f"The {encounter['bandit_name']} was too strong...\n"
        txt += f"_{sector_narrative.get('defeat_consequence', 'Your base is damaged.')}_\n\n"
        txt += f"📉 *Losses:*\n"
        txt += f"  -30% resources stolen\n"
        txt += f"  -20% troops lost\n"
        txt += f"  -50 base durability\n"
    
    txt += f"\n*Rounds:* {result['rounds']}/10\n"
    return txt
