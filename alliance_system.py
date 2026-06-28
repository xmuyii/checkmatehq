"""
alliance_system.py — Player alliances with resource sharing

Mechanics:
  - Players can create or join alliances
  - Alliance members can share resources with each other
  - !share [resource] [amount] @member — Send resources to ally
"""

import json
from datetime import datetime, timedelta
from typing import Tuple, Dict, List
from supabase_db import get_user, save_user

# Max alliance size
MAX_ALLIANCE_SIZE = 50
HELP_REQUEST_INITIAL = {
    "build": 300,
    "research": 600,
}
HELP_REQUEST_REDUCTION = {
    "build": 120,
    "research": 180,
}


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
        "treasury": {"wood": 0, "bronze": 0, "iron": 0, "stone": 0, "relics": 0},
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
    
    if resource_type not in ["wood", "bronze", "iron", "stone", "relics"]:
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


def load_alliances() -> Dict[str, dict]:
    try:
        with open("alliances.json", "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_alliances(alliances: Dict[str, dict]) -> None:
    with open("alliances.json", "w") as f:
        json.dump(alliances, f, indent=2)


def get_alliance_help_requests(alliance_id: str) -> List[dict]:
    alliance = get_alliance_info(alliance_id)
    if not alliance:
        return []
    return alliance.get("help_requests", []) or []


def request_help(player_id: str, request_type: str) -> Tuple[bool, str]:
    """Create a help request for the player's build or research project."""
    user = get_user(player_id)
    if not user:
        return False, "Player not found"

    alliance_id = user.get("alliance_id")
    if not alliance_id:
        return False, "You're not in an alliance"

    alliances = load_alliances()
    alliance = alliances.get(alliance_id)
    if not alliance:
        return False, "Alliance not found"

    if request_type not in ("build", "research"):
        return False, "Invalid help request type"

    if request_type == "build":
        build_queue = user.get("building_queue", {}) or {}
        active_builds = [bid for bid, data in build_queue.items() if data.get("completion_time")]
        if not active_builds:
            return False, "No active building project to request help for"

        building_id = active_builds[0]
        build_info = build_queue[building_id]
        completion = build_info.get("completion_time")
        target = building_id
        description = f"Help finish {building_id.replace('_', ' ').title()}"
    else:
        researched = user.get("researches", {}) or {}
        pending = [
            "armor_plating", "speed_training", "resource_extraction",
            "population_growth", "trap_efficiency"
        ]
        pending_list = [name for name in pending if not researched.get(name)]
        if not pending_list:
            return False, "No pending research to request help for"
        target = pending_list[0]
        completion = (datetime.utcnow() + timedelta(seconds=HELP_REQUEST_INITIAL["research"]))
        description = f"Help research {target.replace('_', ' ').title()}"

    request_id = f"help_{int(datetime.utcnow().timestamp())}_{player_id[-4:]}"
    request = {
        "id": request_id,
        "requester_id": player_id,
        "requester_name": user.get("username", "Unknown"),
        "type": request_type,
        "target": target,
        "description": description,
        "created_at": datetime.utcnow().isoformat(),
        "completion_time": completion if isinstance(completion, str) else completion.isoformat(),
        "helpers": [],
    }

    if "help_requests" not in alliance:
        alliance["help_requests"] = []
    alliance["help_requests"].append(request)
    alliances[alliance_id] = alliance
    save_alliances(alliances)

    return True, f"Help request created for {target}. Alliance members can assist it."


def assist_help_request(helper_id: str, request_id: str) -> Tuple[bool, str]:
    """Assist an existing alliance help request and reduce its timer."""
    helper = get_user(helper_id)
    if not helper:
        return False, "Helper not found"

    alliance_id = helper.get("alliance_id")
    if not alliance_id:
        return False, "You're not in an alliance"

    alliances = load_alliances()
    alliance = alliances.get(alliance_id)
    if not alliance:
        return False, "Alliance not found"

    help_requests = alliance.get("help_requests", []) or []
    request = next((req for req in help_requests if req.get("id") == request_id), None)
    if not request:
        return False, "Help request not found"

    if request.get("requester_id") == helper_id:
        return False, "You cannot assist your own request"

    if helper_id in request.get("helpers", []):
        return False, "You already helped this request"

    reduction = HELP_REQUEST_REDUCTION.get(request.get("type"), 120)
    completion_time = datetime.fromisoformat(request["completion_time"])
    completion_time -= timedelta(seconds=reduction)
    request["helpers"].append(helper_id)
    request["completion_time"] = completion_time.isoformat()
    request["assists"] = request.get("assists", 0) + 1

    # Handle completion
    if completion_time <= datetime.utcnow():
        requester = get_user(request["requester_id"])
        if requester:
            if request["type"] == "build":
                try:
                    from building_queue import complete_building
                    complete_building(requester, request["target"])
                    save_user(request["requester_id"], requester)
                    result_text = f"{request['requester_name']}'s {request['target'].replace('_', ' ').title()} completed!"
                except Exception:
                    result_text = f"{request['requester_name']}'s building project is now ready."
            else:
                researches = requester.get("researches", {}) or {}
                researches[request["target"]] = True
                requester["researches"] = researches
                save_user(request["requester_id"], requester)
                result_text = f"{request['requester_name']}'s research {request['target'].replace('_', ' ').title()} completed!"
        else:
            result_text = "Help request completed."

        # Remove completed request
        help_requests = [req for req in help_requests if req.get("id") != request_id]
        alliance["help_requests"] = help_requests
        alliances[alliance_id] = alliance
        save_alliances(alliances)
        return True, result_text

    alliances[alliance_id] = alliance
    save_alliances(alliances)
    minutes = int(reduction / 60)
    return True, f"Help applied. Timer reduced by {minutes} minutes for {request['requester_name']}"
