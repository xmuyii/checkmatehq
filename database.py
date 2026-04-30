import json
import os
import random
from datetime import datetime, timedelta

# ── Storage paths ──────────────────────────────────────────────────────────
# On Railway set DB_FILE=/data/players.json and mount a Volume at /data
# so the file survives redeploys.  Falls back to local file for local dev.
DB_FILE      = os.environ.get("DB_FILE", "players.json")
SECTORS_FILE = os.environ.get("SECTORS_FILE", "sectors.txt")


# ── Low-level I/O ──────────────────────────────────────────────────────────

def load_data() -> dict:
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}

def save_data(data: dict):
    # Write to a temp file then rename – atomic on most systems
    tmp = DB_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    os.replace(tmp, DB_FILE)

def save_user(user_id, data):
    all_data = load_data()
    all_data[str(user_id)] = data
    save_data(all_data)

def get_user(user_id):
    all_data = load_data()
    return all_data.get(str(user_id))


# ── Sectors ────────────────────────────────────────────────────────────────

def load_sectors() -> dict:
    """Return {sector_id: {name, environment, energy, perks}}"""
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
                    "name":        parts[3].strip(),
                    "environment": parts[1].strip() if len(parts) > 1 else "",
                    "energy":      parts[2].strip() if len(parts) > 2 else "",
                    "perks":       parts[4].strip() if len(parts) > 4 else "",
                }
            except Exception:
                pass
    return sectors

def get_sector_display(sector_id, sectors=None) -> str:
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


# ── User registration ──────────────────────────────────────────────────────

def register_user(user_id, username):
    """Create a fresh account.  Does NOT overwrite an existing one. Returns True on success."""
    try:
        all_data = load_data()
        uid = str(user_id)
        if uid in all_data:
            # Already exists – only update the username if it changed
            if all_data[uid].get("username") != username:
                all_data[uid]["username"] = username
                save_data(all_data)
            return True  # ← already registered

        all_data[uid] = {
            "username":          username,
            "all_time_points":   0,
            "weekly_points":     0,
            "week_start":        get_current_week_start().isoformat(),
            "total_words":       0,
            "silver":            0,
            "xp":                0,
            "level":             1,
            "backpack_slots":    5,
            "backpack_image":    "normal_backpack",
            "inventory":         [],
            "unclaimed_items":   [],
            "sector":            None,
            "registered":        True,
            "completed_tutorial": False,
            "last_level":        1,
        }
        save_data(all_data)
        return True  # ← registration succeeded
    except Exception as e:
        print(f"[REGISTER ERROR] Failed to register {user_id}: {e}")
        return False  # ← registration failed


def get_current_week_start() -> datetime:
    today = datetime.now()
    # weeks run Sunday to Saturday; get Sunday of current week
    # weekday() returns Monday=0, Tuesday=1, ..., Sunday=6
    days_since_sunday = (today.weekday() + 1) % 7
    week_sunday = today - timedelta(days=days_since_sunday)
    # Set to 11:59 PM on Sunday (end of week reset time)
    return week_sunday.replace(hour=23, minute=59, second=0, microsecond=0)


# ── Points / XP / Silver ──────────────────────────────────────────────────

def add_points(user_id, points, username):
    all_data = load_data()
    uid = str(user_id)
    if uid not in all_data:
        register_user(user_id, username)
        all_data = load_data()

    user = all_data[uid]
    current_week = get_current_week_start().isoformat()
    if user.get("week_start") != current_week:
        user["weekly_points"] = 0
        user["week_start"]    = current_week

    user["all_time_points"] = user.get("all_time_points", 0) + points
    user["weekly_points"]   = user.get("weekly_points",   0) + points
    user["total_words"]     = user.get("total_words",     0) + 1
    save_data(all_data)

def add_xp(user_id, amount) -> bool:
    user = get_user(user_id)
    if not user:
        return False
    user["xp"] = user.get("xp", 0) + amount
    save_user(user_id, user)
    return True

def use_xp(user_id, amount) -> bool:
    user = get_user(user_id)
    if not user:
        return False
    if user.get("xp", 0) < amount:
        return False
    user["xp"] -= amount
    save_user(user_id, user)
    return True

def add_silver(user_id, amount, username=""):
    user = get_user(user_id)
    if not user:
        register_user(user_id, username)
        user = get_user(user_id)
    user["silver"] = user.get("silver", 0) + amount
    save_user(user_id, user)

def use_silver(user_id, amount) -> bool:
    user = get_user(user_id)
    if not user:
        return False
    if user.get("silver", 0) < amount:
        return False
    user["silver"] -= amount
    save_user(user_id, user)
    return True


