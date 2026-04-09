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
from config import BOT_TOKEN, ENV_NAME, SUPABASE_URL as CONFIG_SUPABASE_URL

# ── Config ────────────────────────────────────────────────────────────────
API_TOKEN    = os.environ.get('API_TOKEN',    BOT_TOKEN)
SUPABASE_URL = os.environ.get('SUPABASE_URL', CONFIG_SUPABASE_URL).rstrip('/')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJhc25paW9scHBtdHB6aXNoaHRuIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NTQ3NjMwOCwiZXhwIjoyMDkxMDUyMzA4fQ.qrj1BO5dNilRDvgKtvTdwIWjBhFTRyGzuHPD271Xcac')

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
                    crate_note = f"\n\n🎁 *BONUS:* {eng.crates_dropping} crate(s) drop mid-round!"
                else:
                    eng.crates_dropping = 0

                await bot.send_message(
                    chat_id,
                    f"🃏 *GameMaster:* \"New round. Try not to starve.\"\n\n"
                    f"📝 *WORDS:* `{eng.word1}` + `{eng.word2}`"
                    f"{crate_note}\n\n⏱️ You have *2 minutes*. Go.",
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
                            "⚡ *CRATE DROP!* First 3 to react claim a Super Crate!",
                            parse_mode="Markdown"
                        )
                        eng.crate_msg_id   = m.message_id
                        eng.crate_claimers = []
                    if eng.crates_dropping == 0 and elapsed == 60:
                        await bot.send_message(
                            chat_id,
                            "⏱️ *GameMaster:* \"One minute left. Still pathetic, but there's time.\"",
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
                                    f"🃏 *GameMaster:* \"Managed not to embarrass yourself.\"\n\n"
                                    f"✨ Use `!claims` in DM to collect bonus items."
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
                        "🃏 *GameMaster:* \"Silence. I'm bored. Type `!fusion` when you want to play.\"",
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
        "🃏 *GameMaster:* \"Oh, look who's struggling.\"\n\n"
        "*COMMANDS* _(! or / prefix both work)_\n"
        "`!fusion` — Start the game _(group only)_\n"
        "`!forcerestart` — Force-end current round\n"
        "`!weekly` — Weekly leaderboard\n"
        "`!alltime` — All-time leaderboard\n"
        "`!words` — Show current words _(group)_\n"
        "`!help` — This message\n\n"
        "*DM ONLY*\n"
        "`!profile` · `!inventory` · `!claims` · `!autoclaim` · `!changename Name` · `!tutorial`\n\n"
        "*HOW TO PLAY*\n"
        "1️⃣ Two 7-letter words appear.\n"
        "2️⃣ Type any real word using only those letters.\n"
        "3️⃣ Points = word length − 2.  Round = 2 minutes.\n"
        "🏆 Top 3 per round earn bonus Super Crates!\n"
        "🛡️ Use a Shield to protect yourself from attacks.\n"
        "📊 Weekly reset every Sunday 00:00 UTC"
    )

def _unreg() -> str:
    return random.choice([
        "🃏 *GameMaster:* \"A ghost? Message me *privately* to register first.\"",
        "🃏 *GameMaster:* \"Who are you? Nobody. DM me and prove you exist.\"",
        "🃏 *GameMaster:* \"Unregistered souls are invisible. DM me, beg, register, then come back.\"",
    ])

