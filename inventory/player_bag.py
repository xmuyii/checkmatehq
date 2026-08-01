# inventory/player_bag.py

from typing import List, Optional, Dict, Any
from .item import Item, ItemCategory
from .backpack import Backpack


class PlayerBag:
    """
    Active 5-slot personal inventory always accessible by the player anywhere on the map.
    Can hold raw Items, Crates, or full Backpacks.
    """

    def __init__(self, owner_id: int, max_slots: int = 5):
        self.owner_id = owner_id
        self.max_slots = max_slots
        # Slots store dicts: {"type": "item"|"backpack", "object": Item|Backpack, "quantity": int}
        self.slots: List[Optional[Dict[str, Any]]] = [None] * max_slots

    def add_item(self, item: Item, quantity: int = 1) -> bool:
        """Adds a standard item or crate to personal inventory."""
        # 1. Stacking check
        for slot in self.slots:
            if slot and slot["type"] == "item":
                current_item: Item = slot["object"]
                if current_item.item_id == item.item_id:
                    if slot["quantity"] + quantity <= item.stack_limit:
                        slot["quantity"] += quantity
                        return True

        # 2. Empty slot check
        for i in range(self.max_slots):
            if self.slots[i] is None:
                self.slots[i] = {"type": "item", "object": item, "quantity": quantity}
                return True

        return False  # Inventory full

    def add_backpack(self, backpack: Backpack) -> bool:
        """Carries a physical backpack in one of the 5 personal inventory slots."""
        for i in range(self.max_slots):
            if self.slots[i] is None:
                self.slots[i] = {"type": "backpack", "object": backpack, "quantity": 1}
                return True
        return False  # No empty slot to carry backpack

    def use_item_at_slot(self, slot_index: int, player_context: Any) -> Dict[str, Any]:
        """Triggers the item action in the specified slot."""
        if slot_index < 0 or slot_index >= self.max_slots or not self.slots[slot_index]:
            return {"success": False, "message": "Slot is empty."}

        slot = self.slots[slot_index]

        if slot["type"] == "backpack":
            return {
                "success": False, 
                "message": "Cannot 'use' a backpack directly. Inspect or store it in your Warehouse."
            }

        item: Item = slot["object"]
        
        # Execute the item using its effect metadata
        result = self._execute_item_effect(item, player_context)

        if result["success"]:
            # Reduce stack quantity
            slot["quantity"] -= 1
            if slot["quantity"] <= 0:
                self.slots[slot_index] = None

        return result

    def _execute_item_effect(self, item: Item, player: Any) -> Dict[str, Any]:
        """Generic dispatcher that routes item execution based on attributes."""
        effect_type = item.attributes.get("effect_type")

        # 1. TIME REDUCTION (Building, Research, Troop Speedups)
        if effect_type == "speedup":
            target = item.attributes.get("target")  # "research", "building", "troops"
            seconds = item.attributes.get("seconds", 0)
            # player.apply_speedup(target, seconds)
            return {"success": True, "message": f"⚡ Applied {seconds // 60}m speedup to {target}!"}

        # 2. SHIELD / PROTECTION BUFF
        elif effect_type == "shield":
            duration_sec = item.attributes.get("duration_sec", 3600)
            # player.add_shield_time(duration_sec)
            return {"success": True, "message": f"🛡️ Activated peace shield for {duration_sec // 3600}h!"}

        # 3. STAT BUFFS & DEBUFFS (Attack +100, Defense +1000)
        elif effect_type == "stat_buff":
            stat = item.attributes.get("stat")  # "attack", "defense", "food_prod"
            multiplier = item.attributes.get("multiplier", 1.0)
            flat_bonus = item.attributes.get("flat_bonus", 0)
            duration = item.attributes.get("duration_sec", 3600)
            # player.apply_buff(stat, multiplier, flat_bonus, duration)
            return {"success": True, "message": f"🔥 Applied +{flat_bonus} {stat} buff for {duration // 60} mins!"}

        # 4. INSTANT RESOURCE / XP GRANT
        elif effect_type == "grant":
            resource = item.attributes.get("resource")  # "gold", "xp", "energy"
            amount = item.attributes.get("amount", 0)
            # player.add_resource(resource, amount)
            return {"success": True, "message": f"✨ Received +{amount} {resource.upper()}!"}

        # 5. UNOPENED CRATE / CHEST
        elif item.is_crate:
            # Drop table extraction logic
            loot = item.attributes.get("drop_table", [])
            return {"success": True, "message": f"📦 Opened {item.name}! Check your loot log."}

        return {"success": False, "message": "Item cannot be consumed right now."}