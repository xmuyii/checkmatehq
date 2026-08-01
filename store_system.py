# -*- coding: utf-8 -*-
"""
store_system.py — The Nexus Marketplace
=========================================
Replaces the broken cb_menu_shop in main.py which called edit_text twice
(second call immediately overwrites the first — only the last one renders).

This file is standalone. Wire it by replacing cb_menu_shop with:
    from store_system import handle_store_callback
    dp.include_router(store_router)

CURRENCIES:
  🪙 Gold  — earned through gameplay, used for most purchases
  ₿ Bitcoin — earned in Crypto Wastes, used for premium items
  💳 Credits — earned from daily login + leaderboard, used for Fusion/Trivia

STORE SECTIONS:
  🛡️ Tactical Defenses  — Basic/Hazmat/Void suits, Base shields
  ⚡ Speedups            — Training, building, research time reduction
  🌀 Teleports           — Charge packs
  🎒 Consumables         — Energy cells, rations, smoke bombs
  💎 Premium             — Bitcoin-priced rare items
"""
# ... your existing imports ...
from supabase_db import is_backpack_full

# ── ADD THIS: Dynamic Db config loader ───────────────────────────────────
def get_live_store_items() -> dict:
    """
    Attempts to fetch the latest store items/prices from Supabase.
    If the database is offline or empty, gracefully falls back to static dictionary.
    """
    try:
        from supabase_db import supabase
        response = supabase.table("store_items_config").select("*").execute()
        if response.data:
            # Reconstruct the STORE_ITEMS dict format dynamically
            db_items = {}
            for row in response.data:
                db_items[row["id"]] = {
                    "name":        row["name"],
                    "desc":        row["description"],
                    "price":       int(row["price"]),
                    "currency":    row["currency"],
                    "category":    row["category"],
                    "effect_key":  row["effect_key"],
                    "qty":         int(row.get("qty", 1)),
                    # Carry over any optional columns if present in your row
                    "res_type":    row.get("res_type"),
                    "res_amount":  row.get("res_amount"),
                    "duration_m":  row.get("duration_m"),
                    "duration_h":  row.get("duration_h"),
                    "reduces_timer_minutes": row.get("reduces_timer_minutes")
                }
            return db_items
    except Exception as e:
        print(f"⚠️ Could not load live store config ({e}). Using local fallback.")
    
    return STORE_ITEMS  # Fallback to the dictionary below
from datetime import datetime, timedelta
from typing import Tuple
from aiogram import Router, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import CallbackQuery

from supabase_db import is_backpack_full

store_router = Router()

# ═══════════════════════════════════════════════════════════════════════════
#  CATALOGUE
# ═══════════════════════════════════════════════════════════════════════════

