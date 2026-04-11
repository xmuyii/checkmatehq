"""
immersive_systems.py — Deep Psychological & Narrative Systems
=============================================================
The 64 is not a game. It is a DIMENSION.
Every element provokes contemplation before action.
The GameMaster is always watching.
"""

from datetime import datetime
from typing import Dict, Optional
import random

# ══════════════════════════════════════════════════════════════════
#  THE ASSASSIN — 1M XP LEGENDARY EVENT
# ══════════════════════════════════════════════════════════════════

ASSASSIN_PROFILE = {
    "name":          "⚫ THE VOID ASSASSIN",
    "level":         99,
    "hp":            5000,
    "attack":        350,
    "xp_reward":     1_000_000,
    "silver_reward": 50_000,
    "rarity":        "COSMIC",
    "description":   "A being born from the spaces between worlds.",
    "spawn_hours":   72,
}

ASSASSIN_APPEARANCE = """
╔══════════════════════════════════════════════════════════╗
║          ⚫  THE  VOID  ASSASSIN  ⚫                    ║
║          Spawn Rate: Every 72 Hours                      ║
║          Reward:    1,000,000 XP + 50,000 Silver         ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║         ██████████  ████  ██████████                    ║
║         ██░░░░░░████████████░░░░░░██                    ║
║         ██░░█░░░████████████░█░░░░██                    ║
║         ██░░███░████████████░███░░██                    ║
║         ██████░░░░███████░░░░██████                     ║
║         ████████████░███████████████                    ║
║                                                          ║
║  When it moves, the air itself screams.                  ║
║  Those who face it describe one sensation: finality.     ║
║                                                          ║
║  ⚠️  First player to defeat it claims 1,000,000 XP      ║
║      This entity appears ONCE every 3 days.              ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
"""


# ══════════════════════════════════════════════════════════════════
#  OBELISK — The Portal Narrative
# ══════════════════════════════════════════════════════════════════

OBELISK_GATEWAY = """
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║                     ╔═════════╗                         ║
║                   ╔═╩════╤════╩═╗                       ║
║                   ║  ⬢ ⬢ ⬢    ║                       ║
║                ╔══╩══════╤══════╩══╗                    ║
║                ║  ⬢ ⬢ ⬢ ⬢ ⬢ ⬢  ║                    ║
║             ╔══╩─────────╤─────────╩══╗                 ║
║             ║██╪████████╪████████╪██║                  ║
║             ║████████████╪████████████║                  ║
║             ╚═════════════╤════════════╝                 ║
║                          ╚╧╝                             ║
║                                                          ║
║             🌌  THE OBELISK 🌌                          ║
║       GATEWAY TO ANOTHER DIMENSION                       ║
║                                                          ║
║  In a world where you possess no power...                ║
║  Here — you are a GOD.                                   ║
║                                                          ║
║  Your cunning defeats enemies.                           ║
║  Your strategy shapes reality.                           ║
║  Your will defines the battlefield.                      ║
║                                                          ║
║            [ ENTER THE OBELISK ]                        ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
"""


# ══════════════════════════════════════════════════════════════════
#  BASE DESTRUCTION — Visceral, Irreversible Loss
# ══════════════════════════════════════════════════════════════════

BURNED_BASE_IMAGERY = """
░▒▓████████████████████████████████████████░▒▓
░▒▓                                        ░▒▓
░▒▓       🔥  YOUR BASE IS BURNING 🔥     ░▒▓
░▒▓                                        ░▒▓
░▒▓████████████████████████████████████████░▒▓

        ░░▓▓██████▓▓░░
       ░▒▓████████████▓▒░
       ▒▓██ 🔥███🔥███▓
      ░▓███   ███████  █████▓░
      ▓████   ══════   ██████
     ░███░         │         ░███░
      ░██████░═╤═══╧═╤░██████░
        ░░████████████████░░

    EVERYTHING YOU BUILT... REDUCED TO ASH.
    ━━━━━━━━━━━━━━━━━━━━━━━━━━
    ▸ -30% Base Resources Lost
    ▸ -20% Troops Eliminated
    ▸ -50 Base Durability

    The smell of burning wood fills the air.
    Watchtowers crumble. Your dominion... erased.

    Your enemy stands victorious.
    THE RAID IS IRREVERSIBLE.

    What will you do now?
"""

DESTROYED_BASE_TEMPLATE = (
    "╔══════════════════════════════════════════╗\n"
    "║  🔥  YOUR BASE HAS BEEN RAIDED  🔥      ║\n"
    "╠══════════════════════════════════════════╣\n"
    "║  Attacker: {attacker_name:<28} ║\n"
    "║  Time    : {timestamp:<28} ║\n"
    "╠══════════════════════════════════════════╣\n"
    "║  ▸ Resources taken                        ║\n"
    "║  ▸ Troops casualties                      ║\n"
    "╠══════════════════════════════════════════╣\n"
    "║  [⚡ SHIELD]  [💢 REVENGE]  [🔮 SCOUT]  ║\n"
    "╚══════════════════════════════════════════╝"
)


