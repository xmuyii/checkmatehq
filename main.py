# -*- coding: utf-8 -*-
"""
main.py — Checkmate HQ Bot
===========================
Architecture: flat @dp.message decorators with _cmd() filter.
on_group_message is registered LAST so every command above fires first.
Game loop: simple asyncio.sleep ticks, force_stop flag.
"""

# ── Load environment variables FIRST ──────────────────────────────────────
from dotenv import load_dotenv
load_dotenv()

# ── Fix Unicode/Emoji support on Windows –────────────────────────────────
import sys
import os
# This adds the folder containing main.py to Python's search list
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
#print(f"Current Directory: {os.getcwd()}")
#print(f"Files found: {os.listdir('.')}")
if sys.platform == "win32":
    import io
    # Reconfigure stdout to use UTF-8
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import asyncio
import random
import time
import json
import html as _html
from datetime import datetime, timedelta
import httpx
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from sectors_system import SECTORS
from formatting import (
    progress_bar, divider, broadcast, round_start_header, round_end_summary,
    level_up_announcement, battle_result, shield_status_visual, countdown_timer,
    military_deployment, territory_claimed, achievement_unlocked, loading_bar, sector_status
)
# ── Trivia System ─────────────────────────────────────────────────────────
from trivia_system import TriviaEngine, get_trivia_engine, TRIVIA_QUESTIONS, BOSS_QUESTIONS

from new_features import (
    get_shop_items,
    generate_daily_quests,
    get_sector_resource_bonus,
    convert_silver_to_gold,
    SECTOR_RESOURCE_BONUSES,
    setup_buy_command,
    setup_quests_command,
    setup_vault_command,
    setup_chess_command,
    setup_guild_handlers
)
# List of keys that should NEVER be overwritten by a Load/Save
META_KEYS = ["id", "username", "game_saves", "created_at", "premium_credits", "total_words", "backpack_slots"]


# ── GLOBAL EVENT TRACKING ──────────────────────────────────────────────────
game_events = {
    "level_ups": [],      # {"player": name, "level": 10, "time": timestamp}
    "sector_captures": [], # {"player": name, "sector": 3, "troops": 100, "time": timestamp}
    "battle_results": [],  # {"winner": name, "loser": name, "reward": 500, "time": timestamp}
    "challenges": []       # {"player": name, "challenge": "Climber", "reward": 500, "time": timestamp}
}

from save_system import (
    save_game, reset_game, load_game, reset_player_progress, restore_to_checkpoint, list_saves, list_checkpoints, format_reset_status, format_checkpoint_display
)
def add_event(event_type: str, event_data: dict):
    """Add event to tracking queue with timestamp."""
    if event_type in game_events:
        event_data['time'] = datetime.utcnow()
        game_events[event_type].append(event_data)
        # Keep only last 20 events to prevent memory leaks
        if len(game_events[event_type]) > 20:
            game_events[event_type] = game_events[event_type][-20:]
        print(f"[EVENT] {event_type.upper()}: {event_data}")

def get_recent_events(event_type: str, minutes: int = 15) -> list:
    """Get events from last N minutes."""
    if event_type not in game_events:
        return []
    cutoff = datetime.utcnow() - timedelta(minutes=minutes)
    return [e for e in game_events[event_type] if e.get('time', datetime.utcnow()) > cutoff]

# ── Addictive Mechanics ────────────────────────────────────────────────────
from addictive_mechanics import (
    handle_daily_login, get_combo_multiplier, increment_combo, reset_combo,
    get_weekly_challenges, format_challenge_display, check_rare_drop,
    format_rare_drop_notification, get_limited_offer
)

# ── Jammer Perk System (Scrambler/Anti-Jammer) ─────────────────────────────
try:
    from jammer_perk_system import (
        activate_perk, deactivate_perk, is_perk_active, get_active_perks,
        format_active_perks, scramble_word, use_anti_jammer,
        format_scrambled_validation, check_and_cleanup_expired_perks,
        PERK_DEFINITIONS
    )
    print("✅ Jammer perk system loaded")
except Exception as e:
    print(f"⚠️  Jammer perk system failed ({e})")
    def activate_perk(u, p): return {"ok": False}
    def deactivate_perk(u, p): return {"ok": False}
    def is_perk_active(u, p): return False
    def get_active_perks(u): return {}
    def format_active_perks(u): return ""
    def scramble_word(w): return w
    def use_anti_jammer(u): return {"ok": False}
    def format_scrambled_validation(w, v=True): return ""
    def check_and_cleanup_expired_perks(u): pass
    PERK_DEFINITIONS = {}

# ── Immersive Systems (Psychological Depth & Narrative) ───────────────────
try:
    from immersive_systems import (
        ASSASSIN_PROFILE, BURNED_BASE_IMAGERY,
        OBELISK_GATEWAY, SECTOR_CONSCIOUSNESS,
        format_battle_intensity, format_victory_ascension, format_defeat_devastation,
        consciousness_split_awareness, format_shop_menu, SECTOR_SELECTION_FLOW,
        get_awakening_hook, SHOP_CATALOG
    )
    ATTACK_DECISION_SCREEN = "⚔️ Choose your target carefully."
    try:
        print("✅G - I S loaded")
    except UnicodeEncodeError:
        print("[OK] G - I S loaded")
except Exception as e:
    try:
        print(f"⚠️  Immersive systems failves")
    except UnicodeEncodeError:
        print(f"[WARN] Immersive systems failves")
    ASSASSIN_PROFILE = {}
    BURNED_BASE_IMAGERY = "🔥 Your base has been raided. Rebuild or perish."
    OBELISK_GATEWAY = "🌌 ENTER into the interdimensional gateway.\n\n...\nThere are 64 sectors. Which of them will you rule over?"
    ATTACK_DECISION_SCREEN = "⚔️ Choose your target carefully."
    SECTOR_CONSCIOUSNESS = {}
    # Stub functions for missing immersive functions
    def format_battle_intensity(p, e, s): return f"⚔️ {p} battles {e}!"
    def format_victory_ascension(w, l, xp, r): return f"🏆 {w} defeated {l}!"
    def format_defeat_devastation(l, w): return f"💀 {l} was defeated by {w}."
    def consciousness_split_awareness(ps, bs, pn): return "You are split between locations."
    def format_shop_menu(s): return f"💰 You have {s} bitcoin."
    def get_awakening_hook(ht, **ctx): return "The game awaits."
    SECTOR_SELECTION_FLOW = "Select a sector."
    SHOP_CATALOG = {}

# ── Bandit System (Strategic Enemy Encounters) ──────────────────────────────
try:
    from bandit_system import (
        should_trigger_bandit_attack, generate_bandit_encounter, format_bandit_encounter,
        calculate_defense_strength, calculate_battle_outcome_vs_bandit,
        format_battle_description, get_sector_narrative
    )
    print("✅ Bandit system loaded")
except Exception as e:
    print(f"⚠️  Bandit system failed ({e}), no enemy encounters")

# ── Internal Chess System (PvP Chess Challenges) ───────────────────────────
try:
    from internal_chess_system import (
        create_game_challenge, accept_game_challenge, submit_game_result,
        initialize_chess_stats, format_chess_stats, get_game_info, cleanup_expired_games
    )
    print("✅ Internal chess system loaded")
except Exception as e:
    print(f"⚠️  Internal chess system failed ({e}), chess disabled")
    async def create_game_challenge(*args, **kwargs): return False, "❌ Chess system unavailable", ""
    async def accept_game_challenge(*args, **kwargs): return False, "❌ Chess system unavailable"
    async def submit_game_result(*args, **kwargs): return False, "❌ Chess system unavailable"
    async def initialize_chess_stats(*args): return False
    async def format_chess_stats(*args): return "❌ Chess system unavailable"
    async def get_game_info(*args): return False, "❌ Chess system unavailable"
    def cleanup_expired_games(): return 0

# ── Revenge & Scout System ─────────────────────────────────────────────────
try:
    from revenge_system import (
        set_revenge_target, get_revenge_info, clear_revenge, get_revenge_multiplier,
        scout_player, format_full_battle_report
    )
    print("✅ Revenge & Scout system loaded")
except Exception as e:
    print(f"⚠️  Revenge system failed ({e}), attacks will have no revenge multiplier")

# ── Advanced Scout System (5-min delay, deception, traps) ────────────────────
try:
    from scout_system_advanced import (
        scout_player_advanced, check_scout_return, set_displayed_stats,
        clear_displayed_stats, set_mousetraps, activate_firewall, deactivate_firewall,
        check_scout_notifications, format_scout_notification, format_scout_report_advanced
    )
    print("✅ Advanced scout system loaded")
except Exception as e:
    print(f"⚠️  Advanced scout system failed ({e})")

# ── Trap System (Building & Defense) ────────────────────────────────────────
try:
    from trap_system import (
        TRAP_TYPES, get_max_traps, get_available_traps, can_build_trap,
        calculate_trap_damage, format_trap_menu, format_trap_defense_report
    )
    print("✅ Trap system loaded")
except Exception as e:
    print(f"⚠️  Trap system failed ({e})")

# ── Build System (Internal Structures) ──────────────────────────────────────
try:
    from build_system import (
        BUILDING_TYPES, get_available_buildings, can_build_building,
        calculate_building_cost, format_buildings_menu, apply_building_bonuses
    )
    print("✅ Build system loaded")
except Exception as e:
    print(f"⚠️  Build system failed ({e})")

# ── Weapon System (Combat & Sabotage) ────────────────────────────────────────
try:
    from weapon_system import (
        WEAPONS, get_available_weapons, can_buy_weapon, can_use_weapon,
        format_weapons_shop, add_weapon_to_inventory, use_weapon_on_target,
        format_weapon_activation, format_weapon_damage_notification
    )
    print("✅ Weapon system loaded")
except Exception as e:
    print(f"⚠️  Weapon system failed ({e})")

# ── Prestige System (Level Reset with Bonuses) ───────────────────────────────
try:
    from prestige_system import (
        can_prestige, execute_prestige, get_prestige_tier, format_prestige_status,
        format_prestige_confirmation, get_prestige_multiplier, PRESTIGE_BONUSES
    )
    print("✅ Prestige system loaded")
except Exception as e:
    print(f"⚠️  Prestige system failed ({e})")

# ── Attack System ──────────────────────────────────────────────────────────
try:
    from attack_system import (
        calculate_battle_outcome, format_battle_report, format_raid_notification,
        calculate_army_strength, calculate_carrying_capacity
    )
    print("✅ Attack system loaded")
except Exception as e:
    print(f"⚠️  Attack system failed ({e})")

# ── DB import ─────────────────────────────────────────────────────────────
try:
    from supabase_db import (
        get_user, register_user, add_points, get_weekly_leaderboard,
        get_alltime_leaderboard, add_bitcoin, set_sector, upgrade_backpack,
        get_inventory, get_profile, add_xp, use_xp, use_bitcoin,
        remove_inventory_item, load_sectors, save_user, calculate_level,
        check_level_up, add_unclaimed_item, get_unclaimed_items,
        claim_item, remove_unclaimed_item, award_powerful_locked_item,
        add_inventory_item, activate_shield, is_shielded, get_sector_display,
        add_resources_from_word_length, update_streak_and_award_food,
        reset_all_streaks, add_randomized_gift, give_automatic_shield, deactivate_shield, disrupt_shield, restore_shield_after_attack, grant_free_teleports_to_all,
        grant_free_shields_to_all, get_game_weekly_leaderboard, get_game_alltime_leaderboard,
    )
    print("✅ Using Supabase database")
except Exception as e:
    print(f"⚠️  Supabase failed ({e}), using JSON database")
    from database import (
        get_user, register_user, add_points, get_weekly_leaderboard,
        get_alltime_leaderboard, add_bitcoin, set_sector, upgrade_backpack,
        get_inventory, get_profile, add_xp, use_xp, use_bitcoin,
        remove_inventory_item, load_sectors, save_user, calculate_level,
        check_level_up, add_unclaimed_item, get_unclaimed_items,
        claim_item, remove_unclaimed_item, award_powerful_locked_item,
        add_inventory_item, get_game_weekly_leaderboard, get_game_alltime_leaderboard,
    )
    # Stub shield helpers for JSON fallback
    def activate_shield(user_id): return False
    def is_shielded(user): return False

from initiation import initiation_router, CHECKMATE_HQ_GROUP_ID
from config import BOT_TOKEN, ENV_NAME, SUPABASE_URL as CONFIG_SUPABASE_URL, SUPABASE_KEY as CONFIG_SUPABASE_KEY

# ── Config ────────────────────────────────────────────────────────────────
SUPABASE_URL = os.environ.get('SUPABASE_URL', CONFIG_SUPABASE_URL).rstrip('/')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', CONFIG_SUPABASE_KEY)

bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher()
dp.include_router(initiation_router)

# ═══════════════════════════════════════════════════════════════════════════
#  STICKER FILE IDs (Telegram)
# ═══════════════════════════════════════════════════════════════════════════

STICKER_ACCESS_DENIED = "CAACAgQAAxkBAAFIQ_lp8GsJepZi0KF6r2mfAl_WppJJmAAC-xkAAvSegFORr5sV0ZQ50TsE"
STICKER_NEW_ROUND     = "CAACAgQAAxkBAAFIQ_Vp8GsBLJUMxVfnCZf1T2USv9LcmQACTS0AAhhCgVMpo0o9nkUv1TsE"
STICKER_UNREGISTERED  = "CAACAgQAAxkBAAFIQ_dp8GsGpaBG4Mwq8eLR2KssKRZNigACYB8AAkTagVMHGNklL-OePzsE"
STICKER_CRATE_DROP    = "CAACAgQAAxkBAAFIQ9hp8Go_f_MiW-ZSQUiR8aGCuPhZzwAC6B0AAnpiiVMDM_gbbCe70TsE"


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
        self.decoy_claimers   = []  # Track who got decoy crates
        self.dashboard_msgs   = {}  # user_id -> message_id for live dashboards
        self.player_sessions  = {}  # user_id -> round session stats dict

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
DICTIONARY_LOADED = False

def load_dictionary():
    """Load all valid words into memory for O(1) lookups."""
    global DICTIONARY, DICTIONARY_LOADED
    try:
        # Try primary dict file
        dict_files = ['SupaDB1.txt', 'dictionary.txt', 'words.txt']
        
        loaded = False
        for dict_file in dict_files:
            full_path = os.path.abspath(dict_file)
            print(f"[DICT] Checking: {full_path}")
            if not os.path.exists(dict_file):
                print(f"[DICT] File not found: {dict_file}")
                continue
            
            print(f"[DICT] Found {dict_file}, loading...")
            with open(dict_file, 'r', encoding='utf-8') as f:
                # Skip header line if present
                lines = f.readlines()
                print(f"[DICT] Read {len(lines)} total lines")
                if lines and (lines[0].strip().lower() in ['word', 'word_id', 'id']):
                    print(f"[DICT] Skipping header: '{lines[0].strip()}'")
                    lines = lines[1:]
                
                # Sample first 5 words for verification
                if len(lines) > 0:
                    print(f"[DICT] Sample words: {[w.strip() for w in lines[:5]]}")
                
                DICTIONARY = {word.strip().lower() for word in lines if word.strip()}
            
            if DICTIONARY:
                print(f"✅ [OK] Dictionary loaded: {len(DICTIONARY)} words from {dict_file}")
                print(f"[DICT] Sample check: 'aah' in DICTIONARY = {'aah' in DICTIONARY}")
                print(f"[DICT] Sample check: 'players' in DICTIONARY = {'players' in DICTIONARY}")
                loaded = True
                break
        
        if not loaded:
            print(f"❌ [ERROR] No dictionary file found. Word validation will FAIL!")
            print(f"[ERROR] Checked: {', '.join(dict_files)}")
            print(f"[ERROR] Current working directory: {os.getcwd()}")
            DICTIONARY = set()
        
        DICTIONARY_LOADED = True
        return DICTIONARY_LOADED
    
    except Exception as e:
        print(f"❌ [ERROR] Failed to load dictionary: {e}")
        import traceback
        traceback.print_exc()
        DICTIONARY = set()
        DICTIONARY_LOADED = False
        return False


# ═══════════════════════════════════════════════════════════════════════════
#  WORD / DICTIONARY HELPERS
# ═══════════════════════════════════════════════════════════════════════════

async def fetch_words() -> tuple[str, str]:
    headers = {'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}'}
    url = f"{SUPABASE_URL}/rest/v1/Dictionary?word_length=eq.6&select=word&limit=1"
    async with httpx.AsyncClient() as c:
        try:
            r1 = await c.get(f"{url}&offset={random.randint(0,500)}", headers=headers, timeout=8.0)
            r2 = await c.get(f"{url}&offset={random.randint(0,500)}", headers=headers, timeout=8.0)
            w1 = r1.json()[0]['word'].upper() if r1.json() else "PLAYER"
            w2 = r2.json()[0]['word'].upper() if r2.json() else "DANGER"
            return w1, w2
        except Exception:
            return "PLAYER", "DANGER"

def word_in_dict(word: str) -> bool:
    """Check if word exists in local dictionary (fast, no network calls)."""
    if not word:
        return False
    
    word_lower = word.lower().strip()
    
    # Primary check
    if word_lower in DICTIONARY:
        return True
    
    # If dictionary is empty, try to reload it
    if len(DICTIONARY) == 0 and not DICTIONARY_LOADED:
        print(f"[WARN] DICTIONARY is empty, attempting to reload...")
        load_dictionary()
        return word_lower in DICTIONARY
    
    # Debug output for first few failures
    if len(DICTIONARY) == 0:
        print(f"[ERROR] DICTIONARY is EMPTY! word_in_dict('{word_lower}') returning False")
    
    return False

def compute_possible_words(letters: str) -> int:
    if not DICTIONARY:
        load_dictionary()
    count = 0
    for word in DICTIONARY:
        if len(word) >= 3 and can_spell(word, letters):
            count += 1
    return count

def can_spell(word: str, pool: str) -> bool:
    avail = list(pool)
    for ch in word:
        if ch in avail: avail.remove(ch)
        else: return False
    return True

def detect_word_pattern(word: str) -> str:
    """Detect special word patterns for weapon unlocks.
    
    Returns:
    - 'palindrome': Word reads same forwards/backwards (e.g. RACECAR)
    - 'anagram_set': All unique letters (perfect anagram potential)
    - 'double_letters': Has repeated consecutive letters (e.g. COFFEE)
    - 'vowel_rich': 3+ vowels (e.g. BEAUTIFUL)
    - 'standard': Regular word
    """
    word_upper = word.upper()
    
    # Check palindrome
    if word_upper == word_upper[::-1]:
        return 'palindrome'
    
    # Check double letters
    if any(word_upper[i] == word_upper[i+1] for i in range(len(word_upper)-1)):
        return 'double_letters'
    
    # Check vowel rich
    vowels = sum(1 for ch in word_upper if ch in 'AEIOU')
    if vowels >= 3:
        return 'vowel_rich'
    
    # Check anagram set (all unique letters)
    if len(set(word_upper)) == len(word_upper):
        return 'anagram_set'
    
    return 'standard'

def can_spell(word: str, pool: str) -> bool:
    avail = list(pool)
    for ch in word:
        if ch in avail: avail.remove(ch)
        else: return False
    return True


# ═══════════════════════════════════════════════════════════════════════════
#  INITIALIZE DICTIONARY ON MODULE LOAD
# ═══════════════════════════════════════════════════════════════════════════
print("[INIT] Loading dictionary at module startup...")
load_dictionary()


# ═══════════════════════════════════════════════════════════════════════════
#  GAME LOOP  — tick-based, no asyncio.Event complexity
# ═══════════════════════════════════════════════════════════════════════════

ROUND_SECS = 180
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
                eng.dashboard_msgs  = {}
                eng.player_sessions = {}

                eng.word1, eng.word2 = await fetch_words()
                eng.letters = (eng.word1 + eng.word2).lower()
                eng.extra_letters = ""
                eng.words_repeated_count = 0

                crate_note = ""
                if random.random() < 0.2:
                    eng.crates_dropping = random.randint(1, 2)
                    eng.crate_claimers  = []
                    crate_note = f"\n🎁 *BONUS:* {eng.crates_dropping} incoming!"
                else:
                    eng.crates_dropping = 0

                possible_words_count = compute_possible_words(eng.letters)

                # Show last week winners
                last_winners = []
                try:
                    paths_to_try = [
                        'last_week_winners.json',
                        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'last_week_winners.json'),
                        os.path.join(os.getcwd(), 'last_week_winners.json')
                    ]
                    for path in paths_to_try:
                        if os.path.exists(path):
                            with open(path, 'r', encoding='utf-8') as f:
                                last_winners = json.load(f)
                            if last_winners:
                                print(f"[GAME LOOP] Loaded {len(last_winners)} last week winners from {path}")
                            break
                except Exception as e:
                    print(f"[ERROR] Loading last week winners: {e}")
                    import traceback
                    traceback.print_exc()
                    last_winners = []

                winners_text = ""
                if last_winners:
                    winners_text = "🏆 *LAST WEEK'S TOP PLAYERS* 🏆\n"
                    # Only show up to 3 winners to prevent IndexError
                    for i, p in enumerate(last_winners[:3]):
                        medal = ["🥇", "🥈", "🥉"][i]
                        winners_text += f"{medal} {p.get('username', 'Unknown')} — {p.get('points', 0):,} pts\n"
                    winners_text += f"{divider()}\n"

                # Send new round sticker to fusion topic
                try:
                    await bot.send_sticker(chat_id, STICKER_NEW_ROUND, message_thread_id=FUSION_TOPIC_ID)
                except Exception:
                    pass

                await bot.send_message(
                    chat_id,
                    f"{winners_text}"
                    f"🃏 *The GameMaster:* Topic is *FUSION*.\n"
                    f"🃏 You are to use the letters from these words to make new words: *{eng.word1}* + *{eng.word2}*.\n"
                    f"🃏 There are {possible_words_count} possible words.\n"
                    f"{crate_note}\n\n⏱️ *Game on* — Go hard.",
                    parse_mode="Markdown",
                    message_thread_id=FUSION_TOPIC_ID
                )

                crate_dropped = False
                for elapsed in range(ROUND_SECS):
                    await asyncio.sleep(1)
                    if eng.force_stop:
                        break
                        
                    # Repetition every 4 inputs is handled in on_group_message, but we can also just remind them if inactive
                    
                    if eng.crates_dropping > 0 and elapsed == 50 and not crate_dropped:
                        crate_dropped = True
                        # 50% chance for monkey trap decoy
                        is_monkey_trap = random.random() < 0.50
                        # Send crate sticker to fusion topic
                        try:
                            await bot.send_sticker(chat_id, STICKER_CRATE_DROP, message_thread_id=FUSION_TOPIC_ID)
                        except Exception:
                            pass
                        crate_label = "🐵 *CRATE DROP!*" if is_monkey_trap else "⚡ *CRATE DROP!*"
                        m = await bot.send_message(
                            chat_id,
                            crate_label,
                            parse_mode="Markdown",
                            message_thread_id=FUSION_TOPIC_ID
                        )
                        eng.crate_msg_id   = m.message_id
                        eng.crate_claimers = []
                        eng.decoy_claimers = []
                        if not hasattr(eng, 'current_crate_is_trap'):
                            eng.current_crate_is_trap = is_monkey_trap
                        eng.is_current_crate_decoy = is_monkey_trap
                        
                    if elapsed == 120:
                        eng.extra_letters = "".join(random.sample("abcdefghijklmnopqrstuvwxyz", 2))
                        eng.letters += eng.extra_letters
                        new_possible_count = compute_possible_words(eng.letters)
                        
                        await bot.send_message(
                            chat_id,
                            f"🃏 *The GameMaster:* *THE WORDS ARE:* \n\n\n`{eng.word1}` + `{eng.word2}`\n\n", parse_mode="Markdown",
                            message_thread_id=FUSION_TOPIC_ID)

                        # After sending word pair, wait a bit then send extra letters
                        await asyncio.sleep(0.1)
                        await bot.send_message(
                            chat_id,
                            f"🃏 *The GameMaster:* You can add these extra letters as well \n `{eng.extra_letters[0]}` `{eng.extra_letters[1]}`\n\n"
                            f"🃏 There are now {new_possible_count} possible words\n\n"
                            f"🃏 The round will end in 60 seconds.",
                            parse_mode="Markdown",
                            message_thread_id=FUSION_TOPIC_ID
                        )

                eng.active = False
                ss = sorted(eng.scores.values(), key=lambda x: x['pts'], reverse=True)
                
                if not ss:
                    result = f"🏆 *ROUND OVER*\n{divider()}\n."
                    eng.empty_rounds += 1
                else:
                    eng.empty_rounds = 0
                    medals = ["🥇", "🥈", "🥉"]
                    result = (
                        f"🏆 *ROUND COMPLETE*\n{divider()}\n"
                        f"`{'Rank':<4} {'Player':<14} {'Shield':<6} Pts`\n"
                        f"`{'-'*36}`\n"
                    )

                    # Crate bonus notification + decoy trap warning
                    if eng.crates_dropping > 0 and eng.crate_claimers:
                        try:
                            for cl in eng.crate_claimers:
                                add_unclaimed_item(str(cl['user_id']), "super_crate", 1)
                            result += f"🎁 *{len(eng.crate_claimers)} LUCKY PLAYERS CLAIMED MID-ROUND CRATES!*\n\n"
                            
                            # If any decoys were claimed, show warning in group AND send DMs
                            if eng.decoy_claimers:
                                decoy_names = ", ".join([d.get('username', f"Player {d['user_id']}") for d in eng.decoy_claimers])
                                result += f"⚠️ *MONKEY TRAP!* {decoy_names} grabbed DECOY! 💣\n\n"
                                
                                # Send individual DM notifications to decoy victims
                                for decoy_victim in eng.decoy_claimers:
                                    try:
                                        await bot.send_message(
                                            decoy_victim['user_id'],
                                            f"💣 *MONKEY TRAP!*\n\nYou picked a decoy crate during that round!\n\n"
                                            f"🃏 *GameMaster:* \"Better luck next time, be more alert.\"",
                                            parse_mode="Markdown"
                                        )
                                    except Exception as e:
                                        print(f"[ERROR] Sending decoy DM to {decoy_victim.get('username')}: {e}")
                        except Exception as e:
                            print(f"[ERROR] Crate handling: {e}")
                    
                    # Scores with medals + shield column
                    for i, p in enumerate(ss):
                        medal      = medals[i] if i < 3 else f"  {i+1}."
                        p_name     = (p['name'] or "Player")[:13]
                        shield_i   = "⚠️"
                        try:
                            _u = get_user(p.get('user_id', ''))
                            if _u:
                                _st = _u.get("shield_status") or ""
                                shield_i = "🛡️" if "ACTIVE" in _st else ("💥" if "DISRUPTED" in _st else "⚠️")
                        except Exception:
                            pass
                        result += f"{medal} {p_name}  {shield_i}  *{p['pts']:,} pts*\n"
                        if i < 3:
                            try:
                                add_unclaimed_item(p['user_id'], "super_crate", 1)
                            except Exception as e:
                                print(f"[ERROR] Adding crate for {p['name']}: {e}")
                    
                    result += f"\n{divider()}\n`!weekly` | `!alltime` for full stats"
                
                await bot.send_message(chat_id, result, parse_mode="Markdown")

                # Level-up announcements
                try:
                    for uid, sd in eng.scores.items():
                        if sd.get("leveled_up"):
                            user = get_user(uid)
                            if user:
                                lvl = user.get('level', 1)
                                msg = (
                                    f"{divider()}\n"
                                    f"🎊 *LEVEL UP!* 🎊\n"
                                    f"{divider()}\n\n"
                                    f"*{sd['name']}* has reached *LEVEL {lvl}*!\n\n"
                                    f"🃏 *GameMaster:* \"Congratulations. You've achieved the bare minimum. Collect your participation trophy. Use `!claims` in DM.\n\n"
                                    f"✨ *Bonus items awaiting.*\""
                                )
                                add_unclaimed_item(uid, "super_crate", 1)
                                k = "xp_multiplier" if random.random() < 0.5 else "bitcoin_multiplier"
                                add_unclaimed_item(uid, k, 1, xp_reward=0, multiplier_value=2)
                                if lvl % 5 == 0:
                                    iname, idesc = award_powerful_locked_item(uid)
                                    msg += f"\n\n{divider()}\n⚡ *MILESTONE!* Unlocked: *{iname}*\n_{idesc}_\n{divider()}"
                                await bot.send_message(chat_id, msg, parse_mode="Markdown")
                except Exception as e:
                    print(f"[ERROR] Level-up announcements: {e}")

                if eng.empty_rounds >= 3:
                    eng.running = False
                    await bot.send_message(
                        chat_id,
                        f"{divider()}\n"
                        f"🃏 *GameMaster:* \"*Three* empty rounds? Are you all *asleep*?! Pathetic.\n\n"
                        f"{divider()}",
                        parse_mode="Markdown"
                    )
                    break

                eng.games_played += 1
                if eng.games_played >= eng.games_until_help:
                    await bot.send_message(chat_id, _help_text(), parse_mode="Markdown")
                    eng.games_until_help = eng.games_played + random.randint(3, 7)

                if eng.games_played % 5 == 0:
                    try:
                        lb = get_weekly_leaderboard()
                        if lb:
                            t = "🏆 *WEEKLY TOP 10*\n━━━━━━━━━━━━━━━\n"
                            for i, p in enumerate(lb[:10], 1):
                                medal = ["🥇","🥈","🥉"][i-1] if i<=3 else f"{i}."
                                t += f"{medal} {p['username']} — {p['points']:,} pts\n"
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
        "`!profile` — Your stats, base, resources, shield status\n"
        "`!base` — Full base details, military, traps\n"
        "`!inventory` — Your items & crates\n"
        "`!claims` — Unclaimed rewards\n"
        "`!autoclaim` — Claim all rewards at once\n"
        "`!mystats` — Show your personal stats card (Bitcoin, Gold, Level)\n"
        "`!vault` — Vault management (deposit/withdraw Bitcoin & Gold safely)\n"
        "`!changename [Name]` — Change your username\n"
        "`!setup_base [Name]` — Create your first base\n"
        "`!changebasename [Name]` — Rename your base (1-time)\n"
        "`!lab` — Research lab: upgrade your army\n"
        "`!activateshield` — Activate shield (24h cooldown)\n"
        "`!deactivateshield` — Deactivate shield\n"
        "`!disruptor @user` — Break enemy shield for 1 attack\n\n"
        "*GAME COMMANDS* _(group or DM)_\n"
        "`!score` — Your weekly rank + 5 players above/below you\n"
        "`!weekly` — Weekly leaderboard\n"
        "`!alltime` — All-time leaderboard\n"
        "`!fusion` — Start new game round (group only)\n"
        "`!words` — Show current word pair\n"
        "`!forcerestart` — End the round\n\n"
        "*🌌 IMMERSIVE EXPERIENCE* _(DM only)_\n"
        "`!obelisk` — Enter the Obelisk: gateway to consciousness\n"
        "`!sectors` — Explore all 9 sectors and their consciousness\n\n"
        "*INVITE FRIENDS*\n"
        "Enjoy the game? Invite others! https://t.me/checkmateHQ"
    )

async def _send_unreg_sticker(message):
    """Send the unregistered player video sticker (already contains all needed text)."""
    try:
        await bot.send_sticker(message.chat.id, STICKER_UNREGISTERED)
    except Exception:
        pass

async def _send_access_denied_sticker(message):
    """Send the access denied sticker for commands the player can't use here."""
    try:
        await bot.send_sticker(message.chat.id, STICKER_ACCESS_DENIED)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════
#  UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def format_number(num: int) -> str:
    """Format number as 1M, 1K, etc. for numbers >= 1,000,000."""
    if num >= 1_000_000:
        return f"{num // 1_000_000}M"
    elif num >= 1_000:
        return f"{num // 1_000}K"
    else:
        return str(num)


# ═══════════════════════════════════════════════════════════════════════════
#  COMMAND FILTER  — matches "!weekly", "/weekly", "!WEEKLY", "/weekly@BotName"
# ═══════════════════════════════════════════════════════════════════════════

def _cmd(*names):
    ns = {n.lower() for n in names}
    def check(text: str) -> bool:
        if not text: return False
        parts = text.strip().split()
        if not parts: return False
        if not parts[0].startswith("/"): return False
        first = parts[0][1:].lower().split("@")[0]
        return first in ns
    return F.text.func(check)


# ═══════════════════════════════════════════════════════════════════════════
#  COMMAND HANDLERS  (all registered before on_group_message)
# ═══════════════════════════════════════════════════════════════════════════
# Constants
TRIVIA_TOPIC_ID = 36623
FUSION_TOPIC_ID = 36621

@dp.message(_cmd("trivia"))
async def cmd_trivia(message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("🧠 *GameMaster:* \"Trivia is a GROUP activity.\"")
        return

    trivia_eng = get_trivia_engine(message.chat.id)
    if trivia_eng.running:
        # Reply to the user in whatever topic they typed in
        await message.reply("🧠 *GameMaster:* \"Trivia is ALREADY running in the Trivia topic!\"")
        return

    # Start the loop - the loop will handle sending messages to the correct topic
    asyncio.create_task(trivia_game_loop(message.chat.id))
    
    # Optional: Send a redirect message in the current topic
    if message.message_thread_id != TRIVIA_TOPIC_ID:
        await message.answer(f"🧠 *Trivia is starting in the [Trivia Topic](https://t.me/c/{str(message.chat.id)[4:]}/{TRIVIA_TOPIC_ID})!*", parse_mode="Markdown")

@dp.message(_cmd("fusion"))
async def cmd_fusion(message: types.Message):
    if message.chat.type not in ("group","supergroup"):
        await message.answer("🃏 *GameMaster:* \"This is a GROUP game.\""); return
    
    eng = get_engine(message.chat.id)
    if eng.running:
        await message.reply("🃏 *GameMaster:* \"Fusion is already running!\""); return

    asyncio.create_task(game_loop(message.chat.id))
    
    if message.message_thread_id != FUSION_TOPIC_ID:
        await message.answer(f"🃏 *Fusion is starting in the [Fusion Topic](https://t.me/c/{str(message.chat.id)[4:]}/{FUSION_TOPIC_ID})!*", parse_mode="Markdown")


@dp.message(_cmd("forcerestart"))
async def cmd_forcerestart(message: types.Message):
    if message.chat.type not in ("group","supergroup"):
        await message.answer("🃏 *GameMaster:* \"This command is for GROUPS only. Stop wasting my time in private.\"", parse_mode="Markdown"); return
    eng = get_engine(message.chat.id)
    if not eng.running:
        await message.answer("🃏 *GameMaster:* \"No round is running", parse_mode="Markdown"); return
    eng.force_stop = True
    eng.active = False
    await message.answer("🃏 *GameMaster:* \"FINE. Terminating round because apparently you can't handle it. Fresh words incoming. Try not to mess this up.\"", parse_mode="Markdown")


@dp.message(_cmd("stopfusion"))
async def cmd_stopfusion(message: types.Message):
    """Stop the currently running fusion game immediately."""
    if message.chat.type not in ("group","supergroup"):
        await message.answer("🃏 *GameMaster:* \"This command is for GROUPS only.\"", parse_mode="Markdown")
        return
    eng = get_engine(message.chat.id)
    if not eng.running:
        await message.answer("🃏 *GameMaster:* \"No fusion game is currently running.\"", parse_mode="Markdown")
        return
    eng.force_stop = True
    eng.active = False
    eng.running = False
    await message.answer(
        f"🛑 *FUSION GAME STOPPED*\n{divider()}\n"
        f"🃏 *GameMaster:* \"The fusion round has been terminated by an admin.\"\n"
        f"{divider()}",
        parse_mode="Markdown"
    )


@dp.message(_cmd("stoptrivia"))
async def cmd_stoptrivia(message: types.Message):
    """Stop the currently running trivia game immediately."""
    if message.chat.type not in ("group","supergroup"):
        await message.answer("🧠 *GameMaster:* \"This command is for GROUPS only.\"", parse_mode="Markdown")
        return
    trivia_eng = get_trivia_engine(message.chat.id)
    if not trivia_eng.running:
        await message.answer("🧠 *GameMaster:* \"No trivia game is currently running.\"", parse_mode="Markdown")
        return
    trivia_eng.force_stop = True
    trivia_eng.active = False
    trivia_eng.running = False
    await message.answer(
        f"🛑 *TRIVIA GAME STOPPED*\n{divider()}\n"
        f"🧠 *GameMaster:* \"The trivia round has been terminated by an admin.\"\n"
        f"{divider()}",
        parse_mode="Markdown"
    )


@dp.message(_cmd("words"))
async def cmd_words(message: types.Message):
    if message.chat.type not in ("group","supergroup"):
        await message.answer("🃏 *GameMaster:* \"Groups ONLY. What part of that is confusing?\"", parse_mode="Markdown"); return
    eng = get_engine(message.chat.id)
    if not eng.active or not eng.word1:
        await message.answer("🃏 *GameMaster:*No round running.", parse_mode="Markdown"); return
    await message.answer(f"📝 *THE WORDS ARE:* \n\n\n`{eng.word1}`  `{eng.word2}` with added letters `{eng.extra_letters[0]}` `{eng.extra_letters[1]}`", parse_mode="Markdown")


@dp.message(_cmd("weekly"))
async def cmd_weekly(message: types.Message):
    """Display weekly leaderboard with top scores this week."""
    user_id = str(message.from_user.id)
    user = get_user(user_id)
    
    if not user:
        await _send_unreg_sticker(message)
        return
    
    # Get the weekly leaderboard
    try:
        lb = get_weekly_leaderboard(limit=10)
        print(f"[CMD_WEEKLY] Called by {user.get('username')} - got {len(lb)} players")
        
        text = "🏆 *WEEKLY LEADERBOARD*\n━━━━━━━━━━━━━━━\n"
        
        if not lb:
            text += "No scores yet this week. Shocking."
        else:
            from datetime import datetime
            for i, p in enumerate(lb, 1):
                medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."
                
                # Check if player has active name shield
                display_name = p['username']
                name_shield_until = p.get('name_shield_until')
                if name_shield_until:
                    try:
                        expiry = datetime.fromisoformat(name_shield_until)
                        if datetime.now() < expiry:
                            display_name = "[🛡️ Anonymous]"
                    except:
                        pass
                
                text += f"{medal} {display_name} — {p['points']:,} pts\n"
        
        text += "\n━━━━━━━━━━━━━━━\n"
        text += "`!alltime` for all-time scores"
        
        await message.answer(text, parse_mode="Markdown")
    except Exception as e:
        print(f"[ERROR] cmd_weekly: {e}")
        import traceback
        traceback.print_exc()
        await message.answer("❌ Error retrieving leaderboard. Try again.", parse_mode="Markdown")

@dp.message(_cmd("score"))
async def cmd_score(message: types.Message):
    u_id = str(message.from_user.id)
    user = get_user(u_id)
    if not user:
        await _send_unreg_sticker(message); return
        
    lb = get_weekly_leaderboard(limit=500)
    
    # Find user index
    user_idx = -1
    for i, p in enumerate(lb):
        if str(p['id']) == u_id:
            user_idx = i
            break
            
    if user_idx == -1:
        from supabase_db import _current_week_key
        pts = int(user.get('weekly_points', 0))
        if pts > 0 and user.get('week_start') == _current_week_key():
            await message.answer(f"📊 *YOUR SCORE*\n{divider()}\nYou have *{pts:,}* points, but are outside the Top 500.", parse_mode="Markdown")
        else:
            await message.answer(f"📊 *YOUR SCORE*\n{divider()}\nYou haven't scored any points this week yet!", parse_mode="Markdown")
        return
        
    start_idx = max(0, user_idx - 5)
    end_idx = min(len(lb), user_idx + 6)
    
    text = f"📊 *YOUR SCORE AND RANKING*\n{divider()}\n"
    for i in range(start_idx, end_idx):
        p = lb[i]
        rank = i + 1
        prefix = "👉" if i == user_idx else "  "
        medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{rank}."
        text += f"{prefix} {medal} {p.get('username', 'Unknown')} — {p.get('points', 0):,} pts\n"
        
    await message.answer(text, parse_mode="Markdown")

@dp.message(_cmd("alltime"))
async def cmd_alltime(message: types.Message):
    if not get_user(str(message.from_user.id)):
        await _send_unreg_sticker(message); return
    lb = get_alltime_leaderboard()
    text = "🏆 *ALL-TIME LEADERBOARD*\n━━━━━━━━━━━━━━━\n"
    if not lb:
        text += "Blank. Just like your future."
    else:
        from datetime import datetime
        for i, p in enumerate(lb, 1):
            medal = ["🥇","🥈","🥉"][i-1] if i<=3 else f"{i}."
            
            # Check if player has active name shield
            display_name = p['username']
            name_shield_until = p.get('name_shield_until')
            if name_shield_until:
                try:
                    expiry = datetime.fromisoformat(name_shield_until)
                    if datetime.now() < expiry:
                        display_name = "[🛡️ Anonymous]"
                except:
                    pass
            
            text += f"{medal} {display_name} — {p['points']:,} pts\n"
    await message.answer(text, parse_mode="Markdown")


@dp.message(_cmd("weekly_trivia"))
async def cmd_weekly_trivia(message: types.Message):
    """Display weekly trivia leaderboard."""
    user_id = str(message.from_user.id)
    user = get_user(user_id)
    
    if not user:
        await _send_unreg_sticker(message)
        return
    
    try:
        lb = get_game_weekly_leaderboard(game_type="trivia", limit=10)
        print(f"[CMD_WEEKLY_TRIVIA] Called by {user.get('username')} - got {len(lb)} players")
        
        text = "🧠 *WEEKLY TRIVIA LEADERBOARD*\n━━━━━━━━━━━━━━━\n"
        
        if not lb:
            text += "No trivia scores yet this week."
        else:
            for i, p in enumerate(lb, 1):
                medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."
                text += f"{medal} {p['username']} — {p['points']:,} pts\n"
        
        text += "\n━━━━━━━━━━━━━━━\n"
        text += "`!alltime_trivia` | `!weekly_fusion`"
        
        await message.answer(text, parse_mode="Markdown")
    except Exception as e:
        print(f"[ERROR] cmd_weekly_trivia: {e}")
        import traceback
        traceback.print_exc()
        await message.answer("❌ Error retrieving trivia leaderboard. Try again.", parse_mode="Markdown")


@dp.message(_cmd("weekly_fusion"))
async def cmd_weekly_fusion(message: types.Message):
    """Display weekly fusion leaderboard."""
    user_id = str(message.from_user.id)
    user = get_user(user_id)
    
    if not user:
        await _send_unreg_sticker(message)
        return
    
    try:
        lb = get_game_weekly_leaderboard(game_type="fusion", limit=10)
        print(f"[CMD_WEEKLY_FUSION] Called by {user.get('username')} - got {len(lb)} players")
        
        text = "🃏 *WEEKLY FUSION LEADERBOARD*\n━━━━━━━━━━━━━━━\n"
        
        if not lb:
            text += "No fusion scores yet this week."
        else:
            for i, p in enumerate(lb, 1):
                medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."
                text += f"{medal} {p['username']} — {p['points']:,} pts\n"
        
        text += "\n━━━━━━━━━━━━━━━\n"
        text += "`!alltime_fusion` | `!weekly_trivia`"
        
        await message.answer(text, parse_mode="Markdown")
    except Exception as e:
        print(f"[ERROR] cmd_weekly_fusion: {e}")
        import traceback
        traceback.print_exc()
        await message.answer("❌ Error retrieving fusion leaderboard. Try again.", parse_mode="Markdown")


@dp.message(_cmd("alltime_trivia"))
async def cmd_alltime_trivia(message: types.Message):
    """Display all-time trivia leaderboard."""
    if not get_user(str(message.from_user.id)):
        await _send_unreg_sticker(message)
        return
    
    try:
        lb = get_game_alltime_leaderboard(game_type="trivia", limit=10)
        text = "🧠 *ALL-TIME TRIVIA LEADERBOARD*\n━━━━━━━━━━━━━━━\n"
        if not lb:
            text += "No trivia records yet."
        else:
            for i, p in enumerate(lb, 1):
                medal = ["🥇","🥈","🥉"][i-1] if i<=3 else f"{i}."
                text += f"{medal} {p['username']} — {p['points']:,} pts\n"
        await message.answer(text, parse_mode="Markdown")
    except Exception as e:
        print(f"[ERROR] cmd_alltime_trivia: {e}")
        await message.answer("❌ Error retrieving leaderboard. Try again.", parse_mode="Markdown")


@dp.message(_cmd("alltime_fusion"))
async def cmd_alltime_fusion(message: types.Message):
    """Display all-time fusion leaderboard."""
    if not get_user(str(message.from_user.id)):
        await _send_unreg_sticker(message)
        return
    
    try:
        lb = get_game_alltime_leaderboard(game_type="fusion", limit=10)
        text = "🃏 *ALL-TIME FUSION LEADERBOARD*\n━━━━━━━━━━━━━━━\n"
        if not lb:
            text += "No fusion records yet."
        else:
            for i, p in enumerate(lb, 1):
                medal = ["🥇","🥈","🥉"][i-1] if i<=3 else f"{i}."
                text += f"{medal} {p['username']} — {p['points']:,} pts\n"
        await message.answer(text, parse_mode="Markdown")
    except Exception as e:
        print(f"[ERROR] cmd_alltime_fusion: {e}")
        await message.answer("❌ Error retrieving leaderboard. Try again.", parse_mode="Markdown")


@dp.message(_cmd("mystats"))
async def cmd_mystats(message: types.Message):
    """Display player's personal stats card with Bitcoin and other achievements."""
    u_id = str(message.from_user.id)
    user = get_user(u_id)
    
    if not user:
        await _send_unreg_sticker(message)
        return
    
    try:
        username = user.get('username', message.from_user.first_name)
        bitcoin = user.get('bitcoin', 0)
        gold = user.get('gold', 0)
        level = user.get('level', 1)
        all_time_points = user.get('all_time_points', 0)
        weekly_points = user.get('weekly_points', 0)
        
        # Format large numbers
        bitcoin_display = f"{bitcoin:,}"
        gold_display = f"{gold:,}"
        points_display = format_number(all_time_points)
        
        # Create stats card
        stats_card = f"""
╔══════════════════════════════╗
║    ⭐ HQ CARD ⭐            ║
╠══════════════════════════════╣
║                              ║
║  👤 *{username}*            ║
║                              ║
║  💎 Bitcoin:*{bitcoin_display}*║
║  ⭐ Level: *{level}*        ║
║                              ║  
║                              ║
╚══════════════════════════════╝
"""
        await message.answer(stats_card, parse_mode="Markdown")
        
    except Exception as e:
        print(f"[ERROR] cmd_mystats: {e}")
        await message.answer("❌ Error retrieving stats. Try again.", parse_mode="Markdown")


@dp.message(_cmd("vault"))
async def cmd_vault(message: types.Message):
    """Vault management: deposit/withdraw Bitcoin and Gold safely."""
    u_id = str(message.from_user.id)
    user = get_user(u_id)
    
    if not user:
        await _send_unreg_sticker(message)
        return
    
    if message.chat.type != "private":
        await _send_access_denied_sticker(message)
        return
    
    try:
        text = message.text.strip().lower().split()
        
        # Initialize vault if needed
        if 'vault' not in user:
            user['vault'] = {'bitcoin': 0, 'gold': 0}
        else:
            if 'bitcoin' not in user['vault']:
                user['vault']['bitcoin'] = 0
            if 'gold' not in user['vault']:
                user['vault']['gold'] = 0
        
        # No args = show vault status
        if len(text) == 1:
            account_bitcoin = user.get('bitcoin', 0)
            account_gold = user.get('gold', 0)
            vault_bitcoin = user['vault'].get('bitcoin', 0)
            vault_gold = user['vault'].get('gold', 0)
            
            vault_display = f"""
🔐 *VAULT STATUS*
━━━━━━━━━━━━━━━━━━━━━━
 *BALANCE* 

💎 *Bitcoin:* {format_number(account_bitcoin)} 
💰 *Gold:* {format_number(account_gold)} 


 *VAULT*
*Bitcoin:* {format_number(vault_bitcoin)} (safe)

━━━━━━━━━━━━━━━━━━━━━━

*COMMANDS:*
`!vault deposit bitcoin [amount]` — Move Bitcoin to vault
`!vault withdraw bitcoin [amount]` — Withdraw Bitcoin
`!vault deposit gold [amount]` — Move Gold to vault
`!vault withdraw gold [amount]` — Withdraw Gold

Move bitcoin to your vault to protect it from raids/
"""
            await message.answer(vault_display, parse_mode="Markdown")
            return
        
        # Parse command: /vault deposit/withdraw bitcoin/gold amount
        if len(text) < 4:
            await message.answer("❌ Format: `/vault deposit|withdraw bitcoin|gold amount`", parse_mode="Markdown")
            return
        
        action = text[1].lower()  # deposit or withdraw
        currency = text[2].lower()  # bitcoin or gold
        
        try:
            amount = int(text[3])
        except:
            await message.answer("❌ Amount must be a number", parse_mode="Markdown")
            return
        
        if amount <= 0:
            await message.answer("❌ Amount must be positive", parse_mode="Markdown")
            return
        
        if action == "deposit":
            # Move money FROM account TO vault
            if currency == "bitcoin":
                account_amount = user.get('bitcoin', 0)
                if account_amount < amount:
                    await message.answer(f"❌ You only have {format_number(account_amount)} Bitcoin in account", parse_mode="Markdown")
                    return
                user['bitcoin'] = account_amount - amount
                user['vault']['bitcoin'] = user['vault'].get('bitcoin', 0) + amount
                await message.answer(f"✅ Deposited {format_number(amount)} Bitcoin to vault!\n\nAccount: {format_number(user['bitcoin'])} | Vault: {format_number(user['vault']['bitcoin'])}", parse_mode="Markdown")
            elif currency == "gold":
                account_amount = user.get('gold', 0)
                if account_amount < amount:
                    await message.answer(f"❌ You only have {format_number(account_amount)} Gold in account", parse_mode="Markdown")
                    return
                user['gold'] = account_amount - amount
                user['vault']['gold'] = user['vault'].get('gold', 0) + amount
                await message.answer(f"✅ Deposited {format_number(amount)} Gold to vault!\n\nAccount: {format_number(user['gold'])} | Vault: {format_number(user['vault']['gold'])}", parse_mode="Markdown")
            else:
                await message.answer("❌ Currency must be bitcoin or gold", parse_mode="Markdown")
                return
        
        elif action == "withdraw":
            # Move money FROM vault TO account
            if currency == "bitcoin":
                vault_amount = user['vault'].get('bitcoin', 0)
                if vault_amount < amount:
                    await message.answer(f"❌ You only have {format_number(vault_amount)} Bitcoin in vault", parse_mode="Markdown")
                    return
                user['vault']['bitcoin'] = vault_amount - amount
                user['bitcoin'] = user.get('bitcoin', 0) + amount
                await message.answer(f"✅ Withdrew {format_number(amount)} Bitcoin from vault!\n\nAccount: {format_number(user['bitcoin'])} | Vault: {format_number(user['vault']['bitcoin'])}", parse_mode="Markdown")
            elif currency == "gold":
                vault_amount = user['vault'].get('gold', 0)
                if vault_amount < amount:
                    await message.answer(f"❌ You only have {format_number(vault_amount)} Gold in vault", parse_mode="Markdown")
                    return
                user['vault']['gold'] = vault_amount - amount
                user['gold'] = user.get('gold', 0) + amount
                await message.answer(f"✅ Withdrew {format_number(amount)} Gold from vault!\n\nAccount: {format_number(user['gold'])} | Vault: {format_number(user['vault']['gold'])}", parse_mode="Markdown")
            else:
                await message.answer("❌ Currency must be bitcoin or gold", parse_mode="Markdown")
                return
        else:
            await message.answer("❌ Action must be 'deposit' or 'withdraw'", parse_mode="Markdown")
            return
        
        save_user(u_id, user)
        
    except Exception as e:
        print(f"[ERROR] cmd_vault: {e}")
        import traceback
        traceback.print_exc()
        await message.answer("❌ Error with vault operation. Try again.", parse_mode="Markdown")


@dp.message(_cmd("help"))
async def cmd_help(message: types.Message):
    await message.answer(_help_text(), parse_mode="Markdown")


# ═══════════════════════════════════════════════════════════════════════════
#  PERK ACTIVATION COMMANDS
# ═══════════════════════════════════════════════════════════════════════════

@dp.message(_cmd("jammer"))
async def cmd_activate_jammer(message: types.Message):
    """Activate Jammer perk to scramble your words."""
    user_id = str(message.from_user.id)
    user = get_user(user_id)
    
    if not user:
        await message.answer("❌ You must be registered first. Send /start in private chat.", parse_mode="Markdown")
        return
    
    result = activate_perk(user_id, "jammer")
    if result["ok"]:
        # Send sticker
        jammer_sticker = PERK_DEFINITIONS.get("jammer", {}).get("sticker_id")
        if jammer_sticker:
            try:
                await bot.send_sticker(message.chat.id, jammer_sticker)
            except Exception as e:
                print(f"[ERROR] Could not send jammer sticker: {e}")
        
        await message.answer(
            f"✅ *Jammer Activated!*\n\n"
            f"⚡ Your words will be scrambled for 5 minutes.\n"
            f"Other players won't see what you're saying.\n\n"
            f"_Cost: 500 Bitcoin_\n"
            f"_Active: 5 minutes_",
            parse_mode="Markdown"
        )
        # Show perk status above dashboard
        active_display = format_active_perks(user_id)
        if active_display:
            await message.answer(active_display, parse_mode="HTML")
    else:
        await message.answer(f"❌ {result['msg']}", parse_mode="Markdown")


@dp.message(_cmd("anti_jammer"))
async def cmd_activate_anti_jammer(message: types.Message):
    """Activate Anti-Jammer to reveal scrambled words."""
    user_id = str(message.from_user.id)
    user = get_user(user_id)
    
    if not user:
        await message.answer("❌ You must be registered first. Send /start in private chat.", parse_mode="Markdown")
        return
    
    result = activate_perk(user_id, "anti_jammer")
    if result["ok"]:
        # Send sticker
        anti_jammer_sticker = PERK_DEFINITIONS.get("anti_jammer", {}).get("sticker_id")
        if anti_jammer_sticker:
            try:
                await bot.send_sticker(message.chat.id, anti_jammer_sticker)
            except Exception as e:
                print(f"[ERROR] Could not send anti-jammer sticker: {e}")
        
        await message.answer(
            f"✅ *Anti-Jammer Activated!*\n\n"
            f"🔓 You can reveal 5 scrambled words from opponents.\n"
            f"See through the deception!\n\n"
            f"_Cost: 800 Bitcoin_\n"
            f"_Active: 5 minutes_\n"
            f"_Uses: 5_",
            parse_mode="Markdown"
        )
        # Show perk status above dashboard
        active_display = format_active_perks(user_id)
        if active_display:
            await message.answer(active_display, parse_mode="HTML")
    else:
        await message.answer(f"❌ {result['msg']}", parse_mode="Markdown")


@dp.message(_cmd("perks"))
async def cmd_show_perks(message: types.Message):
    """Show currently active perks."""
    user_id = str(message.from_user.id)
    user = get_user(user_id)
    
    if not user:
        await message.answer("❌ You must be registered first. Send /start in private chat.", parse_mode="Markdown")
        return
    
    # Clean up expired perks
    check_and_cleanup_expired_perks(user_id)
    active_perks = get_active_perks(user_id)
    
    if not active_perks:
        await message.answer(
            "❌ No active perks.\n\n"
            "Available perks:\n"
            "• `/jammer` - Scramble your words (500 Bitcoin, 5 min)\n"
            "• `/anti_jammer` - Reveal scrambled words (800 Bitcoin, 5 min, 5 uses)",
            parse_mode="Markdown"
        )
        return
    
    response = "🔥 *ACTIVE PERKS*\n━━━━━━━━━━━━━━\n"
    for perk_type, perk_data in active_perks.items():
        perk_def = PERK_DEFINITIONS.get(perk_type, {})
        icon = perk_def.get("icon", "⚡")
        name = perk_def.get("name", perk_type)
        
        try:
            expires_at = datetime.fromisoformat(perk_data["expires_at"])
            remaining = (expires_at - datetime.utcnow()).total_seconds()
            if remaining > 0:
                minutes = int(remaining // 60)
                seconds = int(remaining % 60)
                time_str = f"{minutes}m {seconds}s"
            else:
                time_str = "Expired"
        except:
            time_str = "?"
        
        if perk_data.get("uses_remaining") is not None:
            response += f"\n{icon} **{name}**\n   ⏱️ {time_str}\n   📊 {perk_data['uses_remaining']} uses left"
        else:
            response += f"\n{icon} **{name}**\n   ⏱️ {time_str}"
    
    await message.answer(response, parse_mode="Markdown")


@dp.message(_cmd("jammers"))
async def cmd_show_jammers(message: types.Message):
    """Show which players in the current chat have jammer active."""
    if message.chat.type not in ["group", "supergroup"]:
        await message.answer("This command only works in group chats.", parse_mode="Markdown")
        return
    
    user_id = str(message.from_user.id)
    user = get_user(user_id)
    
    if not user:
        await message.answer("❌ You must be registered first.", parse_mode="Markdown")
        return
    
    # Check if user has anti-jammer active
    if not is_perk_active(user_id, "anti_jammer"):
        await message.answer(
            "🔓 You need Anti-Jammer active to see who has Jammer!\n\n"
            "Activate it with: `/anti_jammer`",
            parse_mode="Markdown"
        )
        return
    
    # This would need to scan all recent messages to find jammers
    # For now, show a placeholder
    response = "🔓 *JAMMER DETECTION SCAN*\n━━━━━━━━━━━━━━\n\n"
    response += "⚡ Scanning for active scramblers...\n\n"
    response += "_In a real game, this would show players with jammer active in this chat._"
    
    await message.answer(response, parse_mode="Markdown")

# ═══════════════════════════════════════════════════════════════════════════
#  TRIVIA GAME LOOP  (fixed)
# ═══════════════════════════════════════════════════════════════════════════

TRIVIA_QUESTIONS_PER_GAME = 10
TRIVIA_QUESTION_DURATION = 10   # seconds per question
TRIVIA_ANSWER_DISPLAY_TIME = 2  # seconds to show result before next question
TRIVIA_ROUND_TIMEOUT = 300      # 5-minute ceiling (safety net)
TRIVIA_TOPIC_ID = 36623  # Get from group settings
FUSION_TOPIC_ID = 36621  # Get from group settings
LEADERBOARDS_TOPIC_ID = 36626
async def trivia_game_loop(chat_id: int):
    import traceback as _tb
    trivia_eng = get_trivia_engine(chat_id)
    trivia_eng.reset()           # clears scores, player_answers, dashboard_msg_id
    trivia_eng.running = True

    try:
        # --- Intro Message ---
        await bot.send_message(
            chat_id,
            f"🧠 <b>TRIVIA GAME STARTING!</b>\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"📋 <b>{TRIVIA_QUESTIONS_PER_GAME} QUESTIONS</b> — {TRIVIA_QUESTION_DURATION}s each\n"
            f"⚡ First correct answer wins!\n"
            f"✅ Normal: +10 pts | 👑 Boss: +20 pts\n"
            f"🔥 3-streak: +5 bonus | 🔥🔥 5-streak: DOUBLE POINTS\n"
            f"⏱️ Speed bonuses: &lt;2s +3 | &lt;3s +2 | &lt;4s +1\n"
            f"━━━━━━━━━━━━━━━━━\n<i>Get ready...</i>",
            parse_mode="HTML",
            message_thread_id=TRIVIA_TOPIC_ID
        )
        await asyncio.sleep(3)

        # --- Persistent scoreboard placeholder (will be edited each question) ---
        placeholder_msg = await bot.send_message(
            chat_id,
            "📊 <b>SCOREBOARD</b>\n━━━━━━━━━━━━━━━━━\n<i>Waiting for first correct answer...</i>",
            parse_mode="HTML",
            message_thread_id=TRIVIA_TOPIC_ID
        )
        # dashboard_msg_id is the correct attribute on TriviaEngine
        trivia_eng.dashboard_msg_id = placeholder_msg.message_id

        # --- Main question loop ---
        for question_num in range(1, TRIVIA_QUESTIONS_PER_GAME + 1):
            if trivia_eng.force_stop:
                break

            trivia_eng.question_number = question_num
            trivia_eng.reset_for_question()   # clears player_answers & correct_answers only
            question_data = trivia_eng.pick_question()
            trivia_eng.current_question = question_data   # on_group_message reads this
            trivia_eng.active = True

            # Inter-question silent delay (random, no announcement so players can't game it)
            if question_num > 1:
                delay = random.randint(2, 8)  # random 2-8 seconds, no message
                await asyncio.sleep(delay)

            # Send question
            boss_tag = "👑 <b>BOSS ROUND!</b> " if trivia_eng.is_boss_round else ""
            q_text = _html.escape(question_data['question'])
            await bot.send_message(
                chat_id,
                f"{boss_tag}<b>QUESTION {question_num}/{TRIVIA_QUESTIONS_PER_GAME}</b>\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"❓ {q_text}\n"
                f"━━━━━━━━━━━━━━━━━",
                parse_mode="HTML",
                message_thread_id=TRIVIA_TOPIC_ID
            )

            trivia_eng.question_start_time = time.time()

            # Tick through the question timer; on_group_message handles answers in real time
            for _ in range(TRIVIA_QUESTION_DURATION):
                await asyncio.sleep(1)
                if trivia_eng.force_stop:
                    break

            trivia_eng.active = False
            trivia_eng.current_question = None

            # --- Time-up reveal ---
            correct_ans = _html.escape(question_data['answer'].upper())
            # player_answers stores (raw_answer, time_taken) 2-tuples (set by on_group_message)
            # correct_answers is the set of uids who answered correctly
            first_correct_uid = None
            best_time = float('inf')
            for uid in trivia_eng.correct_answers:
                if uid in trivia_eng.player_answers:
                    t = trivia_eng.player_answers[uid][1]
                    if t < best_time:
                        best_time = t
                        first_correct_uid = uid

            if first_correct_uid:
                winner_name = _safe_name(
                    trivia_eng.scores.get(first_correct_uid, {}).get('name', 'Someone')
                )
                result_msg = (
                    f"⏰ <b>TIME'S UP!</b>\n"
                    f"✅ <b>{winner_name}</b> was first correct ({best_time:.1f}s)\n"
                    f"📝 Answer: <b>{correct_ans}</b>"
                )
            else:
                result_msg = (
                    f"⏰ <b>TIME'S UP!</b>\n"
                    f"❌ Nobody got it!\n"
                    f"📝 Answer: <b>{correct_ans}</b>"
                )

            # Send TIME'S UP message, then delete it after 4s so answer isn't visible
            _timeup_msg = None
            try:
                _timeup_msg = await bot.send_message(
                    chat_id, result_msg,
                    parse_mode="HTML",
                    message_thread_id=TRIVIA_TOPIC_ID
                )
            except Exception:
                pass

            # Update persistent scoreboard BEFORE deleting time-up message
            await _update_trivia_scoreboard(chat_id, trivia_eng)

            # Delete the time-up message after a short window (hides the answer)
            await asyncio.sleep(4)
            if _timeup_msg:
                try:
                    await bot.delete_message(chat_id, _timeup_msg.message_id)
                except Exception:
                    pass

        # --- Game over ---
        trivia_eng.active = False
        if trivia_eng.scores:
            sorted_scores = sorted(trivia_eng.scores.items(), key=lambda x: x[1]['pts'], reverse=True)
            final_text = "🏆 <b>TRIVIA GAME OVER — FINAL RESULTS</b>\n━━━━━━━━━━━━━━━━━\n"
            medals = ["🥇", "🥈", "🥉"]
            for i, (uid, data) in enumerate(sorted_scores[:10]):
                medal = medals[i] if i < 3 else f"{i + 1}."
                # TriviaEngine.add_score() uses 'answers' key, not 'correct'
                correct_count = data.get('answers', data.get('correct', 0))
                final_text += (
                    f"{medal} <b>{_safe_name(data['name'])}</b> — "
                    f"{data['pts']} pts ({correct_count} correct)\n"
                )
                if i < 3:
                    try:
                        add_unclaimed_item(uid, "super_crate", 1)
                    except Exception:
                        pass
            await bot.send_message(
                chat_id, final_text, parse_mode="HTML",
                message_thread_id=TRIVIA_TOPIC_ID
            )
        else:
            await bot.send_message(
                chat_id,
                "🧠 <b>Trivia ended!</b>\nNo correct answers this game. Try harder next time!",
                parse_mode="HTML",
                message_thread_id=TRIVIA_TOPIC_ID
            )

    except Exception as e:
        print(f"[TRIVIA LOOP ERROR] {e}")
        _tb.print_exc()
    finally:
        trivia_eng.running = False
        trivia_eng.active = False
        trivia_eng.current_question = None

@dp.message(_cmd("leaderboard"))
async def cmd_leaderboard(message: types.Message):
    # Determine which game the user wants to see
    # You can check if they are in the Trivia topic or Fusion topic
    game = "trivia" if message.message_thread_id == 36623 else "fusion"
    
    players = get_game_weekly_leaderboard(game_type=game)
    
    text = f"🏆 *{game.upper()} WEEKLY TOP 10*\n{divider()}\n"
    for i, p in enumerate(players):
        text += f"{i+1}. {p['username']} — {p['points']} pts\n"
    
    await bot.send_message(
        message.chat.id, 
        text, 
        parse_mode="Markdown",
        message_thread_id=LEADERBOARDS_TOPIC_ID # Sends it to the Leaderboard section
    )


# ═══════════════════════════════════════════════════════════════════════════
#  CHESS SYSTEM - Internal Bot-Managed Games
# ═══════════════════════════════════════════════════════════════════════════

@dp.message(_cmd("callout"))
async def cmd_callout(message: types.Message):
    """Challenge another player to a chess match (no Lichess account required)."""
    if message.chat.type == "private":
        await message.answer("♟️ Use `/callout` in the group chat (reply to a player's message)!", parse_mode="Markdown")
        return
    
    challenger_id = message.from_user.id
    challenger_name = message.from_user.full_name or "Challenger"
    
    # Check if replying to someone
    if not message.reply_to_message:
        await message.answer(
            "♟️ **CHESS CALLOUT**\n━━━━━━━━━━━━━\n\n"
            "Reply to a player's message and use `/callout` to challenge them!",
            parse_mode="Markdown"
        )
        return
    
    opponent_id = message.reply_to_message.from_user.id
    opponent_name = message.reply_to_message.from_user.full_name or "Opponent"
    
    if challenger_id == opponent_id:
        await message.answer("🤔 You can't challenge yourself!", parse_mode="Markdown")
        return
    
    # Initialize chess stats
    await initialize_chess_stats(challenger_id)
    await initialize_chess_stats(opponent_id)
    
    # Create challenge
    success, challenge_msg, game_id = await create_game_challenge(
        challenger_id, challenger_name, opponent_id, opponent_name
    )
    
    if success:
        await message.answer(challenge_msg, parse_mode="Markdown")
        await asyncio.sleep(0.5)
    else:
        await message.answer(challenge_msg, parse_mode="Markdown")


@dp.message(_cmd("accept_chess"))
async def cmd_accept_chess(message: types.Message):
    """Accept a chess challenge."""
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Usage: `/accept_chess <game_id>`", parse_mode="Markdown")
        return
    
    game_id = args[1]
    user_id = message.from_user.id
    
    success, msg = await accept_game_challenge(user_id, game_id)
    
    if success:
        # Send to group so everyone sees
        if message.chat.type != "private":
            await message.answer(msg, parse_mode="Markdown")
        else:
            await message.answer("✅ Accepted! Go to the group to see the challenge.", parse_mode="Markdown")
    else:
        await message.answer(msg, parse_mode="Markdown")


@dp.message(_cmd("chess_result"))
async def cmd_chess_result(message: types.Message):
    """Submit a chess match result for opponent confirmation."""
    args = message.text.split()
    if len(args) < 3:
        await message.answer(
            "♟️ **SUBMIT CHESS RESULT**\n━━━━━━━━━━━━━━\n\n"
            "Usage: `/chess_result <game_id> <win|loss|draw>`\n\n"
            "Example: `/chess_result chess_123456_789 win`\n\n"
            "⏳ Opponent must confirm the result.\n"
            "✅ If both agree → Auto-confirmed\n"
            "⚠️ If dispute → Admin review",
            parse_mode="Markdown"
        )
        return
    
    game_id = args[1]
    result = args[2].lower()
    user_id = message.from_user.id
    
    if result not in ["win", "loss", "draw"]:
        await message.answer("❌ Result must be: **win**, **loss**, or **draw**", parse_mode="Markdown")
        return
    
    success, msg = await submit_game_result(user_id, game_id, result)
    
    if success:
        # Announce to group
        if message.chat.type != "private":
            await message.answer(msg, parse_mode="Markdown")
        else:
            await message.answer(msg, parse_mode="Markdown")
    else:
        await message.answer(msg, parse_mode="Markdown")


@dp.message(_cmd("chess_stats"))
async def cmd_chess_stats(message: types.Message):
    """View your chess statistics."""
    user_id = message.from_user.id
    
    await initialize_chess_stats(user_id)
    stats = await format_chess_stats(user_id)
    await message.answer(stats, parse_mode="Markdown")


@dp.message(_cmd("game_info"))
async def cmd_game_info(message: types.Message):
    """View information about a specific game."""
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Usage: `/game_info <game_id>`", parse_mode="Markdown")
        return
    
    game_id = args[1]
    success, info = await get_game_info(game_id)
    
    if success:
        await message.answer(info, parse_mode="Markdown")
    else:
        await message.answer(info, parse_mode="Markdown")


@dp.message(_cmd("obelisk"))
async def cmd_obelisk(message: types.Message):
    """Experience the Obelisk — gateway to another dimension."""
    if message.chat.type != "private":
        await message.answer("🌌 The Obelisk calls to you in private. Send this command in DM.", parse_mode="Markdown")
        return
    
    try:
        if OBELISK_GATEWAY and OBELISK_GATEWAY.strip():
            await message.answer(OBELISK_GATEWAY)
            await asyncio.sleep(1)
        
        msg = "🌌 Welcome to the Obelisk\n\nYou stand before a gateway to cosmic sectors.\n\nType !sectors to view them.\nType /teleport [1-9] to enter."
        await message.answer(msg, parse_mode="Markdown")
        
    except Exception as e:
        await message.answer("Obelisk awaits you. Use /sectors to explore.", parse_mode="Markdown")


@dp.message(_cmd("sectors"))
async def cmd_sectors(message: types.Message):
    """Explore all sectors and their consciousness."""
    if message.chat.type != "private":
        await message.answer("🗺️ *Sectors guide must be studied alone...* DM me `/sectors`", parse_mode="Markdown")
        return
    
    try:
        msg = """
🗺️ **THE SECTORS OF CONSCIOUSNESS** 🗺️

From the raw deserts to the cosmic void, each sector has its own SOUL:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
        await message.answer(msg, parse_mode="Markdown")
        
        # Show each sector's details
        for sector_num in range(1, 10):
            sector = SECTOR_CONSCIOUSNESS[sector_num]
            sector_msg = f"""
**{sector['name']}**

🧠 *Consciousness:* {sector['consciousness']}

💫 *What you feel:* {sector['feeling']}

{sector['color']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
            await message.answer(sector_msg, parse_mode="Markdown")
            await asyncio.sleep(0.3)  # Brief pause between sectors
        
        final_msg = """
Each sector tests DIFFERENT aspects of your consciousness.

Will you master all realms?

The Obelisk awaits your decision. 🌌
"""
        await message.answer(final_msg, parse_mode="Markdown")
        
    except Exception as e:
        await message.answer(f"❌ Sectors error: {e}", parse_mode="Markdown")


@dp.message(_cmd("tutorial"))
async def cmd_tutorial(message: types.Message):
    """Quick reference guide (simplified)."""
    if message.chat.type != "private":
        await _send_access_denied_sticker(message)
        return
    
    quick_guide = """
🎮 **QUICK START GUIDE**
━━━━━━━━━━━━━━━━━━━━━
✅ Auto-registered with Telegram username!

**IN THE GROUP:**
`!fusion` — Start word game
`!weekly` — View leaderboard
`!mystats` — Your stats

**PERSONAL COMMANDS:**
`/start` — Main menu
`/chess_stats` — Chess rating
`/callout` — Challenge to chess
`/jammer` — Scrambler perk
`/perks` — Active perks

**WORD GAME RULES:**
• 2 words displayed (e.g., PLAYING + FOREIGN)
• Type valid English words using ONLY those letters
• Points = word length − 2
• Streak bonus at 3+ consecutive correct guesses
• Invalid word resets streak

**RESOURCES (by word length):**
4 letters = 🪵 Wood
5 letters = 🧱 Bronze  
6 letters = ⛓️ Iron
7 letters = 💎 Diamond
8+ letters = 🏺 Relics

**CHESS:**
`/callout` → Reply to player
`/accept_chess <id>` → Accept
`/chess_result <id> [win|loss|draw]` → Submit result
(Both players must confirm!)

**JAMMER PERK:**
`/jammer` — Cost: 500 Bitcoin, Duration: 5 mins
Your words will be scrambled, hidden from others!

**CURRENCY:**
💰 Bitcoin — Earn from games, buy perks
⭐ XP — Level up by finding words

---

Questions? Ask in group or DM GameMaster!
Ready to play? Go to the group and type `!fusion` 🎮
"""
    
    await message.answer(quick_guide, parse_mode="Markdown")


@dp.message(_cmd("shop"))
async def cmd_shop(message: types.Message):
    """Buy resources with bitcoin from the vault."""
    if message.chat.type != "private":
        await _send_access_denied_sticker(message)
        return
    
    try:
        user_id = message.from_user.id
        user = get_user(user_id)
        if not user:
            await _send_unreg_sticker(message)
            return
        
        # Parse command: !shop [resource] [quantity]
        parts = message.text.split()
        if len(parts) < 2:
            # Show menu if no args
            menu = format_shop_menu(user.get("bitcoin", 0))
            await message.answer(menu, parse_mode="Markdown")
            return
        
        resource = parts[1].lower()
        if resource not in SHOP_CATALOG:
            available = ", ".join(SHOP_CATALOG.keys())
            await message.answer(f"❌ Unknown resource. Available: {available}", parse_mode="Markdown")
            return
        
        if len(parts) < 3:
            await message.answer(f"❌ Specify quantity. Example: !shop {resource} 1000", parse_mode="Markdown")
            return
        
        try:
            quantity = int(parts[2])
        except ValueError:
            await message.answer("❌ Quantity must be a number.", parse_mode="Markdown")
            return
        
        # Calculate cost
        resource_data = SHOP_CATALOG[resource]
        total_cost = int(quantity * resource_data["price_per_unit"])
        player_bitcoin = user.get("bitcoin", 0)
        
        if total_cost > player_bitcoin:
            deficit = total_cost - player_bitcoin
            await message.answer(
                f"❌ Insufficient bitcoin!\n\n"
                f"Cost: {total_cost:,} bitcoin\n"
                f"You have: {player_bitcoin:,} bitcoin\n"
                f"Needed: {deficit:,} more bitcoin",
                parse_mode="Markdown"
            )
            return
        
        # Deduct bitcoin and add resource
        user["bitcoin"] = player_bitcoin - total_cost
        user[resource] = user.get(resource, 0) + quantity
        save_user(str(user_id), user)
        
        msg = f"""
✅ **PURCHASE COMPLETE**

{resource_data['name']} × {quantity:,}
Cost: {total_cost:,} bitcoin

Your Balance: {user['bitcoin']:,} bitcoin

🏬 *More power flows your way.*
*Will you use it wisely?*
"""
        await message.answer(msg, parse_mode="Markdown")
        
    except Exception as e:
        await message.answer(f"❌ Shop error: {e}", parse_mode="Markdown")


@dp.message(_cmd("weapons"))
async def cmd_weapons(message: types.Message):
    """Browse and buy weapons from weapons shop with inline buttons."""
    if message.chat.type != "private":
        await _send_access_denied_sticker(message)
        return
    
    try:
        u_id = str(message.from_user.id)
        user = get_user(u_id)
        if not user:
            await _send_unreg_sticker(message)
            return
        
        level = user.get("level", 1)
        bitcoin = user.get("bitcoin", 0)
        
        # Get available weapons
        available = get_available_weapons(level)
        
        if not available:
            await message.answer("🃏 *GameMaster:* \"No weapons available for your level yet.\"", parse_mode="Markdown")
            return
        
        # Build message
        txt = f"🔫 **WEAPONS SHOP** (Lv{level})\n\n"
        txt += f"Your bitcoin: **{bitcoin:,}**\n\n"
        
        # Build keyboard with weapon buttons
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"{'✅' if bitcoin >= WEAPONS[wid]['cost'].get('bitcoin', 0) else '❌'} {WEAPONS[wid]['name']} ({WEAPONS[wid]['cost'].get('bitcoin', 0)} 💰)",
                    callback_data=f"weapon_{wid}"
                )] for wid in sorted(available)
            ]
        )
        
        # Add inventory button
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="📦 Your Inventory", callback_data="show_weapons_inv")
        ])
        
        await message.answer(txt, reply_markup=keyboard, parse_mode="Markdown")
        
    except Exception as e:
        await message.answer(f"❌ Error: {e}", parse_mode="Markdown")
        print(f"Error in cmd_weapons: {e}")


@dp.callback_query(lambda q: q.data.startswith("weapon_"))
async def on_weapon_purchase(callback: types.CallbackQuery):
    """Handle weapon purchase from inline buttons."""
    try:
        weapon_id = callback.data.replace("weapon_", "")
        u_id = str(callback.from_user.id)
        user = get_user(u_id)
        
        if not user:
            await callback.answer("❌ User not found", show_alert=True)
            return
        
        if weapon_id not in WEAPONS:
            await callback.answer("❌ Weapon not found", show_alert=True)
            return
        
        # Check if can buy
        can_buy, error = can_buy_weapon(weapon_id, user.get("level", 1), user.get("bitcoin", 0))
        if not can_buy:
            await callback.answer(f"❌ {error}", show_alert=True)
            return
        
        # Process purchase
        weapon = WEAPONS[weapon_id]
        cost = weapon["cost"].get("bitcoin", 0)
        
        user["bitcoin"] -= cost
        if "weapons" not in user:
            user["weapons"] = {}
        
        user["weapons"] = add_weapon_to_inventory(user.get("weapons", {}), weapon_id)
        save_user(u_id, user)
        
        # Notify user
        msg = f"✅ **PURCHASED!**\n\n{weapon['name']}\n\nCharges: {weapon['charges']} | Rarity: {weapon['rarity'].upper()}\n\nYour bitcoin: {user['bitcoin']:,}"
        await callback.answer(msg, show_alert=True)
        await callback.message.edit_text(msg + "\n\nType `/weapons` for more", parse_mode="Markdown")
        
    except Exception as e:
        await callback.answer(f"❌ Error: {e}", show_alert=True)
        print(f"Error in weapon purchase: {e}")


@dp.callback_query(lambda q: q.data == "show_weapons_inv")
async def on_show_weapons_inventory(callback: types.CallbackQuery):
    """Show weapons inventory from callback."""
    try:
        u_id = str(callback.from_user.id)
        user = get_user(u_id)
        
        if not user:
            await callback.answer("❌ User not found", show_alert=True)
            return
        
        weapons = user.get('weapons', {})
        if not weapons or len(weapons) == 0:
            await callback.answer("🃏 You have no weapons yet. Buy some first!", show_alert=True)
            return
        
        txt = "⚔️ **YOUR WEAPONS**\n\n"
        for weapon_id, weapon_data in weapons.items():
            if weapon_id not in WEAPONS:
                continue
            weapon = WEAPONS[weapon_id]
            wname = weapon.get('name', weapon_id.upper())
            
            # Handle both simple and complex data formats
            if isinstance(weapon_data, dict):
                charges_left = weapon_data.get('charges_remaining', 0)
            else:
                charges_left = weapon_data
            
            txt += f"{wname}\n├─ Charges: **{charges_left}**\n└─ {weapon.get('rarity', 'common').upper()}\n\n"
        
        await callback.answer()
        await callback.message.edit_text(txt + "\n\nType `/weapons` to buy more", parse_mode="Markdown")
        
    except Exception as e:
        await callback.answer(f"❌ Error: {e}", show_alert=True)
        print(f"Error in show_weapons_inv: {e}")


@dp.message(_cmd("use_weapon"))
async def cmd_use_weapon(message: types.Message):
    """Launch weapon with inline keyboard target selection."""
    if message.chat.type != "private":
        await message.answer("🎯 Use weapons in private only", parse_mode="Markdown")
        return
    
    try:
        u_id = str(message.from_user.id)
        user = get_user(u_id)
        if not user:
            await _send_unreg_sticker(message)
            return
        
        weapons = user.get('weapons', {})
        if not weapons:
            await message.answer("❌ You have no weapons to use. Buy from `/weapons`", parse_mode="Markdown")
            return
        
        # Show weapons with charges
        txt = "🎯 **SELECT WEAPON TO LAUNCH**\n\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        
        for weapon_id, weapon_data in weapons.items():
            if weapon_id not in WEAPONS:
                continue
            
            weapon = WEAPONS[weapon_id]
            if isinstance(weapon_data, dict):
                charges = weapon_data.get('charges_remaining', 0)
            else:
                charges = weapon_data
            
            if charges <= 0:
                continue
            
            txt += f"✅ {weapon['name']} ({charges} charges)\n"
            
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"🎯 {weapon['name'].split()[-1]} ({charges})",
                    callback_data=f"use_weapon_{weapon_id}"
                )
            ])
        
        if not keyboard.inline_keyboard:
            await message.answer("❌ All your weapons are out of charges!", parse_mode="Markdown")
            return
        
        await message.answer(txt, reply_markup=keyboard, parse_mode="Markdown")
        
    except Exception as e:
        await message.answer(f"❌ Error: {e}", parse_mode="Markdown")
        print(f"Error in use_weapon: {e}")


@dp.callback_query(lambda q: q.data.startswith("use_weapon_"))
async def on_select_target(callback: types.CallbackQuery):
    """Select target for weapon attack."""
    try:
        from supabase_db import supabase, DB_TABLE
        
        weapon_id = callback.data.replace("use_weapon_", "")
        u_id = str(callback.from_user.id)
        user = get_user(u_id)
        
        if not user or weapon_id not in WEAPONS:
            await callback.answer("❌ Invalid weapon", show_alert=True)
            return
        
        # Get top 10 targets from leaderboard (excluding self)
        targets = supabase.table(DB_TABLE).select("user_id, username, level, war_points").order("war_points", desc=True).limit(10).execute()
        target_list = [t for t in targets.data if t['user_id'] != u_id][:8]
        
        if not target_list:
            await callback.answer("❌ No targets available", show_alert=True)
            return
        
        weapon = WEAPONS[weapon_id]
        txt = f"🔫 **{weapon['name']}**\n\n"
        txt += f"Select target to attack:\n\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        
        for target in target_list:
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"⚔️ {target['username']} (Lv{target['level']}) - {target.get('war_points', 0)} pts",
                    callback_data=f"attack_weapon_{weapon_id}_{target['user_id']}"
                )
            ])
        
        await callback.answer()
        await callback.message.edit_text(txt, reply_markup=keyboard, parse_mode="Markdown")
        
    except Exception as e:
        await callback.answer(f"❌ Error: {e}", show_alert=True)
        print(f"Error in select_target: {e}")


@dp.callback_query(lambda q: q.data.startswith("attack_weapon_"))
async def on_confirm_attack(callback: types.CallbackQuery):
    """Confirm and execute weapon attack."""
    try:
        from supabase_db import supabase, DB_TABLE
        
        parts = callback.data.replace("attack_weapon_", "").split("_")
        weapon_id = parts[0]
        target_id = parts[1]
        
        u_id = str(callback.from_user.id)
        attacker = get_user(u_id)
        target = get_user(target_id)
        
        if not attacker or not target or weapon_id not in WEAPONS:
            await callback.answer("❌ Invalid attack", show_alert=True)
            return
        
        weapon = WEAPONS[weapon_id]
        weapon_data = attacker.get('weapons', {}).get(weapon_id, {})
        
        if isinstance(weapon_data, dict):
            charges = weapon_data.get('charges_remaining', 0)
        else:
            charges = weapon_data
        
        if charges <= 0:
            await callback.answer(f"❌ {weapon['name']} out of charges!", show_alert=True)
            return
        
        # Execute weapon effect
        result_msg = f"💥 **WEAPON ACTIVATED!**\n\n"
        result_msg += f"Attacker: {attacker['username']} (Lv{attacker['level']})\n"
        result_msg += f"Weapon: {weapon['name']}\n"
        result_msg += f"Target: {target['username']} (Lv{target['level']})\n\n"
        
        # Apply weapon effect based on type
        effect = weapon.get('effect', '')
        
        if 'damage' in effect:
            damage = weapon.get('damage_bitcoin', 100)
            target['bitcoin'] = max(0, target.get('bitcoin', 0) - damage)
            result_msg += f"💰 Target loses {damage} bitcoin!\n"
        
        if 'drain' in effect or 'steal' in effect:
            steal_amt = weapon.get('steal_amount', 100)
            resource = weapon.get('resource_type', 'bitcoin')
            base_res = target.get('base_resources', {}).get('resources', {})
            stolen = min(steal_amt, base_res.get(resource, 0))
            base_res[resource] = base_res.get(resource, 0) - stolen
            if 'base_resources' not in target:
                target['base_resources'] = {}
            target['base_resources']['resources'] = base_res
            result_msg += f"🌪️ Target loses {stolen} {resource}!\n"
        
        if 'turret' in weapon['name'].lower() or 'cannon' in weapon['name'].lower():
            result_msg += f"\n⚡ **BLAST!** The target's defenses shatter!\n"
        elif 'gun' in weapon['name'].lower():
            result_msg += f"\n🔫 **BANG BANG!** Shots fired!\n"
        
        # Deduct charge
        if weapon_id in attacker.get('weapons', {}):
            attacker['weapons'][weapon_id] = {
                "charges_remaining": max(0, charges - 1),
                "cooldown_until": 0,
                "last_used": None
            }
        
        # Save both players
        save_user(u_id, attacker)
        save_user(target_id, target)
        
        result_msg += f"\n📊 Charges remaining: {charges - 1}"
        
        # Also notify target
        target_notification = f"⚠️ **UNDER ATTACK!**\n\n"
        target_notification += f"Attacker: {attacker['username']} (Lv{attacker['level']})\n"
        target_notification += f"Weapon: {weapon['name']}\n"
        target_notification += f"Effect: {weapon.get('description', 'Unknown')}"
        
        try:
            await bot.send_message(int(target_id), target_notification, parse_mode="Markdown")
        except:
            pass  # Target may not have DM enabled
        
        await callback.answer(result_msg, show_alert=True)
        await callback.message.edit_text(result_msg, parse_mode="Markdown")
        
    except Exception as e:
        await callback.answer(f"❌ Error: {e}", show_alert=True)
        print(f"Error in execute attack: {e}")

@dp.message(_cmd("upgrade"))
async def cmd_upgrade(message: types.Message):
    await message.answer("🃏 *GameMaster:* \"*Queen's Satchel!* Nice try. Not ready yet.\n\nWhen it arrives: unlocks 20 inventory slots for 900 Naira.\n\nUntil then? Manage your pathetic 5 slots like an adult. Stop asking.\"", parse_mode="Markdown")


@dp.message(_cmd("challenges"))
async def cmd_challenges(message: types.Message):
    """Show weekly challenges and progress."""
    if message.chat.type != "private":
        await _send_access_denied_sticker(message); return
    
    u_id = str(message.from_user.id)
    if not get_user(u_id):
        await _send_unreg_sticker(message); return
    
    challenges = get_weekly_challenges(u_id)
    
    msg = (
        f"{divider()}\n"
        f"🎯 *WEEKLY CHALLENGES*\n"
        f"{divider()}\n\n"
    )
    
    total_reward = 0
    for i, challenge in enumerate(challenges, 1):
        msg += format_challenge_display(challenge) + "\n\n"
        if not challenge["completed"]:
            total_reward += challenge["reward"]
    
    msg += (
        f"{divider()}\n"
        f"💎 *TOTAL POTENTIAL REWARD:* {total_reward} Bitcoin\n"
        f"\n🃏 *GameMaster:* \"Complete these challenges and watch yourself feel *accomplished*. "
        f"That's what you're really chasing—not the rewards. Admit it.\"\n"
        f"{divider()}"
    )
    
    await message.answer(msg, parse_mode="Markdown")
  

@dp.message(_cmd("profile"))
async def cmd_profile(message: types.Message):
    if message.chat.type != "private":
        await _send_access_denied_sticker(message); return
    u_id = str(message.from_user.id)
    profile = get_profile(u_id)
    if not profile:
        await _send_unreg_sticker(message); return
    
    xp_pct = (profile['xp_progress'] / profile['xp_needed'] * 100) if profile['xp_needed'] > 0 else 0
    xp_bar = progress_bar(profile['xp_progress'], profile['xp_needed'], width=15)
    
    # Shield status (Phase 2A)
    user = get_user(u_id)
    shield_status = user.get('shield_status', '⚠️ UNPROTECTED')
    if shield_status == '💥 DISRUPTED':
        shield_status_str = "💥 DISRUPTED (1 attack remaining)"
    elif shield_status == '⚠️ UNPROTECTED':
        cooldown = user.get('shield_cooldown')
        if cooldown:
            try:
                remaining = (datetime.fromisoformat(cooldown) - datetime.utcnow()).total_seconds()
                if remaining > 0:
                    hours = int(remaining / 3600)
                    minutes = int((remaining % 3600) / 60)
                    shield_status_str = f"⚠️ UNPROTECTED (Cooldown: {hours}Hrs {minutes}Mins to activate shield)"
                else:
                    shield_status_str = "⚠️ UNPROTECTED (Ready to activate shield)"
            except Exception:
                shield_status_str = "⚠️ UNPROTECTED"
        else:
            shield_status_str = "⚠️ UNPROTECTED"
    else:
        shield_status_str = "🛡️ ACTIVE"
    
    # Format base resources
    base_res = profile.get('base_resources', {})
    base_name = profile.get('base_name') or "Nameless Base"
    resources_str = (
        f"🪵 {base_res.get('wood', 0)} | 🧱 {base_res.get('bronze', 0)} | "
        f"⛓️ {base_res.get('iron', 0)} | 💎 {base_res.get('diamond', 0)} | "
        f"🏺 {base_res.get('relics', 0)}"
    )
    
    # Check for sector consciousness split
    current_sector = profile.get('sector')
    base_sector = user.get('sector')
    sector_split_msg = ""
    if current_sector and base_sector and current_sector != base_sector:
        try:
            sector_split_msg = consciousness_split_awareness(current_sector, base_sector, profile['username'])
            sector_split_msg = "\n\n" + sector_split_msg
        except:
            pass
    
    await message.answer(
        f"🃏 *GameMaster:* \"Staring at your own reflection. Fine.\"\n"
        f"{divider()}\n\n"
        f"👤 *{profile['username']}* — *LEVEL {profile['level']}*\n\n"
        f"⭐ XP Progress:\n{xp_bar}\n"
        f"💰 Bitcoin: *{profile['bitcoin']}*\n"
        f"📍 Current Sector: _{profile.get('sector_display','Not Assigned')}_\n"
        f"🏰 Base Sector: _{get_sector_display(base_sector)}_\n"
        f"🛡️ Shield Status: {shield_status_str}\n\n"
        f"{divider()}\n\n"
        f"📊 *BATTLE RECORDS*\n"
        f"├─ This Week: *{profile['weekly_points']}* pts\n"
        f"└─ All-Time: *{profile['all_time_points']}* pts\n\n"
        f"🏰 *{base_name}*\n"
        f"├─ Resources: {resources_str}\n"
        f"└─ Food: 🌽 *{profile.get('base_food', 0)}*\n\n"
        f"📦 *INVENTORY* ({profile['inventory_count']}/{profile['backpack_slots']} slots)\n"
        f"├─ Unclaimed: *{profile['unclaimed_count']}* ⚠️\n"
        f"└─ Crates: *{profile['crate_count']}* | Shields: *{profile['shield_count']}*\n"
        f"{divider()}{sector_split_msg}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📈 Check Prestige", callback_data="prestige_info")],
            [InlineKeyboardButton(text="🎓 Training", callback_data="train_menu"), 
             InlineKeyboardButton(text="🏰 Build", callback_data="build_menu")],
        ])
    )


@dp.message(_cmd("prestige"))
async def cmd_prestige(message: types.Message):
    """Prestige (reset level) for bonuses."""
    if message.chat.type != "private":
        await message.answer("🃏 *GameMaster:* \"Prestige in private, coward.\"", parse_mode="Markdown")
        return
    
    u_id = str(message.from_user.id)
    user = get_user(u_id)
    if not user:
        await _send_unreg_sticker(message)
        return
    
    level = user.get("level", 1)
    prestige = user.get("prestige", 0)
    
    can_do, error = can_prestige(level, prestige)
    if not can_do:
        await message.answer(f"❌ {error}", parse_mode="Markdown")
        return
    
    # Execute prestige
    result = execute_prestige(user)
    if not result["success"]:
        await message.answer(f"❌ {result['message']}", parse_mode="Markdown")
        return
    
    # Save updated user
    save_user(u_id, user)
    
    # Send confirmation
    confirmation = format_prestige_confirmation(
        result["new_prestige"],
        result["bonus_xp"],
        result["bonus_bitcoin"]
    )
    
    await message.answer(confirmation, parse_mode="Markdown")


@dp.callback_query(lambda q: q.data == "prestige_info")
async def callback_prestige_info(callback: types.CallbackQuery):
    """Show prestige status when button clicked."""
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    if not user:
        await callback.answer("Not registered")
        return
    
    level = user.get("level", 1)
    prestige = user.get("prestige", 0)
    
    status = format_prestige_status(level, prestige)
    await callback.message.edit_text(status, parse_mode="Markdown")
    await callback.answer()


@dp.callback_query(lambda q: q.data == "train_menu")
async def callback_train_menu(callback: types.CallbackQuery):
    """Show training unit menu with inline buttons."""
    await callback.message.edit_text(
        "🎖️ *MILITARY TRAINING*\n\n"
        "Select unit type to train:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👹 Police and Dogs (5 wood)", callback_data="train_pawn"),
             InlineKeyboardButton(text="🗡️ Knights (15 wood + 5 bronze)", callback_data="train_knight")],
            [InlineKeyboardButton(text="⚜️ Bishops (10 bronze + 3 iron)", callback_data="train_bishop"),
             InlineKeyboardButton(text="🏰 Rooks (10 iron + 2 diamond)", callback_data="train_rook")],
            [InlineKeyboardButton(text="👑 Queens (20 iron + 5 diamond)", callback_data="train_queen"),
             InlineKeyboardButton(text="⚔️ Kings (15 diamond + 1 relic)", callback_data="train_king")],
        ]),
        parse_mode="Markdown"
    )
    await callback.answer()


@dp.callback_query(lambda q: q.data == "build_menu")
async def callback_build_menu(callback: types.CallbackQuery):
    """Show building/trap menu with inline select."""
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    if not user:
        await callback.answer("Not registered", show_alert=True)
        return
    
    xp = user.get("xp", 0)
    base_level = max(1, 1 + (xp // 1000))
    
    available_buildings = get_available_buildings(base_level)
    available_traps = get_available_traps(base_level)
    
    keyboard = [
        [InlineKeyboardButton(text="🏰 Build Structure", callback_data="show_building_list"),
         InlineKeyboardButton(text="🔱 Build Trap", callback_data="show_trap_list")],
    ]
    
    msg = f"🏰 *BASE DEVELOPMENT*\n\nBase Level: {base_level}\n\nChoose what to build:"
    
    await callback.message.edit_text(
        msg,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )
    await callback.answer()


@dp.callback_query(lambda q: q.data == "show_building_list")
async def callback_show_buildings(callback: types.CallbackQuery):
    """Show list of available buildings."""
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    if not user:
        await callback.answer("Not registered", show_alert=True)
        return
    
    xp = user.get("xp", 0)
    base_level = max(1, 1 + (xp // 1000))
    current_buildings = user.get("buildings", {})
    
    available = get_available_buildings(base_level)
    
    # Create buttons for each building
    keyboard = []
    for building_id in available:
        building = BUILDING_TYPES[building_id]
        button = InlineKeyboardButton(
            text=f"{building['name']} (Lv: {current_buildings.get(building_id, 0)})",
            callback_data=f"build_{building_id}"
        )
        keyboard.append([button])
    
    msg = f"🏰 *AVAILABLE BUILDINGS* (Level {base_level})\n\nSelect to build:"
    
    await callback.message.edit_text(
        msg,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )
    await callback.answer()


@dp.callback_query(lambda q: q.data == "show_trap_list")
async def callback_show_traps(callback: types.CallbackQuery):
    """Show list of available traps."""
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    if not user:
        await callback.answer("Not registered", show_alert=True)
        return
    
    xp = user.get("xp", 0)
    base_level = max(1, 1 + (xp // 1000))
    current_traps = user.get("traps", {})
    
    available = get_available_traps(base_level)
    
    # Create buttons for each trap
    keyboard = []
    for trap_id in available:
        trap = TRAP_TYPES[trap_id]
        button = InlineKeyboardButton(
            text=f"{trap['name']} (Ct: {current_traps.get(trap_id, 0)})",
            callback_data=f"trap_{trap_id}"
        )
        keyboard.append([button])
    
    msg = f"🔱 *AVAILABLE TRAPS* (Level {base_level})\n\nSelect to build:"
    
    await callback.message.edit_text(
        msg,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )
    await callback.answer()


@dp.callback_query(lambda q: q.data.startswith("build_"))
async def callback_build_structure(callback: types.CallbackQuery):
    """Build selected structure."""
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    if not user:
        await callback.answer("Not registered", show_alert=True)
        return
    
    building_id = callback.data.replace("build_", "")
    xp = user.get("xp", 0)
    base_level = max(1, 1 + (xp // 1000))
    
    can_build, error = can_build_building(building_id, base_level)
    if not can_build:
        await callback.answer(f"❌ {error}", show_alert=True)
        return
    
    # Calculate cost
    current_buildings = user.get("buildings", {})
    current_level = current_buildings.get(building_id, 0)
    cost = calculate_building_cost(building_id, current_level + 1)
    
    building = BUILDING_TYPES[building_id]
    msg = f"{building['name']}\n\n"
    msg += f"Bonus: {building['description']}\n\n"
    msg += f"Cost: " + " + ".join([f"{amt} {res.upper()}" for res, amt in cost.items()])
    msg += f"\n\nConfirm build?"
    
    await callback.message.edit_text(
        msg,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Build", callback_data=f"build_confirm_{building_id}"),
             InlineKeyboardButton(text="❌ Cancel", callback_data="build_menu")],
        ])
    )
    await callback.answer()


@dp.callback_query(lambda q: q.data.startswith("build_confirm_"))
async def callback_build_confirm(callback: types.CallbackQuery):
    """Confirm and execute building."""
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    if not user:
        await callback.answer("Not registered", show_alert=True)
        return
    
    building_id = callback.data.replace("build_confirm_", "")
    
    current_buildings = user.get("buildings", {})
    current_level = current_buildings.get(building_id, 0)
    cost = calculate_building_cost(building_id, current_level + 1)
    
    # Get base resources
    base_res = user.get('base_resources', {})
    resources = base_res.get('resources', {})
    
    # Check resources
    for res_type, needed in cost.items():
        available = resources.get(res_type, 0)
        if available < needed:
            await callback.answer(
                f"❌ Need {needed} {res_type.upper()}, only have {available}",
                show_alert=True
            )
            return
    
    # Deduct and build
    for res_type, needed in cost.items():
        resources[res_type] -= needed
    
    current_buildings[building_id] = current_level + 1
    user["buildings"] = current_buildings
    save_user(u_id, user)
    
    building = BUILDING_TYPES[building_id]
    await callback.message.edit_text(
        f"✅ *{building['name']}* BUILT!\n\n"
        f"Level: {current_level + 1}\n"
        f"Bonus: {building['description']}"
    )
    await callback.answer()


@dp.callback_query(lambda q: q.data.startswith("trap_"))
async def callback_build_trap(callback: types.CallbackQuery):
    """Build selected trap."""
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    if not user:
        await callback.answer("Not registered", show_alert=True)
        return
    
    trap_id = callback.data.replace("trap_", "")
    xp = user.get("xp", 0)
    base_level = max(1, 1 + (xp // 1000))
    
    can_build, error = can_build_trap(trap_id, base_level)
    if not can_build:
        await callback.answer(f"❌ {error}", show_alert=True)
        return
    
    trap = TRAP_TYPES[trap_id]
    cost = trap.get("cost", {})
    
    msg = f"{trap['name']}\n\n"
    msg += f"Effect: {trap['effect']}\n\n"
    msg += f"Cost: " + " + ".join([f"{amt} {res.upper()}" for res, amt in cost.items()])
    msg += f"\n\nBuild?"
    
    await callback.message.edit_text(
        msg,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Build", callback_data=f"trap_confirm_{trap_id}"),
             InlineKeyboardButton(text="❌ Cancel", callback_data="show_trap_list")],
        ])
    )
    await callback.answer()


@dp.callback_query(lambda q: q.data.startswith("trap_confirm_"))
async def callback_trap_confirm(callback: types.CallbackQuery):
    """Confirm and build trap."""
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    if not user:
        await callback.answer("Not registered", show_alert=True)
        return
    
    trap_id = callback.data.replace("trap_confirm_", "")
    trap = TRAP_TYPES[trap_id]
    cost = trap.get("cost", {})
    
    # Get resources
    base_res = user.get('base_resources', {})
    resources = base_res.get('resources', {})
    
    # Check
    for res_type, needed in cost.items():
        available = resources.get(res_type, 0)
        if available < needed:
            await callback.answer(
                f"❌ Need {needed} {res_type.upper()}, only have {available}",
                show_alert=True
            )
            return
    
    # Deduct and build
    for res_type, needed in cost.items():
        resources[res_type] -= needed
    
    traps = user.get("traps", {})
    traps[trap_id] = traps.get(trap_id, 0) + 1
    user["traps"] = traps
    save_user(u_id, user)
    
    await callback.message.edit_text(
        f"✅ *{trap['name']}* BUILT!\n\n"
        f"Count: {traps[trap_id]}\n"
        f"Effect: {trap['effect']}"
    )
    await callback.answer()



@dp.message(_cmd("myaccount"))
async def cmd_myaccount(message: types.Message):
    """Display account management panel with save/load/reset options."""
    if message.chat.type != "private":
        await _send_access_denied_sticker(message)
        return
    
    u_id = str(message.from_user.id)
    user = get_user(u_id)
    if not user:
        await _send_unreg_sticker(message)
        return
    
    username = user.get('username', 'Player')
    level = user.get('level', 1)
    xp = user.get('xp', 0)
    
    # Count saves
    saves = list_saves(u_id)
    save_count = len(saves)
    
    # Build interface
    txt = f"""
🎮 *ACCOUNT MANAGEMENT - {username.upper()}*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 *PROFILE*
├─ Level: **{level}**
├─ XP: **{xp}**
└─ Saves: **{save_count}**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💾 *GAME STATE MANAGEMENT*

**SAVE GAME**
Use: `/save [1-5]`
└─ Creates a backup of your current progress
└─ Max 5 slots available

**LOAD GAME**
Use: `/load [1-5]`
└─ Restore your game from a saved slot
└─ Returns you to that exact point

**RESET GAME**
Use: `/reset soft` or `/reset hard`
├─ **soft**: Reset battle stats only
├─ **hard**: Complete restart (dangerous!)
└─ **weekly**: Reset weekly points

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ *CAUTION*
├─ Hard reset deletes all progress!
├─ Backups are permanent unless deleted
└─ You can have up to 5 manual saves

*Type a command above to get started!*
"""
    
    await message.answer(txt.strip(), parse_mode="Markdown")


@dp.message(_cmd("weapons_inventory"))
async def cmd_weapons_inventory(message: types.Message):
    """Display all weapons currently owned by player."""
    if message.chat.type != "private":
        await _send_access_denied_sticker(message); return
    
    u_id = str(message.from_user.id)
    user = get_user(u_id)
    if not user:
        await _send_unreg_sticker(message); return
    
    weapons = user.get('weapons', {})
    if not weapons:
        await message.answer("🃏 *GameMaster:* \"No weapons. You fight like a peasant. Buy some from `!weapons`\"", parse_mode="Markdown"); return
    
    txt = "⚔️ *YOUR WEAPONS ARSENAL*\n━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for weapon_id, weapon_data in weapons.items():
        if weapon_id not in WEAPONS:
            continue
        weapon = WEAPONS[weapon_id]
        wname = weapon.get('name', weapon_id.upper())
        
        # Handle both simple number format and complex object format
        if isinstance(weapon_data, dict):
            charges_left = weapon_data.get('charges_remaining', 0)
        else:
            charges_left = weapon_data
        
        txt += f"{wname}\n├─ Charges: **{charges_left}**\n└─ {weapon.get('rarity', 'common').upper()}\n\n"
    
    txt += "━━━━━━━━━━━━━━━━━━━━\nBuy more: `!weapons`"
    await message.answer(txt, parse_mode="Markdown")


@dp.message(_cmd("inventory"))
async def cmd_inventory(message: types.Message):
    if message.chat.type != "private":
        await _send_access_denied_sticker(message); return
    u_id = str(message.from_user.id)
    if not get_user(u_id):
        await _send_unreg_sticker(message); return
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
            kind = "XP" if "xp" in itype else "BITCOIN"
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
        await _send_access_denied_sticker(message); return
    u_id = str(message.from_user.id)
    if not get_user(u_id):
        await _send_unreg_sticker(message); return
    
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
        "bitcoin_multiplier": lambda m: f"💎 BITCOIN MULTIPLIER x{m}",
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
        await _send_access_denied_sticker(message); return
    u_id = str(message.from_user.id)
    if not get_user(u_id):
        await _send_unreg_sticker(message); return
    await _do_claim_all(message, u_id, is_command=True)


@dp.message(_cmd("battle_items"))
async def cmd_battle_items(message: types.Message):
    """Show all battle items available for purchase with prices and requirements."""
    if message.chat.type != "private":
        await message.answer("⚔️ *GameMaster:* \"Check your items in *private*.\"", parse_mode="Markdown"); return
    
    u_id = str(message.from_user.id)
    user = get_user(u_id)
    if not user:
        await _send_unreg_sticker(message); return
    
    player_level = user.get("level", 1)
    player_bitcoin = user.get("bitcoin", 0)
    inventory = get_inventory(u_id) or {}
    
    # Define all battle items
    battle_items = {
        "common": [
            {"id": "1minx", "name": "⚡️ 1 Min Speedup", "price": 10, "level": 1, "desc": "Speed up your time"},
            {"id": "5minx", "name": "⚡️ 5 Min Speedup", "price": 50, "level": 1, "desc": "Speed up your time"},
            {"id": "15minx", "name": " ⚡️ 15 Min Speedup", "price": 100, "level": 1, "desc": "Speed up your time"},
            {"id": "30minx", "name": " ⚡️ 30 Min Speedup", "price": 150, "level": 1, "desc": "Speed up your time"},
            {"id": "1hourx", "name": " ⚡️ 1 hour Speedup", "price": 300, "level": 1, "desc": "Speed up your time"},
            {"id": "3hourx", "name": " ⚡️ 3-Hour Speedup", "price": 500, "level": 1, "desc": "Protect your base   "},
            {"id": "1dayx", "name": " ⚡️ 1-Day Speedup", "price": 1000, "level": 1, "desc": "Protect your base   "},
            {"id": "5dayx", "name": " ⚡️ 5-Day Speedup", "price": 500, "level": 7, "desc": "Protect your base   "},
            {"id": "21dayx", "name": " ⚡️ 21-Day Speedup", "price": 500, "level": 10, "desc": "Protect your base   "},
            {"id": "1hours", "name": "🛡️ 1-Hour Shield", "price": 200, "level": 1, "desc": "Protect your base  "},
            {"id": "3hours", "name": "🛡️ 3-Hour Shield", "price": 500, "level": 1, "desc": "Protect your base  "},
            {"id": "12hours", "name": "🛡️ 12-Hour Shield", "price": 700, "level": 1, "desc": "Protect your base  "},
            {"id": "1days", "name": "🛡️ 1-Day Shield", "price": 1000, "level": 1, "desc": "Protect your base  "},
            {"id": "3days", "name": "🛡️ 3-Day Shield", "price": 2500, "level": 1, "desc": "Protect your base  "},
            {"id": "7days", "name": "🛡️ 7-Day Shield", "price": 5000, "level": 10, "desc": "Protect your base  "},
            {"id": "name_shield", "name": "🛡️ Name Shield", "price": 800, "level": 5, "desc": "Hide your username • Block targeting from attackers • Anonymize yourself on leaderboard. Duration: 24h "},
            {"id": "rank_disguise", "name": "🎭 Rank Disguise", "price": 300, "level": 3, "desc": "Hide your true leaderboard rank. Duration: 24h"},
            {"id": "coin_explosion", "name": "🤑 Coin Multiplier", "price": 200, "level": 5, "desc": "Double coins on next win"},
            {"id": "coin_explosion", "name": "🙊 Birthday Coins ", "price": 300, "level": 5, "desc": "Drop a crate in arena for 1 minute All who try to claim the crate will deposit 50 bitcoin from their balance during the next round"},
            {"id": "fake_shield", "name": "🛡️ Fake Shield", "price": 1000, "level": 7, "desc": "Decoy shield to trick attackers. Will get deactivated if player tries to attack another person or if they are being attacked or scouted."},
            {"id": "rank_swap", "name": "💀 Rank Swap", "price": 350, "level": 4, "desc": "Use this to swap ranks with any target for 1 hour, use it to gain their leaderboard buffs temporarily. You can also swap with a lower rank player just to put a bounty on their head"},
            {"id": "arank_swap", "name": "💀 Anti-Rank Swap", "price": 700, "level": 4, "desc": "Use this to restrict your rank from being swapped"},
            {"id": "trade_pla", "name": "🤝 Trading Places", "price": 1200, "level": 4, "desc": "Use this when your opponent tries to swap ranks with you. You select what they will receieve in place of your rank, whether infamy, debuffs or negative resources. They will swap your stats for theirs. ⚠️ Warning, you will receive whatever was swapped even if they have worse than you. Use strategically!"},
            {"id": "clown_badge", "name": "🤡 Clown Badge", "price": 1000, "level": 10, "desc": "Embarrass and disgrace an opponent. This is a cosmetic item and effect will wear off after 24 hours"},
            {"id": "scout", "name": "📸 Scout", "price": 600, "level": 6, "desc": "Reveal target's resources"},
            {"id": "anti_scout", "name": "📴 Anti-Scout", "price": 500, "level": 5, "desc": "Block scouts for 12 hours"},
        ],
        "rare": [
            {"id": "blackout", "name": "⚫ Blackout", "price": 2000, "level": 10, "desc": "Mysterious war effect (powerful)"},
            {"id": "false_chest", "name": "💣 False Chest (Trap)", "price": 1500, "level": 8, "desc": "Gift that explodes in enemy base"},
            {"id": "purge_call", "name": "🔥 Purge Call", "price": 2500, "level": 12, "desc": "Find & raid weaker players"},
            {"id": "gift_drop", "name": "🎁 Gift Drop", "price": 1800, "level": 9, "desc": "Alliance gift for team boost"},
        ],
        "prestige": [
            {"id": "celestial_crown", "name": "👑 Celestial Crown", "price": 5000, "level": 20, "desc": "Ultimate status symbol"},
            {"id": "gem_multiplier", "name": "💎 Gem Multiplier (3x)", "price": 4000, "level": 18, "desc": "Triple item power for one use"},
            {"id": "eternal_shield", "name": "⭐ Eternal Shield", "price": 6000, "level": 25, "desc": "Permanent protection (removable)"},
        ]
    }
    
    txt = f"{divider()}\n⚔️ *BATTLE ITEMS SHOP* ⚔️\n{divider()}\n"
    txt += f"💰 Your Bitcoin: *{player_bitcoin}*\n"
    txt += f"🎖️ Your Level: *{player_level}*\n\n"
    
    # Count items by category
    for category, items in battle_items.items():
        category_name = {"common": "🛡️ COMMON", "rare": "🏆 RARE", "prestige": "👑 PRESTIGE"}[category]
        txt += f"\n*{category_name} ITEMS:*\n"
        
        for item in items:
            count = inventory.get(item["id"], 0)
            affordable = player_bitcoin >= item["price"]
            level_ok = player_level >= item["level"]
            
            # Build status line
            if count > 0:
                status = f"✅ (Have: {count})"
            elif not level_ok:
                status = f"🔒 Level {item['level']} needed"
            elif not affordable:
                status = f"❌ Need {item['price'] - player_bitcoin} more bitcoin"
            else:
                status = f"✅ Buy (${item['price']})"
            
            txt += f"{item['name']}\n   {item['desc']} | {status}\n"
    
    txt += f"\n{divider()}\n"
    txt += "💡 *Tip:* Type `!buy [item_id]` to purchase\n"
    txt += "Example: `!buy 7day_shield`\n"
    txt += f"{divider()}"
    
    await message.answer(txt, parse_mode="Markdown")


@dp.message(_cmd("buy"))
async def cmd_buy(message: types.Message):
    """Buy a battle item from the shop."""
    if message.chat.type != "private":
        await message.answer("🛒 *GameMaster:* \"Shop in *private* only.\"", parse_mode="Markdown"); return
    
    u_id = str(message.from_user.id)
    user = get_user(u_id)
    if not user:
        await _send_unreg_sticker(message); return
    
    args = message.text.strip().split()
    if len(args) < 2:
        await message.answer(
            "🛒 *HOW TO BUY*\n"
            "Usage: `!buy [item_id]`\n\n"
            "Examples:\n"
            "`!buy 7day_shield`\n"
            "`!buy scout`\n"
            "`!buy eternal_shield`\n\n"
            "Type `!battle_items` to see all items and prices",
            parse_mode="Markdown"
        )
        return
    
    item_id = args[1].lower()
    
    # Define all items with pricing
    all_items = {
        "7day_shield": {"name": "🛡️ 7-Day Shield", "price": 500, "level": 1},
        "name_shield": {"name": "🔐 Name Shield (24h)", "price": 800, "level": 5},
        "rank_disguise": {"name": "🎭 Rank Disguise", "price": 300, "level": 3},
        "coin_explosion": {"name": "🧨 Coin Explosion", "price": 400, "level": 5},
        "fake_shield": {"name": "🧠 Fake Shield", "price": 250, "level": 2},
        "rank_swap": {"name": "💀 Rank Swap", "price": 350, "level": 4},
        "clown_badge": {"name": "🤡 Clown Badge", "price": 200, "level": 1},
        "scout": {"name": "📸 Scout", "price": 600, "level": 6},
        "anti_scout": {"name": "📴 Anti-Scout", "price": 500, "level": 5},
        "blackout": {"name": "⚫ Blackout", "price": 2000, "level": 10},
        "false_chest": {"name": "💣 False Chest", "price": 1500, "level": 8},
        "purge_call": {"name": "🔥 Purge Call", "price": 2500, "level": 12},
        "gift_drop": {"name": "🎁 Gift Drop", "price": 1800, "level": 9},
        "celestial_crown": {"name": "👑 Celestial Crown", "price": 5000, "level": 20},
        "gem_multiplier": {"name": "💎 Gem Multiplier", "price": 4000, "level": 18},
        "eternal_shield": {"name": "⭐ Eternal Shield", "price": 6000, "level": 25},
    }
    
    if item_id not in all_items:
        await message.answer(
            f"❌ Item `{item_id}` not found.\n"
            "Type `!battle_items` to see valid items.",
            parse_mode="Markdown"
        )
        return
    
    item = all_items[item_id]
    player_level = user.get("level", 1)
    player_bitcoin = user.get("bitcoin", 0)
    
    # Check level requirement
    if player_level < item["level"]:
        await message.answer(
            f"🔒 *{item['name']}* requires Level {item['level']}\n"
            f"Your level: {player_level}\n"
            f"You need {item['level'] - player_level} more levels.",
            parse_mode="Markdown"
        )
        return
    
    # Check bitcoin
    if player_bitcoin < item["price"]:
        needed = item["price"] - player_bitcoin
        await message.answer(
            f"💰 *{item['name']}* costs **${item['price']}**\n"
            f"Your bitcoin: {player_bitcoin}\n"
            f"❌ You need **${needed} more bitcoin**",
            parse_mode="Markdown"
        )
        return
    
    # Purchase successful
    user["bitcoin"] = player_bitcoin - item["price"]
    
    # Apply special item effects
    from datetime import datetime, timedelta
    if item_id == "name_shield":
        # Activate name shield for 24 hours
        user["name_shield_until"] = (datetime.now() + timedelta(hours=24)).isoformat()
        activation_msg = "🔐 *Name Shield has been ACTIVATED*\n\n" \
                         "Your username is now hidden!\n" \
                         "• Players cannot find you via `/attack` or `/scout`\n" \
                         "• Your name will show up as *[🛡️ Anonymous]* on leaderboards\n" \
                         "• Attackers will appear as *[Anonymous Attacker]** in revenge notifications\n\n" \
                         "• ⏱️Name shield expires in 24 hours!"
    else:
        activation_msg = ""
    
    save_user(u_id, user)
    add_inventory_item(u_id, item_id, 1)
    
    msg = f"✅ *PURCHASE SUCCESSFUL*\n\n" \
          f"🛍️ You bought: {item['name']}\n" \
          f"💰 Cost: ${item['price']}\n" \
          f"💾 Remaining bitcoin: {user['bitcoin']}\n\n"
    
    if activation_msg:
        msg += activation_msg
    else:
        msg += "🃏 *GameMaster:* \"A wise investment... or is it? We'll see.\""
    
    await message.answer(msg, parse_mode="Markdown")


@dp.message(_cmd("changename"))
async def cmd_changename(message: types.Message):
    if message.chat.type != "private":
        await _send_access_denied_sticker(message); return
    u_id = str(message.from_user.id)
    user = get_user(u_id)
    if not user:
        await _send_unreg_sticker(message); return
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


@dp.message(_cmd("name_shield"))
async def cmd_name_shield_status(message: types.Message):
    """Check if your name shield is active and when it expires."""
    if message.chat.type != "private":
        await _send_access_denied_sticker(message)
        return
    
    u_id = str(message.from_user.id)
    user = get_user(u_id)
    if not user:
        await _send_unreg_sticker(message)
        return
    
    name_shield_until = user.get("name_shield_until")
    username = user.get("username", "Unknown")
    
    if not name_shield_until:
        await message.answer(
            f"🔐 *NAME SHIELD STATUS*\n\n"
            f"⚠️ *INACTIVE*\n\n"
            f"Your username is currently visible to all players!\n"
            f"Players can attack or scout you using `/attack @{username}`\n"
            f"Remember that your username appears on leaderboards.\n\n"            
            f"When a name shield is activated your username on leaderboards appear as *Anonymous*.\n\n"
            f"Purchase a *Name Shield* from the battle shop using `/battle_items` in order to protect yourself!",
            parse_mode="Markdown"
        )
        return
    
    from datetime import datetime
    try:
        expiry = datetime.fromisoformat(name_shield_until)
        now = datetime.now()
        
        if now < expiry:
            remaining = expiry - now
            hours = remaining.seconds // 3600
            minutes = (remaining.seconds % 3600) // 60
            
            await message.answer(
                f"🔐 *NAME SHIELD STATUS*\n\n"
                f"✅ *ACTIVE*\n\n"
                f"Your username is now *HIDDEN* from all players!\n\n"
                f"⏱️ *Time Remaining:*\n"
                f"• {hours}H {minutes}M\n\n"
                f"*Take note of the following*\n"
                f"•  Players cannot use `/attack` or `/scout` on you\n"
                f"•  To all players you appear as *[🛡️ Anonymous]* on leaderboards\n"
                f"• 🕵️ Attackers appear as **[Anonymous Attacker]** to you\n\n"
                f"_Your shield expires at {expiry.strftime('%H:%M:%S UTC')}_",
                parse_mode="Markdown"
            )
        else:
            # Shield expired - clean it up
            user.pop("name_shield_until", None)
            save_user(u_id, user)
            
            await message.answer(
                f"🔐 *NAME SHIELD STATUS*\n\n"
                f"❌ **EXPIRED**\n\n"
                f"Your name shield has worn off!\n"
                f"You are now visible to other players again.\n\n"
                f"Purchase another **Name Shield** to stay protected!",
                parse_mode="Markdown"
            )
    except:
        await message.answer(
            f"🔐 *NAME SHIELD STATUS*\n\n"
            f"⚠️ Error reading shield status. Try again.",
            parse_mode="Markdown"
        )


@dp.message(_cmd("setup_base"))
async def cmd_setup_base(message: types.Message):
    if message.chat.type != "private":
        await _send_access_denied_sticker(message); return
    
    u_id = str(message.from_user.id)
    user = get_user(u_id)
    
    if not user:
        await _send_unreg_sticker(message) 
        return
    
    if user.get("base_name"):
        await message.answer(f"🃏 *GameMaster:* \"Your loyalty is fickle. You already rule *{user['base_name']}*.\"", parse_mode="Markdown"); 
        return
    
    # Parse command: !setup_base [sector] [Name]
    parts = message.text.strip().split(maxsplit=2)
    
    if len(parts) < 3:
        # Show selection flow if not enough args
        await message.answer(SECTOR_SELECTION_FLOW, parse_mode="Markdown")
        return
    
    try:
        sector = int(parts[1])
    except ValueError:
        await message.answer("❌ You must choose sector number between (1-9). Example: `/setup_base 5 \"Naomis Fortress\"`", parse_mode="Markdown")
        return
    
    if sector < 1 or sector > 9:
        await message.answer("❌ You must choose sector number between (1-9)", parse_mode="Markdown")
        return
    
    base_name = parts[2].strip()[:25]

    xp = user.get("xp", 0)
    base_level = 1 + (xp // 1000) 

    # Initialize base structure
    user["base_name"] = base_name
    user["base_level"] = base_level
    user["sector"] = sector  # Player's chosen sector
    user["war_points"] = 0
    user["wins"] = 0
    user["losses"] = 0
    user["kings_captured"] = 0
    user["times_captured"] = 0
    user["base_name_changes"] = 0
    user["alliance_id"] = None
    
    # Starting resources vary by sector
    base_resources_template = {"wood": 20, "bronze": 10, "iron": 0, "diamond": 0, "relics": 0}
    
    # Sector bonuses (theme-based resource distribution)
    sector_bonuses = {
        1: {"wood": 30},    # Badlands: more wood
        2: {"bronze": 20},  # Crimson: more bronze
        3: {"wood": 25},    # Resource rich
        4: {"bronze": 15},  # Balanced
        5: {"iron": 5},     # Rare iron
        6: {"iron": 5},     # Rare iron
        7: {"diamond": 2},  # Very rare diamond
        8: {"bronze": 20},  # Balanced
        9: {"diamond": 3},  # Void sector has rarest
    }
    
    # Apply sector bonus
    sector_resources = dict(base_resources_template)
    if sector in sector_bonuses:
        for res, amt in sector_bonuses[sector].items():
            sector_resources[res] = sector_resources.get(res, 0) + amt
    
    user["base_resources"] = {
        "resources": sector_resources,
        "food": 50,
        "current_streak": 0
    }
    user["military"] = {"Police and Dogs": 5}
    military = user["military"]
    user["traps"] = {}
    user["buffs"] = {}
    
    try:
        save_user(u_id, user)
        print(f"[BASE] {user.get('username', message.from_user.first_name)} created base '{base_name}' in SECTOR {sector}")
        
        # Get sector consciousness description
        sector_info = SECTOR_CONSCIOUSNESS.get(sector, {})
        sector_name = sector_info.get("name", f"SECTOR {sector}")
        
        # Resources breakdown
        resources_str = ", ".join([f"{v}x {k}" for k, v in sector_resources.items() if v > 0])
        
        msg = f"""
╔═══════════════════════════════════════════════╗
║        🚩  TERRITORY CLAIMED  🚩             ║
╠═══════════════════════════════════════════════╣
║                                               ║
║  🏰 *Base:* {base_name}                      ║
║  ⭐ *Base Level:* {base_level}               ║
║  📍 *Location:* {sector_name}                ║
║  💰 *Resources:* {resources_str}             ║
║  🛡️ *Garrison:* {military}                   ║
║                                               ║
║                                               ║
║  You didnt choose here, here chose you you.   ║
║  {sector_info.get('consciousness', 'Your destiny awaits.')}           
║                                               ║
║  This is the map laid out before you.         ║
║  Other players will emerge from this darkness.║
║  Be warned. War is coming.                    ║
║                                               ║
║  Type `/profile` to see your empire.          ║
║  Type `/obelisk` to explore further into      ║
║  this dimension.                              ║
║                                               ║
╚═══════════════════════════════════════════════╝
"""
        await message.answer(msg, parse_mode="Markdown")
        
    except Exception as e:
        print(f"[ERROR] Failed to create base for {u_id}: {e}")
        import traceback
        traceback.print_exc()
        await message.answer(f"❌ Error creating base: {str(e)[:100]}", parse_mode="Markdown")


@dp.message(_cmd("changebasename"))
async def cmd_changebasename(message: types.Message):
    if message.chat.type != "private":
        await _send_access_denied_sticker(message); return
    
    u_id = str(message.from_user.id)
    user = get_user(u_id)
    
    if not user:
        await _send_unreg_sticker(message); return
    
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
        await _send_access_denied_sticker(message); return
    
    u_id = str(message.from_user.id)
    user = get_user(u_id)
    
    if not user:
        await _send_unreg_sticker(message); return
    
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
    
    txt = f"{divider()}\n🔬 *SCIENCE LABORATORY* 🔬\n{divider()}\n\n*AVAILABLE UPGRADES:*\n\n"
    
    rows = []
    for key, research in researches.items():
        if user_researches.get(key):
            txt += f"✅ *{research['name']}* — _(UNLOCKED)_\n"
        else:
            cost_str = " + ".join([f"*{v}* {k.title()}" for k, v in research['cost'].items()])
            txt += f"⬜ *{research['name']}*\n├─ Cost: {cost_str}\n└─ Effect: _{research['desc']}_\n\n"
            rows.append([InlineKeyboardButton(text=f"🔎 Research {research['name'].split()[0]}", 
                                            callback_data=f"research_{key}")])
    
    txt += f"\n{divider()}\n🃏 *GameMaster:* \"Invest in power. Or remain weak. Entropy cares not.\"\n{divider()}" 
    
    if rows:
        await message.answer(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="Markdown")
    else:
        await message.answer(txt + "\n\n*All researches unlocked!*", parse_mode="Markdown")


@dp.message(_cmd("shield"))
async def cmd_shield_status(message: types.Message):
    """Check current shield status."""
    if message.chat.type != "private":
        await message.answer("🃏 *GameMaster:* \"Check your shield status and all in *private* lackey.\"", parse_mode="Markdown"); return
    
    u_id = str(message.from_user.id)
    user = get_user(u_id)
    if not user:
        await _send_unreg_sticker(message); return
    
    shield_status = user.get('shield_status', '⚠️ UNPROTECTED')
    
    status_info = {
        '⚠️ UNPROTECTED': ("⚠️ UNPROTECTED", "Your base is vulnerable to attacks. Activate a shield now!"),
        '🛡️ ACTIVE': ("🛡️ ACTIVE", "Your base is protected from attacks."),
        '💥 DISRUPTED': ("💥 DISRUPTED", "Your shield was hit! It will auto-restore to ACTIVE after the next attack.")
    }

    
    emoji, description = status_info.get(shield_status, ("❓", "Unknown status"))
    
    txt = f"{divider()}\n🛡️ *YOUR SHIELD STATUS* 🛡️\n{divider()}\n\n"
    txt += f"Status: {emoji} *{shield_status}*\n\n"
    txt += f"ℹ️ {description}\n\n"
    
    if shield_status == '⚠️ UNPROTECTED':
        txt += "*Available Actions:*\n"
        txt += "• `/activateshield` - Activate the shield you have in your inventory\n"
        txt += "• `/battle_items` - Buy shield items\n"
        txt += "• `/name_shield` - Check name shield\n\n"
    elif shield_status == '🛡️ ACTIVE':
        txt += "*Available Actions:*\n"
        txt += "• `/deactivateshield` - Deactivate your shield\n"
        txt += "• `/name_shield_status` - Check name shield\n"
        txt += "• Attack other players fearlessly!\n\n"
    elif shield_status == '💥 DISRUPTED':
        txt += "*What to do:*\n"
        txt += "Wait for the next attack. Your shield will auto-restore to ACTIVE.\n"
        txt += "• `/name_shield_status` - Check name shield\n\n"
    
    txt += f"{divider()}"
    
    await message.answer(txt, parse_mode="Markdown")


@dp.message(_cmd("activateshield"))
async def cmd_activate_shield(message: types.Message):
    """Activate shield with 24-hour cooldown between activations."""
    if message.chat.type != "private":
        await _send_access_denied_sticker(message); return
    
    u_id = str(message.from_user.id)
    ok, msg = activate_shield(u_id)
    
    if ok:
        await message.answer(f"🛡️ {msg}", parse_mode="Markdown")
    else:
        await message.answer(f"⚠️ 🃏 *GameMaster:* \"{msg}\"", parse_mode="Markdown")


@dp.message(_cmd("deactivateshield"))
async def cmd_deactivate_shield(message: types.Message):
    """Deactivate shield and start 24-hour cooldown before re-activation."""
    if message.chat.type != "private":
        await _send_access_denied_sticker(message); return
    
    u_id = str(message.from_user.id)
    ok, msg = deactivate_shield(u_id)
    
    if ok:
        await message.answer(f"{msg}", parse_mode="Markdown")
    else:
        await message.answer(f"⚠️ 🃏 *GameMaster:* \"{msg}\"", parse_mode="Markdown")


@dp.message(_cmd("disruptor"))
async def cmd_use_disruptor(message: types.Message):
    """Use disruptor item to break enemy shield for 1 attack."""
    if message.chat.type != "private":
        await _send_access_denied_sticker(message); return
    
    # Parse target
    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("🃏 *GameMaster:* \"Usage: `!disruptor @username`\"", parse_mode="Markdown"); return
    
    target_mention = parts[1]
    u_id = str(message.from_user.id)
    
    # Check inventory for disruptor
    inv = get_inventory(u_id)
    disruptor_item = next((i for i in inv if i.get('item_type') == 'shield_disruptor'), None)
    
    if not disruptor_item:
        await message.answer("🃏 *GameMaster:* \"You have no disruptors. Use `!shop` to buy one.\"", parse_mode="Markdown"); return
    
    # TODO: Resolve target username/mention to user_id
    # For now, placeholder response
    await message.answer(
        "🔥 *Disruptor activated!*\n"
        "Target's shield has been disrupted for their next incoming attack.\n\n"
        "_Phase 2B will implement full attack system._",
        parse_mode="Markdown"
    )


@dp.message(_cmd("base"))
async def cmd_base(message: types.Message):
    if message.chat.type != "private":
        await _send_access_denied_sticker(message); return
    
    u_id = str(message.from_user.id)
    user = get_user(u_id)
    
    if not user:
        await _send_unreg_sticker(message); return
    
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
        "Police and Dogs": ("👹 Police and Dogs", 1),
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
    
    military_str = "\n".join(military_lines) if military_lines else "├─ 👹 Police and Dogs: 0"
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
    military_power = sum(military.values()) * 50
    base_power = base_level * 1111
    total_power = military_power + base_power
    
    # Get sector
    sector = user.get("sector", "Unknown")
    
    # Build comprehensive base info with dynamic formatting
    info = (
        f"{divider()}\n"
        f"🏰 {user.get('base_name', 'Unnamed base')} (Level {base_level})\n"
        f"{divider()}\n\n"
        f"⚡️ POWER: {total_power} | 🎖️ WAR POINTS: {war_points}\n"
        f"📍 SECTOR: {sector}\n\n"
        f"{divider()}\n\n"
        f"🪵 *RESOURCES*\n"
        f"├─ 🌲 Wood: *{resources.get('wood', 0)}*\n"
        f"├─ 🧱 Bronze: *{resources.get('bronze', 0)}*\n"
        f"├─ ⛓️ Iron: *{resources.get('iron', 0)}*\n"
        f"├─ 💎 Diamond: *{resources.get('diamond', 0)}*\n"
        f"├─ 🏺 Relics: *{resources.get('relics', 0)}*\n"
        f"└─ 🌽 Food: *{food}*\n\n"
        f"⚔️ *MILITARY* ({total_troops} troops)\n"
        f"{military_str}\n\n"
        f"🔱 *DEFENSIVE TRAPS*\n"
        f"{traps_str}\n\n"
        f"✨ *ACTIVE BUFFS*\n"
        f"└─ {buffs_str}\n\n"
        f"👥 *ALLIANCE*\n"
        f"└─ {alliance_str}\n\n"
        f"⚔️ *BATTLE RECORD*\n"
        f"├─ Wins: *{wins}* 🏆\n"
        f"├─ Losses: *{losses}* ⚰️\n"
        f"├─ Kings Captured: *{kings_captured}* 👑\n"
        f"└─ Times Captured: *{times_captured}* 🔒\n\n"
        f"{divider()}\n"
        f"🃏 *GameMaster:* \"Your fortress. Fragile as it may be.\""
    )
    
    await message.answer(info, parse_mode="Markdown")


@dp.message(_cmd("build"))
async def cmd_build(message: types.Message):
    """Build structures inside your base for bonuses."""
    if message.chat.type != "private":
        await _send_access_denied_sticker(message)
        return
    
    u_id = str(message.from_user.id)
    user = get_user(u_id)
    
    if not user:
        await _send_unreg_sticker(message)
        return
    
    if not user.get("base_name"):
        await message.answer("🏰 *GameMaster:* \"You have no base. Use `!setup_base [sector] [name]` first.\"", parse_mode="Markdown")
        return
    
    # Calculate base level
    xp = user.get("xp", 0)
    base_level = max(1, 1 + (xp // 1000))
    
    # Parse command: !build [building_name]
    args = message.text.strip().split(maxsplit=1)
    
    if len(args) < 2:
        # Show menu
        current_buildings = user.get("buildings", {})
        menu = format_buildings_menu(base_level, current_buildings)
        await message.answer(menu, parse_mode="Markdown")
        return
    
    building_name = args[1].lower().replace(" ", "_").replace("-", "_")
    
    # Check if building exists
    can_build, error_msg = can_build_building(building_name, base_level)
    if not can_build:
        await message.answer(f"❌ {error_msg}", parse_mode="Markdown")
        return
    
    # Get current buildings
    buildings = user.get("buildings", {})
    current_level = buildings.get(building_name, 0)
    
    # Calculate cost for next level
    cost = calculate_building_cost(building_name, current_level + 1)
    
    # Check if player has resources
    base_res = user.get("base_resources", {})
    if isinstance(base_res, str):
        import json as json_lib
        try:
            base_res = json_lib.loads(base_res)
        except:
            base_res = {}
    
    resources = base_res.get("resources", {})
    
    for resource, amount in cost.items():
        if resources.get(resource, 0) < amount:
            await message.answer(
                f"❌ Insufficient {resource}!\n"
                f"Need: {amount}\n"
                f"Have: {resources.get(resource, 0)}",
                parse_mode="Markdown"
            )
            return
    
    # Deduct resources and build
    for resource, amount in cost.items():
        resources[resource] = resources.get(resource, 0) - amount
    
    buildings[building_name] = current_level + 1
    
    base_res["resources"] = resources
    user["buildings"] = buildings
    user["base_resources"] = base_res
    
    save_user(u_id, user)
    
    building_info = BUILDING_TYPES.get(building_name, {})
    
    await message.answer(
        f"✅ **CONSTRUCTION COMPLETE!**\n\n"
        f"{building_info.get('name', building_name)}\n"
        f"Level: {buildings[building_name]}\n\n"
        f"*Bonus:* {building_info.get('description', 'N/A')}\n\n"
        f"🃏 *GameMaster:* \"Your infrastructure grows stronger. The game notices.\"",
        parse_mode="Markdown"
    )


@dp.message(_cmd("scout"))
async def cmd_scout(message: types.Message):
    """Scout a target player to reveal their army and traps."""
    if message.chat.type != "private":
        await message.answer("🛰️ *GM:* \"Scouts use private channels. Run this in DM, fool.\"", parse_mode="Markdown")
        return
    
    u_id = str(message.from_user.id)
    scout_user = get_user(u_id)
    if not scout_user:
        await _send_unreg_sticker(message)
        return
    
    # Parse command: !scout @username or !scout user_id
    args = message.text.strip().split()
    if len(args) < 2:
        await message.answer(
            "[🛰️ *SCOUT COMMAND* ]\n\n"
            "Cost: 100 Bitcoin\n"
            "Success Rate: 70% \n\n"
            "Usage: Just type `/scout @username` or `!scout <name>`, without the brackets <> or quotes ''\n\n"
            "Reveals enemy army and traps if successful, if unsuccessful alerts eenemy of your location.\n",
            parse_mode="Markdown"
        )
        return
    
    target_name = args[1].lstrip("@")
    
    # Find target player
    from supabase_db import supabase, DB_TABLE
    try:
        r = supabase.table(DB_TABLE).select("user_id, username, military, traps, sector").ilike("username", f"%{target_name}%").limit(1).execute()
        if not r.data:
            await message.answer(f"🔍 *GM:* \"No player named '{target_name}' found.\"", parse_mode="Markdown")
            return
        target_id = r.data[0]["user_id"]
        target_display_name = r.data[0].get("username", target_name)
        target_sector = r.data[0].get("sector")
        
    except Exception as e:
        await message.answer(f"🔍 *GM:* \"Scout query failed: {str(e)[:50]}\"", parse_mode="Markdown")
        return
    
    # Check bitcoin cost
    scout_cost = 100
    scout_bitcoin = scout_user.get("bitcoin", 0)
    if scout_bitcoin < scout_cost:
        await message.answer(
            f"❌ Insufficient bitcoin!\n"
            f"Cost: {scout_cost} bitcoin\n"
            f"You have: {scout_bitcoin} bitcoin",
            parse_mode="Markdown"
        )
        return
    
    # Can't scout self
    if target_id == u_id:
        await message.answer("🛰️ *GM:* \"You can't scout yourself, fool.\"", parse_mode="Markdown")
        return
    
    # ═══════════════════════════════════════════════════════════════════════════
    #  NAME SHIELD CHECK — Can't scout if target has active name shield
    # ═══════════════════════════════════════════════════════════════════════════
    from datetime import datetime
    target = get_user(target_id)
    name_shield_until = target.get("name_shield_until")
    if name_shield_until:
        try:
            expiry = datetime.fromisoformat(name_shield_until)
            if datetime.now() < expiry:
                await message.answer(
                    f"🛰️ *SCOUT BLOCKED*\n\n"
                    f"This player has activated a **Name Shield**!\n\n"
                    f"🔐 Your scout cannot locate them. Intelligence is unavailable.\n"
                    f"Try scouting someone else.",
                    parse_mode="Markdown"
                )
                return
        except:
            pass
    
    # Deduct bitcoin
    scout_user["bitcoin"] = scout_bitcoin - scout_cost
    save_user(u_id, scout_user)
    
    # 70% success chance
    success = random.random() < 0.7
    
    if success:
        # Get target's military and traps
        target = get_user(target_id)
        if not target:
            await message.answer("❌ Target no longer exists.", parse_mode="Markdown")
            return
        
        military = target.get("military", {})
        traps = target.get("traps", {})
        
        report = f"""
╔═══════════════════════════════════════╗
║     📸  SCOUT REPORT  📸             ║
╠═══════════════════════════════════════╣
║                                       ║
║  Target: **{target_display_name}**    ║
||  📍 Sector: {target_sector}         ||             
║  Level: {target.get('level', '?')}    ║            
║  Bitcoin: {target.get('bitcoin', 0):,}║              
║                                       ║
║ 🎖️ MILITARY:                                      
"""
        if military:
            for unit_type, count in military.items():
                report += f"║  {unit_type}: {count}\n"
        else:
            report += "║     (No troops)\n"
        
        report += f"""║                           ║
║  🕳️ TRAPS:                                        
"""
        if traps:
            for trap_type, count in traps.items():
                report += f"║  {trap_type}: {count}\n"
        else:
            report += "║    (No traps)\n"
        
        report += """║                     ║
║  ✅ Scout returned safely with intel!   ║        
║                                          ║         
╚══════════════════════════════════════════╝
"""
    else:
        # Failed - honeypot triggered
        report = f"""
╔═════════════════════════════════════════╗
║     ❌  SCOUT HONEYPOT  ❌             ║
╠═════════════════════════════════════════╣
║                                         ║
║  Your scout was detected!               ║
║                                         ║
║  {target_display_name} now knows you    ║
║           spied on them                 ║
║                                         ║
||  🚨 WARNING: They may retaliate!      ||
║                                         ║
╚═════════════════════════════════════════╝
"""
    
    await message.answer(report, parse_mode="Markdown")


@dp.message(_cmd("revenge"))
async def cmd_revenge(message: types.Message):
    """Execute revenge attack on the player who raided you. 1.5x damage for 24h window."""
    if message.chat.type != "private":
        await message.answer("💀 *GM:* \"Settle your grudges in private, coward.\"", parse_mode="Markdown")
        return
    
    u_id = str(message.from_user.id)
    player = get_user(u_id)
    if not player:
        await _send_unreg_sticker(message)
        return
    
    # Check if player has active revenge debt
    from revenge_system import get_revenge_info, clear_revenge
    revenge = get_revenge_info(u_id)
    
    if not revenge["active"]:
        await message.answer(
            "💀 *GM:* \"You have no Blood Debts to settle.\"\n\n"
            "_Get raided first. Then you can take revenge._",
            parse_mode="Markdown"
        )
        return
    
    target_id = revenge["target_id"]
    target_name = revenge["target_name"]
    target_player = get_user(target_id)
    
    if not target_player:
        await message.answer("💀 *GM:* \"Your target has been deleted from existence. Revenge unavailable.\"", parse_mode="Markdown")
        return
    
    # Execute revenge attack with 1.5x buff
    # For now, placeholder - full attack system will integrate this
    await message.answer(
        f"🔥 **BLOOD DEBT ACTIVATED**\n\n"
        f"Target: *{target_name}*\n"
        f"Multiplier: *1.5x* damage\n"
        f"Window: *24 hours*\n\n"
        f"_Full attack system coming Phase 2C._\n\n"
        f"To attack: Use `!attack @{target_name}` (1.5x multiplier applied automatically)",
        parse_mode="Markdown"
    )
    # NOTE: clear_revenge() will be called when attack succeeds


@dp.message(_cmd("attack"))
async def cmd_attack(message: types.Message):
    """Attack another player's base. Steal 50% of their resources if you win.
    If attacker has ACTIVE shield, ask for confirmation before deactivating it."""
    if message.chat.type != "private":
        await message.answer("⚔️ *GM:* \"Conduct raids in private, coward.\"", parse_mode="Markdown")
        return
    
    u_id = str(message.from_user.id)
    attacker = get_user(u_id)
    if not attacker:
        await _send_unreg_sticker(message)
        return
    
    # Check if attacker has troops
    attacker_army = attacker.get("military", {})
    total_troops = sum(attacker_army.values()) if attacker_army else 0
    
    if total_troops == 0:
        await message.answer(
            "⚔️ *GM:* \"You have no troops to command.\"\n\n"
            "_Use !train to raise an army first._",
            parse_mode="Markdown"
        )
        return
    
    # Parse target: !attack @username or !attack username
    args = message.text.strip().split()
    if len(args) < 2:
        await message.answer(
            "⚔️ *ATTACK COMMAND*\n\n"
            "Usage: `!attack @username`\n\n"
            "_Success depends on both armies. Attacker takes losses too._\n"
            "_Victory = steal 50% of resources._\n"
            "_Defeat on a raid earns a revenge window for your opponent._",
            parse_mode="Markdown"
        )
        return
    
    target_name = args[1].lstrip("@")
    
    # Find target player
    from supabase_db import supabase, DB_TABLE
    try:
        r = supabase.table(DB_TABLE).select("user_id, username, military, base_resources, sector").ilike(
            "username", f"%{target_name}%"
        ).limit(1).execute()
        if not r.data:
            await message.answer(f"🔍 *GM:* \"No player named '{target_name}' found.\"", parse_mode="Markdown")
            return
        target_id = r.data[0]["user_id"]
        target_display_name = r.data[0].get("username", target_name)
        target_sector = r.data[0].get("sector")
    except Exception as e:
        await message.answer(f"🔍 *GM:* \"Attack query failed: {e}\"", parse_mode="Markdown")
        return
    
    # Can't attack self
    if target_id == u_id:
        await message.answer("⚔️ *GM:* \"You can't attack yourself, fool.\"", parse_mode="Markdown")
        return
    
    # ═══════════════════════════════════════════════════════════════════════════
    #  NAME SHIELD CHECK — Can't attack if target has active name shield
    # ═══════════════════════════════════════════════════════════════════════════
    from datetime import datetime
    target = get_user(target_id)
    name_shield_until = target.get("name_shield_until")
    if name_shield_until:
        try:
            expiry = datetime.fromisoformat(name_shield_until)
            if datetime.now() < expiry:
                await message.answer(
                    f"🔐 *ATTACK BLOCKED*\n\n"
                    f"This player has activated a **Name Shield** and cannot be targeted!\n\n"
                    f"🛡️ Their identity is protected for now.\n"
                    f"Try attacking someone else.",
                    parse_mode="Markdown"
                )
                return
        except:
            pass
    
    # ═══════════════════════════════════════════════════════════════════════════
    #  SECTOR VALIDATION — Can only attack same sector
    # ═══════════════════════════════════════════════════════════════════════════
    
    attacker_sector = attacker.get("sector")
    if attacker_sector != target_sector:
        await message.answer(
            f"⚔️ *GM:* \"You stand in SECTOR {attacker_sector}, but {target_display_name} inhabits SECTOR {target_sector}.\"\n\n"
            f"📍 *Cross-sector attacks are forbidden.*\n\n"
            f"_You must use !teleport to move to their sector, or find them in the lands you walk._\n\n"
            f"Cost: {500 if target_sector != attacker_sector else 0} Bitcoin to teleport",
            parse_mode="Markdown"
        )
        return
    
    # ═══════════════════════════════════════════════════════════════════════════
    #  OFFER SCOUTING OPTION BEFORE ATTACK
    # ═══════════════════════════════════════════════════════════════════════════
    
    # Show pre-attack options
    options_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🕵️ Scout First (100💰)", callback_data=f"scout_before_attack_{u_id}_{target_id}"),
            InlineKeyboardButton(text="⚔️ Attack Now", callback_data=f"direct_attack_{u_id}_{target_id}"),
        ]
    ])
    
    await message.answer(
        f"🎯 *ATTACK PREPARATION* 🎯\n\n"
        f"Target: **{target_display_name}**\n\n"
        f"*OPTIONS:*\n"
        f"🕵️ *Scout First* - Send scout rat (5 min) to see their base stats\n"
        f"   Cost: 100 Bitcoin | Intel: Military, resources, level, shield\n"
        f"   Risk: 30% chance scout lies, mousetraps, firewall\n\n"
        f"⚔️ *Attack Now* - Assault blindly without intel",
        reply_markup=options_kb,
        parse_mode="Markdown"
    )


@dp.callback_query(F.data.startswith("scout_before_attack_"))
async def cb_scout_before_attack(callback: types.CallbackQuery):
    """Launch scout mission before attack."""
    try:
        parts = callback.data.split("_")
        attacker_id = parts[3]
        target_id = parts[4]
        user_id = str(callback.from_user.id)
        
        if user_id != attacker_id:
            await callback.answer("❌ This isn't your action!", show_alert=True)
            return
        
        attacker = get_user(attacker_id)
        target = get_user(target_id)
        
        if not attacker or not target:
            await callback.answer("❌ Player not found.", show_alert=True)
            return
        
        target_name = target.get("username", "Unknown")
        
        # Launch scout
        result = scout_player_advanced(attacker_id, target_id, target_name)
        
        if not result.get("success"):
            await callback.message.edit_text(
                f"❌ *SCOUT FAILED*\n\n{result.get('message', 'Unknown error')}",
                parse_mode="Markdown"
            )
            return
        
        # Scout sent successfully
        scout_id = result.get("scout_id")
        returns_at_str = result.get("returns_at")
        
        await callback.message.edit_text(
            f"🐀 *SCOUT RAT DEPLOYED* 🐀\n\n"
            f"Target: **{target_name}**\n"
            f"Status: En route to base\n"
            f"Duration: 5 minutes\n\n"
            f"Your scout rat is scurrying toward the target...\n"
            f"⏱️ Returns at: {returns_at_str}\n\n"
            f"💭 *Remember:*\n"
            f"• 30% chance scout will lie\n"
            f"• Target may have set mousetraps (70% escape)\n"
            f"• Target may have firewall (50% kill rate)\n"
            f"• Use multiple scouts to verify intel!\n\n"
            f"• Target may use fake stats!\n\n"
            f"_Scout mission ID: {scout_id}_",
            parse_mode="Markdown"
        )
        
        # Store for later retrieval
        attacker["pending_scout_missions"] = attacker.get("pending_scout_missions", [])
        attacker["pending_scout_missions"].append({
            "id": scout_id,
            "target_id": target_id,
            "target_name": target_name
        })
        save_user(attacker_id, attacker)
        
        await callback.answer("🐀 Scout sent! Check back in 5 minutes.")
        
    except Exception as e:
        print(f"[CB_SCOUT_BEFORE_ATTACK ERROR] {e}")
        await callback.answer(f"❌ Error: {str(e)[:50]}", show_alert=True)


@dp.callback_query(F.data.startswith("direct_attack_"))
async def cb_direct_attack(callback: types.CallbackQuery):
    """Proceed with attack without scouting."""
    try:
        parts = callback.data.split("_")
        attacker_id = parts[2]
        target_id = parts[3]
        user_id = str(callback.from_user.id)
        
        if user_id != attacker_id:
            await callback.answer("❌ This isn't your action!", show_alert=True)
            return
        
        attacker = get_user(attacker_id)
        target = get_user(target_id)
        
        if not attacker or not target:
            await callback.answer("❌ Player not found.", show_alert=True)
            return
        
        target_name = target.get("username", "Unknown")
        
        # CHECK SHIELD STATUS
        attacker_shield = attacker.get('shield_status', '⚠️ UNPROTECTED')
        if attacker_shield == '🛡️ ACTIVE':
            # Ask for confirmation
            confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="⚔️ Yes, Attack!", callback_data=f"confirm_attack_{attacker_id}_{target_id}"),
                    InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_attack")
                ]
            ])
            
            await callback.message.edit_text(
                f"⚠️ *SHIELD DEACTIVATION WARNING* ⚠️\n\n"
                f"You have an *ACTIVE shield* protecting your base.\n\n"
                f"*Attacking {target_name} will deactivate your shield.*\n\n"
                f"Are you sure you want to proceed?",
                reply_markup=confirm_kb,
                parse_mode="Markdown"
            )
            return
        
        # No shield or shield not ACTIVE - proceed with attack
        await _execute_attack(attacker_id, target_id, target_name, callback.message)
        await callback.answer()
        
    except Exception as e:
        print(f"[CB_DIRECT_ATTACK ERROR] {e}")
        await callback.answer(f"❌ Error: {str(e)[:50]}", show_alert=True)


@dp.message(_cmd("scout_results"))
async def cmd_scout_results(message: types.Message):
    """Check scout mission results."""
    if message.chat.type != "private":
        await message.answer("🕵️ *GM:* \"Scout reports in *private*.\"", parse_mode="Markdown")
        return
    
    u_id = str(message.from_user.id)
    user = get_user(u_id)
    if not user:
        await message.answer("❌ Account not found.", parse_mode="Markdown")
        return
    
    pending_scouts = user.get("pending_scout_missions", [])
    
    if not pending_scouts:
        await message.answer(
            "[🐀 *NO ACTIVE SCOUTS*]\n\n"
            "You have no active scout missions.\n"
            "Use `!attack @player` then select *Scout First* option.",
            parse_mode="Markdown"
        )
        return
    
    # Show list of pending scouts
    txt = "🐀 *SCOUT MISSIONS* 🐀\n\n"
    
    for idx, scout in enumerate(pending_scouts, 1):
        scout_id = scout.get("id")
        target_name = scout.get("target_name", "Unknown")
        txt += f"{idx}. Scout sent to **{target_name}**\n"
        txt += f"   Details: `/scout_check {scout_id}`\n\n"
    
    await message.answer(txt, parse_mode="Markdown")


@dp.message(_cmd("scout_check"))
async def cmd_scout_check(message: types.Message):
    """Check results of a specific scout mission."""
    if message.chat.type != "private":
        await message.answer("🕵️ *GM:* \"Scout reports in *private*.\"", parse_mode="Markdown")
        return
    
    u_id = str(message.from_user.id)
    user = get_user(u_id)
    if not user:
        await message.answer("❌ Account not found.", parse_mode="Markdown")
        return
    
    # Parse scout ID
    args = message.text.strip().split()
    if len(args) < 2:
        await message.answer(
            "[🐀 *SCOUT CHECK*]\n\n"
            "Usage: `/scout_check [scout_id]`\n\n"
            "Use `/scout_results` to see all active scouts.",
            parse_mode="Markdown"
        )
        return
    
    scout_id = args[1]
    
    # Check scout return
    result = check_scout_return(u_id, scout_id)
    
    await message.answer(result.get("message", "Scout check failed"), parse_mode="Markdown")
    
    # If completed, show attack option
    if result.get("status") == "completed":
        completed_scouts = user.get("pending_scout_missions", [])
        target_scout = next((s for s in completed_scouts if s["id"] == scout_id), None)
        
        if target_scout:
            target_id = target_scout.get("target_id")
            target_name = target_scout.get("target_name")
            
            attack_kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="⚔️ Attack Now!", callback_data=f"direct_attack_{u_id}_{target_id}"),
                    InlineKeyboardButton(text="🕵️ Send Another Scout", callback_data=f"scout_before_attack_{u_id}_{target_id}"),
                ]
            ])
            
            await message.answer(
                f"\n*READY TO ATTACK?*\n"
                f"Target: **{target_name}**\n\n"
                f"Now you have intel. Attack with confidence!",
                reply_markup=attack_kb,
                parse_mode="Markdown"
            )


@dp.message(_cmd("defenses"))
async def cmd_defenses(message: types.Message):
    """Configure base defenses (mousetraps, firewall, fake stats)."""
    if message.chat.type != "private":
        await message.answer("🛡️ *GM:* \"Configure defenses in *private*.\"", parse_mode="Markdown")
        return
    
    u_id = str(message.from_user.id)
    user = get_user(u_id)
    if not user:
        await message.answer("❌ Account not found.", parse_mode="Markdown")
        return
    
    # Show defense menu
    defense_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🪤 MouseTraps", callback_data="defense_mousetraps"),
            InlineKeyboardButton(text="🔥 Firewall", callback_data="defense_firewall"),
        ],
        [
            InlineKeyboardButton(text="💭 Fake Stats", callback_data="defense_fake_stats"),
            InlineKeyboardButton(text="📊 View Status", callback_data="defense_status"),
        ]
    ])
    
    txt = f"🛡️ *BASE DEFENSE CONFIGURATION* 🛡️\n\n"
    txt += f"*DEFENSE OPTIONS:*\n\n"
    txt += f"🪤 *MouseTraps*: Catch incoming scouts (30% success, 70% escape)\n"
    txt += f"   Cost: Items from inventory\n\n"
    txt += f"🔥 *Firewall*: Incinerate scouts with fireball (50% hit rate)\n"
    txt += f"   Cost: 1 Fireball item | Duration: 1 hour\n\n"
    txt += f"💭 *Fake Stats*: Show false intel to scouts\n"
    txt += f"   Manually edit what scouts see\n"
    txt += f"   Cost: Deception item\n"
    
    await message.answer(txt, reply_markup=defense_kb, parse_mode="Markdown")


@dp.callback_query(F.data == "defense_mousetraps")
async def cb_defense_mousetraps(callback: types.CallbackQuery):
    """Set mousetraps."""
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    
    if not user:
        await callback.answer("❌ User not found.", show_alert=True)
        return
    
    # Get available traps from inventory
    inventory = user.get("inventory", [])
    traps_available = sum(1 for item in inventory if "trap" in item.get("type", "").lower())
    
    await callback.message.edit_text(
        f"🪤 *MOUSETRAP DEFENSE*\n\n"
        f"Set traps to catch incoming scouts.\n\n"
        f"⚙️ How many traps to set?\n"
        f"Available traps: {traps_available}\n\n"
        f"Reply with a number: `/traps 3`",
        parse_mode="Markdown"
    )


@dp.message(_cmd("traps"))
async def cmd_set_traps(message: types.Message):
    """Set number of mousetraps."""
    if message.chat.type != "private":
        return
    
    u_id = str(message.from_user.id)
    user = get_user(u_id)
    if not user:
        await message.answer("❌ Account not found.", parse_mode="Markdown")
        return
    
    # Parse number
    args = message.text.strip().split()
    if len(args) < 2:
        await message.answer(
            "🪤 *SET MOUSETRAPS*\n\n"
            "Usage: `/traps [number]`\n"
            "Example: `/traps 5`",
            parse_mode="Markdown"
        )
        return
    
    try:
        trap_count = int(args[1])
        if trap_count < 0 or trap_count > 10:
            await message.answer("❌ You can only set a maximum of 10 mouse traps.", parse_mode="Markdown")
            return
    except ValueError:
        await message.answer("❌ Invalid number.", parse_mode="Markdown")
        return
    
    # Set traps
    set_mousetraps(u_id, trap_count)
    
    await message.answer(
        f"🪤 *Mouse traps have been set*: {trap_count}\n\n"
        f"✅ {trap_count} mousetraps are now active on your base.\n"
        f"Incoming scouts have a 30% chance of being caught.\n"
        f"(Scouts have 70% chance to escape)\n\n"
        f"Traps reset after catching a scout.",
        parse_mode="Markdown"
    )


@dp.callback_query(F.data == "defense_firewall")
async def cb_defense_firewall(callback: types.CallbackQuery):
    """Activate firewall."""
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    
    if not user:
        await callback.answer("❌ User not found.", show_alert=True)
        return
    
    # Check if they have firewall item
    inventory = user.get("inventory", [])
    has_fireball = any(item.get("type") == "fireball" for item in inventory)
    
    if not has_fireball:
        await callback.answer("❌ You need a Fireball item to activate firewall!", show_alert=True)
        return
    
    # Activate firewall
    activate_firewall(u_id)
    
    # Remove fireball from inventory
    inventory = [item for item in inventory if item.get("type") != "fireball"]
    user["inventory"] = inventory
    save_user(u_id, user)
    
    await callback.message.edit_text(
        f"🔥 *FIREWALL ACTIVATED* 🔥\n\n"
        f"✅ Your base is now protected by a firewall!\n"
        f"🔥 Fireball: 50% chance to incinerate incoming scouts\n"
        f"⏱️ Duration: 1 hour\n\n"
        f"After 1 hour, firewall deactivates automatically.",
        parse_mode="Markdown"
    )


@dp.callback_query(F.data == "defense_fake_stats")
async def cb_defense_fake_stats(callback: types.CallbackQuery):
    """Edit fake stats."""
    u_id = str(callback.from_user.id)
    
    await callback.message.edit_text(
        f"💭 *FAKE STATS EDITOR* 💭\n\n"
        f"Create false intel that scouts will see.\n\n"
        f"Edit your displayed stats using:\n"
        f"`/fake_stats [level] [troops] [wood] [bronze] [iron]`\n\n"
        f"Example:\n"
        f"`/fake_stats 25 500 1000 800 600`\n\n"
        f"This shows scouts you're level 25 with 500 troops\n"
        f"and the listed resources.",
        parse_mode="Markdown"
    )


@dp.message(_cmd("fake_stats"))
async def cmd_fake_stats(message: types.Message):
    """Set fake stats for scouts."""
    if message.chat.type != "private":
        return
    
    u_id = str(message.from_user.id)
    user = get_user(u_id)
    if not user:
        await message.answer("❌ Account not found.", parse_mode="Markdown")
        return
    
    # Parse arguments
    args = message.text.strip().split()
    if len(args) < 6:
        await message.answer(
            "💭 *FAKE STATS*\n\n"
            "Usage: `/fake_stats [level] [troops] [wood] [bronze] [iron]`\n\n"
            "Example: `/fake_stats 20 300 500 400 200`",
            parse_mode="Markdown"
        )
        return
    
    try:
        level = int(args[1])
        troops = int(args[2])
        wood = int(args[3])
        bronze = int(args[4])
        iron = int(args[5])
    except ValueError:
        await message.answer("❌ All values must be numbers.", parse_mode="Markdown")
        return
    
    # Set fake stats
    fake_data = {
        "level": level,
        "shield": "🛡️ ACTIVE",  # Always show as protected
        "military": {"Police and Dogs": troops // 2, "knights": troops // 4, "bishops": troops // 4},
        "resources": {
            "wood": wood,
            "bronze": bronze,
            "iron": iron,
            "diamond": 0,
            "relics": 0
        },
        "deception_chance": 0.85  # 85% of scouts see fake stats
    }
    
    set_displayed_stats(u_id, fake_data)
    
    await message.answer(
        f"💭 *FAKE STATS SET* 💭\n\n"
        f"✅ Scouts will see:\n"
        f"📊 Level: {level}\n"
        f"⚔️ Troops: {troops}\n"
        f"💰 Resources: {wood} wood, {bronze} bronze, {iron} iron\n"
        f"🛡️ Shield: 🛡️ ACTIVE (always shown)\n\n"
        f"85% of scouts will see your false data.\n"
        f"70% of scouts may bypass detection.\n\n"
        f"15% of scouts may bypass deception.\n\n"
        f"Use `/clear_fake_stats` to remove deceptive stats .",
        parse_mode="Markdown"
    )


@dp.message(_cmd("clear_fake_stats"))
async def cmd_clear_fake_stats(message: types.Message):
    """Clear fake stats."""
    if message.chat.type != "private":
        return
    
    u_id = str(message.from_user.id)
    clear_displayed_stats(u_id)
    
    await message.answer(
        f"💭 *FAKE STATS CLEARED* 💭\n\n"
        f"✅ Scouts will now see your actual base stats.",
        parse_mode="Markdown"
    )


async def _execute_attack(attacker_id: str, target_id: str, target_display_name: str, message: types.Message):
    """Execute the attack after all checks and confirmations."""
    attacker = get_user(attacker_id)
    
    # Deactivate attacker's shield if it's ACTIVE
    if attacker.get('shield_status') == '🛡️ ACTIVE':
        attacker['shield_status'] = '⚠️ UNPROTECTED'
        save_user(attacker_id, attacker)
    
    # Get revenge multiplier if applicable
    from revenge_system import get_revenge_multiplier, clear_revenge
    revenge_mult = get_revenge_multiplier(attacker_id, target_id)
    is_revenge = revenge_mult > 1.0
    
    # Execute battle
    from attack_system import calculate_battle_outcome, format_battle_report, format_raid_notification
    success, result = calculate_battle_outcome(attacker_id, target_id, revenge_mult)
    
    # Send battle report to attacker
    battle_report = format_battle_report(
        attacker.get("username", "Unknown"),
        target_display_name,
        result,
        is_revenge=is_revenge
    )
    await message.answer(battle_report, parse_mode="Markdown")
    
    # Send raid notification to defender (if they're in group)
    # Check if attacker has name shield - anonymize if active
    from datetime import datetime
    attacker_display_name = attacker.get("username", "Unknown")
    name_shield_until = attacker.get("name_shield_until")
    if name_shield_until:
        try:
            expiry = datetime.fromisoformat(name_shield_until)
            if datetime.now() < expiry:
                attacker_display_name = "[Anonymous Attacker]"
        except:
            pass
    
    raid_notif = format_raid_notification(
        attacker_display_name,
        target_display_name,
        result
    )
    
    try:
        # Send DM to defender about the raid
        await bot.send_message(
            int(target_id),
            raid_notif,
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"[ATTACK] Failed to send DM to defender {target_id}: {e}")
    
    # Broadcast to group if big victory
    if success:
        await broadcast(
            CHECKMATE_HQ_GROUP_ID,
            f"⚔️ **RAID REPORT**\n\n"
            f"🏆 {attacker_display_name} defeated {target_display_name}!\n"
            f"💎 Plunder: {result.get('total_loot_value', 0)} resources stolen"
        )
        
        # Clear revenge if this was a revenge attack
        if is_revenge:
            clear_revenge(attacker_id)
            await message.answer("\n✅ *Blood debt settled! Revenge cleared.*", parse_mode="Markdown")
    
    # Broadcast loss to group
    else:
        await broadcast(
            CHECKMATE_HQ_GROUP_ID,
            f"🛡️ **DEFENSE VICTORY**\n\n"
            f"🏆 {target_display_name} repelled {attacker.get('username', 'Unknown')}'s attack!\n"
            f"💀 Attacker lost {sum(result.get('attacker_losses', {}).values())} troops"
        )


@dp.chat_member()
async def handle_new_member(event: types.ChatMemberUpdated):
    """Auto-register new members when they join a group."""
    # Only process when someone joins a group
    if event.new_chat_member.status not in ["member", "restricted"]:
        return
    
    # Skip if the member is a bot
    if event.new_chat_member.user.is_bot:
        return
    
    user_id = str(event.new_chat_member.user.id)
    username = event.new_chat_member.user.first_name or event.new_chat_member.user.username or "Player"
    
    try:
        # Check if user exists
        existing_user = get_user(user_id)
        
        if not existing_user:
            # New member - register them
            reg_success = register_user(user_id, username)
            if reg_success:
                print(f"✅ [AUTO-JOIN-REGISTER] {username} ({user_id}) registered")
            else:
                print(f"❌ [AUTO-JOIN-REGISTER FAILED] Could not register {username} ({user_id})")
        else:
            # Already exists, just update name if missing
            if not existing_user.get('username') or existing_user.get('username') == "Player":
                existing_user['username'] = username
                save_user(user_id, existing_user)
                print(f"✅ [UPDATE] {user_id} username set to {username}")
    except Exception as e:
        print(f"❌ [AUTO-REGISTER ERROR] {user_id}: {e}")
        import traceback
        traceback.print_exc()

def register_new_user(user_id, first_name):
    new_user = {
        "id": str(user_id),
        "username": first_name or "Player",
        "level": 1,
        "xp": 0,
        "bitcoin": 100,
        "shield_status": "🛡️ ACTIVE",
        "unclaimed_items": {},
        "completed_tutorial": False,
        "game_saves": {} # Initialize this as an empty dict
    }
    save_user(user_id, new_user)
    return new_user

@dp.message(_cmd("start"))
async def cmd_start(message: types.Message):
    """
    COMMAND CENTER — the single entry point for all bot interaction.
    Works in group AND private. In group: sends DM link. In private: full HUD.
    """
    u_id = str(message.from_user.id)

    # In group chat: just nudge them to DM
    if message.chat.type in ("group", "supergroup"):
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🃏 Open Command Center", url=f"https://t.me/{(await bot.get_me()).username}?start=hq")
        ]])
        await message.reply(
            "🃏 <b>GameMaster:</b> <i>Your Command Center awaits in private.</i>",
            parse_mode="HTML", reply_markup=kb
        )
        return

    # Private chat — full HUD
    user = get_user(u_id)
    if user is None:
        user = register_new_user(u_id, message.from_user.first_name)

    username   = _safe_name(user.get("username") or message.from_user.first_name or "Operative")
    level      = user.get("level", 1)
    xp         = user.get("xp", 0)
    bitcoin    = user.get("bitcoin", 0)
    sector     = user.get("sector", "—")
    base_name  = user.get("base_name") or "No Base"
    shield_st  = user.get("shield_status") or "⚠️ UNPROTECTED"  # guard against None from DB
    unclaimed_raw = user.get("unclaimed_items", [])
    unclaimed  = len(unclaimed_raw) if isinstance(unclaimed_raw, list) else 0
    inv_raw    = user.get("inventory", [])
    inv_count  = len(inv_raw) if isinstance(inv_raw, list) else 0
    inv_slots  = user.get("backpack_slots", 5)
    xp_bar_pct = min(100, int((xp % 100)))
    filled     = xp_bar_pct // 10
    xp_bar     = "█" * filled + "░" * (10 - filled)

    shield_icon = "🛡️" if "ACTIVE" in shield_st else ("💥" if "DISRUPTED" in shield_st else "⚠️")
    claims_warn = f"  ⚡ <b>{unclaimed} UNCLAIMED</b>" if unclaimed > 0 else ""

    hud = (
        f"╔═══════════════════════════╗\n"
        f"║  🃏  <b>CHECKMATE HQ</b>  🃏  ║\n"
        f"╠═══════════════════════════╣\n"
        f"║  👤 <b>{username[:18]}</b>\n"
        f"║  ⭐ Level <b>{level}</b>   💰 <b>{bitcoin:,}</b> BTC\n"
        f"║  [{xp_bar}] {xp_bar_pct}%\n"
        f"║  📍 Sector: <b>{sector}</b>\n"
        f"║  🏰 <b>{base_name[:20]}</b>\n"
        f"║  {shield_icon} Shield: <b>{shield_st}</b>\n"
        f"║  🎒 Inv: <b>{inv_count}/{inv_slots}</b>{claims_warn}\n"
        f"╚═══════════════════════════╝"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👤 Profile",    callback_data="menu_profile"),
            InlineKeyboardButton(text="🏰 My Base",    callback_data="menu_base"),
        ],
        [
            InlineKeyboardButton(text="🎒 Inventory",  callback_data="menu_inventory"),
            InlineKeyboardButton(text="🎁 Claims",     callback_data="menu_claims"),
        ],
        [
            InlineKeyboardButton(text="🛍️ Shop",       callback_data="menu_shop"),
            InlineKeyboardButton(text="⚔️ Battle",     callback_data="menu_battle"),
        ],
        [
            InlineKeyboardButton(text="🏆 Leaderboards", callback_data="menu_leaderboards"),
            InlineKeyboardButton(text="🗺️ Map/Sectors",  callback_data="menu_map"),
        ],
        [
            InlineKeyboardButton(text="🧬 Research Lab", callback_data="menu_research"),
            InlineKeyboardButton(text="⚙️ Account",      callback_data="menu_account"),
        ],
        [
            InlineKeyboardButton(text="🎮 Fusion Game",  callback_data="menu_fusion_info"),
            InlineKeyboardButton(text="🧠 Trivia Game",  callback_data="menu_trivia_info"),
        ],
    ])

    await message.answer(hud, parse_mode="HTML", reply_markup=kb)


@dp.callback_query(lambda q: q.data == "menu_leaderboards")
async def cb_menu_leaderboards(callback: types.CallbackQuery):
    """Leaderboard hub — shows all game leaderboards with inline tabs."""
    await callback.answer()
    u_id = str(callback.from_user.id)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🃏 Fusion Weekly",   callback_data="lb_fusion_weekly"),
            InlineKeyboardButton(text="🃏 Fusion All-Time",  callback_data="lb_fusion_alltime"),
        ],
        [
            InlineKeyboardButton(text="🧠 Trivia Weekly",   callback_data="lb_trivia_weekly"),
            InlineKeyboardButton(text="🧠 Trivia All-Time",  callback_data="lb_trivia_alltime"),
        ],
        [
            InlineKeyboardButton(text="🏆 Overall Weekly",  callback_data="lb_overall_weekly"),
            InlineKeyboardButton(text="🏆 Overall All-Time", callback_data="lb_overall_alltime"),
        ],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="menu_back")],
    ])

    await callback.message.edit_text(
        "🏆 <b>LEADERBOARDS</b>\n━━━━━━━━━━━━━━━━━\n"
        "<i>Select a leaderboard to view:</i>",
        parse_mode="HTML", reply_markup=kb
    )


async def _render_leaderboard(game_type: str, scope: str) -> str:
    """Render a leaderboard as HTML text with shield status column."""
    medals = ["🥇", "🥈", "🥉"]

    # Fetch leaderboard data
    lb = []
    try:
        if game_type == "overall":
            lb = get_weekly_leaderboard(limit=10) if scope == "weekly" else get_alltime_leaderboard(limit=10)
        elif scope == "weekly":
            lb = get_game_weekly_leaderboard(game_type=game_type, limit=10)
        else:
            lb = get_game_alltime_leaderboard(game_type=game_type, limit=10)
    except Exception as e:
        # graceful fallback
        try:
            lb = get_weekly_leaderboard(limit=10) if scope == "weekly" else get_alltime_leaderboard(limit=10)
        except Exception:
            return f"❌ Could not fetch leaderboard: {e}"

    if not lb:
        return "📭 No scores yet. Play some games first!"

    game_icons = {"fusion": "🃏", "trivia": "🧠", "overall": "🏆"}
    icon        = game_icons.get(game_type, "🏆")
    scope_label = "WEEKLY" if scope == "weekly" else "ALL-TIME"

    now_str = datetime.utcnow().strftime("%d %b · %H:%M UTC")

    header = (
        f"{icon} <b>{game_type.upper()} — {scope_label}</b>\n"
        f"<i>{now_str}</i>\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"<b>{'Rank':<4} {'Player':<16} {'Shield':<8} Pts</b>\n"
        f"━━━━━━━━━━━━━━━━━\n"
    )

    rows = ""
    for i, p in enumerate(lb):
        medal     = medals[i] if i < 3 else f"{i+1:>2}."
        name      = _safe_name(p.get("username", "Unknown"))[:14]
        pts       = p.get("points", 0)

        # Shield directly from leaderboard row (no extra DB call needed)
        st          = p.get("shield_status") or "UNPROTECTED"
        shield_icon = "🛡️" if "ACTIVE" in st else ("💥" if "DISRUPTED" in st else "⚠️")
        ns_until    = p.get("name_shield_until")
        if ns_until:
            try:
                from datetime import datetime as _dt
                if _dt.now() < _dt.fromisoformat(ns_until):
                    name        = "🔐 Anonymous"
                    shield_icon = "🛡️"
            except Exception:
                pass

        rows += f"{medal} <b>{name}</b>  {shield_icon}  {pts:,} pts\n"

    footer = (
        f"━━━━━━━━━━━━━━━━━\n"
        f"<i>🛡️ Protected · ⚠️ Exposed · 💥 Disrupted</i>\n"
        f"<i>Use /attack @name to raid · /shield to protect</i>"
    )

    return header + rows + footer


@dp.callback_query(lambda q: q.data.startswith("lb_"))
async def cb_leaderboard_view(callback: types.CallbackQuery):
    """Render the requested leaderboard tab."""
    await callback.answer()
    parts = callback.data.split("_")  # e.g. lb_fusion_weekly
    if len(parts) < 3:
        return
    game_type = parts[1]   # fusion | trivia | overall
    scope     = parts[2]   # weekly | alltime

    text = await _render_leaderboard(game_type, scope)

    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Refresh",      callback_data=callback.data),
            InlineKeyboardButton(text="⬅️ Back",         callback_data="menu_leaderboards"),
        ],
        [
            InlineKeyboardButton(text="⚔️ Attack",       callback_data="battle_attack_menu"),
            InlineKeyboardButton(text="🛡️ My Shield",    callback_data="battle_shield"),
            InlineKeyboardButton(text="🪤 Set Trap",     callback_data="lb_set_trap"),
        ],
    ])

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=back_kb)
    except TelegramBadRequest:
        pass


@dp.callback_query(lambda q: q.data == "lb_set_trap")
async def cb_lb_set_trap(callback: types.CallbackQuery):
    """Quick trap-setting from leaderboard view."""
    await callback.answer()
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    if not user:
        await callback.answer("Not registered", show_alert=True); return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🪤 Set 3 Mousetraps",  callback_data="trap_set_3"),
            InlineKeyboardButton(text="🪤 Set 5 Mousetraps",  callback_data="trap_set_5"),
        ],
        [
            InlineKeyboardButton(text="🔥 Activate Firewall", callback_data="trap_firewall"),
        ],
        [InlineKeyboardButton(text="⬅️ Back",                callback_data="menu_leaderboards")],
    ])
    await callback.message.edit_text(
        "🪤 <b>SET DEFENSES</b>\n━━━━━━━━━━━━━━━━━\n"
        "Mousetraps: 30% chance to catch incoming scouts (70% escape).\n"
        "Firewall: 50% chance to incinerate scouts with fireball.\n\n"
        "<i>Use /defenses in private for full options.</i>",
        parse_mode="HTML", reply_markup=kb
    )


@dp.callback_query(lambda q: q.data.startswith("trap_set_"))
async def cb_trap_set_count(callback: types.CallbackQuery):
    """Set mousetraps from inline menu."""
    u_id = str(callback.from_user.id)
    count = int(callback.data.replace("trap_set_", ""))
    try:
        set_mousetraps(u_id, count)
        await callback.answer(f"✅ {count} mousetraps set!", show_alert=True)
    except Exception as e:
        await callback.answer(f"❌ {e}", show_alert=True)


@dp.callback_query(lambda q: q.data == "trap_firewall")
async def cb_trap_firewall_activate(callback: types.CallbackQuery):
    """Activate firewall from inline menu."""
    u_id = str(callback.from_user.id)
    try:
        activate_firewall(u_id)
        await callback.answer("🔥 Firewall activated for 1 hour!", show_alert=True)
    except Exception as e:
        await callback.answer(f"❌ {e}", show_alert=True)


@dp.callback_query(lambda q: q.data == "battle_attack_menu")
async def cb_battle_attack_menu(callback: types.CallbackQuery):
    """Attack target selection UI."""
    await callback.answer()
    await callback.message.edit_text(
        "⚔️ <b>ATTACK A PLAYER</b>\n━━━━━━━━━━━━━━━━━\n"
        "To attack, go to private chat and type:\n\n"
        "<code>/attack @username</code>\n\n"
        "Or tap the leaderboard and use the attack action buttons next to a player.\n\n"
        "<i>⚠️ Attacking deactivates your own shield!</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back", callback_data="menu_battle")]
        ])
    )


@dp.callback_query(lambda q: q.data == "battle_scout_menu")
async def cb_battle_scout_menu(callback: types.CallbackQuery):
    """Scout target selection UI."""
    await callback.answer()
    await callback.message.edit_text(
        "🔍 <b>SCOUT A PLAYER</b>\n━━━━━━━━━━━━━━━━━\n"
        "Scouting reveals an enemy's army, resources and shield status.\n\n"
        "Cost: <b>100 Bitcoin</b>\n"
        "Success rate: <b>70%</b>\n\n"
        "To scout, type in private chat:\n"
        "<code>/scout @username</code>\n\n"
        "<i>Target's name shield blocks scouting.</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back", callback_data="menu_battle")]
        ])
    )


@dp.callback_query(lambda q: q.data == "battle_revenge")
async def cb_battle_revenge_info(callback: types.CallbackQuery):
    """Revenge info."""
    await callback.answer()
    u_id = str(callback.from_user.id)
    try:
        from revenge_system import get_revenge_info
        rv = get_revenge_info(u_id)
        if rv.get("active"):
            target = rv.get("target_name", "Unknown")
            txt = (
                f"🩸 <b>BLOOD DEBT ACTIVE</b>\n━━━━━━━━━━━━━━━━━\n"
                f"Target: <b>{_safe_name(target)}</b>\n"
                f"Bonus: <b>1.5× damage</b>\n\n"
                f"Type <code>/revenge</code> then\n"
                f"<code>/attack @{target}</code> to settle it."
            )
        else:
            txt = (
                f"🩸 <b>NO BLOOD DEBT</b>\n━━━━━━━━━━━━━━━━━\n"
                f"<i>Get raided first. Then you earn a 1.5× revenge multiplier.</i>"
            )
    except Exception:
        txt = "❌ Revenge system unavailable."
    await callback.message.edit_text(
        txt, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back", callback_data="menu_battle")]
        ])
    )


@dp.callback_query(lambda q: q.data == "menu_back")
async def cb_menu_back_to_hud(callback: types.CallbackQuery):
    """Return to main HUD from any sub-menu."""
    await callback.answer()
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    if not user:
        await callback.answer("Session expired. Type /start", show_alert=True); return

    username   = _safe_name(user.get("username") or "Operative")
    level      = user.get("level", 1)
    xp         = user.get("xp", 0)
    bitcoin    = user.get("bitcoin", 0)
    sector     = user.get("sector", "—")
    base_name  = user.get("base_name") or "No Base"
    shield_st  = user.get("shield_status") or "⚠️ UNPROTECTED"
    unclaimed_raw = user.get("unclaimed_items", [])
    unclaimed  = len(unclaimed_raw) if isinstance(unclaimed_raw, list) else 0
    inv_raw    = user.get("inventory", [])
    inv_count  = len(inv_raw) if isinstance(inv_raw, list) else 0
    inv_slots  = user.get("backpack_slots", 5)
    xp_bar_pct = min(100, int(xp % 100))
    filled     = xp_bar_pct // 10
    xp_bar     = "█" * filled + "░" * (10 - filled)
    shield_icon = "🛡️" if "ACTIVE" in shield_st else ("💥" if "DISRUPTED" in shield_st else "⚠️")
    claims_warn = f"  ⚡ <b>{unclaimed} UNCLAIMED</b>" if unclaimed > 0 else ""

    hud = (
        f"╔═══════════════════════════╗\n"
        f"║  🃏  <b>CHECKMATE HQ</b>  🃏  ║\n"
        f"╠═══════════════════════════╣\n"
        f"║  👤 <b>{username[:18]}</b>\n"
        f"║  ⭐ Level <b>{level}</b>   💰 <b>{bitcoin:,}</b> BTC\n"
        f"║  [{xp_bar}] {xp_bar_pct}%\n"
        f"║  📍 Sector: <b>{sector}</b>\n"
        f"║  🏰 <b>{base_name[:20]}</b>\n"
        f"║  {shield_icon} Shield: <b>{shield_st}</b>\n"
        f"║  🎒 Inv: <b>{inv_count}/{inv_slots}</b>{claims_warn}\n"
        f"╚═══════════════════════════╝"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👤 Profile",      callback_data="menu_profile"),
            InlineKeyboardButton(text="🏰 My Base",      callback_data="menu_base"),
        ],
        [
            InlineKeyboardButton(text="🎒 Inventory",    callback_data="menu_inventory"),
            InlineKeyboardButton(text="🎁 Claims",       callback_data="menu_claims"),
        ],
        [
            InlineKeyboardButton(text="🛍️ Shop",         callback_data="menu_shop"),
            InlineKeyboardButton(text="⚔️ Battle",       callback_data="menu_battle"),
        ],
        [
            InlineKeyboardButton(text="🏆 Leaderboards", callback_data="menu_leaderboards"),
            InlineKeyboardButton(text="🗺️ Map/Sectors",  callback_data="menu_map"),
        ],
        [
            InlineKeyboardButton(text="🧬 Research Lab", callback_data="menu_research"),
            InlineKeyboardButton(text="⚙️ Account",      callback_data="menu_account"),
        ],
        [
            InlineKeyboardButton(text="🎮 Fusion",       callback_data="menu_fusion_info"),
            InlineKeyboardButton(text="🧠 Trivia",       callback_data="menu_trivia_info"),
        ],
    ])
    try:
        await callback.message.edit_text(hud, parse_mode="HTML", reply_markup=kb)
    except TelegramBadRequest:
        await callback.message.answer(hud, parse_mode="HTML", reply_markup=kb)


@dp.callback_query(lambda q: q.data == "menu_claims")
async def cb_menu_claims_shortcut(callback: types.CallbackQuery):
    """Shortcut from HUD to claims."""
    await callback.answer()
    u_id = str(callback.from_user.id)
    unclaimed = get_unclaimed_items(u_id)
    if not unclaimed:
        await callback.message.edit_text(
            "🎁 <b>No unclaimed items.</b>\n<i>Play games to earn rewards!</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="⬅️ Back", callback_data="menu_back")
            ]])
        )
        return
    # Trigger the existing claims flow
    rows = [[InlineKeyboardButton(text="⚡ AUTO-CLAIM ALL", callback_data="claim_all")]]
    for item in unclaimed[:8]:
        iid  = str(item.get("id", 0))
        itype = item.get("type", "?").upper()
        xp   = item.get("xp_reward", 0)
        lbl  = f"🎁 {itype}" + (f" (+{xp} XP)" if xp else "")
        rows.append([
            InlineKeyboardButton(text=lbl,    callback_data=f"claim_{iid}"),
            InlineKeyboardButton(text="🗑️",   callback_data=f"discard_claim_{iid}"),
        ])
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="menu_back")])
    await callback.message.edit_text(
        f"🎁 <b>UNCLAIMED REWARDS</b> ({len(unclaimed)} items)\n━━━━━━━━━━━━━━━━━",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )


@dp.callback_query(lambda q: q.data == "menu_battle")
async def cb_menu_battle(callback: types.CallbackQuery):
    """Battle hub."""
    await callback.answer()
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    if not user:
        await callback.answer("Not registered", show_alert=True); return

    bitcoin = user.get("bitcoin", 0)
    wins    = user.get("wins", 0)
    losses  = user.get("losses", 0)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚔️ Attack Player",   callback_data="battle_attack_menu"),
            InlineKeyboardButton(text="🔍 Scout Player",    callback_data="battle_scout_menu"),
        ],
        [
            InlineKeyboardButton(text="💀 Revenge",         callback_data="battle_revenge"),
            InlineKeyboardButton(text="🛡️ Shield Status",  callback_data="battle_shield"),
        ],
        [
            InlineKeyboardButton(text="🔫 Weapons Shop",    callback_data="shop_weapons"),
            InlineKeyboardButton(text="⚔️ Battle Items",    callback_data="battle_items_inline"),
        ],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="menu_back")],
    ])

    await callback.message.edit_text(
        f"⚔️ <b>BATTLE COMMAND</b>\n━━━━━━━━━━━━━━━━━\n"
        f"💰 Bitcoin: <b>{bitcoin:,}</b>\n"
        f"📊 Record: <b>{wins}W</b> / <b>{losses}L</b>\n\n"
        f"<i>Choose your action:</i>",
        parse_mode="HTML", reply_markup=kb
    )


@dp.callback_query(lambda q: q.data == "battle_shield")
async def cb_battle_shield(callback: types.CallbackQuery):
    """Shield management from battle hub."""
    await callback.answer()
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    if not user:
        return
    shield_st = user.get("shield_status", "⚠️ UNPROTECTED")
    is_active = "ACTIVE" in shield_st

    kb_rows = []
    if is_active:
        kb_rows.append([InlineKeyboardButton(text="🔴 Deactivate Shield", callback_data="shield_deactivate")])
    else:
        kb_rows.append([InlineKeyboardButton(text="🟢 Activate Shield",   callback_data="shield_activate")])
    kb_rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="menu_battle")])

    icon = "🛡️" if is_active else "⚠️"
    await callback.message.edit_text(
        f"{icon} <b>SHIELD STATUS</b>\n━━━━━━━━━━━━━━━━━\n"
        f"Current: <b>{shield_st}</b>\n\n"
        f"{'Your base is protected.' if is_active else 'Your base is VULNERABLE to attacks!'}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows)
    )


@dp.callback_query(lambda q: q.data in ("shield_activate", "shield_deactivate"))
async def cb_shield_toggle(callback: types.CallbackQuery):
    """Toggle shield on/off."""
    u_id = str(callback.from_user.id)
    if callback.data == "shield_activate":
        ok, msg = activate_shield(u_id)
    else:
        ok, msg = deactivate_shield(u_id)
    await callback.answer(msg, show_alert=True)
    # Refresh shield view
    await cb_battle_shield(callback)


@dp.callback_query(lambda q: q.data == "menu_fusion_info")
async def cb_menu_fusion_info(callback: types.CallbackQuery):
    """Fusion game info and quick-start."""
    await callback.answer()
    chat_id_str = str(CHECKMATE_HQ_GROUP_ID).lstrip("-100") if CHECKMATE_HQ_GROUP_ID else ""
    fusion_link  = f"https://t.me/c/{chat_id_str}/{FUSION_TOPIC_ID}" if chat_id_str else "the group"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🃏 Go to Fusion Topic", url=fusion_link)],
        [
            InlineKeyboardButton(text="🏆 Fusion Weekly",   callback_data="lb_fusion_weekly"),
            InlineKeyboardButton(text="📊 Fusion All-Time", callback_data="lb_fusion_alltime"),
        ],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="menu_back")],
    ])
    await callback.message.edit_text(
        "🃏 <b>FUSION WORD GAME</b>\n━━━━━━━━━━━━━━━━━\n"
        "📖 <b>How to play:</b>\n"
        "Two 6-letter words are shown. Use their letters to form new words!\n\n"
        "📏 <b>Scoring:</b>\n"
        "• 3 letters = 1 pt  • 4 = 2 pts  • 5 = 3 pts\n"
        "• 6 = 4 pts  • 7 = 5 pts  • 8+ = 6 pts\n\n"
        "🔥 <b>Streak bonus:</b> 3+ correct in a row = food bonus\n"
        "🎁 <b>Crate drops:</b> React to claim mid-round crates!\n\n"
        "<i>Type /fusion in the Fusion Topic to start a game.</i>",
        parse_mode="HTML", reply_markup=kb
    )


@dp.callback_query(lambda q: q.data == "menu_trivia_info")
async def cb_menu_trivia_info(callback: types.CallbackQuery):
    """Trivia game info and quick-start."""
    await callback.answer()
    chat_id_str = str(CHECKMATE_HQ_GROUP_ID).lstrip("-100") if CHECKMATE_HQ_GROUP_ID else ""
    trivia_link  = f"https://t.me/c/{chat_id_str}/{TRIVIA_TOPIC_ID}" if chat_id_str else "the group"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧠 Go to Trivia Topic", url=trivia_link)],
        [
            InlineKeyboardButton(text="🏆 Trivia Weekly",   callback_data="lb_trivia_weekly"),
            InlineKeyboardButton(text="📊 Trivia All-Time", callback_data="lb_trivia_alltime"),
        ],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="menu_back")],
    ])
    await callback.message.edit_text(
        "🧠 <b>TRIVIA GAME</b>\n━━━━━━━━━━━━━━━━━\n"
        "📖 <b>How to play:</b>\n"
        "Questions appear every round. Type your answer — fastest wins!\n\n"
        "⚡ <b>Speed bonuses:</b>\n"
        "• Answer in &lt;2s → +3 pts  • &lt;3s → +2 pts  • &lt;4s → +1 pt\n\n"
        "🔥 <b>Streak combos:</b>\n"
        "• 3 correct in a row → +5 bonus\n"
        "• 5 in a row → DOUBLE POINTS!\n\n"
        "👑 <b>Boss rounds:</b> Random — worth 20 pts × 2 multiplier!\n\n"
        "<i>Type /trivia in the Trivia Topic to start a game.</i>",
        parse_mode="HTML", reply_markup=kb
    )


@dp.callback_query(lambda q: q.data == "menu_research")
async def cb_menu_research(callback: types.CallbackQuery):
    """Research lab shortcut."""
    await callback.answer()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔬 Open Lab",   callback_data="menu_back")],
        [InlineKeyboardButton(text="⬅️ Back",       callback_data="menu_back")],
    ])
    await callback.message.edit_text(
        "🧬 <b>RESEARCH LAB</b>\n━━━━━━━━━━━━━━━━━\n"
        "Spend resources to unlock powerful army and base upgrades.\n\n"
        "Use <code>/lab</code> in private chat for the full research menu.",
        parse_mode="HTML", reply_markup=kb
    )


@dp.callback_query(lambda q: q.data == "battle_items_inline")
async def cb_battle_items_inline(callback: types.CallbackQuery):
    """Quick battle items listing from HUD."""
    await callback.answer()
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    if not user:
        return

    bitcoin = user.get("bitcoin", 0)
    level   = user.get("level", 1)

    quick_items = [
        ("🛡️ 1-Day Shield",  200,  1),
        ("🛡️ 3-Day Shield",  500,  1),
        ("🛡️ 7-Day Shield",  1000, 10),
        ("🔐 Name Shield",   800,  5),
        ("📸 Scout",         600,  6),
        ("📴 Anti-Scout",    500,  5),
        ("⚫ Blackout",      2000, 10),
    ]

    rows = []
    for name, price, req_lvl in quick_items:
        can_buy = bitcoin >= price and level >= req_lvl
        icon    = "✅" if can_buy else ("🔒" if level < req_lvl else "❌")
        rows.append([InlineKeyboardButton(
            text=f"{icon} {name} — {price:,}₿",
            callback_data="menu_battle"  # placeholder — full buy via /buy command
        )])

    rows.append([
        InlineKeyboardButton(text="💰 Full Shop (/buy)", callback_data="menu_shop"),
        InlineKeyboardButton(text="⬅️ Back",             callback_data="menu_battle"),
    ])

    await callback.message.edit_text(
        f"⚔️ <b>BATTLE ITEMS</b>\n━━━━━━━━━━━━━━━━━\n"
        f"💰 Your Bitcoin: <b>{bitcoin:,}</b>  |  Level: <b>{level}</b>\n"
        f"<i>Use /buy &lt;item&gt; in private to purchase</i>\n━━━━━━━━━━━━━━━━━",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )

# --- CORRECTED HANDLERS ---
# Note: These MUST match the text inside the [ ] exactly.

@dp.message(lambda message: message.text == "[🎮 GAME]")
async def game_module(message: types.Message):
    await message.answer("🕹️ Loading Fusion Engine... Use /fusion in the group!")

@dp.message(lambda message: message.text == "[🛍️ SHOP]")
async def shop_button_handler(message: types.Message):
    # This acts as the entry point from the bottom keyboard
    u_id = str(message.from_user.id)
    user = get_user(u_id)
    bitcoin = user.get("bitcoin", 0)
    gold = user.get("gold", 0)
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏬 GENERAL STORE", callback_data="shop_category_general")],
        [InlineKeyboardButton(text="💀 BLACK MARKET", callback_data="shop_category_blackmarket")],
        [InlineKeyboardButton(text="💎 PREMIUM PLAZA", callback_data="shop_category_premium")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="menu_back")],
    ])
    
    # We use .answer because this is a new message, not an edit
    await message.answer(
        f"🛍️ *THE NEXUS MARKETPLACE*\nBalance: {bitcoin:,} 💳"
        f"🟡 **Gold:** {gold:,}\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"**General:** Basic supplies & resources\n"
        f"**Black Market:** High-risk, rare illegal tech\n"
        f"**Premium:** Special bundles & gold items\n"
        f"━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown",
        reply_markup=markup
    )

@dp.message(lambda message: message.text == "[⚔️ EQUIP]")
async def equip_module(message: types.Message):
    await message.answer("⚔️ LOADOUT: Select your active stickers/items.")

@dp.message(lambda message: message.text == "[🧬 RESEARCH]")
async def research_module(message: types.Message):
    await message.answer("🧬 LAB: Researching new 4D encryption protocols...")

@dp.message(lambda message: message.text == "[⚙️ OPTIONS]")
async def options_module(message: types.Message):
    u_id = str(message.from_user.id)
    user = get_user(u_id)
    
    if not user:
        await message.answer("❌ Error: Operative profile not found.")
        return

    text, markup = get_account_management_ui()
    
    # We use .answer() here because we are responding to a new message
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=markup
    )
@dp.callback_query(lambda q: q.data == "start_tutorial")
async def cb_start_tutorial(callback: types.CallbackQuery):
    """Begin new player tutorial."""
    from initiation import Trial
    await callback.message.delete()
    
    u_id = str(callback.from_user.id)
    username = callback.from_user.first_name or "Player"
    
    # Register the user
    register_user(u_id, username)
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ I'm ready", callback_data="tutorial_start")],
        [InlineKeyboardButton(text="🚪 Cancel", callback_data="tutorial_cancel")],
    ])
    
    await callback.message.answer(
        "🃏 *GameMaster:* \"Good choice. Listen carefully.\"\n\n"
        "_The 64 is divided into sectors. Each sector holds power, resources, and secrets._\n\n"
        "*Three games define your destiny:*\n"
        "• **FUSION** — Master the art of words\n"
        "• **CHESS** — Outthink your opponents\n"
        "• **RAIDS** — Steal from rivals\n\n"
        "_Type `!fusion` in the group when ready to play._",
        parse_mode="Markdown",
        reply_markup=markup
    )
    await callback.answer()


@dp.callback_query(lambda q: q.data == "start_cancel")
async def cb_start_cancel(callback: types.CallbackQuery):
    """Cancel start."""
    await callback.message.delete()
    await callback.answer()


@dp.callback_query(lambda q: q.data == "tutorial_start")
async def cb_tutorial_start(callback: types.CallbackQuery):
    """Start the game."""
    await callback.message.edit_text(
        "🎊 *Welcome to The 64!* 🎊\n\n"
        "_You're now officially registered._\n\n"
        "**Next steps:**\n"
        "1. Join the main group and type `!fusion`\n"
        "2. Build your base with `/base`\n"
        "3. Train troops with `/train`\n"
        "4. Attack rivals with `/attack`\n\n"
        "_Good luck, warrior._",
        parse_mode="Markdown"
    )
    await callback.answer()


@dp.callback_query(lambda q: q.data == "tutorial_cancel")
async def cb_tutorial_cancel(callback: types.CallbackQuery):
    """Cancel tutorial."""
    await callback.message.delete()
    await callback.answer()


@dp.callback_query(lambda q: q.data == "menu_base")
async def cb_menu_base(callback: types.CallbackQuery):
    """Show base information and building menu."""
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    
    if not user:
        await callback.answer("User not found", show_alert=True)
        return
    
    base_name = user.get("base_name", "Unknown")
    base_level = user.get("base_level", 1)
    base_res = user.get("base_resources", {})
    
    res = base_res.get("resources", {})
    wood = res.get("wood", 0)
    bronze = res.get("bronze", 0)
    iron = res.get("iron", 0)
    diamond = res.get("diamond", 0)
    food = base_res.get("food", 0)
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏗️ Build", callback_data="base_build")],
        [InlineKeyboardButton(text="🛡️ Defense", callback_data="base_defense")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="menu_back")],
    ])
    
    await callback.message.edit_text(
        f"🏰 *{base_name}* (Level {base_level})\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"*Resources:*\n"
        f"🪵 Wood: **{wood}**\n"
        f"🧱 Bronze: **{bronze}**\n"
        f"⛓️ Iron: **{iron}**\n"
        f"💎 Diamond: **{diamond}**\n"
        f"🌽 Food: **{food}**\n"
        f"━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown",
        reply_markup=markup
    )
    await callback.answer()


@dp.callback_query(lambda q: q.data == "menu_resources")
async def cb_menu_resources(callback: types.CallbackQuery):
    """Show detailed resource breakdown."""
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    
    if not user:
        await callback.answer("User not found", show_alert=True)
        return
    
    base_res = user.get("base_resources", {})
    res = base_res.get("resources", {})
    
    woods = res.get("wood", 0)
    bronze = res.get("bronze", 0)
    iron = res.get("iron", 0)
    diamond = res.get("diamond", 0)
    relics = res.get("relics", 0)
    food = base_res.get("food", 0)
    streak = base_res.get("current_streak", 0)
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ Mining", callback_data="resources_mining")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="menu_back")],
    ])
    
    await callback.message.edit_text(
        f"⚙️ *RESOURCE INVENTORY*\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"*Building Materials:*\n"
        f"🪵 Wood: **{woods}**\n"
        f"🧱 Bronze: **{bronze}**\n"
        f"⛓️ Iron: **{iron}**\n"
        f"💎 Diamond: **{diamond}**\n"
        f"🏺 Relics: **{relics}**\n\n"
        f"*Supplies:*\n"
        f"🌽 Food: **{food}**\n"
        f"🔥 Streak: **{streak}**\n"
        f"━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown",
        reply_markup=markup
    )
    await callback.answer()


@dp.callback_query(lambda q: q.data == "menu_profile")
async def cb_menu_profile(callback: types.CallbackQuery):
    """Show player profile."""
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    
    if not user:
        await callback.answer("User not found", show_alert=True)
        return
    
    username = user.get("username", "Unknown")
    level = user.get("level", 1)
    xp = user.get("xp", 0)
    all_time_points = user.get("all_time_points", 0)
    weekly_points = user.get("weekly_points", 0)
    total_words = user.get("total_words", 0)
    wins = user.get("wins", 0)
    losses = user.get("losses", 0)
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎖️ Achievements", callback_data="profile_achievements")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="menu_back")],
    ])
    
   
    await callback.message.edit_text(
        f"👤 *{username}*\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"🎖️ **Level:** {level}\n"
        f"✨ **XP:** {xp}\n"
        f"💰 **Gold:** {user.get('gold', 0)}\n"
        f"🏰 **Guild:** {user.get('guild', {}).get('name', 'No Guild')}\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"*Points:*\n"
        f"📊 All-Time: **{all_time_points}**\n"
        f"📈 Weekly: **{weekly_points}**\n\n"
        f"*Statistics:*\n"
        f"📝 Words: **{total_words}**\n"
        f"🏆 Wins: **{wins}**\n"
        f"💀 Losses: **{losses}**\n"
        f"━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown",
        reply_markup=markup

    
            )
    
    
    await callback.answer()


@dp.callback_query(lambda q: q.data == "menu_shop")
async def cb_menu_shop(callback: types.CallbackQuery):
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    bitcoin = user.get("bitcoin", 0)
    gold = user.get("gold", 0) # Assuming you have a premium currency
    if not user:
        await callback.answer("User not found", show_alert=True)
        return
     
    markup1 = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏬 GENERAL STORE", callback_data="shop_category_general")],
        [InlineKeyboardButton(text="💀 BLACK MARKET", callback_data="shop_category_blackmarket")],
        [InlineKeyboardButton(text="💎 PREMIUM PLAZA", callback_data="shop_category_premium")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="menu_back")],
    ])
    await callback.message.edit_text(
        f"🛍️ *THE NEXUS MARKETPLACE* 🛍️\n\n"
        f"💳 **Bitcoin:** {bitcoin:,}\n"
        f"🟡 **Gold:** {gold:,}\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"**General:** Basic supplies & resources\n"
        f"**Black Market:** High-risk, rare illegal tech\n"
        f"**Premium:** Special bundles & gold items\n"
        f"━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown",
        reply_markup=markup1
    )
    await callback.answer()
    
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛡️ Shields", callback_data="shop_shields")],
        [InlineKeyboardButton(text="⚡ Weapons", callback_data="shop_weapons")],
        [InlineKeyboardButton(text="🎁 Boosts", callback_data="shop_boosts")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="menu_back")],
    ])
    
    await callback.message.edit_text(
        f"🛍️ *SHOP* 🛍️\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"**Your Bitcoin:** {bitcoin} 💳\n\n"
        f"_Browse items to protect your base,_\n"
        f"_upgrade your arsenal, and boost gains._\n"
        f"━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown",
        reply_markup=markup
    )
    await callback.answer()

#this is a function for the menu account so that reply keyboard and inline keyboard can call it 

def get_account_management_ui():
    """Returns the text and markup for the Account Management screen."""
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💾 Save", callback_data="account_save_menu")],
        [InlineKeyboardButton(text="📂 Load", callback_data="account_load")],
        [InlineKeyboardButton(text="🔄 Reset", callback_data="account_reset_menu")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="menu_back")],
    ])
    
    text = (
        f"💎 *ACCOUNT MANAGEMENT*\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"*Manage your game saves and resets.*\n\n"
        f"**Save:** Create a checkpoint\n"
        f"**Load:** Restore from a save\n"
        f"**Reset:** Start fresh (⚠️ Careful!)\n"
        f"━━━━━━━━━━━━━━━━━"
    )
    return text, markup
@dp.callback_query(lambda q: q.data == "menu_account")
async def cb_menu_account(callback: types.CallbackQuery):
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    
    if not user:
        await callback.answer("User not found", show_alert=True)
        return

    text, markup = get_account_management_ui()
    
    # We use .edit_text() here to keep the Godot-style 'scene transition'
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=markup
    )
    await callback.answer()

@dp.callback_query(lambda q: q.data == "menu_map")
async def cb_menu_map(callback: types.CallbackQuery):
    """Show sectors/map."""
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    
    if not user:
        await callback.answer("User not found", show_alert=True)
        return
    
    current_sector = user.get("sector", 1)
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Explore", callback_data="map_explore")],
        [InlineKeyboardButton(text="⚔️ Attack", callback_data="map_attack")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="menu_back")],
    ])
    
    await callback.message.edit_text(
        f"🗺️ *MAP* 🗺️\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"**Current Sector:** {current_sector}\n\n"
        f"*Actions:*\n"
        f"🔍 Scout enemies\n"
        f"⚔️ Plan raids\n"
        f"💰 Find merchants\n"
        f"━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown",
        reply_markup=markup
    )
    await callback.answer()


@dp.callback_query(lambda q: q.data == "menu_inventory")
async def cb_menu_inventory(callback: types.CallbackQuery):
    """Show inventory."""
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    
    if not user:
        await callback.answer("User not found", show_alert=True)
        return
    
    inv = user.get("inventory", [])
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Open Crate", callback_data="inv_open")],
        [InlineKeyboardButton(text="⚡ Use Item", callback_data="inv_use")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="menu_back")],
    ])
    
    inv_text = f"🎒 *INVENTORY* ({len(inv)} items)\n\n━━━━━━━━━━━━━━━━━\n"
    if inv:
        for i, item in enumerate(inv[:5], 1):
            inv_text += f"{i}. {item.get('name', 'Unknown')}\n"
        if len(inv) > 5:
            inv_text += f"... and {len(inv) - 5} more\n"
    else:
        inv_text += "_Your inventory is empty._\n"
    inv_text += "━━━━━━━━━━━━━━━━━"
    
    await callback.message.edit_text(
        inv_text,
        parse_mode="Markdown",
        reply_markup=markup
    )
    await callback.answer()
    
def get_user_with_fix(u_id):
    user = get_user(u_id) # Your original database fetch
    if user and "gold" not in user:
        # Player is old! Give them the new fields
        user["gold"] = 0
        user["vault"] = {"bitcoin": 0, "gold": 0}
        user["guild"] = {"name": "No Guild", "members": []} # etc...
        save_user(u_id, user) # Save the fixed version
    return user

# menu_back handler moved to new cb_menu_back_to_hud above


# ━━━━━ SHOP SUBMENUS ━━━━━

@dp.callback_query(lambda q: q.data == "shop_shields")
async def cb_shop_shields(callback: types.CallbackQuery):
    """Show shields for sale."""
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛡️ 1-Hour Shield - 200₿", callback_data="buy_1hshield")],
        [InlineKeyboardButton(text="🛡️ 3-Hour Shield- 500₿", callback_data="buy_3hshield")],
        [InlineKeyboardButton(text="🛡️ 12-Hour Shield - 700₿", callback_data="buy_12hshield")],
        [InlineKeyboardButton(text="🛡️ 1-Day Shield - 1000₿", callback_data="buy_1dshield")],
        [InlineKeyboardButton(text="🛡️ 3-Day Shield - 2500₿", callback_data="buy_3dshield")],
        [InlineKeyboardButton(text="🛡️ 7-Day Shield - 5000₿", callback_data="buy_7dshield")],
        [InlineKeyboardButton(text="🛡️ Name Shield - 800₿", callback_data="buy_nameshield")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="menu_shop")],
    ])
            
    
    await callback.message.edit_text(
        "🛡️ [*SHIELDS*]\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "*Use shield for protections*",
        parse_mode="Markdown",
        reply_markup=markup
    )
    await callback.answer()


@dp.callback_query(lambda q: q.data == "shop_weapons")
async def cb_shop_weapons(callback: types.CallbackQuery):
    """Show weapons for sale."""
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ Iron Sword - 300₿₿", callback_data="buy_weapon_sword")],
        [InlineKeyboardButton(text="🏹 Bronze Bow - 600₿₿", callback_data="buy_weapon_bow")],
        [InlineKeyboardButton(text="💣 Diamond Bomb - 2000₿₿", callback_data="buy_weapon_bomb")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="menu_shop")],
    ])
    
    await callback.message.edit_text(
        "⚔️ *WEAPONS*\n\n"
        "━━━━━━━━━━━━━━━\n"
        "*Strengthen your attack power*",
        parse_mode="Markdown",
        reply_markup=markup
    )
    await callback.answer()


@dp.callback_query(lambda q: q.data == "shop_boosts")
async def cb_shop_boosts(callback: types.CallbackQuery):
    """Show boosts for sale."""
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ 2x Resources - 250₿₿", callback_data="buy_boost_2x")],
        [InlineKeyboardButton(text="🔥 Fast Training - 400₿₿", callback_data="buy_boost_fast")],
        [InlineKeyboardButton(text="💟 Luck Boost - 350₿₿", callback_data="buy_boost_luck")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="menu_shop")],
    ])
    
    await callback.message.edit_text(
        "🎁 *BOOSTS*\n\n"
        "━━━━━━━━━━━━━━━\n"
        "*Temporary power-ups to accelerate progress*",
        parse_mode="Markdown",
        reply_markup=markup
    )
    await callback.answer()


@dp.callback_query(lambda q: q.data.startswith("buy_"))
async def cb_purchase(callback: types.CallbackQuery):
    """Handle purchases."""
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    
    if not user:
        await callback.answer("User not found", show_alert=True)
        return
    
    item = callback.data.split("_", 1)[1]
    costs = {
        "shield_iron": 500,
        "shield_bronze": 1000,
        "shield_diamond": 5000,
        "weapon_sword": 300,
        "weapon_bow": 600,
        "weapon_bomb": 2000,
        "boost_2x": 250,
        "boost_fast": 400,
        "boost_luck": 350,
    }
    
    cost = costs.get(item, 0)
    bitcoin = user.get("bitcoin", 0)
    
    if bitcoin < cost:
        await callback.answer(f"💸 Not enough Bitcoin! You need {cost - bitcoin} more.", show_alert=True)
        return
    
    # Deduct and add to inventory
    user["bitcoin"] = bitcoin - cost
    if "inventory" not in user:
        user["inventory"] = []
    user["inventory"].append({"name": item, "bought_at": int(time.time())})
    save_user(u_id, user)
    
    await callback.answer(f"✅ Purchased {item}!", show_alert=True)
    await callback.message.edit_text(
        f"✅ *Purchase Successful!*\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"**Item:** {item}\n"
        f"**Cost:** {cost} 💳\n"
        f"**New Balance:** {user['bitcoin']} 💳\n"
        f"━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back to Shop", callback_data="menu_shop")],
        ])
    )


# ━━━━━ ACCOUNT SUBMENUS ━━━━━

@dp.callback_query(lambda q: q.data == "account_save_menu")
async def cb_account_save_menu(callback: types.CallbackQuery):
    """Show save menu."""
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💾 Save to Slot 1", callback_data="account_save_slot1")],
        [InlineKeyboardButton(text="💾 Save to Slot 2", callback_data="account_save_slot2")],
        [InlineKeyboardButton(text="💾 Save to Slot 3", callback_data="account_save_slot3")],
        [InlineKeyboardButton(text="💾 Save to Slot 4", callback_data="account_save_slot4")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="menu_account")],
    ])
    
    await callback.message.edit_text(
        "💾 *SAVE GAME*\n\n"
        "━━━━━━━━━━━━━━━━━\n"
        "_Choose a save slot._",
        parse_mode="Markdown",
        reply_markup=markup
    )
    await callback.answer()


@dp.callback_query(lambda q: q.data.startswith("account_save_slot"))
async def cb_account_save_slot(callback: types.CallbackQuery):
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    
    # Extract slot number safely (handles both 'slot1' and 'slot1_confirm')
    raw_slot = callback.data.split("slot")[1]
    slot = raw_slot.replace("_confirm", "")
    is_confirmed = "_confirm" in callback.data

    if not user:
        await callback.answer("User not found", show_alert=True)
        return

    # Handle the game_saves structure
    saves = user.get("game_saves", {})
    if isinstance(saves, str):
        saves = json.loads(saves)

    # 1. OVERWRITE CHECK
    if str(slot) in saves and not is_confirmed:
        ts = saves[str(slot)].get("timestamp", 0)
        dt = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
        
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚠️ YES, Overwrite", callback_data=f"account_save_slot{slot}_confirm")],
            [InlineKeyboardButton(text="❌ Cancel", callback_data="account_save_menu")]
        ])
        
        await callback.message.edit_text(
            f"⚠️ **OVERWRITE WARNING**\n\nSlot {slot} has a save from `{dt}`.\n"
            "Replace it with your current progress?",
            reply_markup=markup, parse_mode="Markdown"
        )
        return

    # 2. CREATE SNAPSHOT (Excluding meta-data and the save dictionary itself)
    snapshot = {k: v for k, v in user.items() if k not in META_KEYS}
    
    # Update the dictionary
    saves[str(slot)] = {
        "timestamp": int(time.time()),
        "data": snapshot
    }
    
    # 3. SAVE TO DB
    # We only update the 'game_saves' column to be safe and efficient
    save_user(u_id, {"game_saves": saves})
    
    await callback.answer(f"✅ Saved to Slot {slot}!", show_alert=True)
    await callback.message.edit_text(
        f"✅ *Game Saved to Slot {slot}*",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back", callback_data="menu_account")]
        ]),
        parse_mode="Markdown"
    )

@dp.callback_query(lambda q: q.data == "account_load")
async def cb_account_load(callback: types.CallbackQuery):
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    
    # Handle JSON string issue from earlier
    saves = user.get("game_saves", {})
    if isinstance(saves, str):
        saves = json.loads(saves)

    buttons = []
    for i in range(1, 5):
        slot_key = str(i)
        if slot_key in saves:
            ts = saves[slot_key].get("timestamp", 0)
            dt = datetime.fromtimestamp(ts).strftime("%m/%d %H:%M")
            buttons.append([InlineKeyboardButton(text=f"📂 Slot {i} ({dt})", callback_data=f"account_load_slot{i}")])
        else:
            buttons.append([InlineKeyboardButton(text=f"📂 Slot {i} - Empty", callback_data=f"account_load_slot{i}")])
    
    buttons.append([InlineKeyboardButton(text="⬅️ Back", callback_data="menu_account")])
    await callback.message.edit_text("📂 *LOAD GAME*", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@dp.callback_query(lambda q: q.data.startswith("account_load_slot"))
async def cb_account_load_slot(callback: types.CallbackQuery):
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    slot = callback.data.split("slot")[1]
    
    saves = user.get("game_saves", {})
    if isinstance(saves, str):
        saves = json.loads(saves)

    if str(slot) not in saves:
        await callback.answer("❌ This slot is empty!", show_alert=True)
        return

    # Extract data
    saved_payload = saves[str(slot)].get("data", {})
    
    # Apply to current user object, but PROTECT meta-keys
    for key, value in saved_payload.items():
        if key not in META_KEYS:
            user[key] = value
    
    # Save the now-restored user object back to the database
    save_user(u_id, user)
    
    await callback.answer(f"✅ Slot {slot} Restored!", show_alert=True)
    await callback.message.edit_text(
        f"✅ *Slot {slot} Loaded Successfully*",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back", callback_data="menu_account")]
        ]),
        parse_mode="Markdown"
    )


@dp.callback_query(lambda q: q.data == "account_reset_menu")
async def cb_account_reset_menu(callback: types.CallbackQuery):
    """Confirm reset."""
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚠️ YES, Reset", callback_data="account_reset_confirm")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="menu_account")],
    ])
    
    await callback.message.edit_text(
        "⚠️ *RESET ACCOUNT*\n\n"
        "━━━━━━━━━━━━━━━━━\n"
        "_Are you sure? This cannot be undone._\n\n"
        "_All progress will be lost._",
        parse_mode="Markdown",
        reply_markup=markup
    )
    await callback.answer()


@dp.callback_query(lambda q: q.data == "account_reset_confirm")
async def cb_account_reset_confirm(callback: types.CallbackQuery):
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    
    if not user: return

    # Define the starting stats
    starting_stats = {
        "level": 1,
        "xp": 0,
        "bitcoin": 100,
        "inventory": [],
        "wins": 0,
        "losses": 0,
        "base_level": 1,
        "inventory": [],
        "completed_tutorial": True,
        "shield_status" : "🛡️ ACTIVE",
        "unclaimed_items" : {},
        "base_resources": {
            "resources": {"wood": 100, "bronze": 50, "iron": 25, "diamond": 10, "relics": 0},
            "food": 100,
            "current_streak": 0
        },
        # ... any other stats you want to reset ...
    }

    # Update current user with starting stats
    # This leaves 'username' and 'game_saves' untouched!
    for key, value in starting_stats.items():
        user[key] = value

    save_user(u_id, user)
    
    await callback.answer("🧹 Account reset complete.", show_alert=True)
    await callback.message.edit_text("✅ *Account Reset Successfully*\nYour saves and name were preserved.")


# ━━━━━ PROFILE SUBMENUS ━━━━━

@dp.callback_query(lambda q: q.data == "profile_achievements")
async def cb_profile_achievements(callback: types.CallbackQuery):
    """Show achievements."""
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    
    if not user:
        await callback.answer("User not found", show_alert=True)
        return
    
    achievements = user.get("achievements", [])
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Back", callback_data="menu_profile")],
    ])
    
    ach_text = f"🎖️ *ACHIEVEMENTS* ({len(achievements)} earned)\n\n━━━━━━━━━━━━━━━━━\n"
    if achievements:
        for ach in achievements[:10]:
            ach_text += f"✅ {ach}\n"
        if len(achievements) > 10:
            ach_text += f"\n_... and {len(achievements) - 10} more_\n"
    else:
        ach_text += "_No achievements yet. Keep playing!_\n"
    ach_text += "━━━━━━━━━━━━━━━━━"
    
    await callback.message.edit_text(
        ach_text,
        parse_mode="Markdown",
        reply_markup=markup
    )
    await callback.answer()


# ━━━━━ BASE SUBMENUS ━━━━━

@dp.callback_query(lambda q: q.data == "base_build")
async def cb_base_build(callback: types.CallbackQuery):
    """Show building options."""
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Storage", callback_data="build_storage")],
        [InlineKeyboardButton(text="🛠️ Workshop", callback_data="build_workshop")],
        [InlineKeyboardButton(text="🌾 Farm", callback_data="build_farm")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="menu_base")],
    ])
    
    await callback.message.edit_text(
        "🏗️ *CONSTRUCTION*\n\n"
        "━━━━━━━━━━━━━━━━━\n"
        "*Build structures to boost your base.*",
        parse_mode="Markdown",
        reply_markup=markup
    )
    await callback.answer()


@dp.callback_query(lambda q: q.data == "base_defense")
async def cb_base_defense(callback: types.CallbackQuery):
    """Show defense options."""
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    
    if not user:
        await callback.answer("User not found", show_alert=True)
        return
    
    defense_level = user.get("defense_level", 1)
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛡️ Raise Defense", callback_data="defense_raise")],
        [InlineKeyboardButton(text="👥 Deploy Troops", callback_data="defense_troops")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="menu_base")],
    ])
    
    await callback.message.edit_text(
        f"🛡️ *DEFENSE*\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"**Defense Level:** {defense_level}\n\n"
        f"*Strengthen your defenses against raids.*",
        parse_mode="Markdown",
        reply_markup=markup
    )
    await callback.answer()


# ━━━━━ RESOURCES SUBMENUS ━━━━━

@dp.callback_query(lambda q: q.data == "resources_mining")
async def cb_resources_mining(callback: types.CallbackQuery):
    """Show mining options."""
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⛏️ Mine Wood", callback_data="mine_wood")],
        [InlineKeyboardButton(text="⛏️ Mine Bronze", callback_data="mine_bronze")],
        [InlineKeyboardButton(text="⛏️ Mine Iron", callback_data="mine_iron")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="menu_resources")],
    ])
    
    await callback.message.edit_text(
        "⛏️ *MINING*\n\n"
        "━━━━━━━━━━━━━━━━━\n"
        "*Extract resources from the ground.*",
        parse_mode="Markdown",
        reply_markup=markup
    )
    await callback.answer()


@dp.callback_query(lambda q: q.data.startswith("mine_"))
async def cb_mine_resource(callback: types.CallbackQuery):
    """Mine a resource."""
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    resource = callback.data.split("_")[1]
    
    if not user:
        await callback.answer("User not found", show_alert=True)
        return
    
    if "base_resources" not in user:
        user["base_resources"] = {"resources": {}, "food": 0}
    if "resources" not in user["base_resources"]:
        user["base_resources"]["resources"] = {}
    
    # Mine the resource
    amount = 10
    user["base_resources"]["resources"][resource] = user["base_resources"]["resources"].get(resource, 0) + amount
    save_user(u_id, user)
    
    await callback.answer(f"⛏️ Mined {amount} {resource}!", show_alert=True)


# ━━━━━ MAP SUBMENUS ━━━━━

@dp.callback_query(lambda q: q.data == "map_explore")
async def cb_map_explore(callback: types.CallbackQuery):
    """Explore sectors."""
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Scout Sector 1", callback_data="scout_sector_1")],
        [InlineKeyboardButton(text="🔍 Scout Sector 2", callback_data="scout_sector_2")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="menu_map")],
    ])
    
    await callback.message.edit_text(
        "🔍 *EXPLORATION*\n\n"
        "━━━━━━━━━━━━━━━━━\n"
        "*Scout territories for enemies and treasure.*",
        parse_mode="Markdown",
        reply_markup=markup
    )
    await callback.answer()


@dp.callback_query(lambda q: q.data == "map_attack")
async def cb_map_attack(callback: types.CallbackQuery):
    """Attack options."""
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ Raid Nearby", callback_data="attack_raid")],
        [InlineKeyboardButton(text="🎯 Target Player", callback_data="attack_player")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="menu_map")],
    ])
    
    await callback.message.edit_text(
        "⚔️ *ATTACKS*\n\n"
        "━━━━━━━━━━━━━━━━━\n"
        "*Raid bases and steal resources.*",
        parse_mode="Markdown",
        reply_markup=markup
    )
    await callback.answer()


# ━━━━━ INVENTORY SUBMENUS ━━━━━

@dp.callback_query(lambda q: q.data == "inv_open")
async def cb_inv_open(callback: types.CallbackQuery):
    """Open a crate."""
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    
    if not user:
        await callback.answer("User not found", show_alert=True)
        return
    
    # Simulate crate opening
    rewards = ["Wood x50", "Bronze x25", "Diamond x5", "Bitcoin x100"]
    reward = rewards[int(time.time()) % len(rewards)]
    
    await callback.answer(f"🎁 You got: {reward}!", show_alert=True)


@dp.callback_query(lambda q: q.data == "inv_use")
async def cb_inv_use(callback: types.CallbackQuery):
    """Use an item from inventory."""
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    
    if not user:
        await callback.answer("User not found", show_alert=True)
        return
    
    inv = user.get("inventory", [])
    if not inv:
        await callback.answer("Your inventory is empty!", show_alert=True)
        return
    
    # Use the first item
    item = inv.pop(0)
    save_user(u_id, user)
    
    await callback.answer(f"✅ Used: {item.get('name', 'Unknown')}", show_alert=True)


# ━━━━━ GUILD / ALLIANCE MENU ━━━━━

@dp.callback_query(lambda q: q.data == "menu_guild")
async def cb_menu_guild(callback: types.CallbackQuery):
    """Show guild/alliance menu."""
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    
    if not user:
        await callback.answer("User not found", show_alert=True)
        return
    
    guild = user.get("guild", {})
    guild_name = guild.get("name", "No Guild")
    guild_rank = guild.get("rank", "N/A")
    guild_members = guild.get("members", [])
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 View Guild", callback_data="guild_view")],
        [InlineKeyboardButton(text="👥 Members", callback_data="guild_members")],
        [InlineKeyboardButton(text="💳 Guild Treasury", callback_data="guild_treasury")],
        [InlineKeyboardButton(text="⚔️ Guild Wars", callback_data="guild_wars")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="menu_back")],
    ])
    
    await callback.message.edit_text(
        f"⚔️ *GUILD / ALLIANCE* ⚔️\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"**Guild:** {guild_name}\n"
        f"**Your Rank:** {guild_rank}\n"
        f"**Members:** {len(guild_members)}\n\n"
        f"_Unite with allies and dominate together._\n"
        f"━━━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown",
        reply_markup=markup
    )
    await callback.answer()


@dp.callback_query(lambda q: q.data == "guild_view")
async def cb_guild_view(callback: types.CallbackQuery):
    """View guild details."""
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    
    guild = user.get("guild", {})
    guild_name = guild.get("name", "No Guild")
    guild_level = guild.get("level", 0)
    treasury = guild.get("treasury", {"bitcoin": 0, "gold": 0})
    perks = guild.get("perks", [])
    
    perks_text = "None"
    if perks:
        perks_text = ", ".join(perks[:5])
    
    await callback.message.edit_text(
        f"📋 *{guild_name}*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"**Level:** {guild_level}\n"
        f"**Treasury:**\n"
        f"  💳 Bitcoin: {treasury.get('bitcoin', 0):,}\n"
        f"  👑 Gold: {treasury.get('gold', 0)}\n\n"
        f"**Guild Perks:**\n"
        f"  {perks_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back", callback_data="menu_guild")],
        ])
    )
    await callback.answer()


@dp.callback_query(lambda q: q.data == "guild_members")
async def cb_guild_members(callback: types.CallbackQuery):
    """View guild members."""
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    
    guild = user.get("guild", {})
    members = guild.get("members", [])
    
    members_text = ""
    for i, member in enumerate(members[:10], 1):
        name = member.get("name", "Unknown")
        level = member.get("level", 0)
        rank = member.get("rank", "Member")
        members_text += f"{i}. {name} (Level {level}) - {rank}\n"
    
    if not members_text:
        members_text = "_No guild members yet._"
    
    await callback.message.edit_text(
        f"👥 *GUILD MEMBERS* ({len(members)})\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{members_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back", callback_data="menu_guild")],
        ])
    )
    await callback.answer()


@dp.callback_query(lambda q: q.data == "guild_treasury")
async def cb_guild_treasury(callback: types.CallbackQuery):
    """Manage guild treasury (deposit/withdraw)."""
    u_id = str(callback.from_user.id)
    user = get_user(u_id)
    
    if not user:
        await callback.answer("User not found", show_alert=True)
        return
    
    treasury = user.get("guild", {}).get("treasury", {"bitcoin": 0, "gold": 0})
    player_bitcoin = user.get("bitcoin", 0)
    player_gold = user.get("gold", 0)
    
    await callback.message.edit_text(
        f"💳 *GUILD TREASURY*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"**Treasury Balance:**\n"
        f"  💰 Bitcoin: {treasury.get('bitcoin', 0):,}\n"
        f"  👑 Gold: {treasury.get('gold', 0)}\n\n"
        f"**Your Balance:**\n"
        f"  💰 Bitcoin: {player_bitcoin:,}\n"
        f"  👑 Gold: {player_gold}\n\n"
        f"_Use `/guild deposit bitcoin 100` to contribute._\n"
        f"━━━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back", callback_data="menu_guild")],
        ])
    )
    await callback.answer()


@dp.callback_query(lambda q: q.data == "guild_wars")
async def cb_guild_wars(callback: types.CallbackQuery):
    """Guild vs Guild wars."""
    await callback.message.edit_text(
        f"⚔️ *GUILD WARS*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"**Coming Soon**\n\n"
        f"_Guild-wide battles for control of sectors._\n"
        f"━━━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back", callback_data="menu_guild")],
        ])
    )
    await callback.answer()


# ━━━━━ COMMAND-BASED SHOPPING SYSTEM ━━━━━

def get_shop_items():
    """Get all purchasable items with prices."""
    items = {
        # RESOURCES
        "wood": {"name": "🌲 Wood", "price": 10, "category": "resource"},
        "bronze": {"name": "🧱 Bronze", "price": 20, "category": "resource"},
        "iron": {"name": "⛓️ Iron", "price": 50, "category": "resource"},
        "diamond": {"name": "💎 Diamond", "price": 100, "category": "resource"},
        
        # SHIELDS
        "basic_shield": {"name": "🛡️ Basic Shield", "price": 500, "category": "shield", "effect": "10% damage reduction"},
        "iron_shield": {"name": "⚔️ Iron Shield", "price": 1500, "category": "shield", "effect": "25% damage reduction"},
        "legendary_shield": {"name": "💥 Legendary Shield", "price": 5000, "category": "shield", "effect": "50% damage reduction"},
        
        # WEAPONS (from weapon_system.py)
        "machine_gun_turret": {"name": "🔫 Machine Gun Turret", "price": 1000, "category": "weapon"},
        "plasma_cannon": {"name": "⚡ Plasma Cannon", "price": 2500, "category": "weapon"},
        "emp_blast": {"name": "💥 EMP Blast", "price": 800, "category": "weapon"},
        "xp_siphon": {"name": "🔋 XP Siphon", "price": 1200, "category": "weapon"},
        "bitcoin_miner": {"name": "💰 Bitcoin Miner", "price": 1500, "category": "weapon"},
        "resource_drain": {"name": "🌀 Resource Drain", "price": 2000, "category": "weapon"},
        
        # TRAPS
        "spike_trap": {"name": "🗡️ Spike Trap", "price": 300, "category": "trap"},
        "fire_trap": {"name": "🔥 Fire Trap", "price": 600, "category": "trap"},
        "poison_trap": {"name": "☠️ Poison Trap", "price": 800, "category": "trap"},
        "tesla_coil": {"name": "⚡ Tesla Coil", "price": 1500, "category": "trap"},
        
        # PERKS / BUFFS
        "2x_resources": {"name": "2️⃣ 2x Resources (1hr)", "price": 250, "category": "buff", "duration": 3600},
        "3x_xp": {"name": "💫 3x XP (1hr)", "price": 400, "category": "buff", "duration": 3600},
        "lucky_boost": {"name": "🍀 Lucky Boost (1hr)", "price": 350, "category": "buff", "duration": 3600},
        "speed_boost": {"name": "⚡ Speed Boost (1hr)", "price": 300, "category": "buff", "duration": 3600},
    }
    return items




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


@dp.message(_cmd("callout"))
async def cmd_callout(message: types.Message):
    """Challenge another player to a chess match. Forces them into a game."""
    if message.chat.type != "private":
        await message.answer("🃏 *GameMaster:* \"Issue challenges in *private*.\"", parse_mode="Markdown")
        return
    
    u_id = str(message.from_user.id)
    challenger = get_user(u_id)
    if not challenger:
        await _send_unreg_sticker(message)
        return
    
    # Parse target player ID or username
    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            "♟️ *CHESS CALLOUT*\n\n"
            "_Challenge another player to a match._\n\n"
            "Usage: `/callout @username` or `/callout userid`\n\n"
            "_The challenge is sent to them._",
            parse_mode="Markdown"
        )
        return
    
    target_username = args[1].lstrip("@")
    
    # Find target by username or ID
    # This would need DB support - for now, send notification
    await message.answer(
        f"♟️ *CALLOUT SENT!*\n\n"
        f"You've challenged *{target_username}* to a chess match!\n"
        f"_They have 5 minutes to accept or the challenge expires._\n\n"
        f"*Reward:* 500 points + bragging rights if you win!",
        parse_mode="Markdown"
    )
    print(f"[CALLOUT] {challenger.get('username', u_id)} challenged {target_username}")


@dp.message(_cmd("train"))
async def cmd_train(message: types.Message):
    """Train military units with queue and timers."""
    if message.chat.type != "private":
        await message.answer("⚔️ *GM:* \"Train troops in private.\"", parse_mode="Markdown")
        return
    
    u_id = str(message.from_user.id)
    user = get_user(u_id)
    if not user:
        await _send_unreg_sticker(message)
        return
    
    # Parse: !train [unit] [amount] or !train (show queue)
    args = message.text.strip().split()
    
    if len(args) == 1:  # Just !train - show status
        from training_system import format_training_status
        status = format_training_status(u_id)
        await message.answer(status, parse_mode="Markdown")
        return
    
    if len(args) < 3:
        from training_system import UNIT_NAMES, UNIT_COSTS, TRAINING_TIMES
        txt = "⚔️ *MILITARY ACADEMY*\n\n"
        txt += "Usage: `!train [unit] [amount]`\n\n"
        txt += "*Available Units:*\n"
        for unit_key, unit_name in UNIT_NAMES.items():
            cost = UNIT_COSTS[unit_key]
            cost_str = " + ".join([f"{amt}{res}" for res, amt in cost.items()])
            time = TRAINING_TIMES[unit_key]
            txt += f"\n{unit_name}\n├─ Cost: {cost_str}\n└─ Time: {time}s per unit\n"
        await message.answer(txt, parse_mode="Markdown")
        return
    
    unit_type = args[1].lower()
    try:
        amount = int(args[2])
    except:
        await message.answer("❌ Invalid amount", parse_mode="Markdown")
        return
    
    # Queue training
    from training_system import add_to_training_queue
    success, msg = add_to_training_queue(u_id, unit_type, amount)
    
    if success:
        await message.answer(f"✅ {msg}\n\nType `!train` to check progress", parse_mode="Markdown")
    else:
        await message.answer(f"❌ {msg}", parse_mode="Markdown")


@dp.message(_cmd("share"))
async def cmd_share(message: types.Message):
    """Share resources with alliance members."""
    if message.chat.type != "private":
        await message.answer("💝 *GM:* \"Share resources in private chat.\"", parse_mode="Markdown")
        return
    
    u_id = str(message.from_user.id)
    user = get_user(u_id)
    if not user:
        await _send_unreg_sticker(message)
        return
    
    # Parse: !share [amount] [resource] @member
    args = message.text.strip().split()
    
    if len(args) < 4:
        await message.answer(
            "💝 *SHARE RESOURCES*\n\n"
            "Usage: `!share [amount] [resource] @member`\n\n"
            "Example: `!share 50 wood @teammate`\n\n"
            "_(Both must be in same alliance)_",
            parse_mode="Markdown"
        )
        return
    
    try:
        amount = int(args[1])
        resource = args[2].lower()
        member_name = args[3].lstrip("@")
    except:
        await message.answer("❌ Invalid format", parse_mode="Markdown")
        return
    
    from alliance_system import share_resources
    success, msg = share_resources(u_id, member_name, resource, amount)
    
    if success:
        await message.answer(f"✅ {msg}", parse_mode="Markdown")
    else:
        await message.answer(f"❌ {msg}", parse_mode="Markdown")


@dp.message(_cmd("alliance"))
async def cmd_alliance(message: types.Message):
    """Manage alliance membership."""
    if message.chat.type != "private":
        await message.answer("👥 *GM:* \"Alliance management in private only.\"", parse_mode="Markdown")
        return
    
    u_id = str(message.from_user.id)
    user = get_user(u_id)
    if not user:
        await _send_unreg_sticker(message)
        return
    
    args = message.text.strip().split()
    
    if len(args) < 2:
        from alliance_system import format_alliance_status
        status = format_alliance_status(u_id)
        await message.answer(status, parse_mode="Markdown")
        return
    
    action = args[1].lower()
    
    if action == "create":
        if len(args) < 3:
            await message.answer("Usage: `!alliance create <name>`", parse_mode="Markdown")
            return
        alliance_name = " ".join(args[2:])
        from alliance_system import create_alliance
        success, msg = create_alliance(u_id, alliance_name)
        await message.answer(msg, parse_mode="Markdown")
    
    elif action == "join":
        if len(args) < 3:
            await message.answer("Usage: `!alliance join <id>`", parse_mode="Markdown")
            return
        alliance_id = args[2]
        from alliance_system import join_alliance
        success, msg = join_alliance(u_id, alliance_id)
        await message.answer(msg, parse_mode="Markdown")
    
    else:
        await message.answer("❌ Unknown action. Use: create or join", parse_mode="Markdown")


@dp.message(_cmd("mine"))
async def cmd_mine(message: types.Message):
    """Start mining operation in a sector."""
    if message.chat.type != "private":
        await message.answer("🃏 *GameMaster:* \"Mine in *private*.\"", parse_mode="Markdown"); return
    
    u_id = str(message.from_user.id)
    user = get_user(u_id)
    if not user:
        await message.answer("❌ Account not found.", parse_mode="Markdown"); return
    
    # Check if already mining
    buffs = user.get('buffs', {})
    if buffs.get('mining_active'):
        # Show mining progress
        await _show_mining_progress(message, u_id)
        return
    
    # Get military
    military = user.get('military', {})
    total_troops = sum(military.values())
    if total_troops == 0:
        await message.answer(
            "❌ You need troops to mine!\n\n"
            "Use `/train` to build your army first.",
            parse_mode="Markdown"
        ); return
    
    # Sector mining info
    sector_info = {
        1: {"name": "Badlands-8", "resources": ["wood", "bronze"], "min_troops": 5},
        2: {"name": "Crimson Wastes", "resources": ["bronze", "iron"], "min_troops": 10},
        3: {"name": "Obsidian Peaks", "resources": ["iron", "diamond"], "min_troops": 15},
        4: {"name": "Shattered Valley", "resources": ["bronze", "wood", "iron"], "min_troops": 8},
        5: {"name": "Frozen Abyss", "resources": ["iron", "diamond"], "min_troops": 20},
        6: {"name": "Molten Gorge", "resources": ["diamond", "relics"], "min_troops": 25},
        7: {"name": "Twilight Marshes", "resources": ["wood", "relics"], "min_troops": 18},
        8: {"name": "Silent Forest", "resources": ["wood", "bronze", "diamond"], "min_troops": 22},
        9: {"name": "Void Canyon", "resources": ["relics", "diamond", "iron"], "min_troops": 30}
    }
    
    # Show available sectors
    txt = f"{divider()}\n⛏️ *MINING OPERATIONS* ⛏️\n{divider()}\n\n"
    txt += f"💪 Your Army: *{total_troops} troops*\n\n"
    txt += "Available sectors (tap to mine):\n\n"
    
    rows = []
    user_level = 1 + (user.get('xp', 0) // 1000)
    for sector_id in range(1, 10):
        info = sector_info.get(sector_id, {})
        resources_str = ", ".join(info['resources'])
        min_troops = info['min_troops']
        
        # Check if unlocked
        if sector_id <= user_level:
            status = "✅" if total_troops >= min_troops else "❌"
            label = f"{status} #{sector_id} {info['name']}"
            rows.append([InlineKeyboardButton(
                text=label,
                callback_data=f"mine_sector_{sector_id}" if total_troops >= min_troops else "mining_locked"
            )])
        else:
            rows.append([InlineKeyboardButton(
                text=f"🔒 #{sector_id} {info['name']} (Unlocked at Level {sector_id})",
                callback_data="mining_locked"
            )])
    
    txt += f"{divider()}\n🃏 *GameMaster:* \"Send your troops to dig and plunder. The strong take resources, the weak... disappear.\""
    
    await message.answer(
        txt,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode="Markdown"
    )


@dp.message(_cmd("map"))
async def cmd_map(message: types.Message):
    """Show current location (current mining sector) or available sectors on the map."""
    if message.chat.type != "private":
        await message.answer("🃏 *GameMaster:* \"Check your map in *private*.\"", parse_mode="Markdown"); return
    
    u_id = str(message.from_user.id)
    user = get_user(u_id)
    if not user:
        await message.answer("❌ Account not found.", parse_mode="Markdown"); return
    
    # Sector info
    sector_info = {
        1: {"name": "Badlands-8", "resources": ["wood", "bronze"], "emoji": "🏜️"},
        2: {"name": "Crimson Wastes", "resources": ["bronze", "iron"], "emoji": "🔴"},
        3: {"name": "Obsidian Peaks", "resources": ["iron", "diamond"], "emoji": "⛰️"},
        4: {"name": "Shattered Valley", "resources": ["bronze", "wood", "iron"], "emoji": "💔"},
        5: {"name": "Frozen Abyss", "resources": ["iron", "diamond"], "emoji": "❄️"},
        6: {"name": "Molten Gorge", "resources": ["diamond", "relics"], "emoji": "🔥"},
        7: {"name": "Twilight Marshes", "resources": ["wood", "relics"], "emoji": "🌙"},
        8: {"name": "Silent Forest", "resources": ["wood", "bronze", "diamond"], "emoji": "🌲"},
        9: {"name": "Void Canyon", "resources": ["relics", "diamond", "iron"], "emoji": "🌑"}
    }
    
    # Check if currently mining
    buffs = user.get('buffs', {})
    if buffs.get('mining_active'):
        sector_id = buffs.get('mining_sector', 0)
        info = sector_info.get(sector_id, {})
        start_time_str = buffs.get('mining_start_time')
        
        if start_time_str:
            start_time = datetime.fromisoformat(start_time_str)
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            total_duration = 600
            remaining = max(0, total_duration - elapsed)
            progress_pct = min(100, int((elapsed / total_duration) * 100))
            bar = progress_bar(progress_pct, 20)
            
            txt = f"{divider()}\n[ 🗺️ *YOUR LOCATION* 🗺️ ]\n{divider()}\n\n"
            txt += f"{info.get('emoji', '📍')} **{info.get('name', 'Unknown')}**\n"
            txt += f"🌍 Sector {sector_id}\n\n"
            txt += f"*Resources Available:* {', '.join(info.get('resources', []))}\n\n"
            txt += f"⏱️ Mining Progress ({int(remaining)}s remaining):\n"
            txt += f"{bar} {progress_pct}%\n\n"
            txt += f"💪 Troops sent: {buffs.get('mining_troops', 0)}\n"
            txt += f"{divider()}"
            
            await message.answer(txt, parse_mode="Markdown")
            return
    
    # Not mining - show map of all sectors
    user_level = 1 + (user.get('xp', 0) // 1000)
    
    txt = f"{divider()}\n🗺️ *SECTOR MAP* 🗺️\n{divider()}\n\n"
    txt += f"📊 Your Level: *{user_level}*\n"
    txt += f"🔓 Unlocked Sectors: *1-{min(user_level, 9)}*\n\n"
    txt += "*AVAILABLE SECTORS:*\n"
    
    for sector_id in range(1, 10):
        info = sector_info.get(sector_id, {})
        emoji = info.get('emoji', '📍')
        name = info.get('name', 'Unknown')
        resources = ", ".join(info.get('resources', []))
        
        if sector_id <= user_level:
            txt += f"{emoji} **#{sector_id} {name}**\n"
            txt += f"   🏭 Resources: {resources}\n"
        else:
            txt += f"🔒 **#{sector_id} {name}** (Unlock at Level {sector_id})\n"
            txt += f"   🏭 Resources: {resources}\n"
        
        txt += "\n"
    
    txt += f"{divider()}\n🃏 *GameMaster:* \"The world is your battlefield. Claim it.\""
    
    await message.answer(txt, parse_mode="Markdown")


@dp.message(_cmd("teleport"))
async def cmd_teleport(message: types.Message):
    """Teleport to a sector with detailed information about buffs, perks, hazards, and drops."""
    if message.chat.type != "private":
        await message.answer("🃏 *GameMaster:* \"Teleport in *private*.\"", parse_mode="Markdown"); return
    
    u_id = str(message.from_user.id)
    user = get_user(u_id)
    if not user:
        await message.answer("❌ Account not found.", parse_mode="Markdown"); return
    
    # Parse sector number from command (optional)
    parts = message.text.strip().split()
    sector_id = None
    if len(parts) > 1:
        try:
            sector_id = int(parts[1])
            if sector_id < 1 or sector_id > 9:
                await message.answer("❌ Sector must be between 1-9", parse_mode="Markdown"); return
        except (ValueError, IndexError):
            pass
    
    # If no sector specified, use random
    if not sector_id:
        sector_id = random.randint(1, 9)
    
    # Import sector system
    from sector_info import get_sector_info, format_sector_display
    
    # Get sector info
    sector = get_sector_info(sector_id)
    if not sector:
        await message.answer("❌ Sector not found", parse_mode="Markdown"); return
    
    # Update user's current sector
    user['sector'] = sector_id
    save_user(u_id, user)
    
    # Send detailed sector information
    detailed_info = format_sector_display(sector_id, divider)
    await message.answer(detailed_info, parse_mode="Markdown")
    
    # Send confirmation
    confirmation = f"\n🌀 *TELEPORTED TO SECTOR {sector_id}*\n\n🃏 *GameMaster:* \"Welcome to {sector['name']}. May fortune favor the bold.\"\n"
    await message.answer(confirmation, parse_mode="Markdown")
    
    # ═══════════════════════════════════════════════════════════════════════════
    #  CHECK FOR RANDOM BANDIT ENCOUNTER
    # ═══════════════════════════════════════════════════════════════════════════
    player_level = user.get('level', 1)
    should_attack, reason = should_trigger_bandit_attack(player_level, sector_id)
    
    if should_attack:
        # Generate encounter
        encounter = generate_bandit_encounter(sector_id, player_level)
        
        # Store encounter for later battle handling
        user['current_encounter'] = encounter
        save_user(u_id, user)
        
        # Send narrative + call to action
        encounter_msg = format_bandit_encounter(encounter)
        await message.answer(encounter_msg, parse_mode="Markdown")
        
        # Send defensive action buttons
        defend_kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🛡️ DEFEND!", callback_data=f"defend_bandit_{u_id}"),
                InlineKeyboardButton(text="💨 FLEE", callback_data=f"flee_bandit_{u_id}"),
            ]
        ])
        
        await message.answer(
            f"⚠️ *WHAT WILL YOU DO?*\n\n"
            f"🛡️ *DEFEND* - Activate your shields, troops, and items to fight\n"
            f"💨 *FLEE* - Abandon this sector (lose some resources)",
            reply_markup=defend_kb,
            parse_mode="Markdown"
        )
    
    # Announce to group
    announcement = f"📍 {message.from_user.first_name} teleported to Sector {sector_id} ({sector['name']})! {sector['emoji']}"
    try:
        await bot.send_message(CHECKMATE_HQ_GROUP_ID, announcement)
    except:
        pass


async def _show_mining_progress(message: types.Message, u_id: str):
    """Display current mining progress."""
    user = get_user(u_id)
    if not user:
        return
    
    buffs = user.get('buffs', {})
    if not buffs.get('mining_active'):
        await message.answer("⛏️ You are not currently mining.", parse_mode="Markdown")
        return
    
    sector_id = buffs.get('mining_sector', 0)
    troop_count = buffs.get('mining_troops', 0)
    start_time_str = buffs.get('mining_start_time')
    drops = buffs.get('mining_drops', [])
    
    if not start_time_str:
        await message.answer("⛏️ Mining data corrupted. Please restart.", parse_mode="Markdown")
        return
    
    # Calculate elapsed time
    start_time = datetime.fromisoformat(start_time_str)
    elapsed = (datetime.utcnow() - start_time).total_seconds()
    total_duration = 600  # 10 minutes
    remaining = max(0, total_duration - elapsed)
    
    # Create progress bar
    progress_pct = min(100, int((elapsed / total_duration) * 100))
    bar = progress_bar(progress_pct, 20)
    
    # Build message
    txt = f"{divider()}\n⛏️ *MINING IN PROGRESS* ⛏️\n{divider()}\n\n"
    txt += f"📍 Sector {sector_id}\n"
    txt += f"💪 Troops: {troop_count}\n"
    txt += f"⏱️ Time remaining: {int(remaining)}s\n\n"
    txt += f"Progress:\n{bar} {progress_pct}%\n\n"
    
    if drops:
        txt += f"📦 *Resources Found:*\n"
        for drop in drops:
            txt += f"├─ +{drop['amount']} {drop['resource']}\n"
        txt += "\n"
    
    if remaining <= 0:
        txt += "✅ *Mining Complete!* Check your inventory for results."
        # Finalize mining
        await _finalize_mining(u_id, sector_id, troop_count)
    else:
        txt += f"_{int(remaining // 60)} min {int(remaining % 60)}s remaining_"
    
    await message.answer(txt, parse_mode="Markdown")


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
            "bitcoin_multiplier": lambda m: f"💎 BITCOIN MULTIPLIER x{m}",
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
            "bitcoin_multiplier": lambda m: f"💎 BITCOIN MULTIPLIER x{m}",
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
    """Activate multiplier with selected tier and quantity."""
    try:
        import re
        # Parse: activate_mult_ITEMID_MULTIPLIER_QUANTITY
        m = re.search(r'activate_mult_(\d+)_(\d+)_(\d+)', callback.data)
        if not m:
            await callback.answer("❌ Invalid format.", show_alert=True)
            return
        item_id = int(m.group(1))
        multiplier = int(m.group(2))  # 2-10
        quantity = int(m.group(3))    # How many guesses
        
        # Validate multiplier is in range 2-10
        if not (2 <= multiplier <= 10):
            await callback.answer("❌ Invalid multiplier tier.", show_alert=True)
            return
        
        u_id = str(callback.from_user.id)
        inv = get_inventory(u_id)
        item = next((it for it in inv if it.get('id') == item_id), None)
        
        if not item or "multiplier" not in item.get('type', '').lower():
            await callback.answer("❌ Item not found or not a multiplier.", show_alert=True)
            return
        
        kind = "XP" if "xp" in item.get('type', '').lower() else "BITCOIN"
        
        # Activate the multiplier (store in buffs JSONB)
        user = get_user(u_id)
        #if user:
         #   buffs = user.get('buffs', {})
          #  buffs['multiplier_type'] = kind.lower()
         #   buffs['multiplier_active'] = multiplier  # Store 2-10
          #  buffs['multiplier_count'] = quantity      # How many times to apply
           # user['buffs'] = buffs
           # save_user(u_id, user)
        
        #remove_inventory_item(u_id, item_id)
        
        #await callback.message.edit_text(
        #    f"⚡ *{kind} MULTIPLIER x{multiplier} ACTIVATED!*\n\n"
        #    f"Your next {quantity} word guesses apply **x{multiplier} {kind}**!\n\n"
        #    f"🃏 *GameMaster:* \"Each word will show *{kind} x{multiplier}* in the feedback. Make them count.\"",
        #    parse_mode="Markdown"
        #)
        #await callback.answer()
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
                    kind = "XP" if "xp" in itype else "BITCOIN"
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


@dp.callback_query(F.data.startswith("train_"))
async def cb_train_unit(callback: types.CallbackQuery):
    """Handle unit training selection."""
    try:
        unit_key = callback.data.replace("train_", "")
        u_id = str(callback.from_user.id)
        user = get_user(u_id)
        
        if not user:
            await callback.answer("❌ User not found.", show_alert=True)
            return
        
        # Unit definitions with costs
        units = {
            "Police and Dogs": {"name": "👹 Police and Dogs", "cost": {"wood": 5}},
            "knight": {"name": "🗡️ Knights", "cost": {"wood": 15, "bronze": 5}},
            "bishop": {"name": "⚜️ Bishops", "cost": {"bronze": 10, "iron": 3}},
            "rook": {"name": "🏰 Rooks", "cost": {"iron": 10, "diamond": 2}},
            "queen": {"name": "👑 Queens", "cost": {"iron": 20, "diamond": 5}},
            "king": {"name": "⚔️ Kings", "cost": {"diamond": 15, "relics": 1}}
        }
        
        if unit_key not in units:
            await callback.answer("❌ Unknown unit.", show_alert=True)
            return
        
        unit = units[unit_key]
        cost_str = " + ".join([f"{amt} {res.upper()}" for res, amt in unit['cost'].items()])
        
        # Show quantity selector
        await callback.message.edit_text(
            f"🎯 *{unit['name']}* Training\n\n"
            f"Cost per unit: {cost_str}\n\n"
            f"How many {unit['name'].lower()} do you want to train?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="5", callback_data=f"train_confirm_{unit_key}_5"),
                 InlineKeyboardButton(text="10", callback_data=f"train_confirm_{unit_key}_10"),
                 InlineKeyboardButton(text="20", callback_data=f"train_confirm_{unit_key}_20")],
                [InlineKeyboardButton(text="50", callback_data=f"train_confirm_{unit_key}_50"),
                 InlineKeyboardButton(text="100", callback_data=f"train_confirm_{unit_key}_100")]
            ]),
            parse_mode="Markdown"
        )
        await callback.answer()
    except Exception as e:
        print(f"[CB_TRAIN ERROR] {e}")
        await callback.answer(f"❌ Error: {str(e)}", show_alert=True)


@dp.callback_query(F.data.startswith("train_confirm_"))
async def cb_train_confirm(callback: types.CallbackQuery):
    """Confirm unit training and deduct resources."""
    try:
        import re
        m = re.search(r'train_confirm_(\w+)_(\d+)', callback.data)
        if not m:
            await callback.answer("❌ Invalid format.", show_alert=True)
            return
        
        unit_key = m.group(1)
        quantity = int(m.group(2))
        u_id = str(callback.from_user.id)
        user = get_user(u_id)
        
        if not user:
            await callback.answer("❌ User not found.", show_alert=True)
            return
        
        # Unit costs
        units = {
            "Police and Dogs": {"name": "👹 Police and Dogs", "cost": {"wood": 5}},
            "knight": {"name": "🗡️ Knights", "cost": {"wood": 15, "bronze": 5}},
            "bishop": {"name": "⚜️ Bishops", "cost": {"bronze": 10, "iron": 3}},
            "rook": {"name": "🏰 Rooks", "cost": {"iron": 10, "diamond": 2}},
            "queen": {"name": "👑 Queens", "cost": {"iron": 20, "diamond": 5}},
            "king": {"name": "⚔️ Kings", "cost": {"diamond": 15, "relics": 1}}
        }
        
        if unit_key not in units:
            await callback.answer("❌ Unknown unit.", show_alert=True)
            return
        
        unit = units[unit_key]
        base_res = user.get('base_resources', {})
        resources = base_res.get('resources', {})
        
        # Check if enough resources
        for res_type, cost_per_unit in unit['cost'].items():
            total_cost = cost_per_unit * quantity
            available = resources.get(res_type, 0) if res_type != 'food' else base_res.get('food', 0)
            if available < total_cost:
                await callback.answer(
                    f"❌ Need {total_cost} {res_type.upper()}, only have {available}",
                    show_alert=True
                )
                return
        
        # Deduct resources
        for res_type, cost_per_unit in unit['cost'].items():
            total_cost = cost_per_unit * quantity
            resources[res_type] = resources.get(res_type, 0) - total_cost
        
        # Add troops
        military = user.get('military', {})
        military[unit_key] = military.get(unit_key, 0) + quantity
        
        # Save
        user['military'] = military
        base_res['resources'] = resources
        user['base_resources'] = base_res
        save_user(u_id, user)
        
        await callback.message.edit_text(
            f"✅ *TRAINING COMPLETE!*\n\n"
            f"🎖️ +{quantity} {unit['name'].lower()}\n\n"
            f"Your army grows stronger. The weak tremble.",
            parse_mode="Markdown"
        )
        await callback.answer()
    except Exception as e:
        print(f"[CB_TRAIN_CONFIRM ERROR] {e}")
        await callback.answer(f"❌ Error: {str(e)}", show_alert=True)


@dp.callback_query(F.data == "mining_locked")
async def cb_mining_locked(callback: types.CallbackQuery):
    await callback.answer("Sector unlocked when you reach that level!", show_alert=True)


@dp.callback_query(F.data.startswith("mine_sector_"))
async def cb_mine_sector(callback: types.CallbackQuery):
    """Setup mining operation."""
    try:
        import re
        m = re.search(r'mine_sector_(\d+)', callback.data)
        if not m:
            await callback.answer("❌ Invalid sector.", show_alert=True)
            return
        
        sector_id = int(m.group(1))
        u_id = str(callback.from_user.id)
        user = get_user(u_id)
        
        if not user:
            await callback.answer("❌ User not found.", show_alert=True)
            return
        
        # Sector info
        sector_info = {
            1: {"name": "Badlands-8", "resources": ["wood", "bronze"], "min_troops": 5, "multiplier": 1.0},
            2: {"name": "Crimson Wastes", "resources": ["bronze", "iron"], "min_troops": 10, "multiplier": 1.2},
            3: {"name": "Obsidian Peaks", "resources": ["iron", "diamond"], "min_troops": 15, "multiplier": 1.5},
            4: {"name": "Shattered Valley", "resources": ["bronze", "wood", "iron"], "min_troops": 8, "multiplier": 1.1},
            5: {"name": "Frozen Abyss", "resources": ["iron", "diamond"], "min_troops": 20, "multiplier": 1.25},
            6: {"name": "Molten Gorge", "resources": ["diamond", "relics"], "min_troops": 25, "multiplier": 1.6},
            7: {"name": "Twilight Marshes", "resources": ["wood", "relics"], "min_troops": 18, "multiplier": 1.3},
            8: {"name": "Silent Forest", "resources": ["wood", "bronze", "diamond"], "min_troops": 22, "multiplier": 1.35},
            9: {"name": "Void Canyon", "resources": ["relics", "diamond", "iron"], "min_troops": 30, "multiplier": 2.0}
        }
        
        if sector_id not in sector_info:
            await callback.answer("❌ Invalid sector.", show_alert=True)
            return
        
        info = sector_info[sector_id]
        military = user.get('military', {})
        total_troops = sum(military.values())
        
        if total_troops < info['min_troops']:
            await callback.answer(
                f"❌ Need {info['min_troops']} troops, you have {total_troops}",
                show_alert=True
            )
            return
        
        # Show troop selection
        await callback.message.edit_text(
            f"⛏️ *{info['name']}* (Sector {sector_id})\n\n"
            f"Available Resources: {', '.join(info['resources'])}\n"
            f"Minimum Troops Required: {info['min_troops']}\n"
            f"You Have: {total_troops} troops\n\n"
            f"How many troops to send mining?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"{info['min_troops']}", callback_data=f"mine_start_{sector_id}_{info['min_troops']}"),
                 InlineKeyboardButton(text=f"{int(total_troops*0.5)}", callback_data=f"mine_start_{sector_id}_{int(total_troops*0.5)}"),
                 InlineKeyboardButton(text=f"{total_troops}", callback_data=f"mine_start_{sector_id}_{total_troops}")]
            ]),
            parse_mode="Markdown"
        )
        await callback.answer()
    except Exception as e:
        print(f"[CB_MINE_SECTOR ERROR] {e}")
        await callback.answer(f"❌ Error: {str(e)}", show_alert=True)


@dp.callback_query(F.data.startswith("mine_start_"))
async def cb_mine_start(callback: types.CallbackQuery):
    """Start mining operation."""
    try:
        import re
        m = re.search(r'mine_start_(\d+)_(\d+)', callback.data)
        if not m:
            await callback.answer("❌ Invalid format.", show_alert=True)
            return
        
        sector_id = int(m.group(1))
        troop_count = int(m.group(2))
        u_id = str(callback.from_user.id)
        user = get_user(u_id)
        
        if not user:
            await callback.answer("❌ User not found.", show_alert=True)
            return
        
        # Sector info with resources
        sector_info = {
            1: {"name": "Badlands-8", "resources": ["wood", "bronze"], "multiplier": 1.0},
            2: {"name": "Crimson Wastes", "resources": ["bronze", "iron"], "multiplier": 1.2},
            3: {"name": "Obsidian Peaks", "resources": ["iron", "diamond"], "multiplier": 1.5},
            4: {"name": "Shattered Valley", "resources": ["bronze", "wood", "iron"], "multiplier": 1.1},
            5: {"name": "Frozen Abyss", "resources": ["iron", "diamond"], "multiplier": 1.25},
            6: {"name": "Molten Gorge", "resources": ["diamond", "relics"], "multiplier": 1.6},
            7: {"name": "Twilight Marshes", "resources": ["wood", "relics"], "multiplier": 1.3},
            8: {"name": "Silent Forest", "resources": ["wood", "bronze", "diamond"], "multiplier": 1.35},
            9: {"name": "Void Canyon", "resources": ["relics", "diamond", "iron"], "multiplier": 2.0}
        }
        
        # Generate 5 mining drops (one every 2 minutes for 10 minutes)
        drops = []
        info = sector_info.get(sector_id, {})
        multiplier = info.get('multiplier', 1.0)
        resources_available = info.get('resources', [])
        
        for drop_num in range(5):
            # Vary amount based on troops sent (more troops = more resources)
            troop_factor = max(1, troop_count // 10)
            
            drop = {}
            for i, res in enumerate(resources_available):
                # Base amount scales with troops
                base_amount = 5 + (troop_count // 15)
                # Apply sector multiplier
                amount = int(base_amount * multiplier)
                # Randomize ±20%
                amount = int(amount * random.uniform(0.8, 1.2))
                
                drop[res] = max(1, amount)
            
            drops.append(drop)
        
        # Start mining
        buffs = user.get('buffs', {})
        buffs['mining_active'] = True
        buffs['mining_sector'] = sector_id
        buffs['mining_troops'] = troop_count
        buffs['mining_start_time'] = datetime.utcnow().isoformat()
        buffs['mining_drops'] = []  # Will be populated as drops occur
        buffs['mining_schedule'] = drops  # Store the drops to be awarded
        user['buffs'] = buffs
        save_user(u_id, user)
        
        # Award first drop immediately
        first_drop = drops[0]
        base_res = user.get('base_resources', {})
        if not isinstance(base_res, dict):
            base_res = {'resources': {}, 'food': 0}
        
        resources = base_res.get('resources', {})
        if not isinstance(resources, dict):
            resources = {}
        
        for res_type, amount in first_drop.items():
            resources[res_type] = resources.get(res_type, 0) + amount
        
        base_res['resources'] = resources
        
        # Deduct troops from military (they're now mining)
        military = user.get('military', {})
        troops_left = troop_count
        for unit_type in ["king", "queen", "rook", "bishop", "knight", "Police and Dogs"]:
            if troops_left <= 0:
                break
            available = military.get(unit_type, 0)
            to_send = min(available, troops_left)
            military[unit_type] -= to_send
            troops_left -= to_send
        
        user['military'] = military
        user['base_resources'] = base_res
        
        # Store mining drop history
        mining_drops_log = buffs.get('mining_drops', [])
        mining_drops_log.append({
            'resource': list(first_drop.keys())[0] if first_drop else 'unknown',
            'amount': list(first_drop.values())[0] if first_drop else 0
        })
        buffs['mining_drops'] = mining_drops_log
        user['buffs'] = buffs
        save_user(u_id, user)
        
        # Build progress message
        drop_str = " + ".join([f"{amt} {res}" for res, amt in first_drop.items()])
        
        await callback.message.edit_text(
            f"⛏️ *MINING STARTED*\n\n"
            f"📍 Sector {sector_id} ({info.get('name', 'Unknown')})\n"
            f"💪 Troops Deployed: {troop_count}\n"
            f"⏱️ Duration: 10 minutes\n\n"
            f"📦 *First Drop Acquired:*\n"
            f"{drop_str}\n\n"
            f"_New drops every 2 minutes..._",
            parse_mode="Markdown"
        )
        await callback.answer("⛏️ Mining operation started!")
    except Exception as e:
        print(f"[CB_MINE_START ERROR] {e}")
        await callback.answer(f"❌ Error: {str(e)}", show_alert=True)


@dp.callback_query(F.data.startswith("confirm_attack_"))
async def cb_confirm_attack(callback: types.CallbackQuery):
    """Handle confirmed attack with shield deactivation."""
    try:
        import re
        m = re.search(r'confirm_attack_(\d+)_(\d+)', callback.data)
        if not m:
            await callback.answer("❌ Invalid format.", show_alert=True)
            return
        
        attacker_id = m.group(1)
        target_id = m.group(2)
        u_id = str(callback.from_user.id)
        
        # Verify the attacker is the one clicking
        if u_id != attacker_id:
            await callback.answer("❌ You are not the attacker!", show_alert=True)
            return
        
        attacker = get_user(attacker_id)
        if not attacker:
            await callback.answer("❌ Attacker not found.", show_alert=True)
            return
        
        target = get_user(target_id)
        if not target:
            await callback.answer("❌ Target not found.", show_alert=True)
            return
        
        target_display_name = target.get("username", "Unknown")
        
        # Edit message to show processing
        await callback.message.edit_text(
            f"⚔️ *ATTACK INITIATED*\n\n"
            f"🛡️ Deactivating shield...\n"
            f"💨 Processing battle...",
            parse_mode="Markdown"
        )
        
        # Execute the attack
        await _execute_attack(attacker_id, target_id, target_display_name, callback.message)
        
        await callback.answer("⚔️ Attack executed!")
    except Exception as e:
        print(f"[CB_CONFIRM_ATTACK ERROR] {e}")
        await callback.answer(f"❌ Error: {str(e)}", show_alert=True)


@dp.callback_query(F.data == "cancel_attack")
async def cb_cancel_attack(callback: types.CallbackQuery):
    """Cancel the attack and keep shield active."""
    try:
        await callback.message.edit_text(
            f"❌ *ATTACK CANCELLED*\n\n"
            f"🛡️ Your shield remains **ACTIVE**.\n"
            f"_Battle averted._",
            parse_mode="Markdown"
        )
        await callback.answer("✅ Attack cancelled. Shield remains active.")
    except Exception as e:
        print(f"[CB_CANCEL_ATTACK ERROR] {e}")
        await callback.answer(f"❌ Error: {str(e)}", show_alert=True)


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
        uid_str = str(uid)
        user_info = get_user(uid_str)
        username = user_info.get("username", f"Player {uid}") if user_info else f"Player {uid}"
        eng.crate_claimers.append({'user_id': uid_str, 'username': username})
        if getattr(eng, 'is_current_crate_decoy', False):
            eng.decoy_claimers.append({'user_id': uid_str, 'username': username})
            if user_info:
                user_info['bitcoin'] = max(0, user_info.get('bitcoin', 0) - 100)
                save_user(uid_str, user_info)
                # Send group notification (fire and forget using asyncio to avoid holding up reaction)
                asyncio.create_task(bot.send_message(
                    event.chat.id,
                    f"⚠️ *MONKEY TRAP!* {username} grabbed a decoy crate and lost *100 Bitcoin*! 💣",
                    parse_mode="Markdown"
                ))

# ═══════════════════════════════════════════════════════════════════════════
#  BANDIT ENCOUNTER HANDLERS
# ═══════════════════════════════════════════════════════════════════════════

@dp.callback_query(F.data.startswith("defend_bandit_"))
async def cb_defend_bandit(callback: types.CallbackQuery):
    """Defend against bandit attack - initiate battle."""
    try:
        u_id = callback.data.split("_")[2]
        
        if str(callback.from_user.id) != u_id:
            await callback.answer("❌ This isn't your encounter!", show_alert=True)
            return
        
        user = get_user(u_id)
        if not user:
            await callback.answer("❌ User not found.", show_alert=True)
            return
        
        encounter = user.get("current_encounter")
        if not encounter:
            await callback.answer("❌ No active encounter.", show_alert=True)
            return
        
        # Calculate defense strength
        player_defense = calculate_defense_strength(user)
        bandit_attack = encounter.get("attack", 15)
        
        # Show battle message
        await callback.message.edit_text(
            f"⚔️ *BATTLE INITIATED* ⚔️\n\n"
            f"Your Defense: **{player_defense}**\n"
            f"Enemy Attack: **{bandit_attack}**\n\n"
            f"_Rolling dice..._\n"
            f"_Calling upon your troops, shields, and every ounce of courage..._",
            parse_mode="Markdown"
        )
        
        # Simulate battle
        result = calculate_battle_outcome_vs_bandit(player_defense, bandit_attack)
        
        # Format battle report
        battle_report = format_battle_description(user, encounter, result)
        
        # Wait a moment for dramatic effect
        await asyncio.sleep(1)
        
        # Send battle outcome
        await callback.message.reply(battle_report, parse_mode="Markdown")
        
        if result["player_won"]:
            # Victory - give loot
            loot = encounter.get("original_loot", {})
            base_res = user.get("base_resources", {})
            if not isinstance(base_res, dict):
                base_res = {"resources": {}, "food": 0}
            
            resources = base_res.get("resources", {})
            if not isinstance(resources, dict):
                resources = {}
            
            for res_type, amount in loot.items():
                resources[res_type] = resources.get(res_type, 0) + amount
            
            base_res["resources"] = resources
            user["base_resources"] = base_res
            
            # Award victory bonus XP
            add_xp(u_id, 250)
            add_points(u_id, 500, user.get("username", "Unknown"))
            
            victory_msg = f"\n🏆 *VICTORY REWARDS*:\n+250 XP\n+500 Points"
            for res, amt in loot.items():
                victory_msg += f"\n+{amt} {res.upper()}"
            
            await callback.message.reply(victory_msg, parse_mode="Markdown")
            
            # Broadcast victory
            try:
                await bot.send_message(
                    CHECKMATE_HQ_GROUP_ID,
                    f"🏆 *HEROIC VICTORY* 🏆\n\n"
                    f"⚔️ {user.get('username', 'Unknown')} defeated the {encounter.get('bandit_name', 'Bandit')}!\n"
                    f"📍 Sector {encounter.get('sector_id', '?')}: {encounter.get('sector_name', 'Unknown')}\n"
                    f"💎 Legend is born!\n"
                )
            except:
                pass
        
        else:
            # Defeat - lose resources/troops
            base_res = user.get("base_resources", {})
            if not isinstance(base_res, dict):
                base_res = {}
            
            resources = base_res.get("resources", {})
            if isinstance(resources, dict):
                for res_type in resources:
                    resources[res_type] = int(resources[res_type] * 0.7)  # Lose 30%
            
            military = user.get("military", {})
            if isinstance(military, dict):
                for unit_type in military:
                    military[unit_type] = int(military[unit_type] * 0.8)  # Lose 20%
            
            base_res["resources"] = resources
            user["base_resources"] = base_res
            user["military"] = military
            
            defeat_msg = f"\n💀 *DEFEAT LOSSES*:\n-30% resources stolen\n-20% troops lost"
            await callback.message.reply(defeat_msg, parse_mode="Markdown")
            
            # Broadcast defeat
            try:
                await bot.send_message(
                    CHECKMATE_HQ_GROUP_ID,
                    f"💀 *SECTOR DEFEAT* 💀\n\n"
                    f"⚔️ {user.get('username', 'Unknown')} was defeated by the {encounter.get('bandit_name', 'Bandit')}!\n"
                    f"📍 Sector {encounter.get('sector_id', '?')}: {encounter.get('sector_name', 'Unknown')}\n"
                    f"📉 Resources and troops lost in battle.\n"
                )
            except:
                pass
        
        # Clear current encounter
        user.pop("current_encounter", None)
        save_user(u_id, user)
        
        await callback.answer("⚔️ Battle resolved!")
    except Exception as e:
        print(f"[CB_DEFEND_BANDIT ERROR] {e}")
        await callback.answer(f"❌ Error during battle: {str(e)[:50]}", show_alert=True)


@dp.callback_query(F.data.startswith("flee_bandit_"))
async def cb_flee_bandit(callback: types.CallbackQuery):
    """Flee from bandit encounter - lose some resources."""
    try:
        u_id = callback.data.split("_")[2]
        
        if str(callback.from_user.id) != u_id:
            await callback.answer("❌ This isn't your encounter!", show_alert=True)
            return
        
        user = get_user(u_id)
        if not user:
            await callback.answer("❌ User not found.", show_alert=True)
            return
        
        encounter = user.get("current_encounter")
        if not encounter:
            await callback.answer("❌ No active encounter.", show_alert=True)
            return
        
        # You flee but lose some resources
        base_res = user.get("base_resources", {})
        if not isinstance(base_res, dict):
            base_res = {}
        
        resources = base_res.get("resources", {})
        if isinstance(resources, dict):
            for res_type in resources:
                resources[res_type] = int(resources[res_type] * 0.85)  # Lose 15%
        
        base_res["resources"] = resources
        user["base_resources"] = base_res
        user.pop("current_encounter", None)
        save_user(u_id, user)
        
        narrative = get_sector_narrative(encounter.get("sector_id", 1))
        
        flee_msg = f"\n💨 *YOU FLED* 💨\n\n" \
                   f"You abandon the sector, running for your life...\n" \
                   f"_{narrative.get('reason_for_attack', 'You escaped... barely.')}_\n\n" \
                   f"📉 *Losses:* -15% resources in panicked escape\n\n" \
                   f"🃏 *GameMaster:* \"Cowardice has a price. Next time, stand and fight.\""
        
        await callback.message.edit_text(flee_msg, parse_mode="Markdown")
        
        # Broadcast flee
        try:
            await bot.send_message(
                CHECKMATE_HQ_GROUP_ID,
                f"💨 *SHAMEFUL RETREAT* 💨\n\n"
                f"🏃 {user.get('username', 'Unknown')} fled from the {encounter.get('bandit_name', 'Bandit')}!\n"
                f"📍 Sector {encounter.get('sector_id', '?')}: {encounter.get('sector_name', 'Unknown')}\n"
                f"😰 Cowardice carries a cost...\n"
            )
        except:
            pass
        
        await callback.answer("💨 Fled successfully!")
    except Exception as e:
        print(f"[CB_FLEE_BANDIT ERROR] {e}")
        await callback.answer(f"❌ Error: {str(e)[:50]}", show_alert=True)


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

    # Bitcoin reward by tier
    bitcoin = 0
    if 'wood'   in ctype: bitcoin = random.randint(2, 8)
    elif 'bronze' in ctype: bitcoin = random.randint(5, 15)
    elif 'iron'   in ctype: bitcoin = random.randint(10, 30)
    elif 'super'  in ctype: bitcoin = random.randint(15, 50)

    add_xp(user_id, xp)
    if bitcoin: add_bitcoin(user_id, bitcoin)
    remove_inventory_item(user_id, item_id)

    msg = f"✨ *CRATE OPENED!*\n📦 {cname}\n+{xp} XP"
    if bitcoin: msg += f"\n+{bitcoin} Bitcoin"
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
        kind = "XP" if "xp" in itype else "BITCOIN"
        # Ask user to select multiplier strength (2x to 10x)
        await message.answer(
            f"⚡ *{kind} MULTIPLIER*\n\n"
            f"Select the multiplier strength for this round:\n"
            f"_(Each applies to all words until uses are exhausted)_",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="2x", callback_data=f"activate_mult_{item_id}_2_5"),
                 InlineKeyboardButton(text="3x", callback_data=f"activate_mult_{item_id}_3_5"),
                 InlineKeyboardButton(text="4x", callback_data=f"activate_mult_{item_id}_4_5")],
                [InlineKeyboardButton(text="5x", callback_data=f"activate_mult_{item_id}_5_5"),
                 InlineKeyboardButton(text="6x", callback_data=f"activate_mult_{item_id}_6_3"),
                 InlineKeyboardButton(text="7x", callback_data=f"activate_mult_{item_id}_7_2")],
                [InlineKeyboardButton(text="8x", callback_data=f"activate_mult_{item_id}_8_2"),
                 InlineKeyboardButton(text="9x", callback_data=f"activate_mult_{item_id}_9_1"),
                 InlineKeyboardButton(text="10x", callback_data=f"activate_mult_{item_id}_10_1")]
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





import html as _html

# ── Safe username helper ─────────────────────────────────────────────────
def _safe_name(name: str) -> str:
    """Escape HTML special chars and strip emojis that break HTML parse mode."""
    if not name:
        return "Player"
    try:
        # Escape HTML entities first
        escaped = _html.escape(str(name))
        return escaped
    except Exception:
        return "Player"


def build_player_dashboard(player_name: str, session: dict, user_id: str = None, has_jammer: bool = False) -> str:
    """Build an HTML-formatted in-text dashboard for a player's round stats."""
    last_word = session.get('last_word', '???')
    total_pts = session.get('pts', 0)
    total_xp = session.get('xp', 0)
    word_count = session.get('word_count', 0)
    streak = session.get('streak', 0)
    food = session.get('food', 0)
    resources = session.get('resources', {})
    last_pts = session.get('last_pts', 0)
    rare_msg = session.get('rare_message', '')

    safe_player_name = _safe_name(player_name)

    res_parts = []
    for key, emoji in [('wood','🪵'),('bronze','🧱'),('iron','⛓️'),('diamond','💎'),('relics','🏺')]:
        val = resources.get(key, 0)
        if val > 0:
            res_parts.append(f"{emoji}{val}")

    extras = []
    if res_parts:
        extras.append("  ".join(res_parts))
    if food > 0:
        extras.append(f"🌽{food}")
    if streak >= 3:
        extras.append(f"🔥x{streak}")
    extras_line = "  ".join(extras)

    dashboard = ""
    if user_id:
        try:
            active_perks = format_active_perks(user_id)
            if active_perks:
                dashboard += f"{_html.escape(active_perks)}\n━━━━━━━━━━━━━━━━━\n"
        except Exception as e:
            print(f"[ERROR] Failed to format perks in dashboard: {e}")

    dashboard += (
        f"🎮 <b>{safe_player_name}</b>\n"
        f"━━━━━━━━━━━━━━━━━\n"
    )

    if has_jammer:
        dashboard += (
            f"💀 GHOST UPLINK 💀\n"
            f"--------------------------\n"
            f"✅ ███▓ (Data Secure)\n"
            f"--------------------------\n"
        )
    else:
        safe_word = _html.escape(last_word.upper())
        dashboard += f"✅ <code>{safe_word}</code>  <b>+{last_pts}</b>\n"

    dashboard += (
        f"━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>{total_pts:,}</b> pts   ⭐ <b>{total_xp:,}</b> XP\n"
    )
    if extras_line:
        dashboard += f"{extras_line}\n"
    dashboard += (
        f"━━━━━━━━━━━━━━━━━\n"
        f"📊 {word_count} word{'s' if word_count != 1 else ''} found"
    )
    if rare_msg:
        dashboard += f"\n\n{rare_msg}"
    return dashboard


# ═══════════════════════════════════════════════════════════════════════════
#  WORD-GUESS CATCH-ALL  ←── MUST BE THE LAST @dp.message HANDLER
# ═══════════════════════════════════════════════════════════════════════════

@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def on_group_message(message: types.Message):
    """Catch-all handler for word guesses during active fusion and trivia rounds."""
    try:
        if not message.text:
            return

        text = message.text.strip()
        u_id = str(message.from_user.id)
        current_topic = message.message_thread_id

        # Skip commands — they have their own handlers
        if text.startswith("!") or text.startswith("/"):
            return

        # ─────────────────────────────────────────────────────────────────
        # TRIVIA TOPIC — only process answers in the trivia thread
        # ─────────────────────────────────────────────────────────────────
        if current_topic == TRIVIA_TOPIC_ID:
            trivia_eng = get_trivia_engine(message.chat.id)
            if not trivia_eng.active or not trivia_eng.current_question:
                return  # no active question — ignore

            # Get / auto-register user
            user = get_user(u_id)
            if not user:
                username = message.from_user.first_name or message.from_user.username or "Player"
                register_user(u_id, username)
                user = get_user(u_id)
            if not user:
                return

            # Use DB username; fall back to Telegram display name safely
            username = user.get("username") or message.from_user.first_name or "Player"
            answer = text.strip()
            time_taken = time.time() - trivia_eng.question_start_time

            # Always delete the player's message to keep chat clean
            try:
                await message.delete()
            except Exception:
                pass

            # Each player gets one attempt per question
            if u_id in trivia_eng.player_answers:
                return

            # Store attempt as (raw_answer, time_taken) — 2-tuple matching TriviaEngine design
            trivia_eng.player_answers[u_id] = (answer, time_taken)

            normalized_answer = trivia_eng.normalize_answer(answer)
            normalized_correct = trivia_eng.normalize_answer(trivia_eng.current_question['answer'])
            is_correct = (normalized_answer == normalized_correct)

            if is_correct:
                # Mark as correct in the engine's set (used by game loop for time-up reveal)
                trivia_eng.correct_answers.add(u_id)

                # Use TriviaEngine.add_score() — handles streak, time bonus, boss multiplier
                base_pts = 20 if trivia_eng.is_boss_round else 10
                base_xp  = base_pts * 2
                score_result = trivia_eng.add_score(u_id, username, base_pts, base_xp, time_taken)
                total_pts = score_result['total_points']

                # Persist to DB
                try:
                    add_points(u_id, total_pts, username, game_type="trivia")
                    add_xp(u_id, base_xp)
                except Exception as e:
                    print(f"[TRIVIA DB ERROR] {e}")

                # Build immediate feedback line
                safe_username = _safe_name(username)
                feedback_parts = [f"✅ <b>{safe_username}</b> — <b>+{total_pts} pts</b> ({time_taken:.1f}s)"]
                if score_result['time_bonus'] > 0:
                    feedback_parts.append(f"⚡ Speed bonus: +{score_result['time_bonus']}")
                if score_result['streak_msg']:
                    feedback_parts.append(score_result['streak_msg'])
                if trivia_eng.is_boss_round:
                    feedback_parts.append("👑 Boss round x2!")

                try:
                    await bot.send_message(
                        message.chat.id,
                        "\n".join(feedback_parts),
                        parse_mode="HTML",
                        message_thread_id=TRIVIA_TOPIC_ID
                    )
                except Exception as e:
                    print(f"[TRIVIA SEND ERROR] {e}")

                # Update the persistent scoreboard immediately
                await _update_trivia_scoreboard(message.chat.id, trivia_eng)
            else:
                # Wrong answer — reset streak
                trivia_eng.reset_streak(u_id)
            return

        # ─────────────────────────────────────────────────────────────────
        # FUSION TOPIC — only process words in the fusion thread
        # ─────────────────────────────────────────────────────────────────
        if current_topic == FUSION_TOPIC_ID:
            eng = get_engine(message.chat.id)
            if not eng.active:
                return

            user = get_user(u_id)
            if not user:
                username = message.from_user.first_name or message.from_user.username or "Player"
                try:
                    reg_success = register_user(u_id, username)
                    if reg_success:
                        user = get_user(u_id)
                        await message.reply(f"✅ Welcome, {username}! You've been automatically registered.")
                    else:
                        return
                except Exception as e:
                    print(f"[AUTO-REGISTER ERROR] {e}")
                    return
            if not user:
                return

            guess = text.lower().strip()
            if len(guess) < 3:
                return

            if guess in eng.used_words:
                update_streak_and_award_food(u_id, correct=False, username=user.get("username", ""))
                await message.reply(f"❌ `{guess.upper()}` was already guessed!", parse_mode="Markdown")
                return

            if not can_spell(guess, eng.letters):
                return

            is_valid = word_in_dict(guess)
            has_jammer = is_perk_active(u_id, "jammer")

            if not is_valid:
                update_streak_and_award_food(u_id, correct=False, username=user.get("username", ""))
                if has_jammer:
                    try:
                        await message.delete()
                    except Exception:
                        pass
                return

            # ── Valid word ──────────────────────────────────────────────
            if has_jammer:
                try:
                    await message.delete()
                except Exception:
                    pass

            eng.used_words.append(guess)
            eng.msg_count += 1
            eng.words_repeated_count = getattr(eng, 'words_repeated_count', 0) + 1

            if eng.words_repeated_count % 4 == 0:
                extra = (
                    f" *{eng.extra_letters[0]}* *{eng.extra_letters[1]}*"
                    if len(getattr(eng, 'extra_letters', '')) >= 2 else ""
                )
                await bot.send_message(
                    message.chat.id,
                    f"🃏 *The GameMaster:* THE WORDS ARE: *{eng.word1.lower()}* *{eng.word2.lower()}*{extra}",
                    parse_mode="Markdown",
                    message_thread_id=FUSION_TOPIC_ID
                )

            pts = max(len(guess) - 2, 1)
            db_name = user.get("username", message.from_user.first_name or "Player")
            word_len = len(guess)

            resources_awarded = {}
            resource_map = {4: 'wood', 5: 'bronze', 6: 'iron', 7: 'diamond'}
            if word_len in resource_map:
                resources_awarded[resource_map[word_len]] = 1
            elif word_len >= 8:
                resources_awarded['relics'] = 1

            streak_info = update_streak_and_award_food(u_id, correct=True, username=db_name)
            rare_item = check_rare_drop()
            if rare_item:
                add_unclaimed_item(u_id, rare_item["key"], 1)

            xp_awarded = pts * 2
            bitcoin_awarded = max(pts // 2, 1)

            if u_id not in eng.player_sessions:
                eng.player_sessions[u_id] = {
                    'pts': 0, 'xp': 0, 'word_count': 0,
                    'resources': {'wood': 0, 'bronze': 0, 'iron': 0, 'diamond': 0, 'relics': 0},
                    'food': 0, 'streak': 0, 'last_word': '', 'last_pts': 0, 'rare_message': ''
                }

            session = eng.player_sessions[u_id]
            session.update({
                'pts': session['pts'] + pts,
                'xp': session['xp'] + xp_awarded,
                'word_count': session['word_count'] + 1,
                'last_word': guess,
                'last_pts': pts,
                'streak': streak_info.get('streak', 0),
                'food': session['food'] + streak_info.get('food_awarded', 0)
            })
            for res_type, amount in resources_awarded.items():
                session['resources'][res_type] += amount
            if rare_item:
                session['rare_message'] = f"🎉 <b>RARE DROP!</b> {_html.escape(rare_item['name'])}"

            dashboard_text = build_player_dashboard(db_name, session, u_id, has_jammer=has_jammer)
            word_num = session['word_count']

            if u_id in eng.dashboard_msgs and word_num % 4 != 0:
                try:
                    await bot.edit_message_text(
                        dashboard_text,
                        chat_id=message.chat.id,
                        message_id=eng.dashboard_msgs[u_id],
                        parse_mode="HTML"
                    )
                except Exception:
                    msg = await bot.send_message(
                        message.chat.id, dashboard_text,
                        parse_mode="HTML",
                        message_thread_id=FUSION_TOPIC_ID
                    )
                    eng.dashboard_msgs[u_id] = msg.message_id
            else:
                if u_id in eng.dashboard_msgs:
                    try:
                        await bot.delete_message(chat_id=message.chat.id, message_id=eng.dashboard_msgs[u_id])
                    except Exception:
                        pass
                msg = await bot.send_message(
                    message.chat.id, dashboard_text,
                    parse_mode="HTML",
                    message_thread_id=FUSION_TOPIC_ID
                )
                eng.dashboard_msgs[u_id] = msg.message_id

            # Also update eng.scores so end-of-round summary works
            if u_id not in eng.scores:
                eng.scores[u_id] = {'name': db_name, 'pts': 0, 'user_id': u_id, 'leveled_up': False}
            eng.scores[u_id]['pts'] += pts

            # Save to DB
            try:
                add_points(u_id, pts, db_name, game_type="fusion")
                add_xp(u_id, xp_awarded)
                add_bitcoin(u_id, bitcoin_awarded, db_name)
                user_fresh = get_user(u_id)
                if user_fresh:
                    base_res = user_fresh.get('base_resources', {'resources': {}})
                    if not isinstance(base_res, dict):
                        base_res = {'resources': {}}
                    res_dict = base_res.get('resources', {})
                    for rt, am in resources_awarded.items():
                        res_dict[rt] = res_dict.get(rt, 0) + am
                    base_res['resources'] = res_dict
                    user_fresh['base_resources'] = base_res
                    save_user(u_id, user_fresh)
            except Exception as e:
                print(f"[DB ERROR] {e}")
            return

        # ── Messages outside any game topic — ignore ──────────────────
        return

    except Exception as e:
        print(f"[HANDLER ERROR] {e}")
        import traceback
        traceback.print_exc()


async def _update_trivia_scoreboard(chat_id: int, trivia_eng) -> None:
    """
    Keep ONE scoreboard message pinned at the BOTTOM of the trivia topic.
    Strategy: delete the old scoreboard, immediately resend it so it is
    always the most-recent (bottom) message — players see it without scrolling.
    """
    if not trivia_eng.scores:
        return

    sorted_scores = sorted(trivia_eng.scores.items(), key=lambda x: x[1]['pts'], reverse=True)
    q_num = getattr(trivia_eng, 'question_number', '?')

    board = (
        f"\n📊 <b>SCOREBOARD — Q{q_num}/{TRIVIA_QUESTIONS_PER_GAME}</b>\n"
        f"━━━━━━━━━━━━━━━━━\n"
    )
    medals = ["🥇", "🥈", "🥉"]

    for i, (uid, data) in enumerate(sorted_scores[:10]):
        medal       = medals[i] if i < 3 else f"{i + 1}."
        safe_name   = _safe_name(data['name'])[:14]
        correct_cnt = data.get('answers', data.get('correct', 0))
        streak      = data.get('streak', 0)
        streak_disp = f" 🔥×{streak}" if streak >= 3 else ""
        # Shield — look up cheaply (trivia scores are in-memory, no lb row)
        shield_i = "⚠️"
        try:
            _u = get_user(uid)
            if _u:
                _st = _u.get("shield_status") or ""
                shield_i = "🛡️" if "ACTIVE" in _st else ("💥" if "DISRUPTED" in _st else "⚠️")
        except Exception:
            pass
        board += f"{medal} <b>{safe_name}</b>  {shield_i}  {data['pts']} pts  ({correct_cnt}✓){streak_disp}\n"

    board += "━━━━━━━━━━━━━━━━━"

    try:
        # Delete old scoreboard so the new one appears at the bottom
        old_id = getattr(trivia_eng, 'dashboard_msg_id', None)
        if old_id:
            try:
                await bot.delete_message(chat_id, old_id)
            except Exception:
                pass
            trivia_eng.dashboard_msg_id = None

        # Send fresh scoreboard at the bottom
        m = await bot.send_message(
            chat_id, board,
            parse_mode="HTML",
            message_thread_id=TRIVIA_TOPIC_ID
        )
        trivia_eng.dashboard_msg_id = m.message_id

    except Exception as e:
        print(f"[SCOREBOARD UPDATE ERROR] {e}")


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


async def weekly_reset_task(bot: Bot, chat_id: int):
    """Background task: Reset weekly points every Sunday at midnight (00:00 UTC+1).
    Checks every 60 seconds. Uses a flag to prevent duplicate resets."""
    weekly_reset_done_for_week = ""
    
    while True:
        try:
            await asyncio.sleep(60)  # Check every 60 seconds
            
            now = datetime.utcnow() + timedelta(hours=1)  # UTC+1 (WAT)
            
            # Sunday = weekday 6, check if within 23:58-23:59 window (just before Monday)
            is_sunday_midnight = (
                now.weekday() == 6 and
                now.hour == 23 and
                now.minute >= 58
            )
            
            # Use week ISO date as key to prevent duplicate resets
            current_week_id = now.strftime("%Y-%W")
            
            if is_sunday_midnight and weekly_reset_done_for_week != current_week_id:
                weekly_reset_done_for_week = current_week_id
                print(f"Leaderboard has been reset at {now.isoformat()}")
                
                try:
                    # 1. Get the final weekly leaderboard BEFORE resetting
                    lb = get_weekly_leaderboard(limit=10)
                    
                    # 2. Build the winners announcement
                    medals = ["🥇", "🥈", "🥉"]
                    announcement = (
                        f"{divider()}\n"
                        f"🏆 *WEEKLY RESET — FINAL STANDINGS* 🏆\n"
                        f"{divider()}\n\n"
                        f"🃏 *GameMaster:* \"Another week concluded. "
                        f"Let's see who proved themselves... and who wasted my time.\"\n\n"
                    )
                    
                    if lb:
                        for i, p in enumerate(lb[:10]):
                            medal = medals[i] if i < 3 else f"  {i+1}."
                            announcement += f"{medal} *{p['username']}* — {p['points']:,} pts\n"
                        
                        # 3. Reward top 3 players
                        for i, p in enumerate(lb[:3]):
                            try:
                                reward_crates = 3 - i  # 1st=3, 2nd=2, 3rd=1
                                for _ in range(reward_crates):
                                    add_unclaimed_item(p['id'], "super_crate", 1)
                                xp_bonus = [500, 300, 150][i]
                                add_xp(p['id'], xp_bonus)
                                print(f"[WEEKLY RESET] Rewarded {p['username']}: {reward_crates} crates + {xp_bonus} XP")
                            except Exception as re:
                                print(f"[WEEKLY RESET] Reward error for {p.get('username')}: {re}")
                        
                        # Save to file for display in games
                        try:
                            with open('last_week_winners.json', 'w', encoding='utf-8') as f:
                                json.dump(lb[:3], f)
                        except Exception as e:
                            print(f"[WEEKLY RESET] Failed to save last week winners: {e}")
                        
                        announcement += (
                            f"\n✨ *Top 3 received bonus crates + XP!*\n"
                            f"Check `!claims` to collect.\n"
                        )
                    else:
                        announcement += "Nobody scored this week. Absolutely pathetic.\n"
                    
                    announcement += (
                        f"\n{divider()}\n"
                        f"📅 *All weekly points have been RESET to 0.*\n"
                        f"A new week begins NOW. Prove yourself.\n"
                        f"{divider()}"
                    )
                    
                    # 4. Reset ALL players' weekly_points to 0 in database
                    try:
                        from supabase_db import supabase, DB_TABLE, _current_week_key
                        new_week = _current_week_key()
                        # Use gt(0) to only update rows that actually have points — safer than neq('')
                        supabase.table(DB_TABLE).update({
                            'weekly_points': 0,
                            'week_start': new_week
                        }).gt('weekly_points', -1).execute()  # -1 catches 0 and above
                        # Also reset game-specific weekly cols
                        for game_col in ['fusion_weekly_points', 'trivia_weekly_points']:
                            try:
                                supabase.table(DB_TABLE).update({
                                    game_col: 0
                                }).gt(game_col, -1).execute()
                            except Exception:
                                pass
                        print(f"[WEEKLY RESET] All weekly_points reset to 0, week_start = {new_week}")
                    except Exception as db_err:
                        print(f"[WEEKLY RESET] DB bulk reset error: {db_err}")
                        
                    # Pre-load bots (including World Boss with its high score)
                    try:
                        from supabase_db import ensure_bot_exists
                        if os.path.exists('bot_initial_scores.json'):
                            with open('bot_initial_scores.json', 'r', encoding='utf-8') as f:
                                bot_scores = json.load(f)
                            for bot_name, score in bot_scores.items():
                                bot_id = ensure_bot_exists(bot_name, score)
                                supabase.table(DB_TABLE).update({
                                    'weekly_points': score,
                                    'week_start': new_week
                                }).eq('user_id', bot_id).execute()
                                print(f"[WEEKLY RESET] Bot '{bot_name}' initialized with {score} pts")
                            print(f"[WEEKLY RESET] Pre-loaded all bot initial scores.")
                    except Exception as bot_preload_err:
                        print(f"[WEEKLY RESET] Bot preload error: {bot_preload_err}")
                    
                    # 5. Send announcement to group
                    if chat_id:
                        try:
                            await bot.send_message(chat_id, announcement, parse_mode="Markdown")
                            print(f"[WEEKLY RESET] Announcement sent to group {chat_id}")
                        except Exception as send_err:
                            print(f"[WEEKLY RESET] Failed to send announcement: {send_err}")
                    
                except Exception as reset_err:
                    print(f"[WEEKLY RESET] Error during reset: {reset_err}")
                    import traceback
                    traceback.print_exc()
                    
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[WEEKLY RESET ERROR] Task error: {e}")
            await asyncio.sleep(60)


async def bot_activity_task():
    """Background task: Give fake points to bot accounts every hour."""
    await asyncio.sleep(10) # Brief pause before initial run
    while True:
        try:
            from supabase_db import supabase, DB_TABLE, ensure_bot_exists, _current_week_key
            from datetime import datetime, timedelta
            import os, json
            
            try:
                now = datetime.utcnow() + timedelta(hours=1)
                
                # Load bot initial scores config
                bot_scores = {}
                if os.path.exists('bot_initial_scores.json'):
                    with open('bot_initial_scores.json', 'r', encoding='utf-8') as f:
                        bot_scores = json.load(f)
                
                # Collect World Boss names so we can exclude them from hourly random points
                world_boss_ids = set()
                
                # Ensure all bots exist and have at least their initial score
                for bot_name, score in bot_scores.items():
                    if "World Boss" in bot_name:
                        # World Boss always stays at the top with its fixed score
                        bot_id = ensure_bot_exists(bot_name, score)
                        world_boss_ids.add(bot_id)
                        r = supabase.table(DB_TABLE).select('weekly_points, week_start').eq('user_id', bot_id).execute()
                        if r.data:
                            wb_data = r.data[0]
                            wb_pts = int(wb_data.get('weekly_points') or 0)
                            wb_week = (wb_data.get('week_start') or '').split('T')[0]
                            # If wrong week or points below initial, force to initial score
                            if wb_week != _current_week_key() or wb_pts < score:
                                supabase.table(DB_TABLE).update({
                                    'weekly_points': score,
                                    'week_start': _current_week_key()
                                }).eq('user_id', bot_id).execute()
                                print(f"[BOT ACTIVITY] World Boss set to {score} points")
                    else:
                        # Normal bots — ensure they exist and have at least initial score
                        bot_id = ensure_bot_exists(bot_name, score)
                        r = supabase.table(DB_TABLE).select('weekly_points, week_start').eq('user_id', bot_id).execute()
                        if r.data:
                            bot_data = r.data[0]
                            bot_pts = int(bot_data.get('weekly_points') or 0)
                            bot_week = (bot_data.get('week_start') or '').split('T')[0]
                            if bot_week != _current_week_key() or bot_pts < score:
                                supabase.table(DB_TABLE).update({
                                    'weekly_points': score,
                                    'week_start': _current_week_key()
                                }).eq('user_id', bot_id).execute()
                                print(f"[BOT ACTIVITY] Bot '{bot_name}' topped up to initial {score} pts")

                # Add hourly random points to NON-World-Boss bots only
                response = supabase.table(DB_TABLE).select("user_id, username, weekly_points").eq("is_bot", True).execute()
                bots = response.data
                
                if bots:
                    updated_count = 0
                    for bot_player in bots:
                        # Skip World Boss — it stays at its fixed score
                        if bot_player['user_id'] in world_boss_ids:
                            continue
                        pts = random.randint(50, 200)
                        current = int(bot_player.get('weekly_points', 0) or 0)
                        supabase.table(DB_TABLE).update({
                            "weekly_points": current + pts,
                            "week_start": _current_week_key()
                        }).eq("user_id", bot_player['user_id']).execute()
                        updated_count += 1
                    print(f"[BOT ACTIVITY] Added 50-200 pts to {updated_count} bots (World Boss excluded).")
            except Exception as db_err:
                print(f"[BOT ACTIVITY] Could not update bots (is_bot column might be missing): {db_err}")
                
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[BOT ACTIVITY] Task error: {e}")
            
        await asyncio.sleep(3600)  # Wait 1 hour between runs


async def sector_status_task(bot: Bot, chat_id: int):
    """Background task: Post hourly sector status to keep chat feeling alive."""
    sector_names = [
        "Badlands-8", "Crimson Wastes", "Obsidian Peaks", "Shattered Valley",
        "Frozen Abyss", "Molten Gorge", "Twilight Marshes", "Silent Forest",
        "Void Canyon", "Ember Fields", "Deep Catacombs", "Azure Fortress"
    ]
    
    resources = [
        ("🪵", "Wood", "up 15%"),
        ("🧱", "Bronze", "down 8%"),
        ("⛓️", "Iron", "up 22%"),
        ("💎", "Diamond", "up 45%"),
        ("🏺", "Relics", "down 12%"),
    ]
    
    while True:
        try:
            wait_time = 3600  # 1 hour
            await asyncio.sleep(wait_time)
            
            # Get random sector and resource
            sector = random.choice(sector_names)
            emoji, resource, price_change = random.choice(resources)
            
            # Get top player (overlord) from leaderboard
            top_players = get_weekly_leaderboard(limit=1)
            overlord = top_players[0].get('username', 'The Council') if top_players else "The Council"
            
            # Generate status message
            status_msg = sector_status(sector, resource, emoji, price_change, overlord)
            
            try:
                await bot.send_message(chat_id, status_msg, parse_mode="Markdown")
            except Exception as send_err:
                print(f"[STATUS ERROR] Failed to send sector status: {send_err}")
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[STATUS ERROR] Sector status task error: {e}")
            await asyncio.sleep(10)


async def sheets_sync_background_task(bot: Bot, chat_id: int):
    """Background task: Sync game to Google Sheets every 30 minutes and notify group."""
    while True:
        try:
            await asyncio.sleep(1800)  # 30 minutes = 1800 seconds
            
            try:
                # Import sync_to_sheets at runtime
                from sync_to_sheets import update_google_sheet, get_leaderboard_data
                
                # Get leaderboard data
                leaderboard = get_leaderboard_data()
                
                if leaderboard:
                    # Sync to Google Sheets
                    update_google_sheet(leaderboard)
                    
                    # Format and send update to group
                    top_10 = leaderboard[:10]
                    msg = "📊 *LEADERBOARD*\n\n"
                    msg += "🏆 Top 5 Players:\n"
                    for idx, player in enumerate(top_10, 1):
                        username = player.get("username", "Unknown")
                        points = player.get("points", 0)
                        msg += f"{idx}. {username} - {points:,} pts\n"
                    
                    msg += f"\n⏰ Updated: {datetime.utcnow().strftime('%H:%M UTC')}"
                    msg += f"\n📈 Total players: {len(leaderboard)}"
                    
                    await bot.send_message(chat_id, msg, parse_mode="Markdown")
                    print(f"[SHEETS] Synced {len(leaderboard)} players to Google Sheets")
                else:
                    print("[SHEETS] No leaderboard data to sync")
                    
            except ImportError:
                print("[SHEETS WARN] sync_to_sheets module not found - skipping sync")
            except Exception as sync_err:
                print(f"[SHEETS ERROR] Sync failed: {sync_err}")
                
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[SHEETS ERROR] Background task error: {e}")
            await asyncio.sleep(60)  # Wait 1 min before retrying


async def gamemaster_announcement_task(bot: Bot, chat_id: int):
    """Background task: Drop random GameMaster announcements every 7-10 minutes + dynamic event announcements."""
    
    # Static announcements (dramatic GameMaster messages)
    static_announcements = [
        f"{divider()}\n🌀 *3 FREE TELEPORTS GRANTED*\n{divider()}\n\nCheck your `!claims` - I've given you **3 free teleports**. Use them wisely. Each sector offers different rewards, risks, and *opportunities*. \n\nType `!teleport [1-9]` to explore. Or be a coward and stay in Sector 1. Your choice. 🌍\n{divider()}",
        
        f"{divider()}\n🌍 *DISCOVER THE SECTORS*\n{divider()}\n\n**SECTOR 1** (🏜️ Badlands): Easy pickings. For noobs.\n**SECTOR 6** (🔥 Molten Gorge): Legendary drops. Almost certain death.\n**SECTOR 9** (🌑 Void Canyon): The best resources. Only legends survive.\n\nType `!map` to see what's available. Type `!teleport [1-9]` to jump in. 🚀\n{divider()}",
        
        f"{divider()}\n📈 *THE LEADERBOARD NEVER LIES*\n{divider()}\n\nSome of you are absolutely CRUSHING it. Others... *exist*. The weak are separated from the strong here on the *WEEKLY LEADERBOARD*. Or stay unknown forever on the *ALLTIME LEADERBOARD*. Your choice, coward. 🃏\n{divider()}",
        
        f"{divider()}\n🏰 *YOUR FORTRESS IS PATHETIC*\n{divider()}\n\nLook at your base. Just... *look* at it. Is that a fortress or a cardboard box? Level it up. Add military units. Place traps. Make it *worthy* of the GameMaster's attention. Otherwise, why should I bother watching? 😑\n{divider()}",
        
        "🪓 *SWORDS WILL SHARPEN SOON*\n\nCurrently, shields are making you soft. Enjoy the free pass while it lasts. Soon the *WARS BEGIN*. Right now? Build your armies like your life depends on it. Because eventually... *it will*. Frame that warning. 💀",
        
        f"{divider()}\n🏪 *SHOPS = YOUR NEW ADDICTION*\n{divider()}\n• **Normal Shop**: For mortals who like... normal things\n• **Black Market**: For those with *taste*\n• **Alliance Shop**: For actual friends (rare)\n• **Ruler's Shop**: For the cocky ones\n• **Premium**: For the desperately impatient\n{divider()}",
        
        f"{divider()}\n🔬 *SCIENCE = POWER = DOMINANCE*\n{divider()}\n\nThe research lab isn't just a building—it's an *IQ test*. Spend your precious resources on upgrades that'll make you 30% better at war. Or don't. I'll enjoy watching you lose. The choice is yours. 🧪\n{divider()}",
        
        "💎 *HOARD EVERYTHING LIKE YOUR LIFE DEPENDS ON IT*\n\nWood. Bronze. Iron. Diamond. Relics. \n\nEvery resource is a *weapon*. Every crate is a gift from me (you're welcome). Every item is *power*. Stop wasting them on stupid stuff. Build empires or die trying. 💰",
        
        f"{divider()}\n👑 *SECTOR WARS ARE COMING*\n{divider()}\n\nYou think Sector 1 is tough? Try Sector 9. Better resources = better rewards = *actual* power. Teleport to a high sector and watch yourself get *obliterated*. Or train harder and actually win. I'm *dying* to see which. 🌍\n{divider()}",
        
        "⚔️ *YOUR MILITARY STINKS*\n\nPolice and Dogs attack like they're scared. Knights are hit-or-miss. Bishops are *trying*. Rooks are solid. Queens? Where are your Queens? Kings? Almost never seen those. \n\nBuild better armies. Stop embarrassing the realm. 👑💔",
        
        f"{divider()}\n🔗 *ALLIANCES = FRIENDSHIP BETRAYAL SIMULATORS*\n{divider()}\n\nBand together with your friends... then stab them in the back for glory. The coming *Alliance Wars* will separate true friends from back-stabbers. Spoiler: everyone's a back-stabber. 😈\n{divider()}",
        
        "🎮 *YOUR FRIENDS ARE WEAK. RECRUIT THEM.*\n\nBored playing alone? Invite them here: https://t.me/checkmateHQ\n\nThen crush them mercilessly. Nothing says friendship like destroying their base while they sleep. *That's* what I'm here for. 🃏",
        
        f"{divider()}\n😴 *STOP LURKING AND START PLAYING*\n{divider()}\n\nI know you're here. Watching. Waiting. *Scared*.\n\nType `!fusion` and face me. Or keep hiding like a coward. Either way, I'm *watching*. Always watching... 👀\n{divider()}",
        
        "🤑 *YOUR RESOURCES ARE USELESS WITHOUT PURPOSE*\n\nHoarding wood? Cute. Building nothing with it? *Pathetic*. Use your resources. Upgrade your base. Train units. Research stronger abilities. Otherwise you're just collecting digital trash. 🗑️",
        
        f"{divider()}\n⏰ *TIME TO DOMINATE*\n{divider()}\n\nEvery second you're NOT playing, someone else is getting stronger.\nEvery crate you don't open is power left on the table.\nEvery word game you skip is resources lost forever.\n\nFeeling the pressure yet? Good. 🔥\n{divider()}",
        
        f"{divider()}\n🎯 *THE WEAK PERISH. THE STRONG CONQUER.*\n{divider()}\n\nI watch you all. Some of you are *actually* trying. Others... are just taking up space. The leaderboard will judge you mercilessly. Will you rise... or fade into obscurity? 💀\n{divider()}",
    ]
    
    while True:
        try:
            wait_time = random.randint(420, 600)  # 7-10 minutes
            await asyncio.sleep(wait_time)
            
            # 60% chance for dynamic event, 40% for static
            if random.random() < 0.6:
                # Check for recent events
                event_announcement = None
                
                # 1. LEVEL-UP ANNOUNCEMENTS
                level_ups = get_recent_events("level_ups", minutes=15)
                if level_ups:
                    lu = random.choice(level_ups)
                    level_messages = [
                        f"🎖️ *{lu['player']}* just reached **LEVEL {lu['new_level']}**! {['', '😤', '👑', '⚡'][random.randint(0, 3)]} The weak tremble.",
                        f"📈 {lu['player']} HAS ASCENDED TO **LEVEL {lu['new_level']}**! The realm trembles. 🔥",
                        f"👁️ I'm watching {lu['player']} climb the ranks... **LEVEL {lu['new_level']}** acquired. Impressive... *for now*. 🎩"
                    ]
                    event_announcement = random.choice(level_messages)
                
                # 2. CHALLENGE COMPLETION ANNOUNCEMENTS
                elif get_recent_events("challenges", minutes=15):
                    challenges = get_recent_events("challenges", minutes=15)
                    ch = random.choice(challenges)
                    challenge_messages = [
                        f"🏆 {ch['player']} CONQUERED THE *{ch['challenge']}* CHALLENGE! +{ch['reward']} pts! The strong grow stronger.",
                        f"✅ *{ch['player']}* just demolished the *{ch['challenge']}* challenge for **+{ch['reward']} points**!  Who's next? 💪",
                        f"🎯 *{ch['player']}* is no slack—*{ch['challenge']}* down for **+{ch['reward']} pts**! Keep this pace and maybe I'll remember your name."
                    ]
                    event_announcement = random.choice(challenge_messages)
                
                # Send event announcement if we have one
                if event_announcement:
                    try:
                        await bot.send_message(chat_id, event_announcement, parse_mode="Markdown")
                        print(f"[EVENT ANNOUNCE] {event_announcement[:60]}...")
                    except Exception as send_err:
                        print(f"[ANNOUNCE ERROR] Failed to send event: {send_err}")
                else:
                    # No events, fall back to static
                    announcement = random.choice(static_announcements)
                    try:
                        await bot.send_message(chat_id, announcement, parse_mode="Markdown")
                    except Exception as send_err:
                        print(f"[ANNOUNCE ERROR] Failed to send: {send_err}")
            else:
                # 40% static announcements
                announcement = random.choice(static_announcements)
                try:
                    await bot.send_message(chat_id, announcement, parse_mode="Markdown")
                except Exception as send_err:
                    print(f"[ANNOUNCE ERROR] Failed to send: {send_err}")
                    
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[ANNOUNCE ERROR] Task error: {e}")
            await asyncio.sleep(10)



async def mining_task(bot: Bot, chat_id: int):
    """Background task: Handle active mining operations every 30 seconds."""
    sector_info = {
        1: {"name": "Badlands-8", "resources": ["wood", "bronze"], "multiplier": 1.0},
        2: {"name": "Crimson Wastes", "resources": ["bronze", "iron"], "multiplier": 1.2},
        3: {"name": "Obsidian Peaks", "resources": ["iron", "diamond"], "multiplier": 1.5},
        4: {"name": "Shattered Valley", "resources": ["bronze", "wood", "iron"], "multiplier": 1.1},
        5: {"name": "Frozen Abyss", "resources": ["iron", "diamond"], "multiplier": 1.25},
        6: {"name": "Molten Gorge", "resources": ["diamond", "relics"], "multiplier": 1.6},
        7: {"name": "Twilight Marshes", "resources": ["wood", "relics"], "multiplier": 1.3},
        8: {"name": "Silent Forest", "resources": ["wood", "bronze", "diamond"], "multiplier": 1.35},
        9: {"name": "Void Canyon", "resources": ["relics", "diamond", "iron"], "multiplier": 2.0}
    }
    
    # Resource amounts per drop (scales with multiplier and troops)
    base_drops = {
        1: {"wood": 5, "bronze": 3},
        2: {"bronze": 5, "iron": 2},
        3: {"iron": 4, "diamond": 1},
        4: {"bronze": 4, "wood": 5, "iron": 2},
        5: {"iron": 5, "diamond": 2},
        6: {"diamond": 3, "relics": 1},
        7: {"wood": 6, "relics": 1},
        8: {"wood": 5, "bronze": 4, "diamond": 1},
        9: {"relics": 2, "diamond": 2, "iron": 3}
    }
    
    while True:
        try:
            await asyncio.sleep(30)  # Check every 30 seconds
            
            # NOTE: For production, you'd query a list of all active mining users
            # This would require a database function like get_all_active_miners()
            # For now, this structure is ready for that integration
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[MINING_TASK ERROR] {e}")
            await asyncio.sleep(10)

@dp.message(_cmd("save"))
async def cmd_save(message: types.Message):
    if message.chat.type != "private":
        await message.answer("🃏 *GM:* \"Save your progress in private, not here.\"", parse_mode="Markdown")
        return

    u_id = str(message.from_user.id)
    user = get_user(u_id) # Fetch the user from Supabase/DB
    
    if not user:
        await _send_unreg_sticker(message)
        return

    # Parse the slot number (e.g., /save 1)
    parts = message.text.split()
    slot = 1 # Default slot
    if len(parts) > 1:
        try:
            slot = int(parts[1])
        except ValueError:
            await message.answer("❌ Slot must be a number (1-5).")
            return

    # Call the function from save_system.py
    success, result_msg = save_game(u_id, user, slot=slot)
    
    if success:
        # IMPORTANT: You must save the updated user object back to the DB 
        # because save_game modifies the 'game_saves' dictionary inside the user object.
        save_user(u_id, user) 
        await message.answer(f"✅ {result_msg}", parse_mode="Markdown")
    else:
        # This is where your "error saving game" message comes from if save_game returns False
        await message.answer(f"❌ {result_msg}", parse_mode="Markdown")

@dp.message(_cmd("load"))
async def cmd_load(message: types.Message):
    if message.chat.type != "private":
        await message.answer("🃏 *GM:* \"You can not do that here!\"", parse_mode="Markdown")
        return

    u_id = str(message.from_user.id)
    user = get_user(u_id) # Fetch the user from Supabase/DB
    
    if not user:
        await _send_unreg_sticker(message)
        return

    # Parse the slot number (e.g., /load 1)
    parts = message.text.split()
    slot = 1 # Default slot
    if len(parts) > 1:
        try:
            slot = int(parts[1])
            if slot < 1 or slot > 5:
                await message.answer("❌ Slot must be between 1-5.", parse_mode="Markdown")
                return
        except ValueError:
            await message.answer("❌ Slot must be a number (1-5).", parse_mode="Markdown")
            return

    # Call the function from save_system.py (returns 3 values)
    success, restored_state, result_msg = load_game(user, slot=slot)
    
    if success:
        # Update the user data if restore was successful
        if restored_state:
            save_user(u_id, restored_state)
        await message.answer(f"✅ {result_msg}", parse_mode="Markdown")
    else:
        await message.answer(f"❌ {result_msg}", parse_mode="Markdown")


@dp.message(_cmd("reset"))
async def cmd_reset(message: types.Message):
    if message.chat.type != "private":
        await message.answer("🃏 *GM:* \"You can not do that here!\"", parse_mode="Markdown")
        return

    u_id = str(message.from_user.id)
    user = get_user(u_id)
    
    if not user:
        await _send_unreg_sticker(message)
        return

    # Parse the reset level (e.g., /reset soft)
    parts = message.text.split()
    reset_level = "hard"  # Default level
    if len(parts) > 1:
        reset_level = parts[1].lower()
        if reset_level not in ["soft", "hard", "weekly"]:
            await message.answer(
                "❌ *Invalid reset level!*\n\n"
                "Use one of:\n"
                "• `/reset soft` — Reset battle stats only\n"
                "• `/reset hard` — Complete restart (careful!)\n"
                "• `/reset weekly` — Reset weekly points",
                parse_mode="Markdown"
            )
            return

    # Confirm dangerous resets
    if reset_level == "hard":
        await message.answer(
            "⚠️ *WARNING: HARD RESET*\n\n"
            "This will completely restart your progress!\n"
            "All achievements, levels, and items will be lost.\n\n"
            "Type: `/confirm_reset hard`\n\n"
            "Or cancel by ignoring this message.",
            parse_mode="Markdown"
        )
        return
    
    # Perform the reset
    success, new_state, result_msg = reset_game(user, reset_level)
    
    if success:
        if new_state:
            save_user(u_id, new_state)
        await message.answer(f"✅ {result_msg}", parse_mode="Markdown")
    else:
        await message.answer(f"❌ {result_msg}", parse_mode="Markdown")


@dp.message(_cmd("confirm_reset"))
async def cmd_confirm_reset(message: types.Message):
    if message.chat.type != "private":
        await message.answer("🃏 *GM:* \"You can not do that here!\"", parse_mode="Markdown")
        return

    u_id = str(message.from_user.id)
    user = get_user(u_id)
    
    if not user:
        await _send_unreg_sticker(message)
        return

    # Parse the reset level
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❌ Specify reset level: `/confirm_reset hard`", parse_mode="Markdown")
        return
    
    reset_level = parts[1].lower()
    if reset_level != "hard":
        await message.answer("❌ Only hard reset requires confirmation.", parse_mode="Markdown")
        return

    # Perform the hard reset
    success, new_state, result_msg = reset_game(user, "hard")
    
    if success:
        if new_state:
            save_user(u_id, new_state)
        await message.answer(
            f"💀 *HARD RESET COMPLETE*\n\n"
            f"Your account has been completely reset.\n"
            f"Type `!start` to begin a new adventure.",
            parse_mode="Markdown"
        )
    else:
        await message.answer(f"❌ Reset failed: {result_msg}", parse_mode="Markdown")


@dp.message(_cmd("saves"))
async def cmd_saves(message: types.Message):
    """Display all saved game slots."""
    if message.chat.type != "private":
        await _send_access_denied_sticker(message)
        return
    
    u_id = str(message.from_user.id)
    user = get_user(u_id)
    
    if not user:
        await _send_unreg_sticker(message)
        return
    
    # Get all save checkpoints
    checkpoints = list_checkpoints(u_id)
    
    if not checkpoints:
        await message.answer(
            "💾 *YOUR SAVED GAMES*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "No saves yet.\n\n"
            "Create one with: `/save [1-5]`",
            parse_mode="Markdown"
        )
        return
    
    # Group saves by slot
    saves_by_slot = {}
    for cp in checkpoints:
        reason = cp.get('reason', 'unknown')
        if reason.startswith('slot_'):
            slot_num = reason.replace('slot_', '')
            if slot_num not in saves_by_slot:
                saves_by_slot[slot_num] = cp
    
    # Build display with friendly timestamp formatting
    from datetime import datetime
    txt = "💾 *YOUR SAVED GAMES*\n━━━━━━━━━━━━━━━━━━━━\n\n"
    
    if saves_by_slot:
        for slot_num in sorted(saves_by_slot.keys(), key=lambda x: int(x)):
            cp = saves_by_slot[slot_num]
            timestamp_str = cp.get('timestamp', 'unknown')
            
            # Format timestamp to be more readable
            # Input: "2026-04-15_14-59-01"
            # Output: "Apr 15, 2026 at 2:59 PM"
            try:
                dt = datetime.strptime(timestamp_str, "%Y-%m-%d_%H-%M-%S")
                # Use format that works on Windows (%-I not supported)
                formatted_time = dt.strftime("%b %d, %Y at %I:%M %p").lstrip('0').replace(' 0', ' ')
            except:
                formatted_time = timestamp_str
            
            txt += f"**Slot {slot_num}:** `{formatted_time}`\n"
    else:
        txt += "No saved slots found.\n"
    
    txt += f"\n━━━━━━━━━━━━━━━━━━━━\n"
    txt += f"*Available slots:* 1-5\n"
    txt += f"*Load:* `/load [slot]`\n"
    txt += f"*Save:* `/save [slot]`"
    
    await message.answer(txt, parse_mode="Markdown")

    

async def _finalize_mining(u_id: str, sector_id: int, troop_count: int):
    """Finalize mining operation and award resources."""
    user = get_user(u_id)
    if not user:
        return
    
    buffs = user.get('buffs', {})
    drops = buffs.get('mining_drops', [])
    
    # Calculate total resources from drops
    total_resources = {}
    for drop in drops:
        res = drop['resource']
        total_resources[res] = total_resources.get(res, 0) + drop['amount']
    
    # Award resources to player
    if total_resources:
        base_res = user.get('base_resources', {})
        if not isinstance(base_res, dict):
            base_res = {'resources': {}, 'food': 0}
        
        resources = base_res.get('resources', {})
        if not isinstance(resources, dict):
            resources = {}
        
        for res_type, amount in total_resources.items():
            resources[res_type] = resources.get(res_type, 0) + amount
        
        base_res['resources'] = resources
        user['base_resources'] = base_res
    
    # Clear mining state
    buffs.pop('mining_active', None)
    buffs.pop('mining_sector', None)
    buffs.pop('mining_troops', None)
    buffs.pop('mining_start_time', None)
    buffs.pop('mining_drops', None)
    user['buffs'] = buffs
    save_user(u_id, user)
    
    print(f"[MINING] User {u_id} completed mining. Resources awarded: {total_resources}")

# --- COMMAND HANDLER REGISTRATION ---
# Existing handlers for /start, /profile, etc. are here...

# ADD THE NEW HANDLERS HERE:
setup_buy_command(dp, _cmd, types, get_user, save_user)
setup_quests_command(dp, _cmd, types, get_user)
setup_vault_command(dp, _cmd, types, get_user, save_user)
setup_chess_command(dp, _cmd, types, get_user, save_user)
setup_guild_handlers(dp, _cmd, types, InlineKeyboardMarkup, InlineKeyboardButton, get_user, save_user)

# ═══════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

async def hourly_leaderboard_broadcast_task(bot: Bot, chat_id: int):
    """Post all leaderboards to the LEADERBOARDS topic every hour."""
    await asyncio.sleep(10)  # brief startup delay
    while True:
        try:
            now_str = datetime.utcnow().strftime("%H:%M UTC")
            medals  = ["🥇", "🥈", "🥉"]

            sections = [
                ("🃏 FUSION — WEEKLY",   get_game_weekly_leaderboard, {"game_type": "fusion",  "limit": 10}),
                ("🃏 FUSION — ALL-TIME", get_game_alltime_leaderboard, {"game_type": "fusion",  "limit": 10}),
                ("🧠 TRIVIA — WEEKLY",   get_game_weekly_leaderboard, {"game_type": "trivia",  "limit": 10}),
                ("🧠 TRIVIA — ALL-TIME", get_game_alltime_leaderboard, {"game_type": "trivia",  "limit": 10}),
                ("🏆 OVERALL — WEEKLY",  get_weekly_leaderboard,       {"limit": 10}),
                ("🏆 OVERALL — ALL-TIME",get_alltime_leaderboard,      {"limit": 10}),
            ]

            full_board = f"📊 <b>LEADERBOARDS</b>  <i>({now_str})</i>\n"

            for title, fn, kwargs in sections:
                full_board += f"\n━━━━━━━━━━━━━━━━━\n<b>{title}</b>\n"
                try:
                    lb = fn(**kwargs)
                    if lb:
                        for i, p in enumerate(lb):
                            medal     = medals[i] if i < 3 else f"  {i+1}."
                            name      = _safe_name(p.get("username", "Unknown"))[:14]
                            pts       = p.get("points", 0)
                            # Shield directly from lb row
                            st       = p.get("shield_status") or "UNPROTECTED"
                            shield_i = "🛡️" if "ACTIVE" in st else ("💥" if "DISRUPTED" in st else "⚠️")
                            ns       = p.get("name_shield_until")
                            if ns:
                                try:
                                    from datetime import datetime as _dt
                                    if _dt.now() < _dt.fromisoformat(ns):
                                        name     = "🔐 Anonymous"
                                        shield_i = "🛡️"
                                except Exception:
                                    pass
                            full_board += f"{medal} <b>{name}</b>  {shield_i}  {pts:,}\n"
                    else:
                        full_board += "<i>No scores yet.</i>\n"
                except Exception as lb_err:
                    full_board += f"<i>Error: {lb_err}</i>\n"

            try:
                await bot.send_message(
                    chat_id, full_board,
                    parse_mode="HTML",
                    message_thread_id=LEADERBOARDS_TOPIC_ID
                )
                print(f"[LEADERBOARD BROADCAST] Sent at {now_str}")
            except Exception as send_err:
                print(f"[LEADERBOARD BROADCAST] Send failed: {send_err}")

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[LEADERBOARD BROADCAST ERROR] {e}")

        await asyncio.sleep(3600)  # every hour


async def main():
    import signal, platform
    print("Bot starting...")
    
    # Load dictionary for word validation
    print(f"[STARTUP] DICTIONARY size before load_dictionary(): {len(DICTIONARY)}")
    load_dictionary()
    print(f"[STARTUP] DICTIONARY size after load_dictionary(): {len(DICTIONARY)}")
    if len(DICTIONARY) == 0:
        print("[ERROR] ⚠️  DICTIONARY IS EMPTY! Word validation will FAIL!")
    
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
    
 
    # Grant 3 free teleports to all players
    grant_free_teleports_to_all()
    print("[OK] Granted 3 free teleports to all players")
    
    # Grant 3 free shields to all players
    grant_free_shields_to_all()
    print("[OK] Granted 3 free shields to all players")
    
    # Start background streak reset task (every 120s)
    round_task = asyncio.create_task(round_reset_task())
    print("[OK] Round timer started (120s rounds with streak reset)")
    
    # Start GameMaster announcements task (using imported CHECKMATE_HQ_GROUP_ID)
    # Note: Telegram group IDs are NEGATIVE numbers (e.g., -1003835925366)
    announce_task = None
    status_task = None
    mining_task_handle = None
    sheets_sync_task = None
    weekly_task = None
    bot_activity = None
    
    # Check if group ID is valid (Telegram group IDs are negative integers)
    is_valid_group = CHECKMATE_HQ_GROUP_ID and isinstance(CHECKMATE_HQ_GROUP_ID, int) and CHECKMATE_HQ_GROUP_ID < 0
    
    if is_valid_group:
        try:
            announce_task = asyncio.create_task(gamemaster_announcement_task(bot, CHECKMATE_HQ_GROUP_ID))
            print(f"[OK] Announcements started for group {CHECKMATE_HQ_GROUP_ID}")
        except Exception as e:
            print(f"[WARN] Announcements failed: {e}")
        
        try:
            status_task = asyncio.create_task(sector_status_task(bot, CHECKMATE_HQ_GROUP_ID))
            print(f"[OK] Sector Status broadcasts started (hourly)")
        except Exception as e:
            print(f"[WARN] Sector Status failed: {e}")
        
        try:
            mining_task_handle = asyncio.create_task(mining_task(bot, CHECKMATE_HQ_GROUP_ID))
            print(f"[OK] Mining task started")
        except Exception as e:
            print(f"[WARN] Mining task failed: {e}")
        
        try:
            sheets_sync_task = asyncio.create_task(sheets_sync_background_task(bot, CHECKMATE_HQ_GROUP_ID))
            print(f"[OK] Google Sheets sync task started (every 30 min)")
        except Exception as e:
            print(f"[WARN] Google Sheets sync failed: {e}")
        
        try:
            weekly_task = asyncio.create_task(weekly_reset_task(bot, CHECKMATE_HQ_GROUP_ID))
            print(f"[OK] Weekly reset task started (Sunday midnight UTC+1)")
        except Exception as e:
            print(f"[WARN] Weekly reset task failed: {e}")
            
        try:
            bot_activity = asyncio.create_task(bot_activity_task())
            print(f"[OK] Bot activity simulator started (hourly)")
        except Exception as e:
            print(f"[WARN] Bot activity task failed: {e}")

        try:
            lb_broadcast_task = asyncio.create_task(hourly_leaderboard_broadcast_task(bot, CHECKMATE_HQ_GROUP_ID))
            print(f"[OK] Hourly leaderboard broadcaster started → topic {LEADERBOARDS_TOPIC_ID}")
        except Exception as e:
            print(f"[WARN] Leaderboard broadcaster failed: {e}")
    else:
        print(f"[WARN] CHECKMATE_HQ_GROUP_ID invalid or not set (got: {CHECKMATE_HQ_GROUP_ID}) - announcements disabled")
    
    task = asyncio.create_task(dp.start_polling(bot, handle_signals=False))
    print("[OK] Polling started successfully - waiting for messages...")
    await stop.wait()
    task.cancel()
    round_task.cancel()
    if announce_task:
        announce_task.cancel()
    if status_task:
        status_task.cancel()
    if mining_task_handle:
        mining_task_handle.cancel()
    if sheets_sync_task:
        sheets_sync_task.cancel()
    if weekly_task:
        weekly_task.cancel()
    if bot_activity:
        bot_activity.cancel()
    try: await task
    except asyncio.CancelledError: pass
    try: await round_task
    except asyncio.CancelledError: pass
    if announce_task:
        try: await announce_task
        except asyncio.CancelledError: pass
    if status_task:
        try: await status_task
        except asyncio.CancelledError: pass
    if mining_task_handle:
        try: await mining_task_handle
        except asyncio.CancelledError: pass
    await bot.session.close()
    print("Bot stopped.")

if __name__ == "__main__":
    asyncio.run(main())