# ── Sector ────────────────────────────────────────────────────────────────

def set_sector(user_id, sector):
    user = get_user(user_id)
    if user:
        user["sector"] = sector
        save_user(user_id, user)

def update_username(user_id, new_username) -> bool:
    user = get_user(user_id)
    if user:
        user["username"] = new_username
        save_user(user_id, user)
        return True
    return False


# ── Backpack / Inventory ──────────────────────────────────────────────────

def upgrade_backpack(user_id) -> bool:
    user = get_user(user_id)
    if user and user.get("silver", 0) >= 900:
        user["silver"]         -= 900
        user["backpack_slots"]  = 20
        user["backpack_image"]  = "queens_satchel"
        save_user(user_id, user)
        return True
    return False

def _next_id(collection: list) -> int:
    return (max((it.get("id", 0) for it in collection), default=-1) + 1)

def add_inventory_item(user_id, item_type, xp_reward=0, expires_at=None) -> bool:
    user = get_user(user_id)
    if not user:
        return False
    inventory = user.get("inventory", [])
    if len(inventory) >= user.get("backpack_slots", 5):
        return False
    inventory.append({
        "id":         _next_id(inventory),
        "type":       item_type,
        "xp_reward":  xp_reward,
        "expires_at": expires_at,
        "created_at": datetime.now().isoformat(),
    })
    user["inventory"] = inventory
    save_user(user_id, user)
    return True

def remove_inventory_item(user_id, item_id) -> bool:
    user = get_user(user_id)
    if not user:
        return False
    user["inventory"] = [it for it in user.get("inventory", []) if it.get("id") != item_id]
    save_user(user_id, user)
    return True

def get_inventory(user_id) -> list:
    user = get_user(user_id)
    return user.get("inventory", []) if user else []


# ── Unclaimed items ───────────────────────────────────────────────────────

def add_unclaimed_item(user_id, item_type, amount=1,
                        multiplier_value=None, xp_reward=None) -> bool:
    user = get_user(user_id)
    if not user:
        return False
    unclaimed = user.get("unclaimed_items", [])
    if not isinstance(unclaimed, list):
        unclaimed = []
    unclaimed.append({
        "id":               _next_id(unclaimed),
        "type":             item_type,
        "amount":           amount,
        "xp_reward":        xp_reward if xp_reward is not None else amount,
        "multiplier_value": multiplier_value,
        "created_at":       datetime.now().isoformat(),
    })
    user["unclaimed_items"] = unclaimed
    save_user(user_id, user)
    return True

def get_unclaimed_items(user_id) -> list:
    user = get_user(user_id)
    return user.get("unclaimed_items", []) if user else []

def remove_unclaimed_item(user_id, item_id) -> bool:
    user = get_user(user_id)
    if not user:
        return False
    user["unclaimed_items"] = [
        it for it in user.get("unclaimed_items", []) if it.get("id") != item_id
    ]
    save_user(user_id, user)
    return True

def claim_item(user_id, item_id):
    """Move an unclaimed item into the inventory.
    Returns (True, 'Item claimed successfully') or (False, reason).
    """
    user = get_user(user_id)
    if not user:
        return False, "Not registered"

    unclaimed = user.get("unclaimed_items", [])
    item = None
    for i, it in enumerate(unclaimed):
        if it.get("id") == item_id:
            item = it
            unclaimed.pop(i)
            break

    if not item:
        return False, "Item not found"

    inventory = user.get("inventory", [])
    if len(inventory) >= user.get("backpack_slots", 5):
        unclaimed.append(item)           # put back
        user["unclaimed_items"] = unclaimed
        save_user(user_id, user)
        return False, "Inventory full — use or discard an item first"

    inventory.append({
        "id":               _next_id(inventory),
        "type":             item.get("type"),
        "xp_reward":        item.get("xp_reward", item.get("amount", 0)),
        "multiplier_value": item.get("multiplier_value"),
        "created_at":       item.get("created_at"),
    })
    user["inventory"]      = inventory
    user["unclaimed_items"] = unclaimed
    save_user(user_id, user)
    return True, "Item claimed successfully"


# ── Profile / Levels ──────────────────────────────────────────────────────

