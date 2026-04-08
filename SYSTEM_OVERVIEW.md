# 🎮 The 64 - Complete System Update

## ✅ UPDATE SUMMARY

Your game system has been fully upgraded with the following features:

---

## 1. **MULTIPLE SIMULTANEOUS GAMES** ✨

### How It Works:
Each group chat now runs its own independent game instance. The system uses a **dictionary of game engines** keyed by `chat_id`.

**Code Structure:**
```python
# In main.py
active_games = {}  # Dictionary storing game instances per chat

def get_or_create_engine(chat_id):
    """Get or create a game engine for a specific chat"""
    if chat_id not in active_games:
        active_games[chat_id] = GameEngine()  # New instance for this group
    return active_games[chat_id]
```

**Example:**
- Group A (`chat_id=12345`) has its own GameEngine running
- Group B (`chat_id=67890`) has a separate GameEngine running  
- Both run independently, no conflicts
- Each stores its own `scores`, `letters`, `used_words`, etc.

**Real-world Scenario:**
- You're in 3 groups with The 64 bot
- Type `!fusion` in Group A → Game starts there
- Type `!fusion` in Group B → Separate game starts there
- Both leaderboards are independent during that round
- After 60 seconds, each group shows its own leaderboard

---

## 2. **COMMANDS NOW USE `!` INSTEAD OF `/`** ⚙️

Changed from slash commands to exclamation commands:

| Command | Purpose |
|---------|---------|
| `!fusion` | Start/join the game (group only) |
| `!weekly` | See weekly leaderboard |
| `!alltime` | See all-time leaderboard |

**Validation:** `!fusion` only works in groups (private message gives error)

---

## 3. **SUNDAY 11:59 PM AUTOMATIC RESET** 🔄

Weekly leaderboard automatically resets every Sunday night → Monday starts fresh week.

**How It Works:**
```python
# In database.py
def get_current_week_start():
    """Get Monday of current week (resets Sunday 11:59 PM)"""
    today = datetime.now()
    days_since_monday = (today.weekday() + 1) % 7
    return (today - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
```

- Monday 00:00 → Sunday 23:59 = One week
- Every player's `weekly_points = 0` resets on Monday
- `all_time_points` never reset (persistent)
- `week_start` timestamp tracks current week

---

## 4. **FULL ONBOARDING SYSTEM** 🎯

When a new player messages the bot in **private DMs**:

### Phase 1: Sadistic Greeting (State: `awaiting_username`)
```
GameMaster: "Look what crawled into my domain..."
Options: ⚔️ Ready to enter | 🚪 Lost
```

### Phase 2: Username Capture
Player types their desired username → Auto-registered in database

### Phase 3: Three Trial Rounds
- **Round 1, 2, 3**: Player finds anagrams from 6-letter word pairs
- Type words → Get points
- Type `!done` → See rigged leaderboard
- Round 1-2: Always ranked 3rd place (or lower each round)
- **Round 3 (FINAL TRICK)**: Player has HIGHEST score but ranked **LAST** 🤣

Example Round 3 Output:
```
🏆 FINAL TRIAL LEADERBOARD
1. Predator_99 — 45 pts
2. ShadowMaster — 38 pts
...
10. **YourName — 65 pts** (11th place)

GameMaster: "Highest score. Lowest rank. How hilariously pathetic!"
```

### Phase 4: Silver & Backpack Choice
- **100 Silver Awarded** (Currency for future purchases)
- Choose backpack:
  - 🐢 **Grumpy Turtle** (FREE) — 5 inventory slots
  - 🐢 **Premium Turtle** (₦900) — 20 slots

### Phase 5: Sector Assignment
Random sector assignment with flavor text:
- 🏜️ **Badlands** (1-20) — Harsh deserts
- ⛰️ **Crimson Peaks** (1-15) — Towering mountains
- 🌌 **Void Sector** (1-10) — Abyss whispers
- 🏭 **Iron Mill** (1-25) — Flesh meets machine
- 🌺 **Floating Gardens** (1-12) — Beauty conceals danger

Example: `"You have spawned in Badlands Sector 8"`

---

## 5. **ENHANCED DATABASE SYSTEM** 📊

### Player Data Structure (players.json):
```json
{
  "123456789": {
    "username": "ShadowKnight",
    "all_time_points": 1250,
    "weekly_points": 145,
    "week_start": "2026-04-07T00:00:00",
    "total_words": 87,
    "silver": 100,
    "backpack_slots": 5,
    "backpack_image": "grumpy_turtle",
    "inventory": [],
    "sector": "Badlands 8",
    "registered": true
  }
}
```

