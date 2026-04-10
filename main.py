"""
main.py — Checkmate HQ Bot
===========================
Architecture: flat @dp.message decorators with _cmd() filter.
on_group_message is registered LAST so every command above fires first.
Game loop: simple asyncio.sleep ticks, force_stop flag.
"""

import asyncio
import random
import httpx
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest

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
    )
    print("✅ Using Supabase database")
except Exception as e:
    print(f"⚠️  Supabase failed ({e}), using JSON database")
    from database import (
        get_user, register_user, add_points, get_weekly_leaderboard,
        get_alltime_leaderboard, add_silver, set_sector, upgrade_backpack,
        get_inventory, get_profile, add_xp, use_xp, use_silver,
        remove_inventory_item, load_sectors, save_user, calculate_level,
        check_level_up, add_unclaimed_item, get_unclaimed_items,
        claim_item, remove_unclaimed_item, award_powerful_locked_item,
        add_inventory_item,
    )
    # Stub shield helpers for JSON fallback
    def activate_shield(user_id): return False
    def is_shielded(user): return False

from initiation import initiation_router
from config import BOT_TOKEN, ENV_NAME, SUPABASE_URL as CONFIG_SUPABASE_URL, SUPABASE_KEY as CONFIG_SUPABASE_KEY

# ── Config ────────────────────────────────────────────────────────────────
API_TOKEN    = os.environ.get('API_TOKEN',    BOT_TOKEN)
SUPABASE_URL = os.environ.get('SUPABASE_URL', CONFIG_SUPABASE_URL).rstrip('/')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', CONFIG_SUPABASE_KEY)

bot = Bot(token=API_TOKEN)
dp  = Dispatcher()
dp.include_router(initiation_router)


# ═══════════════════════════════════════════════════════════════════════════
#  GAME ENGINE
# ═══════════════════════════════════════════════════════════════════════════

class GameEngine:
    def __init__(self):
        self.running          = False
        self.active           = False
        self.force_stop       = False
        self.word1            = ""
        self.word2            = ""
        self.letters          = ""
        self.scores           = {}
        self.used_words       = []
        self.msg_count        = 0
        self.games_played     = 0
        self.games_until_help = random.randint(3, 7)
        self.empty_rounds     = 0
        self.crates_dropping  = 0
        self.crate_claimers   = []
        self.crate_msg_id     = None

active_games: dict[int, GameEngine] = {}

def get_engine(chat_id: int) -> GameEngine:
    if chat_id not in active_games:
        active_games[chat_id] = GameEngine()
    return active_games[chat_id]


# ═══════════════════════════════════════════════════════════════════════════
#  LOAD DICTIONARY INTO MEMORY
# ═══════════════════════════════════════════════════════════════════════════

# Load dictionary from local file for fast validation (no Supabase calls)
DICTIONARY = set()

def load_dictionary():
    """Load all valid words into memory for O(1) lookups."""
    global DICTIONARY
    try:
        with open('SupaDB1.txt', 'r', encoding='utf-8') as f:
            # Skip header line
            lines = f.readlines()[1:]
            DICTIONARY = {word.strip().lower() for word in lines if word.strip()}
        print(f"[OK] Dictionary loaded: {len(DICTIONARY)} words from SupaDB1.txt")
    except Exception as e:
        print(f"[ERROR] Failed to load dictionary: {e}")
        DICTIONARY = set()


# ═══════════════════════════════════════════════════════════════════════════
#  WORD / DICTIONARY HELPERS
# ═══════════════════════════════════════════════════════════════════════════

async def fetch_words() -> tuple[str, str]:
    headers = {'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}'}
    url = f"{SUPABASE_URL}/rest/v1/Dictionary?word_length=eq.7&select=word&limit=1"
    async with httpx.AsyncClient() as c:
        try:
            r1 = await c.get(f"{url}&offset={random.randint(0,500)}", headers=headers, timeout=8.0)
            r2 = await c.get(f"{url}&offset={random.randint(0,500)}", headers=headers, timeout=8.0)
            w1 = r1.json()[0]['word'].upper() if r1.json() else "PLAYERS"
            w2 = r2.json()[0]['word'].upper() if r2.json() else "DANGERS"
            return w1, w2
        except Exception:
            return "PLAYERS", "DANGERS"

def word_in_dict(word: str) -> bool:
    """Check if word exists in local dictionary (fast, no network calls)."""
    return word.lower() in DICTIONARY

def can_spell(word: str, pool: str) -> bool:
    avail = list(pool)
    for ch in word:
        if ch in avail: avail.remove(ch)
        else: return False
    return True


# ═══════════════════════════════════════════════════════════════════════════
#  GAME LOOP  — tick-based, no asyncio.Event complexity
# ═══════════════════════════════════════════════════════════════════════════

ROUND_SECS = 120
BREAK_SECS = 15

async def game_loop(chat_id: int):
    eng = get_engine(chat_id)
    eng.running      = True
    eng.empty_rounds = 0

    try:
        while eng.running:
            try:
                eng.scores     = {}
                eng.used_words = []
                eng.msg_count  = 0
                eng.force_stop = False
                eng.active     = True

                eng.word1, eng.word2 = await fetch_words()
                eng.letters = (eng.word1 + eng.word2).lower()

                crate_note = ""
                if random.random() < 0.2:
                    eng.crates_dropping = random.randint(1, 2)
                    eng.crate_claimers  = []
                    crate_note = f"\n\n🎁 *BONUS:* {eng.crates_dropping} incoming!"
                else:
                    eng.crates_dropping = 0

                await bot.send_message(
                    chat_id,
                    f"🃏 *GameMaster:* \"Fresh meat. Let's see if you've learned *anything* since last time.\"\n\n"
                    f"📝 *WORDS:* `{eng.word1}`  `{eng.word2}`"
                    f"{crate_note}\n\n⏱️ 2 minutes. Don't disappoint me again.",
                    parse_mode="Markdown"
                )

                crate_dropped = False
                for elapsed in range(ROUND_SECS):
                    await asyncio.sleep(1)
                    if eng.force_stop:
                        break
                    if eng.crates_dropping > 0 and elapsed == 50 and not crate_dropped:
                        crate_dropped = True
                        m = await bot.send_message(
                            chat_id,
                            "⚡ *CRATE DROP!*",
                            parse_mode="Markdown"
                        )
                        eng.crate_msg_id   = m.message_id
                        eng.crate_claimers = []
                    if eng.crates_dropping == 0 and elapsed == 60:
                        await bot.send_message(
                            chat_id,
                            "⏱️ *GameMaster:* \"60 seconds remaining. PROVE you're not brain-dead. *Tick tock*.\"",
                            parse_mode="Markdown"
                        )

                eng.active = False
                ss = sorted(eng.scores.values(), key=lambda x: x['pts'], reverse=True)
                result = "🏆 *ROUND OVER*\n━━━━━━━━━━━━━━━\n"

                if not ss:
                    result += "Nobody scored. Pathetic."
                    eng.empty_rounds += 1
                else:
                    eng.empty_rounds = 0
                    try:
                        if eng.crates_dropping > 0 and eng.crate_claimers:
                            for cl in eng.crate_claimers:
                                add_unclaimed_item(str(cl['user_id']), "super_crate", 1)
                            result += f"🎁 {len(eng.crate_claimers)} player(s) grabbed mid-round crates!\n\n"
                    except Exception as e:
                        print(f"[ERROR] Crate handling: {e}")
                    
                    for i, p in enumerate(ss):
                        medal = ["🥇","🥈","🥉"][i] if i < 3 else f"{i+1}."
                        result += f"{medal} {p['name']} — {p['pts']} pts\n"
                        if i < 3:
                            try:
                                add_unclaimed_item(p['user_id'], "super_crate", 1)
                            except Exception as e:
                                print(f"[ERROR] Adding crate for {p['name']}: {e}")

                result += "\n`!weekly` | `!alltime` for full stats"
                await bot.send_message(chat_id, result, parse_mode="Markdown")

                # Level-up announcements
                try:
                    for uid, sd in eng.scores.items():
                        if sd.get("leveled_up"):
                            user = get_user(uid)
                            if user:
                                lvl = user.get('level', 1)
                                msg = (
                                    f"🎊 *LEVEL UP!* {sd['name']} reached *LEVEL {lvl}*!\n\n"
                                    f"🃏 *GameMaster:* \"Congratulations. You've achieved the bare minimum. Collect your participation trophy. Use `!claims` in DM.\n\n"
                                    f"✨ Bonus items awaiting."
                                )
                                add_unclaimed_item(uid, "super_crate", 1)
                                k = "xp_multiplier" if random.random() < 0.5 else "silver_multiplier"
                                add_unclaimed_item(uid, k, 1, xp_reward=0, multiplier_value=2)
                                if lvl % 5 == 0:
                                    iname, idesc = award_powerful_locked_item(uid)
                                    msg += f"\n\n⚡ *MILESTONE!* Unlocked: *{iname}*\n_{idesc}_"
                                await bot.send_message(chat_id, msg, parse_mode="Markdown")
                except Exception as e:
                    print(f"[ERROR] Level-up announcements: {e}")

                if eng.empty_rounds >= 3:
                    eng.running = False
                    await bot.send_message(
                        chat_id,
                        "🃏 *GameMaster:* \"*Three* empty rounds? Are you all *asleep*?! This is pathetic. Tell me when you grow a brain and type `!fusion` again.\"",
                        parse_mode="Markdown"
                    )
                    break

                eng.games_played += 1
                if eng.games_played >= eng.games_until_help:
                    await bot.send_message(chat_id, _help_text(), parse_mode="Markdown")
                    eng.games_until_help = eng.games_played + random.randint(3, 7)

                if eng.games_played % 10 == 0:
                    try:
                        lb = get_weekly_leaderboard()
                        if lb:
                            t = "🏆 *WEEKLY TOP 5*\n━━━━━━━━━━━━━━━\n"
                            for i, p in enumerate(lb[:5], 1):
                                medal = ["🥇","🥈","🥉"][i-1] if i<=3 else f"{i}."
                                t += f"{medal} {p['username']} — {p['points']} pts\n"
                            await bot.send_message(chat_id, t, parse_mode="Markdown")
                    except Exception as e:
                        print(f"[ERROR] Weekly leaderboard display: {e}")

                await asyncio.sleep(BREAK_SECS)
                
            except Exception as e:
                print(f"[ERROR] Round failed in chat {chat_id}: {e}")
                import traceback
                traceback.print_exc()
                try:
                    await bot.send_message(chat_id, f"❌ *ERROR:* {e}\n\nType `!fusion` to restart the game.", parse_mode="Markdown")
                except:
                    pass
                eng.running = False
                break

    except asyncio.CancelledError:
        pass
    finally:
        eng.active  = False
        eng.running = False


# ═══════════════════════════════════════════════════════════════════════════
#  TEXT HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _help_text() -> str:
    return (
        "🃏 *GameMaster:* \"Oh great, another lost soul needing hand-holding. How *delightful*.\"\n\n"
        "*QUICK START*\n"
        "`!tutorial` — Complete game walkthrough (DM only)\n"
        "`!fusion` — Start a word game round (group only)\n"
        "`!help` — This message\n\n"
        "*PLAYER COMMANDS* _(DM only)_\n"
        "`!profile` — Your stats, base, resources\n"
        "`!base` — Full base details, military, traps\n"
        "`!inventory` — Your items & crates\n"
        "`!claims` — Unclaimed rewards\n"
        "`!autoclaim` — Claim all rewards at once\n"
        "`!changename [Name]` — Change your username\n"
        "`!setup_base [Name]` — Create your first base\n"
        "`!changebasename [Name]` — Rename your base (1-time)\n"
        "`!lab` — Research lab: upgrade your army\n\n"
        "*GAME COMMANDS* _(group)_\n"
        "`!fusion` — Start new game round\n"
        "`!words` — Show current word pair\n"
        "`!forcerestart` — End the round\n"
        "`!weekly` — Weekly leaderboard\n"
        "`!alltime` — All-time leaderboard\n\n"
        "*INVITE FRIENDS*\n"
        "Enjoy the game? Invite others! https://t.me/checkmateHQ"
    )

