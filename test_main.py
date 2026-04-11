"""
test_main.py — Simple TEST BOT wrapper
Sets up environment and imports main.py for full functionality
"""

import os
import sys
from dotenv import load_dotenv

# Load .env FIRST
load_dotenv()

# Override environment variables
os.environ['API_TOKEN'] = os.getenv('TEST_BOT_TOKEN', '')
os.environ['CHECKMATE_HQ_GROUP_ID'] = os.getenv('TEST_GROUP_ID', '-1003773433371')
# Use production players table (test bot just uses different group)

if not os.environ.get('API_TOKEN'):
    print("❌ Error: TEST_BOT_TOKEN not found in .env file")
    sys.exit(1)

print("""
╔════════════════════════════════════════════════════════════════════╗
║                    🤖 TEST BOT LAUNCHING                          ║
║  Using: TEST_BOT_TOKEN + TEST_GROUP_ID                            ║
║  Database: Production players table (safe for testing)            ║
║  Group: -1003773433371                                            ║
╚════════════════════════════════════════════════════════════════════╝
""")

print(f"[TEST] API_TOKEN: {os.environ.get('API_TOKEN')[:30]}...")
print(f"[TEST] GROUP_ID: {os.environ.get('CHECKMATE_HQ_GROUP_ID')}")
print(f"\n[TEST] Importing main.py...", end="", flush=True)

try:
    import main
    print(" ✅\n")
