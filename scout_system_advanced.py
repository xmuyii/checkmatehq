"""
🕵️ ENHANCED SCOUT SYSTEM - Intelligence & Deception
===================================================
Advanced scouting with:
- 5-minute travel time for scout rats
- 30% lying chance (false intel)
- MouseTrap defenses (70% escape rate)
- Fireball counter-items
- Fake stat editing system
"""

import random
from datetime import datetime, timedelta
from supabase_db import get_user, save_user

# ═══════════════════════════════════════════════════════════════════════════
#  SCOUT TRACKING SYSTEM
# ═══════════════════════════════════════════════════════════════════════════

def scout_player_advanced(scout_id: str, target_id: str, target_name: str) -> dict:
    """
    Launch a scout rat against target.
    
    Returns: {
        'success': bool,
        'message': str,
        'scout_id': str (unique ID for this scout mission),
        'started_at': ISO timestamp,
        'returns_at': ISO timestamp (5 minutes later),
        'status': 'pending' | 'completed' | 'killed' | 'escaped'
    }
    """
    scout_user = get_user(scout_id)
    target_user = get_user(target_id)
    
    if not scout_user or not target_user:
        return {
            "success": False,
            "message": "❌ Player not found"
        }
    
    # Cost check: 75 Silver per scout
    scout_silver = scout_user.get("silver", 0)
    if scout_silver < 75:
        return {
            "success": False,
            "message": f"❌ Scout costs 75 Silver. You have {scout_silver}."
        }
    
    # Deduct silver immediately
    scout_user["silver"] = scout_silver - 75
    
    # Create scout mission
    import uuid
    scout_mission_id = str(uuid.uuid4())
    
    now = datetime.utcnow()
    returns_at = now + timedelta(minutes=5)  # 5 minute round trip
    
    # Check if target has active firewall
    target_buffs = target_user.get("buffs", {})
    has_firewall = target_buffs.get("firewall_active", False)
    
    # Generate mission data
    mission = {
        "id": scout_mission_id,
        "scout_id": scout_id,
        "target_id": target_id,
        "target_name": target_name,
        "started_at": now.isoformat(),
        "returns_at": returns_at.isoformat(),
        "status": "pending",  # pending -> completed/killed/escaped
        "will_lie": random.random() < 0.30,  # 30% chance of lying
        "firewall_hit": has_firewall and random.random() < 0.50,  # 50% killed by firewall if active
        "trap_hit": False,  # Will be checked when scout returns
        "escaped_trap": False,  # Will be checked when scout returns
    }
    
    # Store scout mission
    if "active_scouts" not in scout_user:
        scout_user["active_scouts"] = []
    scout_user["active_scouts"].append(mission)
    
    save_user(scout_id, scout_user)
    
    # Notify target that they're being scouted
    if "incoming_scouts" not in target_user:
        target_user["incoming_scouts"] = []
    
    incoming_scout_notification = {
        "scout_id": scout_id,
        "scout_name": scout_user.get("username", "Unknown"),
        "arrived_at": returns_at.isoformat(),
        "mission_id": scout_mission_id,
    }
    target_user["incoming_scouts"].append(incoming_scout_notification)
    save_user(target_id, target_user)
    
    return {
        "success": True,
        "message": f"🐀 Scout rat sent to {target_name}'s base! Returns in 5 minutes.",
        "scout_id": scout_mission_id,
        "returns_at": returns_at.isoformat(),
    }