def _unreg() -> str:
    return random.choice([
        "🃏 *GameMaster:* \"Who even *are* you? An unregistered ghost. How pathetic. DM me to exist.\"",
        "🃏 *GameMaster:* \"You're not real to me. Register in my DMs and *maybe* I'll acknowledge you.\"",
        "🃏 *GameMaster:* \"Nobody cares about unregistered nobodies. Go beg me for registration in private. *Now*.\"",
    ])

def _dm_only(cmd: str) -> str:
    return random.choice([
        f"🃏 *GameMaster:* \"Did you just expose your business to *everyone*? Brilliant move. Use `{cmd}` in my *PRIVATE* DMs, genius.\"",
        f"🃏 *GameMaster:* \"`{cmd}` is for PRIVATE conversations only. Stop embarrassing yourself publicly, idiot.\"",
        f"🃏 *GameMaster:* \"Oh look, another moron broadcasting personal stuff to the whole group. DM me next time, *please*.\"",
    ])


# ═══════════════════════════════════════════════════════════════════════════
#  COMMAND FILTER  — matches "!weekly", "/weekly", "!WEEKLY", "/weekly@BotName"
# ═══════════════════════════════════════════════════════════════════════════

def _cmd(*names):
    ns = {n.lower() for n in names}
    def check(text: str) -> bool:
        if not text: return False
        first = text.strip().split()[0].lstrip("/!").lower().split("@")[0]
        return first in ns
    return F.text.func(check)


# ═══════════════════════════════════════════════════════════════════════════
#  COMMAND HANDLERS  (all registered before on_group_message)
# ═══════════════════════════════════════════════════════════════════════════

@dp.message(_cmd("fusion"))
async def cmd_fusion(message: types.Message):
    if message.chat.type not in ("group","supergroup"):
        await message.answer("🃏 *GameMaster:* \"This is a *GROUP* game, genius. Why are you DMing me? Go to a group chat.\"", parse_mode="Markdown"); return
    eng = get_engine(message.chat.id)
    if eng.running:
        await message.answer("🃏 *GameMaster:* \"A game is ALREADY running, you blind buffoon. Pay attention next time.\"", parse_mode="Markdown"); return
    if not get_user(str(message.from_user.id)):
        await message.answer("🃏 *GameMaster:* \"An unregistered peasant summoning me? Fine. *Fine.* I'll start. But YOU—go beg for registration in my DMs. *NOW*.\"\n\n_Nobody plays unregistered._", parse_mode="Markdown")
    asyncio.create_task(game_loop(message.chat.id))


@dp.message(_cmd("forcerestart"))
async def cmd_forcerestart(message: types.Message):
    if message.chat.type not in ("group","supergroup"):
        await message.answer("🃏 *GameMaster:* \"This command is for GROUPS only. Stop wasting my time in private.\"", parse_mode="Markdown"); return
    eng = get_engine(message.chat.id)
    if not eng.running:
        await message.answer("🃏 *GameMaster:* \"No round is running, numbskull. Type `!fusion` to start one.\"", parse_mode="Markdown"); return
    eng.force_stop = True
    eng.active = False
    await message.answer("🃏 *GameMaster:* \"FINE. Terminating round because apparently you can't handle it. Fresh words incoming. Try not to mess this up.\"", parse_mode="Markdown")


@dp.message(_cmd("words"))
async def cmd_words(message: types.Message):
    if message.chat.type not in ("group","supergroup"):
        await message.answer("🃏 *GameMaster:* \"Groups ONLY. What part of that is confusing?\"", parse_mode="Markdown"); return
    eng = get_engine(message.chat.id)
    if not eng.active or not eng.word1:
        await message.answer("🃏 *GameMaster:* \"No round running. Stop asking stupid questions and type `!fusion`.\"", parse_mode="Markdown"); return
    await message.answer(f"📝 *CURRENT WORDS:* `{eng.word1}` + `{eng.word2}`", parse_mode="Markdown")


@dp.message(_cmd("weekly"))
async def cmd_weekly(message: types.Message):
    """Display weekly leaderboard with top scores this week."""
    user_id = str(message.from_user.id)
    user = get_user(user_id)
    
    if not user:
        await message.answer(_unreg(), parse_mode="Markdown")
        return
    
    # Get the weekly leaderboard
    try:
        lb = get_weekly_leaderboard(limit=10)
        print(f"[CMD_WEEKLY] Called by {user.get('username')} - got {len(lb)} players")
        
        text = "🏆 *WEEKLY LEADERBOARD*\n━━━━━━━━━━━━━━━\n"
        
        if not lb:
            text += "No scores yet this week. Shocking."
        else:
            for i, p in enumerate(lb, 1):
                medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."
                text += f"{medal} {p['username']} — {p['points']} pts\n"
        
        text += "\n━━━━━━━━━━━━━━━\n"
        text += "`!alltime` for all-time scores"
        
        await message.answer(text, parse_mode="Markdown")
    except Exception as e:
        print(f"[ERROR] cmd_weekly: {e}")
        import traceback
        traceback.print_exc()
        await message.answer("❌ Error retrieving leaderboard. Try again.", parse_mode="Markdown")


@dp.message(_cmd("alltime"))
async def cmd_alltime(message: types.Message):
    if not get_user(str(message.from_user.id)):
        await message.answer(_unreg(), parse_mode="Markdown"); return
    lb = get_alltime_leaderboard()
    text = "🏆 *ALL-TIME LEADERBOARD*\n━━━━━━━━━━━━━━━\n"
    if not lb:
        text += "Blank. Just like your future."
    else:
        for i, p in enumerate(lb, 1):
            medal = ["🥇","🥈","🥉"][i-1] if i<=3 else f"{i}."
            text += f"{medal} {p['username']} — {p['points']} pts\n"
    await message.answer(text, parse_mode="Markdown")


@dp.message(_cmd("help"))
async def cmd_help(message: types.Message):
    await message.answer(_help_text(), parse_mode="Markdown")


@dp.message(_cmd("tutorial"))
async def cmd_tutorial(message: types.Message):
    """Comprehensive game tutorial and walkthrough."""
    if message.chat.type != "private":
        await message.answer(_dm_only("!tutorial"), parse_mode="Markdown"); return
    
    tutorial = """
🃏 *WELCOME TO CHECKMATE HQ*
━━━━━━━━━━━━━━━━━━━━━━━━━━

*PART 1: THE BASICS*

🎮 *How to Play the Word Game*
1️⃣ `!fusion` starts a round in the group
2️⃣ Two random 7-letter words appear (e.g., PLAYING + FOREIGN)
3️⃣ Type ANY valid English word using ONLY those letters
4️⃣ Points = word length − 2 (4-letter word = 2 pts)
5️⃣ Highest scorers get bonus crates! (Top 3 = prizes)
6️⃣ Rounds last 2 minutes, then streak resets

⭐ *Your Streaks & Food*
• Build consecutive correct words = higher streaks
• At streak 3+, earn FOOD each guess
• Food feeds your base during wars
• Invalid words reset your streak to 0
• New round = new streak (automatic reset)

📊 *Resources Matter*
🪵 Wood (4-letter words) — Build structures
🧱 Bronze (5-letter words) — Military training
⛓️ Iron (6-letter words) — Fortifications
💎 Diamond (7-letter words) — Elite units
🏺 Relics (8+ letter words) — Ancient power

━━━━━━━━━━━━━━━━━━━━━━━━━━

*PART 2: YOUR PROFILE & IDENTITY*

👤 *Change Your Name*
Command: `!changename [NewName]`
• One-time change only (then you're stuck with it)
• GameMaster loves mockery: "Running from your past? Noted."
• Shows in leaderboards and scores

📍 *View Your Profile*
Command: `!profile`
Shows:
• Your level & XP progress
• Resources: wood, bronze, iron, diamond, relics
• Food reserves
• Silver balance (premium currency)
• Shield status
• Sector location

━━━━━━━━━━━━━━━━━━━━━━━━━━

*PART 3: BASE MANAGEMENT*

🏰 *Create Your First Base*
Command: `!setup_base [BaseName]`
• Creates your fortress in a random sector
• You get starting resources & units
• Sector determines which resources spawn more
• Station your troops there

🏗️ *Rename Your Base*
Command: `!changebasename [NewName]`
• Only one rename allowed (track it carefully)
• Shows your loyalty... or cowardice

👁️ *View Your Base Details*
Command: `!base`
Shows:
• Base name & level
• Resource reserves
• Military: Pawns, Knights, Bishops, Rooks, Queens, Kings
• Traps: Spike Pits, Arrow Towers, Cannons, Tesla Towers, Inferno
• Buffs & active shields
• War record (wins/losses)

🏅 *Level Up Your Base*
• Each level requires resources
• Higher level = more military slots
• Higher level = stronger defenses
• Improves your power in war

━━━━━━━━━━━━━━━━━━━━━━━━━━

*PART 4: INVENTORY & ITEMS*

📦 *Your Inventory*
Command: `!inventory`
• Max 5 slots (upgrade to 20)
• Shows all claimed items
• Crates ready to open
• Shields to activate
• Multipliers to use

🎁 *Claim Rewards*
Commands: `!claims` — See unclaimed items
Command: `!autoclaim` — Grab all at once
• Items wait until you claim them
• If inventory full, discard items first
• Random gifts: crates, powerful items, or resources

⚡ *Multiplier Items*
• XP Multiplier: Double/triple your XP gains
• When used: pick 5/10/15/20 guesses
• X multiplier applies to selected guesses
• Uses up and expires

🗑️ *Discard Items*
• Use 🗑️ button in inventory
• Frees up slots for new rewards
• Can't undo — think first!

━━━━━━━━━━━━━━━━━━━━━━━━━━

*PART 5: SECTORS & TELEPORTATION*

🌍 *What Are Sectors?*
• 9 different regions on the map
• Each has unique environments & perks
• Different sectors = different resource rates
• Better sectors = more competition

🧭 *Your Current Sector*
• Shown in `!profile`
• Determines resource availability
• Teleport to move between sectors

📍 *Teleport Between Sectors*
• Collect TELEPORT items from crates
• Use from inventory to jump sectors
• Strategy: find sectors with your preferred resources
• High-level players own the best sectors

━━━━━━━━━━━━━━━━━━━━━━━━━━

*PART 6: MILITARY & COMBAT*

⚔️ *Build an Army*
Command: `!base`
Units available:
• 👹 Pawns (1 power) — Cheap, weak
• 🗡️ Knights (3 power) — Balanced
• ⚜️ Bishops (5 power) — Magic damage
• 🏰 Rooks (8 power) — Fortress strength
• 👑 Queens (12 power) — Domination
• ⚔️ Kings (20 power) — Ultimate force

💪 *Train Soldiers*
• Costs resources (wood, bronze, iron)
• Higher tier = expensive (diamond/relics)
• More soldiers = higher power
• Power determines war outcomes

🛡️ *Shields Protect You*
• Everyone starts with PERMANENT shield
• Shields prevent attacks on your base
• Later: can be removed by enemy kings
• Gather resources while shielded

━━━━━━━━━━━━━━━━━━━━━━━━━━

*PART 7: DEFENSES & TRAPS*

🕳️ *Traps Defend Your Base*
Available:
• 🕳️ Spike Pits — Low damage, cheap
• 🏹 Arrow Towers — Medium damage
• 🔫 Cannons — Heavy damage
• ⚡ Tesla Towers — Area damage
• 🔥 Inferno — Massive AOE

🎯 *How Traps Work*
• Cost resources to build
• Damage invaders during war
• Research "Trap Mastery" for +60% damage
• More traps = stronger defense

━━━━━━━━━━━━━━━━━━━━━━━━━━

*PART 8: RESEARCH LABORATORY*

🔬 *Unlock Power Through Research*
Command: `!lab`
Spend resources to unlock:

⚙️ *Armor Plating*
Cost: 100 Iron + 50 Bronze
Effect: Soldiers take 20% less damage

⚡ *Speed Training*
Cost: 150 Wood + 100 Bronze
Effect: Armies attack 30% faster

🪓 *Deep Mining*
Cost: 20 Diamond + 200 Wood
Effect: Resource gathering +50% yield

👨‍👩‍👧‍👦 *Breeding Program*
Cost: 200 Food + 150 Bronze
Effect: Natural unit spawn +40%

🔩 *Trap Mastery*
Cost: 150 Iron + 25 Diamond
Effect: Traps deal 60% more damage

━━━━━━━━━━━━━━━━━━━━━━━━━━

*PART 9: LEADERBOARDS & RANKING*

🏆 *Weekly Leaderboard*
Command: `!weekly`
• Resets every Sunday 00:00 UTC
• Top players earn bonus rewards
• Ranked by points earned this week
• Compete in your group

🌟 *All-Time Leaderboard*
Command: `!alltime`
• Never resets
• Shows strongest players ever
• Bragging rights eternal
• Legend status

━━━━━━━━━━━━━━━━━━━━━━━━━━

*PART 10: COMING SOON*

🤝 *Alliances* (Soon™)
• Team up with other players
• Shared alliance shop & buffs
• Alliance wars & conquest
• Split spoils from victories

⚔️ *Wars & Conquest* (Soon™)
• Attack unshielded players
• Steal their resources
• Capture their sectors
• Build empires

💰 *Premium Shop* (Soon™)
• Real-money packs for impatient players
• Bundles with exclusive items
• Battle passes seasonal rewards

🎯 *Missions & Quests* (Soon™)
• Daily challenges
• Seasonal events
• Legendary item hunts

━━━━━━━━━━━━━━━━━━━━━━━━━━

*FINAL TIPS*

✅ *DO*
✓ Build your base before wars start
✓ Mine resources obsessively in group games
✓ Research upgrades for huge power boost
✓ Collect crates from game rounds
✓ Invite friends — more players = more fun!

❌ *DON'T*
✗ Waste resources early
✗ Neglect trap defenses
✗ Skip the research lab
✗ Discard valuable items carelessly
✗ Ignore your streak resets

🔗 *Share With Friends*
If you enjoy this game, and would love to play with your friends, share this link to others:
https://t.me/checkmateHQ

━━━━━━━━━━━━━━━━━━━━━━━━━━

Good luck, warrior. The GameMaster is watching. 👀
"""
    
    await message.answer(tutorial, parse_mode="Markdown")