STORE_ITEMS = {

    # ── Suits & Protection ────────────────────────────────────────────────
    "basic_suit": {
        "name":        "🧪 Basic Radiation Suit",
        "desc":        "Protects from radiation hazards. 10 minutes.",
        "price":       80,
        "currency":    "credits",
        "category":    "protection",
        "effect_key":  "basic_suit",
        "duration_m":  10,
        "qty":         1,
    },
    "hazmat_suit": {
        "name":        "☢️ Hazmat Suit",
        "desc":        "Full hazmat protection. 20 minutes.",
        "price":       180,
        "currency":    "credits",
        "category":    "protection",
        "effect_key":  "hazmat_suit",
        "duration_m":  20,
        "qty":         1,
    },
    "void_suit": {
        "name":        "🌑 Void Suit",
        "desc":        "Void Canyon protection. 15 minutes.",
        "price":       350,
        "currency":    "credits",
        "category":    "protection",
        "effect_key":  "void_suit",
        "duration_m":  15,
        "qty":         1,
    },
    "bitcoin_format": {
        "name":        "💾 Bitcoin Format",
        "desc":        "Crypto Wastes protection. 20 minutes.",
        "price":       300,
        "currency":    "credits",
        "category":    "protection",
        "effect_key":  "bitcoin_format",
        "duration_m":  20,
        "qty":         1,
    },
    "shield_2h": {
        "name":        "🛡️ 2-Hour Shield",
        "desc":        "Protect your base for 2 hours.",
        "price":       40,
        "currency":    "credits",
        "category":    "protection",
        "effect_key":  "shield_item",
        "duration_h":  2,
        "qty":         1,
    },
    "shield_8h": {
        "name":        "🛡️ 8-Hour Base Shield",
        "desc":        "Protects your base from raids for 8 hours.",
        "price":       152,
        "currency":    "credits",
        "category":    "protection",
        "effect_key":  "shield_item",
        "duration_h":  8,
        "qty":         1,
    },
    "shield_24h": {
        "name":        "🛡️ 1-Day Base Shield (24h)",
        "desc":        "Full day of base protection.",
        "price":       408,
        "currency":    "credits",
        "category":    "protection",
        "effect_key":  "shield_item",
        "duration_h":  24,
        "qty":         1,
    },
    "shield_72h": {
        "name":        "🛡️ 3-Day Base Shield (72h)",
        "desc":        "3-day base protection. Best value.",
        "price":       1008,
        "currency":    "credits",
        "category":    "protection",
        "effect_key":  "shield_item",
        "duration_h":  72,
        "qty":         1,
    },           

    # ── Speedups ─────────────────────────────────────────────────────────
    "speedup_1m": {
        "name":        "⏩ 1-Minute Speedup",
        "desc":        "Reduce any timer by 1 minute.",
        "price":       1,
        "currency":    "credits",
        "category":    "speedup",
        "effect_key":  "speedup",
        "reduces_timer_minutes": 1,
        "qty":         1,
    },
    "speedup_5m": {
        "name":        "⏩ 5-Minute Speedup",
        "desc":        "Reduce any timer by 5 minutes.",
        "price":       3,
        "currency":    "credits",
        "category":    "speedup",
        "effect_key":  "speedup",
        "reduces_timer_minutes": 5,
        "qty":         1,
    },
    "speedup_15m": {
        "name":        "⏩ 15-Minute Speedup",
        "desc":        "Reduce any timer by 15 minutes.",
        "price":       8,
        "currency":    "credits",
        "category":    "speedup",
        "effect_key":  "speedup",
        "reduces_timer_minutes": 15,
        "qty":         1,
    },
    "speedup_30m": {
        "name":        "⏩ 30-Minute Speedup",
        "desc":        "Reduce any timer by 30 minutes.",
        "price":       14,
        "currency":    "credits",
        "category":    "speedup",
        "effect_key":  "speedup",
        "reduces_timer_minutes": 30,
        "qty":         1,
    },
    "speedup_1h": {
        "name":        "`⏩` 1-Hour Speedup",
        "desc":        "Reduce any timer by 60 minutes.",
        "price":       27,
        "currency":    "credits",
        "category":    "speedup",
        "effect_key":  "speedup",
        "reduces_timer_minutes": 60,
        "qty":         1,
    },
    "speedup_3h": {
        "name":        "`⏩` 3-Hour Speedup",
        "desc":        "Reduce any timer by 3 hours.",
        "price":       77,
        "currency":    "credits",
        "category":    "speedup",
        "effect_key":  "speedup",
        "reduces_timer_minutes": 180,
        "qty":         1,
    },
    "speedup_8h": {
        "name":        "`⏩` 8-Hour Speedup",
        "desc":        "Reduce any timer by 8 hours.",
        "price":       180,
        "currency":    "credits",
        "category":    "speedup",
        "effect_key":  "speedup",
        "reduces_timer_minutes": 480,
        "qty":         1,
    },
    "speedup_1day": {
        "name":        "⏩ 1-Day Speedup",
        "desc":        "Reduce any timer by 24 hours.",
        "price":       504,
        "currency":    "credits",
        "category":    "speedup",
        "effect_key":  "speedup",
        "reduces_timer_minutes": 1440,
        "qty":         1,
    },
    "speedup_7day": {
        "name":        "⏩ 7-Day Speedup",
        "desc":        "Reduce any timer by 7 days.",
        "price":       4000,
        "currency":    "credits",
        "category":    "speedup",
        "effect_key":  "speedup",
        "reduces_timer_minutes": 10080,
        "qty":         1,
    },
    "speedup_21day": {
        "name":        "⏩ 21-Day Speedup",
        "desc":        "Reduce any timer by 21 days.",
        "price":       6804,
        "currency":    "credits",
        "category":    "speedup",
        "effect_key":  "speedup",
        "reduces_timer_minutes": 30240,
        "qty":         1,
    },
    "speedup_pack": {
        "name":        "⏩ Speedup Pack (×5 30m)",
        "desc":        "5× 30-minute speedups. Save 20%.",
        "price":       56,
        "currency":    "credits",
        "category":    "speedup",
        "effect_key":  "speedup",
        "reduces_timer_minutes": 30,
        "qty":         5,
    },

    # ── Teleport Charges ──────────────────────────────────────────────────
    "teleport_1": {
        "name":        "🌀 Quantum Teleport",
        "desc":        "One additional teleport charge.",
        "price":       75,
        "currency":    "credits",
        "category":    "teleport",
        "effect_key":  "teleport_charge",
        "qty":         1,
    },
    "teleport_5": {
        "name":        "🌀 Teleport Core Pack",
        "desc":        "5 charges. 15% off.",
        "price":       320,
        "currency":    "credits",
        "category":    "teleport",
        "effect_key":  "teleport_charge",
        "qty":         5,
    },
    "teleport_10": {
        "name":        "🌀 Sector Warp Matrix",
        "desc":        "10 charges. Best value.",
        "price":       525,
        "currency":    "credits",
        "category":    "teleport",
        "effect_key":  "teleport_charge",
        "qty":         10,
    },

    # ── Consumables ───────────────────────────────────────────────────────
    "energy_cell": {
        "name":        "⚡ Energy Cell",
        "desc":        "Restore 100 energy instantly.",
        "price":       25,
        "currency":    "credits",
        "category":    "consumable",
        "effect_key":  "energy_restore",
        "energy":      100,
        "qty":         1,
    },
    "energy_pack": {
        "name":        "⚡ Energy Pack",
        "desc":        "5× energy cells. Save 20%.",
        "price":       100,
        "currency":    "credits",
        "category":    "consumable",
        "effect_key":  "energy_restore",
        "energy":      100,
        "qty":         5,
    },
    "xp_chip_minor": {
        "name":        "📁 Tactical Data Chip",
        "desc":        "Add 250 XP to your commander. Useful for leveling up.",
        "price":       125,
        "currency":    "credits",
        "category":    "xp_point",
        "effect_key":  "xp_boost",       
        "xp":          250,
        "qty":         1,
    },
    "xp_chip_major": {
        "name":        "📂 Combat Simulator Log",
        "desc":        "Add 1000 XP to your commander. Essential for progression.",
        "price":       450,
        "currency":    "credits",
        "category":    "xp_point",
        "effect_key":  "xp_boost",
        "xp":          1000,
        "qty":         1,
    },
    "xp_chip_relic": {
        "name":        "🗂 Ancient Commander Core",
        "desc":        "Add 5000 XP to your commander. Legendary for progression.",
        "price":       2000,
        "currency":    "credits",
        "xp":          5000,
        "category":    "xp_point",
        "effect_key":  "xp_boost",
        "qty":         1,
    },
    "energy_cell": {
        "name":        "⚡ Energy Cell",
        "desc":        "Restore 100 energy instantly.",
        "price":       25,
        "currency":    "credits",
        "category":    "consumable",
        "effect_key":  "energy_restore",
        "energy":      100,
        "qty":         1,
    },

    # ── Premium (Bitcoin) ─────────────────────────────────────────────────
    "cold_wallet": {
        "name":        "🔐 Cold Wallet",
        "desc":        "Max Crypto Wastes protection. 45 minutes. Survives Market Crash.",
        "price":       50,
        "currency":    "bitcoin",
        "category":    "premium",
        "effect_key":  "cold_wallet",
        "duration_m":  45,
        "qty":         1,
    },
    "xp_boost_2x": {
        "name":        "💫 2× XP Boost (1h)",
        "desc":        "Double XP for one hour.",
        "price":       80,
        "currency":    "bitcoin",
        "category":    "premium",
        "effect_key":  "xp_boost",
        "qty":         1,
    },
    "resource_boost": {
        "name":        "2️⃣ 2× Resources (1h)",
        "desc":        "All node yields doubled for 1 hour.",
        "price":       60,
        "currency":    "bitcoin",
        "category":    "premium",
        "effect_key":  "resource_boost",
        "qty":         1,
    },
    "crate_wood_credits": {
    "name": "🪵 Wood Crate",
    "desc": "Random wood resources + small XP.",
    "price": 100,
    "currency": "credits", 
    "category": "crates",
    "effect_key": "crate_unclaimed", 
    "crate_type": "wood_crate", 
    "qty": 1,
    },
    "crate_bronze_credits": {
        "name": "🥉 Bronze Crate",
        "desc": "Random bronze resources + XP.",
        "price": 250, 
        "currency": "credits", 
        "category": "crates",
        "effect_key": "crate_unclaimed", 
        "crate_type": "bronze_crate", 
        "qty": 1,
    },
    "crate_iron_credits": {
        "name": "⚙️ Iron Crate",
        "desc": "Random iron resources + solid XP.",
        "price": 500, 
        "currency": "credits", 
        "category": "crates",
        "effect_key": "crate_unclaimed", 
        "crate_type": "iron_crate", 
        "qty": 1,
    },
    "crate_super_credits": {
        "name": "🌟 Super Crate",
        "desc": "Best odds, biggest XP payout.",
        "price": 1000, 
        "currency": "credits", 
        "category": "crates",
        "effect_key": "crate_unclaimed", 
        "crate_type": "super_crate", 
        "qty": 1,
    },
    "food_1k": {
    "name": "🥫 Rations Pack (1,000)",
    "desc": "Feed your base.", 
    "price": 50, 
    "currency": "credits",
    "category": "resources", 
    "effect_key": "resource_pack",
    "res_type": "food", 
    "res_amount": 1000, 
    "qty": 1,
    },
    "food_10k": {
    "name": "🥫 Rations Pack (10,000)",
    "desc": "Feed your base — bulk.", 
    "price": 400, "currency": "credits",
    "category": "resources", 
    "effect_key": "resource_pack",
    "res_type": "food", "res_amount": 10000, "qty": 1,
    },
    "wood_1k": {
    "name": "🪵 Wood Pack (1,000)",
    "desc": "Basic building resource.", 
    "price": 50, 
    "currency": "credits",
    "category": "resources", 
    "effect_key": "resource_pack",
    "res_type": "wood", 
    "res_amount": 1000, "qty": 1,
},
# ...repeat the 1k/10k pattern for wood, bronze, iron, stone, relics
}

