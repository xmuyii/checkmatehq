import os
import random
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
DB_TABLE = 'players_test' if os.environ.get('ENVIRONMENT', 'prod').lower() == 'test' else 'players'

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY in environment variables.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def simulate_bot_activity():
    """
    Fetch all users where is_bot is True and add 50-200 random points 
    to their weekly_points.
    """
    try:
        # Fetch bot players
        response = supabase.table(DB_TABLE).select("user_id, username, weekly_points").eq("is_bot", True).execute()
        
        bot_players = response.data
        if not bot_players:
            print(f"[{datetime.now()}] No bot players found in database.")
            return

        print(f"[{datetime.now()}] Found {len(bot_players)} bot players. Simulating activity...")

        updated_count = 0
        for bot in bot_players:
            current_points = int(bot.get('weekly_points', 0) or 0)
            random_points = random.randint(50, 200)
            new_points = current_points + random_points
            
            try:
                # Update database
                supabase.table(DB_TABLE).update({"weekly_points": new_points}).eq("user_id", bot['user_id']).execute()
                print(f"  -> Added {random_points} pts to {bot.get('username', 'Unknown Bot')} (New Total: {new_points})")
                updated_count += 1
            except Exception as e:
                print(f"  -> Failed to update bot {bot.get('username')}: {e}")
                
        print(f"[{datetime.now()}] Successfully updated {updated_count} bot players.")
        
    except Exception as e:
        print(f"[{datetime.now()}] Error simulating bot activity: {e}")

if __name__ == "__main__":
    print(f"Running Bot Activity Simulator on table: {DB_TABLE}")
    simulate_bot_activity()
