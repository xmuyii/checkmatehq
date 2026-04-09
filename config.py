"""
Configuration management for production and test environments.
Set ENVIRONMENT environment variable to 'prod' or 'test' before running.
"""

import os

# Determine environment (default to prod for safety)
ENVIRONMENT = os.getenv('ENVIRONMENT', 'prod').lower()

# ============================================================================
# PRODUCTION CONFIG
# ============================================================================
if ENVIRONMENT == 'prod':
    BOT_TOKEN = '8770224655:AAElFUaS_9ZMFsowhkWPtSU_9LwzdKMqGoU'
    SUPABASE_URL = 'https://basniiolppmtpzishhtn.supabase.co'
    SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJhc25paW9scHBtdHB6aXNoaHRuIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NTQ3NjMwOCwiZXhwIjoyMDkxMDUyMzA4fQ.qrj1BO5dNilRDvgKtvTdwIWjBhFTRyGzuHPD271Xcac'
    DB_TABLE = 'players'  # Production table
    ENV_NAME = 'PRODUCTION'
    
# ============================================================================
# TEST CONFIG
# ============================================================================
elif ENVIRONMENT == 'test':
    BOT_TOKEN = '8625871733:AAEwODvBBGxkDnq6DiB9TNqdcTXAnVPWNoI'
    SUPABASE_URL = 'https://basniiolppmtpzishhtn.supabase.co'
    SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJhc25paW9scHBtdHB6aXNoaHRuIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NTQ3NjMwOCwiZXhwIjoyMDkxMDUyMzA4fQ.qrj1BO5dNilRDvgKtvTdwIWjBhFTRyGzuHPD271Xcac'
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
