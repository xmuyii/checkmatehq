"""
🎮 BOTFATHER INLINE GAME COMMANDS - The 64
===========================================

This file contains the command list to paste into BotFather for setting up
the game's inline command buttons and descriptions.

HOW TO USE:
1. Open Telegram and search for @BotFather
2. Send: /setcommands
3. Select your bot
4. Copy the commands from the COMMANDS_LIST section below
5. Paste them into the chat with BotFather

COMPLIANCE NOTE:
✅ All commands comply with Telegram's Bot API terms
✅ No external links or ads
✅ No payment requests on custom URLs
✅ Privacy-safe (no cookie tracking)
✅ No third-party data transfers
"""

# ═══════════════════════════════════════════════════════════════════════════
#  BOTFATHER COMMANDS LIST
# ═══════════════════════════════════════════════════════════════════════════

COMMANDS_LIST = """
start - ▶️ Begin your journey in The 64
fusion - 🎮 Play the Word Fusion game (group only)
tower - 🏰 Defend your tower from bandits
help - 📖 View all commands and gameplay guide
profile - 👤 Check your stats and achievements
leaderboard - 🏆 View weekly and all-time rankings
inventory - 🎒 Manage your items and resources
challenges - 🎯 View weekly challenges and progress
shield - 🛡️ Manage your base shield
military - ⚔️ Manage your troops and army
teleport - 🌀 Travel to different sectors and face bandits
sectors - 🌍 View information about all 9 sectors
mine - ⛏️ Mine resources in your current sector
attack - ⚔️ Attack another player's base
revenge - 💢 Take revenge on a player
bandit - 👹 View current bandit threat in sector
defend - 🛡️ Prepare defenses against bandits
fleece - 💰 Collect tribute from conquered territories
battle_items - 🗡️ Purchase and use battle items
base - 🏛️ View and upgrade your base
research - 🔬 Unlock new technologies
clan - 👥 Manage alliance and clan features
settings - ⚙️ Customize game preferences
stats - 📊 View detailed game statistics
skills - 💪 View and train character skills
arena - 🥊 Competitive 1v1 battles
quests - 📜 Daily and weekly objectives
rewards - 🎁 Claim daily rewards and bonuses
market - 🛒 Trade with other players
events - 📢 View active events and tournaments
tutorial - 🎓 Replay the onboarding tutorial
"""

# ═══════════════════════════════════════════════════════════════════════════
#  GAME MECHANICS DOCUMENTATION
# ═══════════════════════════════════════════════════════════════════════════

