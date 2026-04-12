# -*- coding: utf-8 -*-
"""
word_fusion_immersive.py — Make Word Fusion Feel Like Real Resource Gathering
Connects the word game to the dimension of consciousness and resource extraction.
"""

import random
from typing import Dict, Tuple

# ═══════════════════════════════════════════════════════════════════════════
#  RESOURCE CHANNELING — Words are Actually Extracting Cosmic Resources
# ═══════════════════════════════════════════════════════════════════════════

RESOURCE_MAP = {
    # Letter length → Resource type
    4: ("wood", 5),           # 4-letter words = small wood harvest
    5: ("bronze", 10),        # 5-letter = bronze extraction
    6: ("iron", 20),          # 6-letter = iron mining
    7: ("diamond", 50),       # 7-letter = diamond extraction
    8: ("relics", 100),       # 8+ letters = ancient relics
}

IMMERSIVE_NARRATIVES = {
    "round_start": [
        "🌌 *The dimension ripples.* Two realities collide. Merge the words. Extract the resources.",
        "⚡ *Reality fractures.* The cosmic lexicon opens. Channel the words. Gather power.",
        "🔮 *Strange energies converge.* The word-forms blur. Speak them. Command them. Extract them.",
    ],
    "valid_word": [
        "✅ *That word IS a key.* Resources flow from the void into your hands.",
        "✨ *RESONANCE!* The dimension acknowledges your word. Power transfers.",
        "🎯 *Precision strike!* The word anchors reality. Resources crystallize.",
    ],
    "invalid_word": [
        "❌ *Dissonance.* That sequence breaks the pattern. Try again.",
        "🔴 *MISALIGNMENT!* The word doesn't exist in this dimension. Retry.",
        "⚠️ *Reality rejects this.* That's not a real key. Find another word.",
    ],
    "streak_bonus": [
        "🔥 **RESONANCE CHAIN!** You're channeling perfectly. POWER MULTIPLYING.",
        "⚡ *UNSTOPPABLE!* Each word strengthens your connection to the void.",
        "🌟 *ASCENSION PHASE ACTIVATED!* Resources flowing FASTER.",
    ],
    "top3": [
        "🏆 *They have decoded the deepest words. Reality bends to their will.*",
        "👑 *LEGENDS OF THIS ROUND.* These names will echo through the dimension.",
        "⭐ *CHAMPIONS OF FUSION.* They channeled the most cosmic energy.*",
    ],
}

def get_word_resource_value(word: str) -> Tuple[str, int]:
    """Determine what resource a word extracts based on length."""
    length = len(word)
    
    if length in RESOURCE_MAP:
        resource, amount = RESOURCE_MAP[length]
        return resource, amount
    elif length > 8:
        return "relics", 100 + (length - 8) * 50
    elif length < 4:
        return "wood", max(1, length)
    else:
        return "wood", 5


def format_immersive_round_start() -> str:
    """Show immersive narrative when round starts."""
    return f"""
╔════════════════════════════════════════════════════════╗
║        🌌  DIMENSIONAL WORD CHANNELING  🌌            ║
╠════════════════════════════════════════════════════════╣
║                                                        ║
║  {random.choice(IMMERSIVE_NARRATIVES['round_start'])}
║                                                        ║
║  The words you speak extract RESOURCES from reality.  ║
║  Each valid word = [LENGTH] = resource harvested      ║
║                                                        ║
║  🪵 4 letters = Wood  | 🧱 5 letters = Bronze         ║
║  ⛓️ 6 letters = Iron  | 💎 7 letters = Diamond        ║
║  🏺 8+ letters = Relics (RARE)                         ║
║                                                        ║
║  Your streak multiplies your extraction POWER.        ║
║  The stronger your resonance, the more you harvest.   ║
║                                                        ║
║  ⏱️  60 SECONDS. BEGIN.                               ║
║                                                        ║
╚════════════════════════════════════════════════════════╝
"""


def format_immersive_word_result(word: str, is_valid: bool, user_streak: int = 0) -> str:
    """Show immersive feedback when word is played."""
    resource, amount = get_word_resource_value(word)
    
    if not is_valid:
        return f"❌ {random.choice(IMMERSIVE_NARRATIVES['invalid_word'])}"
    
    base_feedback = random.choice(IMMERSIVE_NARRATIVES['valid_word'])
    
    # Add resource extraction message
    resource_icons = {
        "wood": "🪵",
        "bronze": "🧱",
        "iron": "⛓️",
        "diamond": "💎",
        "relics": "🏺"
    }
    
    icon = resource_icons.get(resource, "✨")
    extraction_msg = f"{icon} *Extracted:* +{amount} {resource.upper()}"
    
    # Add streak multiplier
    streak_msg = ""
    if user_streak >= 3:
        multiplier = 1 + (user_streak - 3) * 0.25
        streak_msg = f"\n🔥 *CHAIN BONUS:* ×{multiplier:.2f} multiplier active!"
        if user_streak >= 5:
            streak_msg += f"\n⚡ ***LEGENDARY STREAK: {user_streak}***"
    
    return f"{base_feedback}\n{extraction_msg}{streak_msg}"