def check_scout_return(scout_id: str, mission_id: str) -> dict:
    """
    Check if scout mission is complete and get results.
    Called when player opens their scout results.
    """
    scout_user = get_user(scout_id)
    if not scout_user:
        return {"success": False, "message": "Scout not found"}
    
    # Find the mission
    active_scouts = scout_user.get("active_scouts", [])
    mission = next((s for s in active_scouts if s["id"] == mission_id), None)
    
    if not mission:
        return {"success": False, "message": "Scout mission not found"}
    
    # Check if time has passed
    try:
        returns_at = datetime.fromisoformat(mission["returns_at"])
    except:
        return {"success": False, "message": "Invalid scout data"}
    
    if datetime.utcnow() < returns_at:
        remaining = (returns_at - datetime.utcnow()).total_seconds()
        minutes = int(remaining // 60)
        seconds = int(remaining % 60)
        return {
            "success": False,
            "message": f"⏳ Scout still en route. Returns in {minutes}m {seconds}s",
            "status": "pending"
        }
    
    # Scout has returned! Process results
    target_id = mission["target_id"]
    target_user = get_user(target_id)
    
    if not target_user:
        return {"success": False, "message": "Target no longer exists"}
    
    # Determine final status
    if mission.get("firewall_hit"):
        mission["status"] = "killed"
        # Remove from active scouts
        scout_user["active_scouts"] = [s for s in active_scouts if s["id"] != mission_id]
        save_user(scout_id, scout_user)
        
        return {
            "success": False,
            "status": "killed",
            "message": f"💀 Your scout rat was INCINERATED by a fireball before reaching the base!\n"
                       f"The {mission['target_name']} has a firewall defense active.",
            "mission_id": mission_id,
        }
    
    # Check for mousetraps
    target_traps = target_user.get("traps", {})
    if "mousetrap" in target_traps and target_traps["mousetrap"] > 0:
        # Target has traps! Scout might escape
        if random.random() < 0.70:  # 70% escape rate
            mission["status"] = "escaped_trap"
            mission["escaped_trap"] = True
        else:
            mission["status"] = "captured"
            target_traps["mousetrap"] -= 1
            target_user["traps"] = target_traps
            save_user(target_id, target_user)
            
            # Remove from active scouts
            scout_user["active_scouts"] = [s for s in active_scouts if s["id"] != mission_id]
            save_user(scout_id, scout_user)
            
            return {
                "success": False,
                "status": "captured",
                "message": f"💀 Your scout rat was caught in a MOUSETRAP!\n"
                           f"The trap was set at {mission['target_name']}'s base.",
                "mission_id": mission_id,
            }
    
    # Scout succeeded! Get target's actual stats
    target_military = target_user.get("military", {})
    target_resources = target_user.get("base_resources", {}).get("resources", {})
    target_level = target_user.get("level", 1)
    target_shield = target_user.get("shield_status", "UNPROTECTED")
    
    # Check if target has fake stats set
    fake_stats = target_user.get("displayed_stats", {})
    
    # Determine what scout reports (actual or fake)
    if mission.get("will_lie"):
        # Generate fake data
        reported_data = generate_false_intel(target_military, target_resources, target_level)
        status_note = f"\n⚠️ *SCOUT INTEGRITY: QUESTIONABLE* ⚠️\nThis intel may contain lies (30% chance this scout is unreliable)"
    elif fake_stats.get("active") and random.random() < fake_stats.get("deception_chance", 0.8):
        # Use player's manually set fake stats
        reported_data = fake_stats.get("fake_data", {})
        status_note = f"\n💭 The base appears different than usual..."
    else:
        # Report actual data
        reported_data = {
            "military": target_military,
            "resources": target_resources,
            "level": target_level,
            "shield": target_shield,
        }
        status_note = ""
    
    mission["status"] = "completed"
    mission["reported_data"] = reported_data
    
    # Remove from active scouts and add to history
    scout_user["active_scouts"] = [s for s in active_scouts if s["id"] != mission_id]
    if "completed_scouts" not in scout_user:
        scout_user["completed_scouts"] = []
    scout_user["completed_scouts"].append(mission)
    save_user(scout_id, scout_user)
    
    # Format report
    report_msg = format_scout_report_advanced(mission, reported_data, status_note)
    
    return {
        "success": True,
        "status": "completed",
        "message": report_msg,
        "mission_id": mission_id,
        "intelligence": reported_data,
    }


def generate_false_intel(actual_military: dict, actual_resources: dict, actual_level: int) -> dict:
    """Generate false/lying scout data."""
    false_military = {}
    for unit, count in (actual_military or {}).items():
        # Vary by ±20-40%
        variance = random.uniform(0.6, 1.4)
        false_military[unit] = int(count * variance)
    
    false_resources = {}
    for res, amount in (actual_resources or {}).items():
        # Vary by ±25-50%
        variance = random.uniform(0.5, 1.5)
        false_resources[res] = int(amount * variance)
    
    false_level = actual_level + random.randint(-2, 3)  # Off by 2-3 levels
    
    return {
        "military": false_military,
        "resources": false_resources,
        "level": max(1, false_level),
        "shield": random.choice(["ACTIVE", "UNPROTECTED", "DISRUPTED"]),
    }


def format_scout_report_advanced(mission: dict, data: dict, note: str = "") -> str:
    """Format comprehensive scout report."""
    target_name = mission.get("target_name", "Unknown")
    scout_name = mission.get("scout_id", "Scout")
    
    txt = f"\n{'='*60}\n"
    txt += f"🕵️ *SCOUT REPORT* - {target_name}\n"
    txt += f"{'='*60}\n\n"
    
    txt += f"🐀 *Scout Mission:* Infiltration successful\n"
    txt += f"⏱️ *Duration:* 5 minutes (round trip)\n\n"
    
    # Military Intel
    military = data.get("military", {})
    if military:
        txt += f"⚔️ *MILITARY FORCES:*\n"
        total = 0
        for unit, count in military.items():
            txt += f"  • {unit.upper()}: {count}\n"
            total += count
        txt += f"  **TOTAL: {total} troops**\n\n"
    else:
        txt += f"⚔️ *MILITARY:* No troops detected\n\n"
    
    # Resources
    resources = data.get("resources", {})
    if resources:
        txt += f"💰 *BASE RESOURCES:*\n"
        for res, amount in resources.items():
            txt += f"  • {res.upper()}: {amount}\n"
        txt += "\n"
    
    # Shield Status
    shield = data.get("shield", "UNKNOWN")
    txt += f"🛡️ *SHIELD STATUS:* {shield}\n\n"
    
    # Level
    level = data.get("level", "?")
    txt += f"📊 *PLAYER LEVEL:* {level}\n"
    
    # Integrity warning if lied
    if note:
        txt += f"\n{note}\n"
    
    txt += f"\n{'='*60}\n"
    
    return txt


def set_displayed_stats(player_id: str, fake_stats: dict) -> bool:
    """
    Player sets custom fake stats to show to scouts.
    fake_stats = {
        'military': {...},
        'resources': {...},
        'level': X,
        'shield': '...',
        'deception_chance': 0.8  # 80% of scouts see fake stats
    }
    """
    user = get_user(player_id)
    if not user:
        return False
    
    # Validate structure
    required = ['military', 'resources', 'level', 'shield']
    if not all(k in fake_stats for k in required):
        return False
    
    # Store with deception chance
    user["displayed_stats"] = {
        "active": True,
        "fake_data": fake_stats,
        "deception_chance": fake_stats.get("deception_chance", 0.8),
        "set_at": datetime.utcnow().isoformat(),
    }
    
    save_user(player_id, user)
    return True


def clear_displayed_stats(player_id: str) -> bool:
    """Clear fake stats - scouts will see actual stats again."""
    user = get_user(player_id)
    if not user:
        return False
    
    user.pop("displayed_stats", None)
    save_user(player_id, user)
    return True


def set_mousetraps(player_id: str, trap_count: int) -> bool:
    """
    Player sets mousetraps to catch scout rats.
    Each active trap has 30% chance to catch incoming scout (70% escape).
    """
    user = get_user(player_id)
    if not user:
        return False
    
    if "traps" not in user:
        user["traps"] = {}
    
    user["traps"]["mousetrap"] = trap_count
    save_user(player_id, user)
    return True


def activate_firewall(player_id: str) -> bool:
    """
    Activate firewall defense.
    50% chance to incinerate incoming scout rats with fireball.
    """
    user = get_user(player_id)
    if not user:
        return False
    
    buffs = user.get("buffs", {})
    buffs["firewall_active"] = True
    buffs["firewall_expires"] = (datetime.utcnow() + timedelta(hours=1)).isoformat()
    user["buffs"] = buffs
    save_user(player_id, user)
    return True


def deactivate_firewall(player_id: str) -> bool:
    """Deactivate firewall."""
    user = get_user(player_id)
    if not user:
        return False
    
    buffs = user.get("buffs", {})
    buffs.pop("firewall_active", None)
    buffs.pop("firewall_expires", None)
    user["buffs"] = buffs
    save_user(player_id, user)
    return True


def check_scout_notifications(player_id: str) -> list:
    """Get list of incoming scouts targeting this player."""
    user = get_user(player_id)
    if not user:
        return []
    
    incoming = user.get("incoming_scouts", [])
    
    # Filter out scouts that have already arrived/completed
    now = datetime.utcnow()
    active_incoming = []
    
    for scout in incoming:
        try:
            arrived_at = datetime.fromisoformat(scout["arrived_at"])
            if now < arrived_at:
                remaining = (arrived_at - now).total_seconds()
                minutes = int(remaining // 60)
                scout["minutes_remaining"] = minutes
                active_incoming.append(scout)
        except:
            continue
    
    return active_incoming


def format_scout_notification(scout_notification: dict) -> str:
    """Format notification about incoming scout."""
    txt = f"\n⚠️ *INCOMING SCOUT ALERT* ⚠️\n"
    txt += f"👁️ From: {scout_notification.get('scout_name', 'Unknown')}\n"
    txt += f"⏱️ Arrives in: {scout_notification.get('minutes_remaining', '?')} minutes\n\n"
    txt += f"*OPTIONS:*\n"
    txt += f"🛡️ Set firewall defense (50% chance to incinerate)\n"
    txt += f"🪤 Set mousetraps (30% catch rate, but 70% escape)\n"
    txt += f"💭 Edit displayed stats (deceive the scout)\n"
    return txt
