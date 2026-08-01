"""
warehouse.py - Player Inventory and Warehouse Management System.
Handles item storage, stack limits, equipment, and database serialization.
"""

from typing import Dict, Any, Optional, List
from inventory.registry import ITEM_REGISTRY, WEAPONS


class Warehouse:
    def __init__(self, owner_id: str, capacity: int = 50):
        self.owner_id = owner_id
        self.capacity = capacity
        # Storage format: {item_id: {"qty": int, "type": "item" | "weapon"}}
        self.slots: Dict[str, Dict[str, Any]] = {}

    # ── Utility Helpers ──────────────────────────────────────────────────

    def _get_item_info(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Look up metadata from either registry."""
        if item_id in ITEM_REGISTRY:
            data = ITEM_REGISTRY[item_id].copy()
            data["_source"] = "item"
            return data
        elif item_id in WEAPONS:
            data = WEAPONS[item_id].copy()
            data["_source"] = "weapon"
            return data
        return None

    @property
    def used_slots(self) -> int:
        """Total distinct item slots currently used."""
        return len(self.slots)

    @property
    def is_full(self) -> bool:
        return self.used_slots >= self.capacity

    # ── Core Operations ──────────────────────────────────────────────────

    def add_item(self, item_id: str, amount: int = 1) -> bool:
        """
        Adds an item to the warehouse.
        Returns True on success, False if warehouse is full.
        """
        info = self._get_item_info(item_id)
        if not info:
            raise ValueError(f"Unknown item_id: '{item_id}'")

        if amount <= 0:
            return False

        # If it's a new item slot and we are at capacity, fail
        if item_id not in self.slots and self.is_full:
            return False

        if item_id in self.slots:
            self.slots[item_id]["qty"] += amount
        else:
            self.slots[item_id] = {
                "qty": amount,
                "type": info["_source"]
            }
        return True

    def remove_item(self, item_id: str, amount: int = 1) -> bool:
        """
        Removes a given amount of an item from the warehouse.
        Returns True on success, False if insufficient stock.
        """
        if item_id not in self.slots or self.slots[item_id]["qty"] < amount:
            return False

        self.slots[item_id]["qty"] -= amount

        # Clean up empty slots
        if self.slots[item_id]["qty"] <= 0:
            del self.slots[item_id]

        return True

    def has_item(self, item_id: str, amount: int = 1) -> bool:
        """Check if warehouse contains at least `amount` of item_id."""
        return self.slots.get(item_id, {}).get("qty", 0) >= amount

    def get_quantity(self, item_id: str) -> int:
        """Returns current quantity of a specific item."""
        return self.slots.get(item_id, {}).get("qty", 0)

    # ── Filtering & Views ────────────────────────────────────────────────

    def get_items_by_category(self, category: str) -> Dict[str, Dict[str, Any]]:
        """Returns all warehouse items matching a specific category."""
        filtered = {}
        for item_id, slot_data in self.slots.items():
            info = self._get_item_info(item_id)
            if info and info.get("category") == category:
                filtered[item_id] = {**slot_data, "metadata": info}
        return filtered

    def get_summary(self) -> List[Dict[str, Any]]:
        """Returns a formatted list of all items for UI/API responses."""
        summary = []
        for item_id, slot_data in self.slots.items():
            info = self._get_item_info(item_id)
            if info:
                summary.append({
                    "item_id": item_id,
                    "name": info.get("name", item_id),
                    "qty": slot_data["qty"],
                    "category": info.get("category", "general"),
                    "price": info.get("price", 0),
                    "currency": info.get("currency", "credits"),
                    "description": info.get("desc") or info.get("description", ""),
                })
        return summary

    # ── Serialization (Database Persistence) ────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Serialize state for database storage (e.g., Supabase JSONB)."""
        return {
            "owner_id": self.owner_id,
            "capacity": self.capacity,
            "slots": self.slots,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Warehouse":
        """Reconstruct Warehouse instance from database dictionary."""
        instance = cls(
            owner_id=data["owner_id"],
            capacity=data.get("capacity", 50)
        )
        instance.slots = data.get("slots", {})
        return instance