@dp.message(_cmd("shop"))
async def cmd_shop(message: types.Message):
    await message.answer("🃏 *GameMaster:* \"The shop? Still under construction. Your impatience amuses me. Come back later, peasant.\"", parse_mode="Markdown")

@dp.message(_cmd("upgrade"))
async def cmd_upgrade(message: types.Message):
    await message.answer("🃏 *GameMaster:* \"*Queen's Satchel!* Nice try. Not ready yet.\n\nWhen it arrives: unlocks 20 inventory slots for 900 Naira.\n\nUntil then? Manage your pathetic 5 slots like an adult. Stop asking.\"", parse_mode="Markdown")


@dp.message(_cmd("profile"))
async def cmd_profile(message: types.Message):
    if message.chat.type != "private":
        await message.answer(_dm_only("!profile"), parse_mode="Markdown"); return
    u_id = str(message.from_user.id)
    profile = get_profile(u_id)
    if not profile:
        await message.answer("🃏 *GameMaster:* \"No profile? You haven't even *started* the tutorial? What are you doing here, fool? DM me, run `!start`, and actually play the game.\"", parse_mode="Markdown"); return
    bar = "█" * int(profile['xp_progress'] / profile['xp_needed'] * 20) + "░" * (20 - int(profile['xp_progress'] / profile['xp_needed'] * 20))
    shield_str = "🛡️ SHIELDED" if profile.get('shielded') else "⚔️ UNPROTECTED"
    
    # Format base resources
    base_res = profile.get('base_resources', {})
    base_name = profile.get('base_name') or "Nameless Base"
    resources_str = (
        f"🪵 Wood: {base_res.get('wood', 0)} | 🧱 Bronze: {base_res.get('bronze', 0)} | "
        f"⛓️ Iron: {base_res.get('iron', 0)} | 💎 Diamond: {base_res.get('diamond', 0)} | "
        f"🏺 Relics: {base_res.get('relics', 0)}"
    )
    food_str = f"🌽 Food: {profile.get('base_food', 0)}"
    
    await message.answer(
        f"🃏 *GameMaster:* \"Staring at your own reflection. Fine.\"\n\n"
        f"👤 *PROFILE: {profile['username']}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎖️ *LEVEL {profile['level']}*\n"
        f"⭐ XP: {profile['xp']} | [{bar}] {profile['xp_progress']}/100\n\n"
        f"💰 Silver: {profile['silver']}\n"
        f"📍 Sector: {profile.get('sector_display','Not Assigned')}\n"
        f"{shield_str}\n\n"
        f"📊 *STATS*\n"
        f"├─ Weekly Points: {profile['weekly_points']}\n"
        f"└─ All-Time Points: {profile['all_time_points']}\n\n"
        f"🏰 *BASE: {base_name}*\n"
        f"├─ {resources_str}\n"
        f"└─ {food_str}\n\n"
        f"📦 *INVENTORY*\n"
        f"├─ Claimed: {profile['inventory_count']}/{profile['backpack_slots']} slots\n"
        f"├─ Unclaimed: {profile['unclaimed_count']} items ⚠️\n"
        f"└─ Crates: {profile['crate_count']} | Shields: {profile['shield_count']}",
        parse_mode="Markdown"
    )


@dp.message(_cmd("inventory"))
async def cmd_inventory(message: types.Message):
    if message.chat.type != "private":
        await message.answer(_dm_only("!inventory"), parse_mode="Markdown"); return
    u_id = str(message.from_user.id)
    if not get_user(u_id):
        await message.answer("🃏 *GameMaster:* \"You have nothing. You ARE nothing. Register first.\"", parse_mode="Markdown"); return
    inv = get_inventory(u_id)
    if not inv:
        await message.answer("🃏 *GameMaster:* \"Your inventory is empty. How *pathetic*.\"", parse_mode="Markdown"); return

    rows = []
    for item in inv:
        iid   = item.get('id')
        iid_str = str(iid) if iid is not None else "0"
        itype = item.get('type','').lower()
        xp    = item.get('xp_reward', 0)
        print(f"[CMD_INV] Item ID: {iid} (type: {type(iid).__name__}) -> callback string: {iid_str}")
        if   "wood"   in itype and "crate" in itype: lbl, cb = f"🪵 WOOD CRATE ({xp} XP)",   f"open_{iid_str}"
        elif "bronze" in itype and "crate" in itype: lbl, cb = f"🥉 BRONZE CRATE ({xp} XP)", f"open_{iid_str}"
        elif "iron"   in itype and "crate" in itype: lbl, cb = f"⚙️ IRON CRATE ({xp} XP)",   f"open_{iid_str}"
        elif "super"  in itype and "crate" in itype: lbl, cb = f"🎁 SUPER CRATE ({xp} XP)",  f"open_{iid_str}"
        elif itype == "shield":                       lbl, cb = "🛡️ SHIELD — tap to ACTIVATE", f"activate_shield_{iid_str}"
        elif itype == "teleport":                     lbl, cb = "🌀 TELEPORT",                 f"teleport_{iid_str}"
        elif "multiplier" in itype:
            mult = item.get('multiplier_value', 2)
            kind = "XP" if "xp" in itype else "SILVER"
            lbl, cb = f"⚡ {kind} MULTIPLIER x{mult}", f"use_{iid_str}"
        elif "locked_" in itype:                      lbl, cb = "🔒 LEGENDARY [TOO POWERFUL]", f"info_{iid_str}"
        else:                                         lbl, cb = f"❓ {itype.upper()}",          f"use_{iid_str}"
        # Add action button and discard button on same row
        rows.append([
            InlineKeyboardButton(text=lbl, callback_data=cb),
            InlineKeyboardButton(text="🗑️ DISCARD", callback_data=f"discard_{iid_str}")
        ])

    profile = get_profile(u_id)
    su = profile['inventory_count'] if profile else len(inv)
    st = profile['backpack_slots']  if profile else 5
    await message.answer(
        f"📦 *YOUR INVENTORY*\n━━━━━━━━━━━━━━━\n📊 Slots: {su}/{st}\n\n*Items:* (tap to use or discard)",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode="Markdown"
    )


@dp.message(_cmd("claims"))
async def cmd_claims(message: types.Message):
    """Display unclaimed rewards with individual or auto-claim options."""
    if message.chat.type != "private":
        await message.answer(_dm_only("!claims"), parse_mode="Markdown"); return
    u_id = str(message.from_user.id)
    if not get_user(u_id):
        await message.answer("🃏 *GameMaster:* \"No account. Register first.\"", parse_mode="Markdown"); return
    
    unclaimed = get_unclaimed_items(u_id)
    if not unclaimed:
        await message.answer("🃏 *GameMaster:* \"No unclaimed rewards. Go earn something.\"", parse_mode="Markdown"); return

    locked_names = {
        "locked_legendary_artifact": "⚔️ LEGENDARY ARTIFACT",
        "locked_mythical_crown":     "👑 MYTHICAL CROWN",
        "locked_void_stone":         "🌑 VOID STONE",
        "locked_eternal_flame":      "🔥 ETERNAL FLAME",
        "locked_celestial_key":      "🗝️ CELESTIAL KEY",
    }
    item_labels = {
        "xp_multiplier":     lambda m: f"⚡ XP MULTIPLIER x{m}",
        "silver_multiplier": lambda m: f"💎 SILVER MULTIPLIER x{m}",
        "super_crate":  lambda _: "🎁 SUPER CRATE",
        "wood_crate":   lambda _: "🪵 WOOD CRATE",
        "bronze_crate": lambda _: "🥉 BRONZE CRATE",
        "iron_crate":   lambda _: "⚙️ IRON CRATE",
        "shield":       lambda _: "🛡️ SHIELD",
        "teleport":     lambda _: "🌀 TELEPORT",
    }

    rows = []
    for item in unclaimed:
        itype = item.get("type","").lower()
        mult  = item.get("multiplier_value", 0)
        iid   = item.get("id")
        iid_str = str(iid) if iid is not None else "0"
        xp    = item.get("xp_reward", 0)
        print(f"[CMD_CLAIMS] Item ID: {iid} (type: {type(iid).__name__}) -> callback string: {iid_str}")
        if "locked_" in itype:
            lbl = f"{locked_names.get(itype,'🔒 LEGENDARY')} [CLAIM]"
        else:
            fn  = item_labels.get(itype, lambda _: f"🎁 {itype.upper()}")
            xp_str = f" ({xp} XP)" if xp > 0 else ""
            lbl = f"{fn(mult)}{xp_str} [CLAIM]"
        # Add claim button and discard button on same row
        rows.append([
            InlineKeyboardButton(text=lbl, callback_data=f"claim_{iid_str}"),
            InlineKeyboardButton(text="🗑️ DISCARD", callback_data=f"discard_claim_{iid_str}")
        ])

    # Auto-claim all button at top
    rows.insert(0, [InlineKeyboardButton(text="⚡ AUTO-CLAIM ALL", callback_data="claim_all")])

    await message.answer(
        f"🎁 *UNCLAIMED REWARDS*\n━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ {len(unclaimed)} item(s) waiting!\n"
        f"💡 Tap *[CLAIM]* to move to inventory, *[AUTO-CLAIM ALL]* to claim everything, or *[DISCARD]* to get rid of items",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode="Markdown"
    )


@dp.message(_cmd("autoclaim"))
async def cmd_autoclaim(message: types.Message):
    """Auto-claim all unclaimed items to inventory."""
    if message.chat.type != "private":
        await message.answer(_dm_only("!autoclaim"), parse_mode="Markdown"); return
    u_id = str(message.from_user.id)
    if not get_user(u_id):
        await message.answer("🃏 *GameMaster:* \"No account. Register first.\"", parse_mode="Markdown"); return
    await _do_claim_all(message, u_id, is_command=True)


