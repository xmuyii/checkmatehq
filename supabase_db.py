"""
Supabase database backend for The 64 game.
Replaces JSON persistence with persistent Supabase tables.
"""

import os
import json
from datetime import datetime, timedelta
from supabase import create_client, Client

# ── Environment Configuration ──────────────────────────────────────────────
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://basniiolppmtpzishhtn.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJhc25paW9scHBtdHB6aXNoaHRuIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NTQ3NjMwOCwiZXhwIjoyMDkxMDUyMzA4fQ.qrj1BO5dNilRDvgKtvTdwIWjBhFTRyGzuHPD271Xcac')
SECTORS_FILE = os.environ.get("SECTORS_FILE", "sectors.txt")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL.rstrip('/'), SUPABASE_KEY)

# ── Verify Supabase Connection ────────────────────────────────────────────
def verify_supabase_connection() -> bool:
    """Test that Supabase connection is working."""
    try:
        # Try a simple query to verify connection
        response = supabase.table('players').select('count', count='exact').limit(1).execute()
        print(f"   ✅ Supabase connection verified!")
        print(f"   📊 Players table is accessible")
        return True
    except Exception as e:
        print(f"   ❌ Supabase connection failed: {e}")
        print(f"   🔍 Troubleshooting:")
        print(f"      1. Check SUPABASE_URL and SUPABASE_KEY are correct")
        print(f"      2. Verify Supabase project is active")
        print(f"      3. Run SUPABASE_SETUP.sql to create tables")
        raise

# Test connection on import
verify_supabase_connection()


# ── Helper Functions ──────────────────────────────────────────────────────

def get_current_week_start() -> datetime:
    today = datetime.now()
    # weeks run Sunday to Saturday; get Sunday of current week
    # weekday() returns Monday=0, Tuesday=1, ..., Sunday=6
    days_since_sunday = (today.weekday() + 1) % 7
    week_sunday = today - timedelta(days=days_since_sunday)
    # Set to 11:59 PM on Sunday (end of week reset time)
    return week_sunday.replace(hour=23, minute=59, second=0, microsecond=0)


# ── User Management ─────────────────────────────────────────────────────

def register_user(user_id, username):
    """Create a new player account. Doesn't overwrite existing."""
    uid = str(user_id)
    
    # Check if already exists
    response = supabase.table('players').select('*').eq('user_id', uid).execute()
    if response.data:
        # User exists - just update username if different
        existing = response.data[0]
        if existing.get('username') != username:
            supabase.table('players').update({'username': username}).eq('user_id', uid).execute()
        return
    
    # Create new player
    new_player = {
        'user_id': uid,
        'username': username,
        'all_time_points': 0,
        'weekly_points': 0,
        'week_start': get_current_week_start().isoformat(),
        'total_words': 0,
        'silver': 0,
        'xp': 0,
        'level': 1,
        'backpack_slots': 5,
        'backpack_image': 'normal_backpack',
        'inventory': json.dumps([]),
        'unclaimed_items': json.dumps([]),
        'sector': None,
        'completed_tutorial': False,
        'last_level': 1,
        'created_at': datetime.now().isoformat(),
    }
    supabase.table('players').insert(new_player).execute()


def get_user(user_id):
    """Fetch player data."""
    uid = str(user_id)
    response = supabase.table('players').select('*').eq('user_id', uid).execute()
    if not response.data:
        return None
    
    user = response.data[0]
    # Convert JSON fields
    try:
        user['inventory'] = json.loads(user.get('inventory', '[]')) if isinstance(user.get('inventory'), str) else user.get('inventory', [])
        user['unclaimed_items'] = json.loads(user.get('unclaimed_items', '[]')) if isinstance(user.get('unclaimed_items'), str) else user.get('unclaimed_items', [])
    except:
        user['inventory'] = []
        user['unclaimed_items'] = []
    
    return user


def save_user(user_id, data):
    """Save player data."""
    uid = str(user_id)
    
    # Convert complex fields to JSON strings
    data_copy = data.copy()
    if 'inventory' in data_copy and isinstance(data_copy['inventory'], (list, dict)):
        data_copy['inventory'] = json.dumps(data_copy['inventory'])
    if 'unclaimed_items' in data_copy and isinstance(data_copy['unclaimed_items'], (list, dict)):
        data_copy['unclaimed_items'] = json.dumps(data_copy['unclaimed_items'])
    
    # Remove the id field if present
    data_copy.pop('id', None)
    
    supabase.table('players').update(data_copy).eq('user_id', uid).execute()


# ── Points & Scoring ──────────────────────────────────────────────────────

def add_points(user_id, points, username):
    """Add points and track weekly reset."""
    uid = str(user_id)
    user = get_user(uid)
    
    if not user:
        register_user(user_id, username)
        user = get_user(uid)
    
    current_week = get_current_week_start().isoformat()
    
    # Reset weekly points if needed
    if user.get('week_start') != current_week:
        user['weekly_points'] = 0
        user['week_start'] = current_week
    
    # Add points
    user['all_time_points'] = user.get('all_time_points', 0) + points
    user['weekly_points'] = user.get('weekly_points', 0) + points
    user['total_words'] = user.get('total_words', 0) + 1
    
    save_user(uid, user)


