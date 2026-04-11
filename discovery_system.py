"""
discovery_system.py — Track first player discoveries in vault sectors

When a player is the first to mine/guess in a vault sector (60-64),
a special discovery is announced to the group and unlocked for all players.
"""

import json
from datetime import datetime
from typing import List, Dict

# File to track discoveries
DISCOVERIES_FILE = "discoveries.json"

def load_discoveries() -> Dict[int, Dict]:
    """Load discovery records from file."""
    try:
        with open(DISCOVERIES_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_discoveries(discoveries: Dict):
    """Save discovery records to file."""
    with open(DISCOVERIES_FILE, 'w') as f:
        json.dump(discoveries, f, indent=2)

def record_discovery(player_id: str, player_name: str, sector_id: int, resource_name: str) -> bool:
    """
    Record a discovery. Returns True if it's the FIRST discovery, False if already discovered.
    
    Args:
        player_id: User ID of discoverer
        player_name: Display name
        sector_id: Vault sector (60-64)
        resource_name: Resource discovered (e.g., "Gold", "Emerald")
    
    Returns:
        True if first discovery, False if already discovered
    """
    discoveries = load_discoveries()
    sector_key = str(sector_id)
    
    # Check if already discovered
    if sector_key in discoveries:
        return False  # Already discovered
    
    # Record new discovery
    discoveries[sector_key] = {
        "sector_id": sector_id,
        "resource": resource_name,
        "discovered_by_id": player_id,
        "discovered_by_name": player_name,
        "discovered_at": datetime.utcnow().isoformat(),
    }
    
    save_discoveries(discoveries)
    return True  # First discovery!

def get_discovery(sector_id: int) -> Dict | None:
    """Get discovery info for a sector (or None if not discovered)."""
    discoveries = load_discoveries()
    return discoveries.get(str(sector_id))

def is_discovered(sector_id: int) -> bool:
    """Check if a sector has been discovered."""
    return get_discovery(sector_id) is not None

def get_all_discoveries() -> List[Dict]:
    """Get all discoveries made so far."""
    discoveries = load_discoveries()
    return list(discoveries.values())

def format_discovery_announcement(player_name: str, resource_name: str, sector_id: int) -> str:
    """Format announcement message for a new discovery."""
    return (
        f"🔓 **VAULT UNLOCKED!** 🔓\n\n"
        f"@{player_name} has discovered {resource_name} in Sector {sector_id}!\n\n"
        f"The vault is now accessible to all players. Head to the sector to claim your rewards!\n\n"
        f"⭐ {player_name} has been awarded 1000 bonus XP and 500 Silver for the discovery!"
    )

# Example usage
if __name__ == "__main__":
    # Test recording a discovery
    if record_discovery("12345", "TestPlayer", 60, "Gold"):
        print("✅ Gold discovered in Sector 60!")
    else:
        print("⚠️  Gold already discovered")
    
    # Check discoveries
    print("\nAll discoveries:")
    for discovery in get_all_discoveries():
        print(f"  - {discovery['resource']} in Sector {discovery['sector_id']} "
              f"(by {discovery['discovered_by_name']} at {discovery['discovered_at']})")
