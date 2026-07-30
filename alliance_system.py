"""
alliance_system.py — Player alliances with resource sharing
=============================================================
Backed by a proper Supabase `alliances` table (see migration SQL in
project notes) instead of a local alliances.json file. The old file-based
version was a real risk: no backup, no concurrency safety, and wiped on
any redeploy with an ephemeral filesystem.
"""

from datetime import datetime, timedelta
from typing import Tuple, Dict, List, Optional
from supabase_db import get_user, save_user, supabase, DB_TABLE

ALLIANCE_TABLE = "alliances"

MAX_ALLIANCE_SIZE = 50
HELP_REQUEST_INITIAL = {
    "build": 300,
    "research": 600,
}
HELP_REQUEST_REDUCTION = {
    "build": 120,
    "research": 180,
}

DEFAULT_TREASURY = {"gold": 0, "wood": 0, "bronze": 0, "iron": 0, "stone": 0, "relics": 0}


# ═══════════════════════════════════════════════════════════════════════════
#  RAW DB HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def get_alliance_info(alliance_id: str) -> Optional[dict]:
    """Fetch one alliance row from Supabase."""
    if not alliance_id:
        return None
    try:
        r = supabase.table(ALLIANCE_TABLE).select("*").eq("alliance_id", alliance_id).execute()
        return r.data[0] if r.data else None
    except Exception as e:
        print(f"[ALLIANCE ERROR] get_alliance_info: {e}")
        return None


def save_alliance(alliance: dict) -> bool:
    """Upsert a full alliance row back to Supabase."""
    try:
        supabase.table(ALLIANCE_TABLE).update(alliance).eq(
            "alliance_id", alliance["alliance_id"]
        ).execute()
        return True
    except Exception as e:
        print(f"[ALLIANCE ERROR] save_alliance: {e}")
        return False


def find_alliance_by_name(name: str) -> Optional[dict]:
    try:
        r = supabase.table(ALLIANCE_TABLE).select("*").ilike("name", name).limit(1).execute()
        return r.data[0] if r.data else None
    except Exception as e:
        print(f"[ALLIANCE ERROR] find_alliance_by_name: {e}")
        return None


def list_alliances(limit: int = 15) -> List[dict]:
    """
    Browse existing alliances, largest/most active first. This is the
    missing discovery step — join_alliance() requires an alliance_id,
    but nothing previously let a player find one without being told it
    by another player directly.
    """
    try:
        r = (
            supabase.table(ALLIANCE_TABLE)
            .select("alliance_id, name, members, max_size, alliance_points")
            .order("alliance_points", desc=True)
            .limit(limit)
            .execute()
        )
        return r.data or []
    except Exception as e:
        print(f"[ALLIANCE ERROR] list_alliances: {e}")
        return []


def search_alliances(query: str, limit: int = 10) -> List[dict]:
    """Partial, case-insensitive name search — unlike find_alliance_by_name,
    which only ever returns a single exact match."""
    if not query or len(query.strip()) < 2:
        return []
    try:
        r = (
            supabase.table(ALLIANCE_TABLE)
            .select("alliance_id, name, members, max_size, alliance_points")
            .ilike("name", f"%{query.strip()}%")
            .limit(limit)
            .execute()
        )
        return r.data or []
    except Exception as e:
        print(f"[ALLIANCE ERROR] search_alliances: {e}")
        return []


def format_alliance_browse_list(alliances: List[dict]) -> str:
    """Render a list_alliances()/search_alliances() result as display text."""
    if not alliances:
        return "🔍 No alliances found."
    lines = ["🏰 *ALLIANCES*", "━━━━━━━━━━━━━━━━━"]
    for a in alliances:
        members = a.get("members", []) or []
        count    = len(members)
        cap      = a.get("max_size", MAX_ALLIANCE_SIZE)
        pts      = a.get("alliance_points", 0)
        full_tag = " (FULL)" if count >= cap else ""
        lines.append(
            f"*{a.get('name','?')}*{full_tag}\n"
            f"  👥 {count}/{cap} members · 🏆 {pts:,} pts\n"
            f"  ID: `{a.get('alliance_id','?')}`"
        )
    lines.append("\nUse `!alliance join <id>` to join one, or tap below 👇")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
#  CORE ACTIONS
# ═══════════════════════════════════════════════════════════════════════════