def _dm_only(cmd: str) -> str:
    return random.choice([
        f"🃏 *GameMaster:* \"Did you just use `{cmd}` *in public*? DM me, fool.\"",
        f"🃏 *GameMaster:* \"`{cmd}` is *private*. Message me directly, amateur.\"",
        f"🃏 *GameMaster:* \"Handle your personal business in my DMs, not here.\"",
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
        await message.answer("🃏 *GameMaster:* \"This is a GROUP game. Stop pestering me in private.\"", parse_mode="Markdown"); return
    eng = get_engine(message.chat.id)
    if eng.running:
        await message.answer("🃏 *GameMaster:* \"The souls are already being harvested. Open your eyes.\"", parse_mode="Markdown"); return
    if not get_user(str(message.from_user.id)):
        await message.answer("🃏 *GameMaster:* \"An unregistered nomad triggering my game. Bold, stupid. DM me — but fine, I'll start.\"\n\n_(DM me to register!)_", parse_mode="Markdown")
    asyncio.create_task(game_loop(message.chat.id))


@dp.message(_cmd("forcerestart"))
async def cmd_forcerestart(message: types.Message):
    if message.chat.type not in ("group","supergroup"):
        await message.answer("🃏 *GameMaster:* \"Use this in the group, fool.\"", parse_mode="Markdown"); return
    eng = get_engine(message.chat.id)
    if not eng.running:
        await message.answer("🃏 *GameMaster:* \"Nothing is running. Type `!fusion` to start.\"", parse_mode="Markdown"); return
    eng.force_stop = True
    eng.active = False
    await message.answer("🃏 *GameMaster:* \"Fine. Round terminated. Fresh words incoming.\"", parse_mode="Markdown")


@dp.message(_cmd("words"))
async def cmd_words(message: types.Message):
    if message.chat.type not in ("group","supergroup"):
        await message.answer("🃏 *GameMaster:* \"This only works in groups.\"", parse_mode="Markdown"); return
    eng = get_engine(message.chat.id)
    if not eng.active or not eng.word1:
        await message.answer("🃏 *GameMaster:* \"No round active. Type `!fusion` to start.\"", parse_mode="Markdown"); return
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


@dp.message(_cmd("shop"))
async def cmd_shop(message: types.Message):
    await message.answer("🃏 *GameMaster:* \"The shop is under construction. Patience, worm.\"", parse_mode="Markdown")

@dp.message(_cmd("upgrade"))
async def cmd_upgrade(message: types.Message):
    await message.answer("🃏 *GameMaster:* \"Queen's Satchel not ready yet.\n\nWhen it launches: 5 → 20 slots for 900 Naira.\n\nManage your 5 slots and stop complaining.\"", parse_mode="Markdown")


@dp.message(_cmd("profile"))
async def cmd_profile(message: types.Message):
    if message.chat.type != "private":
        await message.answer(_dm_only("!profile"), parse_mode="Markdown"); return
    u_id = str(message.from_user.id)
    profile = get_profile(u_id)
    if not profile:
        await message.answer("🃏 *GameMaster:* \"You have no profile. Complete the tutorial first.\"", parse_mode="Markdown"); return
    bar = "█" * int(profile['xp_progress'] / profile['xp_needed'] * 20) + "░" * (20 - int(profile['xp_progress'] / profile['xp_needed'] * 20))
    shield_str = "🛡️ SHIELDED" if profile.get('shielded') else "⚔️ UNPROTECTED"
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
        raw_id = callback.data.rsplit('_', 1)[1]
        item_id = int(raw_id)
        print(f"[DISCARD_CLAIM] Parsed callback_data='{callback.data}' -> item_id={item_id}")
    except (IndexError, ValueError, TypeError) as e:
        print(f"[DISCARD_CLAIM ERROR] Failed to parse callback_data='{callback.data}': {e}")
        await callback.answer("❌ Invalid item.", show_alert=True); return
    
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
    import re; m = re.search(r'\d+', callback.data)
    if m: await _do_use_item(callback.message, str(callback.from_user.id), int(m.group()))
    await callback.answer()


@dp.callback_query(F.data.startswith("info_"))
async def cb_info(callback: types.CallbackQuery):
    await callback.answer("🔒 Too powerful. Upgrade your backpack first.", show_alert=True)


@dp.callback_query(F.data.startswith("discard_"))
async def cb_discard(callback: types.CallbackQuery):
    """Discard an item from inventory or claims."""
    try:
        # Parse item_id from callback data format: "discard_5"
        raw_id = callback.data.split('_', 1)[1]  # Use split with maxsplit to handle IDs with underscores
        item_id = int(raw_id)
        print(f"[DISCARD] Parsed callback_data='{callback.data}' -> item_id={item_id}")
    except (IndexError, ValueError, TypeError) as e:
        print(f"[DISCARD ERROR] Failed to parse callback_data='{callback.data}': {e}")
        await callback.answer("❌ Invalid item.", show_alert=True); return
    
    u_id = str(callback.from_user.id)
    inv = get_inventory(u_id)
    print(f"[DISCARD] User {u_id}: Looking for item_id={item_id} in {len(inv)} items")
    print(f"[DISCARD] Available IDs: {[it.get('id') for it in inv]}")
    print(f"[DISCARD] Available ID types: {[(it.get('id'), type(it.get('id')).__name__) for it in inv]}")
    
    item = next((it for it in inv if it.get('id') == item_id), None)
    
    if not item:
        await callback.answer("❌ Item not found.", show_alert=True); return
    
    # Remove the item
    remove_inventory_item(u_id, item_id)
    
    item_type = item.get('type', 'Unknown').upper()
    await callback.answer(f"🗑️ {item_type} discarded.", show_alert=True)
    
    # Refresh inventory display
    remaining = get_inventory(u_id)
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
        su = profile['inventory_count'] if profile else len(remaining)
        st = profile['backpack_slots']  if profile else 5
        await callback.message.edit_text(
            f"📦 *YOUR INVENTORY*\n━━━━━━━━━━━━━━━\n📊 Slots: {su}/{st}\n\n*Items:* (tap to use or discard)",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
            parse_mode="Markdown"
        )


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
    item = next((it for it in inv if it.get('id') == item_id), None)
    if not item:
        await message.answer("🃏 *GameMaster:* \"Invalid item.\"", parse_mode="Markdown"); return
    
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
        # Activate multiplier
        user = get_user(user_id)
        if user:
            user[f"{kind.lower()}_multiplier_active"] = mult
            user[f"{kind.lower()}_multiplier_count"]  = 10   # lasts 10 guesses
            save_user(user_id, user)
        remove_inventory_item(user_id, item_id)
        await message.answer(
            f"⚡ *{kind} MULTIPLIER x{mult} ACTIVATED!*\n\n"
            f"Your next 10 word guesses give x{mult} {kind}!\n"
            f"🃏 *GameMaster:* \"Use it wisely. Or don't. I don't care.\"",
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
        txt += f"⚠️ Couldn't claim {len(failed_items)} more items\n"
        txt += f"\n_Reason:_ {failed_items[0][1]}"
    else:
        txt += "🃏 *GameMaster:* \"All claimed. Greedy little wretch.\""
    
    if edit:
        await target.edit_text(txt, parse_mode="Markdown")
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

    # Commands not matched above — silently ignore
    if text.startswith("!") or text.startswith("/"): return

    eng  = get_engine(message.chat.id)
    user = get_user(u_id)

    if not user:
        if random.random() < 0.25:
            await message.reply(_unreg(), parse_mode="Markdown")
        return

    if eng.active:
        eng.msg_count += 1
        if eng.msg_count >= 4:
            eng.msg_count = 0
            await message.answer(f"📌 *Still playing:* `{eng.word1}` + `{eng.word2}`", parse_mode="Markdown")

    if not eng.active:
        g = text.lower()
        if len(g) >= 3 and eng.letters and can_spell(g, eng.letters):
            await message.reply("🛑 *GameMaster:* \"Round is OVER. Type `!fusion` to start a new one.\"", parse_mode="Markdown")
        return

    guess = text.lower()
    if len(guess) < 3: return
    if guess in eng.used_words:
        await message.reply(f"❌ `{guess.upper()}` was already guessed this round!"); return
    if not can_spell(guess, eng.letters): return

    if word_in_dict(guess):
        pts     = max(len(guess) - 2, 1)
        db_name = user.get("username", message.from_user.first_name)
        eng.used_words.append(guess)

        # Check for active XP multiplier
        xp_mult = int(user.get('xp_multiplier_active', 1) or 1)
        xp_count = int(user.get('xp_multiplier_count', 0) or 0)
        xp_to_award = pts * xp_mult if xp_count > 0 else pts
        mult_note = f" ⚡x{xp_mult}" if xp_count > 0 else ""

        if xp_count > 0:
            user['xp_multiplier_count'] = xp_count - 1
            if user['xp_multiplier_count'] <= 0:
                user['xp_multiplier_active'] = 1
                user['xp_multiplier_count']  = 0
            save_user(u_id, user)

        add_points(u_id, pts, db_name)
        add_xp(u_id, xp_to_award)
        old_lvl, new_lvl = check_level_up(u_id)

        if u_id not in eng.scores:
            eng.scores[u_id] = {"pts": 0, "name": db_name, "user_id": u_id, "leveled_up": False}
        eng.scores[u_id]["pts"] += pts

        fb = f"✅ `{guess.upper()}` +{pts} pts  ⭐ +{xp_to_award} XP{mult_note}"
        if old_lvl and new_lvl:
            fb += f"\n🎊 *LEVEL UP!* {old_lvl} → {new_lvl}"
            eng.scores[u_id]["leveled_up"] = True
        await message.reply(fb, parse_mode="Markdown")


# ═══════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

async def main():
    import signal, platform
    print("Bot starting...")
    
    # Load dictionary for word validation
    load_dictionary()
    
    await bot.delete_webhook(drop_pending_updates=True)

    loop = asyncio.get_running_loop()
    stop = asyncio.Event()

    if platform.system() != "Windows":
        for sig in (signal.SIGTERM, signal.SIGINT):
            try: loop.add_signal_handler(sig, stop.set)
            except (NotImplementedError, OSError): pass

    task = asyncio.create_task(dp.start_polling(bot, handle_signals=False))
    await stop.wait()
    task.cancel()
    try: await task
    except asyncio.CancelledError: pass
    await bot.session.close()
    print("Bot stopped.")

if __name__ == "__main__":
    asyncio.run(main())