CATEGORIES = {
    "protection": "🛡️ Tactical Defenses",
    "speedup":    "⏩ Quantum Speedups",
    "teleport":   "🌀 Sector Warp Cores",
    "consumable": "🎒 Hardware Utilities",
    "premium":    "📈 Cryptographic Assets",
    "crates":     "📦 Crate packages",
    "resources":   "🎁 Resources Shipping",

}


# ═══════════════════════════════════════════════════════════════════════════
#  PURCHASE LOGIC
# ═══════════════════════════════════════════════════════════════════════════
from item_factory import create_item_from_store_data

def purchase_item(user: dict, item_key: str) -> Tuple[bool, str, dict]:
    """
    Execute a store purchase.
    Deducts currency, saves consumables/shields/energy to the backpack inventory, 
    and credits top-level stat columns directly (like teleports).
    Returns (success, message, updated_user)
    """
    from supabase_db import add_inventory_item

    items_catalog = get_live_store_items()
    raw_item_data = items_catalog.get(item_key)
    item = items_catalog.get(item_key)
    if not raw_item_data:
        return False, "❌ Item not found.", user

    item_obj: Item = create_item_from_store_data(item_key, raw_item_data)

    price    = item_obj.attributes.get("price", 0)
    currency = item_obj.attributes.get("currency", "credits")
    qty      = raw_item_data.get("qty", 1)

    # Helper balance accessors
    def _get_gold(u):
        return u.get("gold", 0) or 0

    def _set_gold(u, val):
        u["gold"] = val
        return u

    # ── Currency Deductions ──
    if currency == "gold":
        balance = _get_gold(user)
        if balance < price:
            return False, f"❌ Need {price} 🪙. You have {balance} 🪙.", user
        user = _set_gold(user, balance - price)

    elif currency == "bitcoin":
        balance = user.get("bitcoin", 0)
        if balance < price:
            return False, f"❌ Need {price} ₿. You have {balance} ₿.", user
        user["bitcoin"] = balance - price

    elif currency == "credits":
        balance = user.get("credits", 0)
        if balance < price:
            return False, f"❌ Need {price} 💳. You have {balance} 💳.", user
        user["credits"] = balance - price

    # ── Apply Item Routing ──
    effect_key = item_obj.attributes.get("effect_key", "")
    effect_msg = ""

    # 1. Teleport Charges (Kept as a direct account stat top-up to save backpack space)
    if effect_key == "teleport_charge":
        current = user.get("teleport_charges", 0) or 0
        user["teleport_charges"] = current + qty
        effect_msg = f"🌀 Matrix updated: +{qty} teleport charge(s) added directly to your console."

    # 2. Energy Cells (FIXED: Now stashed safely in backpack instead of instant consumption!)
    elif effect_key == "energy_restore":
        user = add_inventory_item(user, item_key, qty, item["name"], category="consumable")
        effect_msg = f"🎒 Stashed in backpack: {item['name']} ×{qty}. Use it whenever your generator runs dry."

    # 3. XP Points / Chips Category (Saves to backpack)
    elif effect_key == "xp_point":
        user = add_inventory_item(user, item_key, qty, item["name"], category="consumable")
        effect_msg = f"📦 Added to inventory: {item['name']} ×{qty}"

    # 4. Base Protective Shields (Saves to backpack)
    elif effect_key == "shield_item":
        user = add_inventory_item(user, item_key, qty, item["name"], category="protective")
        effect_msg = f"📦 Added to inventory: {item['name']} ×{qty}"

    # 5. Tactical Suits & Gear (Saves to backpack)
    elif effect_key in ("basic_suit", "hazmat_suit", "void_suit", "bitcoin_format", "cold_wallet"):
        user = add_inventory_item(user, effect_key, qty, item["name"], category="protective")
        effect_msg = f"💼 Added to loadout options: {item['name']} ×{qty}"

    # 6. Building / Training Speedups (Saves to backpack)
    elif effect_key == "speedup":
        mins = item.get("reduces_timer_minutes", 5)
        skey = f"speedup_{mins}m"
        user = add_inventory_item(user, skey, qty, f"⏩ {mins}m Speedup", category="speedup")
        effect_msg = f"⏩ {qty}× {mins}m speedup(s) stored in backpack"
        # In purchase_item(), new effect branch:
    # store_system.py, purchase_item() — REPLACE the earlier resource_pack branch with this:
    elif effect_key == "resource_pack":
        from supabase_db import add_inventory_item
        res_type = item.get("res_type")
        res_amount = item.get("res_amount", 0)
        user = add_inventory_item(
            user, item_key, qty, item["name"],
            category="resource_pack",
        )
        # stash the pack's payload on the item row so the "use" action knows what to grant
        from supabase_db import get_inventory_item
        row = get_inventory_item(user, item_key)
        row["res_type"] = res_type
        row["res_amount"] = res_amount
        effect_msg = f"📦 {qty}× {item['name']} added to your backpack." # In purchase_item(), new effect branch:
    elif effect_key == "crate_unclaimed":
        from supabase_db import _next_id, _crate_xp
        crate_type = item.get("crate_type", item_key)
        unclaimed = user.get("unclaimed_items", [])
        if not isinstance(unclaimed, list):
            unclaimed = []
        for _ in range(qty):
            unclaimed.append({
                "id": _next_id(unclaimed),
                "type": crate_type,
                "amount": 1,
                "xp_reward": _crate_xp(crate_type) if "crate" in crate_type.lower() else 0,
                "multiplier_value": 0,
                "created_at": datetime.utcnow().isoformat(),
            })
        user["unclaimed_items"] = unclaimed
        effect_msg = f"📬 {qty}× {item['name']} sent to your unclaimed rewards — use /claims to open."
    # 7. Safe Structural Fallback for General Consumables
    else:
        # Save serialized OOP Item payload into the inventory
        user = add_inventory_item(
            user=user, 
            item_key=item_obj.item_id, 
            qty=qty, 
            name=item_obj.name, 
            category=item_obj.category.value, # Uses Enum value ('utility', 'defend', etc.)
            item_data=item_obj.to_dict()       # Attaches complete OOP dictionary payload
        )
        effect_msg = f"📦 {qty}× {item_obj.name} added into inventory."
    # ── Final Message Compilation ──
    curr_symbol = {"gold": "🪙", "bitcoin": "₿", "credits": "💳"}[currency]
    new_bal     = _get_gold(user) if currency == "gold" else user.get(currency, 0)

    return True, (
        f"✅ *Purchase Complete!*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{item_obj.name}\n"
        f"Cost: {price} {curr_symbol}\n"
        f"Balance: {new_bal} {curr_symbol}\n\n"
        f"{effect_msg}"
    ), user

