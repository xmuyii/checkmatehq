import asyncio
import random
import httpx
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import get_user, register_user, add_silver, set_sector
from config import BOT_TOKEN, SUPABASE_URL as CONFIG_SUPABASE_URL, SUPABASE_KEY as CONFIG_SUPABASE_KEY

# Load credentials from environment or config
API_TOKEN = os.environ.get('API_TOKEN', BOT_TOKEN)
SUPABASE_URL = os.environ.get('SUPABASE_URL', CONFIG_SUPABASE_URL).rstrip('/')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', CONFIG_SUPABASE_KEY)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- TRIAL FSM STATES ---
class Trial(StatesGroup):
    awaiting_username = State()
    trial_round_1 = State()
    trial_round_2 = State()
    trial_round_3 = State()
    backpack_choice = State()


# --- HELPER FUNCTIONS ---

async def fetch_trial_words():
    """Fetch two random 6-7 letter words for trials"""
    headers = {'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}'}
    url = f"{SUPABASE_URL}/rest/v1/Dictionary?word_length=eq.6&select=word&limit=1"
    async with httpx.AsyncClient() as client:
        try:
            r1 = await client.get(f"{url}&offset={random.randint(0, 500)}", headers=headers)
            r2 = await client.get(f"{url}&offset={random.randint(0, 500)}", headers=headers)
            w1 = r1.json()[0]['word'].upper() if r1.json() else "PYTHON"
            w2 = r2.json()[0]['word'].upper() if r2.json() else "PLAYER"
            return w1, w2
        except:
            return "PYTHON", "PLAYER"

def is_anagram(guess, letters_pool):
    """Check if word is anagram of letters"""
    pool = list(letters_pool)
    for char in guess:
        if char in pool:
            pool.remove(char)
        else:
            return False
    return True

async def check_dict(word):
    """Check if word exists in dictionary"""
    headers = {'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}'}
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{SUPABASE_URL}/rest/v1/Dictionary?word=ilike.{word}&select=word", headers=headers)
        return len(r.json()) > 0


# --- 🎬 FIRST CONTACT: THE SADISTIC WELCOME ---

@dp.message(StateFilter(None), F.chat.type == "private")
async def first_contact(message: types.Message, state: FSMContext):
    """Sadistic welcome for anyone messaging the bot privately"""
    user_id = str(message.from_user.id)
    
    # If already registered, don't bother
    if get_user(user_id):
        await message.answer(
            "🃏 *GameMaster:* \"You're already here. Stop pestering me.\"",
            parse_mode="Markdown"
        )
        return
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ I'm ready to enter", callback_data="trial_yes")],
        [InlineKeyboardButton(text="🚪 I'm just lost", callback_data="trial_no")]
    ])
    
    await message.answer(
        "🃏 *GameMaster:* \"Well, well, well. Look what crawled into my domain.\"\n\n"
        "\"You show up unannounced, uninvited, and probably unprepared. I don't know who you are. "
        "I don't care who you are.\"\n\n"
        "\"But something about you... *interests* me. Maybe it's the desperation in your message. "
        "Or maybe you're just incredibly stupid.\"\n\n"
        "\"So tell me, little mortal: are you here to join **The 64**? Or did you just wander in by accident?\"",
        parse_mode="Markdown",
        reply_markup=markup
    )
    await state.set_state(Trial.awaiting_username)


@dp.callback_query(Trial.awaiting_username, F.data == "trial_no")
async def decline_entry(callback: types.CallbackQuery, state: FSMContext):
    """User declines to enter"""
    await callback.answer()
    await callback.message.edit_text(
        "🃏 *GameMaster:* \"Thought so. Weak. *Pathetic.*\"\n\n"
        "\"Come back if you ever grow a spine.\"",
        parse_mode="Markdown"
    )
    await state.clear()


@dp.callback_query(Trial.awaiting_username, F.data == "trial_yes")
async def accept_entry(callback: types.CallbackQuery, state: FSMContext):
    """User accepts entry - ask for username"""
    await callback.answer()
    await callback.message.edit_text(
        "🃏 *GameMaster:* \"Good. Foolish, but good.\"\n\n"
        "\"I need your name for my records. What shall I call you?\"",
        parse_mode="Markdown"
    )


# --- USERNAME CAPTURE ---

@dp.message(Trial.awaiting_username)
async def capture_username(message: types.Message, state: FSMContext):
    """Capture player username and start first trial"""
    username = message.text.strip()[:20]
    user_id = str(message.from_user.id)
    
    # Register player
    register_user(user_id, username)
    
    await state.update_data(username=username, scores_list=[])
    
    await message.answer(
        f"🃏 *GameMaster:* \"{username}. *Derivative.*\"\n\n"
        f"\"You must survive three trials. Prove you have even a shred of wit.\"\n\n"
        f"\"Let's begin.\"",
        parse_mode="Markdown"
    )
    
    await asyncio.sleep(1)
    await send_trial_letters(message, state, 0)


