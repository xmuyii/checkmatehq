"""
Internal Chess System - Bot-Managed Games
==========================================
Players can challenge each other without needing Lichess accounts.
Bot manages game state, color assignment, and leaderboard.

Features:
- Internal chess game creation
- Automatic color assignment (white/black)
- Game state tracking
- Winner determination by moves
- Leaderboard with rating system
- Prevents unauthorized players from joining
"""

import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional, List
from supabase_db import get_user, save_user

# ═══════════════════════════════════════════════════════════════════════════
#  INTERNAL CHESS GAME STATE
# ═══════════════════════════════════════════════════════════════════════════

# Store active games: game_id -> game_data
ACTIVE_GAMES: Dict[str, Dict] = {}

# Game status constants
GAME_STATUS_PENDING = "pending"      # Waiting for opponent to accept
GAME_STATUS_ACTIVE = "active"        # Game in progress
GAME_STATUS_COMPLETED = "completed"  # Game finished
GAME_STATUS_REJECTED = "rejected"    # Challenge rejected
GAME_STATUS_EXPIRED = "expired"      # Challenge timed out

# ═══════════════════════════════════════════════════════════════════════════
#  CHESS GAME MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

def generate_game_id() -> str:
    """Generate unique game ID."""
    return f"chess_{random.randint(100000, 999999)}_{int(datetime.now().timestamp())}"


async def initialize_chess_stats(user_id: int) -> bool:
    """Initialize chess stats for a player."""
    try:
        user = await get_user(user_id)
        if not user:
            return False
        
        if "chess_stats" not in user:
            user["chess_stats"] = {
                "wins": 0,
                "losses": 0,
                "draws": 0,
                "rating": 1000,
                "games_played": 0,
                "recent_games": [],
                "challenges_sent": [],
                "challenges_received": [],
                "streak": 0,
                "best_streak": 0
            }
            await save_user(user_id, user)
            print(f"[CHESS] Initialized stats for user {user_id}")
            return True
        
        return True
    
    except Exception as e:
        print(f"[CHESS ERROR] Failed to initialize stats: {e}")
        return False


