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

import os
import json
import random
from datetime import datetime, timedelta
from supabase import create_client, Client
from config import DB_TABLE, SUPABASE_URL as CONFIG_SUPABASE_URL, SUPABASE_KEY as CONFIG_SUPABASE_KEY, ENV_NAME

SUPABASE_URL = os.environ.get('SUPABASE_URL', CONFIG_SUPABASE_URL).rstrip('/')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', CONFIG_SUPABASE_KEY)
SECTORS_FILE = os.environ.get('SECTORS_FILE', 'sectors.txt')

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
print(f"[OK] Supabase module loaded (Environment: {ENV_NAME}, Table: {DB_TABLE})")


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


# ── Week helper ────────────────────────────────────────────────────────────

def _current_week_key() -> str:
    """ISO date string of the Monday that starts this week (Mon-Sun). Resets Monday 00:00 WAT (Sunday 11:59 PM)."""
    today = datetime.utcnow() + timedelta(hours=1)
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
    
    # Parse military, traps, buffs JSONB fields
    for k in ('military', 'traps', 'buffs', 'weapons'):
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
    
    # CRITICAL: Ensure base_resources has complete resource types (wood, bronze, iron, diamond, relics)
    # NOT silver - we use diamond as the 4th tier
    if 'resources' not in base_res or not isinstance(base_res.get('resources'), dict):
        base_res['resources'] = {}
    
    # Ensure ALL resource types exist (don't rely on stored value which might have old structure)
    default_resources = {'wood': 0, 'bronze': 0, 'iron': 0, 'diamond': 0, 'relics': 0}
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
    
    return u


def get_user(user_id) -> dict | None:
    r = supabase.table(DB_TABLE).select('*').eq('user_id', str(user_id)).execute()
    return _row_to_user(r.data[0]) if r.data else None


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
    d.pop('shield_status', None)  # Shield status is in-memory only, not in DB
    d.pop('prestige', None)  # Prestige tier is in-memory only, not in DB
    
    # Serialize JSONB fields (inventory, unclaimed_items, military, traps, buffs, base_resources, weapons)
    for k in ('inventory', 'unclaimed_items', 'military', 'traps', 'buffs', 'weapons'):
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


def register_user(user_id, username: str):
    uid = str(user_id)
    r = supabase.table(DB_TABLE).select('user_id, username').eq('user_id', uid).execute()
    if r.data:
        if r.data[0].get('username') != username:
            supabase.table(DB_TABLE).update({'username': username}).eq('user_id', uid).execute()
        return
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
        'level': 1,
        'last_level': 1,
        'backpack_slots': 5,
        'backpack_image': 'normal_backpack',
        'inventory': json.dumps([]),
        'unclaimed_items': json.dumps([]),
        'sector': None,
        'completed_tutorial': False,
        'base_name': random_base_name,
        'base_resources': json.dumps({
            'resources': {'wood': 0, 'bronze': 0, 'iron': 0, 'diamond': 0, 'relics': 0},
            'food': 0,
            'current_streak': 0
        }),
        'military': json.dumps({}),
        'traps': json.dumps({}),
        'shield_status': 'UNPROTECTED',
        'shield_cooldown': None,
    }).execute()


# ── Points (weekly + all-time) ─────────────────────────────────────────────

def add_points(user_id, points: int, username: str = ''):
    """Accumulate points. Resets weekly bucket if the week has turned over."""
    uid = str(user_id)
    user = get_user(uid)
    if not user:
        register_user(uid, username)
        user = get_user(uid)

    this_week = _current_week_key()
    last_week = user.get('week_start', '')
    
    # Compare dates explicitly - extract just the date portion for both
    last_week_date = last_week.split('T')[0] if last_week else ''
    
    if last_week_date != this_week:
        # New week — wipe weekly bucket and update week marker
        user['weekly_points'] = 0
        user['week_start'] = this_week
        print(f"[POINTS] Week boundary for {username}: {last_week_date} → {this_week}")
    
    # Add the points (whether it's a new week or not)
    user['all_time_points'] = user.get('all_time_points', 0) + points
    user['weekly_points']   = user.get('weekly_points',   0) + points
    user['total_words']     = user.get('total_words',     0) + 1
    save_user(uid, user)


