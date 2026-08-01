# item_factory.py
from inventory.item import Item, ItemCategory

# Map store string categories to your ItemCategory Enum
CATEGORY_MAP = {
    "protection": ItemCategory.DEFEND,
    "speedup": ItemCategory.UTILITY,
    "teleport": ItemCategory.UTILITY,
    "consumable": ItemCategory.UTILITY,
    "premium": ItemCategory.COMMANDER,
    "crates": ItemCategory.CRATES,
    "resources": ItemCategory.RESOURCES,
    "xp_point": ItemCategory.COMMANDER,
}

def create_item_from_store_data(item_key: str, store_item_dict: dict) -> Item:
    """Instantiates an Item class object from store dictionary data."""
    
    cat_str = store_item_dict.get("category", "consumable")
    mapped_category = CATEGORY_MAP.get(cat_str, ItemCategory.UTILITY)
    
    # Is it a crate? Crates cannot fit in standard backpacks
    is_crate = (mapped_category == ItemCategory.CRATES) or store_item_dict.get("category") == "crates"

    # Extract dynamic item attributes
    attributes = {
        "price": store_item_dict.get("price", 0),
        "currency": store_item_dict.get("currency", "credits"),
        "effect_key": store_item_dict.get("effect_key", ""),
        "duration_m": store_item_dict.get("duration_m"),
        "duration_h": store_item_dict.get("duration_h"),
        "energy": store_item_dict.get("energy"),
        "xp": store_item_dict.get("xp"),
        "reduces_timer_minutes": store_item_dict.get("reduces_timer_minutes"),
        "res_type": store_item_dict.get("res_type"),
        "res_amount": store_item_dict.get("res_amount"),
    }
    # Clean out None values
    attributes = {k: v for k, v in attributes.items() if v is not None}

    return Item(
        item_id=item_key,
        name=store_item_dict.get("name", "Unknown Item"),
        category=mapped_category,
        description=store_item_dict.get("desc", ""),
        stack_limit=99,
        is_crate=is_crate,
        attributes=attributes
    )