@dp.message(_cmd("changename"))
async def cmd_changename(message: types.Message):
    if message.chat.type != "private":
        await message.answer(_dm_only("!changename"), parse_mode="Markdown"); return
    u_id = str(message.from_user.id)
    user = get_user(u_id)
    if not user:
        await message.answer("🃏 *GameMaster:* \"Not registered. Can't change a name you don't have.\"", parse_mode="Markdown"); return
    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer("🃏 *GameMaster:* \"Usage: `!changename NewName`\"", parse_mode="Markdown"); return
    new_name = parts[1].strip()[:20]
    old_name = user.get("username", message.from_user.first_name)
    if new_name.lower() == old_name.lower():
        await message.answer(f"🃏 *GameMaster:* \"You're already '{old_name}'. Changing nothing.\"", parse_mode="Markdown"); return
    user["username"] = new_name
    save_user(u_id, user)
    await message.answer(f"✅ Name changed: *{old_name}* → *{new_name}*\n🃏 *GameMaster:* \"Running from your past? Noted.\"", parse_mode="Markdown")


@dp.message(_cmd("setup_base"))
async def cmd_setup_base(message: types.Message):
    if message.chat.type != "private":
        await message.answer(_dm_only("!setup_base"), parse_mode="Markdown"); return
    
    u_id = str(message.from_user.id)
    user = get_user(u_id)
    
    if not user:
        await message.answer("🃏 *GameMaster:* \"You haven't survived initiation. Use `/start` first.\"", parse_mode="Markdown"); return
    
    if user.get("base_name"):
        await message.answer(f"🃏 *GameMaster:* \"Your loyalty is fickle. You already rule **{user['base_name']}**.\"", parse_mode="Markdown"); return
    
    # Extract base name from message
    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("🃏 *GameMaster:* \"A fortress needs a name. Use: `!setup_base [Name]`\"", parse_mode="Markdown"); return
    
    base_name = parts[1].strip()[:25]
    
    # Initialize base structure
    user["base_name"] = base_name
    user["base_level"] = 1
    user["sector"] = random.randint(1, 9)  # Random sector 1-9
    user["war_points"] = 0
    user["wins"] = 0
    user["losses"] = 0
    user["kings_captured"] = 0
    user["times_captured"] = 0
    user["base_name_changes"] = 0  # Track name changes (limit to 1)
    user["alliance_id"] = None
    
    # Initialize base resources and military
    user["base_resources"] = {
        "resources": {"wood": 20, "bronze": 10, "iron": 0, "diamond": 0, "relics": 0},
        "food": 50,
        "current_streak": 0
    }
    user["military"] = {"pawn": 5}  # Start with 5 footmen
    user["traps"] = {}
    user["buffs"] = {}
    
    try:
        save_user(u_id, user)
        print(f"[BASE] {user.get('username', message.from_user.first_name)} created base '{base_name}'")
        
        await message.answer(
            f"🚩 **TERRITORY CLAIMED**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🏰 **Base:** {base_name}\n"
            f"📍 **Sector:** {user['sector']}\n"
            f"⭐ **Level:** 1\n"
            f"🛡️ **Garrison:** 5x Footmen\n\n"
            f"🃏 *GameMaster:* \"Welcome to the map, Lord {message.from_user.first_name}. Try not to let it burn.\"",
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"[ERROR] Failed to create base for {u_id}: {e}")
        import traceback
        traceback.print_exc()
        await message.answer(f"❌ Error creating base: {str(e)[:100]}", parse_mode="Markdown")


@dp.message(_cmd("changebasename"))
async def cmd_changebasename(message: types.Message):
    if message.chat.type != "private":
        await message.answer(_dm_only("!changebasename"), parse_mode="Markdown"); return
    
    u_id = str(message.from_user.id)
    user = get_user(u_id)
    
    if not user:
        await message.answer("🃏 *GameMaster:* \"You have no base to rename.\"", parse_mode="Markdown"); return
    
    if not user.get("base_name"):
        await message.answer("🃏 *GameMaster:* \"You haven't established a base yet. Use `!setup_base`\"", parse_mode="Markdown"); return
    
    # Check if they've already used their one name change
    if user.get("base_name_changes", 0) >= 1:
        await message.answer("🃏 *GameMaster:* \"You've already renamed your base once. That's your lot.\"", parse_mode="Markdown"); return
    
    # Extract new base name
    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("🃏 *GameMaster:* \"Usage: `!changebasename [New Name]`\"", parse_mode="Markdown"); return
    
    new_name = parts[1].strip()[:25]
    old_name = user.get("base_name", "Unknown")
    
    if new_name.lower() == old_name.lower():
        await message.answer("🃏 *GameMaster:* \"Same name. Nothing changes.\"", parse_mode="Markdown"); return
    
    user["base_name"] = new_name
    user["base_name_changes"] = user.get("base_name_changes", 0) + 1
    save_user(u_id, user)
    
    await message.answer(
        f"✅ **BASE RENAMED**\n"
        f"🏰 *{old_name}* → **{new_name}**\n\n"
        f"🃏 *GameMaster:* \"History rewritten. How delightfully dishonest.\"",
        parse_mode="Markdown"
    )


@dp.message(_cmd("lab"))
async def cmd_research_lab(message: types.Message):
    """Science Laboratory: Spend resources to unlock powerful abilities."""
    if message.chat.type != "private":
        await message.answer(_dm_only("!lab"), parse_mode="Markdown"); return
    
    u_id = str(message.from_user.id)
    user = get_user(u_id)
    
    if not user:
        await message.answer("🃏 *GameMaster:* \"You're not even registered, fool. Can't research nothing.\"", parse_mode="Markdown"); return
    
    # Define research upgrades
    researches = {
        "armor_plating": {
            "name": "⚙️ Armor Plating",
            "desc": "Soldiers take 20% less damage in combat",
            "cost": {"iron": 100, "bronze": 50},
            "bonus": {"defense": 0.20}
        },
        "speed_training": {
            "name": "⚡ Speed Training", 
            "desc": "Armies attack 30% faster, capturing bases in less time",
            "cost": {"wood": 150, "bronze": 100},
            "bonus": {"attack_speed": 0.30}
        },
        "resource_extraction": {
            "name": "🪓 Deep Mining",
            "desc": "Resource gathering yield increased by 50%",
            "cost": {"diamond": 20, "wood": 200},
            "bonus": {"resource_yield": 0.50}
        },
        "population_growth": {
            "name": "👨‍👩‍👧‍👦 Breeding Program",
            "desc": "Population growth increased by 40%—more soldiers spawn naturally",
            "cost": {"food": 200, "bronze": 150},
            "bonus": {"unit_spawn": 0.40}
        },
        "trap_efficiency": {
            "name": "🔩 Trap Mastery",
            "desc": "Traps deal 60% more damage to invaders",
            "cost": {"iron": 150, "diamond": 25},
            "bonus": {"trap_damage": 0.60}
        }
    }
    
    user_researches = user.get('researches', {})
    
    txt = "🔬 *SCIENCE LABORATORY*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    txt += "*AVAILABLE UPGRADES:*\n\n"
    
    rows = []
    for key, research in researches.items():
        if user_researches.get(key):
            txt += f"✅ {research['name']} *(ALREADY RESEARCHED)*\n"
        else:
            cost_str = " + ".join([f"{v} {k.title()}" for k, v in research['cost'].items()])
            txt += f"{research['name']}\n*Cost:* {cost_str}\n*Effect:* {research['desc']}\n\n"
            rows.append([InlineKeyboardButton(text=f"Research {research['name'].split()[0]}", 
                                            callback_data=f"research_{key}")])
    
    txt += "\n🃏 *GameMaster:* \"Invest in power. Or remain weak. Entropy cares not.\"" 
    
    if rows:
        await message.answer(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="Markdown")
    else:
        await message.answer(txt + "\n\n*All researches unlocked!*", parse_mode="Markdown")


@dp.message(_cmd("base"))
async def cmd_base(message: types.Message):
    if message.chat.type != "private":
        await message.answer(_dm_only("!base"), parse_mode="Markdown"); return
    
    u_id = str(message.from_user.id)
    user = get_user(u_id)
    
    if not user:
        await message.answer("🃏 *GameMaster:* \"You have no profile.\"", parse_mode="Markdown"); return
    
    if not user.get("base_name"):
        await message.answer("🃏 *GameMaster:* \"You haven't claimed a base. Use `!setup_base [Name]`\"", parse_mode="Markdown"); return
    
    # Calculate base level from XP
    xp = user.get("xp", 0)
    base_level = 1 + (xp // 1000)
    
    # Get base resources
    base_res = user.get("base_resources", {})
    if isinstance(base_res, str):  # Just in case it comes back as string
        import json as json_lib
        try:
            base_res = json_lib.loads(base_res)
        except:
            base_res = {}
    resources = base_res.get("resources", {})
    food = base_res.get("food", 0)
    
    # Get military with better display
    military = user.get("military", {})
    troop_emojis = {
        "pawn": ("👹 Pawns", 1),
        "knight": ("🗡️ Knights", 3),
        "bishop": ("⚜️ Bishops", 5),
        "rook": ("🏰 Rooks", 8),
        "queen": ("👑 Queens", 12),
        "king": ("⚔️ Kings", 20)
    }
    
    military_lines = []
    total_troops = 0
    for unit_type, count in military.items():
        if count > 0:
            emoji_name, power = troop_emojis.get(unit_type, (f"❓ {unit_type.capitalize()}", 1))
            military_lines.append(f"├─ {emoji_name}: {count}")
            total_troops += count
    
    military_str = "\n".join(military_lines) if military_lines else "├─ 👹 Pawns: 0"
    if military_str:
        military_str += f"\n└─ **Total Troops:** {total_troops}"
    
    # Get traps with better display
    traps = user.get("traps", {})
    trap_emojis = {
        "spike_pit": "🕳️ Spike Pits",
        "arrow_tower": "🏹 Arrow Towers",
        "cannon": "🔫 Cannons",
        "tesla_tower": "⚡ Tesla Towers",
        "inferno": "🔥 Inferno"
    }
    
    trap_lines = []
    for trap_type, count in sorted(traps.items()):
        if count > 0:
            emoji_name = trap_emojis.get(trap_type, f"❓ {trap_type.replace('_', ' ').title()}")
            trap_lines.append(f"├─ {emoji_name}: {count}")
    
    traps_str = "\n".join(trap_lines) if trap_lines else "├─ No traps built"
    if traps_str and "Total" not in traps_str:
        total_traps = sum(traps.values())
        traps_str += f"\n└─ **Total Traps:** {total_traps}"
    
    # Get buffs
    buffs = user.get("buffs", {})
    buffs_str = "None" if not buffs else ", ".join([f"{name.capitalize()}" for name in buffs.keys()])
    
    # Get alliance info
    alliance_id = user.get("alliance_id")
    alliance_str = "Not in alliance" if not alliance_id else f"Alliance: {alliance_id}"
    
    # War record
    wins = user.get("wins", 0)
    losses = user.get("losses", 0)
    kings_captured = user.get("kings_captured", 0)
    times_captured = user.get("times_captured", 0)
    war_points = user.get("war_points", 0)
    
    # Calculate power (simple formula)
    res_power = sum(resources.values()) * 10
    military_power = sum(military.values()) * 50
    base_power = base_level * 100
    total_power = res_power + military_power + base_power
    
    # Get sector
    sector = user.get("sector", "Unknown")
    
    # Build comprehensive base info
    info = (
        f"🏰 **{user.get('base_name', 'Unnamed')}**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⭐ **BASE STATS**\n"
        f"├─ **Level:** {base_level} (XP: {xp}/1M)\n"
        f"├─ **Sector:** {sector}\n"
        f"├─ **Power:** ⚡ {total_power}\n"
        f"└─ **War Points:** 🎖️ {war_points}\n\n"
        f"🪵 **RESOURCES**\n"
        f"├─ 🪵 Wood: {resources.get('wood', 0)}\n"
        f"├─ 🧱 Bronze: {resources.get('bronze', 0)}\n"
        f"├─ ⛓️ Iron: {resources.get('iron', 0)}\n"
        f"├─ 💎 Diamond: {resources.get('diamond', 0)}\n"
        f"├─ 🏺 Relics: {resources.get('relics', 0)}\n"
        f"└─ 🍖 Food: {food}\n\n"
        f"⚔️ **MILITARY**\n"
        f"{military_str}\n\n"
        f"🔱 **TRAPS**\n"
        f"{traps_str}\n\n"
        f"✨ **BUFFS**\n"
        f"└─ {buffs_str}\n\n"
        f"👥 **ALLIANCE**\n"
        f"└─ {alliance_str}\n\n"
        f"⚔️ **WAR RECORD**\n"
        f"├─ **Wins:** 🏆 {wins}\n"
        f"├─ **Losses:** ⚰️ {losses}\n"
        f"├─ **Kings Captured:** 👑 {kings_captured}\n"
        f"└─ **Times Captured:** 🔒 {times_captured}\n\n"
        f"🃏 *GameMaster:* \"Your fortress. Fragile as it may be.\""
    )
    
    await message.answer(info, parse_mode="Markdown")


@dp.message(_cmd("tutorial", "start"))
async def cmd_tutorial(message: types.Message, state: FSMContext):
    if message.chat.type != "private":
        await message.answer(_dm_only("!tutorial"), parse_mode="Markdown"); return
    from initiation import Trial
    u_id = str(message.from_user.id)
    user = get_user(u_id)
    cmd  = message.text.strip().lstrip("/!").lower().split("@")[0]
    if user and user.get("completed_tutorial") and cmd == "tutorial":
        await message.answer("🃏 *GameMaster:* \"You've already been through the trials. Try `!fusion` in the group.\"", parse_mode="Markdown"); return
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ I'm ready to enter", callback_data="trial_yes")],
        [InlineKeyboardButton(text="🚪 I'm just lost",       callback_data="trial_no")],
    ])
    await message.answer(
        "🃏 *GameMaster:* \"Well, well, well. Look what crawled into my domain.\"\n\n"
        "\"You show up unannounced, uninvited, probably unprepared. I don't care who you are.\"\n\n"
        "\"Are you here to join *The 64*? Or just wandering in by accident?\"",
        parse_mode="Markdown", reply_markup=markup
    )
    await state.set_state(Trial.awaiting_username)