def create_alliance(leader_id: str, alliance_name: str) -> Tuple[bool, str]:
    """Create a new alliance. Leader becomes the founder."""
    leader = get_user(leader_id)
    if not leader:
        return False, "Player not found"

    if leader.get("alliance_id"):
        return False, "Already in an alliance"

    if len(alliance_name) < 3 or len(alliance_name) > 20:
        return False, "Alliance name must be 3-20 characters"

    if find_alliance_by_name(alliance_name):
        return False, "That alliance name is already taken"

    alliance_id = f"alliance_{int(datetime.utcnow().timestamp())}"

    alliance_row = {
        "alliance_id":     alliance_id,
        "name":            alliance_name,
        "leader_id":       leader_id,
        "members":         [leader_id],
        "member_roles":    {leader_id: "LEADER"},
        "treasury":        DEFAULT_TREASURY.copy(),
        "help_requests":   [],
        "shop_stock":      {},
        "alliance_points": 0,
        "max_size":        MAX_ALLIANCE_SIZE,
        "created_at":      datetime.utcnow().isoformat(),
    }

    try:
        supabase.table(ALLIANCE_TABLE).insert(alliance_row).execute()
    except Exception as e:
        print(f"[ALLIANCE ERROR] create_alliance insert: {e}")
        return False, "❌ Failed to create alliance (DB error)."

    leader["alliance_id"]   = alliance_id
    leader["alliance_role"] = "LEADER"
    save_user(leader_id, leader)

    return True, f"✅ Alliance '{alliance_name}' created!"


def join_alliance(player_id: str, alliance_id: str) -> Tuple[bool, str]:
    """Join an existing alliance."""
    player = get_user(player_id)
    if not player:
        return False, "Player not found"

    if player.get("alliance_id"):
        return False, "Already in an alliance"

    alliance = get_alliance_info(alliance_id)
    if not alliance:
        return False, "Alliance not found"

    members = alliance.get("members", []) or []
    if len(members) >= alliance.get("max_size", MAX_ALLIANCE_SIZE):
        return False, f"Alliance is full ({alliance.get('max_size', MAX_ALLIANCE_SIZE)} members)"

    if player_id in members:
        return False, "Already a member"

    members.append(player_id)
    roles = alliance.get("member_roles", {}) or {}
    roles[player_id] = "MEMBER"

    alliance["members"]      = members
    alliance["member_roles"] = roles
    if not save_alliance(alliance):
        return False, "❌ Failed to join (DB error)."

    player["alliance_id"]   = alliance_id
    player["alliance_role"] = "MEMBER"
    save_user(player_id, player)

    return True, f"✅ Joined alliance '{alliance['name']}'"


def leave_alliance(player_id: str) -> Tuple[bool, str]:
    """Leave current alliance. Leaders must transfer or disband first."""
    player = get_user(player_id)
    if not player:
        return False, "Player not found"

    alliance_id = player.get("alliance_id")
    if not alliance_id:
        return False, "You're not in an alliance"

    alliance = get_alliance_info(alliance_id)
    if alliance and alliance.get("leader_id") == player_id:
        return False, "❌ Leaders must transfer leadership or disband the alliance first."

    if alliance:
        members = [m for m in alliance.get("members", []) if m != player_id]
        roles   = alliance.get("member_roles", {}) or {}
        roles.pop(player_id, None)
        alliance["members"]      = members
        alliance["member_roles"] = roles
        save_alliance(alliance)

    player["alliance_id"]   = None
    player["alliance_role"] = None
    save_user(player_id, player)

    return True, "✅ You have left the alliance."


def get_alliance_members(alliance_id: str) -> List[str]:
    """Return the list of member user_ids for an alliance."""
    alliance = get_alliance_info(alliance_id)
    if not alliance:
        return []
    return alliance.get("members", []) or []


# ═══════════════════════════════════════════════════════════════════════════
#  RESOURCE SHARING (already correct — uses base_resources directly)
# ═══════════════════════════════════════════════════════════════════════════

def share_resources(
    sender_id: str,
    receiver_name: str,
    resource_type: str,
    amount: int
) -> Tuple[bool, str]:
    """Share resources with alliance member. Both must be in same alliance."""
    sender = get_user(sender_id)
    if not sender:
        return False, "Sender not found"

    if resource_type not in ["wood", "bronze", "iron", "stone", "relics"]:
        return False, f"Invalid resource: {resource_type}"

    if amount <= 0:
        return False, "Amount must be > 0"

    sender_alliance = sender.get("alliance_id")
    if not sender_alliance:
        return False, "You're not in an alliance"

    try:
        r = supabase.table(DB_TABLE).select("user_id, username, alliance_id").ilike(
            "username", f"%{receiver_name}%"
        ).limit(1).execute()

        if not r.data:
            return False, f"Player '{receiver_name}' not found"

        receiver_id      = r.data[0]["user_id"]
        receiver_display = r.data[0].get("username", receiver_name)
        receiver_alliance = r.data[0].get("alliance_id")
    except Exception:
        return False, "Lookup failed"

    receiver = get_user(receiver_id)
    if not receiver:
        return False, "Receiver not found"

    if receiver_alliance != sender_alliance:
        return False, "Target is not in your alliance"

    from build_system import clamp_resource_add
    sender_res = sender.get("base_resources", {}).get("resources", {})
    have = sender_res.get(resource_type, 0)

    if have < amount:
        return False, f"You only have {have} {resource_type}"

    sender_res[resource_type] = have - amount
    sender_base = sender.get("base_resources", {})
    sender_base["resources"] = sender_res
    sender["base_resources"] = sender_base

    clamp_resource_add(receiver, resource_type, amount)

    save_user(sender_id, sender)
    save_user(receiver_id, receiver)

    return True, f"✅ Sent {amount} {resource_type} to {receiver_display}"