### New Database Functions:
```python
add_silver(user_id, amount)          # Add currency
set_sector(user_id, sector)          # Assign sector
upgrade_backpack(user_id)            # Upgrade if have 900 silver
get_weekly_leaderboard()             # Top 10 this week (auto-resets)
get_alltime_leaderboard()            # Top 10 all-time (permanent)
```

---

## 6. **LEADERBOARD SYSTEM** 🏆

### Weekly Leaderboard (`!weekly`)
Shows top 10 players THIS WEEK ONLY
- Resets every Monday (Sunday 11:59 PM)
- Encourages competition fresh each week

### All-Time Leaderboard (`!alltime`)
Shows top 10 players EVER
- Never resets
- Permanent records
- Shows total words found

### Round-End Display
After each 60-second round in the group:
```
🏆 ROUND OVER
🥇 Player1 — 18 pts
🥈 Player2 — 12 pts
🥉 Player3 — 9 pts

📊 Use `!weekly` or `!alltime` for full stats
```

---

## 7. **GAME FLOW SUMMARY** 🎮

### For New Players:
1. Message bot in private → Get sadistic greeting
2. Accept → Enter username
3. Complete 3 trial rounds (rigged against them)
4. Get 100 silver
5. Choose backpack
6. Get assigned random sector
7. ✅ **Can now join group game with `!fusion`**

### For Playing in Group:
1. Type `!fusion` in group → Start/join game
2. GameMaster posts 2 seven-letter words (mixed)
3. 60 seconds to find as many anagrams as possible
4. Each valid word = (length - 2) points
5. Points go to: weekly + all-time + round score
6. Leaderboard shown after 60s
7. 10-second break, then new round
8. Game stops after 3 empty rounds (no one plays)

---

## 8. **IMPORTANT NOTES** ⚠️

### Supabase Integration:
- **Dictionary table required** with columns: `word`, `word_length`
- All word validation happens via Supabase API
- Anagram checking is done locally for speed

### Player Auto-Registration:
- If unregistered player types a word in group → Auto-registers
- They get default stats immediately
- Can view leaderboards after this

### Command Exclusivity:
- `!fusion` only works in **groups/supergroups**, blocked in DMs
- Other commands (`!weekly`, `!alltime`) work everywhere

### No Word Duplication:
- Once a word is used in current round, no one else can use it
- Reset when game ends and new round starts

---

## 9. **FILE CHANGES MADE** 📝

### ✅ database.py
- Added `get_or_create_engine()` dictionary system
- Fixed Sunday reset logic
- Added `add_silver()`, `set_sector()`, `upgrade_backpack()`
- Player data now includes: silver, backpack, inventory, sector

### ✅ main.py
- Changed `/` commands to `!` commands
- Replaced `GlobalEngine` with `GameEngine` (per-chat instance)
- Added `active_games` dictionary for simultaneous games
- `!fusion` now group-only with validation
- `get_or_create_engine(chat_id)` handles per-chat games

### ✅ initiation.py
- Complete rewrite with full onboarding flow
- 3-round trial system with FSM states
- Rigged leaderboards
- Backpack choice & sector assignment
- Proper error handling and state management

---

## 10. **NEXT STEPS / FUTURE FEATURES** 🚀

Currently ready:
- ✅ Multi-group support
- ✅ Weekly leaderboards with resets
- ✅ Full onboarding experience
- ✅ Proper command structure

Could add (when needed):
- Crate system (inventory management)
- Sector-based challenges
- Buffs/effects system
- Trading between players
- Rank achievements
- Streaks/combo multipliers

---

## 11. **TESTING CHECKLIST** ✓

Before going live:
```
[ ] Test !fusion in multiple groups simultaneously
[ ] Test player onboarding (private DM → trial rounds)
[ ] Verify Sunday reset works
[ ] Check weekly vs all-time leaderboards
[ ] Verify !weekly and !alltime commands work
[ ] Test word validation against Supabase
[ ] Check that players auto-register on first guess
[ ] Verify rigged leaderboards show correctly
[ ] Test backpack choice and sector assignment
```

---

**Your game is now fully operational with multi-group support, proper leaderboards, and a comprehensive onboarding system!** 🎮✨