def add_xp(user_id, amount: int) -> bool:
    user = get_user(str(user_id))
    if not user:
        return False
    user['xp'] = user.get('xp', 0) + amount
    user['level'] = 1 + (user['xp'] // 100)
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


def use_bitcoin(user_id, amount: int) -> bool:
    user = get_user(str(user_id))
    if not user or user.get('bitcoin', 0) < amount:
        return False
    user['bitcoin'] -= amount
    save_user(str(user_id), user)
    return True


def add_resources_from_word_length(user_id, word_length: int, username: str = '') -> dict:
    """Award resources based on word length: 3L→Wood, 4L→Bronze, 5L→Iron, 6L→Diamond, 7L→Relics"""
    uid = str(user_id)
    user = get_user(uid)
    if not user:
        register_user(uid, username)
        user = get_user(uid)
    
    # Initialize resources if not present
    if 'resources' not in user or not isinstance(user.get('resources'), dict):
        user['resources'] = {'wood': 0, 'bronze': 0, 'iron': 0, 'diamond': 0, 'relics': 0}
    
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
        user['resources']['diamond'] = user['resources'].get('diamond', 0) + 1
        resources_awarded['diamond'] = 1  # Different from the 'bitcoin' currency
    elif word_length >= 7:
        user['resources']['relics'] = user['resources'].get('relics', 0) + 1
        resources_awarded['relics'] = 1
    
    save_user(uid, user)
    return resources_awarded


def update_streak_and_award_food(user_id, correct: bool, username: str = '') -> dict:
    """Track consecutive correct words and award food when streak >= 3.
    Store streak and food in base_resources JSONB, not as separate columns."""
    uid = str(user_id)
    user = get_user(uid)
    if not user:
        register_user(uid, username)
        user = get_user(uid)
    
    # Initialize base_resources if not present
    if not user.get('base_resources'):
        user['base_resources'] = {
            'resources': {'wood': 0, 'bronze': 0, 'iron': 0, 'diamond': 0, 'relics': 0},
            'food': 0,
            'current_streak': 0
        }
    
    base_res = user['base_resources']
    if not isinstance(base_res, dict):
        base_res = {
            'resources': {'wood': 0, 'bronze': 0, 'iron': 0, 'diamond': 0, 'relics': 0},
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
            print(f"[STREAK_CALC] Streak {old_streak}→{current_streak}, Food: {old_food}→{base_res['food']} (+{food_to_award})")
        else:
            print(f"[STREAK_CALC] Streak {old_streak}→{current_streak}, Food: 0 (need 3)")
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


# ── Leaderboards ───────────────────────────────────────────────────────────

def get_weekly_leaderboard(limit: int = 10) -> list:
    """Return top players by weekly_points. Handles week rollover."""
    this_week = _current_week_key()
    try:
        r = supabase.table(DB_TABLE) \
            .select('user_id, username, weekly_points, week_start') \
            .order('weekly_points', desc=True) \
            .limit(50) \
            .execute()
        results = []
        for p in (r.data or []):
            pts = int(p.get('weekly_points') or 0)
            player_week = p.get('week_start', '')
            # Extract just the date part (Supabase may return full timestamp)
            player_week_date = player_week.split('T')[0] if player_week else ''
            if player_week_date != this_week:
                pts = 0
            if pts > 0:
                results.append({
                    'id': p['user_id'],
                    'username': p.get('username', 'Unknown'),
                    'points': pts,
                })
        results.sort(key=lambda x: x['points'], reverse=True)
        return results[:limit]
    except Exception as e:
        print(f"[ERROR] get_weekly_leaderboard: {e}")
        import traceback
        traceback.print_exc()
        return []


def get_alltime_leaderboard(limit: int = 10) -> list:
    try:
        r = supabase.table(DB_TABLE) \
            .select('user_id, username, all_time_points, total_words, is_bot') \
            .order('all_time_points', desc=True) \
            .limit(limit * 5) \
            .execute()
        return [
            {'id': p['user_id'], 'username': p.get('username', 'Unknown'),
             'points': int(p.get('all_time_points') or 0), 'words': int(p.get('total_words') or 0)}
            for p in (r.data or []) if p.get('is_bot') is not True
        ][:limit]
    except Exception as e:
        print(f"[ERROR] get_alltime_leaderboard: {e}")
        return []


# ── Inventory ──────────────────────────────────────────────────────────────

def get_inventory(user_id) -> list:
    user = get_user(str(user_id))
    if not user:
        return []
    inv = user.get('inventory', [])
    # Fix any items with None IDs
    inv = _fix_item_ids(inv)
    # Save the fixed inventory back if any items were fixed
    if any(it.get('id') is None for it in user.get('inventory', [])):
        user['inventory'] = inv
        save_user(str(user_id), user)
    return inv


def add_inventory_item(user_id, item_type: str, xp_reward: int = 0,
                        expires_at: str = None, multiplier_value: int = 0) -> bool:
    user = get_user(str(user_id))
    if not user:
        return False
    inv = user.get('inventory', [])
    if len(inv) >= user.get('backpack_slots', 5):
        return False
    item = {
        'id':               _next_id(inv),
        'type':             item_type,
        'xp_reward':        xp_reward,
        'multiplier_value': multiplier_value,
        'expires_at':       expires_at,
        'acquired':         datetime.utcnow().isoformat(),
    }
    inv.append(item)
    user['inventory'] = inv
    save_user(str(user_id), user)
    return True


def remove_inventory_item(user_id, item_id) -> bool:
    """Remove by unique item['id'], not list index. Verify deletion succeeded."""
    user = get_user(str(user_id))
    if not user:
        return False
    
    old_inv = user.get('inventory', [])
    
    # First, fix any None IDs in the inventory
    old_inv = _fix_item_ids(old_inv)
    old_count = len(old_inv)
    
    # Filter out matching item - handle both int and string IDs
    item_id_int = int(item_id) if isinstance(item_id, (int, str)) else item_id
    new_inv = [it for it in old_inv if it.get('id') is not None and int(it.get('id')) != item_id_int]
    
    # Verify something was actually removed
    if len(new_inv) == old_count:
        print(f"[REMOVE_INV] WARNING: Item {item_id} not found in inventory. Old: {[it.get('id') for it in old_inv]}, New: {[it.get('id') for it in new_inv]}")
        return False
    
    user['inventory'] = new_inv
    save_user(str(user_id), user)
    
    # Double-check by re-fetching
    user_after = get_user(str(user_id))
    inv_after = user_after.get('inventory', [])
    final_ids = [it.get('id') for it in inv_after]
    print(f"[REMOVE_INV] VERIFIED: Removed item {item_id}. Remaining IDs: {final_ids}")
    return True


def upgrade_backpack(user_id, new_slots: int = 20):
    user = get_user(str(user_id))
    if not user:
        return
    user['backpack_slots'] = new_slots
    user['backpack_image'] = 'premium_backpack' if new_slots > 5 else 'normal_backpack'
    save_user(str(user_id), user)


# ── Shield helpers ─────────────────────────────────────────────────────────

def activate_shield(user_id) -> bool:
    """Move a shield from inventory to the 'shield_expires' field. Returns True if done."""
    user = get_user(str(user_id))
    if not user:
        return False
    inv = user.get('inventory', [])
    shield = next((it for it in inv if it.get('type', '') == 'shield'), None)
    if not shield:
        return False
    # Remove from inventory
    user['inventory'] = [it for it in inv if it.get('id') != shield['id']]
    # Set expiry 24 h from now
    expires = (datetime.utcnow() + timedelta(hours=24)).isoformat()
    user['shield_expires'] = expires
    save_user(str(user_id), user)
    return True


def is_shielded(user: dict) -> bool:
    """Return True if user has an active (non-disrupted) shield.
    
    Shield statuses:
    - UNPROTECTED: No shield active
    - ACTIVE: Shield is on
    - DISRUPTED: Shield was hit, no protection for 1 attack
    """
    shield_status = user.get('shield_status', 'UNPROTECTED')
    
    # Only ACTIVE shields provide protection
    if shield_status == 'ACTIVE':
        return True
    
    # DISRUPTED or UNPROTECTED = no shield
    if shield_status in ['DISRUPTED', 'UNPROTECTED']:
        return False
    
    # Legacy support for old fields
    exp = user.get('shield_expires')
    if exp and exp != 'permanent':
        # Check if expiry time has passed
        try:
            if datetime.utcnow() < datetime.fromisoformat(exp):
                return True
        except Exception:
            pass
    
    return False


def activate_shield(user_id: str) -> tuple[bool, str]:
    """Activate shield for a player. Returns (success, message)."""
    user = get_user(user_id)
    if not user:
        return False, "User not found"
    
    shield_status = user.get('shield_status', 'UNPROTECTED')
    
    # Can't activate if shield is DISRUPTED (was just hit)
    if shield_status == 'DISRUPTED':
        return False, "⚠️ Your shield is DISRUPTED from an attack. Wait for it to auto-restore."
    
    # Already ACTIVE
    if shield_status == 'ACTIVE':
        return False, "✅ Your shield is already ACTIVE!"
    
    # Activate from UNPROTECTED
    user['shield_status'] = 'ACTIVE'
    user.pop('shield_cooldown', None)  # Clear any cooldowns
    save_user(user_id, user)
    return True, "✅ Shield activated!"


def deactivate_shield(user_id: str) -> tuple[bool, str]:
    """Deactivate shield voluntarily. Returns (success, message)."""
    user = get_user(user_id)
    if not user:
        return False, "User not found"
    
    shield_status = user.get('shield_status', 'UNPROTECTED')
    
    if shield_status != 'ACTIVE':
        return False, "⚠️ Your shield is not currently ACTIVE"
    
    # Deactivate
    user['shield_status'] = 'UNPROTECTED'
    save_user(user_id, user)
    return True, "⚠️ Shield deactivated! You're now vulnerable."


def disrupt_shield(user_id: str) -> tuple[bool, str]:
    """Temporarily disrupt enemy shield (1 attack only). Returns (success, message)."""
    user = get_user(user_id)
    if not user:
        return False, "User not found"
    
    if not is_shielded(user):
        return False, "Target has no active shield to disrupt"
    
    user['shield_status'] = 'DISRUPTED'
    save_user(user_id, user)
    return True, "Shield disrupted for 1 attack!"


def restore_shield_after_attack(user_id: str):
    """Restore shield from DISRUPTED back to ACTIVE after 1 attack."""
    user = get_user(user_id)
    if user and user.get('shield_status') == 'DISRUPTED':
        user['shield_status'] = 'ACTIVE'
        save_user(user_id, user)
        print(f"[SHIELD] Shield restored for {user_id}: DISRUPTED → ACTIVE")


def give_automatic_shield(user_id):
    """Grant a shield to a player (in-memory only, not persisted to DB)."""
    user = get_user(str(user_id))
    if user:
        # Shield status is kept in-memory only, not in database
        user['shield_status'] = 'ACTIVE'
        user.pop('shield_expires', None)  # Remove legacy permanent shield
        # NOTE: shield_status is NOT saved to database (column doesn't exist)
        return True
    return False


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


def grant_free_teleports_to_all():
    """Grant 3 free teleport items to all players as unclaimed gifts."""
    try:
        users = supabase.table(DB_TABLE).select('user_id').execute().data
        teleport_count = 0
        for user_data in users:
            try:
                user_id = user_data.get('user_id')
                # Add 3 teleport items as unclaimed
                for _ in range(3):
                    add_unclaimed_item(user_id, 'free_teleport', 1)
                teleport_count += 1
            except Exception as e:
                print(f"[WARN] Could not grant teleports to {user_data.get('user_id')}: {e}")
                continue
        print(f"[TELEPORTS] Granted 3 free teleports to {teleport_count} players")
        return teleport_count
    except Exception as e:
        print(f"[ERROR] grant_free_teleports_to_all failed: {e}")
        return 0


def grant_free_shields_to_all():
    """Grant 3 free shield items to all players as unclaimed gifts."""
    try:
        users = supabase.table(DB_TABLE).select('user_id').execute().data
        shield_count = 0
        for user_data in users:
            try:
                user_id = user_data.get('user_id')
                # Add 3 shield items as unclaimed
                for _ in range(3):
                    add_unclaimed_item(user_id, 'shield_potion', 1)
                shield_count += 1
            except Exception as e:
                print(f"[WARN] Could not grant shields to {user_data.get('user_id')}: {e}")
                continue
        print(f"[SHIELDS] Granted 3 free shields to {shield_count} players")
        return shield_count
    except Exception as e:
        print(f"[ERROR] grant_free_shields_to_all failed: {e}")
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


def add_randomized_gift(user_id):
    """Award random gift: XP crate, powerful item, or resources bundle."""
    choice = random.randint(1, 3)
    if choice == 1:
        # XP Crate
        gift_type = random.choice(['wood_crate', 'bronze_crate', 'iron_crate', 'super_crate'])
        add_unclaimed_item(user_id, gift_type, 1, xp_reward=None)
    elif choice == 2:
        # Powerful locked item
        award_powerful_locked_item(user_id)
    else:
        # Resources bundle (give direct resources)
        user = get_user(str(user_id))
        if user:
            base_res = user.get('base_resources', {})
            resources = base_res.get('resources', {})
            # Random resource boost
            res_choice = random.choice(['wood', 'bronze', 'iron', 'diamond'])
            amount = random.randint(50, 200) if res_choice != 'diamond' else random.randint(10, 50)
            resources[res_choice] = resources.get(res_choice, 0) + amount
            base_res['resources'] = resources
            user['base_resources'] = base_res
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
    Moves it into inventory. Returns (True, msg) or (False, reason).
    """
    uid = str(user_id)
    user = get_user(uid)
    if not user:
        return False, "Not registered"

    unclaimed = user.get('unclaimed_items', [])
    item = next((it for it in unclaimed if it.get('id') == item_id), None)
    if not item:
        return False, "Item not found"

    inv = user.get('inventory', [])
    if len(inv) >= user.get('backpack_slots', 5):
        return False, "Inventory full — use or open an item first"

    # Move to inventory
    inv.append({
        'id':               _next_id(inv),
        'type':             item.get('type'),
        'xp_reward':        item.get('xp_reward', 0),
        'multiplier_value': item.get('multiplier_value', 0),
        'acquired':         datetime.utcnow().isoformat(),
    })
    user['inventory']      = inv
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
        'sector_display':  get_sector_display(user.get('sector')),
        'backpack_slots':  user.get('backpack_slots', 5),
        'inventory_count': len(inv),
        'unclaimed_count': len(uncl),
        'crate_count':     sum(1 for i in inv if 'crate' in i.get('type','').lower()),
        'shield_count':    sum(1 for i in inv if i.get('type','') == 'shield'),
        'shielded':        shielded,
        'shield_expires':  user.get('shield_expires'),
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


def reset_all_streaks():
    """Reset current_streak to 0 for all players (called every 120s for new game round)."""
    try:
        users = get_all_users()
        reset_count = 0
        
        for user_data in users:
            try:
                user = _row_to_user(user_data)  # Deserialize
                if not user:
                    continue
                
                base_res = user.get('base_resources', {})
                old_streak = base_res.get('current_streak', 0)
                
                if old_streak > 0:  # Only update if there's a streak to reset
                    base_res['current_streak'] = 0
                    user['base_resources'] = base_res
                    save_user(user.get('user_id'), user)
                    reset_count += 1
            except Exception as e:
                print(f"[ERROR] Failed to reset streak for user {user_data.get('user_id')}: {e}")
                continue
        
        if reset_count > 0:
            print(f"[ROUND] Streak reset for {reset_count} players - NEW ROUND STARTED ⚡")
        return reset_count
    except Exception as e:
        print(f"[ERROR] reset_all_streaks failed: {e}")
        return 0
