# ═══════════════════════════════════════════════════════════════════════════
# DATABASE MIGRATION GUIDE
# The 64 Game — Phase 1, 2 & 3 Schema
# ═══════════════════════════════════════════════════════════════════════════
#
# THE BUG: 'str' object has no attribute 'append'
# ────────────────────────────────────────────────
# Your Supabase table has columns typed as TEXT instead of JSONB.
# Supabase returns TEXT columns as Python strings, not dicts/lists.
# When code does inventory.append(...) on a string — it crashes.
#
# THE FIX: Two parts
#   1. Run the SQL migration below in Supabase SQL editor
#   2. Add safe_json() to supabase_db.py and wrap all field reads
#
# ═══════════════════════════════════════════════════════════════════════════
# PART 1: SQL TO RUN IN SUPABASE SQL EDITOR
# Go to: supabase.com → your project → SQL Editor → New Query
# Paste and run each block separately
# ═══════════════════════════════════════════════════════════════════════════

SQL_CONVERT_COLUMNS = """
-- STEP 1: Convert existing TEXT/JSON columns to JSONB
-- Run these one at a time. If a column doesn't exist yet, skip that line.

ALTER TABLE users ALTER COLUMN inventory       TYPE jsonb USING inventory::jsonb;
ALTER TABLE users ALTER COLUMN unclaimed_items TYPE jsonb USING unclaimed_items::jsonb;
ALTER TABLE users ALTER COLUMN military        TYPE jsonb USING military::jsonb;
ALTER TABLE users ALTER COLUMN buildings       TYPE jsonb USING buildings::jsonb;
ALTER TABLE users ALTER COLUMN building_queue  TYPE jsonb USING building_queue::jsonb;
ALTER TABLE users ALTER COLUMN researches      TYPE jsonb USING researches::jsonb;
ALTER TABLE users ALTER COLUMN research_queue  TYPE jsonb USING research_queue::jsonb;
ALTER TABLE users ALTER COLUMN base_resources  TYPE jsonb USING base_resources::jsonb;
ALTER TABLE users ALTER COLUMN traps           TYPE jsonb USING traps::jsonb;
ALTER TABLE users ALTER COLUMN weapons         TYPE jsonb USING weapons::jsonb;
ALTER TABLE users ALTER COLUMN buffs           TYPE jsonb USING buffs::jsonb;
ALTER TABLE users ALTER COLUMN march_queue     TYPE jsonb USING march_queue::jsonb;
ALTER TABLE users ALTER COLUMN active_suit     TYPE jsonb USING active_suit::jsonb;
ALTER TABLE users ALTER COLUMN banishments     TYPE jsonb USING banishments::jsonb;
ALTER TABLE users ALTER COLUMN visas           TYPE jsonb USING visas::jsonb;
ALTER TABLE users ALTER COLUMN eject_log       TYPE jsonb USING eject_log::jsonb;
ALTER TABLE users ALTER COLUMN teleport_history TYPE jsonb USING teleport_history::jsonb;
ALTER TABLE users ALTER COLUMN commander_location TYPE jsonb USING commander_location::jsonb;
ALTER TABLE users ALTER COLUMN visa_applications  TYPE jsonb USING visa_applications::jsonb;
ALTER TABLE users ALTER COLUMN visa_queue         TYPE jsonb USING visa_queue::jsonb;
ALTER TABLE users ALTER COLUMN current_node       TYPE jsonb USING current_node::jsonb;
"""