def add_xp(user_id, amount) -> bool:
    """Add XP and return True if level up."""
    uid = str(user_id)
    user = get_user(uid)
    if not user:
        return False
    
    user['xp'] = user.get('xp', 0) + amount
    old_level = user.get('level', 1)
    user['level'] = 1 + (user['xp'] // 100)
    
    save_user(uid, user)
    return user['level'] > old_level


def add_silver(user_id, amount, username):
    """Add silver to player."""
    uid = str(user_id)
    user = get_user(uid)
    if not user:
        register_user(user_id, username)
        user = get_user(uid)
    
    user['silver'] = user.get('silver', 0) + amount
    save_user(uid, user)


def set_sector(user_id, sector_id):
    """Set player's current sector."""
    uid = str(user_id)
    user = get_user(uid)
    if not user:
        return
    
    user['sector'] = sector_id
    save_user(uid, user)


# ── Leaderboards ──────────────────────────────────────────────────────────

def get_weekly_leaderboard(limit: int = 10) -> list:
    """Get top weekly scorers."""
    response = supabase.table('players')\
        .select('user_id, username, weekly_points')\
        .order('weekly_points', desc=True)\
        .limit(limit)\
        .execute()
    
    return [
        {'id': p['user_id'], 'username': p['username'], 'points': p['weekly_points']}
        for p in response.data
    ] if response.data else []


def get_alltime_leaderboard(limit: int = 10) -> list:
    """Get all-time top scorers."""
    response = supabase.table('players')\
        .select('user_id, username, all_time_points, total_words')\
        .order('all_time_points', desc=True)\
        .limit(limit)\
        .execute()
    
    return [
        {'id': p['user_id'], 'username': p['username'], 'points': p['all_time_points'], 'words': p['total_words']}
        for p in response.data
    ] if response.data else []


# ── Inventory Management ──────────────────────────────────────────────────

def get_inventory(user_id) -> list:
    """Get player's inventory items."""
    uid = str(user_id)
    user = get_user(uid)
    if not user:
        return []
    
    return user.get('inventory', [])


def add_inventory_item(user_id, item_type, amount=1, xp_reward=0):
    """Add item to player inventory."""
    uid = str(user_id)
    user = get_user(uid)
    if not user:
        return
    
    inventory = user.get('inventory', [])
    
    # Find existing stack
    existing = None
    for item in inventory:
        if item.get('type') == item_type:
            existing = item
            break
    
    if existing:
        existing['amount'] = existing.get('amount', 0) + amount
    else:
        inventory.append({
            'type': item_type,
            'amount': amount,
            'xp_reward': xp_reward,
            'acquired': datetime.now().isoformat()
        })
    
    user['inventory'] = inventory
    save_user(uid, user)


def remove_inventory_item(user_id, item_type, amount=1):
    """Remove item from inventory."""
    uid = str(user_id)
    user = get_user(uid)
    if not user:
        return
    
    inventory = user.get('inventory', [])
    for item in inventory:
        if item.get('type') == item_type:
            item['amount'] = max(0, item.get('amount', 0) - amount)
            break
    
    user['inventory'] = [i for i in inventory if i.get('amount', 0) > 0]
    save_user(uid, user)


def get_unclaimed_items(user_id) -> list:
    """Get player's unclaimed reward items."""
    uid = str(user_id)
    user = get_user(uid)
    if not user:
        return []
    
    return user.get('unclaimed_items', [])


def add_unclaimed_item(user_id, item_type, amount=1, xp_reward=0):
    """Add unclaimed reward item."""
    uid = str(user_id)
    user = get_user(uid)
    if not user:
        return
    
    unclaimed = user.get('unclaimed_items', [])
    unclaimed.append({
        'type': item_type,
        'amount': amount,
        'xp_reward': xp_reward,
        'claimed': False,
        'created_at': datetime.now().isoformat()
    })
    
    user['unclaimed_items'] = unclaimed
    save_user(uid, user)


def claim_item(user_id, index: int):
    """Claim an unclaimed reward item and move to inventory."""
    uid = str(user_id)
    user = get_user(uid)
    if not user:
        return False
    
    unclaimed = user.get('unclaimed_items', [])
    if not (0 <= index < len(unclaimed)):
        return False
    
    item = unclaimed[index]
    if item.get('claimed'):
        return False
    
    # Step 1: Move item to inventory
    add_inventory_item(uid, item['type'], item['amount'], item.get('xp_reward', 0))
    
    # Step 2: Fetch fresh user data (after add_inventory_item has saved)
    user = get_user(uid)
    
    # Step 3: Remove from unclaimed list
    unclaimed = user.get('unclaimed_items', [])
    if 0 <= index < len(unclaimed):
        unclaimed.pop(index)
        user['unclaimed_items'] = unclaimed
        save_user(uid, user)
        return True
    
    return False


def remove_unclaimed_item(user_id, index: int):
    """Remove unclaimed item by index."""
    uid = str(user_id)
    user = get_user(uid)
    if not user:
        return
    
    unclaimed = user.get('unclaimed_items', [])
    if 0 <= index < len(unclaimed):
        unclaimed.pop(index)
        user['unclaimed_items'] = unclaimed
        save_user(uid, user)


# ── Sector Management ──────────────────────────────────────────────────────

def load_sectors() -> dict:
    """Load sectors from file."""
    sectors = {}
    if not os.path.exists(SECTORS_FILE):
        return sectors
    
    try:
        with open(SECTORS_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return sectors
    
    for line in lines[1:]:
        line = line.strip()
        if not line or line.startswith("SectorID"):
            continue
        parts = line.split("\t")
        if len(parts) >= 4:
            try:
                sector_id = int(parts[0])
                sectors[sector_id] = {
                    "name": parts[3].strip(),
                    "environment": parts[1].strip() if len(parts) > 1 else "",
                    "energy": parts[2].strip() if len(parts) > 2 else "",
                    "perks": parts[4].strip() if len(parts) > 4 else "",
                }
            except Exception:
                pass
    return sectors


def get_sector_display(sector_id, sectors=None) -> str:
    """Get sector display name."""
    if sector_id is None:
        return "Not Assigned"
    if sectors is None:
        sectors = load_sectors()
    try:
        sid = int(sector_id)
    except (TypeError, ValueError):
        return f"Sector {sector_id}"
    info = sectors.get(sid)
    if info:
        return f"#{sid} {info['name']}"
    return f"Sector {sid}"


# ── Level Management ──────────────────────────────────────────────────────

def calculate_level(xp: int) -> int:
    """Calculate level from XP."""
    return 1 + (xp // 100)


def check_level_up(user_id) -> tuple[int, int]:
    """Check for level up. Returns (old_level, new_level) or (None, None) if no level up."""
    uid = str(user_id)
    user = get_user(uid)
    if not user:
        return None, None
    
    old_level = user.get('last_level', 1)
    new_level = user.get('level', 1)
    
    if new_level > old_level:
        user['last_level'] = new_level
        save_user(uid, user)
        return old_level, new_level
    return None, None


# ── Item Rewards ──────────────────────────────────────────────────────────

def award_powerful_locked_item(user_id):
    """Award a rare milestone item."""
    items = [
        ("legendary_artifact", "⚔️ LEGENDARY ARTIFACT"),
        ("mythic_shard", "🌟 MYTHIC SHARD"),
        ("dimensional_rift", "🌀 DIMENSIONAL RIFT"),
        ("cosmic_crown", "👑 COSMIC CROWN"),
    ]
    import random
    item_type, display = random.choice(items)
    add_unclaimed_item(user_id, item_type, 1)
    return display


def get_profile(user_id) -> dict:
    """Get player profile display data."""
    uid = str(user_id)
    user = get_user(uid)
    if not user:
        return {}
    
    inventory = user.get('inventory', [])
    unclaimed = user.get('unclaimed_items', [])
    sectors = load_sectors()
    sector_display = get_sector_display(user.get('sector'), sectors)
    
    # XP calculations
    total_xp = user.get('xp', 0)
    current_level = user.get('level', 1)
    xp_for_next_level = 100
    xp_progress = total_xp % 100
    
    return {
        "username": user.get('username', 'Unknown'),
        "level": current_level,
        "xp": total_xp,
        "xp_progress": xp_progress,
        "xp_needed": xp_for_next_level,
        "silver": user.get('silver', 0),
        "all_time_points": user.get('all_time_points', 0),
        "weekly_points": user.get('weekly_points', 0),
        "total_words": user.get('total_words', 0),
        "sector": sector_display,
        "backpack_slots": user.get('backpack_slots', 5),
        "inventory_count": len(inventory),
        "unclaimed_count": len(unclaimed),
        "crate_count": sum(1 for i in inventory if "crate" in i.get("type", "").lower()),
        "shield_count": sum(1 for i in inventory if i.get("type", "").lower() == "shield"),
    }


def upgrade_backpack(user_id, new_slots: int):
    """Upgrade player backpack."""
    uid = str(user_id)
    user = get_user(uid)
    if not user:
        return
    
    user['backpack_slots'] = new_slots
    user['backpack_image'] = 'premium_backpack' if new_slots > 5 else 'normal_backpack'
    save_user(uid, user)


def use_xp(user_id, amount) -> bool:
    """Spend XP. Returns True if successful."""
    uid = str(user_id)
    user = get_user(uid)
    if not user or user.get('xp', 0) < amount:
        return False
    
    user['xp'] = user.get('xp', 0) - amount
    save_user(uid, user)
    return True


def use_silver(user_id, amount) -> bool:
    """Spend silver. Returns True if successful."""
    uid = str(user_id)
    user = get_user(uid)
    if not user or user.get('silver', 0) < amount:
        return False
    
    user['silver'] = user.get('silver', 0) - amount
    save_user(uid, user)
    return True
