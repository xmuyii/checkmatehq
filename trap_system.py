# -*- coding: utf-8 -*-
"""
trap_system.py — Trap Building & Defense System
Traps scale with base level. Higher level bases can hold more traps.
"""

from typing import Dict, Tuple
import random

# ═══════════════════════════════════════════════════════════════════════════
#  TRAP TYPES & PROPERTIES
# ═══════════════════════════════════════════════════════════════════════════

TRAP_TYPES = {
    "spike_pit": {
        "name": "🕳️ SPIKE PIT",
        "description": "Weak traps. Damage: 10-20",
        "cost": {"bronze": 20, "wood": 50},
        "damage_range": (10, 20),
        "min_level": 1,
        "capacity": 5,
        "cooldown": 0,
    },
    "arrow_tower": {
        "name": "🏹 ARROW TOWER",
        "description": "Medium defense. Damage: 30-50",
        "cost": {"bronze": 50, "wood": 100, "iron": 20},
        "damage_range": (30, 50),
        "min_level": 3,
        "capacity": 4,
        "cooldown": 2,
    },
    "cannon": {
        "name": "🔫 CANNON",
        "description": "Heavy impact. Damage: 60-90",
        "cost": {"bronze": 100, "iron": 50, "wood": 150},
        "damage_range": (60, 90),
        "min_level": 5,
        "capacity": 3,
        "cooldown": 5,
    },
    "tesla_tower": {
        "name": "⚡ TESLA TOWER",
        "description": "Area damage. Damage: 80-120 (multiple targets)",
        "cost": {"iron": 75, "diamond": 10, "bronze": 100},
        "damage_range": (80, 120),
        "min_level": 7,
        "capacity": 2,
        "cooldown": 8,
    },
    "inferno": {
        "name": "🔥 INFERNO",
        "description": "Apocalyptic. Damage: 150-250 (all enemies)",
        "cost": {"diamond": 25, "iron": 100, "bronze": 150},
        "damage_range": (150, 250),
        "min_level": 9,
        "capacity": 1,
        "cooldown": 15,
    },
    "poison_gas": {
        "name": "☠️ POISON GAS",
        "description": "Lingering damage. Damage: 40-70 (over time)",
        "cost": {"bronze": 60, "iron": 30},
        "damage_range": (40, 70),
        "min_level": 4,
        "capacity": 4,
        "cooldown": 3,
    },
    "lava_moat": {
        "name": "🌋 LAVA MOAT",
        "description": "Perimeter defense. Damage: 50-80",
        "cost": {"iron": 40, "diamond": 5},
        "damage_range": (50, 80),
        "min_level": 6,
        "capacity": 3,
        "cooldown": 4,
    },
    "void_lattice": {
        "name": "🌑 VOID LATTICE",
        "description": "Cosmic barrier. Damage: 200-300",
        "cost": {"diamond": 50, "iron": 150},
        "damage_range": (200, 300),
        "min_level": 10,
        "capacity": 1,
        "cooldown": 20,
    },
}

# ═══════════════════════════════════════════════════════════════════════════
#  TRAP CAPACITY BY BASE LEVEL
# ═══════════════════════════════════════════════════════════════════════════

def get_max_traps(base_level: int) -> int:
    """Calculate max number of traps per type based on base level."""
    # Level 1: 2 traps
    # Level 5: 6 traps
    # Level 10: 12 traps
    return 2 + (base_level - 1) * 1


def get_available_traps(base_level: int) -> list:
    """Get all trap types available at this base level."""
    available = []
    for trap_id, trap_info in TRAP_TYPES.items():
        if trap_info["min_level"] <= base_level:
            available.append(trap_id)
    return available


def can_build_trap(trap_type: str, base_level: int) -> Tuple[bool, str]:
    """Check if a trap can be built at this base level."""
    if trap_type not in TRAP_TYPES:
        return False, f"❌ Unknown trap type: {trap_type}"
    
    trap = TRAP_TYPES[trap_type]
    if trap["min_level"] > base_level:
        return False, f"❌ Base level {base_level} too low. Need level {trap['min_level']} to build {trap['name']}"
    
    return True, "✅ Can build"


def calculate_trap_damage(trap_type: str, modifier: float = 1.0) -> int:
    """Calculate damage for a trap with optional modifier (e.g., from research)."""
    if trap_type not in TRAP_TYPES:
        return 0
    
    trap = TRAP_TYPES[trap_type]
    min_dmg, max_dmg = trap["damage_range"]
    base_damage = random.randint(min_dmg, max_dmg)
    return int(base_damage * modifier)


def format_trap_menu(base_level: int, current_traps: Dict[str, int]) -> str:
    """Format available traps for building."""
    available = get_available_traps(base_level)
    max_traps = get_max_traps(base_level)
    
    menu = f"""
╔════════════════════════════════════════════════════════════════╗
║          🏰  TRAP BUILDING SYSTEM  🏰                        ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║  Base Level: {base_level}                                               ║
║  Max Traps Per Type: {max_traps}                                         ║
║                                                                ║
╠════════════════════════════════════════════════════════════════╣
║  AVAILABLE TRAPS:                                              ║
║
"""
    
    for trap_id in available:
        trap = TRAP_TYPES[trap_id]
        current_count = current_traps.get(trap_id, 0)
        can_build = current_count < max_traps
        
        # Cost formatting
        cost_parts = []
        for res, amt in trap["cost"].items():
            cost_parts.append(f"{amt}{res[0].upper()}")
        cost_str = " + ".join(cost_parts)
        
        status = "✅ Can build" if can_build else "❌ At capacity"
        
        menu += f"║  {trap['name']:<25} | Built: {current_count}/{max_traps} | {status}\n"
        menu += f"║    Damage: {trap['damage_range'][0]}-{trap['damage_range'][1]} | Cost: {cost_str}\n"
        menu += f"║\n"
    
    menu += """║                                                                ║
║  Build: !build_trap [trap_name]                              ║
║  Example: !build_trap spike_pit                              ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
"""
    return menu


def format_trap_defense_report(traps_triggered: Dict[str, int], total_damage: int) -> str:
    """Format report of traps that triggered during defense."""
    if not traps_triggered:
        return "No traps triggered."
    
    report = "🎯 *TRAP DEFENSE ACTIVATED*\n\n"
    for trap_type, count in traps_triggered.items():
        if trap_type in TRAP_TYPES:
            trap = TRAP_TYPES[trap_type]
            report += f"{trap['name']} × {count}\n"
    
    report += f"\n💢 Total damage dealt: {total_damage}\n"
    return report
