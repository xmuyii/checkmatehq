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


# ── Week helper ────────────────────────────────────────────────────────────

def _current_week_key() -> str:
    """ISO date string of the Sunday that starts this week (Sun–Sat)."""
    today = datetime.utcnow()
    days_since_sunday = (today.weekday() + 1) % 7   # Monday=0 … Sunday=6
    sunday = today - timedelta(days=days_since_sunday)
    return sunday.date().isoformat()   # e.g. "2026-04-06"


def _next_id(lst: list) -> int:
    """Generate a unique integer ID that is 1 higher than any existing id."""
    if not lst:
        return 0
    return max(it.get('id', 0) for it in lst) + 1


# ── Raw DB helpers ─────────────────────────────────────────────────────────

def _row_to_user(row: dict) -> dict:
    """Normalise a raw Supabase row into the in-memory user dict."""
    u = dict(row)
    # Integers
    for k, default in [('weekly_points', 0), ('all_time_points', 0),
                        ('total_words', 0), ('xp', 0), ('silver', 0),
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
    return u


def get_user(user_id) -> dict | None:
    r = supabase.table(DB_TABLE).select('*').eq('user_id', str(user_id)).execute()
    return _row_to_user(r.data[0]) if r.data else None


def save_user(user_id, data: dict):
    d = dict(data)
    d.pop('id', None)
    for k in ('inventory', 'unclaimed_items'):
        if isinstance(d.get(k), (list, dict)):
            d[k] = json.dumps(d[k])
    supabase.table(DB_TABLE).update(d).eq('user_id', str(user_id)).execute()


def register_user(user_id, username: str):
    uid = str(user_id)
    r = supabase.table(DB_TABLE).select('user_id, username').eq('user_id', uid).execute()
    if r.data:
        if r.data[0].get('username') != username:
            supabase.table(DB_TABLE).update({'username': username}).eq('user_id', uid).execute()
        return
    supabase.table(DB_TABLE).insert({
        'user_id': uid,
        'username': username,
        'all_time_points': 0,
        'weekly_points': 0,
        'week_start': _current_week_key(),
        'total_words': 0,
        'silver': 0,
        'xp': 0,
        'level': 1,
        'last_level': 1,
        'backpack_slots': 5,
        'backpack_image': 'normal_backpack',
        'inventory': json.dumps([]),
        'unclaimed_items': json.dumps([]),
        'sector': None,
        'completed_tutorial': False,
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


def add_silver(user_id, amount: int, username: str = ''):
    user = get_user(str(user_id))
    if not user:
        register_user(user_id, username)
        user = get_user(str(user_id))
    user['silver'] = user.get('silver', 0) + amount
    save_user(str(user_id), user)


def use_silver(user_id, amount: int) -> bool:
    user = get_user(str(user_id))
    if not user or user.get('silver', 0) < amount:
        return False
    user['silver'] -= amount
    save_user(str(user_id), user)
    return True


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
            .select('user_id, username, all_time_points, total_words') \
            .order('all_time_points', desc=True) \
            .limit(limit) \
            .execute()
        return [
            {'id': p['user_id'], 'username': p.get('username', 'Unknown'),
             'points': int(p.get('all_time_points') or 0), 'words': int(p.get('total_words') or 0)}
            for p in (r.data or [])
        ]
    except Exception as e:
        print(f"[ERROR] get_alltime_leaderboard: {e}")
        return []


# ── Inventory ──────────────────────────────────────────────────────────────

def get_inventory(user_id) -> list:
    user = get_user(str(user_id))
    return user.get('inventory', []) if user else []


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
    """Remove by unique item['id'], not list index."""
    user = get_user(str(user_id))
    if not user:
        return False
    user['inventory'] = [it for it in user.get('inventory', []) if it.get('id') != item_id]
    save_user(str(user_id), user)
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
    """Return True if user has an active (non-expired) shield."""
    exp = user.get('shield_expires')
    if not exp:
        return False
    try:
        return datetime.utcnow() < datetime.fromisoformat(exp)
    except Exception:
        return False


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


def get_unclaimed_items(user_id) -> list:
    user = get_user(str(user_id))
    return user.get('unclaimed_items', []) if user else []


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
    return {
        'username':        user.get('username', 'Unknown'),
        'level':           level,
        'xp':              xp,
        'xp_progress':     xp_prog,
        'xp_needed':       100,
        'silver':          user.get('silver', 0),
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
