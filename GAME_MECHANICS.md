# ⚙️ CORE MECHANICS & IMPLEMENTATION GUIDE

## **PHASE 1: Foundation (This Week)**

### **1. Player Registration Flow** (Level 0)

```
New Player Messages Bot in PM
    ↓
Sadistic Welcome (existing code)
    ↓
Username Check (must be unique)
    ↓
Create Player Row in PLAYERS sheet
    ├─ level: 1
    ├─ xp: 0
    ├─ coins: 0
    ├─ gold_coins: 0
    ├─ shield_status: "ACTIVE"
    ├─ shield_expiry: NOW + 3 days  ← 3-Day Newbie Shield
    ├─ sector: random_sector()
    └─ backpack_slots: 5
    ↓
Add NOVICE CRATE to inventory
    ├─ 🛡️ 3-Day Shield
    ├─ 🪙 50 Coins
    └─ ⚡ 1x XP Booster
    ↓
RESTRICT ARENA: "You're shielded. Complete tasks to Level 3 first."
    ↓
Show NEWBIE TASKS (to reach Level 3)
```

**Newbie Tasks to Unlock Arena (Level 3):**
```
✓ Complete 3 Practice Anagrams (50 XP each = 150 XP)
✓ Play 1 Tutorial Chess vs AI (100 XP)
✓ Answer 5 Trivia Questions (50 XP total)
✓ Join or search for Alliance (explore feature)
    
Total: 300 XP → Level 3 ✅
```

---

### **2. Level 3 Bundle Offer** (One-time limited)

**When they hit Level 3:**

```
🛡️ WELCOME TO THE FRONTLINE
━━━━━━━━━━━━━━━━━━━━━━━━━━
You are no longer a Newbie. Your 3-day shield is 
the only thing protecting you from the Elite players.

📦 THE GLADIATOR BUNDLE (900 NGN):
━━━━━━━━━━━━━━━━━━━━━━━━━━
🎒 +15 Permanent Slot Upgrade (5→20 slots)
🎖️ 'Founder' Badge (shows in profile)
🪙 1,000 Gold Coins  ← Cannot be looted
⚡ 3x XP Booster (2 Hours each)

━━━━━━━━━━━━━━━━━━━━━━━━━━
"Will you survive the Arena?  
Or remain a commoner?"

[💳 BUY NOW] [⏭️ SKIP]
```

**If skip:** Message repeats weekly at 09:00 AM for 2 weeks

---

## **PHASE 2: Combat & Attack System**

### **Shield Logic**

```
IF player.shield_status == "ACTIVE":
   ├─ Cannot be attacked ✅
   ├─ Cannot use attacks ❌
   ├─ Cannot join wars ❌
   └─ CAN participate in Anagrams/Chess (earn points)

IF shield_expiry < NOW:
   ├─ Deactivate shield
   ├─ Set shield_reactivate_cooldown = NOW + 24h
   └─ Send warning: "Your shield is gone!"

IF player wants to reactivate:
   ├─ Check: Is reactivate_cooldown active?
   │  ├─ YES: "Cannot shield for 24h"
   │  └─ NO: Proceed
   ├─ Check: Does player have shield item?
   │  ├─ YES: Consume item, reactivate
   │  └─ NO: Buy from shop (coins or 500₦)
   └─ Set new expiry = NOW + 7 days
```

---

### **Attack System** (Only when unshielded)

```
CHALLENGE RULES:
├─ Attacker must be at most 5 ranks ABOVE target
├─ (Block farming: Level 40 can't attack Level 3)
├─ Rank Disguise exception:
│  └─ If attacker uses Rank Disguise:
│     └─ Weaker players CAN call them out
│     └─ (Rank Disguise shows fake rank, real rank hidden)
│
ATTACK OUTCOME:
├─ Attacker wins (50-60% base win rate based on level diff):
│  ├─ Loot coins: 10-50 coins OR
│  ├─ Loot item (30% chance)
│  └─ If item looted: Notify victim
│
├─ Attacker loses:
│  ├─ Nothing happens (no loot from defeat)
│  └─ But defender wins = Defense counted
│
COOLDOWN:
└─ Cannot attack same player twice in 1 hour
```

---

### **Item Effects During Combat**