# ══════════════════════════════════════════════════════════════════
#  SECTOR CONSCIOUSNESS — Psychological identity of each zone
# ══════════════════════════════════════════════════════════════════

SECTOR_CONSCIOUSNESS = {
    1: {
        "name":          "🏜️  BADLANDS-8: The Crucible",
        "consciousness": "Raw. Primal. Where survivors are forged.",
        "feeling":       "You feel the desert heat. Exposed. Vulnerable. ALIVE.",
        "welcome":       "The Badlands do not welcome you. They CHALLENGE you.",
        "color":         "🟧 ORANGE — Harsh, unforgiving, burning",
    },
    2: {
        "name":          "🔴 CRIMSON WASTES: The Proving Grounds",
        "consciousness": "Aggressive clans clash. Dominance written in blood.",
        "feeling":       "Adrenaline courses. You are being HUNTED. You are HUNTING.",
        "welcome":       "The Fire Clans tolerate no trespassers. Prove your worth or burn.",
        "color":         "🔴 RED — Violent, passionate, consuming",
    },
    3: {
        "name":          "⛰️  OBSIDIAN PEAKS: The Isolated Throne",
        "consciousness": "Only the merciless survive here. Kindness is death.",
        "feeling":       "Dread. Isolation. You are ALONE against the universe.",
        "welcome":       "The Peaks are silent. That silence has teeth.",
        "color":         "⚫ BLACK — Dark, deadly, absolute",
    },
    4: {
        "name":          "💔 SHATTERED VALLEY: The Warzone",
        "consciousness": "Chaos reigns. Alliances form and SHATTER. Everyone lies.",
        "feeling":       "Paranoia. Betrayal. Trust NO ONE. Every decision matters.",
        "welcome":       "The Valley has no rules. There never were any.",
        "color":         "🟣 PURPLE — Chaotic, unpredictable, mad",
    },
    5: {
        "name":          "❄️  FROZEN ABYSS: The Addictive Cold",
        "consciousness": "Beautiful and deadly. You keep coming back for more.",
        "feeling":       "Addiction pulses. Just one more battle. One more conquest.",
        "welcome":       "The Abyss whispers your name. It always knew you'd return.",
        "color":         "🔵 BLUE — Hypnotic, addictive, inescapable",
    },
    6: {
        "name":          "🔥 MOLTEN GORGE: The Apocalypse",
        "consciousness": "Reality bends here. The strong become GODS.",
        "feeling":       "POWER. Pure, intoxicating, overwhelming power.",
        "welcome":       "Only legends reach the Gorge. Whether you survive it is another question.",
        "color":         "🟠 FIRE RED — Apocalyptic, godlike, transcendent",
    },
    7: {
        "name":          "🌙 TWILIGHT MARSHES: The Dream Realm",
        "consciousness": "Is this real? Who can tell anymore?",
        "feeling":       "Surreal. Dream-like. Your mind bends with each choice.",
        "welcome":       "Lost souls wander here. Now you are one of them.",
        "color":         "🟣 VIOLET — Mysterious, dreamlike, ethereal",
    },
    8: {
        "name":          "🌲 SILENT FOREST: The Ancient Balance",
        "consciousness": "Honor matters here. Skill determines fate.",
        "feeling":       "Respect. Clarity. You face worthy opponents as equals.",
        "welcome":       "The Forest watches. It always watches.",
        "color":         "🟢 GREEN — Fair, honorable, balanced",
    },
    9: {
        "name":          "🌑 VOID CANYON: The Cosmic Horror",
        "consciousness": "Things that should not exist. Winners become LEGENDS.",
        "feeling":       "Transcendence. You touch something BEYOND human.",
        "welcome":       "Few reach here. Fewer still return.",
        "color":         "⚫ VOID — Cosmic, legendary, incomprehensible",
    },
}

def format_sector_arrival(sector_id: int, player_name: str) -> str:
    """Atmospheric sector arrival message."""
    sector = SECTOR_CONSCIOUSNESS.get(sector_id, {})
    if not sector:
        return f"📍 You arrive in Sector {sector_id}."
    return (
        f"📍 *SECTOR ARRIVAL*\n"
        f"{'═' * 32}\n"
        f"*{sector['name']}*\n\n"
        f"_{sector['consciousness']}_\n\n"
        f"💭 {sector['feeling']}\n\n"
        f"🃏 *GameMaster:* \"{sector['welcome']}, {player_name}.\"\n"
        f"{'═' * 32}"
    )


