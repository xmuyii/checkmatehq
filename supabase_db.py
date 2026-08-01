"""
supabase_db.py — Supabase persistence layer for The 64 Game
============================================================
Key fixes vs previous version:
  - add_points: accumulates; never resets within same week; week key is ISO date
  - add_unclaimed_item: xp_reward stored correctly on each item
  - claim_item: moves item by its unique 'id', not fragile list index
  - remove_inventory_item: uses unique item 'id'
  - Shield: stored with expiry timestamp; is_shielded() helper
  - Crate XP: super_crate=50-200, wood=50-100, bronze=100-150, iron=150-200
"""
from typing import Tuple, Dict, Any
import os
import json
import random
from datetime import datetime, timedelta, UTC, timezone
from supabase import create_client, Client
from base_layout import get_default_base_layout
from teleport_system import on_user_load
from config import DB_TABLE, SUPABASE_URL as CONFIG_SUPABASE_URL, SUPABASE_KEY as CONFIG_SUPABASE_KEY, ENV_NAME

SUPABASE_URL = os.environ.get('SUPABASE_URL', CONFIG_SUPABASE_URL).rstrip('/')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', CONFIG_SUPABASE_KEY)
SECTORS_FILE = os.environ.get('SECTORS_FILE', 'sectors.txt')

# Items that stack into a single inventory slot.
# Claiming more of a stackable just increments quantity on the existing slot —
# no extra backpack space consumed. Add new item types here as needed.
STACKABLE_ITEMS = {
    'super_crate', 'wood_crate', 'bronze_crate', 'iron_crate',
    'shield_potion', 'free_teleport', 'teleport', 'shield',
}

# Initialize Supabase with error handling for invalid credentials
supabase: Client = None
try:
    if SUPABASE_URL and SUPABASE_KEY and 'your' not in SUPABASE_KEY.lower():
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print(f"[OK] Supabase module loaded (Environment: {ENV_NAME}, Table: {DB_TABLE})")
    else:
        print(f"[WARNING] Supabase credentials not configured - running in offline mode")
except Exception as e:
    print(f"[WARNING] Supabase connection failed: {e} - running in offline mode")


# ── Random Base Names ──────────────────────────────────────────────────────

DEFAULT_BASE_NAMES = [
    "Iron Fortress", "Stone Keep", "Bronze Citadel", "The Stronghold",
    "Crystal Tower", "Shadow Bastion", "Eagle's Nest", "Dragon's Lair",
    "Obsidian Hall", "Midnight Manor", "The Throne", "Kingdom's Crown",
    "Warrior's Peak", "Sentinel Post", "The Ramparts", "Silver Spire",
    "Timber Lodge", "Crimson Hold", "The Garrison", "Paladin's Rest",
    "Raven's Keep", "Phoenix Rising", "Stormhold", "Avalon Castle",
    "Winterfort", "Sunkeep", "Moonlight Bridge", "Starlight Citadel",
    "Ironheart Keep", "Ravenstorm", "The Bulwark", "Dreadfort",
    "Whitewall", "Blackthorne", "Mystic Tower", "The Sanctuary",
    "Skyward Spire", "Earthen Vault", "Twilight Realm", "The Citadel",
]


# ═══════════════════════════════════════════════════════════════════════════
# PASTE BLOCK 3 — safe_json and normalize_user (fixes the append crash)
# ═══════════════════════════════════════════════════════════════════════════

import json as _json

# ── Week helper ────────────────────────────────────────────────────────────

def _current_week_key() -> str:
    """ISO date string of the Monday that starts this week (Mon-Sun). Resets Monday 00:00 WAT (Sunday 11:59 PM)."""
    today = datetime.now(UTC) + timedelta(hours=1)
    days_since_monday = today.weekday()   # Monday=0 … Sunday=6
    monday = today - timedelta(days=days_since_monday)
    return monday.date().isoformat()


def _fix_item_ids(items_list: list) -> list:
    """Fix items with None/missing IDs by assigning them proper sequential IDs."""
    if not items_list:
        return []
    
    # Find the highest existing ID
    valid_ids = [it.get('id') for it in items_list if it.get('id') is not None]
    next_id = (max(valid_ids) if valid_ids else 0) + 1
    
    # Fix items with None IDs
    for item in items_list:
        if item.get('id') is None:
            item['id'] = next_id
            next_id += 1
    
    return items_list


def _next_id(lst: list) -> int:
    """Generate a unique integer ID that is 1 higher than any existing id."""
    if not lst:
        return 1
    # Get max ID, treating None as 0
    valid_ids = [it.get('id', 0) for it in lst if it.get('id') is not None]
    if not valid_ids:
        return 1
    return max(valid_ids) + 1


# ── Raw DB helpers ─────────────────────────────────────────────────────────

def _row_to_user(row: dict) -> dict:
    """Normalise a raw Supabase row into the in-memory user dict."""
    u = dict(row)
    # Integers
    for k, default in [('weekly_points', 0), ('all_time_points', 0),
                        ('total_words', 0), ('xp', 0), ('bitcoin', 0),
                        ('level', 1), ('last_level', 1), ('backpack_slots', 5)]:
        u[k] = int(u.get(k) or default)
    # Normalize week_start to just the date part (Supabase may return full timestamp)
    if u.get('week_start'):
        u['week_start'] = u['week_start'].split('T')[0]
    
    # JSONB fields may arrive as string or list/dict
    for k in ('inventory', 'unclaimed_items'):
        val = u.get(k, '[]')
        if isinstance(val, str):
            try:
                u[k] = json.loads(val)
            except Exception:
                u[k] = []
        elif val is None:
            u[k] = []
        # Defensive: ensure it's always a list (e.g. registered as {} by old code)
        if not isinstance(u.get(k), list):
            u[k] = []
    
    # Parse military, traps, buffs, buildings, weapons JSONB fields
    for k in ('military', 'traps', 'buffs', 'weapons', 'buildings', 'building_queue'):
        val = u.get(k, '{}')
        if isinstance(val, str):
            try:
                u[k] = json.loads(val)
            except Exception:
                u[k] = {}
        elif val is None:
            u[k] = {}
    
    # Parse base_resources JSONB field with COMPLETE structure
    val = u.get('base_resources', '{}')
    if isinstance(val, str):
        try:
            base_res = json.loads(val)
        except Exception:
            base_res = {}
    elif val is None:
        base_res = {}
    else:
        base_res = dict(val) if val else {}
    
    # CRITICAL: Ensure base_resources has complete resource types (wood, bronze, iron, stone, relics)
    # NOT silver - we use stone as the 4th tier
    if 'resources' not in base_res or not isinstance(base_res.get('resources'), dict):
        base_res['resources'] = {}
    
    # Ensure ALL resource types exist (don't rely on stored value which might have old structure)
    default_resources = {'wood': 0, 'bronze': 0, 'iron': 0, 'stone': 0, 'relics': 0, 'incubus': 0}
    stored_resources = base_res.get('resources', {})
    
    # Merge: keep stored values but ensure all keys exist
    for res_type, default_val in default_resources.items():
        if res_type not in stored_resources:
            stored_resources[res_type] = default_val
    
   
   
    
    base_res['resources'] = stored_resources
    
    # Ensure food and streak exist
    if 'food' not in base_res:
        base_res['food'] = 0
    if 'current_streak' not in base_res:
        base_res['current_streak'] = 0
    
    u['base_resources'] = base_res
     # Handle base_layout
    if isinstance(u.get("base_layout"), str):
        try:
            u["base_layout"] = json.loads(u["base_layout"])
        except:
            u["base_layout"] = get_default_base_layout()
    elif not u.get("base_layout"):
        u["base_layout"] = get_default_base_layout()
    
    
    return u


def get_user(user_id: str) -> dict | None:
    try:
        r = supabase.table(DB_TABLE).select("*").eq(
            "user_id", str(user_id)
        ).execute()
        if r.data:
            user = r.data[0]
            user = normalize_user(user)      # Fix all JSON fields
            from teleport_system import on_user_load
            user = on_user_load(user)        # Run passive ticks
            user = sync_player_passive_energy(user)  # Recalculate energy every load, not just on use
            user = sync_shield_state(user)  # Correct expired shield_status/shield_expires_at every load
            return user
        return None
    except Exception as e:
        print(f"[DB ERROR] get_user: {e}")
        return None
    
    
def get_or_save_user(user_id: str, data: dict | None) -> dict | None:
    '''
    If data is None: acts as getter — returns user dict.
    If data is dict: acts as setter — saves and returns None.
    Used by systems that need to inject DB access without circular imports.
    '''
    if data is None:
        return get_user(user_id)
    else:
        save_user(user_id, data)
        return None
    
def save_user(user_id, data: dict):
    d = dict(data)
    d.pop('id', None)
    # Extract base/resources data to save separately
    base_data = d.pop('base', None)
    resources_data = d.pop('resources', None)
    
    # Exclude fields that don't exist in DB schema
    # These are tracked in memory but not persisted to database
    d.pop('challenges', None)
    d.pop('metadata', None)
    d.pop('training_queue', None)
    d.pop('prestige', None)  # Prestige tier is in-memory only, not in DB
    
    # Serialize JSONB fields (inventory, unclaimed_items, military, traps, buffs, base_resources, weapons, buildings, building_queue)
    for k in ('inventory', 'unclaimed_items', 'military', 'traps', 'buffs', 'weapons', 'buildings', 'building_queue'):
        if isinstance(d.get(k), (list, dict)):
            d[k] = json.dumps(d[k])
    
    # Serialize base resources data if present
    if base_data or resources_data:
        # Combine base and resources into one structure
        base_structure = base_data or {}
        if resources_data and 'resources' not in base_structure:
            base_structure['resources'] = resources_data
        if base_structure:
            d['base_resources'] = json.dumps(base_structure)
    
    # Also serialize base_resources if it's a dict (not already JSON string)
    if isinstance(d.get('base_resources'), dict):
        d['base_resources'] = json.dumps(d['base_resources'])
    
    supabase.table(DB_TABLE).update(d).eq('user_id', str(user_id)).execute()

