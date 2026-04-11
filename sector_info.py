"""
🌍 SECTOR INFORMATION SYSTEM
Complete details for all 9 sectors including buffs, perks, hazards, and unique drops.
"""

SECTOR_DETAILS = {
    1: {
        "name": "Badlands-8",
        "emoji": "🏜️",
        "resources": ["wood", "bronze"],
        "buffs": {"wood_gathering": 1.2, "bronze_gathering": 1.15},
        "perks": [
            "✅ Easy entry point - great for beginners",
            "✅ 1.2x wood gathering bonus",
            "✅ 1.15x bronze gathering bonus",
        ],
        "hazards": [
            "⚠️ Low-level monsters",
            "⚠️ Dust storms reduce visibility",
        ],
        "unique_drops": ["📦 Wooden Crate", "🛡️ Basic Shield", "💰 Bronze Coins"],
        "difficulty": "⭐ Easy",
        "recommended_level": "1+",
    },
    2: {
        "name": "Crimson Wastes",
        "emoji": "🔴",
        "resources": ["bronze", "iron"],
        "buffs": {"bronze_gathering": 1.3, "iron_gathering": 1.1},
        "perks": [
            "✅ 1.3x bronze gathering bonus",
            "✅ 1.1x iron gathering bonus",
            "✅ Rare bronze drops",
        ],
        "hazards": [
            "⚠️ Fire damage risk during mining",
            "⚠️ Medium-level raiders",
        ],
        "unique_drops": ["🧱 Bronze Ore", "⚡ Fire Stone", "💎 Crimson Gem"],
        "difficulty": "⭐⭐ Normal",
        "recommended_level": "3+",
    },
    3: {
        "name": "Obsidian Peaks",
        "emoji": "⛰️",
        "resources": ["iron", "diamond"],
        "buffs": {"iron_gathering": 1.4, "diamond_gathering": 1.25},
        "perks": [
            "✅ 1.4x iron gathering bonus",
            "✅ 1.25x diamond gathering bonus",
            "✅ Premium drops",
        ],
        "hazards": [
            "⚠️ Avalanche risk",
            "⚠️ Strong hostile forces",
            "⚠️ Extreme cold slows mining",
        ],
        "unique_drops": ["⚒️ Iron Ore", "💎 Obsidian Diamond", "👑 Rare Crown Fragment"],
        "difficulty": "⭐⭐⭐ Hard",
        "recommended_level": "8+",
    },
    4: {
        "name": "Shattered Valley",
        "emoji": "💔",
        "resources": ["bronze", "wood", "iron"],
        "buffs": {"all_resources": 1.15},
        "perks": [
            "✅ 1.15x all resources gathering",
            "✅ Balanced resource collection",
            "✅ Great for mixed mining",
        ],
        "hazards": [
            "⚠️ Unstable ground",
            "⚠️ PvP hotspot (player attacks common)",
        ],
        "unique_drops": ["🎁 Mixed Crate", "🗡️ Warrior's Blade", "🛡️ Balanced Shield"],
        "difficulty": "⭐⭐ Normal",
        "recommended_level": "5+",
    },
    5: {
        "name": "Frozen Abyss",
        "emoji": "❄️",
        "resources": ["iron", "diamond"],
        "buffs": {"iron_gathering": 1.35, "diamond_gathering": 1.2},
        "perks": [
            "✅ 1.35x iron gathering bonus",
            "✅ 1.2x diamond gathering bonus",
            "✅ Frozen treasures",
        ],
        "hazards": [
            "⚠️ Extreme freezing conditions",
            "⚠️ Resource deterioration over time",
            "⚠️ Heavy attacks from ice creatures",
        ],
        "unique_drops": ["❄️ Frozen Core", "💎 Ice Diamond", "🧊 Permafrost Ore"],
        "difficulty": "⭐⭐⭐ Hard",
        "recommended_level": "10+",
    },
    6: {
        "name": "Molten Gorge",
        "emoji": "🔥",
        "resources": ["diamond", "relics"],
        "buffs": {"diamond_gathering": 1.5, "relics_gathering": 1.4},
        "perks": [
            "✅ 1.5x diamond gathering bonus",
            "✅ 1.4x relics gathering bonus",
            "✅ Extremely valuable drops",
            "✅ Legendary items here",
        ],
        "hazards": [
            "⚠️ EXTREME heat damage",
            "⚠️ Fire explosions during mining",
            "⚠️ Deadly lava flows",
            "⚠️ Boss-tier monsters",
        ],
        "unique_drops": ["🌋 Lava Diamond", "🏺 Ancient Relic", "👑 Molten Crown"],
        "difficulty": "⭐⭐⭐⭐⭐ EXTREME",
        "recommended_level": "15+",
    },
    7: {
        "name": "Twilight Marshes",
        "emoji": "🌙",
        "resources": ["wood", "relics"],
        "buffs": {"wood_gathering": 1.25, "relics_gathering": 1.2},
        "perks": [
            "✅ 1.25x wood gathering bonus",
            "✅ 1.2x relics gathering bonus",
            "✅ Mysterious artifacts",
        ],
        "hazards": [
            "⚠️ Fog of war (reduced visibility)",
            "⚠️ Cursed lands (debuffs)",
            "⚠️ Undead creatures",
        ],
        "unique_drops": ["🌙 Moonwood", "👻 Spirit Relic", "🔮 Twilight Crystal"],
        "difficulty": "⭐⭐⭐ Hard",
        "recommended_level": "12+",
    },
    8: {
        "name": "Silent Forest",
        "emoji": "🌲",
        "resources": ["wood", "bronze", "diamond"],
        "buffs": {"wood_gathering": 1.3, "bronze_gathering": 1.15, "diamond_gathering": 1.1},
        "perks": [
            "✅ 1.3x wood gathering",
            "✅ 1.15x bronze gathering",
            "✅ 1.1x diamond gathering",
            "✅ Diverse drops",
        ],
        "hazards": [
            "⚠️ Dense forests block paths",
            "⚠️ Wild animals",
            "⚠️ Trap zones",
        ],
        "unique_drops": ["🪵 Ancient Wood", "🐾 Beast Hide", "💚 Forest Gem"],
        "difficulty": "⭐⭐ Normal",
        "recommended_level": "7+",
    },
    9: {
        "name": "Void Canyon",
        "emoji": "🌑",
        "resources": ["relics", "diamond", "iron"],
        "buffs": {"relics_gathering": 1.6, "diamond_gathering": 1.4, "iron_gathering": 1.2},
        "perks": [
            "✅ 1.6x relics gathering bonus (HIGHEST)",
            "✅ 1.4x diamond gathering bonus",
            "✅ 1.2x iron gathering bonus",
            "✅ THE most valuable sector",
            "✅ Cosmic items unique to void",
        ],
        "hazards": [
            "⚠️ EXTREME: Void corruption damage",
            "⚠️ Reality distortions",
            "⚠️ Eldritch horrors",
            "⚠️ Instant death zones",
            "⚠️ Only for the bravest legends",
        ],
        "unique_drops": ["🌑 Void Shard", "💫 Cosmic Dust", "👑 Celestial Relic"],
        "difficulty": "⭐⭐⭐⭐⭐ LEGENDARY",
        "recommended_level": "20+",
    }
}