```
ATTACKER ITEMS:
├─ 💀 Rank Swap: Swap points with target
├─ 🎭 Rank Disguise: Appear as lower rank (24h)
├─ 🔥 Purge Call: Track down 3 random unshielded players
└─ 🧨 Coin Explosion: Deduct 3 coins from top 10 on leaderboard

DEFENDER ITEMS:
├─ 🛡️ Shield: Block all attacks for duration
├─ 🧠 Fake Shield: Appears protected, but isn't ← Trap!
├─ 📴 Anti-Scout: Block player recon scans
└─ ⚫ Blackout: (Special event only - mysterious effect)

NEUTRAL ITEMS:
└─ 📸 Scout: Reveal player location/rank/coins (no combat)
```

---

## **PHASE 3: Alliances**

### **Creating an Alliance** (Level 10+ only)

```
Player Types: !createalliance [NAME]
    ↓
Validate: Is name 3 letters? Is it unique?
    ↓
Create ALLIANCE row:
├─ founder_username: (not ID - shows neater)
├─ member_count: 1
├─ members_list: [player_username]
├─ weekly_points: 0
├─ alltime_points: 0
├─ alliance_bank: 0
├─ tax_rate: 10% (auto)
└─ has_expansion: false (5 members default)
    ↓
Create SECRET PRIVATE GROUP for alliance:
├─ Bot becomes ADMIN
├─ Group name: "[ALLIANCE_NAME] CHECKMATE"
├─ Join code sent to founder
├─ Founder can restrict/allow new members
└─ Bot runs ALLIANCE SHOP inside
    ↓
Auto-send group to all members:
└─ "Welcome to [ABC] CHECKMATE!"
```

### **Alliance Bank & Tax**

```
When member earns coins:
├─ If from Anagram: +100 coins
│  ├─ 10% tax (~10 coins) → Alliance bank
│  └─ 90% to player (90 coins)
│
├─ If from Chess win: +50 coins
│  ├─ 10% tax (~5 coins) → Alliance bank
│  └─ 90% to player (45 coins)
│
└─ If attacked & looted: NO TAX (already lost)

Alliance Leader Can:
├─ View alliance bank balance
├─ Distribute rewards manually
├─ Set tax rate (5-20%)
├─ Purchase expansions (3,000₦ → 14 members)
└─ Change alliance name (2,000₦ one-time)

Alliance Members:
├─ Make VOLUNTARY donations: !transfer [amount]
├─ Receive daily reward (if bank > 50 coins):
│  └─ 5 coins/day + shared gift drops
└─ Claim gift drops together
```

---

## **PHASE 4: Weekly Reset & Events**

### **Sunday 11:59 PM Reset**

```
EVERY SUNDAY 23:59 UTC+1:

1️⃣ LEADERBOARD SNAPSHOT:
   ├─ Top alliance gets GOLDEN TROPHY 👑
   ├─ Top 10 players get badges
   └─ Record in ALLTIME sheets

2️⃣  WEEKLY RESET:
   ├─ Clear all weekly_points (player + alliance)
   ├─ weekly_rank resets
   ├─ Shield durations reset (restart count)
   └─ Reset Daily Quest counter

3️⃣ REWARD DISTRIBUTION:
   ├─ Top Alliance: +1,000 coins to bank
   ├─ 2nd Alliance: +500 coins
   ├─ 3rd Alliance: +250 coins
   ├─ Top 10 Players: Double XP multiplier for "Elite Week"
   └─ Event prizes claimed automatically

4️⃣ MESSAGE TO HQ:
   └─ "🏆 [ALLIANCE_NAME] DOMINATED THIS WEEK!
      They control the HQ. Can you dethrone them?"
```

### **Wednesday Mid-Week Contention**

```
Every WEDNESDAY 18:00 UTC+1:

🔔 "HQ CONTENTION BEGINS!"
├─ Current ruling alliance: [NAME]
├─ Challenge window: 24 hours
└─ Top 3 alliances can vie for control

Scoring:
├─ Anagrams: 1 point per word
├─ Chess wins: 10 points
├─ Trivia: 2 points per correct
├─ Alliance members earn for alliance
└─ Individual can carry points for multiple alliances? NO!
   (Players belong to one alliance only)

Winner:
├─ Temporary "HQ Occupants" badge for 3 days
├─ +500 coins to alliance bank
└─ Bragging rights in group
```

---

## **PHASE 5: Games Integration**

### **Anagrams** (Existing)
- Still runs normal 60s rounds
- Top finisher gets 2x points this week
- Points also count toward WEEKLY LEADERBOARD

### **Chess** (New - Lichess Integration)