async def create_game_challenge(
    challenger_id: int,
    challenger_name: str,
    opponent_id: int,
    opponent_name: str,
    time_control: str = "5+3"
) -> Tuple[bool, str, str]:
    """
    Create a chess challenge between two players.
    
    Args:
        challenger_id: ID of player challenging
        challenger_name: Name of challenger
        opponent_id: ID of player being challenged
        opponent_name: Name of opponent
        time_control: Time format (e.g., "5+3")
    
    Returns:
        (success: bool, message: str, game_id: str)
    """
    try:
        challenger = await get_user(challenger_id)
        opponent = await get_user(opponent_id)
        
        if not challenger or not opponent:
            return False, "❌ One or both players not found", ""
        
        # Initialize chess stats if needed
        await initialize_chess_stats(challenger_id)
        await initialize_chess_stats(opponent_id)
        
        # Generate game ID
        game_id = generate_game_id()
        
        # Randomly assign colors
        colors = ["white", "black"]
        random.shuffle(colors)
        challenger_color = colors[0]
        opponent_color = colors[1]
        
        # Create game record
        game_data = {
            "game_id": game_id,
            "challenger_id": challenger_id,
            "challenger_name": challenger_name,
            "challenger_color": challenger_color,
            "opponent_id": opponent_id,
            "opponent_name": opponent_name,
            "opponent_color": opponent_color,
            "time_control": time_control,
            "status": GAME_STATUS_PENDING,
            "created_at": datetime.now().isoformat(),
            "accepted_at": None,
            "completed_at": None,
            "result": None,  # "win", "loss", "draw"
            "winner_id": None,
            "loser_id": None,
            "white_player_id": challenger_id if challenger_color == "white" else opponent_id,
            "black_player_id": challenger_id if challenger_color == "black" else opponent_id,
            "moves": [],  # Track moves for replay
            "authorized_players": [challenger_id, opponent_id]  # Only these can play
        }
        
        # Store game
        ACTIVE_GAMES[game_id] = game_data
        
        # Store in user data
        challenger_obj = await get_user(challenger_id)
        opponent_obj = await get_user(opponent_id)
        
        if "chess_stats" not in challenger_obj:
            await initialize_chess_stats(challenger_id)
            challenger_obj = await get_user(challenger_id)
        
        if "chess_stats" not in opponent_obj:
            await initialize_chess_stats(opponent_id)
            opponent_obj = await get_user(opponent_id)
        
        if "challenges_sent" not in challenger_obj["chess_stats"]:
            challenger_obj["chess_stats"]["challenges_sent"] = []
        
        if "challenges_received" not in opponent_obj["chess_stats"]:
            opponent_obj["chess_stats"]["challenges_received"] = []
        
        challenger_obj["chess_stats"]["challenges_sent"].append({
            "game_id": game_id,
            "opponent_id": opponent_id,
            "timestamp": datetime.now().isoformat()
        })
        
        opponent_obj["chess_stats"]["challenges_received"].append({
            "game_id": game_id,
            "challenger_id": challenger_id,
            "timestamp": datetime.now().isoformat()
        })
        
        await save_user(challenger_id, challenger_obj)
        await save_user(opponent_id, opponent_obj)
        
        # Create challenge message
        message = f"""
♟️ **CHESS CHALLENGE!**
━━━━━━━━━━━━━━━━━━
🔔 {challenger_name} challenges {opponent_name}

⏱️ Format: {time_control}
🎮 Game ID: `{game_id}`

**Colors:**
⚪ White: {challenger_name if challenger_color == "white" else opponent_name}
⚫ Black: {challenger_name if challenger_color == "black" else opponent_name}

👆 {opponent_name}: Accept the challenge with `/accept_chess {game_id}`

This challenge will expire in 10 minutes.
"""
        
        print(f"[CHESS] Challenge created: {game_id}")
        return True, message, game_id
    
    except Exception as e:
        print(f"[CHESS ERROR] Failed to create challenge: {e}")
        return False, f"❌ Error: {str(e)}", ""


async def accept_game_challenge(user_id: int, game_id: str) -> Tuple[bool, str]:
    """
    Accept a chess challenge.
    
    Args:
        user_id: ID of player accepting
        game_id: Game ID to accept
    
    Returns:
        (success: bool, message: str)
    """
    try:
        if game_id not in ACTIVE_GAMES:
            return False, f"❌ Game `{game_id}` not found"
        
        game = ACTIVE_GAMES[game_id]
        
        # Check if user is the opponent
        if game["opponent_id"] != user_id:
            return False, "❌ You are not the challenged player"
        
        if game["status"] != GAME_STATUS_PENDING:
            return False, f"❌ Game status: {game['status']}"
        
        # Accept the challenge
        game["status"] = GAME_STATUS_ACTIVE
        game["accepted_at"] = datetime.now().isoformat()
        
        message = f"""
♟️ **CHALLENGE ACCEPTED!**
━━━━━━━━━━━━━━━━━━
✅ {game['opponent_name']} accepted!

**Match Starting:**
⚪ White: {game['challenger_name'] if game['challenger_color'] == 'white' else game['opponent_name']}
⚫ Black: {game['challenger_name'] if game['challenger_color'] == 'black' else game['opponent_name']}

🎮 **Game ID:** `{game_id}`
⏱️ **Time:** {game['time_control']}

Players can now record the game result.
Use `/chess_result {game_id} [win|loss|draw]` to record outcome.
"""
        
        print(f"[CHESS] Challenge accepted: {game_id}")
        return True, message
    
    except Exception as e:
        print(f"[CHESS ERROR] Failed to accept challenge: {e}")
        return False, f"❌ Error: {str(e)}"


