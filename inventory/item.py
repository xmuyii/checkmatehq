from enum import Enum
from typing import Optional, Dict, Any


class ItemCategory(str, Enum):
    ATTACK = "attack"
    DEFEND = "defend"
    UTILITY = "utility"
    CRATES = "crates"
    RESOURCES = "resources"
    COMMANDER = "commander"


class Item:
    """Base class for all items in the game."""

    def __init__(
        self,
        item_id: str,
        name: str,
        category: ItemCategory,
        description: str = "",
        stack_limit: int = 99,
        is_crate: bool = False,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        self.item_id = item_id
        self.name = name
        self.category = category
        self.description = description
        self.stack_limit = stack_limit
        self.is_crate = is_crate  # True = Cannot fit inside backpacks
        self.attributes = attributes or {}

    def to_dict(self) -> Dict[str, Any]:
        """Serializes item state for database storage or JSON responses."""
        return {
            "item_id": self.item_id,
            "name": self.name,
            "category": self.category.value,
            "description": self.description,
            "stack_limit": self.stack_limit,
            "is_crate": self.is_crate,
            "attributes": self.attributes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Item":
        """Reconstructs an item instance from serialized data."""
        return cls(
            item_id=data["item_id"],
            name=data["name"],
            category=ItemCategory(data["category"]),
            description=data.get("description", ""),
            stack_limit=data.get("stack_limit", 99),
            is_crate=data.get("is_crate", False),
            attributes=data.get("attributes", {}),
        )

    def use(self, player: Any) -> bool:
        """Override in subclasses for interactive behavior upon use."""
        raise NotImplementedError("This item has no direct use action.")