SQL_ADD_NEW_COLUMNS = """
-- STEP 2: Add new columns needed by Phase 1, 2 & 3
-- Safe to run even if columns already exist (uses IF NOT EXISTS pattern)

ALTER TABLE users ADD COLUMN IF NOT EXISTS inventory            jsonb    DEFAULT '{}'::jsonb;
ALTER TABLE users ADD COLUMN IF NOT EXISTS research_queue       jsonb    DEFAULT '{}'::jsonb;
ALTER TABLE users ADD COLUMN IF NOT EXISTS march_queue          jsonb    DEFAULT '[]'::jsonb;
ALTER TABLE users ADD COLUMN IF NOT EXISTS researches           jsonb    DEFAULT '{}'::jsonb;
ALTER TABLE users ADD COLUMN IF NOT EXISTS active_suit          jsonb    DEFAULT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS teleport_charges     integer  DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS teleport_daily_claimed_date text DEFAULT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS teleport_last_claim_ts      text DEFAULT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS teleport_history     jsonb    DEFAULT '[]'::jsonb;
ALTER TABLE users ADD COLUMN IF NOT EXISTS home_sector          integer  DEFAULT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS commander_location   jsonb    DEFAULT '{"sector_id": 1}'::jsonb;
ALTER TABLE users ADD COLUMN IF NOT EXISTS current_node         jsonb    DEFAULT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS base_shielded        boolean  DEFAULT false;
ALTER TABLE users ADD COLUMN IF NOT EXISTS shield_expires_at    text     DEFAULT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS energy               integer  DEFAULT 100;
ALTER TABLE users ADD COLUMN IF NOT EXISTS energy_last_regen    text     DEFAULT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS banishments          jsonb    DEFAULT '{}'::jsonb;
ALTER TABLE users ADD COLUMN IF NOT EXISTS visas                jsonb    DEFAULT '{}'::jsonb;
ALTER TABLE users ADD COLUMN IF NOT EXISTS visa_applications    jsonb    DEFAULT '{}'::jsonb;
ALTER TABLE users ADD COLUMN IF NOT EXISTS visa_queue           jsonb    DEFAULT '[]'::jsonb;
ALTER TABLE users ADD COLUMN IF NOT EXISTS eject_log            jsonb    DEFAULT '[]'::jsonb;
ALTER TABLE users ADD COLUMN IF NOT EXISTS research_power       integer  DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS alliance_points      integer  DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS pending_notification text     DEFAULT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS suit_just_expired    boolean  DEFAULT false;
ALTER TABLE users ADD COLUMN IF NOT EXISTS shield_just_expired  boolean  DEFAULT false;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_jam_at          text     DEFAULT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS skill_points_total   integer  DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS skill_points_spent   jsonb    DEFAULT '{}'::jsonb;
ALTER TABLE users ADD COLUMN IF NOT EXISTS dominance_scores     jsonb    DEFAULT '{}'::jsonb;
ALTER TABLE users ADD COLUMN IF NOT EXISTS bounty_visible       boolean  DEFAULT false;
ALTER TABLE users ADD COLUMN IF NOT EXISTS home_sector_revealed jsonb    DEFAULT '[]'::jsonb;
ALTER TABLE users ADD COLUMN IF NOT EXISTS credits              integer  DEFAULT 0;
"""

SQL_SECTOR_STATE_TABLE = """
-- STEP 3: Create sector_state table (new — stores live sector data)
-- This replaces relying on the alliances.json file for sector data

CREATE TABLE IF NOT EXISTS sector_state (
    sector_id       integer PRIMARY KEY,
    occupancy       jsonb   DEFAULT '{}'::jsonb,
    roaming         jsonb   DEFAULT '{}'::jsonb,
    sector_chat     jsonb   DEFAULT '[]'::jsonb,
    active_predators jsonb  DEFAULT '{}'::jsonb,
    active_jam      jsonb   DEFAULT NULL,
    dominance       jsonb   DEFAULT '{}'::jsonb,
    pending_ruler_alerts jsonb DEFAULT '[]'::jsonb,
    pending_predator_loot jsonb DEFAULT '{}'::jsonb,
    pending_notifications jsonb DEFAULT '{}'::jsonb,
    incoming_marches jsonb  DEFAULT '{}'::jsonb,
    last_phase_name text    DEFAULT NULL,
    last_updated    text    DEFAULT NULL
);

-- Seed all sectors with empty state
INSERT INTO sector_state (sector_id)
SELECT generate_series(1, 9)
ON CONFLICT (sector_id) DO NOTHING;

INSERT INTO sector_state (sector_id) VALUES (65)
ON CONFLICT (sector_id) DO NOTHING;

INSERT INTO sector_state (sector_id)
SELECT generate_series(10, 64)
ON CONFLICT (sector_id) DO NOTHING;
"""

