"""
Configuration management for production and test environments.

IMPORTANT: Create a .env file in your workspace root with your real credentials:
    BOT_TOKEN=your_real_bot_token
    SUPABASE_URL=your_real_supabase_url
    SUPABASE_KEY=your_real_supabase_key

Set ENVIRONMENT environment variable to 'prod' or 'test' before running.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Determine environment (default to prod for safety)
ENVIRONMENT = os.getenv('ENVIRONMENT', 'prod').lower()

# ============================================================================
# PRODUCTION CONFIG
# ============================================================================
if ENVIRONMENT == 'prod':
    BOT_TOKEN = os.getenv('BOT_TOKEN', 'your_bot_token_here').strip()
    SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://your-project.supabase.co').strip()
    SUPABASE_KEY = os.getenv('SUPABASE_KEY', 'your_supabase_anon_key_here').strip()
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
