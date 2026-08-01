"""
equipment.py - Manages active gear, weapons, shields, and active combat cooldowns.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from inventory.registry import ITEM_REGISTRY, WEAPONS
from inventory.warehouse import Warehouse


class EquipmentManager:
    SLOT_LIMITS = {
        "weapon": 2,
        "shield": 1,
        "protection": 1,
    }

    def __init__(self, owner_id: str, warehouse: Warehouse):
        self.owner_id = owner_id
        self.warehouse = warehouse
        self.equipped: Dict[str, list] = {
            "weapon": [],
            "shield": [],
            "protection": []
        }
        # Tracks weapon cooldown timestamps ISO format: {"plasma_cannon": "2026-07-28T10:00:00+00:00"}
        self.cooldowns: Dict[str, str] = {}

    def _resolve_slot_type(self, item_id: str, metadata: Dict[str, Any]) -> Optional[str]:
        if item_id in WEAPONS or metadata.get("category") == "weapon":
            return "weapon"
        category = metadata.get("category")
        if category in ("shield", "protection"):
            return category
        return None

    def equip_item(self, item_id: str, player_level: int = 1) -> Dict[str, Any]:
        metadata = self.warehouse._get_item_info(item_id)
        if not metadata:
            return {"success": False, "reason": f"Unknown item '{item_id}'."}

        min_lvl = metadata.get("min_level", 1)
        if player_level < min_lvl:
            return {
                "success": False, 
                "reason": f"Requires Level {min_lvl} (Current: Level {player_level})."
            }

        slot_type = self._resolve_slot_type(item_id, metadata)
        if not slot_type or slot_type not in self.SLOT_LIMITS:
            return {"success": False, "reason": f"Item '{item_id}' is not equippable."}

        current_equipped = self.equipped[slot_type]
        max_allowed = self.SLOT_LIMITS[slot_type]

        if len(current_equipped) >= max_allowed:
            return {
                "success": False, 
                "reason": f"All {slot_type} slots are full ({len(current_equipped)}/{max_allowed})."
            }

        if not self.warehouse.has_item(item_id, 1):
            return {"success": False, "reason": "Item not present in warehouse."}

        self.warehouse.remove_item(item_id, 1)
        self.equipped[slot_type].append(item_id)

        return {
            "success": True, 
            "message": f"Equipped {metadata.get('name', item_id)}.",
            "slot_type": slot_type
        }

    def unequip_item(self, item_id: str) -> Dict[str, Any]:
        metadata = self.warehouse._get_item_info(item_id)
        slot_type = self._resolve_slot_type(item_id, metadata or {})

        if not slot_type or item_id not in self.equipped.get(slot_type, []):
            return {"success": False, "reason": "Item is not currently equipped."}

        if self.warehouse.is_full and item_id not in self.warehouse.slots:
            return {"success": False, "reason": "Warehouse is full! Cannot unequip item."}

        self.equipped[slot_type].remove(item_id)
        self.warehouse.add_item(item_id, 1)

        return {
            "success": True, 
            "message": f"Unequipped {metadata.get('name', item_id)} back to warehouse."
        }

    # ── Cooldown Mechanics ───────────────────────────────────────────────

    def get_weapon_cooldown_status(self, weapon_id: str) -> Dict[str, Any]:
        """
        Checks if an equipped weapon is ready or on cooldown.
        Returns remaining time details.
        """
        w_data = WEAPONS.get(weapon_id)
        if not w_data:
            return {"is_ready": False, "reason": "Unknown weapon."}

        cooldown_hours = w_data.get("cooldown_hours", 0)
        last_used_str = self.cooldowns.get(weapon_id)

        # If it was never used, it's ready
        if not last_used_str or cooldown_hours <= 0:
            return {"is_ready": True, "remaining_seconds": 0, "remaining_formatted": "Ready"}

        last_used = datetime.fromisoformat(last_used_str)
        now = datetime.now(timezone.utc)
        ready_at = last_used + timedelta(hours=cooldown_hours)

        if now >= ready_at:
            return {"is_ready": True, "remaining_seconds": 0, "remaining_formatted": "Ready"}

        time_left = ready_at - now
        total_seconds = int(time_left.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        return {
            "is_ready": False,
            "remaining_seconds": total_seconds,
            "remaining_formatted": f"{hours}h {minutes}m {seconds}s",
            "ready_at": ready_at.isoformat()
        }

    def trigger_weapon(self, weapon_id: str) -> Dict[str, Any]:
        """
        Attempts to discharge an equipped weapon. On success, sets the cooldown timestamp.
        """
        if weapon_id not in self.equipped["weapon"]:
            return {"success": False, "reason": "Weapon is not equipped."}

        status = self.get_weapon_cooldown_status(weapon_id)
        if not status["is_ready"]:
            return {
                "success": False,
                "reason": f"Weapon on cooldown! Ready in {status['remaining_formatted']}."
            }

        # Set new timestamp to current UTC time
        now = datetime.now(timezone.utc)
        self.cooldowns[weapon_id] = now.isoformat()

        w_data = WEAPONS.get(weapon_id, {})
        return {
            "success": True,
            "message": f"Fired {w_data.get('name', weapon_id)}!",
            "effect": w_data.get("effect"),
            "cooldown_hours": w_data.get("cooldown_hours", 0)
        }

    # ── Active Combat Loadout Inspection ──────────────────────────────────

    def get_active_combat_stats(self) -> Dict[str, Any]:
        """
        Gathers equipped loadout along with live cooldown availability.
        """
        active_weapons = []
        damage_reduction = 0.0

        for w_id in self.equipped["weapon"]:
            w_data = WEAPONS.get(w_id, {})
            cd_info = self.get_weapon_cooldown_status(w_id)
            
            active_weapons.append({
                "id": w_id,
                "name": w_data.get("name"),
                "effect": w_data.get("effect"),
                "cooldown_hours": w_data.get("cooldown_hours", 0),
                "is_ready": cd_info["is_ready"],
                "cooldown_remaining": cd_info["remaining_formatted"]
            })

        for s_id in self.equipped["shield"]:
            s_data = ITEM_REGISTRY.get(s_id, {})
            effect_str = s_data.get("effect", "")
            if "25%" in effect_str:
                damage_reduction += 0.25
            elif "50%" in effect_str:
                damage_reduction += 0.50
            elif "10%" in effect_str:
                damage_reduction += 0.10

        return {
            "active_weapons": active_weapons,
            "damage_reduction": min(damage_reduction, 0.75),
            "protection_suits": self.equipped["protection"]
        }

    # ── Persistence ──────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "owner_id": self.owner_id,
            "equipped": self.equipped,
            "cooldowns": self.cooldowns
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], warehouse: Warehouse) -> "EquipmentManager":
        manager = cls(owner_id=data["owner_id"], warehouse=warehouse)
        manager.equipped = data.get("equipped", {"weapon": [], "shield": [], "protection": []})
        manager.cooldowns = data.get("cooldowns", {})
        return manager