SQL_BOUNTY_TABLE = """
-- STEP 4: Create bounty_board table

CREATE TABLE IF NOT EXISTS bounty_board (
    bounty_id       text    PRIMARY KEY,
    target_id       text    NOT NULL,
    target_name     text    NOT NULL,
    target_home_sector integer DEFAULT NULL,
    posted_by_id    text    NOT NULL,
    posted_by_name  text    NOT NULL,
    reward_gold     integer DEFAULT 0,
    reason          text    DEFAULT 'open bounty',
    posted_at       text    NOT NULL,
    expires_at      text    NOT NULL,
    claimed_by_id   text    DEFAULT NULL,
    claimed_at      text    DEFAULT NULL,
    status          text    DEFAULT 'active'
);
"""

SQL_FIX_NULL_INVENTORY = """
-- STEP 5: Fix existing rows that have NULL or string inventory
-- Run this AFTER the column type conversion above

UPDATE users SET inventory       = '{}'::jsonb WHERE inventory IS NULL;
UPDATE users SET unclaimed_items = '[]'::jsonb WHERE unclaimed_items IS NULL;
UPDATE users SET military        = '{}'::jsonb WHERE military IS NULL;
UPDATE users SET buildings       = '{}'::jsonb WHERE buildings IS NULL;
UPDATE users SET building_queue  = '{}'::jsonb WHERE building_queue IS NULL;
UPDATE users SET researches      = '{}'::jsonb WHERE researches IS NULL;
UPDATE users SET research_queue  = '{}'::jsonb WHERE research_queue IS NULL;
UPDATE users SET base_resources  = '{}'::jsonb WHERE base_resources IS NULL;
UPDATE users SET march_queue     = '[]'::jsonb WHERE march_queue IS NULL;
UPDATE users SET banishments     = '{}'::jsonb WHERE banishments IS NULL;
UPDATE users SET visas           = '{}'::jsonb WHERE visas IS NULL;
UPDATE users SET commander_location = '{"sector_id": 1}'::jsonb
    WHERE commander_location IS NULL;
UPDATE users SET credits = 0 WHERE credits IS NULL;
"""

# ═══════════════════════════════════════════════════════════════════════════
# PART 2: safe_json() — Add this to supabase_db.py
# This is the Python-side defence. Even if SQL migration isn't complete,
# this prevents the 'str has no attribute append' crash.
# ═══════════════════════════════════════════════════════════════════════════

SUPABASE_DB_ADDITIONS = '''
import json as _json

def safe_json(value, default=None):
    """
    Safely parse a value that might be:
      - Already a dict/list (JSONB column) → return as-is
      - A JSON string (TEXT column) → parse it
      - None → return default
      - Anything else → return default

    Use this everywhere you read JSON fields from Supabase.
    """
    if default is None:
        default = {}
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return _json.loads(value)
        except Exception:
            return default
    return default


def normalize_user(user: dict) -> dict:
    """
    Normalize all JSON fields on a user dict loaded from Supabase.
    Prevents 'str object has no attribute append/get/keys' errors.
    Call this at the top of get_user() before returning.
    """
    if not user:
        return user

    # Fields that should be dicts
    dict_fields = [
        "inventory", "military", "buildings", "building_queue",
        "researches", "research_queue", "base_resources", "traps",
        "weapons", "buffs", "banishments", "visas", "visa_applications",
        "commander_location", "current_node", "active_suit",
        "skill_points_spent", "dominance_scores", "home_sector_revealed",
    ]
    for field in dict_fields:
        user[field] = safe_json(user.get(field), default={})

    # Fields that should be lists
    list_fields = [
        "unclaimed_items", "march_queue", "eject_log",
        "teleport_history", "visa_queue",
    ]
    for field in list_fields:
        user[field] = safe_json(user.get(field), default=[])

    # Fields with specific defaults
    if not user.get("commander_location"):
        user["commander_location"] = {"sector_id": 1}
    if not isinstance(user.get("base_resources"), dict):
        user["base_resources"] = {"resources": {}, "food": 0, "current_streak": 0}
    if not isinstance(user.get("base_resources", {}).get("resources"), dict):
        user["base_resources"]["resources"] = {}

    # Ensure credits exists
    if user.get("credits") is None:
        user["credits"] = 0

    return user
'''