# ═══════════════════════════════════════════════════════════════════════════
#  DISPLAY FORMATTERS
# ═══════════════════════════════════════════════════════════════════════════

def format_store_home(user: dict) -> str:
    gold    = user.get("gold", 0)
    bitcoin = user.get("bitcoin", 0)
    credits = user.get("credits", 0)
    return (
        f"🛍️ *THE NEXUS MARKETPLACE*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🪙 Gold: *{gold:,}*\n"
        f"₿ Bitcoin: *{bitcoin:,}*\n"
        f"💳 Credits: *{credits:,}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Select a category below."
    )


def format_category(category: str, user: dict) -> str:
    gold    = user.get("gold", 0)
    bitcoin = user.get("bitcoin", 0)
    credits = user.get("credits", 0) # Added credits variable
    cat_label = CATEGORIES.get(category, category)
    lines = [
        f"{cat_label}",
        f"━━━━━━━━━━━━━━━━━━━━━━━━",
    ]
    items_catalog = get_live_store_items()
    for ikey, item in items_catalog.items():
        if item["category"] != category:
            continue
        price    = item["price"]
        currency = item["currency"]
        curr_sym = {"gold": "🪙", "bitcoin": "₿", "credits": "💳"}[currency]
        
        # FIX: Check the exact active currency
        if currency == "gold":
            balance = gold
        elif currency == "bitcoin":
            balance = bitcoin
        else:
            balance = credits

        can      = "✅" if balance >= price else "❌"
        qty_tag  = f" ×{item['qty']}" if item.get("qty", 1) > 1 else ""
        lines.append(f"{can} {item['name']}{qty_tag} — {price}{curr_sym}")
        lines.append(f"   _{item['desc']}_")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