@dp.message(_cmd("open"))
async def cmd_open(message: types.Message):
    if message.chat.type != "private":
        await message.answer("🃏 *GameMaster:* \"Open crates in *private*, not here.\"", parse_mode="Markdown"); return
    import re; m = re.search(r'\d+', message.text)
    if not m:
        await message.answer("🃏 *GameMaster:* \"Usage: `!open 1`\"", parse_mode="Markdown"); return
    pos = int(m.group()) - 1
    inv = get_inventory(str(message.from_user.id))
    if 0 <= pos < len(inv):
        await _do_open_crate(message, str(message.from_user.id), inv[pos]['id'])


@dp.message(_cmd("use"))
async def cmd_use(message: types.Message):
    if message.chat.type != "private":
        await message.answer("🃏 *GameMaster:* \"Use items in *private*, fool.\"", parse_mode="Markdown"); return
    import re; m = re.search(r'\d+', message.text)
    if not m:
        await message.answer("🃏 *GameMaster:* \"Usage: `!use 1`\"", parse_mode="Markdown"); return
    pos = int(m.group()) - 1
    inv = get_inventory(str(message.from_user.id))
    if 0 <= pos < len(inv):
        await _do_use_item(message, str(message.from_user.id), inv[pos]['id'])


# ═══════════════════════════════════════════════════════════════════════════
#  CALLBACK HANDLERS
# ═══════════════════════════════════════════════════════════════════════════

@dp.callback_query(F.data.startswith("claim_all"))
async def cb_claim_all(query: types.CallbackQuery):
    await query.answer()
    u_id = str(query.from_user.id)
    await _do_claim_all(query.message, u_id, edit=True)


@dp.callback_query(F.data.startswith("claim_"))
async def cb_claim(query: types.CallbackQuery):
    await query.answer()
    u_id = str(query.from_user.id)
    try:
        raw_id = query.data.rsplit("_", 1)[1]  # Get everything after the last underscore
        item_id = int(raw_id)
        print(f"[CB_CLAIM] Parsed callback_data='{query.data}' -> item_id={item_id}")
    except (IndexError, ValueError, TypeError) as e:
        print(f"[CB_CLAIM ERROR] Failed to parse callback_data='{query.data}': {e}")
        await query.answer("Invalid item.", show_alert=True); return

    ok, msg = claim_item(u_id, item_id)
    if not ok:
        await query.answer(f"❌ {msg}", show_alert=True); return

    remaining = get_unclaimed_items(u_id)
    if not remaining:
        await query.message.edit_text(
            "✅ *Item CLAIMED!*\n\n🃏 *GameMaster:* \"All claimed. Good little minion.\"",
            parse_mode="Markdown"
        )
    else:
        # Rebuild the claims list in-place with discard buttons
        locked_names = {
            "locked_legendary_artifact": "⚔️ LEGENDARY ARTIFACT",
            "locked_mythical_crown":     "👑 MYTHICAL CROWN",
            "locked_void_stone":         "🌑 VOID STONE",
            "locked_eternal_flame":      "🔥 ETERNAL FLAME",
            "locked_celestial_key":      "🗝️ CELESTIAL KEY",
        }
        item_labels = {
            "xp_multiplier":     lambda m: f"⚡ XP MULTIPLIER x{m}",
            "silver_multiplier": lambda m: f"💎 SILVER MULTIPLIER x{m}",
            "super_crate":  lambda _: "🎁 SUPER CRATE",
            "wood_crate":   lambda _: "🪵 WOOD CRATE",
            "bronze_crate": lambda _: "🥉 BRONZE CRATE",
            "iron_crate":   lambda _: "⚙️ IRON CRATE",
            "shield":       lambda _: "🛡️ SHIELD",
            "teleport":     lambda _: "🌀 TELEPORT",
        }
        rows = [[InlineKeyboardButton(text="⚡ AUTO-CLAIM ALL", callback_data="claim_all")]]
        for item in remaining:
            itype = item.get("type","").lower()
            mult  = item.get("multiplier_value", 0)
            iid   = item.get("id")
            iid_str = str(iid) if iid is not None else "0"
            xp    = item.get("xp_reward", 0)
            print(f"[CLAIM_REFRESH] Item ID: {iid} (type: {type(iid).__name__}) -> callback string: {iid_str}")
            if "locked_" in itype:
                lbl = f"{locked_names.get(itype,'🔒 LEGENDARY')} [CLAIM]"
            else:
                fn  = item_labels.get(itype, lambda _: f"🎁 {itype.upper()}")
                xp_str = f" ({xp} XP)" if xp > 0 else ""
                lbl = f"{fn(mult)}{xp_str} [CLAIM]"
            rows.append([
                InlineKeyboardButton(text=lbl, callback_data=f"claim_{iid_str}"),
                InlineKeyboardButton(text="🗑️ DISCARD", callback_data=f"discard_claim_{iid_str}")
            ])
        await query.message.edit_text(
            f"✅ *Item CLAIMED!*\n\n🎁 *{len(remaining)}* item(s) remaining",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
            parse_mode="Markdown"
        )


