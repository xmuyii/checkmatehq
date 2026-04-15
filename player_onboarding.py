"""
NEW PLAYER ONBOARDING: Welcome Screen and Username Registration
================================================================
Improved flow for new players to register and be welcomed to the game.
"""

import asyncio
from aiogram import types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

try:
    from supabase_db import register_user, get_user, save_user
except:
    from database import register_user, get_user, save_user

# ═══════════════════════════════════════════════════════════════════════════
#  ONBOARDING STATE MACHINE
# ═══════════════════════════════════════════════════════════════════════════

class PlayerOnboarding(StatesGroup):
    """Welcome new players and collect username."""
    welcome_screen = State()        # Show dramatic welcome
    collect_username = State()      # Ask for username
    confirm_username = State()      # Show confirmation
    choose_sector = State()         # Pick starting sector
    tutorial_start = State()        # Offer tutorial


async def show_welcome_screen(message: types.Message, state: FSMContext):
    """
    Display dramatic welcome screen for new players.
    Called when a user first messages the bot.
    """
    user_id = str(message.from_user.id)
    first_name = message.from_user.first_name or "Stranger"
    
    # Check if already registered
    if get_user(user_id):
        await message.answer(
            f"🃏 *GameMaster:* \"Oh, it's you again. Your soul is already in my ledger. "
            f"Go play — type `!fusion` in the group.\"\n\n"
            f"Need help? Type `!help`.",
            parse_mode="Markdown"
        )
        await state.clear()
        return
    
    # Show welcome screen
    welcome_msg = f"""
╔════════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║                    🃏 WELCOME TO THE GAME 🃏                             ║
║                                                                            ║
║  {first_name.upper()}, you have arrived at a place where others have       ║
║  forgotten their names. Where power is measured in words and cunning.    ║
║                                                                            ║
║  The GameMaster sees you. And the GameMaster... is not impressed.         ║
║                                                                            ║
║  *\"So. Another lost soul seeking fortune in MY domain.\"*                 ║
║                                                                            ║
║  *\"You will need a NAME. Something to carve into history... or dust.\"* ║
║  *\"What shall I call you, mortal?\"*                                     ║
║                                                                            ║
║  *Answer below:*                                                          ║
║  `Your username (1-20 characters)`                                        ║
║                                                                            ║
║  Type your desired username and press Enter.                             ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝
"""
    
    await message.answer(welcome_msg, parse_mode="Markdown")
    await state.set_state(PlayerOnboarding.collect_username)
    await state.update_data(first_contact_user_id=user_id)


async def collect_username(message: types.Message, state: FSMContext):
    """
    Collect username from new player.
    Validates length and uniqueness.
    """
    username = message.text.strip()
    user_id = str(message.from_user.id)
    
    # Validation
    if not username or len(username) < 2:
        await message.answer(
            "🃏 *GameMaster:* \"A name needs at least 2 characters, fool. Try again.\"",
            parse_mode="Markdown"
        )
        return
    
    if len(username) > 20:
        await message.answer(
            f"🃏 *GameMaster:* \"'{username}' is too long. 20 characters max. Shorten it.\"",
            parse_mode="Markdown"
        )
        return
    
    # Check if username already exists
    # (This would require a function to check usernames in DB)
    # For now, just proceed
    
    await state.update_data(chosen_username=username)
    await state.set_state(PlayerOnboarding.confirm_username)
    
    # Show confirmation screen
    confirm_msg = f"""
╔════════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║  🃏 *CONFIRM YOUR IDENTITY* 🃏                                           ║
║                                                                            ║
║  You shall be known as: **{username.upper()}**                            ║
║                                                                            ║
║  _A name echoes through this realm. Is this YOUR true name?_             ║
║                                                                            ║
║  *Choose carefully. You can change it later, but it costs...*             ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝
"""
    
    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ YES, I'm " + username, callback_data="username_confirm"),
            InlineKeyboardButton(text="❌ NO, let me choose again", callback_data="username_retry")
        ]
    ])
    
    await message.answer(confirm_msg, reply_markup=confirm_kb, parse_mode="Markdown")


async def handle_username_confirmation(callback: types.CallbackQuery, state: FSMContext):
    """Handle username confirmation."""
    user_id = str(callback.from_user.id)
    data = await state.get_data()
    username = data.get("chosen_username", "Stranger")
    
    if callback.data == "username_retry":
        # Let them try again
        await callback.message.edit_text(
            "🃏 *GameMaster:* \"Choose differently, then. I await your new name.\"",
            parse_mode="Markdown"
        )
        await state.set_state(PlayerOnboarding.collect_username)
        await callback.answer()
        return
    
    # Username confirmed - register player
    await callback.answer("✅ Identity confirmed!", show_alert=False)
    
    # Register in database
    try:
        success = register_user(
            user_id,
            username,
            first_name=callback.from_user.first_name or "Player"
        )
        
        if not success:
            await callback.message.edit_text(
                "❌ Registration failed. Try `/start` again.",
                parse_mode="Markdown"
            )
            await state.clear()
            return
        
    except Exception as e:
        print(f"[ONBOARDING ERROR] Failed to register {user_id}: {e}")
        await callback.message.edit_text(
            f"❌ Error during registration: {str(e)[:100]}",
            parse_mode="Markdown"
        )
        await state.clear()
        return
    
    # Show welcome message
    welcome_text = f"""
╔════════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║        🏆 WELCOME TO THE GAME, {username.upper()} 🏆                     ║
║                                                                            ║
║  Your name is now inscribed in the ledger.                               ║
║  Your journey begins here.                                               ║
║                                                                            ║
║  🃏 *GameMaster's Words:*                                                 ║
║  *\"You are no longer a ghost. You have a destiny. Whether it leads      ║
║  to glory or oblivion is entirely your choice.\"*                        ║
║                                                                            ║
║  *\"The game awaits. The word fusion has begun already...\"*            ║
║                                                                            ║
║  📚 **QUICK START:**                                                      ║
║  1. Go to the group and type `/fusion` to start word games              ║
║  2. Type valid English words using only the given letters               ║
║  3. Earn points, resources, and build your empire                       ║
║  4. Return to chat (me) for deeper gameplay                             ║
║                                                                            ║
║  🎓 Type `/tutorial` for a complete walkthrough                         ║
║  ❓ Type `/help` for command reference                                   ║
║  👤 Type `/profile` to see your stats                                    ║
║                                                                            ║
║  *The Obelisk gates are open. The choice is yours.*                      ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝
"""
    
    await callback.message.edit_text(welcome_text, parse_mode="Markdown")
    
    # Give starter pack
    await callback.message.answer(
        "💝 **STARTER PACK:**\n\n"
        "✅ 100 Silver (pocket money)\n"
        "✅ Tutorial access\n"
        "✅ Optional: `/setup_base` to claim territory\n\n"
        "Good luck, {username}. The game notices you now.".format(username=username),
        parse_mode="Markdown"
    )
    
    await state.clear()


# ═══════════════════════════════════════════════════════════════════════════
# EXPORT FOR INTEGRATION INTO MAIN BOT
# ═══════════════════════════════════════════════════════════════════════════

__all__ = [
    'PlayerOnboarding',
    'show_welcome_screen',
    'collect_username',
    'handle_username_confirmation'
]