#  INLINE KEYBOARDS
# ═══════════════════════════════════════════════════════════════════════════

def kb_category(category: str, user: dict) -> InlineKeyboardMarkup:
    gold    = user.get("gold", 0)
    bitcoin = user.get("bitcoin", 0)
    credits = user.get("credits", 0)
    
    buttons = []
    items_catalog = get_live_store_items() # 👈 Load live configurations
    for ikey, item in items_catalog.items():
        if item["category"] != category:
            continue
        price    = item["price"]
        currency = item["currency"]
        curr_sym = {"gold": "🪙", "bitcoin": "₿", "credits": "💳"}[currency]
        
        if currency == "gold":
            balance = gold
        elif currency == "bitcoin":
            balance = bitcoin
        else:
            balance = credits
            
        can      = "" if balance >= price else "❌ "
        qty_tag  = f" ×{item['qty']}" if item.get("qty", 1) > 1 else ""
        
        # Route through confirmation step first — actual purchase only happens
        # after the player taps "Confirm Purchase" in handle_store's "conf" branch.
        buttons.append([InlineKeyboardButton(
            text=f"{can}{item['name']}{qty_tag} — {price}{curr_sym}",
            callback_data=f"store:conf:{ikey}"
        )])
        
    buttons.append([InlineKeyboardButton(text="🔙👤 Commander", callback_data="menu_profile"),
                    InlineKeyboardButton(text="🔙🏪 Store", callback_data="store:home")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_after_purchase(category: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙🎒 Items",       callback_data="menu_inventory_store"),
        InlineKeyboardButton(text="🛍️ Buy More",   callback_data=f"store:cat:{category}")],
        [InlineKeyboardButton(text="🏰 My Base",    callback_data="menu_base"),
        InlineKeyboardButton(text="🏠 Dashboard",  callback_data="menu_back")],
    ])

