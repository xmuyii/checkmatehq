"""
Lichess Chess Integration System
==================================
Handles chess challenges, game tracking, and leaderboard management.

Features:
- Create challenges between players via Lichess API
- Automatic game result tracking (Win/Loss/Draw)
- Chess leaderboard with rating system
- Challenge notifications and reminders
- Game statistics per player
"""

import aiohttp
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional, List
from supabase_db import get_user, save_user

# ═══════════════════════════════════════════════════════════════════════════
#  LICHESS API CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

LICHESS_API_URL = "https://lichess.org/api"
LICHESS_TOKEN = os.getenv('LICHESS_API_KEY', 'your_lichess_api_key_here')

# Challenge configuration
CHALLENGE_CONFIG = {
    "time_control": "5+3",  # 5 min + 3 sec increment (rapid)
    "variant": "standard",
    "color": "random",
    "accept_seconds": 600  # 10 minutes to accept
}

# ═══════════════════════════════════════════════════════════════════════════
#  LICHESS API FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

async def create_challenge(challenger_lichess_id: str, opponent_lichess_id: str) -> Tuple[bool, Dict]:
    """
    Create a chess challenge on Lichess.
    
    Args:
        challenger_lichess_id: Challenger's Lichess username
        opponent_lichess_id: Opponent's Lichess username
    
    Returns:
        (success: bool, response_data: dict)
    """
    if not LICHESS_TOKEN or LICHESS_TOKEN == 'your_lichess_api_key_here':
        print("[LICHESS ERROR] API key not configured")
        return False, {"error": "Lichess API key not configured"}
    
    try:
        headers = {
            "Authorization": f"Bearer {LICHESS_TOKEN}",
            "Accept": "application/json"
        }
        
        # Time control format: "5+3" means 5 minutes + 3 seconds per move
        time_parts = CHALLENGE_CONFIG["time_control"].split("+")
        limit = int(time_parts[0]) * 60  # Convert to seconds
        increment = int(time_parts[1]) if len(time_parts) > 1 else 0
        
        data = {
            "rated": False,  # Set to False for casual, True for rated
            "clock.limit": limit,
            "clock.increment": increment,
            "color": CHALLENGE_CONFIG["color"],
            "variant": CHALLENGE_CONFIG["variant"],
            "text": f"Challenge from The64 Game - Let's play!"
        }
        
        url = f"{LICHESS_API_URL}/challenge/{opponent_lichess_id}"
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, data=data) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"[LICHESS] Challenge created: {challenger_lichess_id} vs {opponent_lichess_id}")
                    return True, result
                else:
                    error_text = await response.text()
                    print(f"[LICHESS ERROR] Status {response.status}: {error_text}")
                    return False, {"error": error_text, "status": response.status}
    
    except Exception as e:
        print(f"[LICHESS ERROR] Failed to create challenge: {e}")
        return False, {"error": str(e)}


async def get_game_status(game_id: str) -> Tuple[bool, Dict]:
    """
    Get the status of a chess game.
    
    Args:
        game_id: Lichess game ID
    
    Returns:
        (success: bool, game_data: dict)
    """
    try:
        headers = {
            "Authorization": f"Bearer {LICHESS_TOKEN}",
            "Accept": "application/json"
        }
        
        url = f"{LICHESS_API_URL}/games/{game_id}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    return True, result
                else:
                    return False, {"error": "Game not found"}
    
    except Exception as e:
        print(f"[LICHESS ERROR] Failed to get game status: {e}")
        return False, {"error": str(e)}


async def get_user_games(lichess_username: str, limit: int = 5) -> Tuple[bool, List[Dict]]:
    """
    Get recent games for a Lichess user.
    
    Args:
        lichess_username: Lichess username
        limit: Number of recent games to fetch
    
    Returns:
        (success: bool, games_list: list)
    """
    try:
        headers = {
            "Accept": "application/x-ndjson"
        }
        
        url = f"{LICHESS_API_URL}/api/games/user/{lichess_username}?max={limit}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    games = []
                    async for line in response.content:
                        if line:
                            try:
                                game = json.loads(line.decode('utf-8'))
                                games.append(game)
                            except:
                                pass
                    return True, games
                else:
                    return False, []
    
    except Exception as e:
        print(f"[LICHESS ERROR] Failed to get user games: {e}")
        return False, []


# ═══════════════════════════════════════════════════════════════════════════
#  CHESS LEADERBOARD MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

