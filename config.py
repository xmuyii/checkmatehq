"""
Configuration management for production and test environments.

IMPORTANT: Create a .env file in your workspace root with your real credentials:
    BOT_TOKEN=your_real_bot_token
    SUPABASE_URL=your_real_supabase_url
    SUPABASE_KEY=your_real_supabase_key

Set ENVIRONMENT environment variable to 'prod' or 'test' before running.
"""

import os
import re
from dotenv import load_dotenv
GAME_TOPICS = {
    "trivia": 36623,      # Topic ID for trivia
    "fusion": 36621,      # Topic ID for fusion
    "leaderboards": 36626  # Topic ID for leaderboards
}

# Load environment variables from .env file
load_dotenv()

# Determine environment (default to prod for safety)
ENVIRONMENT = os.getenv('ENVIRONMENT', 'prod').lower()


def _get_first_env(*names, default=''):
    for name in names:
        value = os.getenv(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def is_valid_telegram_token(token: str) -> bool:
    if not token:
        return False
    return bool(re.fullmatch(r"\d+:[A-Za-z0-9_-]{35,}", token.strip()))


LOCAL_DEV = os.getenv('LOCAL_DEV', '0').lower() in {'1', 'true', 'yes', 'on'}

# ============================================================================
# PRODUCTION CONFIG
# ============================================================================
if ENVIRONMENT == 'prod':
    BOT_TOKEN = _get_first_env('BOT_TOKEN', 'API_TOKEN', default='your_bot_token_here')
    SUPABASE_URL = _get_first_env('SUPABASE_URL', default='https://your-project.supabase.co')
    SUPABASE_KEY = _get_first_env('SUPABASE_KEY', default='your_supabase_anon_key_here')
    DB_TABLE = 'players'  # Production table
    ENV_NAME = 'PRODUCTION'

# ============================================================================
# TEST CONFIG
# ============================================================================
elif ENVIRONMENT == 'test':
    BOT_TOKEN = os.getenv('TEST_BOT_TOKEN', 'your_test_bot_token_here').strip()
    SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://your-project.supabase.co').strip()
    SUPABASE_KEY = os.getenv('SUPABASE_KEY', 'your_supabase_anon_key_here').strip()
    DB_TABLE = 'players_test'  # Test table (separate from production)
    ENV_NAME = 'TEST'

# ============================================================================
# Invalid config fallback
# ============================================================================
else:
    raise ValueError(f"Invalid ENVIRONMENT '{ENVIRONMENT}'. Use 'prod' or 'test'.")

# Print startup info
print(f"\n{'='*70}")
print(f"ENVIRONMENT: {ENV_NAME}")
print(f"DATABASE TABLE: {DB_TABLE}")
print(f"BOT TOKEN: {BOT_TOKEN[:30]}...")
print(f"{'='*70}\n")