except Exception as e:
    print(f" ❌\nError: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Run main's async entry point
if __name__ == "__main__":
    import asyncio
    
    print("[TEST] Starting bot...\n")
    
    try:
        asyncio.run(main.main())
    except KeyboardInterrupt:
        print("\n\n[TEST] ✅ Bot stopped (Ctrl+C)")
    except Exception as e:
        print(f"\n\n[TEST] ❌ Error: {e}")
        import traceback
        traceback.print_exc()
"""
test_main.py — Test bot using TEST_BOT_TOKEN and TEST_GROUP_ID
Runs all main.py features but in isolated test environment
"""

import os
import sys
from dotenv import load_dotenv

# Load .env file FIRST
load_dotenv()

# Override environment variables AFTER loading .env
os.environ['API_TOKEN'] = os.getenv('TEST_BOT_TOKEN', 'YOUR_TEST_BOT_TOKEN')
os.environ['CHECKMATE_HQ_GROUP_ID'] = os.getenv('TEST_GROUP_ID', '-1003773433371')
# DON'T set ENVIRONMENT to 'test' - use production players table
# Test bot just uses different group ID but same database
# os.environ['ENVIRONMENT'] = 'TEST'  # <-- Commented out

print("""
╔═══════════════════════════════════════════════════════════════════╗
║                    TEST BOT LAUNCHING                             ║
║  Using: TEST_BOT_TOKEN + TEST_GROUP_ID                            ║
║  Database: players table (PRODUCTION DATA FOR TESTING)            ║
║  All commands work normally, group announcements → test group     ║
╚═══════════════════════════════════════════════════════════════════╝
""")

# Now import main.py which will use the overridden environment variables
import asyncio
import random
from datetime import datetime, timedelta
import httpx
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from formatting import (
    progress_bar, divider, broadcast, round_start_header, round_end_summary,
    level_up_announcement, battle_result, shield_status_visual, countdown_timer,
    military_deployment, territory_claimed, achievement_unlocked, loading_bar, sector_status
)

# ── Addictive Mechanics ────────────────────────────────────────────────
from addictive_mechanics import (
    handle_daily_login, get_combo_multiplier, increment_combo, reset_combo,
    get_weekly_challenges, format_challenge_display, check_rare_drop,
    format_rare_drop_notification, get_limited_offer
)

# ── DB import ─────────────────────────────────────────────────────────────
try:
    from supabase_db import (
        get_user, register_user, add_points, get_weekly_leaderboard,
        get_alltime_leaderboard, add_silver, set_sector, upgrade_backpack,
        get_inventory, get_profile, add_xp, use_xp, use_silver,
        remove_inventory_item, load_sectors, save_user, calculate_level,
        check_level_up, add_unclaimed_item, get_unclaimed_items,
        claim_item, remove_unclaimed_item, award_powerful_locked_item,
        add_inventory_item, activate_shield, is_shielded, get_sector_display,
        add_resources_from_word_length, update_streak_and_award_food,
        reset_all_streaks, add_randomized_gift, give_automatic_shield, give_shields_to_all,
        deactivate_shield, disrupt_shield, restore_shield_after_attack,
    )
    print("✅ Using Supabase database")
except Exception as e:
    print(f"⚠️  Supabase failed ({e})")
    sys.exit(1)

# ── Config ─────────────────────────────────────────────────────────────
try:
    from config import BOT_TOKEN, ENV_NAME, SUPABASE_URL as CONFIG_SUPABASE_URL, SUPABASE_KEY as CONFIG_SUPABASE_KEY
except:
    BOT_TOKEN = os.environ.get('API_TOKEN', 'YOUR_BOT_TOKEN_HERE')

# Bot initialization
API_TOKEN = os.environ.get('API_TOKEN', BOT_TOKEN)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

print(f"\n[TEST BOT] Token: {API_TOKEN[:30]}...")
print(f"[TEST BOT] Group: {os.environ.get('CHECKMATE_HQ_GROUP_ID')}")
print(f"[TEST BOT] Ready to test!\n")

# ─────────────────────────────────────────────────────────────────────────
# Import all handlers from main.py and register them with dispatcher
# ─────────────────────────────────────────────────────────────────────────

from word_fusion import WordFusionGame
import word_fusion as wf

# Global state
eng = WordFusionGame(chat_id=int(os.environ.get('CHECKMATE_HQ_GROUP_ID', '-1003773433371')))

# Load command utilities
def _cmd(name):
    """Check if message starts with command"""
    async def check(message: types.Message) -> bool:
        if not message.text:
            return False
        return message.text.lower().startswith(f"/{name}") or message.text.lower().startswith(f"!{name}")
    return check

def _dm_only(cmd_name):
    """Return DM-only message"""
    return f"🃏 *GameMaster:* \"That command is DM-only, fool. Type `{cmd_name}` in my inbox, not here.\""

# ═══════════════════════════════════════════════════════════════════════════
# CORE HANDLERS (copied from main.py simplified for test)
# ═══════════════════════════════════════════════════════════════════════════

# Load dictionary
dictionary = set()

def load_dictionary():
    """Load 267k word dictionary"""
    try:
        with open("SupaDB1.txt", "r") as f:
            for line in f:
                dictionary.add(line.strip().lower())
        print(f"[OK] Dictionary loaded: {len(dictionary)} words")
    except Exception as e:
        print(f"[ERROR] Failed to load dictionary: {e}")

def word_in_dict(word: str) -> bool:
    return word.lower() in dictionary

def can_spell(word: str, letters: str) -> bool:
    """Check if word can be spelled from available letters"""
    word_lower = word.lower()
    letters_lower = letters.lower()
    for char in word_lower:
        if char not in letters_lower:
            return False
        letters_lower = letters_lower.replace(char, '', 1)
    return True

# Test start command
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    u_id = str(message.from_user.id)
    user = get_user(u_id)
    
    if not user:
        username = message.from_user.first_name or "Tester"
        register_user(u_id, username)
        await message.answer(
            f"🎮 *Welcome to Checkmate HQ Test Bot!*\n\n"
            f"You're registered as *{username}*\n\n"
            f"Commands:\n"
            f"• `!fusion` — Play word fusion game (group only)\n"
            f"• `!profile` — Check your stats (DM only)\n"
            f"• `!challenges` — Weekly quests (DM only)\n"
            f"• `!weekly` — Leaderboard (DM only)\n"
            f"• `!base` — Your fortress (DM only)\n"
            f"• `!lab` — Research (DM only)\n"
            f"• `!help` — Full commands\n\n"
            f"*Addictive Features Active:*\n"
            f"🔥 Daily streaks\n"
            f"🔥 Combo multipliers\n"
            f"💎 Rare drops\n"
            f"🎯 Weekly challenges",
            parse_mode="Markdown"
        )
    else:
        await message.answer(f"👋 Welcome back! Type `!help` for commands.", parse_mode="Markdown")

@dp.message(_cmd("profile"))
async def cmd_profile(message: types.Message):
    if message.chat.type != "private":
        await message.answer(_dm_only("!profile"), parse_mode="Markdown")
        return
    
    u_id = str(message.from_user.id)
    profile = get_profile(u_id)
    
    if not profile:
        await message.answer("🃏 No profile. Type `/start` first.", parse_mode="Markdown")
        return
    
    xp_pct = (profile['xp_progress'] / profile['xp_needed'] * 100) if profile['xp_needed'] > 0 else 0
    xp_bar = progress_bar(profile['xp_progress'], profile['xp_needed'], width=15)
    
    msg = (
        f"🃏 *GameMaster:* \"Staring at your own reflection. Fine.\"\n"
        f"{divider()}\n\n"
        f"👤 *{profile['username']}* — *LEVEL {profile['level']}*\n\n"
        f"⭐ XP Progress:\n{xp_bar}\n"
        f"💰 Silver: *{profile['silver']}*\n"
        f"📍 Sector: _{profile.get('sector_display','Not Assigned')}_\n\n"
        f"{divider()}\n\n"
        f"📊 *STATS*\n"
        f"├─ Weekly: *{profile['weekly_points']}* pts\n"
        f"└─ All-Time: *{profile['all_time_points']}* pts\n\n"
        f"📦 *INVENTORY* ({profile['inventory_count']}/{profile['backpack_slots']} slots)\n"
        f"├─ Unclaimed: *{profile['unclaimed_count']}*\n"
        f"└─ Crates: *{profile['crate_count']}*\n"
        f"{divider()}"
    )
    
    await message.answer(msg, parse_mode="Markdown")

@dp.message(_cmd("challenges"))
async def cmd_challenges(message: types.Message):
    if message.chat.type != "private":
        await message.answer(_dm_only("!challenges"), parse_mode="Markdown")
        return
    
    u_id = str(message.from_user.id)
    if not get_user(u_id):
        await message.answer("🃏 Not registered. Type `/start` first.", parse_mode="Markdown")
        return
    
    challenges = get_weekly_challenges(u_id)
    
    msg = f"{divider()}\n🎯 *WEEKLY CHALLENGES*\n{divider()}\n\n"
    
    for challenge in challenges:
        msg += format_challenge_display(challenge) + "\n\n"
    
    msg += f"{divider()}\n🃏 *Complete challenges to feel accomplished. That's what you're really chasing.*\n{divider()}"
    
    await message.answer(msg, parse_mode="Markdown")

@dp.message(_cmd("weekly"))
async def cmd_weekly(message: types.Message):
    if message.chat.type != "private":
        await message.answer(_dm_only("!weekly"), parse_mode="Markdown")
        return
    
    top = get_weekly_leaderboard(limit=10)
    
    msg = f"{divider()}\n🏆 *WEEKLY LEADERBOARD*\n{divider()}\n\n"
    medals = ["🥇", "🥈", "🥉"]
    
    for i, (name, pts, user_id) in enumerate(top):
        medal = medals[i] if i < 3 else f"{i+1}."
        msg += f"{medal} *{name}* — *{pts}* pts\n"
    
    msg += f"\n{divider()}"
    
    await message.answer(msg, parse_mode="Markdown")

@dp.message(_cmd("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "*CHECKMATE HQ — TEST BOT COMMANDS*\n\n"
        "*GROUP COMMANDS:*\n"
        "`!fusion [word]` — Submit word in game round\n\n"
        "*DM COMMANDS:*\n"
        "`!start` — Register\n"
        "`!profile` — Your stats\n"
        "`!challenges` — Weekly quests\n"
        "`!weekly` — Leaderboard\n"
        "`!alltime` — All-time leaderboard\n"
        "`!base` — Your fortress\n"
        "`!lab` — Research lab\n"
        "`!inventory` — Your items\n"
        "`!claims` — Unclaimed items\n\n"
        "*ACTIVE FEATURES:*\n"
        "🔥 Daily login streaks (+50-2000 silver)\n"
        "🔥 Combo multipliers (1.5x-3.0x)\n"
        "💎 Rare item drops (0.5%-1%)\n"
        "🎯 5 weekly challenges\n"
        "📡 Hourly sector broadcasts\n"
        "⚔️ Shield system (Phase 2A)\n",
        parse_mode="Markdown"
    )

# Group message handler (word fusion)
@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def on_group_message(message: types.Message):
    """Process word submissions in group"""
    if not eng.active:
        return
    
    text = message.text or ""
    if not text or text.startswith(('/', '!')):
        return
    
    u_id = str(message.from_user.id)
    user = get_user(u_id)
    
    if not user:
        user = {"username": message.from_user.first_name or "Player"}
        register_user(u_id, user["username"])
        user = get_user(u_id)
    
    if len(text) < 3 or text in eng.used_words:
        return
    
    if not can_spell(text, eng.letters):
        return
    
    if word_in_dict(text):
        # WORD IS VALID - Apply addictive mechanics
        pts = max(len(text) - 2, 1)
        db_name = user.get("username", message.from_user.first_name)
        eng.used_words.append(text)
        
        # 🔥 ADDICTIVE MECHANICS TRIGGER 🔥
        login_result = handle_daily_login(u_id)
        combo = increment_combo(u_id)
        rare_item = check_rare_drop()
        
        # Apply multiplier
        pts = int(pts * combo["multiplier"])
        
        # Build feedback
        fb = f"✅ `{text.upper()}` +{pts} pts  ⭐ +{pts} XP"
        
        if combo["multiplier"] > 1.0:
            fb += f" 🔥x{combo['multiplier']}"
        
        if combo["milestone_message"]:
            fb += f"\n\n{combo['milestone_message']}"
        
        if rare_item:
            fb += f"\n\n🎉 {format_rare_drop_notification(rare_item)}"
        
        # Save data
        add_points(u_id, pts, db_name)
        add_xp(u_id, pts)
        
        await message.reply(fb, parse_mode="Markdown")

# Game management commands
@dp.message(_cmd("fusion"))
async def cmd_fusion_start(message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("🃏 *GameMaster:* \"That command works in groups only, fool.\"", parse_mode="Markdown")
        return
    
    if eng.active:
        await message.answer("🃏 *GameMaster:* \"Game already running. Pay attention, peasant.\"", parse_mode="Markdown")
        return
    
    eng.active = True
    eng.round_number += 1
    eng.round_scores = {}
    eng.used_words = []
    
    # Get random words
    word1, word2 = await eng.fetch_two_words()
    eng.word1, eng.word2 = word1, word2
    eng.letters = "".join(sorted(set(word1 + word2)))
    
    msg = (
        f"{divider()}\n"
        f"🃏 *GameMaster:* \"Fresh meat...\"\n"
        f"{divider()}\n\n"
        f"📝 *FUSION PAIR*\n"
        f"`{word1.upper()}` + `{word2.upper()}`\n"
        f"{divider()}\n\n"
        f"⏱️ *120 SECONDS* — Go hard."
    )
    
    await message.answer(msg, parse_mode="Markdown")
    
    # 120 second game timer
    await asyncio.sleep(120)
    
    if eng.active:
        eng.active = False
        
        # Calculate winners
        if eng.round_scores:
            sorted_scores = sorted(eng.round_scores.items(), key=lambda x: x[1], reverse=True)
            msg = (
                f"{divider()}\n"
                f"🏆 *ROUND COMPLETE*\n"
                f"{divider()}\n\n"
            )
            
            medals = ["🥇", "🥈", "🥉"]
            for i, (name, pts) in enumerate(sorted_scores[:3]):
                medal = medals[i]
                msg += f"{medal} *{name}* — *{pts}* pts\n"
            
            msg += f"\n{divider()}"
        else:
            msg = f"{divider()}\n🃏 *No one guessed anything. Pathetic.*\n{divider()}"
        
        await message.answer(msg, parse_mode="Markdown")

# ═══════════════════════════════════════════════════════════════════════════
#  BACKGROUND TASKS
# ═══════════════════════════════════════════════════════════════════════════

async def sector_status_task(bot: Bot, chat_id: int):
    """Hourly sector status broadcasts"""
    sector_names = ["Badlands-8", "Crimson Wastes", "Frozen Abyss", "Molten Gorge"]
    resources = [("🪵", "Wood"), ("🧱", "Bronze"), ("⛓️", "Iron"), ("💎", "Diamond")]
    
    while True:
        try:
            await asyncio.sleep(3600)
            sector = random.choice(sector_names)
            emoji, resource = random.choice(resources)
            price = random.choice(["up 15%", "down 8%", "up 22%"])
            
            top = get_weekly_leaderboard(limit=1)
            overlord = top[0][0] if top else "The Council"
            
            msg = sector_status(sector, resource, emoji, price, overlord)
            await bot.send_message(chat_id, msg, parse_mode="Markdown")
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[SECTOR ERROR] {e}")
            await asyncio.sleep(10)

async def main():
    """Main bot entry point"""
    print("[TEST BOT] Bot starting...")
    load_dictionary()
    
    give_shields_to_all()
    
    # Start background tasks
    test_group_id = int(os.environ.get('CHECKMATE_HQ_GROUP_ID', '-1003773433371'))
    status_task = asyncio.create_task(sector_status_task(bot, test_group_id))
    
    try:
        await dp.start_polling(bot, handle_signals=False)
    finally:
        status_task.cancel()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