async def initialize_chess_leaderboard(user_id: int) -> bool:
    """Initialize chess stats for a new player."""
    try:
        user = await get_user(user_id)
        if not user:
            return False
        
        if "chess_stats" not in user:
            user["chess_stats"] = {
                "wins": 0,
                "losses": 0,
                "draws": 0,
                "rating": 1000,  # Starting rating
                "games_played": 0,
                "lichess_username": None,
                "recent_games": [],
                "challenges_sent": [],
                "challenges_received": [],
                "streak": 0,
                "best_streak": 0
            }
            await save_user(user_id, user)
            print(f"[CHESS] Initialized leaderboard for user {user_id}")
            return True
        
        return True
    
    except Exception as e:
        print(f"[CHESS ERROR] Failed to initialize leaderboard: {e}")
        return False


async def register_lichess_username(user_id: int, lichess_username: str) -> Tuple[bool, str]:
    """
    Register a Lichess username for a player.
    
    Args:
        user_id: Telegram user ID
        lichess_username: Lichess username to register
    
    Returns:
        (success: bool, message: str)
    """
    try:
        user = await get_user(user_id)
        if not user:
            return False, "❌ Player not found"
        
        if "chess_stats" not in user:
            await initialize_chess_leaderboard(user_id)
            user = await get_user(user_id)
        
        # Verify username exists on Lichess
        headers = {"Accept": "application/json"}
        url = f"{LICHESS_API_URL}/api/user/{lichess_username}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status != 200:
                        return False, f"❌ Lichess user '{lichess_username}' not found"
        except:
            return False, "❌ Could not verify Lichess username (API error)"
        
        user["chess_stats"]["lichess_username"] = lichess_username
        await save_user(user_id, user)
        
        print(f"[CHESS] Registered {lichess_username} for user {user_id}")
        return True, f"✅ Lichess account **{lichess_username}** linked!"
    
    except Exception as e:
        print(f"[CHESS ERROR] Failed to register username: {e}")
        return False, f"❌ Error: {str(e)}"


async def record_game_result(user_id: int, opponent_id: int, result: str, game_id: str = None) -> Tuple[bool, str]:
    """
    Record a chess game result.
    
    Args:
        user_id: User's Telegram ID
        opponent_id: Opponent's Telegram ID
        result: "win", "loss", or "draw"
        game_id: Lichess game ID
    
    Returns:
        (success: bool, message: str)
    """
    try:
        user = await get_user(user_id)
        opponent = await get_user(opponent_id)
        
        if not user or not opponent:
            return False, "❌ Player not found"
        
        if "chess_stats" not in user:
            await initialize_chess_leaderboard(user_id)
            user = await get_user(user_id)
        
        if "chess_stats" not in opponent:
            await initialize_chess_leaderboard(opponent_id)
            opponent = await get_user(opponent_id)
        
        # Update stats
        if result == "win":
            user["chess_stats"]["wins"] += 1
            user["chess_stats"]["streak"] += 1
            user["chess_stats"]["rating"] += 15
            
            opponent["chess_stats"]["losses"] += 1
            opponent["chess_stats"]["streak"] = 0
            opponent["chess_stats"]["rating"] = max(800, opponent["chess_stats"]["rating"] - 10)
            
            message = f"🏆 **Victory!** +15 rating points"
        
        elif result == "loss":
            user["chess_stats"]["losses"] += 1
            user["chess_stats"]["streak"] = 0
            user["chess_stats"]["rating"] = max(800, user["chess_stats"]["rating"] - 10)
            
            opponent["chess_stats"]["wins"] += 1
            opponent["chess_stats"]["streak"] += 1
            opponent["chess_stats"]["rating"] += 15
            
            message = f"😢 **Defeated** -10 rating points"
        
        elif result == "draw":
            user["chess_stats"]["draws"] += 1
            opponent["chess_stats"]["draws"] += 1
            
            message = "🤝 **Draw** - no rating change"
        
        else:
            return False, "❌ Invalid result"
        
        # Update streaks
        if user["chess_stats"]["streak"] > user["chess_stats"]["best_streak"]:
            user["chess_stats"]["best_streak"] = user["chess_stats"]["streak"]
        
        user["chess_stats"]["games_played"] += 1
        opponent["chess_stats"]["games_played"] += 1
        
        # Add to game history
        game_record = {
            "timestamp": datetime.now().isoformat(),
            "opponent_id": opponent_id,
            "result": result,
            "rating_before": user["chess_stats"]["rating"],
            "game_id": game_id
        }
        
        if "recent_games" not in user["chess_stats"]:
            user["chess_stats"]["recent_games"] = []
        
        user["chess_stats"]["recent_games"].insert(0, game_record)
        user["chess_stats"]["recent_games"] = user["chess_stats"]["recent_games"][:10]  # Keep last 10
        
        await save_user(user_id, user)
        await save_user(opponent_id, opponent)
        
        print(f"[CHESS] Recorded {result}: {user_id} vs {opponent_id}")
        return True, message
    
    except Exception as e:
        print(f"[CHESS ERROR] Failed to record result: {e}")
        return False, f"❌ Error recording game: {str(e)}"