def save_weekly_winners():
    """Fetches current weekly leaderboard top 3 and snapshots them to last_week_winners."""
    try:
        current_week = _current_week_key()
        
        # 1. Get top 10 players from weekly leaderboard (excluding bots)
        res = supabase.table('leaderboard_weekly') \
            .select('user_id, username, points, is_bot') \
            .eq('week_key', current_week) \
            .order('points', desc=True) \
            .limit(10) \
            .execute()
        
        top_players = [p for p in (res.data or []) if not p.get('is_bot', False)][:10]

        if not top_players:
            print("[RESET] No real players found to save for last_week_winners.")
            return

        # 2. Clear old entries from last_week_winners (so it only holds the latest batch)
        supabase.table('last_week_winners').delete().neq('id', '').execute()

        # 3. Format & Insert new records
        records_to_insert = []
        for rank, p in enumerate(top_players, start=1):
            records_to_insert.append({
                'rank': rank,
                'username': p.get('username', 'Unknown'),
                'points': p.get('points', 0),
                'week_key': current_week
            })

        insert_res = supabase.table('last_week_winners').insert(records_to_insert).execute()
        print(f"[RESET] Successfully saved {len(records_to_insert)} winners to last_week_winners!")

    except Exception as e:
        print(f"[ERROR] Failed to save weekly winners: {e}")


def register_user(user_id, username: str):
    """Create a fresh account. Returns True on success, False on failure."""
    try:
        uid = str(user_id)
        r = supabase.table(DB_TABLE).select('user_id, username').eq('user_id', uid).execute()
        if r.data:
            if r.data[0].get('username') != username:
                supabase.table(DB_TABLE).update({'username': username}).eq('user_id', uid).execute()
            return True  # Already registered
        
        random_base_name = random.choice(DEFAULT_BASE_NAMES)
        supabase.table(DB_TABLE).insert({
            'user_id': uid,
            'username': username,
            'all_time_points': 0,
            'weekly_points': 0,
            'week_start': _current_week_key(),
            'total_words': 0,
            'bitcoin': 0,
            'xp': 0,
            'energy': 1000,
            'power': 0,
            'gold': 0,
            'level': 1,
            'last_level': 1,
            "teleport_charges": 0,
            "home_sector":  None, # Set when player chooses base plot
            "commander_location": 1,  # Start in Sector 1
            "shield_expires_at": None,
            "active_suit":  None,
            "energy_last_regen": None,
            "march_queue":  [],
            "research_queue": {},
            "banishments":  {},
            "visas":        {},
            "alliance_id":  None,
            "alliance_role": None,
            'backpack_slots': 5,
            'inventory': [],
            'unclaimed_items': [],
            "researches":   {},
            'sector': 1,
            'completed_tutorial': False,
            'base_name': random_base_name,
            'base_hq_level': 1,
            'login_streak': 0,
            'buildings': json.dumps({}),
            'building_queue': json.dumps({}),
            'base_resources': json.dumps({
                'resources': {'wood': 0, 'bronze': 0, 'iron': 0, 'stone': 0, 'relics': 0, 'incubus': 0},
                'food': 0,
                'current_streak': 0
            }),
            'military': json.dumps({"pawns": 5}),
            'traps': json.dumps({"spike_pit": 0}),
            'shield_status': 'UNPROTECTED',
            'credits': 0,
            'active_perks': {},
            'chess_stats': json.dumps({
                'rating': 1000,
                'wins': 0,
                'losses': 0,
                'draws': 0,
                'current_streak': 0,
                'best_streak': 0,
                'total_games': 0
            }),
        }).execute()
        give_automatic_shield(uid)   # ← add this line, one-time new-player shield
        print(f"[REGISTER SUCCESS] User {uid} ({username}) registered to Supabase")
        return True  # Registration succeeded
    except Exception as e:
        print(f"[REGISTER ERROR] Failed to register {user_id}: {e}")
        import traceback
        traceback.print_exc()
        return False  # Registration failed
def global_weekly_reset() -> bool:
    """
    Hard-resets weekly_points for ALL players in the database.
    Run this at Sunday midnight WAT / Monday 00:00 AM via a cron scheduler.
    """
    this_week = _current_week_key()
    try:
        print("[RESET] Starting global weekly points reset...")
        
        # 1. Fetch all rows that currently have weekly points or game-specific weekly points > 0
        # (This prevents modifying every single row if your DB scales up)
        result = supabase.table(DB_TABLE).select("user_id").gt("weekly_points", 0).execute()
        players_to_reset = result.data or []
        
        if not players_to_reset:
            print("[RESET] No active weekly scores found to clear.")
            return True
            
        print(f"[RESET] Clearing weekly scores for {len(players_to_reset)} players...")
        
        # 2. Update their records globally
        for row in players_to_reset:
            uid = row.get("user_id")
            payload = {
                'weekly_points': 0,
                'week_start': this_week,
                # Clear game specific columns if you use them:
                'fusion_weekly_points': 0,
                'fusion_week_start': this_week
            }
            supabase.table(DB_TABLE).update(payload).eq('user_id', uid).execute()
            
        print("[RESET] Global weekly slate wiped successfully!")
        return True
    except Exception as e:
        print(f"[RESET ERROR] Failed global reset: {e}")
        return False
    
def get_game_weekly_leaderboard(game_type="fusion", limit=10):
    """
    Weekly leaderboard for a specific game type.
    Tries the game-specific column (e.g. fusion_weekly_points).
    If that column doesn't exist or is empty, falls back to shared weekly_points.
    No week_start filtering — trust the stored value.
    """
    game_field = f"{game_type}_weekly_points"

    try:
        r = supabase.table(DB_TABLE) \
            .select(f"user_id, username, {game_field}, shield_status, name_shield_until") \
            .gt(game_field, 0) \
            .order(game_field, desc=True) \
            .limit(limit) \
            .execute()

        raw = r.data or []
        print(f"[LB] {game_field}: {len(raw)} rows returned")

        results = []
        for p in raw:
            pts = int(p.get(game_field) or 0)
            if pts <= 0:
                continue
            results.append({
                'id':                p['user_id'],
                'username':          p.get('username', 'Unknown'),
                'points':            pts,
                'shield_status':     p.get('shield_status') or 'UNPROTECTED',
                'name_shield_until': p.get('name_shield_until') or "Expired",
            })

        if results:
            print(f"[LB] {game_field}: returning {len(results)} players")
            return results

    except Exception as e:
        print(f"[LB] {game_field} not available ({e}) — using shared weekly_points fallback")

    # Fallback: use shared weekly_points (guaranteed to exist)
    return get_weekly_leaderboard(limit=limit)


def get_game_alltime_leaderboard(game_type="fusion", limit=10):
    """
    All-time leaderboard for a specific game type.
    Tries the game-specific column (e.g. fusion_all_time_points).
    Falls back to shared all_time_points if missing or empty.
    """
    game_field = f"{game_type}_all_time_points"

    try:
        r = supabase.table(DB_TABLE) \
            .select(f"user_id, username, {game_field}, is_bot, shield_status, name_shield_until") \
            .gt(game_field, 0) \
            .order(game_field, desc=True) \
            .limit(limit) \
            .execute()

        raw = r.data or []
        print(f"[LB] {game_field}: {len(raw)} rows returned")

        results = []
        for p in raw:
            if p.get('is_bot'):
                continue
            pts = int(p.get(game_field) or 0)
            if pts <= 0:
                continue
            results.append({
                'id':                p['user_id'],
                'username':          p.get('username', 'Unknown'),
                'points':            pts,
                'shield_status':     p.get('shield_status') or 'UNPROTECTED',
                'name_shield_until': p.get('name_shield_until') or "Expired",
            })

        if results:
            print(f"[LB] {game_field}: returning {len(results)} players")
            return results

    except Exception as e:
        print(f"[LB] {game_field} not available ({e}) — using shared all_time_points fallback")

    # Fallback: shared all_time_points (guaranteed to exist)
    return get_alltime_leaderboard(limit=limit)


def ensure_bot_exists(username: str, initial_points: int = 0):
    """Ensure a bot account exists in the database. Returns user_id."""
    # First find by username and is_bot=True
    r = supabase.table(DB_TABLE).select('user_id').eq('username', username).eq('is_bot', True).execute()
    if r.data:
        return r.data[0]['user_id']
        
    # Generate a unique pseudo user_id for the bot
    import hashlib
    bot_id = "bot_" + hashlib.md5(username.encode()).hexdigest()[:12]
    
    random_base_name = random.choice(DEFAULT_BASE_NAMES)
    supabase.table(DB_TABLE).upsert({
        'user_id': bot_id,
        'username': username,
        'is_bot': True,
        'all_time_points': 0,
        'weekly_points': initial_points,
        'week_start': _current_week_key(),
        'total_words': 0,
        'bitcoin': 0,
        'xp': 0,
        'level': 1,
        'last_level': 1,
        'backpack_slots': 5,
        'backpack_image': 'normal_backpack',
        'inventory': [],
        'unclaimed_items': [],
        'base_name': random_base_name,
        'base_resources': json.dumps({
            'resources': {'wood': 0, 'bronze': 0, 'iron': 0, 'stone': 0, 'relics': 0},
            'food': 0,
            'current_streak': 0
        }),
        'military': json.dumps({}),
        'traps': json.dumps({}),
        'shield_status': 'UNPROTECTED'
    }).execute()
    
    return bot_id