def calculate_level(xp: int) -> int:
    return (xp // 100) + 1

def get_xp_for_level(level: int) -> int:
    return (level - 1) * 100

def check_level_up(user_id):
    """Return (old_level, new_level) if leveled up, else (None, None)."""
    user = get_user(user_id)
    if not user:
        return None, None
    old_level = user.get("last_level", 1)
    new_level = calculate_level(user.get("xp", 0))
    if new_level > old_level:
        user["last_level"] = new_level
        user["level"]      = new_level
        save_user(user_id, user)
        return old_level, new_level
    return None, None

def get_profile(user_id) -> dict | None:
    user = get_user(user_id)
    if not user:
        return None
    inventory = user.get("inventory", [])
    unclaimed = user.get("unclaimed_items", [])
    xp        = user.get("xp", 0)
    level     = calculate_level(xp)
    xp_base   = get_xp_for_level(level)
    xp_next   = get_xp_for_level(level + 1)
    return {
        "username":        user.get("username", "Unknown"),
        "xp":              xp,
        "level":           level,
        "xp_progress":     xp - xp_base,
        "xp_needed":       xp_next - xp_base,
        "silver":          user.get("silver", 0),
        "sector":          user.get("sector"),
        "sector_display":  get_sector_display(user.get("sector")),
        "weekly_points":   user.get("weekly_points", 0),
        "all_time_points": user.get("all_time_points", 0),
        "backpack_slots":  user.get("backpack_slots", 5),
        "inventory_count": len(inventory),
        "unclaimed_count": len(unclaimed),
        "crate_count":     sum(1 for i in inventory if "crate" in i.get("type","").lower()),
        "shield_count":    sum(1 for i in inventory if i.get("type","").lower() == "shield"),
    }


# ── Leaderboards ──────────────────────────────────────────────────────────

def get_weekly_leaderboard() -> list:
    all_data = load_data()
    players = [
        {"id": uid, "username": d.get("username","Unknown"), "points": d.get("weekly_points",0)}
        for uid, d in all_data.items()
    ]
    return sorted(players, key=lambda x: x["points"], reverse=True)[:10]

def get_alltime_leaderboard() -> list:
    all_data = load_data()
    players = [
        {"id": uid, "username": d.get("username","Unknown"),
         "points": d.get("all_time_points",0), "words": d.get("total_words",0)}
        for uid, d in all_data.items()
    ]
    return sorted(players, key=lambda x: x["points"], reverse=True)[:10]


# ── Powerful locked items ─────────────────────────────────────────────────

def award_powerful_locked_item(user_id):
    """Award a rare milestone item.  Returns (display_name, description)."""
    items = [
        ("legendary_artifact", "⚔️ LEGENDARY ARTIFACT",
         "An ancient weapon of unimaginable power. You can feel its raw energy."),
        ("mythical_crown",     "👑 MYTHICAL CROWN",
         "The crown of a forgotten god. Its beauty is almost unbearable."),
        ("void_stone",         "🌑 VOID STONE",
         "A stone from beyond the stars. It defies your understanding."),
        ("eternal_flame",      "🔥 ETERNAL FLAME",
         "A flame that never dies. Holds secrets of the universe."),
        ("celestial_key",      "🗝️ CELESTIAL KEY",
         "A key to dimensions you cannot yet comprehend."),
    ]
    item_type, display_name, desc = random.choice(items)
    add_unclaimed_item(user_id, f"locked_{item_type}", 1)
    return display_name, desc

# ── Resources & food streak ───────────────────────────────────────────────

# Resource awarded per word length:
# 3 letters = +1 wood
# 4 letters = +1 bronze  
# 5 letters = +1 iron
# 6 letters = +1 silver (currency)
# 7+ letters = +1 relic

RESOURCE_BY_LENGTH = {3: "wood", 4: "bronze", 5: "iron", 6: "silver_res", 7: "relics"}

def add_resources_from_word_length(user_id, word_len: int, username: str = "") -> dict:
    user = get_user(user_id)
    if not user:
        return {}
    res_key = RESOURCE_BY_LENGTH.get(min(word_len, 7), "relics")
    resources = user.get("resources", {"wood": 0, "bronze": 0, "iron": 0, "silver_res": 0, "relics": 0, "food": 0})
    resources[res_key] = resources.get(res_key, 0) + 1
    user["resources"] = resources
    save_user(user_id, user)
    return {res_key: 1}

def update_streak_and_award_food(user_id, correct: bool, username: str = "") -> dict:
    user = get_user(user_id)
    if not user:
        return {"food_awarded": 0, "streak": 0}
    streak = user.get("word_streak", 0)
    if correct:
        streak += 1
    else:
        streak = 0
    food_awarded = 0
    # Food starts after 3 correct words in a row; more words = more food
    if correct and streak >= 3:
        food_awarded = streak - 2   # streak 3 = +1, streak 4 = +2, etc.
        resources = user.get("resources", {})
        resources["food"] = resources.get("food", 0) + food_awarded
        user["resources"] = resources
    user["word_streak"] = streak
    save_user(user_id, user)
    return {"food_awarded": food_awarded, "streak": streak}