"""
Jammer Message Management System
=================================
Auto-delete messages from players with jammer active.
Prevents other players from seeing scrambled text.
"""

import asyncio
from datetime import datetime
from typing import Optional
from aiogram import Bot, types

# ═══════════════════════════════════════════════════════════════════════════
#  JAMMER MESSAGE HANDLING
# ═══════════════════════════════════════════════════════════════════════════

async def should_delete_jammer_message(user_id: int) -> bool:
    """
    Check if a player has jammer active and their message should be deleted.
    
    Args:
        user_id: Telegram user ID
    
    Returns:
        True if message should be deleted
    """
    try:
        from jammer_perk_system import is_perk_active
        return is_perk_active(user_id, "jammer")
    except:
        return False


async def delete_jammer_message(message: types.Message, bot: Bot, delay: float = 0.5) -> bool:
    """
    Delete a message from a player with jammer active.
    
    Args:
        message: The message to delete
        bot: Bot instance
        delay: Delay before deletion (seconds)
    
    Returns:
        True if deleted successfully
    """
    try:
        await asyncio.sleep(delay)
        await bot.delete_message(
            chat_id=message.chat.id,
            message_id=message.message_id
        )
        print(f"[JAMMER] Deleted message {message.message_id} from user {message.from_user.id}")
        return True
    except Exception as e:
        print(f"[JAMMER ERROR] Could not delete message: {e}")
        return False


async def handle_jammer_word_submission(
    bot: Bot,
    message: types.Message,
    guess: str,
    user_id: int,
    username: str
) -> dict:
    """
    Handle word submission from a player with jammer active.
    
    Features:
    - Send response to player (DM)
    - Delete group message
    - Log the submission internally
    - Don't show word in group
    
    Args:
        bot: Bot instance
        message: The group message
        guess: The word guessed
        user_id: User Telegram ID
        username: Player username
    
    Returns:
        dict with handling info
    """
    try:
        from jammer_perk_system import is_perk_active
        
        has_jammer = is_perk_active(user_id, "jammer")
        
        if has_jammer:
            # Send response in DM instead of group
            try:
                dm_response = f"""
⚡ **SCRAMBLER ACTIVE**
━━━━━━━━━━━━━━━━━
✅ Your word was accepted
🔐 Hidden from other players

Your message in group has been deleted for stealth.
"""
                await bot.send_message(user_id, dm_response, parse_mode="Markdown")
            except:
                pass  # DM might be disabled
            
            # Delete the message from group
            await delete_jammer_message(message, bot, delay=0.1)
            
            return {
                "jammer_active": True,
                "deleted": True,
                "sent_dm": True
            }
        
        return {
            "jammer_active": False,
            "deleted": False,
            "sent_dm": False
        }
    
    except Exception as e:
        print(f"[JAMMER ERROR] Failed to handle jammer submission: {e}")
        return {
            "jammer_active": False,
            "deleted": False,
            "sent_dm": False,
            "error": str(e)
        }


async def notify_jammer_word_to_gamemaster(
    bot: Bot,
    user_id: int,
    username: str,
    word: str,
    points: int,
    game_id: str,
    group_id: int
) -> bool:
    """
    Notify Game Master of a jammer player's word submission.
    Bot validates internally, players never see it.
    
    Args:
        bot: Bot instance
        user_id: User Telegram ID
        username: Player username
        word: The word submitted
        points: Points awarded
        game_id: Current game/round ID
        group_id: Group chat ID
    
    Returns:
        True if notified
    """
    try:
        gm_notification = f"""
⚡ **JAMMER WORD SUBMISSION**
━━━━━━━━━━━━━━━━━━━━
👤 Player: {username}
📝 Word: **{word}**
⭐ Points: +{points}
🎮 Round: {game_id}

✅ Validated by Game Master
🔐 Hidden from other players
"""
        # Send to game master log (if you have a GM log channel)
        # For now, just log it
        print(f"[GAMEMASTER] {username} submitted '{word}' with jammer active")
        return True
    
    except Exception as e:
        print(f"[JAMMER ERROR] Failed to notify GM: {e}")
        return False
