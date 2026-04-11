"""
alliance_system.py — Player alliances with resource sharing

Mechanics:
  - Players can create or join alliances
  - Alliance members can share resources with each other
  - !share [resource] [amount] @member — Send resources to ally
"""

import json
from datetime import datetime
from typing import Tuple, Dict, List
from supabase_db import get_user, save_user

# Max alliance size
MAX_ALLIANCE_SIZE = 50


def create_alliance(leader_id: str, alliance_name: str) -> Tuple[bool, str]:
    """Create a new alliance. Leader becomes the founder."""
    leader = get_user(leader_id)
    if not leader:
        return False, "Player not found"
    
    if leader.get("alliance_id"):
        return False, "Already in an alliance"
    
    if len(alliance_name) < 3 or len(alliance_name) > 20:
        return False, "Alliance name must be 3-20 characters"
    
    # Create alliance ID (timestamp-based)
    alliance_id = f"alliance_{int(datetime.utcnow().timestamp())}"
    
    # Initialize alliance data
    alliance_data = {
        "id": alliance_id,
        "name": alliance_name,
        "leader_id": leader_id,
        "members": [leader_id],
        "created_at": datetime.utcnow().isoformat(),
        "treasury": {"wood": 0, "bronze": 0, "iron": 0, "diamond": 0, "relics": 0},
    }
    
    # Update leader
    leader["alliance_id"] = alliance_id
    leader["alliance_role"] = "LEADER"
    save_user(leader_id, leader)
    
    # Store alliance in a file for now (ideally would be in DB)
    try:
        with open("alliances.json", "r") as f:
            alliances = json.load(f)
    except:
        alliances = {}
    
    alliances[alliance_id] = alliance_data
    
    with open("alliances.json", "w") as f:
        json.dump(alliances, f, indent=2)
    
    return True, f"✅ Alliance '{alliance_name}' created!"


def join_alliance(player_id: str, alliance_id: str) -> Tuple[bool, str]:
    """Join an existing alliance."""
    player = get_user(player_id)
    if not player:
        return False, "Player not found"
    
    if player.get("alliance_id"):
        return False, "Already in an alliance"
    
    try:
        with open("alliances.json", "r") as f:
            alliances = json.load(f)
    except:
        return False, "Alliance not found"
    
    if alliance_id not in alliances:
        return False, "Alliance not found"
    
    alliance = alliances[alliance_id]
    
    if len(alliance["members"]) >= MAX_ALLIANCE_SIZE:
        return False, f"Alliance is full ({MAX_ALLIANCE_SIZE} members)"
    
    # Add member
    alliance["members"].append(player_id)
    player["alliance_id"] = alliance_id
    player["alliance_role"] = "MEMBER"
    
    alliances[alliance_id] = alliance
    save_user(player_id, player)
    
    with open("alliances.json", "w") as f:
        json.dump(alliances, f, indent=2)
    
    return True, f"✅ Joined alliance '{alliance['name']}'"


def get_alliance_info(alliance_id: str) -> Dict:
    """Get alliance information."""
    try:
        with open("alliances.json", "r") as f:
            alliances = json.load(f)
    except:
        return None
    
    return alliances.get(alliance_id)


def share_resources(
    sender_id: str, 
    receiver_name: str, 
    resource_type: str, 
    amount: int
) -> Tuple[bool, str]:
    """
    Share resources with alliance member.
    
    Both must be in same alliance.
    Sender must have resources.
    """
    sender = get_user(sender_id)
    if not sender:
        return False, "Sender not found"
    
    if resource_type not in ["wood", "bronze", "iron", "diamond", "relics"]:
        return False, f"Invalid resource: {resource_type}"
    
    if amount <= 0:
        return False, "Amount must be > 0"
    
    # Check sender is in an alliance
    sender_alliance = sender.get("alliance_id")
    if not sender_alliance:
        return False, "You're not in an alliance"
    
    # Find receiver by name
    try:
        from supabase_db import supabase, DB_TABLE
        r = supabase.table(DB_TABLE).select("user_id, username, alliance_id").ilike(
            "username", f"%{receiver_name}%"
        ).limit(1).execute()
        
        if not r.data:
            return False, f"Player '{receiver_name}' not found"
        
        receiver_id = r.data[0]["user_id"]
        receiver_display = r.data[0].get("username", receiver_name)
        receiver_alliance = r.data[0].get("alliance_id")
    except:
        return False, "Lookup failed"
    
    receiver = get_user(receiver_id)
    if not receiver:
        return False, "Receiver not found"
    
    # Check same alliance
    if receiver_alliance != sender_alliance:
        return False, "Target is not in your alliance"
    
    # Check sender has resources
    sender_res = sender.get("base_resources", {}).get("resources", {})
    have = sender_res.get(resource_type, 0)
    
    if have < amount:
        return False, f"You only have {have} {resource_type}"
    
    # Transfer resources
    sender_res[resource_type] = have - amount
    sender_base = sender.get("base_resources", {})
    sender_base["resources"] = sender_res
    sender["base_resources"] = sender_base
    
    receiver_res = receiver.get("base_resources", {}).get("resources", {})
    receiver_res[resource_type] = receiver_res.get(resource_type, 0) + amount
    receiver_base = receiver.get("base_resources", {})
    receiver_base["resources"] = receiver_res
    receiver["base_resources"] = receiver_base
    
    save_user(sender_id, sender)
    save_user(receiver_id, receiver)
    
    return True, f"✅ Sent {amount} {resource_type} to {receiver_display}"


def format_alliance_status(player_id: str) -> str:
    """Format alliance information."""
    player = get_user(player_id)
    if not player:
        return "Player not found"
    
    alliance_id = player.get("alliance_id")
    if not alliance_id:
        return "❌ You're not in an alliance\n\n" \
               "Use `!alliance create <name>` to create one\n" \
               "Or `!alliance join <id>` to join"
    
    alliance = get_alliance_info(alliance_id)
    if not alliance:
        return "❌ Alliance not found"
    
    lines = [
        f"👥 *{alliance['name']}*",
        f"👤 Leader: {alliance['leader_id']}",
        f"📊 Members: {len(alliance['members'])}/{MAX_ALLIANCE_SIZE}",
        f"💾 Treasury: {alliance['treasury']}",
    ]
    
    return "\n".join(lines)