@dp.callback_query(F.data.startswith("discard_claim_"))
async def cb_discard_claim(callback: types.CallbackQuery):
    """Discard an unclaimed item (delete it completely)."""
    try:
        # Parse item_id from callback data format: "discard_claim_5"
        # Use rsplit with maxsplit=1 to get the last part (in case ID has underscores)
        parts = callback.data.rsplit('_', 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid format: {callback.data}")
        raw_id = parts[1]
        item_id = int(raw_id)
        print(f"[DISCARD_CLAIM] Parsed callback_data='{callback.data}' -> item_id={item_id}")
    except (IndexError, ValueError, TypeError) as e:
        print(f"[DISCARD_CLAIM ERROR] Failed to parse callback_data='{callback.data}': {e}")
        await callback.answer("❌ Invalid item.", show_alert=True)
        return
    
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    if not user:
        await callback.answer("Account not found.", show_alert=True); return
    
    unclaimed = user.get('unclaimed_items', [])
    print(f"[DISCARD_CLAIM] User {u_id}: Looking for item_id={item_id} in {len(unclaimed)} unclaimed items")
    print(f"[DISCARD_CLAIM] Available IDs: {[it.get('id') for it in unclaimed]}")
    print(f"[DISCARD_CLAIM] Available ID types: {[(it.get('id'), type(it.get('id')).__name__) for it in unclaimed]}")
    
    item = next((it for it in unclaimed if it.get('id') == item_id), None)
    
    if not item:
        await callback.answer("❌ Item not found.", show_alert=True); return
    
    # Remove from unclaimed
    user['unclaimed_items'] = [it for it in unclaimed if it.get('id') != item_id]
    save_user(u_id, user)
    
    item_type = item.get('type', 'Unknown').upper()
    await callback.answer(f"🗑️ {item_type} discarded permanently.", show_alert=True)
    
    # Refresh claims display
    remaining = get_unclaimed_items(u_id)
    if not remaining:
        await callback.message.edit_text(
            "🎁 *UNCLAIMED REWARDS*\n━━━━━━━━━━━━━━━━━━━\n\n"
            "✅ No more unclaimed items!",
            parse_mode="Markdown"
        )
    else:
        # Rebuild unclaimed list
        locked_names = {
            "locked_legendary_artifact": "⚔️ LEGENDARY ARTIFACT",
            "locked_mythical_crown":     "👑 MYTHICAL CROWN",
            "locked_void_stone":         "🌑 VOID STONE",
            "locked_eternal_flame":      "🔥 ETERNAL FLAME",
            "locked_celestial_key":      "🗝️ CELESTIAL KEY",
        }
        item_labels = {
            "xp_multiplier":     lambda m: f"⚡ XP MULTIPLIER x{m}",
            "silver_multiplier": lambda m: f"💎 SILVER MULTIPLIER x{m}",
            "super_crate":  lambda _: "🎁 SUPER CRATE",
            "wood_crate":   lambda _: "🪵 WOOD CRATE",
            "bronze_crate": lambda _: "🥉 BRONZE CRATE",
            "iron_crate":   lambda _: "⚙️ IRON CRATE",
            "shield":       lambda _: "🛡️ SHIELD",
            "teleport":     lambda _: "🌀 TELEPORT",
        }
        rows = [[InlineKeyboardButton(text="⚡ AUTO-CLAIM ALL", callback_data="claim_all")]]
        for itm in remaining:
            itype = itm.get("type","").lower()
            mult  = itm.get("multiplier_value", 0)
            iid   = itm.get("id")
            xp    = itm.get("xp_reward", 0)
            # Ensure iid is a string for callback_data
            iid_str = str(iid) if iid is not None else "0"
            print(f"[CLAIMS_REBUILD] Item ID: {iid} (type: {type(iid).__name__}) -> callback string: {iid_str}")
            if "locked_" in itype:
                lbl = f"{locked_names.get(itype,'🔒 LEGENDARY')} [CLAIM]"
            else:
                fn  = item_labels.get(itype, lambda _: f"🎁 {itype.upper()}")
                xp_str = f" ({xp} XP)" if xp > 0 else ""
                lbl = f"{fn(mult)}{xp_str} [CLAIM]"
            rows.append([
                InlineKeyboardButton(text=lbl, callback_data=f"claim_{iid_str}"),
                InlineKeyboardButton(text="🗑️ DISCARD", callback_data=f"discard_claim_{iid_str}")
            ])
        await callback.message.edit_text(
            f"🎁 *UNCLAIMED REWARDS*\n━━━━━━━━━━━━━━━━━━━\n⚠️ {len(remaining)} item(s) remaining",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
            parse_mode="Markdown"
        )


@dp.callback_query(F.data.startswith("open_"))
async def cb_open(callback: types.CallbackQuery):
    import re; m = re.search(r'\d+', callback.data)
    if m: await _do_open_crate(callback.message, str(callback.from_user.id), int(m.group()))
    await callback.answer()


@dp.callback_query(F.data.startswith("activate_shield_"))
async def cb_activate_shield(callback: types.CallbackQuery):
    u_id = str(callback.from_user.id)
    import re; m = re.search(r'\d+', callback.data)
    if not m: await callback.answer("Invalid.", show_alert=True); return
    item_id = int(m.group())
    # Remove the shield from inventory and set shield_expires
    user = get_user(u_id)
    if not user: await callback.answer("Account not found.", show_alert=True); return
    inv = user.get('inventory', [])
    shield = next((it for it in inv if it.get('id') == item_id and it.get('type') == 'shield'), None)
    if not shield: await callback.answer("Shield not found.", show_alert=True); return

    from datetime import datetime, timedelta
    import json
    user['inventory'] = [it for it in inv if it.get('id') != item_id]
    user['shield_expires'] = (datetime.utcnow() + timedelta(hours=24)).isoformat()
    save_user(u_id, user)

    await callback.answer("🛡️ Shield activated! Protected for 24 hours.", show_alert=True)
    await callback.message.edit_text(
        "🛡️ *SHIELD ACTIVATED!*\n\n"
        "You are now *SHIELDED* for the next 24 hours.\n"
        "Your name will show as **[🛡️ Shielded]** in leaderboards.\n\n"
        "🃏 *GameMaster:* \"Even cowards deserve protection. Temporarily.\"",
        parse_mode="Markdown"
    )


@dp.callback_query(F.data.startswith("use_"))
async def cb_use(callback: types.CallbackQuery):
    try:
        import re
        m = re.search(r'\d+', callback.data)
        if not m:
            await callback.answer("❌ Invalid item ID.", show_alert=True)
            return
        item_id = int(m.group())
        await _do_use_item(callback.message, str(callback.from_user.id), item_id)
        await callback.answer()
    except Exception as e:
        print(f"[CB_USE ERROR] {e}")
        await callback.answer(f"❌ Error: {str(e)}", show_alert=True)


@dp.callback_query(F.data.startswith("activate_mult_"))
async def cb_activate_multiply(callback: types.CallbackQuery):
    """Activate multiplier with selected quantity."""
    try:
        import re
        # Parse: activate_mult_ITEMID_QUANTITY
        m = re.search(r'activate_mult_(\d+)_(\d+)', callback.data)
        if not m:
            await callback.answer("❌ Invalid format.", show_alert=True)
            return
        item_id = int(m.group(1))
        quantity = int(m.group(2))
        
        u_id = str(callback.from_user.id)
        inv = get_inventory(u_id)
        item = next((it for it in inv if it.get('id') == item_id), None)
        
        if not item or "multiplier" not in item.get('type', '').lower():
            await callback.answer("❌ Item not found or not a multiplier.", show_alert=True)
            return
        
        mult = item.get('multiplier_value', 2)
        kind = "XP" if "xp" in item.get('type', '').lower() else "SILVER"
        
        # Activate the multiplier (store in buffs JSONB)
        user = get_user(u_id)
        if user:
            buffs = user.get('buffs', {})
            buffs['multiplier_type'] = kind.lower()
            buffs['multiplier_active'] = mult
            buffs['multiplier_count'] = quantity
            user['buffs'] = buffs
            save_user(u_id, user)
        
        remove_inventory_item(u_id, item_id)
        
        await callback.message.edit_text(
            f"⚡ *{kind} MULTIPLIER x{mult} ACTIVATED!*\n\n"
            f"Your next {quantity} word guesses give x{mult} {kind}!\n"
            f"🃏 *GameMaster:* \"Make them count, or waste them. Either way, entertain me.\"",
            parse_mode="Markdown"
        )
        await callback.answer()
    except Exception as e:
        print(f"[CB_ACTIVATE_MULT ERROR] {e}")
        await callback.answer(f"❌ Error: {str(e)}", show_alert=True)



@dp.callback_query(F.data.startswith("research_"))
async def cb_research(callback: types.CallbackQuery):
    """Research unlock callback."""
    try:
        research_key = callback.data.replace("research_", "")
        u_id = str(callback.from_user.id)
        user = get_user(u_id)
        
        if not user:
            await callback.answer("❌ User not found.", show_alert=True)
            return
        
        # Research definitions
        researches = {
            "armor_plating": {"name": "⚙️ Armor Plating", "cost": {"iron": 100, "bronze": 50}},
            "speed_training": {"name": "⚡ Speed Training", "cost": {"wood": 150, "bronze": 100}},
            "resource_extraction": {"name": "🪓 Deep Mining", "cost": {"diamond": 20, "wood": 200}},
            "population_growth": {"name": "👨‍👩‍👧‍👦 Breeding Program", "cost": {"food": 200, "bronze": 150}},
            "trap_efficiency": {"name": "🔩 Trap Mastery", "cost": {"iron": 150, "diamond": 25}}
        }
        
        if research_key not in researches:
            await callback.answer("❌ Unknown research.", show_alert=True)
            return
        
        research = researches[research_key]
        
        # Check if already researched
        if user.get('researches', {}).get(research_key):
            await callback.answer("✅ Already researched!", show_alert=True)
            return
        
        # Check resources
        base_res = user.get('base_resources', {})
        resources = base_res.get('resources', {})
        
        for res_type, cost in research['cost'].items():
            available = resources.get(res_type, 0) if res_type != 'food' else base_res.get('food', 0)
            if available < cost:
                await callback.answer(f"❌ Need {cost} {res_type}, have {available}", show_alert=True)
                return
        
        # Deduct resources
        for res_type, cost in research['cost'].items():
            if res_type == 'food':
                base_res['food'] = base_res.get('food', 0) - cost
            else:
                resources[res_type] = resources.get(res_type, 0) - cost
        
        # Mark as researched
        user_researches = user.get('researches', {})
        user_researches[research_key] = True
        user['researches'] = user_researches
        base_res['resources'] = resources
        user['base_resources'] = base_res
        save_user(u_id, user)
        
        await callback.message.edit_text(
            f"🔬 *RESEARCH COMPLETE!*\n\n"
            f"{research['name']} unlocked!\n\n"
            f"🃏 *GameMaster:* \"Progress. Adequate.\"",
            parse_mode="Markdown"
        )
        await callback.answer("✅ Research unlocked!", show_alert=False)
    except Exception as e:
        print(f"[CB_RESEARCH ERROR] {e}")
        await callback.answer(f"❌ Error: {str(e)}", show_alert=True)


@dp.callback_query(F.data.startswith("info_"))
async def cb_info(callback: types.CallbackQuery):
    await callback.answer("🔒 Too powerful. Upgrade your backpack first.", show_alert=True)


@dp.callback_query(F.data.startswith("discard_"))
async def cb_discard(callback: types.CallbackQuery):
    """Discard an item from inventory."""
    try:
        # Parse item_id from callback data format: "discard_5"
        # Use rsplit to handle discard_claim_ pattern (which should match discard_claim_ handler first)
        parts = callback.data.rsplit('_', 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid format: {callback.data}")
        raw_id = parts[1]
        item_id = int(raw_id)
        print(f"[DISCARD] Parsed callback_data='{callback.data}' -> item_id={item_id}")
    except (IndexError, ValueError, TypeError) as e:
        print(f"[DISCARD ERROR] Failed to parse callback_data='{callback.data}': {e}")
        await callback.answer("❌ Invalid item.", show_alert=True)
        return
    
    u_id = str(callback.from_user.id)
    inv = get_inventory(u_id)
    print(f"[DISCARD] User {u_id}: Looking for item_id={item_id} in {len(inv)} items")
    print(f"[DISCARD] Available IDs: {[it.get('id') for it in inv]}")
    print(f"[DISCARD] Available ID types: {[(it.get('id'), type(it.get('id')).__name__) for it in inv]}")
    
    item = next((it for it in inv if it.get('id') == item_id), None)
    
    if not item:
        await callback.answer("❌ Item not found.", show_alert=True); return
    
    # Remove the item
    item_type = item.get('type', 'Unknown').upper()
    success = remove_inventory_item(u_id, item_id)
    if not success:
        await callback.answer("❌ Failed to discard item.", show_alert=True); return
    
    print(f"[DISCARD] Item {item_id} removed successfully")
    await callback.answer(f"🗑️ {item_type} discarded.", show_alert=True)
    
    # Refresh inventory display
    remaining = get_inventory(u_id)
    print(f"[DISCARD] After removal: {len(remaining)} items remaining")
    
    try:
        if not remaining:
            await callback.message.edit_text(
                "📦 *Your inventory is now empty.*\n\n🃏 *GameMaster:* \"Threw it all away, did you? Pathetic.\"",
                parse_mode="Markdown"
            )
        else:
            # Rebuild inventory list
            rows = []
            for itm in remaining:
                iid   = itm.get('id')
                itype = itm.get('type','').lower()
                xp    = itm.get('xp_reward', 0)
                # Ensure iid is a string for callback_data
                iid_str = str(iid) if iid is not None else "0"
                print(f"[INV_REBUILD] Item ID: {iid} (type: {type(iid).__name__}) -> callback string: {iid_str}")
                if   "wood"   in itype and "crate" in itype: lbl, cb = f"🪵 WOOD CRATE ({xp} XP)",   f"open_{iid_str}"
                elif "bronze" in itype and "crate" in itype: lbl, cb = f"🥉 BRONZE CRATE ({xp} XP)", f"open_{iid_str}"
                elif "iron"   in itype and "crate" in itype: lbl, cb = f"⚙️ IRON CRATE ({xp} XP)",   f"open_{iid_str}"
                elif "super"  in itype and "crate" in itype: lbl, cb = f"🎁 SUPER CRATE ({xp} XP)",  f"open_{iid_str}"
                elif itype == "shield":                       lbl, cb = "🛡️ SHIELD — tap to ACTIVATE", f"activate_shield_{iid_str}"
                elif itype == "teleport":                     lbl, cb = "🌀 TELEPORT",                 f"teleport_{iid_str}"
                elif "multiplier" in itype:
                    mult = itm.get('multiplier_value', 2)
                    kind = "XP" if "xp" in itype else "SILVER"
                    lbl, cb = f"⚡ {kind} MULTIPLIER x{mult}", f"use_{iid_str}"
                elif "locked_" in itype:                      lbl, cb = "🔒 LEGENDARY [TOO POWERFUL]", f"info_{iid_str}"
                else:                                         lbl, cb = f"❓ {itype.upper()}",          f"use_{iid_str}"
                rows.append([
                    InlineKeyboardButton(text=lbl, callback_data=cb),
                    InlineKeyboardButton(text="🗑️ DISCARD", callback_data=f"discard_{iid_str}")
                ])
            
            profile = get_profile(u_id)
            su = len(remaining)  # Use actual count, not cached
            st = profile['backpack_slots'] if profile else 5
            await callback.message.edit_text(
                f"📦 *YOUR INVENTORY*\n━━━━━━━━━━━━━━━\n📊 Slots: {su}/{st}\n\n*Items:* (tap to use or discard)",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
                parse_mode="Markdown"
            )
    except TelegramBadRequest as e:
        # Message content hasn't changed, so Telegram rejects the edit - that's OK
        if "message is not modified" in str(e):
            print(f"[DISCARD] Message not modified (inventory unchanged)")
        else:
            print(f"[DISCARD] Telegram error: {e}")
            await callback.answer("❌ Failed to update display.", show_alert=True)


@dp.callback_query(F.data.startswith("teleport_to_"))
async def cb_teleport_to(callback: types.CallbackQuery):
    import re; m = re.search(r'\d+', callback.data)
    if not m: return
    sector_id = int(m.group())
    u_id = str(callback.from_user.id)
    if not (1 <= sector_id <= 9): await callback.answer("That sector is locked!", show_alert=True); return
    all_sectors = load_sectors()
    info  = all_sectors.get(sector_id, {})
    sname = info.get('name', f'Sector {sector_id}') if isinstance(info, dict) else str(info)
    set_sector(u_id, sector_id)
    for it in get_inventory(u_id):
        if it.get('type','').lower() == 'teleport':
            remove_inventory_item(u_id, it.get('id')); break
    await callback.answer("✨ Teleported!")
    await callback.message.edit_text(
        f"✨ *TELEPORTED!*\n📍 *#{sector_id} {sname.upper()}*\n\nTeleport consumed.",
        parse_mode="Markdown"
    )


@dp.callback_query(F.data.startswith("teleport_"))
async def cb_teleport(callback: types.CallbackQuery):
    import re; m = re.search(r'\d+', callback.data)
    if not m: return
    iid  = int(m.group())
    u_id = str(callback.from_user.id)
    inv  = get_inventory(u_id)
    item = next((it for it in inv if it.get('id') == iid), None)
    if not item or item.get('type','').lower() != 'teleport':
        await callback.answer("Invalid teleport item.", show_alert=True); return
    await callback.answer("Choose destination!")
    all_sectors = load_sectors()
    rows = []
    for sid in range(1, 10):
        info  = all_sectors.get(sid, {})
        sname = info.get('name', f'Sector {sid}') if isinstance(info, dict) else str(info)
        rows.append([InlineKeyboardButton(text=f"#{sid} {sname}", callback_data=f"teleport_to_{sid}")])
    rows.append([InlineKeyboardButton(text="🔒 Sectors 10-64 (LOCKED)", callback_data="locked_sectors")])
    await callback.message.answer(
        "🌀 *TELEPORT NETWORK*\n━━━━━━━━━━━━━━━\nChoose your sector:",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )


@dp.callback_query(F.data == "locked_sectors")
async def cb_locked(callback: types.CallbackQuery):
    await callback.answer("Sectors 10-64 unlock as you level up!", show_alert=True)


@dp.message_reaction()
async def on_reaction(event: types.MessageReactionUpdated):
    try:
        uid = event.user.id if hasattr(event, 'user') and event.user else event.user_id
    except Exception:
        return
    eng = get_engine(event.chat.id)
    if (eng.crate_msg_id == event.message_id
            and eng.crates_dropping > 0
            and uid not in [c['user_id'] for c in eng.crate_claimers]
            and len(eng.crate_claimers) < 3):
        eng.crate_claimers.append({'user_id': uid})


# ═══════════════════════════════════════════════════════════════════════════
#  ITEM ACTION HELPERS
# ═══════════════════════════════════════════════════════════════════════════

async def _do_open_crate(message: types.Message, user_id: str, item_id: int):
    inv = get_inventory(user_id)
    crate = next((it for it in inv if it.get('id') == item_id), None)
    if not crate: await message.answer("🃏 *GameMaster:* \"Invalid crate.\"", parse_mode="Markdown"); return
    if "crate" not in crate.get('type','').lower(): await message.answer("🃏 *GameMaster:* \"That's not a crate.\"", parse_mode="Markdown"); return

    xp    = int(crate.get('xp_reward', 0))
    ctype = crate.get('type','unknown').lower()
    cname = ctype.replace("_"," ").upper()

    # If xp is 0 (old item stored before fix), assign fresh value
    if xp == 0:
        from supabase_db import _crate_xp
        xp = _crate_xp(ctype)

    # Silver reward by tier
    silver = 0
    if 'wood'   in ctype: silver = random.randint(2, 8)
    elif 'bronze' in ctype: silver = random.randint(5, 15)
    elif 'iron'   in ctype: silver = random.randint(10, 30)
    elif 'super'  in ctype: silver = random.randint(15, 50)

    add_xp(user_id, xp)
    if silver: add_silver(user_id, silver)
    remove_inventory_item(user_id, item_id)

    msg = f"✨ *CRATE OPENED!*\n📦 {cname}\n+{xp} XP"
    if silver: msg += f"\n+{silver} Silver"
    await message.answer(msg, parse_mode="Markdown")


async def _do_use_item(message: types.Message, user_id: str, item_id: int):
    inv  = get_inventory(user_id)
    print(f"[USE_ITEM] User {user_id}: Looking for item_id={item_id} (type: {type(item_id).__name__}) in {len(inv)} items")
    print(f"[USE_ITEM] Available IDs: {[(it.get('id'), type(it.get('id')).__name__) for it in inv]}")
    item = next((it for it in inv if it.get('id') == item_id), None)
    if not item:
        await message.answer("🃏 *GameMaster:* \"Item not found in your inventory. Refresh and try again.\"", parse_mode="Markdown"); return
    
    itype = item.get('type','').lower()
    
    if "crate" in itype:
        await message.answer("🃏 *GameMaster:* \"Use the OPEN button for crates.\"", parse_mode="Markdown"); return
    elif itype == "shield":
        await message.answer("🃏 *GameMaster:* \"Tap the ACTIVATE SHIELD button in your inventory.\"", parse_mode="Markdown"); return
    elif "locked_" in itype:
        await message.answer("🃏 *GameMaster:* \"You can't use that. Upgrade backpack first.\"", parse_mode="Markdown"); return
    elif "multiplier" in itype:
        mult = item.get('multiplier_value', 2)
        kind = "XP" if "xp" in itype else "SILVER"
        # Ask user how many uses they want via inline buttons
        await message.answer(
            f"⚡ *{kind} MULTIPLIER x{mult}*\n\n"
            f"How many word guesses should this apply to?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="5 guesses", callback_data=f"activate_mult_{item_id}_5"),
                 InlineKeyboardButton(text="10 guesses", callback_data=f"activate_mult_{item_id}_10")],
                [InlineKeyboardButton(text="15 guesses", callback_data=f"activate_mult_{item_id}_15"),
                 InlineKeyboardButton(text="20 guesses", callback_data=f"activate_mult_{item_id}_20")]
            ]),
            parse_mode="Markdown"
        ); return
    else:
        await message.answer("🃏 *GameMaster:* \"Unknown item.\"", parse_mode="Markdown"); return


