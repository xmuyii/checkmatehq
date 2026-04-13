"""
api_web.py — Simple FastAPI server for web game integration
Handles crate drops, silver deductions, and chat notifications
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
from datetime import datetime
from typing import Dict, List

# Import game functions
from supabase_db import get_user, save_user

app = FastAPI(title="The64 Web API")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store for notifications (will be flushed periodically)
trap_triggered_notifications: List[Dict] = []

@app.post("/api/deduct_silver_trap")
async def deduct_silver_trap(data: dict):
    """
    Deduct silver from a player for triggering a monkey trap.
    Called from web frontend when player grabs a monkey crate decoy.
    """
    try:
        user_id = str(data.get("user_id"))
        amount = int(data.get("amount", 50))
        
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id required")
        
        # Get user from database
        user = get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Player not found")
        
        # Deduct silver
        current_silver = user.get("silver", 0)
        new_silver = max(0, current_silver - amount)
        user["silver"] = new_silver
        
        # Save updated user
        save_user(user_id, user)
        
        # Store notification for Telegram chat
        notification = {
            "user_id": user_id,
            "username": user.get("username", f"Player_{user_id}"),
            "type": "trap_triggered",
            "amount": amount,
            "timestamp": datetime.utcnow().isoformat(),
            "old_silver": current_silver,
            "new_silver": new_silver
        }
        trap_triggered_notifications.append(notification)
        
        return {
            "success": True,
            "message": f"Deducted {amount} silver",
            "new_silver": new_silver,
            "old_silver": current_silver
        }
    
    except Exception as e:
        print(f"[ERROR] deduct_silver_trap: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/trap_notifications")
async def get_trap_notifications():
    """
    Get all pending trap notifications for the Telegram bot to broadcast.
    Called by the bot to fetch and send notifications to players.
    """
    global trap_triggered_notifications
    
    notifications = trap_triggered_notifications.copy()
    trap_triggered_notifications.clear()  # Clear after retrieval
    
    return {
        "notifications": notifications,
        "count": len(notifications)
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


if __name__ == "__main__":
    import uvicorn
    
    # Run on port 8000 (you may need to adjust for your deployment)
    print("🌐 Web API starting on http://0.0.0.0:8000")
    print("📚 Docs available at http://0.0.0.0:8000/docs")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