# ═══════════════════════════════════════════════════════════════════════════
#  DISPLAY
# ═══════════════════════════════════════════════════════════════════════════

def format_alliance_status(player_id: str) -> str:
    """Format alliance information."""
    player = get_user(player_id)
    if not player:
        return "Player not found"

    alliance_id = player.get("alliance_id")
    if not alliance_id:
        return ("❌ You're not in an alliance\n\n"
                "Create an alliance below\n"
                "Or join an existing one")

    alliance = get_alliance_info(alliance_id)
    if not alliance:
        return "❌ Alliance not found"

    members = alliance.get("members", []) or []
    treasury = alliance.get("treasury", {}) or {}
    treasury_line = ", ".join(f"{k}: {v}" for k, v in treasury.items())

    lines = [
        f"👥 *{alliance['name']}*",
        f"👤 Leader: {alliance['leader_id']}",
        f"📊 Members: {len(members)}/{alliance.get('max_size', MAX_ALLIANCE_SIZE)}",
        f"🏆 Alliance Points: {alliance.get('alliance_points', 0):,}",
        f"💾 Treasury: {treasury_line}",
    ]

    return "\n".join(lines)


def get_alliance_summary_line(user: dict) -> str:
    """
    One-line alliance summary for the main dashboard HUD.
    Returns empty string if not in an alliance (dashboard should skip it).
    """
    alliance_id = user.get("alliance_id")
    if not alliance_id:
        return ""
    alliance = get_alliance_info(alliance_id)
    if not alliance:
        return ""
    members = alliance.get("members", []) or []
    return f"👥 {alliance['name']} ({len(members)}/{alliance.get('max_size', MAX_ALLIANCE_SIZE)})"


# ═══════════════════════════════════════════════════════════════════════════
#  HELP REQUESTS
# ═══════════════════════════════════════════════════════════════════════════

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

    alliance = get_alliance_info(alliance_id)
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
        build_info  = build_queue[building_id]
        completion  = build_info.get("completion_time")
        target      = building_id
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
        target      = pending_list[0]
        completion  = (datetime.utcnow() + timedelta(seconds=HELP_REQUEST_INITIAL["research"]))
        description = f"Help research {target.replace('_', ' ').title()}"

    request_id = f"help_{int(datetime.utcnow().timestamp())}_{player_id[-4:]}"
    request = {
        "id":              request_id,
        "requester_id":    player_id,
        "requester_name":  user.get("username", "Unknown"),
        "type":            request_type,
        "target":          target,
        "description":     description,
        "created_at":      datetime.utcnow().isoformat(),
        "completion_time": completion if isinstance(completion, str) else completion.isoformat(),
        "helpers":         [],
    }

    help_requests = alliance.get("help_requests", []) or []
    help_requests.append(request)
    alliance["help_requests"] = help_requests
    save_alliance(alliance)

    return True, f"Help request created for {target}. Alliance members can assist it."


def assist_help_request(helper_id: str, request_id: str) -> Tuple[bool, str]:
    """Assist an existing alliance help request and reduce its timer."""
    helper = get_user(helper_id)
    if not helper:
        return False, "Helper not found"

    alliance_id = helper.get("alliance_id")
    if not alliance_id:
        return False, "You're not in an alliance"

    alliance = get_alliance_info(alliance_id)
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

    if completion_time <= datetime.utcnow():
        requester = get_user(request["requester_id"])
        if requester:
            if request["type"] == "build":
                try:
                    from building_queue import complete_building
                    requester = complete_building(requester, request["target"])
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

        help_requests = [req for req in help_requests if req.get("id") != request_id]
        alliance["help_requests"] = help_requests
        save_alliance(alliance)
        return True, result_text

    save_alliance(alliance)
    minutes = int(reduction / 60)
    return True, f"Help applied. Timer reduced by {minutes} minutes for {request['requester_name']}"