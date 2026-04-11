"""
sectors_system.py — Sector definitions with unique buffs and multipliers

Each sector has:
- name: Display name
- emoji: Visual indicator
- buffs: Resource multipliers (x1.0 = normal, x4 = 4x, x0.5 = half)
- score_multiplier: Points per correct word (x1 = 10 pts, x2 = 20 pts)
- discovery: Unique resource when first found (sectors 60-64)
- hidden: If True, activity not announced to group
"""

SECTORS = {
    # ═══════════════════════════════════════════════════════════════
    # SECTOR 1-9: PUBLIC SECTORS (Activity announced)
    # ═══════════════════════════════════════════════════════════════
    
    1: {
        "name": "Badlands-8",
        "emoji": "🏜️",
        "resources": ["wood", "bronze"],
        "multiplier": 1.0,
        "buffs": {
            "iron": 4.0,        # x4 iron gain
            "wood": 0.5,        # -50% wood (halved)
            "score": 1.0,       # Normal points
        },
        "discovery": None,
        "hidden": False,
    },
    
    2: {
        "name": "Crimson Wastes",
        "emoji": "🔴",
        "resources": ["bronze", "iron"],
        "multiplier": 1.2,
        "buffs": {
            "food": 10.0,       # x10 food gain
            "bronze": 0.8,      # -20% bronze
            "score": 1.0,
        },
        "discovery": None,
        "hidden": False,
    },
    
    3: {
        "name": "Obsidian Peaks",
        "emoji": "⛰️",
        "resources": ["iron", "diamond"],
        "multiplier": 1.5,
        "buffs": {
            "diamond": 2.0,     # x2 diamond
            "xp": 0.0,          # No XP gained (only resources)
            "score": 2.0,       # x2 points per word!
        },
        "discovery": None,
        "hidden": False,
    },
    
    4: {
        "name": "Shattered Valley",
        "emoji": "💔",
        "resources": ["bronze", "wood", "iron"],
        "multiplier": 1.0,
        "buffs": {
            "bronze": 5.0,      # x5 bronze
            "relics": 0.1,      # -90% relics (very rare)
            "score": 1.5,       # x1.5 points
        },
        "discovery": None,
        "hidden": False,
    },
    
    5: {
        "name": "Frozen Abyss",
        "emoji": "❄️",
        "resources": ["iron", "diamond"],
        "multiplier": 1.8,
        "buffs": {
            "diamond": 3.0,     # x3 diamond
            "xp": 0.5,          # -50% XP
            "score": 1.2,
        },
        "discovery": None,
        "hidden": False,
    },
    
    6: {
        "name": "Molten Gorge",
        "emoji": "🔥",
        "resources": ["diamond", "relics"],
        "multiplier": 2.0,
        "buffs": {
            "relics": 2.0,      # x2 relics
            "food": 0.1,        # -90% food
            "score": 1.8,       # x1.8 points
        },
        "discovery": None,
        "hidden": False,
    },
    
    7: {
        "name": "Twilight Marshes",
        "emoji": "🌙",
        "resources": ["wood", "relics"],
        "multiplier": 1.3,
        "buffs": {
            "wood": 8.0,        # x8 wood gain
            "iron": 0.5,        # -50% iron
            "score": 1.0,
        },
        "discovery": None,
        "hidden": False,
    },
    
    8: {
        "name": "Silent Forest",
        "emoji": "🌲",
        "resources": ["wood", "bronze", "diamond"],
        "multiplier": 1.4,
        "buffs": {
            "bronze": 6.0,      # x6 bronze
            "silver": -1.0,     # Lose silver (cursed)
            "score": 1.3,
        },
        "discovery": None,
        "hidden": False,
    },
    
    9: {
        "name": "Void Canyon",
        "emoji": "🌑",
        "resources": ["relics", "diamond", "iron"],
        "multiplier": 2.0,
        "buffs": {
            "all": 1.0,         # Neutral - all normal
            "score": 2.5,       # x2.5 points (high reward!)
        },
        "discovery": None,
        "hidden": False,
    },
    
    # ═══════════════════════════════════════════════════════════════
    # SECTORS 10-59: HIDDEN SECTORS (Activity never announced)
    # ═══════════════════════════════════════════════════════════════
    
    **{
        i: {
            "name": f"Hidden Sector {i}",
            "emoji": "🔒",
            "resources": ["wood", "bronze", "iron", "diamond", "relics"],
            "multiplier": 1.0 + (i % 5) * 0.2,  # Varied multipliers
            "buffs": {
                "score": 1.0 + (i % 3) * 0.5,  # Some have score bonuses
            },
            "discovery": None,
            "hidden": True,  # ← Activity not announced
        }
        for i in range(10, 60)
    },
    
    # ═══════════════════════════════════════════════════════════════
    # SECTORS 60-64: VAULT SECTORS (Special discoveries announced!)
    # ═══════════════════════════════════════════════════════════════
    
    60: {
        "name": "Golden Vault",
        "emoji": "🏆",
        "resources": ["relics", "diamond"],
        "multiplier": 3.0,
        "buffs": {
            "relics": 5.0,      # x5 relics!
            "score": 3.0,       # x3 points
        },
        "discovery": "Gold",    # First to find announces: "Gold discovered!"
        "hidden": False,        # Activity announced
    },
    
    61: {
        "name": "Emerald Chamber",
        "emoji": "💚",
        "resources": ["diamond", "relics"],
        "multiplier": 2.8,
        "buffs": {
            "diamond": 5.0,     # x5 diamond
            "score": 2.8,
        },
        "discovery": "Emerald",
        "hidden": False,
    },
    
    62: {
        "name": "Platinum Mines",
        "emoji": "⚪",
        "resources": ["iron", "relics"],
        "multiplier": 3.2,
        "buffs": {
            "iron": 6.0,        # x6 iron
            "score": 3.2,
        },
        "discovery": "Platinum",
        "hidden": False,
    },
    
    63: {
        "name": "Diamond Cathedral",
        "emoji": "💎",
        "resources": ["diamond"],
        "multiplier": 4.0,
        "buffs": {
            "diamond": 10.0,    # x10 diamond
            "score": 4.0,
        },
        "discovery": "Diamond",
        "hidden": False,
    },
    
    64: {
        "name": "Relic Vault",
        "emoji": "🏺",
        "resources": ["relics"],
        "multiplier": 5.0,
        "buffs": {
            "relics": 20.0,     # x20 relics!!!
            "score": 5.0,       # x5 points
        },
        "discovery": "Relic Vault",
        "hidden": False,
    },
}