# ══════════════════════════════════════════════════════════════════
#  INFLUENCE SYSTEM — Reputation shapes the world
# ══════════════════════════════════════════════════════════════════

INFLUENCE_TIERS = {
    (0,    4):    ("👤 UNKNOWN",    "You go unnoticed. Nobody fears what they don't know."),
    (5,   14):    ("🪖 RECRUIT",    "Your name surfaces in whispers. Keep going."),
    (15,  29):    ("⚔️ WARRIOR",    "Enemies hesitate before attacking you."),
    (30,  49):    ("🔥 VETERAN",    "Players in your sector know your reputation."),
    (50,  74):    ("👑 CHAMPION",   "Your very presence on a leaderboard shifts behavior."),
    (75,  99):    ("💀 TERROR",     "Your name alone breaks morale. Alliances form against you."),
    (100, 9999):  ("⚫ VOID GOD",   "You ARE the game. Others exist to oppose you."),
}

def get_influence_tier(level: int) -> tuple:
    for (low, high), (title, description) in INFLUENCE_TIERS.items():
        if low <= level <= high:
            return title, description
    return "⚫ VOID GOD", "You transcend measurement."


# ══════════════════════════════════════════════════════════════════
#  VICTORY & DEFEAT SCREENS
# ══════════════════════════════════════════════════════════════════

def format_victory_ascension(winner: str, loser: str, xp_gained: int,
                               resources: Dict) -> str:
    resource_lines = []
    for res, amt in resources.items():
        if amt > 0:
            resource_lines.append(f"  ✦ +{amt:,} {res.capitalize()}")
    resource_block = "\n".join(resource_lines) if resource_lines else "  ✦ Honor earned"

    return (
        f"╔══════════════════════════════════════════╗\n"
        f"║        🏆  ASCENSION  🏆                 ║\n"
        f"╠══════════════════════════════════════════╣\n"
        f"║                                          ║\n"
        f"║  {winner.upper()[:38]:<38} ║\n"
        f"║  EMERGES VICTORIOUS                      ║\n"
        f"║                                          ║\n"
        f"║  {loser}'s defenses crumble.             ║\n"
        f"║  Their will BREAKS.                      ║\n"
        f"║                                          ║\n"
        f"╠══════════════════════════════════════════╣\n"
        f"║  ✨ +{xp_gained:,} XP                         ║\n"
        f"╠══════════════════════════════════════════╣\n"
        f"║  SPOILS OF WAR:                          ║\n"
        f"{resource_block}\n"
        f"╠══════════════════════════════════════════╣\n"
        f"║                                          ║\n"
        f"║  Your enemies speak your name in FEAR.   ║\n"
        f"║  What sector will you conquer next?       ║\n"
        f"║                                          ║\n"
        f"╚══════════════════════════════════════════╝"
    )


def format_defeat_devastation(loser: str, winner: str) -> str:
    return (
        f"╔══════════════════════════════════════════╗\n"
        f"║        💀  ANNIHILATION  💀              ║\n"
        f"╠══════════════════════════════════════════╣\n"
        f"║                                          ║\n"
        f"║  {loser.upper()[:38]:<38} ║\n"
        f"║  HAS BEEN DEFEATED                       ║\n"
        f"║                                          ║\n"
        f"║  Your defenses CRUMBLED.                 ║\n"
        f"║  Your troops SCATTERED.                  ║\n"
        f"║  Your will... SHATTERED.                 ║\n"
        f"║                                          ║\n"
        f"║  {winner} claims your territory.         ║\n"
        f"║                                          ║\n"
        f"╠══════════════════════════════════════════╣\n"
        f"║  This is NOT the end.                    ║\n"
        f"║                                          ║\n"
        f"║  [⚡ SHIELD]   [💢 REVENGE]              ║\n"
        f"║  [🔮 SCOUT]    [🏰 REBUILD]              ║\n"
        f"║                                          ║\n"
        f"║  Your vengeance will be ABSOLUTE.        ║\n"
        f"║                                          ║\n"
        f"╚══════════════════════════════════════════╝"
    )


def format_battle_intensity(player_name: str, enemy_name: str, sector: str) -> str:
    return (
        f"╔══════════════════════════════════════════╗\n"
        f"║        ⚔️  BATTLE OF WILLS  ⚔️           ║\n"
        f"╠══════════════════════════════════════════╣\n"
        f"║  {player_name.upper()[:18]:<18} vs {enemy_name.upper()[:14]:<14} ║\n"
        f"║  📍 {sector[:38]:<38} ║\n"
        f"╠══════════════════════════════════════════╣\n"
        f"║                                          ║\n"
        f"║  The air CRACKLES with energy.           ║\n"
        f"║  Every movement is CALCULATED.           ║\n"
        f"║  Every decision is FINAL.                ║\n"
        f"║                                          ║\n"
        f"║  This is not a game. This is REALITY.    ║\n"
        f"║  One rises. One falls into OBLIVION.     ║\n"
        f"║                                          ║\n"
        f"╚══════════════════════════════════════════╝"
    )