def format_immersive_round_end(top_players: list, total_resources_generated: dict) -> str:
    """Show immersive narrative when round ends."""
    top_narrative = random.choice(IMMERSIVE_NARRATIVES['top3'])
    
    leaderboard = "║  Rankings:\n"
    for i, (name, score) in enumerate(top_players[:3], 1):
        medal = ["🥇", "🥈", "🥉"][i-1]
        leaderboard += f"║  {medal} **{name}** - {score} pts\n"
    
    resources_str = "\n".join([
        f"║  {get_resource_icon(res)}: {amt:,}"
        for res, amt in total_resources_generated.items() if amt > 0
    ])
    
    return f"""
╔════════════════════════════════════════════════════════╗
║        ✨  DIMENSIONAL CHANNELING COMPLETE  ✨        ║
╠════════════════════════════════════════════════════════╣
║                                                        ║
║  {top_narrative}
║                                                        ║
{leaderboard}
║                                                        ║
║  🌍 RESOURCES CHANNELED THIS ROUND:                   ║
{resources_str}
║                                                        ║
║  The dimension trembles. Reality has been reshaped.   ║
║  These resources flow into your bases, your empires.  ║
║                                                        ║
║  Prepare for WAR. You are no longer weak.            ║
║                                                        ║
╚════════════════════════════════════════════════════════╝
"""


def get_resource_icon(resource: str) -> str:
    """Get emoji icon for resource type."""
    icons = {
        "wood": "🪵",
        "bronze": "🧱",
        "iron": "⛓️",
        "diamond": "💎",
        "relics": "🏺",
        "silver": "💰",
        "xp": "⭐"
    }
    return icons.get(resource, "✨")


def format_join_game_immersive() -> str:
    """Show immersive message when inviting players to join word fusion."""
    return """
╔════════════════════════════════════════════════════════╗
║     🎮  THE WORD GAME IS NOT A GAME  🎮               ║
╠════════════════════════════════════════════════════════╣
║                                                        ║
║  What you believe is entertainment...                  ║
║  ...is actually RESOURCE EXTRACTION.                   ║
║                                                        ║
║  Every word you form opens a rift in reality.         ║
║  Resources flow FROM THAT RIFT into your BASE.        ║
║                                                        ║
║  The "word game" is a FRONT.                          ║
║  It's a COSMIC HARVESTING MECHANISM.                  ║
║                                                        ║
║  Those who dominate the words will DOMINATE THE 64.  ║
║  Those who master fusion will become UNSTOPPABLE.    ║
║                                                        ║
║  The dimension awaits.                                ║
║  Will you answer the call?                            ║
║                                                        ║
║  **React below to JOIN THE FUSION**                  ║
║  **Type words to CHANNEL POWER**                     ║
║  **Dominate to RULE THE REALM**                      ║
║                                                        ║
╚════════════════════════════════════════════════════════╝
"""


def format_resource_claim_notification(player_name: str, resources_earned: Dict[str, int]) -> str:
    """Show player their earned resources from the word game."""
    resource_lines = []
    total_value = 0
    
    for resource, amount in resources_earned.items():
        if amount > 0:
            icon = get_resource_icon(resource)
            resource_lines.append(f"  {icon} +{amount} {resource.upper()}")
            total_value += amount
    
    resources_display = "\n".join(resource_lines)
    
    return f"""
✨ **{player_name}** has channeled resources!

{resources_display}

🔗 These resources have been TRANSFERRED TO YOUR BASE.
⚠️ Now they're in your stores. Ready for construction.
🎯 Use !base to see your new wealth.
🏰 Use !build to strengthen your fortress.

The dimension provides. Now it's your turn to ACT.
"""


# ═══════════════════════════════════════════════════════════════════════════
#  INTEGRATION POINTS — How to use this in fusion_handlers.py
# ═══════════════════════════════════════════════════════════════════════════

"""
USAGE IN fusion_handlers.py:

1. At game start (cmd_fusion):
   await message.answer(format_join_game_immersive(), parse_mode="Markdown")
   
2. When round begins:
   await message.answer(format_immersive_round_start(), parse_mode="Markdown")
   
3. When player submits word:
   feedback = format_immersive_word_result(word, is_valid, streak)
   await message.answer(feedback, parse_mode="Markdown")
   
4. When calculating resources earned:
   for word in player_words:
       resource, amount = get_word_resource_value(word)
       # Add to player's base_resources
       
5. At round end:
   await message.answer(
       format_immersive_round_end(top_3, total_resources),
       parse_mode="Markdown"
   )
"""