# ═══════════════════════════════════════════════════════════════════════════
# PART 3: Updated get_user() for supabase_db.py
# Replace your existing get_user with this exact version
# ═══════════════════════════════════════════════════════════════════════════

UPDATED_GET_USER = '''
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
            return user
        return None
    except Exception as e:
        print(f"[DB ERROR] get_user: {e}")
        return None
'''

# ═══════════════════════════════════════════════════════════════════════════
# PART 4: Fix the grant_teleports / grant_shields functions
# The crash is in whatever function loops all users and appends to inventory.
# Find that function in your main.py or supabase_db.py and wrap the
# inventory read with safe_json().
# ═══════════════════════════════════════════════════════════════════════════

GRANT_TELEPORTS_FIX = '''
# Find your grant_daily_teleports or similar function.
# It probably looks something like this (BROKEN):

async def grant_daily_teleports():
    users = supabase.table(DB_TABLE).select("*").execute().data
    for user in users:
        try:
            inv = user.get("inventory", [])   # BUG: returns string "[]"
            inv.append({"type": "teleport", "qty": 3})  # CRASHES here
        except Exception as e:
            print(f"[WARN] Could not grant teleports to {user['user_id']}: {e}")

# FIXED VERSION — replace it with this:

async def grant_daily_teleports():
    from supabase_db import safe_json, save_user  # make sure safe_json is defined
    users = supabase.table(DB_TABLE).select("user_id, inventory, teleport_charges,
        teleport_daily_claimed_date").execute().data
    granted = 0
    today = datetime.utcnow().strftime("%Y-%m-%d")

    for user in users:
        try:
            uid = user["user_id"]
            # Skip if already claimed today
            if user.get("teleport_daily_claimed_date") == today:
                continue
            # Add 3 charges directly to the integer column
            current = user.get("teleport_charges") or 0
            supabase.table(DB_TABLE).update({
                "teleport_charges": current + 3,
                "teleport_daily_claimed_date": today,
            }).eq("user_id", uid).execute()
            granted += 1
        except Exception as e:
            print(f"[WARN] Could not grant teleports to {user['user_id']}: {e}")

    print(f"[TELEPORTS] Granted 3 free teleports to {granted} players")

# Do the same for grant_shields — use the shield_expires_at TEXT column
# instead of appending to inventory:

async def grant_daily_shields():
    users = supabase.table(DB_TABLE).select("user_id, base_shielded,
        shield_expires_at").execute().data
    granted = 0
    shield_duration_hours = 8

    for user in users:
        try:
            uid = user["user_id"]
            already_shielded = user.get("base_shielded", False)
            if already_shielded:
                continue
            expires = (datetime.utcnow() +
                timedelta(hours=shield_duration_hours)).isoformat()
            supabase.table(DB_TABLE).update({
                "base_shielded": True,
                "shield_expires_at": expires,
            }).eq("user_id", uid).execute()
            granted += 1
        except Exception as e:
            print(f"[WARN] Could not grant shields to {user['user_id']}: {e}")

    print(f"[SHIELDS] Granted shields to {granted} players")
'''

if __name__ == "__main__":
    print("DATABASE MIGRATION GUIDE")
    print("=" * 50)
    print("Run these SQL blocks in Supabase SQL Editor IN ORDER:")
    print()
    print("1. SQL_CONVERT_COLUMNS   — convert TEXT → JSONB")
    print("2. SQL_ADD_NEW_COLUMNS   — add missing columns")
    print("3. SQL_SECTOR_STATE_TABLE — create sector_state table")
    print("4. SQL_BOUNTY_TABLE      — create bounty_board table")
    print("5. SQL_FIX_NULL_INVENTORY — fix NULL rows")
    print()
    print("Then update supabase_db.py:")
    print("  - Add safe_json() and normalize_user() functions")
    print("  - Update get_user() to call normalize_user()")
    print("  - Fix grant_daily_teleports() and grant_daily_shields()")
    print()
    print("The crash: inventory stored as string '[]' not list []")
    print("The fix:   safe_json() handles both transparently")