async def _do_claim_all(target, user_id: str, edit: bool = False, is_command: bool = False):
    """Claim ALL unclaimed items to inventory, one by one until inventory is full."""
    user_id = str(user_id)
    
    claimed_items = []
    failed_items = []
    
    # Keep looping until no more items can be claimed
    while True:
        unclaimed = get_unclaimed_items(user_id)
        
        if not unclaimed:
            break
        
        # Try to claim the first item in the list
        item = unclaimed[0]
        ok, msg = claim_item(user_id, item['id'])
        
        if ok:
            claimed_items.append(item)
            print(f"[CLAIM] {user_id} claimed {item.get('type')} (id={item.get('id')})")
        else:
            # If this item can't be claimed, stop trying
            failed_items.append((item, msg))
            print(f"[CLAIM] {user_id} failed to claim {item.get('type')}: {msg}")
            break  # Stop trying if we hit an error
    
    # Build response with details
    txt = f"✅ *AUTO-CLAIM COMPLETE!*\n━━━━━━━━━━━━━━━━━━━\n"
    txt += f"🎁 Items claimed: {len(claimed_items)}\n"
    
    if failed_items:
        reason = failed_items[0][1]
        txt += f"⚠️ Couldn't claim {len(failed_items)} more items\n"
        if "Inventory full" in reason:
            txt += f"\n📦 *Your backpack is FULL!*\nUse or discard items to make space.\n"
            txt += f"Then use `!autoclaim` again."
        else:
            txt += f"\n_Reason:_ {reason}"
    else:
        txt += "🃏 *GameMaster:* \"All claimed. Greedy little wretch.\""
    
    if edit:
        await target.edit_text(txt, parse_mode="Markdown")
    elif is_command:
        # Called from /autoclaim command
        await target.answer(txt, parse_mode="Markdown")
    else:
        await target.answer(txt, parse_mode="Markdown")


# ═══════════════════════════════════════════════════════════════════════════
#  WORD-GUESS CATCH-ALL  ←── MUST BE THE LAST @dp.message HANDLER
# ═══════════════════════════════════════════════════════════════════════════

@dp.message(F.chat.type.in_({"group","supergroup"}))
async def on_group_message(message: types.Message):
    if not message.text: return
    text = message.text.strip()
    u_id = str(message.from_user.id)
    print(f"[MSG] '{text}' from {u_id}")

    # Commands not matched above — silently ignore
    if text.startswith("!") or text.startswith("/"): 
        print(f"[SKIP] Command detected"); return

    eng  = get_engine(message.chat.id)
    user = get_user(u_id)
    print(f"[USER] {user.get('username') if user else 'NOT_REGISTERED'}, eng.active={eng.active}")

    if not user:
        if random.random() < 0.25:
            await message.reply(_unreg(), parse_mode="Markdown")
        print(f"[SKIP] User not registered"); return

    if eng.active:
        eng.msg_count += 1
        if eng.msg_count >= 4:
            eng.msg_count = 0
            await message.answer(f"📌 *Still playing:* `{eng.word1}` + `{eng.word2}`", parse_mode="Markdown")

    if not eng.active:
        g = text.lower()
        if len(g) >= 3 and eng.letters and can_spell(g, eng.letters):
            await message.reply("🛑 *GameMaster:* \"Round is OVER. Type `!fusion` to start a new one.\"", parse_mode="Markdown")
        print(f"[SKIP] Round not active"); return

    guess = text.lower()
    print(f"[GUESS] Processing: '{guess}'")
    if len(guess) < 3: 
        print(f"[SKIP] Too short"); return
    if guess in eng.used_words:
        print(f"[SKIP] Already used - resetting streak")
        # Reset streak when using same word twice
        update_streak_and_award_food(u_id, correct=False, username=user.get("username", ""))
        await message.reply(f"❌ `{guess.upper()}` was already guessed this round!"); return
    if not can_spell(guess, eng.letters): 
        print(f"[SKIP] Can't spell from {eng.letters}"); return

    print(f"[CHECK] Checking dict for '{guess}'...")
    if word_in_dict(guess):
        print(f"[VALID] `{guess}` found in dictionary")
        pts     = max(len(guess) - 2, 1)
        db_name = user.get("username", message.from_user.first_name)
        eng.used_words.append(guess)
        word_len = len(guess)

        # Check for active XP/SILVER multiplier (stored in buffs JSONB)
        buffs = user.get('buffs', {})
        mult_active = buffs.get('multiplier_active', 1)
        mult_count = buffs.get('multiplier_count', 0)
        mult_type = buffs.get('multiplier_type', 'xp').lower()
        
        xp_mult = mult_active if mult_type == 'xp' and mult_count > 0 else 1
        xp_to_award = pts * xp_mult if mult_count > 0 else pts
        mult_note = f" ⚡x{xp_mult}" if mult_count > 0 else ""

        # SIMPLE RESOURCE SYSTEM - Add 1 resource based on word length
        # Resources start from 4-letter words
        resources_awarded = {}
        if word_len == 4:
            resources_awarded = {'wood': 1}
        elif word_len == 5:
            resources_awarded = {'bronze': 1}
        elif word_len == 6:
            resources_awarded = {'iron': 1}
        elif word_len == 7:
            resources_awarded = {'diamond': 1}
        elif word_len >= 8:
            resources_awarded = {'relics': 1}
        # 3-letter words give no resources, just XP
        
        print(f"[RESOURCES] {db_name}: +{resources_awarded} (word_len={word_len})")
        
        # Calculate streak and food reward
        streak_info = update_streak_and_award_food(u_id, correct=True, username=db_name)
        print(f"[STREAK] Streak: {streak_info.get('streak')}, Food awarded: {streak_info.get('food_awarded')}, Status: {streak_info.get('status')}")
        
        # Build feedback message FIRST (no database calls needed)
        fb = f"✅ `{guess.upper()}` +{pts} pts  ⭐ +{xp_to_award} XP{mult_note}"
        
        # Add resource rewards to feedback with format: +amount ResourceName emoji
        resource_info = {
            "wood": ("Wood", "🪵"),
            "bronze": ("Bronze", "🧱"),
            "iron": ("Iron", "⛓️"),
            "diamond": ("Diamond", "💎"),
            "relics": ("Relics", "🏺")
        }
        for resource, amount in resources_awarded.items():
            if amount > 0:
                res_name, emoji = resource_info.get(resource, ("Unknown", "📦"))
                fb += f" +{amount} {res_name} {emoji}"
        
        # Add food reward from streak if any
        if streak_info["food_awarded"] > 0:
            fb += f" +{streak_info['food_awarded']} Food 🌽"
            print(f"[FOOD] Food awarded: {streak_info['food_awarded']}, Total streak: {streak_info['streak']}")
        else:
            print(f"[FOOD] No food this round - Streak: {streak_info['streak']}, Food awarded: {streak_info['food_awarded']}")
        
        # Send feedback immediately (doesn't require database)
        print(f"[DEBUG] Final feedback: {fb}")
        await message.reply(fb, parse_mode="Markdown")
        
        # NOW do database saves (in background, won't block feedback)
        # Wrap in try-catch so timeouts don't affect user experience
        try:
            # Streak/food was already updated by update_streak_and_award_food() above
            # Now just need to add resources to the saved base_resources
            # Get fresh user data (which now has streak/food from update_streak_and_award_food)
            user_fresh = get_user(u_id)
            if not user_fresh:
                print(f"[DB ERROR] User {u_id} not found after save")
                return
            
            print(f"[DEBUG] User fresh before update: base_resources={user_fresh.get('base_resources', {})}")
            
            # Initialize base_resources structure if needed
            if not user_fresh.get('base_resources'):
                user_fresh['base_resources'] = {
                    'resources': {'wood': 0, 'bronze': 0, 'iron': 0, 'diamond': 0, 'relics': 0},
                    'food': 0,
                    'current_streak': 0
                }
            
            base_res = user_fresh.get('base_resources', {})
            if not isinstance(base_res, dict):
                base_res = {'resources': {}, 'food': 0, 'current_streak': 0}
            
            # Make sure resources dict exists
            if 'resources' not in base_res:
                base_res['resources'] = {'wood': 0, 'bronze': 0, 'iron': 0, 'diamond': 0, 'relics': 0}
            
            # IMPORTANT: Get existing resources and ADD new ones (not replace)
            resources_dict = base_res.get('resources', {})
            print(f"[DEBUG] Existing resources before merge: {resources_dict}")
            
            for res_type, amount in resources_awarded.items():
                old_amount = resources_dict.get(res_type, 0)
                new_amount = old_amount + amount
                resources_dict[res_type] = new_amount
                print(f"[DEBUG] {res_type}: {old_amount} -> {new_amount}")
            
            # Ensure ALL resource types exist
            for res_type in ['wood', 'bronze', 'iron', 'diamond', 'relics']:
                if res_type not in resources_dict:
                    resources_dict[res_type] = 0
            
            # Update resources in base_resources
            base_res['resources'] = resources_dict
            
            # Save updated base_resources to database
            user_fresh['base_resources'] = base_res
            save_user(u_id, user_fresh)
            print(f"[DB] Resources saved: {resources_awarded}")
            print(f"[DB] Total resources now: {resources_dict}")
            print(f"[DB] Food in base_resources: {base_res.get('food', 0)} | Streak in base_resources: {base_res.get('current_streak', 0)}")
            
            # Handle multiplier deduction
            if mult_count > 0:
                buffs['multiplier_count'] = mult_count - 1
                if buffs['multiplier_count'] <= 0:
                    buffs.pop('multiplier_active', None)
                    buffs.pop('multiplier_count', None)
                    buffs.pop('multiplier_type', None)
                user['buffs'] = buffs
                save_user(u_id, user)
                print(f"[MULTIPLIER] Decreased count: {mult_count} -> {buffs.get('multiplier_count', 0)}")
            
            # Award points and XP
            add_points(u_id, pts, db_name)
            add_xp(u_id, xp_to_award)
            print(f"[DB] Points & XP saved for {db_name}")
        except Exception as e:
            print(f"[DB ERROR] Failed to save data: {e}")
            import traceback
            traceback.print_exc()
            # Don't crash - user already got feedback, data will retry on next action
        
        # Check level up (also in try-catch)
        try:
            old_lvl, new_lvl = check_level_up(u_id)
            if old_lvl and new_lvl:
                print(f"[LEVEL UP] {db_name}: {old_lvl} → {new_lvl}")
        except Exception as e:
            print(f"[LEVEL ERROR] {e}")
        
        # Update scores for end-of-round display
        if u_id not in eng.scores:
            eng.scores[u_id] = {"pts": 0, "name": db_name, "user_id": u_id, "leveled_up": False}
        eng.scores[u_id]["pts"] += pts
    else:
        # Word not in dictionary - reset streak and log
        print(f"[INVALID] '{guess}' NOT in dictionary - no points, resetting streak")
        update_streak_and_award_food(u_id, correct=False, username=user.get("username", "") if user else "")
        # No action needed, just silently skip invalid words