```
!play @username [TIME_CONTROL]
    ↓
Create Lichess game via API
    ↓
Share game link in group
    ↓
Players play on Lichess
    ↓
Lichess API notifies bot of result (webhook)
    ↓
Verify: Did they play at claimed time control?
    ↓
Award points:
├─ Win: +50 coins, +10 XP
├─ Draw: +25 coins, +5 XP
└─ Loss: 0 (no penalty)
    ↓
Update ACTIVE_GAMES sheet (auto-verified)
```

### **Trivia** (New)

```
!trivia [difficulty]
    ↓
Bot asks 5 questions
├─ Easy: +5 XP per correct
├─ Medium: +10 XP
└─ Hard: +25 XP
    ↓
Reward coins: (correct_count * 5)
```

### **Daily Quests**

```
Daily reset at 06:00 AM:
├─ "Score 100 points on Anagrams" → 50 XP + 50 coins
├─ "Win 1 Chess game" → 100 XP + 100 coins
├─ "Answer 5 Trivia questions" → 50 XP + 25 coins
├─ "Claim gift drop with alliance" → 50 XP + 100 coins
└─ "Attack 2 players" → 75 XP + 50 coins

Completion: Quest Chest reward
└─ Common Weekly Chest (random items)
```

---

## **PHASE 6: Shop System**

### **Player DM Shop** (Always available)

```
!shop [category]
    ↓
Categories:
├─ SHIELDS (🛡️)
│  ├─ 7-Day Shield: 200 coins OR 500₦
│  └─ 14-Day Shield: 400 coins OR 900₦
│
├─ ITEMS (Strategic)
│  ├─ 🎭 Rank Disguise: 300 coins OR 750₦
│  ├─ 💀 Rank Swap: 400 coins OR 1,000₦
│  ├─ 🧨 Coin Explosion: 250 coins OR 600₦
│  └─ 🤡 Clown Badge: 150 coins OR 350₦
│
├─ BOOSTS (⚡)
│  ├─ 2-Hour XP Booster (2x): 200 coins OR 500₦
│  └─ 24-Hour Coin Booster (1.5x): 300 coins OR 750₦
│
├─ BUNDLES (📦)
│  ├─ Starter Pack: 900₦ (see above)
│  ├─ Advanced: 1,500₦
│  └─ Elite: 3,000₦
│
└─ COSMETICS (👑)
   ├─ Founder Badge: 500 coins
   └─ Elite Title: 1,000 coins
```

### **Alliance Shop** (Member-only, in alliance group)

```
Same items PLUS:

EXCLUSIVE TO ALLIANCES:
├─ 🎁 Gift Drop (for whole alliance): 500 coins
─ └─ Distributes 100 coins to each member
├─ 🏦 Alliance Expansion: 3,000₦ (5→14 members)
├─ 📛 Name Change: 2,000₦ (once per year)
└─ 📢 Announcement Banner: 750 coins
   └─ Post message on main HQ for visibility
```

---

## **Backpack Limit Check** (Pseudocode)

```python
def canAddItem(user_id, item_id):
    player = get_player(user_id)
    item = get_item(item_id)
    
    current_slots_used = len(player.inventory)
    backpack_capacity = player.backpack_slots  # 5 or 20
    
    if current_slots_used >= backpack_capacity:
        return {
            "success": False,
            "error": f"Backpack full! {current_slots_used}/{backpack_capacity}",
            "suggestion": "Discard items with !discard or upgrade backpack"
        }
    
    if item.max_stack and item.quantity >= item.max_stack:
        return {
            "success": False,
            "error": f"{item.name} maxed! Can't hold more.",
            "suggestion": "Use or discard to make room"
        }
    
    return {"success": True}

def discardItem(user_id, item_id):
    player = get_player(user_id)
    item = get_item_from_inventory(user_id, item_id)
    
    if not item:
        return {"error": "Item not found"}
    
    player.inventory.remove(item)
    update_sheet(player)
    return {"success": True, "message": f"Discarded {item.name}"}
```

---

## **Alliance Join Request Flow**

```
New Player Searches for Alliance:
    ↓
!findalliance [name_filter]
    ↓
Bot shows:
├─ Alliance Name
├─ Founder
├─ Current Members:
│  └─ Show first 5, then "... +2 more"
├─ Weekly Rank
├─ Weekly Points
└─ [REQUEST TO JOIN]
    ↓
Player clicks: [REQUEST TO JOIN]
    ↓
Bot AUTOMATICALLY:
├─ Takes screenshot of player profile:
│  ├─ Level, XP, Shield status
│  ├─ W/D/L record
│  ├─ Alliance (if any)
│  └─ Sector
│
├─ Sends to Alliance Founder in DM:
│  └─ "🚨 [PlayerName] requests to join [ABC]
│     LVL 4 | ⚔️ 2-1-3 | 🛡️ Shield Active
│     [✅ ACCEPT] [❌ DECLINE]"
│
└─ Notifies Player: "Request sent! Waiting for approval..."
    ↓
Founder Decision (24h timeout):
├─ ACCEPT:
│  ├─ Add to alliance
│  ├─ Add to group chat
│  └─ Start 10% tax on earnings
│
├─ DECLINE:
│  └─ Notify player: "Alliance full or declined"
│
└─ NO RESPONSE (24h):
   └─ Auto-decline, player can try again
```