async def record_game_result(user_id: int, game_id: str, result: str) -> Tuple[bool, str]:
    """
    Record the result of a chess game.
    
    Args:
        user_id: User submitting result
        game_id: Game ID
        result: "win", "loss", or "draw"
    
    Returns:
        (success: bool, message: str)
    """
    try:
        if game_id not in ACTIVE_GAMES:
            return False, f"❌ Game `{game_id}` not found"
        
        game = ACTIVE_GAMES[game_id]
        
        # Verify user is authorized
        if user_id not in game["authorized_players"]:
            return False, "❌ You are not a participant in this game"
        
        if game["status"] != GAME_STATUS_ACTIVE:
            return False, f"❌ Game is {game['status']}"
        
        # Determine opponent
        opponent_id = game["opponent_id"] if game["challenger_id"] == user_id else game["challenger_id"]
        user_name = game["challenger_name"] if game["challenger_id"] == user_id else game["opponent_name"]
        opponent_name = game["opponent_name"] if game["challenger_id"] == user_id else game["challenger_name"]
        
        # Update game record
        game["status"] = GAME_STATUS_COMPLETED
        game["completed_at"] = datetime.now().isoformat()
        game["result"] = result
        
        # Get both players
        user_obj = await get_user(user_id)
        opponent_obj = await get_user(opponent_id)
        
        if not user_obj or not opponent_obj:
            return False, "❌ Player data not found"
        
        # Initialize stats if needed
        if "chess_stats" not in user_obj:
            await initialize_chess_stats(user_id)
            user_obj = await get_user(user_id)
        
        if "chess_stats" not in opponent_obj:
            await initialize_chess_stats(opponent_id)
            opponent_obj = await get_user(opponent_id)
        
        # Record result
        if result == "win":
            game["winner_id"] = user_id
            game["loser_id"] = opponent_id
            
            user_obj["chess_stats"]["wins"] += 1
            user_obj["chess_stats"]["streak"] += 1
            user_obj["chess_stats"]["rating"] += 15
            
            opponent_obj["chess_stats"]["losses"] += 1
            opponent_obj["chess_stats"]["streak"] = 0
            opponent_obj["chess_stats"]["rating"] = max(800, opponent_obj["chess_stats"]["rating"] - 10)
            
            result_msg = f"🏆 **{user_name}** WINS! +15 rating"
        
        elif result == "loss":
            game["winner_id"] = opponent_id
            game["loser_id"] = user_id
            
            user_obj["chess_stats"]["losses"] += 1
            user_obj["chess_stats"]["streak"] = 0
            user_obj["chess_stats"]["rating"] = max(800, user_obj["chess_stats"]["rating"] - 10)
            
            opponent_obj["chess_stats"]["wins"] += 1
            opponent_obj["chess_stats"]["streak"] += 1
            opponent_obj["chess_stats"]["rating"] += 15
            
            result_msg = f"💀 **{opponent_name}** WINS! {user_name} loses 10 rating"
        
        elif result == "draw":
            user_obj["chess_stats"]["draws"] += 1
            opponent_obj["chess_stats"]["draws"] += 1
            
            result_msg = f"🤝 **DRAW** - Both players drew"
        
        else:
            return False, "❌ Invalid result. Use: win, loss, or draw"
        
        # Update stats
        if user_obj["chess_stats"]["streak"] > user_obj["chess_stats"]["best_streak"]:
            user_obj["chess_stats"]["best_streak"] = user_obj["chess_stats"]["streak"]
        
        if opponent_obj["chess_stats"]["streak"] > opponent_obj["chess_stats"]["best_streak"]:
            opponent_obj["chess_stats"]["best_streak"] = opponent_obj["chess_stats"]["streak"]
        
        user_obj["chess_stats"]["games_played"] += 1
        opponent_obj["chess_stats"]["games_played"] += 1
        
        # Save game in history
        game_record = {
            "game_id": game_id,
            "opponent_id": opponent_id,
            "result": result,
            "rating_before": user_obj["chess_stats"]["rating"],
            "timestamp": datetime.now().isoformat()
        }
        
        if "recent_games" not in user_obj["chess_stats"]:
            user_obj["chess_stats"]["recent_games"] = []
        
        user_obj["chess_stats"]["recent_games"].insert(0, game_record)
        user_obj["chess_stats"]["recent_games"] = user_obj["chess_stats"]["recent_games"][:10]
        
        await save_user(user_id, user_obj)
        await save_user(opponent_id, opponent_obj)
        
        print(f"[CHESS] Game result recorded: {game_id} - {result}")
        
        return True, result_msg
    
    except Exception as e:
        print(f"[CHESS ERROR] Failed to record result: {e}")
        return False, f"❌ Error: {str(e)}"