# ── Points (weekly + all-time) ─────────────────────────────────────────────

def add_points(user_id, points: int, username: str = '', game_type: str = 'fusion'):
    """
    Persist points for a player. Uses read-compute-write with full logging
    so any failure is visible in the Railway logs immediately.
    """
    uid       = str(user_id)
    this_week = _current_week_key()

    try:
        # ── Read current state ─────────────────────────────────────────────
        user = get_user(uid)
        if not user:
            register_user(uid, username)
            user = get_user(uid)
        if not user:
            print(f"[ADD_POINTS] CRITICAL: cannot find or create user {uid}")
            return

        last_week_date = (user.get('week_start') or '').split('T')[0]
        old_weekly     = int(user.get('weekly_points') or 0)
        old_alltime    = int(user.get('all_time_points') or 0)
        old_words      = int(user.get('total_words') or 0)

        # Reset weekly if week has rolled over
        new_weekly  = points if last_week_date != this_week else old_weekly + points
        new_alltime = old_alltime + points
        new_words   = old_words + 1

        payload = {
            'weekly_points':   new_weekly,
            'all_time_points': new_alltime,
            'total_words':     new_words,
            'week_start':      this_week,
        }

        # ── Write ──────────────────────────────────────────────────────────
        result = supabase.table(DB_TABLE).update(payload).eq('user_id', uid).execute()

        if not (hasattr(result, 'data') and result.data):
            # Supabase returned empty — the user_id column value didn't match.
            # This happens when the PK column is named 'id' not 'user_id'.
            print(f"[ADD_POINTS] WARNING: eq('user_id') matched nothing for {uid} — checking DB schema")
            # Probe: fetch the row to see what column holds our ID
            probe = supabase.table(DB_TABLE).select('id, user_id').limit(1).execute()
            if probe.data:
                sample = probe.data[0]
                print(f"[ADD_POINTS] Sample row keys: {list(sample.keys())}")
                # If 'user_id' is a column but our value didn't match, the user might not exist
                # Try inserting a fresh registration then retrying
                register_user(uid, username or 'Player')
                supabase.table(DB_TABLE).update(payload).eq('user_id', uid).execute()
        else:
            print(f"[ADD_POINTS] ✅ {username or uid}: +{points}pts → weekly={new_weekly} alltime={new_alltime}")

        # ── Game-specific columns (best-effort, ignore if missing) ─────────
        gw_key  = f"{game_type}_weekly_points"
        ga_key  = f"{game_type}_all_time_points"
        gws_key = f"{game_type}_week_start"
        gw_prev = int(user.get(gw_key) or 0)
        ga_prev = int(user.get(ga_key) or 0)
        gw_date = (user.get(gws_key) or '').split('T')[0]

        new_gw = points if gw_date != this_week else gw_prev + points
        new_ga = ga_prev + points
        try:
            supabase.table(DB_TABLE).update({
                gw_key:  new_gw,
                ga_key:  new_ga,
                gws_key: this_week,
            }).eq('user_id', uid).execute()
        except Exception:
            pass  # columns don't exist yet — core points already saved

    except Exception as e:
        print(f"[ADD_POINTS] EXCEPTION for {uid}: {e}")
        import traceback
        traceback.print_exc()


def add_xp(user_id, amount: int) -> bool:
    user = get_user(str(user_id))
    if not user:
        return False
        
    user['xp'] = user.get('xp', 0) + amount
    
    # Simple Progressive Curve: Each level requires (Level * 150) XP
    # Level 1->2: 150 XP | Level 2->3: 300 XP | Level 10->11: 1500 XP
    current_xp = user['xp']
    lvl = 1
    while True:
        xp_needed_for_next = lvl * 150
        if current_xp >= xp_needed_for_next:
            current_xp -= xp_needed_for_next
            lvl += 1
        else:
            break
            
    user['level'] = lvl
    save_user(str(user_id), user)
    return True

def use_xp(user_id, amount: int) -> bool:
    user = get_user(str(user_id))
    if not user or user.get('xp', 0) < amount:
        return False
    user['xp'] -= amount
    save_user(str(user_id), user)
    return True


def add_bitcoin(user_id, amount: int, username: str = ''):
    user = get_user(str(user_id))
    if not user:
        register_user(user_id, username)
        user = get_user(str(user_id))
    user['bitcoin'] = user.get('bitcoin', 0) + amount
    save_user(str(user_id), user)