---

## **Lichess API Integration** (Step-by-step)

### **1. Get Lichess Token** (One-time setup)

```
1. Go to: https://lichess.org/account/oauth/token
2. Sign in with your Lichess account
3. Create Personal Access Token
   ├─ Name: "The64 Chess Bot"
   ├─ Scopes: challenge:read, challenge:bulk, challenge:write
   └─ Generate
4. Copy token (something like: "lip_abc123xyz")
```

### **2. Store in Google Script**

```javascript
// ⚙️ Google Apps Script (script.gs)

// Add these at the TOP of your script
const LICHESS_TOKEN = "lip_abc123xyz";
const LICHESS_API = "https://lichess.org/api";
const HQ_GROUP_ID = 123456789; // Get from group chat link

function createLichessGame(player1_id, player2_lichess_username, timeControl = "bullet") {
    const payload = {
        targetId: player2_lichess_username,
        rated: false,
        "clock.limit": 180, // 3 min for bullet
        "clock.increment": 0,
        color: "random",
        variant: "standard"
    };
    
    const options = {
        method: "post",
        muteHttpExceptions: true,
        headers: {
            "Authorization": `Bearer ${LICHESS_TOKEN}`
        },
        payload: JSON.stringify(payload)
    };
    
    const response = UrlFetchApp.fetch(
        `${LICHESS_API}/challenge/open`,
        options
    );
    
    if (response.getResponseCode() === 200) {
        const gameData = JSON.parse(response.getContentText());
        return {
            success: true,
            gameUrl: `https://lichess.org/${gameData.challenge.id}`,
            gameId: gameData.challenge.id
        };
    } else {
        return {
            success: false,
            error: response.getContentText()
        };
    }
}
```

### **3. Verify Game Result** (Webhook listener)

```javascript
function doPost(e) {
    const payload = JSON.parse(e.postData.contents);
    
    // Lichess sends:
    // {
    //   "type": "challenge",
    //   "challenge": {
    //     "id": "game_id",
    //     "challenger": { "name": "player1" },
    //     "destUser": { "name": "player2" },
    //     "status": "finished",
    //     "winner": "player1" | "player2" | null
    //   }
    // }
    
    if (payload.type === "gameFinish") {
        const game = payload.game;
        const winner = game.winner;
        
        recordGameResult(
            game.players[0].id,
            game.players[1].id,
            winner,
            game.id
        );
    }
}

function recordGameResult(player1_id, player2_id, winner_id, game_id) {
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("ACTIVE_GAMES");
    
    sheet.appendRow([
        game_id,
        "chess",
        player1_id,
        player2_id,
        winner_id,
        50, // coins awarded
        10, // xp awarded
        true, // verified
        "lichess_api",
        new Date()
    ]);
    
    // Update player coins/xp
    updatePlayerStats(winner_id, 50, 10);
}
```

---

## **How Group ID Works**

```
To find your Checkmate HQ Group ID:

1. Open Telegram group
2. Pin a message
3. Right-click → "Copy Message Link"
   Example: https://t.me/c/1234567890/1

   Extracted ID: 1234567890
   (This is your GROUP_ID)

4. Add "-100" prefix: -1001234567890
   (This is used in bot code)

Use in code:
    await bot.sendMessage(-1001234567890, "message")
```

---

## **Event Leaderboards** (New tracking sheet)

```
EVENTS LEADERBOARD:

| event_name | player_id | player_event_rank | event_points |
| prize_claimed | event_end_time |

🔄 AUTO-UPDATE (refreshes every 10 min during active event)

Example display in group:

⚡ BLITZ HOUR - 45 MIN REMAINING
━━━━━━━━━━━━━━━━━━━━━
🥇 Player1 — 1,200 pts
🥈 Player2 — 850 pts
🥉 Player3 — 720 pts

Prizes:
🥇 5x XP Booster + 500 coins
🥈 3x XP Booster + 300 coins
🥉 1x XP Booster + 150 coins
```