# ═══════════════════════════════════════════════════════════════════════════
#  BACKGROUND TASKS
# ═══════════════════════════════════════════════════════════════════════════

async def round_reset_task():
    """Background task: Reset all player streaks every 120 seconds (new game round)."""
    while True:
        try:
            await asyncio.sleep(120)  # Wait 120 seconds per round
            reset_all_streaks()
        except Exception as e:
            print(f"[ERROR] round_reset_task failed: {e}")
            await asyncio.sleep(5)  # Brief pause before retry


async def gamemaster_announcement_task(bot: Bot, chat_id: int):
    """Background task: Drop random GameMaster announcements every 7-10 minutes."""
    announcements = [
        "🛡️ *PERMANENT SHIELDS ACTIVATED*\n\nI've gifted you all *eternal protection*. Not because you deserve it—but because watching you fumble around defenseless was getting *boring*. Your bases are now sacred ground. Try not to embarrass yourselves *too* much. 👀",
        
        "📈 *THE LEADERBOARD NEVER LIES*\n\nSome of you are absolutely CRUSHING it. Others... *exist*. The weak are separated from the strong here on the *WEEKLY LEADERBOARD*. Or stay unknown forever on the *ALLTIME LEADERBOARD*. Your choice, coward. 🃏",
        
        "🏰 *YOUR FORTRESS IS PATHETIC*\n\nLook at your base. Just... *look* at it. Is that a fortress or a cardboard box? Level it up. Add military units. Place traps. Make it *worthy* of the GameMaster's attention. Otherwise, why should I bother watching? 😑",
        
        "🪓 *SWORDS WILL SHARPEN SOON*\n\nCurrently, shields are making you soft. Enjoy the free pass while it lasts. Soon the *WARS BEGIN*. Right now? Build your armies like your life depends on it. Because eventually... *it will*. Frame that warning. 💀",
        
        "🏪 *SHOPS = YOUR NEW ADDICTION*\n\n• **Normal Shop**: For mortals who like... normal things\n• **Black Market**: For those with *taste*\n• **Alliance Shop**: For actual friends (rare)\n• **Ruler's Shop**: For the cocky ones\n• **Premium**: For the desperately impatient ⏰\n\nYour coins are *begging* to be spent here.",
        
        "🔬 *SCIENCE = POWER = DOMINANCE*\n\nThe research lab isn't just a building—it's an *IQ test*. Spend your precious resources on upgrades that'll make you 30% better at war. Or don't. I'll enjoy watching you lose. The choice is yours. 🧪",
        
        "💎 *HOARD EVERYTHING LIKE YOUR LIFE DEPENDS ON IT*\n\nWood. Bronze. Iron. Diamond. Relics. \n\nEvery resource is a *weapon*. Every crate is a gift from me (you're welcome). Every item is *power*. Stop wasting them on stupid stuff. Build empires or die trying. 💰",
        
        "👑 *SECTOR WARS ARE COMING*\n\nYou think Sector 1 is tough? Try Sector 9. \nBetter resources = better rewards = *actual* power. Teleport to a high sector and watch yourself get *obliterated*. Or train harder and actually win. I'm *dying* to see which. 🌍",
        
        "⚔️ *YOUR MILITARY STINKS*\n\nPawns attack like they're scared. Knights are hit-or-miss. Bishops are *trying*. Rooks are solid. Queens? Where are your Queens? Kings? Almost never seen those. \n\nBuild better armies. Stop embarrassing the realm. 👑💔",
        
        "🔗 *ALLIANCES = FRIENDSHIP BETRAYAL SIMULATORS*\n\nBand together with your friends... then stab them in the back for glory. The coming *Alliance Wars* will separate true friends from back-stabbers. Spoiler: everyone's a back-stabber. 😈",
        
        "🎮 *YOUR FRIENDS ARE WEAK. RECRUIT THEM.*\n\nBored playing alone? Invite them here:\nhttps://t.me/checkmateHQ\n\nThen crush them mercilessly. Nothing says friendship like destroying their base while they sleep. *That's* what I'm here for. 🃏",
        
        "😴 *STOP LURKING AND START PLAYING*\n\nI know you're here. Watching. Waiting. *Scared*.\n\nType `!fusion` and face me. Or keep hiding like a coward. Either way, I'm *watching*. Always watching... 👀",
        
        "🤑 *YOUR RESOURCES ARE USELESS WITHOUT PURPOSE*\n\nHoarding wood? Cute. Building nothing with it? *Pathetic*. Use your resources. Upgrade your base. Train units. Research stronger abilities. Otherwise you're just collecting digital trash. 🗑️",
        
        "⏰ *TIME TO DOMINATE*\n\nEvery second you're NOT playing, someone else is getting stronger.\nEvery crate you don't open is power left on the table.\nEvery word game you skip is resources lost forever.\n\nFeeling the pressure yet? Good. 🔥",
        
        "🎯 *THE WEAK PERISH. THE STRONG CONQUER.*\n\nI watch you all. Some of you are *actually* trying. Others... are just taking up space. The leaderboard will judge you mercilessly. Will you rise... or fade into obscurity? 💀",
    ]
    
    while True:
        try:
            wait_time = random.randint(420, 600)  # 7-10 minutes
            await asyncio.sleep(wait_time)
            announcement = random.choice(announcements)
            try:
                await bot.send_message(chat_id, announcement, parse_mode="Markdown")
            except Exception as send_err:
                print(f"[ANNOUNCE ERROR] Failed to send: {send_err}")
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[ANNOUNCE ERROR] Task error: {e}")
            await asyncio.sleep(10)


# ═══════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

async def main():
    import signal, platform
    print("Bot starting...")
    
    # Load dictionary for word validation
    load_dictionary()
    
    # Try to delete webhook with timeout, but don't crash if network is down
    try:
        await asyncio.wait_for(bot.delete_webhook(drop_pending_updates=True), timeout=5.0)
    except asyncio.TimeoutError:
        print("[WARN] Webhook deletion timed out (network slow)")
        print("[INFO] Bot will continue without webhook cleanup")
    except Exception as e:
        print(f"[WARN] Could not delete webhook: {e}")
        print("[INFO] Bot will continue without webhook cleanup")

    loop = asyncio.get_running_loop()
    stop = asyncio.Event()

    if platform.system() != "Windows":
        for sig in (signal.SIGTERM, signal.SIGINT):
            try: loop.add_signal_handler(sig, stop.set)
            except (NotImplementedError, OSError): pass

    print("[INFO] Connecting to Telegram polling...")
    
    # Initialize shields for all players
    give_shields_to_all()
    print("[OK] All players now have permanent shields")
    
    # Start background streak reset task (every 120s)
    round_task = asyncio.create_task(round_reset_task())
    print("[OK] Round timer started (120s rounds with streak reset)")
    
    # Start GameMaster announcements task (if group chat ID provided)
    announce_task = None
    group_chat_id = os.environ.get('CHECKMATE_HQ_GROUP_ID')
    if group_chat_id:
        try:
            announce_task = asyncio.create_task(gamemaster_announcement_task(bot, int(group_chat_id)))
            print(f"[OK] Announcements started for group {group_chat_id}")
        except (ValueError, TypeError) as e:
            print(f"[WARN] Invalid CHECKMATE_HQ_GROUP_ID: {e}")
    else:
        print("[WARN] CHECKMATE_HQ_GROUP_ID not set - announcements disabled")
    
    task = asyncio.create_task(dp.start_polling(bot, handle_signals=False))
    print("[OK] Polling started successfully - waiting for messages...")
    await stop.wait()
    task.cancel()
    round_task.cancel()
    if announce_task:
        announce_task.cancel()
    try: await task
    except asyncio.CancelledError: pass
    try: await round_task
    except asyncio.CancelledError: pass
    if announce_task:
        try: await announce_task
        except asyncio.CancelledError: pass
    await bot.session.close()
    print("Bot stopped.")

if __name__ == "__main__":
    asyncio.run(main())