def get_sector_info(sector_id: int) -> dict:
    """Get full information about a sector."""
    return SECTOR_DETAILS.get(sector_id, {})

def format_sector_display(sector_id: int, divider_fn=None) -> str:
    """Format sector information for display."""
    sector = get_sector_info(sector_id)
    if not sector:
        return "❌ Sector not found"
    
    if divider_fn is None:
        from formatting import divider
        divider_fn = divider
    
    txt = f"{divider_fn()}\n🌍 *SECTOR {sector_id}: {sector['emoji']} {sector['name'].upper()}* 🌍\n{divider_fn()}\n\n"
    
    # Difficulty & Recommended Level
    txt += f"Difficulty: {sector['difficulty']}\n"
    txt += f"Recommended: {sector['recommended_level']}\n\n"
    
    # Resources
    txt += f"*📦 Resources Available:*\n"
    txt += f"{', '.join(sector['resources'])}\n\n"
    
    # Gathering Buffs
    txt += f"*⬆️ Gathering Bonuses:*\n"
    for buff_name, multiplier in sector.get('buffs', {}).items():
        if multiplier >= 1.5:
            prefix = "🔥"
        elif multiplier >= 1.2:
            prefix = "✅"
        else:
            prefix = "📈"
        txt += f"{prefix} x{multiplier:.2f} {buff_name}\n"
    txt += "\n"
    
    # Perks
    txt += f"*✨ PERKS:*\n"
    for perk in sector['perks']:
        txt += f"{perk}\n"
    txt += "\n"
    
    # Hazards
    txt += f"*⚠️ HAZARDS:*\n"
    for hazard in sector['hazards']:
        txt += f"{hazard}\n"
    txt += "\n"
    
    # Unique Drops
    txt += f"*🎁 UNIQUE DROPS IN THIS SECTOR:*\n"
    for drop in sector['unique_drops']:
        txt += f"• {drop}\n"
    
    txt += f"\n{divider_fn()}"
    return txt