GAME_OVERVIEW = """
THE 64 - Strategic Territory Control Game on Telegram
═════════════════════════════════════════════════════

CORE GAMEPLAY:
• Word Fusion Challenge (60 seconds) - Combine base word fragments
• Territory Control - Capture and hold sector territories
• Resource Management - Gather wood, bronze, iron, diamond, relics
• Base Defense - Fortify against random bandit attacks
• Strategic Combat - Attack other players' bases

🎯 CORE FEATURES:

1. WORD FUSION GAME (Group Activity)
   └─ Minimum 3-letter words from base fragments
   └─ Points based on word length
   └─ Combo multiplier (increases on consecutive wins)
   └─ Combo milestone bonuses at 10, 25, 50, 110, 250 wins
   └─ Daily login streaks with food rewards
   └─ Rare drops (crates with XP rewards)

2. RESOURCE GATHERING SYSTEM
   ├─ Wood (gathered in early sectors)
   ├─ Bronze (mid-tier resource)
   ├─ Iron (mid-high tier resource)
   ├─ Diamond (valuable resource)
   └─ Relics (legendary resource from high-tier sectors)

3. SECTOR SYSTEM (9 Unique Territories)
   ├─ Sector 1: Badlands-8 (Easy, Low loot)
   ├─ Sector 2: Crimson Wastes (Medium heat)
   ├─ Sector 3: Obsidian Peaks (Hard, Brutal)
   ├─ Sector 4: Shattered Valley (Chaotic, PvP hotspot)
   ├─ Sector 5: Frozen Abyss (Addictive, Dangerous)
   ├─ Sector 6: Molten Gorge (EXTREME, Legendary items)
   ├─ Sector 7: Twilight Marshes (Mysterious, Hypnotic)
   ├─ Sector 8: Silent Forest (Fair, Honorable battles)
   └─ Sector 9: Void Canyon (LEGENDARY, Cosmic horrors)

4. BANDIT ENCOUNTER SYSTEM (LEVEL 6+)
   ├─ Random CPU enemies attack when teleporting to sectors
   ├─ Level 6+ players enter the bandit era
   ├─ Level 1-5 are invisible to bandits
   ├─ Each sector has unique enemy types and narratives
   ├─ Battle outcome depends on:
   │  ├─ Your troop count
   │  ├─ Active shield status
   │  ├─ Battle items equipped
   │  └─ Enemy tier/power level
   ├─ Victory: Earn loot + XP + points
   ├─ Defeat: Lose 30% resources + 20% troops
   └─ Flee: Lose 15% resources + reputation

5. WEEKLY CHALLENGES (Achievement System)
   ├─ 📈 Climber: Gain 5000+ XP
   ├─ 💰 Banker: Accumulate 1000+ silver
   ├─ 🏆 Top 10: Rank in top 10 leaderboard
   ├─ 🔥 Streak Master: 10-day login streak
   ├─ 👑 King's Ransom: Steal 500+ resources in raids
   └─ 🔤 Seven-Letter Master: 10 consecutive 7-letter words

6. MULTIPLIER SYSTEM
   ├─ XP multipliers (earned from crates)
   ├─ Silver multipliers (earned from events)
   ├─ Sector gathering multipliers (1.15x - 2.0x)
   ├─ Combo multiplier (increases every 10 wins)
   └─ Active duration: Uses count down on each word win

7. MILITARY & COMBAT
   ├─ Unit Types: Pawns, Knights, Bishops, Rooks, Queens, Kings
   ├─ Training time varies by unit (15s - 120s per unit)
   ├─ Resource costs vary by unit tier
   ├─ Combat calculation: Troops vs Enemy stats
   └─ Territory control grants mining bonuses

8. SHIELD SYSTEM (Defense Mechanics)
   ├─ States: UNPROTECTED (default) → ACTIVE (protected) → DISRUPTED (attacked)
   ├─ Activation: Player manually activates when desired
   ├─ Deactivation: Automatic when attacking, or manual
   ├─ Disruption: Triggered during player attacks against you
   ├─ Restoration: Automatic after 2 hours (DISRUPTED → ACTIVE)
   ├─ Battle Impact: +50 DEF when active
   └─ Free shields: 3 given to each player on game start

NARRATIVE ELEMENTS:

Each sector tells a story. When players reach a sector, they experience
the region's unique atmosphere and character:

• Badlands-8 🏜️: Gritty, survival-focused, lawless desert
• Crimson Wastes 🔴: Fast-paced, aggressive fire clans
• Obsidian Peaks ⛰️: Unforgiving, brutal mountain assassins
• Shattered Valley 💔: Chaotic multiplayer warzone
• Frozen Abyss ❄️: Addictive yet desperate ice realm
• Molten Gorge 🔥: Epic, apocalyptic ultimate test
• Twilight Marshes 🌙: Mysterious, hypnotic, dreamlike
• Silent Forest 🌲: Fair, wild, honorable battles
• Void Canyon 🌑: Cosmic, reality-bending, legendary

ENEMY ENCOUNTERS:

When entering a sector at Level 6+:
• 15-75% chance of random bandit encounter
• Enemy strength scales with player level
• Unique enemy types per sector
• Narrative-driven combat experience
• Strategic use of items and troops required
• Victory broadcasts achievements to group
• Defeat broadcasts throughout community

PROGRESSION TIERS:

Level 1-5:   Starting phase, no bandits
Level 6-10:  Bandit era begins, entry-level enemies
Level 11-20: Advanced battles, high-value loot
Level 20+:   Legendary tier, cosmic horrors

MONETIZATION (Privacy-Compliant):

✅ The bot complies with Telegram's unified monetization (coming soon)
✅ No ads or external links
✅ No payment requests on custom URLs
✅ No cookies or third-party data sharing
✅ All player data remains private and secure

STRATEGIC GAMEPLAY ELEMENTS:

1. Resource Management
   • Balance spending on troops vs reserves
   • Strategic resource allocation per sector
   • Hoarding vs active trading

2. Base Defense Strategy
   • Shield placement timing
   • Troop positioning
   • Battle item selection

3. Territory Control
   • Sector selection for mining bonuses
   • Risk/reward of high-tier sectors
   • Coalition building for control

4. Offensive Strategy
   • 50% loot steal on victory
   • Revenge window after defeat
   • Reputation system

5. Community Dynamics
   • Public victory/defeat broadcasts
   • Leaderboard competition
   • Alliance formation and clan wars

COMPELLING FEATURES FOR ENGAGEMENT:

✨ Dopamine Hits:
   • Rare drop notifications
   • Combo milestone celebrations
   • Victory broadcasts
   • Leaderboard position changes
   • Challenge completions
   • Level-up announcements
   • Bandit defeats

🎯 Attention Grabbing:
   • Random encounter notifications
   • Time-limited challenges
   • Limited-time offers
   • Sector-specific narratives
   • Unique enemy encounters
   • Streaming/broadcasting of battles

🔥 Addictive Mechanics:
   • Streak system (consecutive logins)
   • Combo multiplier (continuous wins)
   • Resource accumulation (never stops)
   • Level progression (always increasing)
   • Weekly challenges (recurring goals)
   • Territory control (persistent advantage)

🎭 Narrative Engagement:
   • Unique sector atmospheres
   • Enemy-specific storylines
   • Victory/defeat consequences
   • Player agency in outcomes
   • Community events
   • Dynamic storytelling
"""

