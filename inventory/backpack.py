from typing import List, Optional, Dict, Any
from .item import Item


class Backpack:
    """Standard 20-slot container carried in inventory or stored in warehouse."""

    def __init__(
        self,
        backpack_id: str,
        name: str = "Standard Backpack",
        max_slots: int = 20,
        is_trap: bool = False,
    ):
        self.backpack_id = backpack_id
        self.name = name
        self.max_slots = max_slots
        self.is_trap = is_trap
        self.slots: List[Optional[Dict[str, Any]]] = [None] * max_slots

    def add_item(self, item: Item, quantity: int = 1) -> bool:
        """Adds an item to the backpack. Rejects Crates."""
        if item.is_crate:
            return False  # Rule: Crates CANNOT go inside backpacks

        # 1. Try to stack with an existing item slot
        for slot in self.slots:
            if slot and slot["item"].item_id == item.item_id:
                if slot["quantity"] + quantity <= item.stack_limit:
                    slot["quantity"] += quantity
                    return True

        # 2. Look for an empty slot
        for i in range(len(self.slots)):
            if self.slots[i] is None:
                self.slots[i] = {"item": item, "quantity": quantity}
                return True

        return False  # Backpack is full

    def remove_item(self, slot_index: int, quantity: int = 1) -> Optional[Item]:
        """Removes a specified quantity from a slot index."""
        if slot_index < 0 or slot_index >= self.max_slots or not self.slots[slot_index]:
            return None

        slot = self.slots[slot_index]
        removed_item = slot["item"]

        if slot["quantity"] <= quantity:
            self.slots[slot_index] = None
        else:
            slot["quantity"] -= quantity

        return removed_item

    def on_looted(self, attacker: Any) -> Dict[str, Any]:
        """Triggered during a base raid if an attacker loots this backpack."""
        if self.is_trap:
            # Trap logic execution
            return {
                "triggered_trap": True,
                "message": f"💥 BOOM! {self.name} was rigged with explosives!",
            }
        return {"triggered_trap": False, "stolen": True}


class RiggedBackpack(Backpack):
    """Specifically crafted trap backpack designed as raid bait."""

    def __init__(self, backpack_id: str, explosion_damage: int = 150):
        super().__init__(
            backpack_id=backpack_id,
            name="Rigged Decoy Backpack",
            max_slots=0,  # Holds no real items—it IS the trap!
            is_trap=True,
        )
        self.explosion_damage = explosion_damage

    def on_looted(self, attacker: Any) -> Dict[str, Any]:
        return {
            "triggered_trap": True,
            "damage_dealt": self.explosion_damage,
            "message": f"💥 BOOM! Rigged Decoy exploded dealing {self.explosion_damage} casualties!",
        }