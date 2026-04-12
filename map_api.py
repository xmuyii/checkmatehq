"""
map_api.py — Game Map API Endpoints for web visualization
Provides real-time world map data, player positions, bases, and resources
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from datetime import datetime

from supabase_db import get_user, get_alltime_leaderboard

app = FastAPI(title="The64 Map API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/player/{user_id}")
async def get_player_map_data(user_id: str):
    """Get player data for map display."""
    try:
        user = get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Player not found")
        
        base_res = user.get('base_resources', {})
        if isinstance(base_res, str):
            import json
            try:
                base_res = json.loads(base_res)
            except:
                base_res = {'resources': {}, 'food': 0}
        
        return {
            "user_id": user_id,
            "username": user.get("username", "Unknown"),
            "level": user.get("level", 1),
            "sector": user.get("sector", 1),
            "base_name": user.get("base_name", "Base"),
            "war_points": user.get("war_points", 0),
            "wins": user.get("wins", 0),
            "losses": user.get("losses", 0),
            "base_resources": base_res,
            "xp": user.get("xp", 0),
            "silver": user.get("silver", 0),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        print(f"[ERROR] get_player_map_data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/all_bases")
async def get_all_bases():
    """Get all player bases for map display."""
    try:
        # Get top 50 players by war points (most active players with established bases)
        leaderboard = get_alltime_leaderboard(limit=50)
        
        bases = []
        for player in leaderboard:
            if player.get("base_name"):
                bases.append({
                    "user_id": player.get("user_id"),
                    "username": player.get("username", "Unknown"),
                    "sector": player.get("sector", 1),
                    "base_name": player.get("base_name"),
                    "level": player.get("level", 1),
                    "war_points": player.get("all_time_points", 0),
                    "wins": player.get("wins", 0),
                    "xp": player.get("xp", 0),
                    "alliance_id": player.get("alliance_id")
                })
        
        return {
            "bases": bases,
            "count": len(bases),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        print(f"[ERROR] get_all_bases: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sector/{sector_num}")
async def get_sector_info(sector_num: int):
    """Get detailed information about a specific sector."""
    try:
        if sector_num < 1 or sector_num > 64:
            raise HTTPException(status_code=400, detail="Sector must be 1-64")
        
        leaderboard = get_alltime_leaderboard(limit=100)
        
        # Get all bases in this sector
        bases_in_sector = [
            {
                "user_id": p.get("user_id"),
                "username": p.get("username"),
                "level": p.get("level", 1),
                "war_points": p.get("all_time_points", 0),
                "base_name": p.get("base_name")
            }
            for p in leaderboard
            if p.get("sector") == sector_num and p.get("base_name")
        ]
        
        # Sector characteristics
        sector_bonus = {}
        if sector_num == 1:
            sector_bonus = {"wood": 30, "description": "Abundant forests"}
        elif sector_num == 2:
            sector_bonus = {"bronze": 20, "description": "Bronze deposits"}
        elif sector_num == 5:
            sector_bonus = {"iron": 5, "description": "Iron veins"}
        elif sector_num == 7 or sector_num == 9:
            sector_bonus = {"diamond": 2, "description": "Rare crystals"}
        
        return {
            "sector": sector_num,
            "bases": bases_in_sector,
            "base_count": len(bases_in_sector),
            "resources": sector_bonus,
            "danger_level": len(bases_in_sector),  # More bases = more danger
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        print(f"[ERROR] get_sector_info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/world/stats")
async def get_world_stats():
    """Get global world statistics."""
    try:
        leaderboard = get_alltime_leaderboard(limit=100)
        
        total_bases = len([p for p in leaderboard if p.get("base_name")])
        total_war_points = sum([p.get("all_time_points", 0) for p in leaderboard])
        occupied_sectors = len(set([p.get("sector", 1) for p in leaderboard if p.get("base_name")]))
        
        return {
            "total_players": len(leaderboard),
            "total_bases": total_bases,
            "total_war_points": total_war_points,
            "occupied_sectors": occupied_sectors,
            "max_sectors": 64,
            "coverage_percent": (occupied_sectors / 64) * 100,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        print(f"[ERROR] get_world_stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/leaderboard/map")
async def get_map_leaderboard():
    """Get top players for map leaderboard display."""
    try:
        leaderboard = get_alltime_leaderboard(limit=10)
        
        top_players = [
            {
                "rank": i + 1,
                "username": p.get("username", "Unknown"),
                "level": p.get("level", 1),
                "war_points": p.get("all_time_points", 0),
                "sector": p.get("sector", 1),
                "base_name": p.get("base_name"),
                "alliance": p.get("alliance_id", "Solo")
            }
            for i, p in enumerate(leaderboard)
        ]
        
        return {
            "leaderboard": top_players,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        print(f"[ERROR] get_map_leaderboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "map-api", "timestamp": datetime.utcnow().isoformat()}


if __name__ == "__main__":
    import uvicorn
    
    print("🗺️ Map API starting on http://0.0.0.0:8001")
    print("📚 Docs: http://0.0.0.0:8001/docs")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_level="info"
    )