# ═══════════════════════════════════════════════════════════════════════════
#  INLINE KEYBOARD GAME COMMANDS
# ═══════════════════════════════════════════════════════════════════════════

INLINE_BUTTON_COMMANDS = {
    "game_main_menu": {
        "buttons": [
            ["🎮 Play Game", "🏆 Leaderboard"],
            ["📖 Help", "👤 Profile"],
            ["🌀 Teleport", "🛡️ Defend"]
        ]
    },
    "sector_selection": {
        "buttons": [
            ["🏜️ Badlands", "🔴 Wastes", "⛰️ Peaks"],
            ["💔 Valley", "❄️ Abyss", "🔥 Gorge"],
            ["🌙 Marshes", "🌲 Forest", "🌑 Void"]
        ]
    },
    "combat_options": {
        "buttons": [
            ["⚔️ Attack", "🛡️ Defend", "💨 Flee"],
            ["🗡️ Items", "📊 Stats"]
        ]
    },
    "resource_menu": {
        "buttons": [
            ["⛏️ Mine", "🎁 Inventory", "💰 Resources"],
            ["📈 Upgrades", "🏛️ Base"]
        ]
    }
}

print("""
╔═══════════════════════════════════════════════════════════════╗
║     THE 64 - BOTFATHER CONFIGURATION READY                   ║
║                                                               ║
║  To use this configuration:                                  ║
║  1. Message @BotFather on Telegram                           ║
║  2. Send: /setcommands                                       ║
║  3. Select your bot                                          ║
║  4. Copy commands from COMMANDS_LIST section                ║
║  5. Paste into Telegram chat with BotFather                 ║
║                                                               ║
║  All features are Telegram-compliant and support privacy    ║
╚═══════════════════════════════════════════════════════════════╝
""")