async def get_game_info(game_id: str) -> Tuple[bool, str]:
    """Get information about a specific game."""
    try:
        if game_id not in ACTIVE_GAMES:
            return False, f"❌ Game `{game_id}` not found"
        
        game = ACTIVE_GAMES[game_id]
        
        info = f"""
♟️ **GAME INFO**
━━━━━━━━━━━━━
🆔 Game ID: `{game_id}`
📊 Status: {game['status'].upper()}

**Players:**
🔔 Challenger: {game['challenger_name']} ({game['challenger_color']})
👤 Opponent: {game['opponent_name']} ({game['opponent_color']})

⏱️ Time Control: {game['time_control']}
🕐 Created: {game['created_at']}

"""
        
        if game["status"] == GAME_STATUS_COMPLETED:
            if game["result"] == "draw":
                result_text = f"🤝 Draw"
            else:
                winner = game["challenger_name"] if game["winner_id"] == game["challenger_id"] else game["opponent_name"]
                result_text = f"🏆 {winner} Won"
            
            info += f"**Result:** {result_text}\n"
        
        return True, info
    
    except Exception as e:
        print(f"[CHESS ERROR] Failed to get game info: {e}")
        return False, f"❌ Error: {str(e)}"


async def format_chess_stats(user_id: int) -> str:
    """Format player's chess statistics."""
    try:
        user = await get_user(user_id)
        if not user or "chess_stats" not in user:
            return "❌ No chess stats found. Use `/callout` to play!"
        
        stats = user["chess_stats"]
        total_games = stats["wins"] + stats["losses"] + stats["draws"]
        win_rate = (stats["wins"] / total_games * 100) if total_games > 0 else 0
        
        message = f"""
♟️ **CHESS STATS**
━━━━━━━━━━━━━━━━━
⭐ Rating: **{stats['rating']}**
🎮 Games: **{total_games}**

**Record:**
🏆 Wins: **{stats['wins']}**
💀 Losses: **{stats['losses']}**
🤝 Draws: **{stats['draws']}**
📊 Win Rate: **{win_rate:.1f}%**

**Streaks:**
🔥 Current: **{stats['streak']}**
⚡ Best: **{stats['best_streak']}**
"""
        return message.strip()
    
    except Exception as e:
        return f"❌ Error loading stats: {str(e)}"


def cleanup_expired_games():
    """Remove games that have expired (older than 24 hours)."""
    try:
        expired = []
        cutoff = datetime.now() - timedelta(hours=24)
        
        for game_id, game in ACTIVE_GAMES.items():
            if game["status"] == GAME_STATUS_PENDING:
                created = datetime.fromisoformat(game["created_at"])
                if created < cutoff:
                    expired.append(game_id)
        
        for game_id in expired:
            ACTIVE_GAMES[game_id]["status"] = GAME_STATUS_EXPIRED
            print(f"[CHESS] Game expired: {game_id}")
        
        return len(expired)
    
    except Exception as e:
        print(f"[CHESS ERROR] Cleanup failed: {e}")
        return 0
