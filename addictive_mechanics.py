"""
addictive_mechanics.py — Features that keep players hooked

PSYCHOLOGICAL TRIGGERS:
1. Daily Streaks (loss aversion - don't break it!)
2. Time-Limited Offers (FOMO - limited window)
3. Escalating Rewards (variable ratio schedule)
4. Social Proof (leaderboards, competition)
5. Rare Drops (dopamine hit from randomness)
6. Achievement Notifications (accomplishment)
7. Urgent Timers (anxiety + relief cycle)
"""

from datetime import datetime, timedelta
from supabase_db import get_user, save_user, get_weekly_leaderboard
import random


# ═══════════════════════════════════════════════════════════════════════════
#  DAILY LOGIN STREAKS - Loss Aversion
# ═══════════════════════════════════════════════════════════════════════════

def get_login_streak(user_id: str) -> dict:
    """Get player's login streak info."""
    user = get_user(user_id)
    if not user:
        return {"streak": 0, "last_login": None, "broken": False}
    
    streak = user.get("login_streak", 0)
    # Read last_login from buffs JSONB instead
    buffs = user.get("buffs", {})
    last_login = buffs.get("last_login")
    
    # Check if streak is broken (missed more than 24 hours)
    if last_login:
        try:
            last_time = datetime.fromisoformat(last_login)
            hours_since = (datetime.utcnow() - last_time).total_seconds() / 3600
            
            if hours_since > 48:  # More than 2 days
                return {"streak": 0, "last_login": last_login, "broken": True}
            elif hours_since > 24:
                return {"streak": streak, "last_login": last_login, "broken": False}
        except:
            pass
    
    return {"streak": streak, "last_login": last_login, "broken": False}


def handle_daily_login(user_id: str) -> dict:
    """
    Player logs in (plays !fusion).
    Increment streak, award bonus.
    """
    user = get_user(user_id)
    if not user:
        return {"success": False, "message": "User not found"}
    
    streak_info = get_login_streak(user_id)
    
    # Calculate new streak
    if streak_info["broken"]:
        new_streak = 1
        bonus = 50  # Starter bonus
        message = f"🔥 *Streak Broken!* Starting fresh at **Day 1**. Earned *50 Silver*."
    else:
        new_streak = streak_info["streak"] + 1
        
        # Escalating rewards: Day 1 = 50, Day 2 = 75, Day 3 = 100, etc.
        bonus = 50 + (new_streak - 1) * 25
        
        # Milestone bonuses
        if new_streak == 7:
            bonus += 500
            message = f"🔥 *DAY 7 MILESTONE!* Streak: **7 DAYS**. Earned *{bonus} Silver* + Super Crate!"
            # TODO: Add super crate
        elif new_streak == 30:
            bonus += 2000
            message = f"👑 *DAY 30 LEGEND!* Streak: **30 DAYS**. Earned *{bonus} Silver* + Legendary Item!"
        else:
            message = f"🔥 *Day {new_streak}* Streak! Earned *{bonus} Silver*."
    
    # Update user
    user["login_streak"] = new_streak
    # Store last_login in buffs JSONB instead of as separate column
    buffs = user.get("buffs", {})
    buffs["last_login"] = datetime.utcnow().isoformat()
    user["buffs"] = buffs
    user["silver"] = user.get("silver", 0) + bonus
    save_user(user_id, user)
    
    return {
        "success": True,
        "streak": new_streak,
        "bonus": bonus,
        "message": message
    }


# ═══════════════════════════════════════════════════════════════════════════
#  COMBO MULTIPLIERS - Variable Reward Schedule
# ═══════════════════════════════════════════════════════════════════════════

def get_combo_multiplier(user_id: str) -> dict:
    """Get player's current combo (consecutive word wins this round)."""
    user = get_user(user_id)
    if not user:
        return {"combo": 0, "multiplier": 1.0}
    
    combo = user.get("combo_count", 0)
    
    # Multiplier: 0-2 wins = 1x, 3 wins = 1.5x, 5 wins = 2x, 10 wins = 3x
    multiplier = 1.0
    if combo >= 3:
        multiplier = 1.5
    if combo >= 5:
        multiplier = 2.0
    if combo >= 10:
        multiplier = 3.0
    
    return {
        "combo": combo,
        "multiplier": multiplier,
        "next_milestone": None  # For display
    }


