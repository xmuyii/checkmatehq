# CheckMate HQ - Telegram Word Game Bot

A strategic word game bot for Telegram with resource management, base building, military units, and persistent progression.

## Features

- **Word Game Mechanics**: Submit 7-letter words to earn resources and XP
- **Resource System**: Mine Wood, Bronze, Iron, Diamond, and Relics
- **Base Management**: Build and upgrade your fortress
- **Military Units**: Train Pawns, Knights, Bishops, Rooks, Queens, Kings
- **Research Lab**: Unlock 5 powerful upgrades
- **Inventory System**: Claim items, use crates, manage your backpack
- **Leaderboards**: Weekly and all-time rankings
- **GameMaster Announcements**: Periodic messages with game info and viral sharing
- **Multiplier System**: Boost your XP or Silver earnings
- **Permanent Shields**: All players protected by default

## Setup Instructions

### 1. Prerequisites

- Python 3.9+
- Telegram account
- Supabase account (free tier works)

### 2. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/checkmateHQ.git
cd checkmateHQ
```

### 3. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure Credentials

**Create a `.env` file in the project root:**

```bash
cp .env.example .env
```

**Edit `.env` and add your real credentials:**

```
BOT_TOKEN=your_real_bot_token
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_real_supabase_key
DATABASE_TABLE=players
ENV_NAME=PRODUCTION
```

**How to get credentials:**

- **BOT_TOKEN**: Chat with [@BotFather](https://t.me/botfather) on Telegram, create a new bot, copy the token
- **SUPABASE_URL & KEY**: 
  1. Go to [supabase.com](https://supabase.com)
  2. Create a new project
  3. Go to Settings → API
  4. Copy the "Project URL" and "anon public" key

### 6. Set Up Supabase Database

Create a table named `players` with this schema:

```sql
CREATE TABLE players (
  user_id TEXT PRIMARY KEY,
  username TEXT,
  level INT DEFAULT 1,
  base_resources JSONB DEFAULT '{"resources": {"wood": 0, "bronze": 0, "iron": 0, "diamond": 0, "relics": 0}, "food": 0, "current_streak": 0}',
  buffs JSONB DEFAULT '{}',
  shield_expires TEXT DEFAULT 'permanent',
  researches JSONB DEFAULT '{}',
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);
```

### 7. Run the Bot

```bash
python main.py
```

## Project Structure

```
.
├── main.py                 # Primary bot handler & commands
├── supabase_db.py          # Database persistence layer
├── initiation.py           # Tutorial trials system
├── config.py               # Environment configuration
├── SupaDB1.txt             # Dictionary (267K+ words)
├── requirements.txt        # Python dependencies
├── .env.example            # Environment template (copy to .env)
├── .gitignore              # Git ignore rules
└── DATABASE_SCHEMA.md      # Detailed schema documentation
```

## Commands

### Player Commands
- `!start` - Initialize your account
- `!profile` - View your stats
- `!inventory` - Check items
- `!claims` - View unclaimed items
- `!autoclaim` - Auto-claim all items
- `!discard` - Remove items from inventory

### Base Commands
- `!setup_base [BaseName]` - Create your base
- `!base` - View base status
- `!changebasename [NewName]` - Rename base (once)
- `!changename [NewName]` - Change username (once)

### Game Commands
- `!tutorial` - Comprehensive 10-part walkthrough
- `!help` - Show all commands
- `!lab` - Research lab with 5 upgrades
- `!weekly` - Weekly leaderboard
- `!alltime` - All-time leaderboard

## Game Mechanics

### Word Validation
- Submit 7-letter words during your turn
- Words validated using 267K+ word dictionary
- Correct words earn resources based on word length

### Resources
- **4-letter words** → Wood
- **5-letter words** → Bronze  
- **6-letter words** → Iron
- **7-letter words** → Diamond
- **8+ letter words** → Relics

### Streaks
- **3+ consecutive correct words** = Food streak
- **Streak resets every 120 seconds**
- Food helps build military units

## Security

⚠️ **IMPORTANT**: Never commit `.env` file to GitHub!

- `.env` is in `.gitignore` - it stays local only
- Real credentials ONLY go in local `.env`
- `.env.example` uses placeholders for reference
- Each developer creates their own `.env` locally

## Troubleshooting

### Bot won't start
- Check BOT_TOKEN is correct
- Verify Supabase credentials
- Run `python requirements.txt` to ensure all packages installed

### Database errors (PGRST204)
- Verify Supabase table schema matches expected columns
- Check SUPABASE_KEY has correct permissions

### Dictionary not loading
- Verify `SupaDB1.txt` exists in project root
- File should contain 267,627 words (one per line)

## Coming Soon

- 🔗 Alliance system
- ⚔️ PvP wars & conquest
- 🛍️ Premium shop
- 📋 Missions & quests
- 🌍 More sectors

## Contributing

Feel free to fork, modify, and submit pull requests!

## License

This project is for personal/educational use.

## Support

For issues or questions, feel free to create an issue on GitHub or contact the GameMaster 👀