def kb_store_home(user: dict) -> InlineKeyboardMarkup:
    """Generates the primary marketplace navigation landing categories."""
    buttons = [
        [   InlineKeyboardButton(text="🖼 Base Resource", callback_data="store:cat:resources"),
            InlineKeyboardButton(text="🎁 Resource Crates", callback_data="store:cat:crates"),
            InlineKeyboardButton(text="🛡️ Tactical Defenses", callback_data="store:cat:protection"),
            InlineKeyboardButton(text="⏩ Quantum Speedups", callback_data="store:cat:speedup")
        ],
        [
            InlineKeyboardButton(text="🌀 Sector Warp Cores", callback_data="store:cat:teleport"),
            InlineKeyboardButton(text="🎒 Hardware Utilities", callback_data="store:cat:consumable")
        ],
        [
            InlineKeyboardButton(text="📈 Cryptographic Assets", callback_data="store:cat:premium"),
            InlineKeyboardButton(text="🎖 XP Points", callback_data="store:cat:xp_point")
        ],
        [   InlineKeyboardButton(text="🔙👤 Commander",   callback_data="menu_profile"),
            InlineKeyboardButton(text="🔙🎒 Items",       callback_data="menu_inventory")], 
        [   InlineKeyboardButton(text="❌ Close Marketplace", callback_data="menu_back")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
# ═══════════════════════════════════════════════════════════════════════════
#  ROUTER HANDLERS
# ═══════════════════════════════════════════════════════════════════════════

@store_router.callback_query(F.data.startswith("store:") | F.data.in_({"menu_shop"}))
async def handle_store(cb: CallbackQuery):
    from supabase_db import get_user, save_user
    u_id = str(cb.from_user.id)
    kb = None  # Default keyboard fallback
    text = "🛍️ Welcome to the Nexus Marketplace!"
    user = get_user(u_id)
    if not user:
        await cb.answer("Please /start first.", show_alert=True)
        return

    data = cb.data
    if data == "menu_shop" or data == "store:home":
        text = format_store_home(user)
        
        # 💡 Calling our restored function right here!
        kb = kb_store_home(user) 
        
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")
        await cb.answer()
        return

    parts = data.split(":")
    action = parts[1] if len(parts) > 1 else ""
    param  = parts[2] if len(parts) > 2 else ""

    if action == "cat":
        text = format_category(param, user)
        kb   = kb_category(param, user)
        # Render right here and stop execution
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")
        await cb.answer()
        return
    
    if action == "conf":
        item_key = param
        items_catalog = get_live_store_items()
        item = items_catalog.get(item_key)
        if not item:
            await cb.answer("Item not found.", show_alert=True)
            return

        curr_sym = {"gold": "🪙", "bitcoin": "₿", "credits": "💳"}[item["currency"]]
        text = (
            f"🚨 *CONFIRM PURCHASE*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 *{item['name']}*\n"
            f"📝 _{item['desc']}_\n\n"
            f"💰 Cost: {item['price']} {curr_sym}"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Confirm", callback_data=f"store:buy:{item_key}"),
                InlineKeyboardButton(text="❌ Cancel", callback_data=f"store:cat:{item.get('category','consumable')}")
            ]
        ])
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")
        await cb.answer()
        return

    elif action == "buy":
        item_key = param
        items_catalog = get_live_store_items()
        item     = items_catalog.get(item_key)
        
        if is_backpack_full(user):
            await cb.answer("🎒 Your backpack is full! Upgrade your storage capacity or clear space first.", show_alert=True)
            return
            
        if not item:
            await cb.answer("Item not found.", show_alert=True)
            return

        ok, msg, user = purchase_item(user, item_key)
        if ok:
            save_user(u_id, user)
            category = item.get("category", "consumable")
            kb = kb_after_purchase(category)
            text = msg  # Map msg content to our unified text variable
            
            try:
                await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
            except Exception:
                await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

            # Notification pipeline
            try:
                from notification_engine import notify_player
                from supabase_db import supabase
                await notify_player(
                    cb.bot, u_id, "daily_reward",
                    f"🛍️ *Purchase confirmed:* {item['name']}",
                    supabase, "players"
                )
            except Exception:
                pass
                
            await cb.answer()
            return
        else:
            # Handle failed purchase cleanly
            await cb.answer(msg[:200], show_alert=True)
            text = msg 
            kb = None
            
            try:
                await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
            except Exception:
                await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")
                
            await cb.answer()
            return