def get_sector_info(sector_id: int) -> dict:
    """Get sector info, return sector 1 as fallback."""
    return SECTORS.get(sector_id, SECTORS[1])


def apply_sector_buffs(resources: dict, sector_id: int) -> dict:
    """
    Apply sector buffs to resource drops.
    
    Args:
        resources: {"wood": 10, "bronze": 5, ...}
        sector_id: Sector number
    
    Returns:
        Buffed resources
    """
    sector = get_sector_info(sector_id)
    buffs = sector.get("buffs", {})
    buffed = dict(resources)
    
    for resource, amount in buffed.items():
        if resource in buffs:
            multiplier = buffs[resource]
            buffed[resource] = max(0, int(amount * multiplier))
        elif "all" in buffs:
            multiplier = buffs["all"]
            buffed[resource] = max(0, int(amount * multiplier))
    
    return buffed


def get_score_multiplier(sector_id: int) -> float:
    """Get points multiplier for a sector (default 1.0 = 10 pts per word)."""
    sector = get_sector_info(sector_id)
    return sector.get("buffs", {}).get("score", 1.0)


def get_discovery(sector_id: int) -> str | None:
    """Get discovery resource name (or None if not a vault sector)."""
    sector = get_sector_info(sector_id)
    return sector.get("discovery")


def is_hidden_sector(sector_id: int) -> bool:
    """Check if sector activity should be hidden from group."""
    sector = get_sector_info(sector_id)
    return sector.get("hidden", False)


def is_vault_sector(sector_id: int) -> bool:
    """Check if sector is a vault (60-64) with special discovery."""
    return 60 <= sector_id <= 64


def get_public_sectors() -> list:
    """Get sectors whose activity is announced (1-9, 60-64)."""
    return list(range(1, 10)) + list(range(60, 65))


# Example usage
if __name__ == "__main__":
    print("SECTOR INFORMATION:\n")
    
    for sid in [1, 3, 5, 9, 60, 64]:
        sector = get_sector_info(sid)
        print(f"{sector['emoji']} Sector {sid}: {sector['name']}")
        print(f"   Buffs: {sector['buffs']}")
        print(f"   Discovery: {sector.get('discovery', 'None')}")
        print(f"   Hidden: {sector.get('hidden', False)}")
        print()
    
    print("\nTesting buff application:")
    test_resources = {"wood": 10, "bronze": 5, "iron": 8}
    print(f"Original: {test_resources}")
    print(f"Sector 3 (x4 Iron): {apply_sector_buffs(test_resources, 3)}")
    print(f"Sector 6 (x2 Relics, -90% Food): {apply_sector_buffs({'relics': 2, 'food': 20}, 6)}")
