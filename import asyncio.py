import asyncio
import random
import httpx
from aiogram import Bot, Dispatcher, types, F # Added F for better filtering
from aiogram.fsm.context import FSMContext # <--- Add this!
from aiogram.fsm.state import StatesGroup, State

# --- CONFIGURATION ---
API_TOKEN = '8761897858:AAEb1nCZQ_I4DKgMa9PgMk-q0t8Be0bMZlQ' # Use the Revoked Token here
SUPABASE_URL = 'https://basniiolppmtpzishhtn.supabase.co'.rstrip('/')
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJhc25paW9scHBtdHB6aXNoaHRuIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NTQ3NjMwOCwiZXhwIjoyMDkxMDUyMzA4fQ.qrj1BO5dNilRDvgKtvTdwIWjBhFTRyGzuHPD271Xcac'
APPS_URL = 'https://script.google.com/macros/s/AKfycby1Uq9VsH7QT9M-2oEklJaLS0jerCe16BUzgC17mkwSGqHZgYGLBTGzUNCayyCE7ICS/exec'

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

class GameState:
    def __init__(self):
        self.timer = 60
        self.word1 = ""
        self.word2 = ""
        self.letters = ""
        self.used_words = []
        self.scores = {}
        self.game_active = False
        self.msg_counter = 0 # Tracks messages since last HUD post

game = GameState()
@dp.message(F.text == "!inventory")
async def show_inventory(message: types.Message):
    import database
    user_id = message.from_user.id
    user_data = database.get_user(user_id)

    if not user_data:
        await message.answer(
            "🃏 *GameMaster:* \"Who are you? You don't even have a soul in my system, let alone a backpack. Go to my DMs and type `/start`.\"",
            parse_mode="Markdown"
        )
        return

    # Extracting data from our JSON
    silver = user_data.get("silver", 0)
    items = user_data.get("inventory", [])
    backpack = user_data.get("backpack", "Pockets")
    slots = 10 if "Premium" in backpack else 5
    
    # Formatting the item list
    item_list = "\n".join([f"• {item}" for item in items]) if items else "• Empty (Pathetic)"
    
    inventory_text = (
        f"🎒 *{message.from_user.first_name}'s {backpack}*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🪙 *Silver:* {silver}\n"
        f"📦 *Slots Used:* {len(items)} / {slots}\n\n"
        f"*Items:*\n{item_list}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📍 *Sector:* {user_data.get('sector', 'Unknown')}\n\n"
        f"🃏 *GameMaster:* \"Nice collection of junk you've got there.\""
    )

    await message.answer(inventory_text, parse_mode="Markdown")
# --- FREE CHOICE ---
@dp.callback_query(F.data == "turtle_free")
async def process_free_turtle(call: types.CallbackQuery, state: FSMContext):
    import database
    user_data = {
        "username": call.from_user.first_name,
        "silver": 100,
        "backpack": "Grumpy Turtle (5 Slots)",
        "sector": "Badlands Sector 8",
        "inventory": ["Bronze Key", "Cracked Compass"]
    }
    database.save_user(call.from_user.id, user_data)
    
    await call.message.edit_text(
        "🃏 *GameMaster:* \"The Grumpy Turtle it is. It suits your low-budget ambitions.\"\n\n"
        "\"You have been spawned in **Badlands Sector 8**. Try not to die immediately.\"",
        parse_mode="Markdown"
    )
    await state.clear()

# --- PAID CHOICE (The ₦900 Trap) ---
@dp.callback_query(F.data == "turtle_paid")
async def process_premium_turtle(call: types.CallbackQuery, state: FSMContext):
    # In a real CS project, you'd link Flutterwave/Paystack here.
    # For now, we mock the 'Success'
    import database
    user_data = {
        "username": call.from_user.first_name,
        "silver": 250, # Bonus silver for buying!
        "backpack": "Premium Turtle (10 Slots)",
        "sector": "The Gilded Spire - Sector 1",
        "inventory": ["Silver Key", "Mystery Crate", "Map Fragment"]
    }
    database.save_user(call.from_user.id, user_data)
    
    await call.message.edit_text(
        "🃏 *GameMaster:* \"Ah, a big spender. Fine. You've bought your way into a bigger bag.\"\n\n"
        "\"You have been spawned in **The Gilded Spire Sector 1**. Use those extra slots wisely.\"",
        parse_mode="Markdown"
    )
    await state.clear()

# --- ENTRY LOGIC ---
async def start_new_round():
    print("🛰️ Connecting to Supabase...")
    headers = {'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}'}
    base_url = f"{SUPABASE_URL}/rest/v1/Dictionary?word_length=eq.7&select=word&limit=1"
    
    async with httpx.AsyncClient() as client:
        try:
            # Parallel fetching
            res1, res2 = await asyncio.gather(
                client.get(f"{base_url}&offset={random.randint(0, 500)}", headers=headers),
                client.get(f"{base_url}&offset={random.randint(0, 500)}", headers=headers)
            )
            w1 = res1.json()[0]['word'].upper() if res1.json() else "PLAYERS"
            w2 = res2.json()[0]['word'].upper() if res2.json() else "DANGERS"
        except Exception as e:
            print(f"❌ Supabase Error: {e}")
            w1, w2 = "PLAYERS", "DANGERS"

    game.word1, game.word2 = w1, w2
    game.letters = (w1 + w2).lower()
    game.timer, game.used_words, game.scores = 60, [], {}
    game.game_active = True
    print(f"✅ Words Loaded: {w1} & {w2}")

# --- TRIGGER: !fusion ---
@dp.message(F.text == "!fusion")
async def run_game(message: types.Message):
    if game.game_active: return
    
    await start_new_round()
    game.msg_counter = 0 
    
    # Send the Initial HUD
    await message.answer(
        f"🃏 *GameMaster:* \"The board is set. Try not to embarrass yourself.\"\n\n"
        f"🎯 `{game.word1}` & `{game.word2}`\n"
        f"⌛ 60s starts now.\"",
        parse_mode="Markdown"
    )

    # The Background Timer
    while game.timer > 0:
        await asyncio.sleep(1) # Tick every second for accuracy
        game.timer -= 1
        
        # Optional: Post a "15 Seconds Left" warning regardless of message count
        if game.timer == 15:
            await message.answer("🚨 *15 SECONDS LEFT!* 🚨", parse_mode="Markdown")

    # --- LEADERBOARD TRIGGER ---
    game.game_active = False
    # (Insert your leaderboard logic here) here)")

@dp.message()
async def global_message_handler(message: types.Message):
    # 1. First, check if the message is a valid word guess
    if game.game_active and not message.text.startswith("!"):
        # (Your Validator Logic goes here - checking anagrams/Supabase)
        
        # 2. Increment counter for every message sent during a game
        game.msg_counter += 1
        
        if game.msg_counter >= 10:
                game.msg_counter = 0
                await message.answer(
                    f"🃏 \"You are still at it? Fine.\"\n\n"
                    f"🎯 `The words are {game.word1}` | `{game.word2}`\n"
                    f"⌛ {game.timer}s left. Or don't finish. I don't care.",
                    parse_mode="Markdown"
                )

async def main():
    print("🚀 Bot is starting... Looking for !fusion")
    # This line clears any pending updates so it doesn't get overwhelmed on start
    await bot.delete_webhook(drop_pending_updates=True) 
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())