def increment_combo(user_id: str) -> dict:
    """Player won a word fusion. Increment combo."""
    user = get_user(user_id)
    if not user:
        return {"combo": 0}
    
    combo = user.get("combo_count", 0) + 1
    multiplier = get_combo_multiplier(user_id)["multiplier"]
    
    # Check thresholds
    message = ""
    if combo == 3:
        message = f"🔥 *COMBO x3!* Bonus multiplier: **1.5x** — Keep it going!"
    elif combo == 5:
        message = f"🔥 *COMBO x5!* Bonus multiplier: **2.0x** — You're unstoppable!"
    elif combo == 10:
        message = f"👑 *COMBO x10!* Bonus multiplier: **3.0x** — LEGEND!"
    elif combo % 5 == 0 and combo > 0:
        message = f"🔥 *COMBO x{combo}!* Still at **{multiplier}x** bonus!"
    
    user = get_user(user_id)
    if user:
        user["combo_count"] = combo
        save_user(user_id, user)
    
    return {
        "combo": combo,
        "multiplier": multiplier,
        "milestone_message": message
    }


def reset_combo(user_id: str):
    """Player lost or game reset. Reset combo."""
    user = get_user(user_id)
    if user:
        user["combo_count"] = 0
        save_user(user_id, user)


# ═══════════════════════════════════════════════════════════════════════════
#  WEEKLY CHALLENGES - Mini-quests for Big Rewards
# ═══════════════════════════════════════════════════════════════════════════

WEEKLY_CHALLENGES = {
    "word_warrior": {
        "name": "🗡️ Word Warrior",
        "desc": "Win 50 word fusions",
        "reward": 1000,
        "icon": "🗡️"
    },
    "level_up": {
        "name": "📈 Climber",
        "desc": "Reach Level 25",
        "reward": 500,
        "icon": "📈"
    },
    "rich_player": {
        "name": "💰 Banker",
        "desc": "Accumulate 50,000 Silver",
        "reward": 2000,
        "icon": "💰"
    },
    "leaderboard": {
        "name": "🏆 Top 10",
        "desc": "Reach Top 10 Weekly Leaderboard",
        "reward": 1500,
        "icon": "🏆"
    },
    "streak_master": {
        "name": "🔥 Streak Master",
        "desc": "Maintain 7-day login streak",
        "reward": 800,
        "icon": "🔥"
    }
}


def get_weekly_challenges(user_id: str) -> list:
    """Get player's progress on all weekly challenges."""
    user = get_user(user_id)
    if not user:
        return []
    
    challenges = []
    for key, challenge in WEEKLY_CHALLENGES.items():
        # Check if completed
        completed = user.get("challenges", {}).get(key, False)
        
        # Get progress
        progress = 0
        if key == "word_warrior":
            progress = user.get("weekly_fusion_wins", 0)
            total = 50
        elif key == "level_up":
            progress = user.get("level", 1)
            total = 25
        elif key == "rich_player":
            progress = user.get("silver", 0)
            total = 50000
        elif key == "leaderboard":
            # Check leaderboard rank
            top_10 = get_weekly_leaderboard(limit=10)
            progress = 1 if any(p[1] == user_id for p in top_10) else 0
            total = 1
        elif key == "streak_master":
            progress = user.get("login_streak", 0)
            total = 7
        
        challenges.append({
            "key": key,
            "name": challenge["name"],
            "desc": challenge["desc"],
            "reward": challenge["reward"],
            "progress": min(progress, total),
            "total": total,
            "completed": completed,
            "icon": challenge["icon"]
        })
    
    return challenges


def format_challenge_display(challenge: dict) -> str:
    """Format a single challenge for display."""
    icon = challenge["icon"]
    name = challenge["name"]
    desc = challenge["desc"]
    progress = challenge["progress"]
    total = challenge["total"]
    reward = challenge["reward"]
    
    # Progress bar
    pct = int((progress / total) * 100) if total > 0 else 0
    filled = int(pct / 10)
    bar = "⬛" * filled + "⬜" * (10 - filled)
    
    if challenge["completed"]:
        return f"✅ *{name}* — *{reward} points claimed*"
    else:
        return f"{icon} *{name}*\n├─ {desc}\n├─ Progress: [ {bar} ] {progress}/{total}\n└─ Reward: *{reward} silver*"


# ═══════════════════════════════════════════════════════════════════════════
#  RARE DROP NOTIFICATIONS - Dopamine Hits
# ═══════════════════════════════════════════════════════════════════════════