# ══════════════════════════════════════════════════════════════════
#  GAMEMASTER — Dynamic Situational Commentary
# ══════════════════════════════════════════════════════════════════

GM_COMMENTS = {
    "first_login": [
        "\"Well. Another soul stumbles into my domain. Predictable.\"",
        "\"Oh, you actually showed up. Color me... mildly surprised.\"",
        "\"I've seen thousands walk through that door. Most don't last.\"",
    ],
    "level_up": [
        "\"Growing stronger. Slowly. Like a very cautious plant.\"",
        "\"You leveled up. I'll acknowledge it. Don't let it go to your head.\"",
        "\"Power. You're beginning to accumulate it. Interesting.\"",
    ],
    "attack_win": [
        "\"Decisive. Clean. You're developing instincts.\"",
        "\"They didn't see you coming. Smart.\"",
        "\"Another falls before you. The sectors remember.\"",
    ],
    "attack_lose": [
        "\"Humbled. Good. Hubris is the first casualty of weakness.\"",
        "\"They were stronger. For now. The operative phrase.\"",
        "\"You lost. Now the question is — what do you do with that?\"",
    ],
    "revenge_achieved": [
        "\"Blood debt: satisfied. How does vengeance taste?\"",
        "\"The universe remembers debts. You just collected one.\"",
        "\"They thought you'd forget. You didn't.\"",
    ],
    "shield_activated": [
        "\"A shield. Sensible. Hiding behind it... less so.\"",
        "\"Protected. For now. But shields don't last forever.\"",
        "\"Smart move. Your enemies will find another way.\"",
    ],
    "long_absence": [
        "\"You were gone. I noticed the silence.\"",
        "\"The sectors shifted while you were away. Catch up.\"",
        "\"Did you think taking a break would save you? How naive.\"",
    ],
    "resource_milestone": [
        "\"Wealth accumulates. Power follows. Use it.\"",
        "\"Your coffers grow heavy. Your enemies notice.\"",
        "\"Resources are potential. What you build with them defines you.\"",
    ],
}

def get_gm_comment(event: str) -> str:
    options = GM_COMMENTS.get(event, [
        "\"The game continues. As it always does.\"",
    ])
    return f"🃏 *GameMaster:* {random.choice(options)}"


# ══════════════════════════════════════════════════════════════════
#  ACHIEVEMENT SYSTEM — Milestone events that matter
# ══════════════════════════════════════════════════════════════════

ACHIEVEMENTS = {
    "first_blood": {
        "name":   "🩸 FIRST BLOOD",
        "desc":   "Win your first PvP battle",
        "reward": "200 XP + 50 silver",
        "gm":     "\"You shed your first blood. The sectors acknowledge the shift.\"",
    },
    "revenge_served": {
        "name":   "💢 BLOOD DEBT PAID",
        "desc":   "Successfully execute a revenge attack",
        "reward": "150 XP + 100 silver",
        "gm":     "\"Vengeance served cold. As it should be.\"",
    },
    "untouchable": {
        "name":   "🛡️ UNTOUCHABLE",
        "desc":   "Block 5 attacks with your shield",
        "reward": "300 XP",
        "gm":     "\"They keep hitting a wall. That wall is you.\"",
    },
    "warlord_trained": {
        "name":   "💀 WARLORD FORGED",
        "desc":   "Train your first Warlord unit",
        "reward": "500 XP",
        "gm":     "\"A legend joins your ranks. The game changes.\"",
    },
    "void_survivor": {
        "name":   "🌑 VOID SURVIVOR",
        "desc":   "Survive 10 battles in Sector 9",
        "reward": "1000 XP + 500 silver",
        "gm":     "\"The Void tried to claim you. It failed. Remarkable.\"",
    },
    "intelligence_master": {
        "name":   "🕵️ SHADOW BROKER",
        "desc":   "Successfully scout 10 players",
        "reward": "200 XP",
        "gm":     "\"Information is power. You understand this now.\"",
    },
}

def format_achievement_unlock(achievement_id: str) -> str:
    ach = ACHIEVEMENTS.get(achievement_id)
    if not ach:
        return ""
    return (
        f"🏅 *ACHIEVEMENT UNLOCKED!*\n"
        f"{'═' * 32}\n"
        f"{ach['name']}\n"
        f"_{ach['desc']}_\n"
        f"🎁 *Reward:* {ach['reward']}\n"
        f"{'─' * 32}\n"
        f"🃏 *GameMaster:* {ach['gm']}"
    )