async def get_chess_leaderboard(limit: int = 10) -> Tuple[bool, List[Dict]):
    """
    Get top players by chess rating.
    
    Args:
        limit: Number of top players to return
    
    Returns:
        (success: bool, leaderboard: list)
    """
    try:
        # This would fetch from database
        # For now, returning empty - will be populated via record_game_result
        print(f"[CHESS] Fetching leaderboard (top {limit})")
        return True, []
    
    except Exception as e:
        print(f"[CHESS ERROR] Failed to get leaderboard: {e}")
        return False, []


async def format_chess_stats(user_id: int) -> str:
    """Format chess stats for display."""
    try:
        user = await get_user(user_id)
        if not user or "chess_stats" not in user:
            return "❌ No chess stats found"
        
        stats = user["chess_stats"]
        total_games = stats["wins"] + stats["losses"] + stats["draws"]
        win_rate = (stats["wins"] / total_games * 100) if total_games > 0 else 0
        
        username = stats.get("lichess_username", "Not linked")
        
        message = f"""
♟️ **CHESS STATS**
━━━━━━━━━━━━━━━━━
🔗 Lichess: {username}
⭐ Rating: **{stats['rating']}**
🎮 Games: **{total_games}**
🏆 Wins: **{stats['wins']}**
💀 Losses: **{stats['losses']}**
🤝 Draws: **{stats['draws']}**
📊 Win Rate: **{win_rate:.1f}%**
🔥 Current Streak: **{stats['streak']}**
⚡ Best Streak: **{stats['best_streak']}**
"""
        return message.strip()
    
    except Exception as e:
        return f"❌ Error loading stats: {str(e)}"


async def format_challenge(challenger_name: str, opponent_name: str, game_link: str) -> str:
    """Format a chess challenge notification."""
    return f"""
♟️ **CHESS CHALLENGE!**
━━━━━━━━━━━━━━━━━
{challenger_name} has challenged {opponent_name} to a chess match!

🎮 **Play Here:** {game_link}

⏱️ Format: 5 min + 3 sec (Rapid)
⏰ Accept within 10 minutes

Good luck! ♟️✨
"""


# ═══════════════════════════════════════════════════════════════════════════
#  CHALLENGE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

async def create_callout(challenger_id: int, opponent_id: int, challenger_name: str, opponent_name: str) -> Tuple[bool, str, str]:
    """
    Create a chess callout between two players.
    
    Args:
        challenger_id: Telegram ID of challenger
        opponent_id: Telegram ID of opponent
        challenger_name: Name of challenger
        opponent_name: Name of opponent
    
    Returns:
        (success: bool, message: str, game_link: str)
    """
    try:
        challenger = await get_user(challenger_id)
        opponent = await get_user(opponent_id)
        
        if not challenger or not opponent:
            return False, "❌ One or both players not found", ""
        
        # Check if both have Lichess accounts
        if "chess_stats" not in challenger or not challenger["chess_stats"].get("lichess_username"):
            return False, f"❌ {challenger_name} hasn't linked their Lichess account. Use `/linkchess your_lichess_username`", ""
        
        if "chess_stats" not in opponent or not opponent["chess_stats"].get("lichess_username"):
            return False, f"❌ {opponent_name} hasn't linked their Lichess account. Use `/linkchess your_lichess_username`", ""
        
        challenger_lichess = challenger["chess_stats"]["lichess_username"]
        opponent_lichess = opponent["chess_stats"]["lichess_username"]
        
        # Create Lichess challenge
        success, result = await create_challenge(challenger_lichess, opponent_lichess)
        
        if not success:
            return False, f"❌ Could not create Lichess challenge: {result.get('error', 'Unknown error')}", ""
        
        # Extract game link
        game_link = result.get("challenge", {}).get("url", f"https://lichess.org/{challenger_lichess}")
        
        # Store challenge info in user data
        if "chess_stats" not in challenger["chess_stats"]:
            challenger["chess_stats"]["challenges_sent"] = []
        
        challenge_record = {
            "timestamp": datetime.now().isoformat(),
            "opponent_id": opponent_id,
            "opponent_name": opponent_name,
            "game_id": result.get("challenge", {}).get("id"),
            "status": "pending"
        }
        
        challenger["chess_stats"]["challenges_sent"].append(challenge_record)
        opponent["chess_stats"]["challenges_received"].append(challenge_record)
        
        await save_user(challenger_id, challenger)
        await save_user(opponent_id, opponent)
        
        message = await format_challenge(challenger_name, opponent_name, game_link)
        
        print(f"[CHESS] Callout created: {challenger_name} vs {opponent_name}")
        return True, message, game_link
    
    except Exception as e:
        print(f"[CHESS ERROR] Failed to create callout: {e}")
        return False, f"❌ Error: {str(e)}", ""
