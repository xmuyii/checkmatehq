#!/usr/bin/env python
"""
Check Supabase directly
"""
import os
from supabase import create_client
from config import SUPABASE_URL as CONFIG_SUPABASE_URL, SUPABASE_KEY as CONFIG_SUPABASE_KEY

SUPABASE_URL = os.environ.get('SUPABASE_URL', CONFIG_SUPABASE_URL)
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', CONFIG_SUPABASE_KEY)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

print("=" * 60)
print("SUPABASE DATA CHECK")
print("=" * 60)

try:
    # Get all players
    response = supabase.table('players').select('*').execute()
    
    if response.data:
        print(f"\n✅ Found {len(response.data)} players in Supabase:")
        for player in response.data:
            print(f"\n   User ID: {player.get('user_id')}")
            print(f"   Username: {player.get('username')}")
            print(f"   Level: {player.get('level')}")
            print(f"   Tutorial Complete: {player.get('completed_tutorial')}")
            print(f"   Sector: {player.get('sector')}")
    else:
        print("\n❌ No players found in Supabase 'players' table")
        print("   This means SUPABASE_SETUP.sql hasn't been run yet!")
        
except Exception as e:
    print(f"\n❌ Error querying Supabase: {e}")
    print("\nTroubleshooting:")
    print("1. Run SUPABASE_SETUP.sql in your Supabase dashboard")
    print("2. Verify SUPABASE_URL and SUPABASE_KEY are correct")
    print("3. Check Supabase project is active")

print("\n" + "=" * 60)