def award_word_score(user_id: str, pts: int, xp: int, bitcoin: int,
                     resources: dict, username: str = '', game_type: str = 'fusion', user_obj=None) -> dict:
    """
    ONE function, ONE DB read, ONE DB write for the entire word-score pipeline.
    Returns the updated user dict so the caller can use it without re-fetching.
    
    Pass user_obj to avoid redundant DB fetch if user was already loaded.
    
    Replaces: add_points() + add_xp() + add_bitcoin() + get_user() + save_user()
    That was 8-10 Supabase round-trips. This is 2 (read + write).
    """
    uid       = str(user_id)
    this_week = _current_week_key()

    # ── Single read ────────────────────────────────────────────────────────
    # Use passed user object if available, otherwise fetch from DB
    if user_obj:
        user = user_obj
    else:
        user = get_user(uid)
        if not user:
            register_user(uid, username)
            user = get_user(uid)
    if not user:
        return {}

    last_week_date = (user.get('week_start') or '').split('T')[0]
    old_weekly     = int(user.get('weekly_points') or 0)
    old_alltime    = int(user.get('all_time_points') or 0)
    old_words      = int(user.get('total_words') or 0)
    old_xp         = int(user.get('xp') or 0)
    old_bitcoin    = int(user.get('bitcoin') or 0)

    new_weekly     = pts if last_week_date != this_week else old_weekly + pts
    new_alltime    = old_alltime + pts
    new_words      = old_words + 1
    new_xp         = old_xp + xp
    new_level      = 1 + (new_xp // 100)
    new_bitcoin    = old_bitcoin + bitcoin

    # Game-specific weekly/alltime
    gw_key         = f"{game_type}_weekly_points"
    ga_key         = f"{game_type}_all_time_points"
    gw_date        = (user.get(f"{game_type}_week_start") or '').split('T')[0]
    gw_prev        = int(user.get(gw_key) or 0)
    ga_prev        = int(user.get(ga_key) or 0)
    new_gw         = pts if gw_date != this_week else gw_prev + pts
    new_ga         = ga_prev + pts

    # Resources
    base_res       = user.get('base_resources', {})
    if not isinstance(base_res, dict):
        base_res   = {}
    res_dict       = base_res.get('resources', {})
    if not isinstance(res_dict, dict):
        res_dict   = {}
    for rt, am in resources.items():
        res_dict[rt] = res_dict.get(rt, 0) + am
    base_res['resources'] = res_dict

    # ── Single write ───────────────────────────────────────────────────────
    payload = {
        'weekly_points':   new_weekly,
        'all_time_points': new_alltime,
        'total_words':     new_words,
        'week_start':      this_week,
        'xp':              new_xp,
        'level':           new_level,
        'bitcoin':         new_bitcoin,
        'base_resources':  json.dumps(base_res),
    }

    # Add game-specific fields (silently skipped by Supabase if columns missing)
    try:
        supabase.table(DB_TABLE).update({
            **payload,
            gw_key:                           new_gw,
            ga_key:                           new_ga,
            f"{game_type}_week_start":        this_week,
        }).eq('user_id', uid).execute()
    except Exception as e:
        # Game-specific columns don't exist — write core only
        try:
            supabase.table(DB_TABLE).update(payload).eq('user_id', uid).execute()
        except Exception as e:
            print(f"[AWARD_WORD] ❌ write failed for {uid}: {e}")
            return user

    # Update the in-memory user object for the caller
    user.update({
        'weekly_points':   new_weekly,
        'all_time_points': new_alltime,
        'total_words':     new_words,
        'week_start':      this_week,
        'xp':              new_xp,
        'level':           new_level,
        'bitcoin':         new_bitcoin,
        'base_resources':  base_res,
        gw_key:            new_gw,
        ga_key:            new_ga,
    })

    print(f"[AWARD_WORD] ✅ {username or uid}: +{pts}pts +{xp}xp +{bitcoin}btc "
          f"(weekly={new_weekly} alltime={new_alltime})")
    return user


def use_bitcoin(user_id, amount: int) -> bool:
    user = get_user(str(user_id))
    if not user or user.get('bitcoin', 0) < amount:
        return False
    user['bitcoin'] -= amount
    save_user(str(user_id), user)
    return True


def add_resources_from_word_length(user_id, word_length: int, username: str = '') -> dict:
    """Award resources based on word length: 3L→Wood, 4L→Bronze, 5L→Iron, 6L→Stone, 7L→Relics"""
    uid = str(user_id)
    user = get_user(uid)
    if not user:
        register_user(uid, username)
        user = get_user(uid)
    
    # Initialize resources if not present
    if 'resources' not in user or not isinstance(user.get('resources'), dict):
        user['resources'] = {'wood': 0, 'bronze': 0, 'iron': 0, 'stone': 0, 'relics': 0, 'incubus': 0}
    
    resources_awarded = {}
    
    # Award resources based on word length
    if word_length == 3:
        user['resources']['wood'] = user['resources'].get('wood', 0) + 1
        resources_awarded['wood'] = 1
    elif word_length == 4:
        user['resources']['bronze'] = user['resources'].get('bronze', 0) + 1
        resources_awarded['bronze'] = 1
    elif word_length == 5:
        user['resources']['iron'] = user['resources'].get('iron', 0) + 1
        resources_awarded['iron'] = 1
    elif word_length == 6:
        user['resources']['stone'] = user['resources'].get('stone', 0) + 1
        resources_awarded['stone'] = 1  # Different from the 'bitcoin' currency
    elif word_length >= 7:
        user['resources']['relics'] = user['resources'].get('relics', 0) + 1
        resources_awarded['relics'] = 1
    
    save_user(uid, user)
    return resources_awarded


def update_streak_and_award_food(user_id, correct: bool, username: str = '', user_obj=None) -> dict:
    """Track consecutive correct words and award food when streak >= 3.
    Store streak and food in base_resources JSONB, not as separate columns.
    
    Pass user_obj to avoid redundant DB fetch if user was already loaded."""
    uid = str(user_id)
    
    # Use passed user object if available, otherwise fetch from DB
    if user_obj:
        user = user_obj
    else:
        user = get_user(uid)
        if not user:
            register_user(uid, username)
            user = get_user(uid)
    
    # Initialize base_resources if not present
    if not user.get('base_resources'):
        user['base_resources'] = {
            'resources': {'wood': 0, 'bronze': 0, 'iron': 0, 'stone': 0, 'relics': 0, 'incubus': 0},
            'food': 0,
            'current_streak': 0
        }
    
    base_res = user['base_resources']
    if not isinstance(base_res, dict):
        base_res = {
            'resources': {'wood': 0, 'bronze': 0, 'iron': 0, 'stone': 0, 'relics': 0, 'incubus': 0},
            'food': 0,
            'current_streak': 0
        }
        user['base_resources'] = base_res
    
    food_awarded = 0
    streak_status = "broken"
    old_streak = base_res.get('current_streak', 0)
    old_food = base_res.get('food', 0)
    
    if correct:
        base_res['current_streak'] = base_res.get('current_streak', 0) + 1
        current_streak = base_res['current_streak']
        
        # Award food based on streak
        if current_streak >= 3:
            # Award 1 food per streak (so 3-streak = 1 food, 4-streak = 2 food, etc.)
            food_to_award = current_streak - 2
            base_res['food'] = base_res.get('food', 0) + food_to_award
            food_awarded = food_to_award
            streak_status = f"streak_{current_streak}"
            print(f"[STREAK_CALC] Streak {old_streak}→{current_streak}, Rations: {old_food}→{base_res['food']} (+{food_to_award})")
        else:
            print(f"[STREAK_CALC] Streak {old_streak}→{current_streak}, Rations: 0 (need 3)")
    else:
        # Wrong word - reset streak
        base_res['current_streak'] = 0
        streak_status = "broken"
        print(f"[STREAK_CALC] Reset streak from {old_streak} to 0")
    
    user['base_resources'] = base_res
    save_user(uid, user)
    
    return {
        "streak": base_res.get('current_streak', 0),
        "food_awarded": food_awarded,
        "status": streak_status
    }


def set_sector(user_id, sector_id):
    user = get_user(str(user_id))
    if user:
        user['sector'] = sector_id
        save_user(str(user_id), user)

def set_commander_location(user_id, sector_id):
    user = get_user(str(user_id))
    if user:
        user['commander_location'] = sector_id
        save_user(str(user_id), user)


# ── Leaderboards ───────────────────────────────────────────────────────────

def get_weekly_leaderboard(limit: int = 10) -> list:
    """
    Return top players by weekly_points.
    Shows anyone with weekly_points > 0.
    We trust the stored value — add_points resets it when the week rolls over.
    No week_start filter here (that was hiding valid scores due to timezone drift).
    """
    try:
        r = supabase.table(DB_TABLE) \
            .select('user_id, username, weekly_points, shield_status, name_shield_until') \
            .gt('weekly_points', 0) \
            .order('weekly_points', desc=True) \
            .limit(limit) \
            .execute()

        raw = r.data or []
        print(f"[LB] weekly: {len(raw)} rows returned")

        results = []
        for p in raw:
            pts = int(p.get('weekly_points') or 0)
            if pts <= 0:
                continue
            results.append({
                'id':                p['user_id'],
                'username':          p.get('username', 'Unknown'),
                'points':            pts,
                'shield_status':     p.get('shield_status') or 'UNPROTECTED',
                'name_shield_until': p.get('name_shield_until') or "Expired",
            })

        print(f"[LB] weekly: returning {len(results)} players")
        return results

    except Exception as e:
        print(f"[ERROR] get_weekly_leaderboard: {e}")
        import traceback
        traceback.print_exc()
        return []


def get_alltime_leaderboard(limit: int = 10) -> list:
    try:
        r = supabase.table(DB_TABLE) \
            .select('user_id, username, all_time_points, total_words, is_bot, shield_status, name_shield_until') \
            .gt('all_time_points', 0) \
            .order('all_time_points', desc=True) \
            .limit(limit * 5) \
            .execute()

        raw = r.data or []
        print(f"[LB] alltime: {len(raw)} rows returned")
        results = [
            {
                'id':                p['user_id'],
                'username':          p.get('username', 'Unknown'),
                'points':            int(p.get('all_time_points') or 0),
                'words':             int(p.get('total_words') or 0),
                'shield_status':     p.get('shield_status') or 'UNPROTECTED',
                'name_shield_until': p.get('name_shield_until') or "Expired",
            }
            for p in raw
            if not p.get('is_bot') and int(p.get('all_time_points') or 0) > 0
        ]
        return results[:limit]
    except Exception as e:
        print(f"[ERROR] get_alltime_leaderboard: {e}")
        import traceback
        traceback.print_exc()
        return []


# ── Inventory ──────────────────────────────────────────────────────────────
def get_inventory_item(user: dict, item_key: str) -> dict:
    """Safely retrieves an item from the user's inventory list array.
    Matches on either 'item_key' (Schema A) or 'type' (Schema B) since
    both field names can appear on inventory rows.
    """
    inventory = user.get("inventory", []) or []
    for item in inventory:
        if isinstance(item, dict) and (item.get("item_key") == item_key or item.get("type") == item_key):
            return item
    return {}

def add_inventory_item(user: dict, item_key: str, qty: int, display_name: str, category: str = "consumable", xp_reward: int = 0, multiplier_value: int = 0) -> dict:
    """Adds an item or increments its quantity safely, ensuring no data loss.
    Writes BOTH field-name schemas so every inventory-reading code path works:
      Schema A: item_key / qty / display   (used by get_inventory_item, store purchases)
      Schema B: type / quantity            (used by claim_item, most of main.py's display/use code)
    """
    if not isinstance(user.get("inventory"), list):
        user["inventory"] = []  # never silently accept a dict/None here

    # Check if the player already owns at least one copy of this item
    item = get_inventory_item(user, item_key)
    if item:
        new_qty = item.get("qty", item.get("quantity", 0)) + qty
        item["qty"]      = new_qty
        item["quantity"] = new_qty
    else:
        from supabase_db import _next_id
        user["inventory"].append({
            "id": _next_id(user["inventory"]),
            # Schema A
            "item_key": item_key,
            "qty": qty,
            "display": display_name,
            "category": category,
            # Schema B aliases
            "type": item_key,
            "quantity": qty,
            "name": display_name,
            "xp_reward": xp_reward,
            "multiplier_value": multiplier_value,
            "acquired": datetime.utcnow().isoformat(),
        })
    return user

def remove_inventory_item(user: Dict[str, Any], item_key: str) -> Dict[str, Any]:
    """Removes one instance of an item by key."""
    inventory = user.get("inventory", [])
    
    for item in inventory:
        if item.get("item_key") == item_key:
            if item.get("quantity", 1) > 1:
                item["quantity"] -= 1
            else:
                inventory.remove(item)
            break
            
    user["inventory"] = inventory
    return user

def get_max_slots(user: dict) -> int:
    """Helper to return max backpack slots, defaulting to 20 if missing."""
    return int(user.get('backpack_slots', 5))

def is_backpack_full(user: dict) -> bool:
    """
    Checks if the total unique item slots used exceeds the maximum allowed slots.
    Note: Stackable items grouped in a single dictionary count as 1 slot.
    """
    current_slots_used = len(user.get('inventory', []) or [])
    max_slots = get_max_slots(user)
    return current_slots_used >= max_slots

def upgrade_backpack(user_id, additional_slots: int = 5) -> Tuple[bool, str]:
    """
    Increases the player's total storage cap and updates their backpack tier aesthetics.
    """
    user = get_user(str(user_id))
    if not user:
        return False, "❌ Player profile not found."
        
    current_slots = get_max_slots(user)
    new_slots = current_slots + additional_slots
    
    user['backpack_slots'] = new_slots
    
    # Dynamically scale tiers based on slot sizes
    if new_slots >= 40:
        user['backpack_image'] = 'military_tactical_pack'
    elif new_slots >= 30:
        user['backpack_image'] = 'premium_vault_backpack'
    else:
        user['backpack_image'] = 'normal_backpack'
        
    save_user(str(user_id), user)
    return True, f"✅ Backpack upgraded successfully! Max capacity increased from {current_slots} ➡️ {new_slots} slots."
# ── Shield helpers ──────────────────────────────────────────────────────
SHIELD_DISRUPT_MINUTES = 10       # fixed lockout + amount drained from remaining shield time
NEW_PLAYER_SHIELD_HOURS = 24      # one-time grant at registration only
def sync_shield_state(user: dict) -> dict:
    """
    Bring shield_status up to date based on elapsed time. Call this before
    reading OR mutating shield state anywhere.
    - ACTIVE past shield_expires_at -> UNPROTECTED
    - DISRUPTED past shield_disrupted_until -> reactivate with whatever
      shield_expires_at is left, or UNPROTECTED if nothing's left
    """
    status = user.get("shield_status", "UNPROTECTED")
    now = datetime.utcnow()

    if status == "ACTIVE":
        exp_str = user.get("shield_expires_at")
        if exp_str:
            try:
                if now >= datetime.fromisoformat(exp_str):
                    user["shield_status"] = "UNPROTECTED"
                    user["shield_expires_at"] = None
            except Exception:
                pass

    elif status == "DISRUPTED":
        until_str = user.get("shield_disrupted_until")
        if until_str:
            try:
                if now >= datetime.fromisoformat(until_str):
                    exp_str = user.get("shield_expires_at")
                    still_has_time = False
                    if exp_str:
                        try:
                            still_has_time = now < datetime.fromisoformat(exp_str)
                        except Exception:
                            pass
                    user["shield_status"] = "ACTIVE" if still_has_time else "UNPROTECTED"
                    if not still_has_time:
                        user["shield_expires_at"] = None
                    user["shield_disrupted_until"] = None
            except Exception:
                pass

    return user
def is_shielded(user: dict) -> bool:
    user = sync_shield_state(user)
    return user.get('shield_status', 'UNPROTECTED') == 'ACTIVE'

def activate_shield(user_id: str, item_key: str) -> tuple[bool, str]:
    """Player-triggered only — consumes one shield item from the backpack."""
    user = get_user(user_id)
    if not user:
        return False, "❌ User profile not found."

    from store_system import STORE_ITEMS
    shield_data = STORE_ITEMS.get(item_key)
    if not shield_data:
        return False, "❌ Shield configuration not found."

    user = sync_shield_state(user)
    status = user.get('shield_status', 'UNPROTECTED')

    if status == 'DISRUPTED':
        until_str = user.get('shield_disrupted_until')
        try:
            until = datetime.fromisoformat(until_str) if until_str else None
        except Exception:
            until = None
        mins_left = int((until - datetime.utcnow()).total_seconds() // 60) + 1 if until else SHIELD_DISRUPT_MINUTES
        return False, f"⚠️ Shield DISRUPTED — locked out for {mins_left} more minute(s)."

    hours = shield_data.get("duration_h", 8)
    now = datetime.utcnow()

    user['shield_status'] = 'ACTIVE'
    user['shield_expires_at'] = (now + timedelta(hours=hours)).isoformat()
    user['shield_disrupted_until'] = None
    user = remove_inventory_item(user, item_key)   # actually consume it now
    user.pop('shield_cooldown', None)  # Clear old structural cooldown tracking flags safely

    save_user(user_id, user)
    return True, f"🛡️ Shield activated successfully! Base protected for the next {hours} hours."

def reset_all_shields():
    """Reset all players' shields to UNPROTECTED (in-memory only)."""
    try:
        users = supabase.table(DB_TABLE).select('user_id').execute().data
        reset_count = 0
        for user_data in users:
            try:
                user_id = user_data.get('user_id')
                user = get_user(user_id)
                if user:
                    # Reset shield status in-memory (not saved to DB)
                    user['shield_status'] = 'UNPROTECTED'
                    user.pop('shield_expires', None)  # Remove legacy permanent shield
                    user.pop('shield_cooldown', None)  # Clear any cooldowns
                    # NOTE: These changes are NOT persisted to database
                    # (shield_status column doesn't exist in schema)
                    reset_count += 1
            except Exception as e:
                # Silently continue - in-memory operations don't fail on DB issues
                continue
        print(f"[OK] All shields reset to UNPROTECTED status (in-memory)")
        return reset_count
    except Exception as e:
        print(f"[ERROR] reset_all_shields failed: {e}")
        return 0


# ── Unclaimed items ────────────────────────────────────────────────────────

def _crate_xp(item_type: str) -> int:
    """Return a proper random XP value for a given crate type."""
    t = item_type.lower()
    if 'super' in t:
        return random.randint(50, 200)
    elif 'wood' in t:
        return random.randint(50, 100)
    elif 'bronze' in t:
        return random.randint(100, 150)
    elif 'iron' in t:
        return random.randint(150, 200)
    return random.randint(30, 80)


def add_unclaimed_item(user_id, item_type: str, amount: int = 1,
                        xp_reward: int = None, multiplier_value: int = 0):
    """Add an unclaimed reward. xp_reward is auto-set for crates if not supplied."""
    user = get_user(str(user_id))
    if not user:
        return
    unclaimed = user.get('unclaimed_items', [])
    # Ensure unclaimed is a list (defensive: could be dict from old registrations or bad DB state)
    if not isinstance(unclaimed, list):
        unclaimed = list(unclaimed.values()) if isinstance(unclaimed, dict) else []
    # Auto-assign XP for crates
    if xp_reward is None:
        xp_reward = _crate_xp(item_type) if 'crate' in item_type.lower() else 0

    unclaimed.append({
        'id':               _next_id(unclaimed),
        'type':             item_type,
        'amount':           amount,
        'xp_reward':        xp_reward,
        'multiplier_value': multiplier_value,
        'created_at':       datetime.utcnow().isoformat(),
    })
    user['unclaimed_items'] = unclaimed
    save_user(str(user_id), user)

def get_unclaimed_items(user_id) -> list:
    user = get_user(str(user_id))
    if not user:
        return []
    unclaimed = user.get('unclaimed_items', [])
    # Fix any items with None IDs
    unclaimed = _fix_item_ids(unclaimed)
    # Save the fixed unclaimed back if any items were fixed
    if any(it.get('id') is None for it in user.get('unclaimed_items', [])):
        user['unclaimed_items'] = unclaimed
        save_user(str(user_id), user)
    return unclaimed


def claim_item(user_id, item_id: int):
    """
    Claim ONE unclaimed item identified by its unique 'id' field.
    - Stackable items (crates, shields, teleports) merge into one inventory slot.
    - Non-stackable items require a free backpack slot.
    - Backpack items increase backpack_slots instead of entering inventory.
    Returns (True, msg) or (False, reason).
    """
    uid = str(user_id)
    user = get_user(uid)
    if not user:
        return False, "Not registered"

    unclaimed = user.get('unclaimed_items', [])
    item = next((it for it in unclaimed if it.get('id') == item_id), None)
    if not item:
        return False, "Item not found"

    item_type = item.get('type', '')
    inv = user.get('inventory', [])
    if not isinstance(inv, list):
        inv = []

    # Special handling: backpack upgrades don't enter inventory
    if 'backpack' in item_type.lower():
        old_slots = user.get('backpack_slots', 5)
        new_slots = old_slots + 15
        user['backpack_slots'] = new_slots
        user['unclaimed_items'] = [it for it in unclaimed if it.get('id') != item_id]
        save_user(uid, user)
        return True, f"Backpack upgraded! Capacity: {old_slots} → {new_slots} slots"

    # Stackable items: merge into existing slot or use one slot for all of this type
    if item_type in STACKABLE_ITEMS:
        existing = next((s for s in inv if s.get('type') == item_type or s.get('item_key') == item_type), None)
        if existing:
            # Increment quantity on the existing stack — no new slot needed
            new_qty = existing.get('quantity', existing.get('qty', 1)) + 1
            existing['quantity'] = new_qty
            existing['qty'] = new_qty
        else:
            # No existing stack — needs a free slot
            if len(inv) >= user.get('backpack_slots', 5):
                return False, "Inventory full — buy more backpack slots or use an item first"
            inv.append({
                'id':       _next_id(inv),
                'type':     item_type,
                'quantity': 1,
                'item_key': item_type,
                'qty':      1,
                'display':  item_type.replace('_', ' ').title(),
                'category': 'consumable',
                'xp_reward':        item.get('xp_reward', 0),
                'multiplier_value': item.get('multiplier_value', 0),
                'acquired': datetime.utcnow().isoformat(),
            })
        user['inventory']       = inv
        user['unclaimed_items'] = [it for it in unclaimed if it.get('id') != item_id]
        save_user(uid, user)
        return True, f"{item_type.replace('_', ' ').title()} added to stack"

    # Non-stackable: requires a free slot
    if len(inv) >= user.get('backpack_slots', 5):
        return False, "Inventory full — buy more backpack slots or use an item first"

    inv.append({
        'id':               _next_id(inv),
        'type':             item_type,
        'quantity':         1,
        'item_key':         item_type,
        'qty':              1,
        'display':          item_type.replace('_', ' ').title(),
        'category':         'consumable',
        'xp_reward':        item.get('xp_reward', 0),
        'multiplier_value': item.get('multiplier_value', 0),
        'acquired':         datetime.utcnow().isoformat(),
    })
    user['inventory']       = inv
    user['unclaimed_items'] = [it for it in unclaimed if it.get('id') != item_id]
    save_user(uid, user)
    return True, "Item claimed successfully"


def remove_unclaimed_item(user_id, item_id: int):
    user = get_user(str(user_id))
    if not user:
        return
    user['unclaimed_items'] = [it for it in user.get('unclaimed_items', []) if it.get('id') != item_id]
    save_user(str(user_id), user)


# ── Levels ─────────────────────────────────────────────────────────────────

def calculate_level(xp: int) -> int:
    return 1 + (xp // 100)


def check_level_up(user_id):
    """Return (old_level, new_level) if leveled up, else (None, None)."""
    user = get_user(str(user_id))
    if not user:
        return None, None
    old = user.get('last_level', 1)
    new = user.get('level', 1)
    if new > old:
        user['last_level'] = new
        save_user(str(user_id), user)
        return old, new
    return None, None


# ── Profile ────────────────────────────────────────────────────────────────

def get_profile(user_id) -> dict | None:
    user = get_user(str(user_id))
    if not user:
        return None
    inv      = user.get('inventory', [])
    uncl     = user.get('unclaimed_items', [])
    xp       = user.get('xp', 0)
    energy   = user.get('energy', 0)
    gold   = user.get('gold', 0)
    level    = user.get('level', 1)
    xp_prog  = xp % 100
    shielded = is_shielded(user)
    
    # Get resources and food from base_resources
    base_res = user.get('base_resources', {})
    resources_dict = base_res.get('resources', {})
    food = base_res.get('food', 0)
    
    return {
        'username':        user.get('username', 'Unknown'),
        'level':           level,
        'xp':              xp,
        'xp_progress':     xp_prog,
        'xp_needed':       100,
        'bitcoin':          user.get('bitcoin', 0),
        'all_time_points': user.get('all_time_points', 0),
        'weekly_points':   user.get('weekly_points', 0),
        'total_words':     user.get('total_words', 0),
        'sector':          user.get('sector'),
        'energy':          user.get('energy'),
        'power':           user.get('power'),
        'buildings':       user.get('buildings', {}),
        'gold':            user.get('gold'),
        'sector_display':  get_sector_display(user.get('sector')),
        'backpack_slots':  user.get('backpack_slots', 5),
        'inventory_count': len(inv),
        'unclaimed_count': len(uncl),
        'crate_count':     sum(1 for i in inv if 'crate' in i.get('type','').lower()),
        'shield_count':    sum(1 for i in inv if i.get('item_key', '').startswith('shield_')),
        'shielded':        shielded,
        'shield_expires_at':user.get('shield_expires_at'),
        'shield_disrupted_until':  user.get('shield_disrupted_until'),
        'base_name':       user.get('base_name'),
        'base_resources':  resources_dict,
        'base_food':       food,
    }


# ── Sectors ────────────────────────────────────────────────────────────────

def load_sectors() -> dict:
    sectors = {}
    if not os.path.exists(SECTORS_FILE):
        return sectors
    try:
        with open(SECTORS_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except OSError:
        return sectors
    for line in lines[1:]:
        line = line.strip()
        if not line or line.startswith('SectorID'):
            continue
        parts = line.split('\t')
        if len(parts) >= 4:
            try:
                sid = int(parts[0])
                sectors[sid] = {
                    'name':        parts[3].strip(),
                    'environment': parts[1].strip() if len(parts) > 1 else '',
                    'energy':      parts[2].strip() if len(parts) > 2 else '',
                    'perks':       parts[4].strip() if len(parts) > 4 else '',
                }
            except Exception:
                pass
    return sectors


def get_sector_display(sector_id, sectors=None) -> str:
    if sector_id is None:
        return 'Not Assigned'
    if sectors is None:
        sectors = load_sectors()
    try:
        sid  = int(sector_id)
        info = sectors.get(sid)
        return f'#{sid} {info["name"]}' if info else f'Sector {sid}'
    except (TypeError, ValueError):
        return f'Sector {sector_id}'


# ── Powerful milestone items ───────────────────────────────────────────────

def award_powerful_locked_item(user_id):
    items = [
        ('legendary_artifact', '⚔️ LEGENDARY ARTIFACT', 'An ancient weapon of unimaginable power.'),
        ('mythical_crown',     '👑 MYTHICAL CROWN',      'The crown of a forgotten god.'),
        ('void_stone',         '🌑 VOID STONE',          'A stone from beyond the stars.'),
        ('eternal_flame',      '🔥 ETERNAL FLAME',       'A flame that never dies.'),
        ('celestial_key',      '🗝️ CELESTIAL KEY',       'A key to dimensions you cannot yet comprehend.'),
    ]
    item_type, display, desc = random.choice(items)
    add_unclaimed_item(user_id, f'locked_{item_type}', 1, xp_reward=0)
    return display, desc


# ── Round management (streak resets every 120s) ─────────────────────────────

def get_all_users() -> list:
    """Fetch all users from database for roundly streak reset."""
    try:
        r = supabase.table(DB_TABLE).select('*').execute()
        return r.data if r.data else []
    except Exception as e:
        print(f"[ERROR] get_all_users failed: {e}")
        return []

# ═══════════════════════════════════════════════════════════════════════════
# PASTE BLOCK 2 — Teleport grant (replaces the broken version)
# main.py imports: grant_free_teleports_to_all
# ═══════════════════════════════════════════════════════════════════════════
def get_sector_state(sector_id: int) -> dict:
    try:
        r = supabase.table("sector_state").select("*").eq(
            "sector_id", sector_id
        ).execute()
        if r.data:
            state = r.data[0]
            # Normalize JSON fields
            for field in ["occupancy", "roaming", "dominance", "active_predators",
                          "pending_notifications", "incoming_marches"]:
                state[field] = safe_json(state.get(field), default={})
            for field in ["sector_chat", "pending_ruler_alerts"]:
                state[field] = safe_json(state.get(field), default=[])
            return state
        # Return empty state if not seeded yet
        return {"sector_id": sector_id, "occupancy": {}, "roaming": {},
                "sector_chat": [], "dominance": {}, "active_predators": {}}
    except Exception as e:
        print(f"[DB ERROR] get_sector_state {sector_id}: {e}")
        return {"sector_id": sector_id, "occupancy": {}, "roaming": {},
                "sector_chat": [], "dominance": {}, "active_predators": {}}

def save_sector_state(sector_id: int, state: dict) -> None:
    try:
        state["last_updated"] = datetime.utcnow().isoformat()
        supabase.table("sector_state").upsert(
            {"sector_id": sector_id, **state}
        ).execute()
    except Exception as e:
        print(f"[DB ERROR] save_sector_state {sector_id}: {e}")

import json as _json
from datetime import datetime as _dt, timedelta as _td


# ═══════════════════════════════════════════════════════════════════════════
#  JSON SAFETY — fixes 'str object has no attribute append'
# ═══════════════════════════════════════════════════════════════════════════

def safe_json(value, default=None):
    """Parse a value that might be a JSON string or already parsed dict/list."""
    if default is None:
        default = {}
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        v = value.strip()
        if not v or v in ('null', 'None', ''):
            return default
        try:
            return _json.loads(v)
        except Exception:
            return default
    return default


def normalize_user(user: dict) -> dict:
    """Normalize all JSON fields on a user dict from Supabase."""
    if not user:
        return user

    # NOTE: inventory is a LIST not a dict — kept in list_fields
    dict_fields = [
        "military", "buildings", "building_queue",
        "researches", "research_queue", "base_resources", "traps",
        "weapons", "buffs", "banishments", "visas", "visa_applications",
        "commander_location", "current_node", "active_suit",
        "skill_points_spent", "dominance_scores",
    ]
    for field in dict_fields:
        user[field] = safe_json(user.get(field), default={})

    list_fields = [
        "inventory", "unclaimed_items", "march_queue", "eject_log",
        "teleport_history", "visa_queue",
    ]
    for field in list_fields:
        val = safe_json(user.get(field), default=[])
        user[field] = val if isinstance(val, list) else (list(val.values()) if isinstance(val, dict) else [])

    if not user.get("commander_location"):
        user["commander_location"] = 1

    base_res = user.get("base_resources", {})
    if not isinstance(base_res, dict):
        base_res = {}
    if not isinstance(base_res.get("resources"), dict):
        base_res["resources"] = {}
    user["base_resources"] = base_res

    if user.get("credits") is None:
        user["credits"] = 0

    return user


# ═══════════════════════════════════════════════════════════════════════════
#  CREDITS SYSTEM
# ═══════════════════════════════════════════════════════════════════════════
CREDITS_PER_STAR = 30   # 1 ⭐ Star = 30 Credits (matches the rate shown in credits_info)
CREDITS_TO_PLAY     = 10
CREDITS_DAILY_LOGIN = 50
CREDITS_RANK_REWARDS = {
    1: 50, 2: 45, 3: 30, 4: 20, 5: 10,
    6: 5,  7: 5,  8: 5,  9: 5,  10: 5,
}
GOLD_PER_STAR = 1

def get_credits(user_id: str) -> int:
    user = get_user(str(user_id))
    if not user:
        return 0
    return int(user.get("credits", 0) or 0)


def add_credits(user_id: str, amount: int) -> int:
    user = get_user(str(user_id))
    if not user:
        return 0
    current = int(user.get("credits", 0) or 0)
    new_bal = current + amount
    save_user(str(user_id), {**user, "credits": new_bal})
    return new_bal


def spend_credits(user_id: str, amount: int, reason: str = None) -> tuple:
    user = get_user(str(user_id))
    if not user:
        return False, 0
    current = int(user.get("credits", 0) or 0)
    if current < amount:
        return False, current
    new_bal = current - amount
    save_user(str(user_id), {**user, "credits": new_bal})
    return True, new_bal

def add_gold(user_id: str, amount: int) -> int:
    """Add gold to a player. Returns new balance."""
    user = get_user(str(user_id))
    if not user:
        return 0
    current = int(user.get("gold", 0) or 0)
    new_bal = current + amount
    save_user(str(user_id), {**user, "gold": new_bal})
    return new_bal


def spend_gold(user_id: str, amount: int) -> tuple:
    """
    Spend gold. Returns (success: bool, new_balance: int).
    Fails if player doesn't have enough.
    """
    user = get_user(str(user_id))
    if not user:
        return False, 0
    current = int(user.get("gold", 0) or 0)
    if current < amount:
        return False, current
    new_bal = current - amount
    save_user(str(user_id), {**user, "gold": new_bal})
    return True, new_bal


def claim_daily_login_credits(user_id: str) -> tuple:
    """
    Claim daily login credits with a 7-day reward streak.
    Returns (awarded: bool, amount: int, new_balance: int, current_streak: int).
    Can only be claimed once per UTC day.
    """
    from datetime import datetime, timedelta, timezone
    from supabase_db import get_user as _get_user, save_user as _save_user
    
    user = _get_user(str(user_id))
    if not user:
        return False, 0, 0, 0

    # Define the 7-day credit reward matrix
    STREAK_REWARDS = {1: 50, 2: 60, 3: 75, 4: 100, 5: 125, 6: 150, 7: 200}

    # Use modern timezone-aware UTC dates to clear your terminal warnings
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")

    last_claim = user.get("last_credit_login", "")
    current_credits = int(user.get("credits", 0) or 0)
    login_streak = int(user.get("login_streak", 0) or 0)

    # 1. Block if already claimed today
    if last_claim == today:
        return False, 0, current_credits, login_streak

    # 2. Calculate the streak progress
    if last_claim == yesterday:
        # Progress streak, reset back to 1 if they completed day 7 yesterday
        if login_streak >= 7:
            new_streak = 1
        else:
            new_streak = login_streak + 1
    else:
        # Missed a day or brand new player -> Start at Day 1
        new_streak = 1

    # 3. Determine reward values
    amount = STREAK_REWARDS.get(new_streak, 50)
    new_bal = current_credits + amount

    # 4. Save updated payload back to Supabase
    updated_fields = {
        **user,
        "credits": new_bal,
        "last_credit_login": today,
        "login_streak": new_streak
    }

    # Optional: If Day 7, add your bronze crate item here!
    if new_streak == 7:
        from supabase_db import add_inventory_item
        user = add_inventory_item(user, "crt_brz", 1, "🥉 Bronze Crate", category="consumable")

    updated_fields = {
        **user,
        "credits": new_bal,
        "last_credit_login": today,
        "login_streak": new_streak
    }

    _save_user(str(user_id), updated_fields)
    
    return True, amount, new_bal, new_streak


def award_scoreboard_credits(user_id: str, rank: int) -> int:
    amount = CREDITS_RANK_REWARDS.get(rank, 0)
    if amount > 0:
        add_credits(str(user_id), amount)
    return amount


# ═══════════════════════════════════════════════════════════════════════════
#  TELEPORT GRANT
# ═══════════════════════════════════════════════════════════════════════════
# supabase_db.py — add near add_credits/add_gold

def claim_daily_teleports(user_id: str) -> tuple:
    """
    Claim 3 free teleport charges. ADDS to existing balance — never overwrites.
    Once per UTC calendar day; if the player doesn't tap the claim button that
    day, that day's free teleports simply don't get granted — no stacking of
    missed days, but charges they already own are never touched.
    Returns (claimed: bool, message: str, new_charges: int).
    """
    user = get_user(str(user_id))
    if not user:
        return False, "❌ User not found.", 0

    today = datetime.utcnow().strftime("%Y-%m-%d")
    if user.get("teleport_daily_claimed_date") == today:
        current = int(user.get("teleport_charges", 0) or 0)
        return False, "⏳ Already claimed today — come back tomorrow!", current

    current = int(user.get("teleport_charges", 0) or 0)
    new_charges = current + 3
    save_user(str(user_id), {
        **user,
        "teleport_charges": new_charges,
        "teleport_daily_claimed_date": today,
    })
    return True, f"🌀 +3 Teleport Charges claimed! Total: {new_charges}", new_charges


# ═══════════════════════════════════════════════════════════════════════════
#  SHIELD FUNCTIONS
#  You said you don't want to give free shields automatically.
#  grant_free_shields_to_all is a no-op stub — it's imported by main.py
#  but does nothing. The other functions are real.
# ═══════════════════════════════════════════════════════════════════════════
def give_automatic_shield(user_id: str, duration_hours: int = NEW_PLAYER_SHIELD_HOURS) -> bool:
    """
    Grant a shield ONLY at registration, to help new players learn the game
    safely. Never called automatically after this — every shield beyond
    this one is player-activated from their backpack.
    """
    try:
        user = get_user(str(user_id))
        if not user:
            return False
        expires = (datetime.now(timezone.utc) + timedelta(hours=duration_hours)).isoformat()
        save_user(str(user_id), {
            **user,
            "shield_status": "ACTIVE",
            "shield_expires_at": expires,
            "shield_disrupted_until": None,
        })
        return True
    except Exception as e:
        print(f"[SHIELD] give_automatic_shield error: {e}")
        return False

def deactivate_shield(user_id: str) -> tuple:
    """
    Called automatically by scout/attack action handlers — going on the
    offensive forfeits your own shield. Not a player-facing command.
    """
    user = get_user(str(user_id))
    if not user:
        return False, "Player not found"

    user = sync_shield_state(user)
    if user.get("shield_status") != "ACTIVE":
        return False, "No active shield to deactivate"

    save_user(str(user_id), {
        **user,
        "shield_status": "UNPROTECTED",
        "shield_expires_at": None,
    })
    return True, "🔓 Shield deactivated — you're now vulnerable."

def disrupt_shield(user_id: str) -> tuple:
    """
    First hit on a shielded base: locks the player out of shield protection
    for a fixed SHIELD_DISRUPT_MINUTES, and drains that same amount off the
    remaining shield timer. Cannot be sped up. If the remaining timer was
    shorter than the disrupt window, the shield expires outright once the
    lockout ends instead of going negative.
    """
    user = get_user(str(user_id))
    if not user:
        return False, "Player not found"

    user = sync_shield_state(user)
    if user.get("shield_status") != "ACTIVE":
        return False, "Target has no active shield to disrupt"

    now = datetime.utcnow()
    exp_str = user.get("shield_expires_at")
    try:
        exp = datetime.fromisoformat(exp_str) if exp_str else now
    except Exception:
        exp = now

    remaining = exp - now
    drained = remaining - timedelta(minutes=SHIELD_DISRUPT_MINUTES)
    new_expires_at = (now + drained).isoformat() if drained > timedelta(0) else None
    disrupted_until = (now + timedelta(minutes=SHIELD_DISRUPT_MINUTES)).isoformat()

    save_user(str(user_id), {
        **user,
        "shield_status": "DISRUPTED",
        "shield_expires_at": new_expires_at,
        "shield_disrupted_until": disrupted_until,
    })
    return True, f"Shield disrupted for {SHIELD_DISRUPT_MINUTES} minutes!"


def restore_shield_after_attack(user_id: str) -> bool:
    """
    Called if an attack was defended successfully — attacker's disruption attempt failed.
    No change to shield needed, but logs the event.
    Returns True always.
    """
    print(f"[SHIELD] Attack on {user_id} defended — shield intact")
    return True


# ═══════════════════════════════════════════════════════════════════════════
#  MISC STUBS / WRAPPERS
#  These exist so main.py imports work. If you already have these
#  functions in supabase_db.py, the later definition wins — safe to paste.
# ═══════════════════════════════════════════════════════════════════════════

def add_randomized_gift(user_id: str) -> dict:
    """
    Award a random gift item to a player.
    Returns dict describing what was given, or {} if nothing.
    Extend this to add real gift logic when ready.
    """
    import random
    gifts = [
        {"type": "credits", "amount": 25,  "display": "+25 credits"},
        {"type": "credits", "amount": 50,  "display": "+50 credits"},
        {"type": "resource","resource": "iron",   "amount": 20, "display": "+20 iron"},
        {"type": "resource","resource": "bronze", "amount": 30, "display": "+30 bronze"},
        {"type": "teleport","amount": 1,   "display": "+1 teleport charge"},
    ]
    gift = random.choice(gifts)

    try:
        user = get_user(str(user_id))
        if not user:
            return {}

        if gift["type"] == "credits":
            add_credits(str(user_id), gift["amount"])

        elif gift["type"] == "resource":
            base_res = safe_json(user.get("base_resources"), default={})
            resources = safe_json(base_res.get("resources"), default={})
            resources[gift["resource"]] = resources.get(gift["resource"], 0) + gift["amount"]
            base_res["resources"] = resources
            save_user(str(user_id), {**user, "base_resources": base_res})

        elif gift["type"] == "teleport":
            current = int(user.get("teleport_charges") or 0)
            save_user(str(user_id), {**user, "teleport_charges": current + 1})

    except Exception as e:
        print(f"[GIFT] add_randomized_gift error: {e}")
        return {}

    return gift


def reset_all_streaks() -> None:
    """
    Reset all player current streaks (called at round end).
    Only resets current_streak, not all_time records.
    """
    try:
        # Batch update — set current_streak to 0 for all players
        # We do this via base_resources JSONB update
        result = supabase.table(DB_TABLE).select(
            "user_id, base_resources"
        ).execute()

        for row in (result.data or []):
            try:
                uid      = row.get("user_id")
                base_res = safe_json(row.get("base_resources"), default={})
                if base_res.get("current_streak", 0) > 0:
                    base_res["current_streak"] = 0
                    supabase.table(DB_TABLE).update({
                        "base_resources": base_res
                    }).eq("user_id", uid).execute()
            except Exception:
                pass

    except Exception as e:
        print(f"[STREAKS] reset_all_streaks error: {e}")

def sync_player_passive_energy(user: dict) -> dict:
    """
    Calculates passive energy recovery based on elapsed time.
    Regenerates up to a hard ceiling of 1000 energy in exactly 1 hour.
    """
    max_energy = 1000
    reg_rate_per_sec = 1000 / 3600  # 0.2778 per second
    
    current_energy = user.get("energy", 0)
    
    # If already at max capacity, update the tracking timestamp and return
    if current_energy >= max_energy:
        user["energy"] = max_energy
        user["energy_last_updated_at"] = datetime.utcnow().isoformat()
        return user

    last_update_str = user.get("energy_last_updated_at")
    if not last_update_str:
        # Fallback if the field doesn't exist yet
        user["energy_last_updated_at"] = datetime.utcnow().isoformat()
        return user

    try:
        last_update = datetime.fromisoformat(last_update_str)
        elapsed_seconds = (datetime.utcnow() - last_update).total_seconds()
        
        if elapsed_seconds > 0:
            # Calculate gained energy
            gained = elapsed_seconds * reg_rate_per_sec
            new_energy = min(max_energy, current_energy + gained)
            
            user["energy"] = int(new_energy)
            user["energy_last_updated_at"] = datetime.utcnow().isoformat()
    except Exception:
        pass

    return user

def activate_energy_cell_from_backpack(user_id: str, item_key: str) -> tuple[bool, str]:
    """
    Consumes an energy item from the player's backpack.
    Restricts total energy from exceeding the hard ceiling cap of 1000.
    """
    user = get_user(user_id)
    if not user:
        return False, "❌ User profile not found."

    # Force a passive regeneration sync first so their energy is up-to-date
    user = sync_player_passive_energy(user)

    current_energy = user.get("energy", 0)
    max_energy = 1000

    if current_energy >= max_energy:
        return False, f"⚠️ Your Energy Core is already completely filled! ({current_energy}/{max_energy})"

    # Fetch configuration properties from catalog
    from store_system import STORE_ITEMS
    item_data = STORE_ITEMS.get(item_key)
    if not item_data:
        return False, "❌ Item data configurations not found."

    # Determine how much energy this specific cell item restores (default to 250)
    energy_to_restore = item_data.get("energy", 250)

    # Apply boost capped at 1000 max
    user["energy"] = min(max_energy, current_energy + energy_to_restore)
    
    # Update timestamp so passive generation adjusts to the new value properly
    user["energy_last_updated_at"] = datetime.utcnow().isoformat()

    # Deduct 1 item from inventory backpack
    user = remove_inventory_item(user, item_key)

    save_user(user_id, user)
    return True, f"⚡ Charged up! Core energy updated to {user['energy']}/{max_energy}."


def use_energy(user_id: str, amount: int) -> tuple[bool, str, int]:
    """
    Spend energy on an action. NEVER refuses — players can always use energy,
    even if it drives their balance to 0 or negative, so they can waste it
    strategically or take a risk on a low tank.
    Returns (success: bool, message: str, new_energy: int).
    `success` is always True here; kept in the return signature so callers
    that check `ok, msg = use_energy(...)` style still work without changes.
    """
    user = get_user(user_id)
    if not user:
        return False, "❌ User profile not found.", 0

    # Sync passive regen first so the deduction starts from an accurate value
    user = sync_player_passive_energy(user)

    current_energy = user.get("energy", 0)
    new_energy = current_energy - amount   # intentionally allowed to go negative

    user["energy"] = new_energy
    user["energy_last_updated_at"] = datetime.utcnow().isoformat()
    save_user(user_id, user)

    if new_energy < 0:
        return True, f"⚡ Used {amount} energy. Core is now overdrawn: {new_energy}/1000.", new_energy
    return True, f"⚡ Used {amount} energy. Remaining: {new_energy}/1000.", new_energy

def use_resource_pack_from_backpack(user_id: str, item_key: str) -> tuple:
    """
    Apply a resource pack's contents (food or a base resource) to the
    player's base, then consume exactly one unit from the backpack.
    """
    user = get_user(str(user_id))
    if not user:
        return False, "❌ User profile not found."

    row = get_inventory_item(user, item_key)
    if not row or row.get("category") != "resource_pack":
        return False, "❌ You don't have this resource pack."

    res_type = row.get("res_type")
    res_amount = row.get("res_amount", 0)

    base_res = user.get("base_resources", {})
    if not isinstance(base_res, dict):
        base_res = {"resources": {}, "food": 0, "current_streak": 0}

    if res_type == "food":
        base_res["food"] = base_res.get("food", 0) + res_amount
    else:
        resources = base_res.get("resources", {})
        if not isinstance(resources, dict):
            resources = {}
        resources[res_type] = resources.get(res_type, 0) + res_amount
        base_res["resources"] = resources

    user["base_resources"] = base_res
    user = remove_inventory_item(user, item_key)
    save_user(user_id, user)

    return True, f"📦 +{res_amount:,} {res_type.title()} added to your warehouse!"
def start_operation(user_id: str, op_type: str, duration_seconds: int,
                     target_id: str = None, target_name: str = None,
                     extra: dict = None) -> dict:
    """
    op_type: 'attack_march' | 'scout_march' | 'scout_return' |
             'battle_sim' | 'shield_disrupt'
    Every timed thing in the game becomes one of these rows.
    """
    user = get_user(user_id)
    if not user:
        return {}
    now = datetime.utcnow()
    ops = user.get("active_operations", [])
    if not isinstance(ops, list):
        ops = []
    op = {
        "id": _next_id(ops),
        "type": op_type,
        "target_id": target_id,
        "target_name": target_name,
        "started_at": now.isoformat(),
        "ends_at": (now + timedelta(seconds=duration_seconds)).isoformat(),
        "extra": extra or {},
    }
    ops.append(op)
    user["active_operations"] = ops
    save_user(user_id, user)
    return op


def clear_operation(user_id: str, op_id: int):
    user = get_user(user_id)
    if not user:
        return
    ops = [o for o in user.get("active_operations", []) if o.get("id") != op_id]
    user["active_operations"] = ops
    save_user(user_id, user)

def render_progress_bar(started_at: str, ends_at: str, width: int = 10) -> str:
    try:
        start = datetime.fromisoformat(started_at)
        end = datetime.fromisoformat(ends_at)
        now = datetime.utcnow()
        total = (end - start).total_seconds()
        elapsed = max(0, (now - start).total_seconds())
        pct = 100 if total <= 0 else max(0, min(100, int((elapsed / total) * 100)))
        filled = pct * width // 100
        bar = "█" * filled + "░" * (width - filled)
        remaining = max(0, (end - now).total_seconds())
        m, s = divmod(int(remaining), 60)
        return f"[{bar}] {pct}% — {m}m {s}s left"
    except Exception:
        return "[░░░░░░░░░░] --"
    
OP_LABELS = {
    "attack_march":   "⚔️ Marching to attack {target}",
    "scout_march":    "🕵️ Scout en route to {target}",
    "scout_return":   "🐀 Scout returning home",
    "battle_sim":     "💥 Battle underway at {target}",
    "shield_disrupt": "🛡️💥 Shield disrupted",
}

def get_active_operations_display(user_id: str) -> str:
    user = get_user(user_id)
    if not user:
        return "No active operations."
    ops = user.get("active_operations", [])
    now = datetime.utcnow()
    lines = []
    for op in ops:
        try:
            if now >= datetime.fromisoformat(op["ends_at"]):
                continue  # expired — a separate resolver processes completion
        except Exception:
            continue
        label = OP_LABELS.get(op["type"], op["type"]).format(target=op.get("target_name", "?"))
        lines.append(f"{label}\n{render_progress_bar(op['started_at'], op['ends_at'])}")
    return "\n\n".join(lines) if lines else "🟢 No active operations."
MARCH_DURATION_SECONDS = 180          # 3 min flat for now — later: distance-based
BATTLE_SIM_MIN, BATTLE_SIM_MAX = 15, 20
SCOUT_RETURN_DURATION_SECONDS = 180   # separate leg, for future interception mechanic

async def _shield_warning_or_none(user_id: str) -> str | None:
    """Returns warning text if shielded, else None (safe to proceed silently)."""
    user = get_user(user_id)
    user = sync_shield_state(user)
    if user.get("shield_status") != "ACTIVE":
        return None
    exp = datetime.fromisoformat(user["shield_expires_at"])
    remaining = exp - datetime.utcnow()
    h, rem = divmod(int(remaining.total_seconds()), 3600)
    m, _ = divmod(rem, 60)
    return f"⚠️ This will deactivate YOUR shield immediately.\nTime remaining: {h}h {m}m\n\nProceed anyway?"

def apply_speedup_to_operation(user_id: str, operation_id: int, item_key: str) -> tuple:
    user = get_user(user_id)
    row = get_inventory_item(user, item_key)
    if not row or row.get("category") != "speedup":
        return False, "❌ Invalid speedup item."
    minutes = row.get("reduces_timer_minutes", 5)
    ops = user.get("active_operations", [])
    op = next((o for o in ops if o.get("id") == operation_id), None)
    if not op:
        return False, "❌ Operation not found."
    ends = datetime.fromisoformat(op["ends_at"]) - timedelta(minutes=minutes)
    op["ends_at"] = max(datetime.utcnow(), ends).isoformat()
    user["active_operations"] = ops
    user = remove_inventory_item(user, item_key)
    save_user(user_id, user)
    return True, f"⏩ -{minutes}m applied!"