RARE_ITEMS = {
    "legendary_sword": {"name": "⚔️ Legendary Sword", "rarity": 0.01, "value": 5000},
    "phoenix_egg": {"name": "🔥 Phoenix Egg", "rarity": 0.005, "value": 10000},
    "void_shard": {"name": "⚫ Void Shard", "rarity": 0.008, "value": 7500},
    "crown_of_kings": {"name": "👑 Crown of Kings", "rarity": 0.002, "value": 25000},
}


def check_rare_drop() -> dict or None:
    """
    Random chance to drop a rare item.
    Returns item or None.
    """
    r = random.random()
    for item_key, item in RARE_ITEMS.items():
        if r < item["rarity"]:
            return {
                "key": item_key,
                "name": item["name"],
                "value": item["value"],
                "rarity_pct": item["rarity"] * 100
            }
    return None


def format_rare_drop_notification(item: dict) -> str:
    """Format a rare drop notification for max dopamine."""
    return (
        f"🎉 *ULTRA RARE DROP!*\n\n"
        f"You've found: *{item['name']}*\n"
        f"Rarity: **{item['rarity_pct']:.2f}%** (1 in {int(1/item['rarity_pct']*100)})\n"
        f"Value: *{item['value']} Silver*\n\n"
        f"😲 *LEGENDARY!*"
    )


# ═══════════════════════════════════════════════════════════════════════════
#  TIME-LIMITED OFFERS - FOMO
# ═══════════════════════════════════════════════════════════════════════════

def get_limited_offer() -> dict:
    """Generate a time-limited offer (changes hourly)."""
    hour = datetime.utcnow().hour
    
    offers = [
        {
            "name": "⚡ Speed Boost Hour",
            "desc": "50% more Silver for next 1 hour",
            "bonus": 0.5,
            "duration": 60,
            "emoji": "⚡"
        },
        {
            "name": "💎 Double Resources",
            "desc": "All base resources doubled for 1 hour",
            "bonus": 2.0,
            "duration": 60,
            "emoji": "💎"
        },
        {
            "name": "🔥 XP Blitz",
            "desc": "Triple XP gained for next 30 minutes",
            "bonus": 3.0,
            "duration": 30,
            "emoji": "🔥"
        },
    ]
    
    # Deterministic per hour
    offer = offers[hour % len(offers)]
    return offer


# ═══════════════════════════════════════════════════════════════════════════
#  NOTIFICATION TEMPLATES
# ═══════════════════════════════════════════════════════════════════════════

def notification_level_up(player_name: str, new_level: int) -> str:
    """Congratulations notification."""
    return (
        f"🎊 *{player_name} LEVELED UP!*\n\n"
        f"Now reaching *LEVEL {new_level}*\n\n"
        f"Keep climbing the ranks! 🚀"
    )


def notification_new_record(player_name: str, record: str, value: int) -> str:
    """New personal record."""
    icons = {
        "mostsilver": "💰",
        "highestcombo": "🔥",
        "mostxp": "⭐",
    }
    icon = icons.get(record, "🏆")
    return (
        f"{icon} *NEW RECORD!*\n"
        f"{player_name} just set a new personal best:\n\n"
        f"*{record.replace('_', ' ').title()}: {value}*\n\n"
        f"Can you beat it? 🔥"
    )


def notification_leaderboard_change(player_name: str, old_rank: int, new_rank: int) -> str:
    """Leaderboard rank changed."""
    if new_rank < old_rank:
        return (
            f"📈 *CLIMBING!*\n"
            f"{player_name} jumped from *#{old_rank}* to *#{new_rank}*! 🚀"
        )
    else:
        return (
            f"📉 *DROPPED!*\n"
            f"{player_name} fell from *#{old_rank}* to *#{new_rank}* ⚰️"
        )


# ═══════════════════════════════════════════════════════════════════════════
#  EXAMPLE USAGE
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Test daily login
    result = handle_daily_login("test_user")
    print(result)
    
    # Test combo multiplier
    combo = get_combo_multiplier("test_user")
    print(f"Combo: {combo}")
    
    # Test rare drop
    drop = check_rare_drop()
    if drop:
        print(format_rare_drop_notification(drop))
    
    # Test weekly challenges
    challenges = get_weekly_challenges("test_user")
    for c in challenges:
        print(format_challenge_display(c))