async def send_trial_letters(message: types.Message, state: FSMContext, round_num: int):
    """Send trial round letters"""
    if round_num > 2:
        return
    
    word1, word2 = await fetch_trial_words()
    letters = (word1 + word2).lower()
    
    await state.update_data(
        trial_letters=letters,
        trial_word1=word1,
        trial_word2=word2,
        trial_round=round_num,
        trial_round_score=0,
        trial_used=[]
    )
    
    names = ["FIRST", "SECOND", "FINAL"]
    states = [Trial.trial_round_1, Trial.trial_round_2, Trial.trial_round_3]
    
    await message.answer(
        f"💎 *{names[round_num]} TRIAL*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📝 **LETTERS:** {' '.join(letters.upper())}\n\n"
        f"Find dictionary words. Type `!done` when ready to see results.",
        parse_mode="Markdown"
    )
    
    await state.set_state(states[round_num])


# --- TRIAL RESPONSES ---

@dp.message(Trial.trial_round_1)
@dp.message(Trial.trial_round_2)
@dp.message(Trial.trial_round_3)
async def on_trial_guess(message: types.Message, state: FSMContext):
    """Process trial guesses"""
    data = await state.get_data()
    guess = message.text.lower().strip()
    
    if guess == "!done":
        await end_trial_round(message, state)
        return
    
    round_num = data['trial_round']
    letters = data['trial_letters']
    used = data.get('trial_used', [])
    
    # Validate
    if is_anagram(guess, letters) and guess not in used:
        if await check_dict(guess):
            pts = len(guess) - 2
            used.append(guess)
            score = data.get('trial_round_score', 0) + pts
            
            await state.update_data(trial_round_score=score, trial_used=used)
    elif guess in used:
        pass  # Silently ignore duplicates


async def end_trial_round(message: types.Message, state: FSMContext):
    """End current round and show rigged leaderboard"""
    data = await state.get_data()
    round_num = data['trial_round']
    score = data.get('trial_round_score', 0)
    username = data['username']
    scores_list = data.get('scores_list', [])
    scores_list.append(score)
    
    if round_num == 2:
        # FINAL ROUND - They have highest score but placed LAST
        lead_text = f"""🏆 *FINAL TRIAL LEADERBOARD*
━━━━━━━━━━━━━━━
🥇 Predator\_99 — 45 pts
🥈 ShadowMaster — 38 pts
🥉 Vortex\_7 — 31 pts
4. Knight\_44 — 28 pts
5. Breaker\_12 — 25 pts
6. Phoenix\_8 — 22 pts
7. Rogue\_33 — 18 pts
8. Storm\_5 — 15 pts
9. Sentinel\_2 — 12 pts
10. **{username} — {score} pts**

🃏 *GameMaster:* \"HIGHEST SCORE. LOWEST RANK. How *absurdly pathetic*! But I admire the cosmic joke. Take 100 silver.\" """
        
        await message.answer(lead_text, parse_mode="Markdown")
        
        await asyncio.sleep(2)
        
        # Award silver
        add_silver(str(message.from_user.id), 100, username)
        await state.update_data(scores_list=scores_list)
        await show_backpack_choice(message, state, data)
    else:
        # Rounds 1-2: Normal rigged placements
        placement_text = f"""🏆 *ROUND {round_num + 1} LEADERBOARD*
━━━━━━━━━━━━━━━
🥇 ShadowMaster — {score + 10} pts
🥈 Predator\_99 — {score + 5} pts
🥉 **{username} — {score} pts**"""
        
        placement_text += f"\n\n🃏 *GameMaster:* \"Next.\""
        
        await message.answer(placement_text, parse_mode="Markdown")
        
        await asyncio.sleep(2)
        await state.update_data(scores_list=scores_list)
        await send_trial_letters(message, state, round_num + 1)


async def show_backpack_choice(message: types.Message, state: FSMContext, data: dict):
    """Show backpack upgrade options"""
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🐢 Premium Turtle (900 ₦)", callback_data="backpack_premium")],
        [InlineKeyboardButton(text="🐢😤 Grumpy Turtle (FREE)", callback_data="backpack_default")]
    ])
    
    await message.answer(
        f"💰 **100 SILVER AWARDED**\n\n"
        f"🎒 *Choose your vessel:*\n"
        f"• **Premium** — ₦900 | 20 slots\n"
        f"• **Grumpy** — FREE | 5 slots",
        parse_mode="Markdown",
        reply_markup=markup
    )
    
    await state.set_state(Trial.backpack_choice)


@dp.callback_query(Trial.backpack_choice)
async def backpack_choice_handler(callback: types.CallbackQuery, state: FSMContext):
    """Handle backpack selection"""
    data = await state.get_data()
    user_id = str(callback.from_user.id)
    username = data.get('username', callback.from_user.first_name)
    
    await callback.answer("✅ Backpack equipped!")
    
    # Assign sector
    sectors = [
        ("Badlands", random.randint(1, 20), "🏜️"),
        ("Crimson Peaks", random.randint(1, 15), "⛰️"),
        ("Void Sector", random.randint(1, 10), "🌌"),
        ("Iron Mill", random.randint(1, 25), "🏭"),
        ("Floating Gardens", random.randint(1, 12), "🌺")
    ]
    
    sector_name, sector_num, emoji = random.choice(sectors)
    sector_full = f"{sector_name} {sector_num}"
    
    set_sector(user_id, sector_full)
    
    await callback.message.edit_text(
        f"🌍 *SECTOR ASSIGNMENT*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{emoji} **{sector_full.upper()}**\n\n"
        f"🔥 Welcome to The 64, {username}.\n\n"
        f"Head to the group and type `!fusion` to begin.",
        parse_mode="Markdown"
    )
    
    await state.clear()


# --- MAIN ---

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
