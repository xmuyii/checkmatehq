# -*- coding: utf-8 -*-
"""
black_market.py — The Black Market
=====================================
A hidden trading system accessible only through hidden sector nodes
(sectors 10-59). Players can trade soulbound items, sell rare drops,
and buy items unavailable anywhere else — at their own risk.

MECHANICS:
  - Accessible only from hidden sectors (10-59)
  - Finding a Black Market node requires teleporting to hidden sectors
    and occupying the special "black_market" node type
  - Listings persist for 24 hours then expire
  - Trades execute instantly when buyer accepts
  - 10% market fee taken by the sector ruler (or void if no ruler)
  - Soulbound items CAN be traded here (unique property of Black Market)
  - Risk: you can be attacked while browsing/trading in hidden sectors

RARE ITEMS EXCLUSIVE TO BLACK MARKET:
  - Recipe books (unlock hidden crafting recipes)
  - Scammer Kit (crypto sector ability)
  - Black market deeds (claim a hidden sector base plot without a ruler)
  - Banishment Pardon (removes a banishment from yourself)
  - Commander's Echo (copies another player's skill tree for 1 hour)

PRICE DISCOVERY:
  Prices are set by sellers. The market decides what's fair.
  The Chronicle tracks the most expensive trades of the week.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import json
import os
import random

MARKET_FILE      = "black_market_listings.json"
MARKET_FEE_PCT   = 0.10
LISTING_HOURS    = 24
MAX_LISTINGS     = 50    # Total server listings cap

# ── Exclusive Black Market items ──────────────────────────────────────────
EXCLUSIVE_ITEMS: Dict[str, dict] = {
    "recipe_book_military": {
        "display_name": "Military Recipe Book",
        "emoji":        "📖",
        "description":  "Unlocks all hidden military crafting recipes permanently.",
        "category":     "recipe_book",
        "base_price":   800,
        "rarity":       "rare",
        "tradeable":    True,
        "effect":       {"unlock_recipes": ["craft_siege_hammer", "craft_war_banner",
                                             "craft_decoy_signal"]},
    },
    "recipe_book_legendary": {
        "display_name": "Legendary Recipe Tome",
        "emoji":        "📕",
        "description":  "Unlocks all legendary crafting recipes permanently.",
        "category":     "recipe_book",
        "base_price":   2500,
        "rarity":       "legendary",
        "tradeable":    True,
        "effect":       {"unlock_recipes": ["craft_commanders_sigil",
                                             "craft_void_lattice_trap",
                                             "craft_ancient_banner"]},
    },
    "scammer_kit": {
        "display_name": "🦹 Scammer Kit",
        "emoji":        "🦹",
        "description":  "Equip in the Crypto Wastes during Scammer Alert phase. "
                        "YOU become the scammer — steal Satoshi from unprotected miners "
                        "for 10 minutes. Loot kept by you, not the sector.",
        "category":     "ability_item",
        "base_price":   1500,
        "rarity":       "rare",
        "tradeable":    True,
        "consumable":   True,
        "duration_minutes": 10,
    },
    "banishment_pardon": {
        "display_name": "Banishment Pardon",
        "emoji":        "📜",
        "description":  "Removes ONE active banishment from yourself instantly. "
                        "Does not work on war-system bans.",
        "category":     "utility",
        "base_price":   600,
        "rarity":       "uncommon",
        "tradeable":    True,
        "consumable":   True,
    },
    "commanders_echo": {
        "display_name": "Commander's Echo",
        "emoji":        "🪞",
        "description":  "Choose any player. Copy their entire skill tree allocation "
                        "for exactly 1 hour. Then your points reset to what they were.",
        "category":     "ability_item",
        "base_price":   2000,
        "rarity":       "legendary",
        "tradeable":    True,
        "consumable":   True,
        "duration_minutes": 60,
    },
    "sector_deed": {
        "display_name": "Hidden Sector Deed",
        "emoji":        "🗺️",
        "description":  "Claim a base plot in any hidden sector (10-59) without "
                        "needing a sector ruler's approval. The deed is sector-specific.",
        "category":     "utility",
        "base_price":   1200,
        "rarity":       "rare",
        "tradeable":    True,
        "consumable":   True,
    },
    "ghost_cloak": {
        "display_name": "Ghost Cloak",
        "emoji":        "👻",
        "description":  "For 2 hours: your name appears as 'Unknown Commander' "
                        "in all sector reports, chats, and node maps. "
                        "Bounty hunters cannot track you. Lasts 2 hours.",
        "category":     "stealth",
        "base_price":   900,
        "rarity":       "rare",
        "tradeable":    True,
        "consumable":   True,
        "duration_minutes": 120,
    },
    "market_insider": {
        "display_name": "Market Insider Report",
        "emoji":        "📊",
        "description":  "Reveals the exact pending resource amounts at every "
                        "occupied node in one sector of your choice. One use.",
        "category":     "intelligence",
        "base_price":   500,
        "rarity":       "uncommon",
        "tradeable":    True,
        "consumable":   True,
    },
}


# ═══════════════════════════════════════════════════════════════════════════
#  LISTING MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

def _load_listings() -> List[dict]:
    if not os.path.exists(MARKET_FILE):
        return []
    try:
        with open(MARKET_FILE) as f:
            listings = json.load(f)
        if not isinstance(listings, list):
            return []
        # Auto-expire old listings
        now      = datetime.utcnow().isoformat()
        active   = [l for l in listings
                    if l.get("expires_at", "") > now and l.get("status") == "active"]
        if len(active) != len(listings):
            _save_listings(active)
        return active
    except Exception:
        return []


def _save_listings(listings: List[dict]):
    try:
        with open(MARKET_FILE, "w") as f:
            json.dump(listings, f, indent=2)
    except Exception as e:
        print(f"[BLACK MARKET] Save error: {e}")


def get_active_listings(
    category: str = None,
    seller_id: str = None,
) -> List[dict]:
    """Get all active listings, optionally filtered."""
    listings = _load_listings()
    if category:
        listings = [l for l in listings if l.get("category") == category]
    if seller_id:
        listings = [l for l in listings if l.get("seller_id") == seller_id]
    return sorted(listings, key=lambda x: x.get("listed_at", ""), reverse=True)


def create_listing(
    seller_user: dict,
    item_key: str,
    item_qty: int,
    price_gold: int,
    sector_id: int,
) -> Tuple[bool, str, dict]:
    """
    Seller lists an item on the Black Market.
    Item is removed from their inventory immediately (held in escrow).
    Returns (success, message, updated_seller)
    """
    if price_gold < 10:
        return False, "❌ Minimum price is 10 🪙.", seller_user

    # Check seller is in a hidden sector
    loc = seller_user.get("commander_location", {}) or {}
    current_sector = loc.get("sector_id", 0)
    if not (10 <= current_sector <= 59):
        return False, (
            "❌ Black Market only accessible from hidden sectors (10-59).\n"
            "Teleport to a hidden sector first."
        ), seller_user

    # Check item in inventory
    from supabase_db import get_inventory_item, remove_inventory_item
    item_row = get_inventory_item(seller_user, item_key)
    have_qty = int(item_row.get("qty", item_row.get("quantity", 0)) or 0) if item_row else 0
    if have_qty < item_qty:
        return False, f"❌ Not enough {item_key} in inventory.", seller_user

    # Check listings cap
    listings = _load_listings()
    if len(listings) >= MAX_LISTINGS:
        return False, "❌ Black Market is at capacity. Try again later.", seller_user

    # Check seller's own listing limit (max 5)
    seller_id  = seller_user.get("user_id", "")
    my_listings = [l for l in listings if l.get("seller_id") == seller_id]
    if len(my_listings) >= 5:
        return False, "❌ You can only have 5 active listings at a time.", seller_user

    # Deduct from inventory (escrow)
    for _ in range(item_qty):
        seller_user = remove_inventory_item(seller_user, item_key)

    # Create listing
    listing_id = f"mkt_{int(datetime.utcnow().timestamp())}_{seller_id[-4:]}"
    expires_at = (datetime.utcnow() + timedelta(hours=LISTING_HOURS)).isoformat()

    # Get item display info
    from resource_registry import RESOURCES, get_display_name, get_emoji
    exclusive = EXCLUSIVE_ITEMS.get(item_key, {})
    res_data  = RESOURCES.get(item_key, {})
    item_name = (exclusive.get("display_name") or
                 res_data.get("display_name") or
                 get_display_name(item_key))
    item_emoji = (exclusive.get("emoji") or
                  res_data.get("emoji") or
                  get_emoji(item_key))
    item_desc  = (exclusive.get("description") or
                  res_data.get("description") or "")
    category   = (exclusive.get("category") or
                  res_data.get("category") or "misc")

    listing = {
        "listing_id":    listing_id,
        "seller_id":     seller_id,
        "seller_name":   seller_user.get("username", "Anonymous"),
        "item_key":      item_key,
        "item_name":     item_name,
        "item_emoji":    item_emoji,
        "item_desc":     item_desc,
        "item_qty":      item_qty,
        "price_gold":    price_gold,
        "price_per_unit": price_gold // item_qty,
        "category":      category,
        "sector_id":     current_sector,
        "listed_at":     datetime.utcnow().isoformat(),
        "expires_at":    expires_at,
        "status":        "active",
        "is_exclusive":  item_key in EXCLUSIVE_ITEMS,
    }

    listings.append(listing)
    _save_listings(listings)

    return True, (
        f"🏪 *Listed on Black Market!*\n"
        f"{item_emoji} {item_name} ×{item_qty}\n"
        f"Price: {price_gold} 🪙 total ({price_gold//item_qty} 🪙 each)\n"
        f"Expires: {LISTING_HOURS}h\n"
        f"ID: `{listing_id}`"
    ), seller_user


def purchase_listing(
    buyer_user: dict,
    listing_id: str,
    supabase,
    DB_TABLE: str = "players",
) -> Tuple[bool, str, dict]:
    """
    Buyer purchases a listing.
    Gold transferred: buyer → seller (minus fee → ruler or void).
    Item transferred: escrow → buyer inventory.
    Returns (success, message, updated_buyer)
    """
    listings = _load_listings()
    target   = None
    idx      = None
    for i, l in enumerate(listings):
        if l.get("listing_id") == listing_id and l.get("status") == "active":
            target = l
            idx    = i
            break

    if not target:
        return False, "❌ Listing not found or already sold.", buyer_user

    buyer_id = buyer_user.get("user_id", "")
    if target.get("seller_id") == buyer_id:
        return False, "❌ Cannot buy your own listing.", buyer_user

    price  = target.get("price_gold", 0)
    gold   = buyer_user.get("gold", 0) or 0

    if gold < price:
        return False, f"❌ Need {price} 🪙. You have {gold} 🪙.", buyer_user

    # Deduct gold from buyer
    buyer_user["gold"] = gold - price

    # Calculate fee
    fee        = int(price * MARKET_FEE_PCT)
    seller_cut = price - fee

    # Pay seller
    try:
        from supabase_db import get_user, save_user
        seller_id = target["seller_id"]
        seller    = get_user(seller_id)
        if seller:
            seller["gold"] = (seller.get("gold", 0) or 0) + seller_cut
            seller["pending_notification"] = (
                f"🏪 *Item Sold!*\n"
                f"{target['item_emoji']} {target['item_name']} ×{target['item_qty']}\n"
                f"Earned: {seller_cut} 🪙 (after {fee} 🪙 market fee)\n"
                f"Buyer: @{buyer_user.get('username','?')}"
            )
            save_user(seller_id, seller)
    except Exception as e:
        print(f"[BLACK MARKET] Seller payment error: {e}")

    # Give item to buyer
    item_key  = target["item_key"]
    item_qty  = target["item_qty"]
    item_name = target["item_name"]
    item_emoji = target["item_emoji"]
    item_desc  = target.get("item_desc", "")

    from supabase_db import add_inventory_item
    buyer_user = add_inventory_item(
        buyer_user, item_key, item_qty, item_name,
        category=target.get("category", "misc"),
    )

    # Apply recipe book effect immediately
    if target.get("category") == "recipe_book":
        exclusive = EXCLUSIVE_ITEMS.get(item_key, {})
        effect    = exclusive.get("effect", {})
        new_recipes = effect.get("unlock_recipes", [])
        discovered = buyer_user.get("discovered_recipes", []) or []
        for rk in new_recipes:
            if rk not in discovered:
                discovered.append(rk)
        buyer_user["discovered_recipes"] = discovered

    # Mark listing sold
    listings[idx]["status"]    = "sold"
    listings[idx]["buyer_id"]  = buyer_id
    listings[idx]["buyer_name"] = buyer_user.get("username", "?")
    listings[idx]["sold_at"]   = datetime.utcnow().isoformat()
    _save_listings(listings)

    return True, (
        f"✅ *Purchase Complete!*\n"
        f"{item_emoji} *{item_name}* ×{item_qty}\n"
        f"Paid: {price} 🪙\n"
        f"_{item_desc}_\n"
        f"Check your backpack."
    ), buyer_user


def cancel_listing(
    seller_user: dict,
    listing_id: str,
) -> Tuple[bool, str, dict]:
    """
    Seller cancels their listing. Item returned from escrow.
    """
    listings  = _load_listings()
    seller_id = seller_user.get("user_id", "")
    target    = None
    idx       = None

    for i, l in enumerate(listings):
        if l.get("listing_id") == listing_id:
            if l.get("seller_id") != seller_id:
                return False, "❌ That's not your listing.", seller_user
            if l.get("status") != "active":
                return False, "❌ Listing is no longer active.", seller_user
            target = l
            idx    = i
            break

    if not target:
        return False, "❌ Listing not found.", seller_user

    # Return item to inventory
    item_key  = target["item_key"]
    item_qty  = target["item_qty"]

    from supabase_db import add_inventory_item
    seller_user = add_inventory_item(
        seller_user, item_key, item_qty, target["item_name"],
        category=target.get("category", "misc"),
    )

    listings[idx]["status"] = "cancelled"
    _save_listings(listings)

    return True, (
        f"✅ Listing cancelled.\n"
        f"{target['item_emoji']} {target['item_name']} ×{item_qty} returned."
    ), seller_user


def use_exclusive_item(
    user: dict,
    item_key: str,
    target_player_id: str = None,
    target_sector_id: int = None,
    supabase=None,
    DB_TABLE: str = "players",
) -> Tuple[bool, str, dict]:
    """
    Use a Black Market exclusive item.
    Returns (success, message, updated_user)
    """
    from supabase_db import get_inventory_item
    item_row = get_inventory_item(user, item_key)
    have_qty = int(item_row.get("qty", item_row.get("quantity", 0)) or 0) if item_row else 0
    if have_qty < 1:
        return False, f"❌ No {item_key} in inventory.", user

    exclusive = EXCLUSIVE_ITEMS.get(item_key, {})
    if not exclusive:
        return False, "❌ Unknown item.", user

    result_msg = ""

    # ── Banishment Pardon ─────────────────────────────────────────────────
    if item_key == "banishment_pardon":
        bans = user.get("banishments", {}) or {}
        if not bans:
            return False, "❌ You have no active banishments to pardon.", user
        # Remove the first (soonest-expiring) non-war ban
        for sid_key, ban in list(bans.items()):
            if ban.get("issued_by_id") != "WAR_SYSTEM":
                del bans[sid_key]
                user["banishments"] = bans
                result_msg = (
                    f"📜 *Banishment Pardon used.*\n"
                    f"Banishment from Sector {sid_key} removed.\n"
                    f"You may now re-enter that sector."
                )
                break
        if not result_msg:
            return False, "❌ Only war-system bans remain. Pardons don't affect those.", user

    # ── Ghost Cloak ───────────────────────────────────────────────────────
    elif item_key == "ghost_cloak":
        duration = exclusive.get("duration_minutes", 120)
        expires  = (datetime.utcnow() + timedelta(minutes=duration)).isoformat()
        user["ghost_cloak_expires"] = expires
        result_msg = (
            f"👻 *Ghost Cloak active for {duration} minutes.*\n"
            f"You appear as 'Unknown Commander' to all players.\n"
            f"Bounty hunters cannot track you."
        )

    # ── Scammer Kit ───────────────────────────────────────────────────────
    elif item_key == "scammer_kit":
        loc = user.get("commander_location", {}) or {}
        if loc.get("sector_id") != 65:
            return False, "❌ Scammer Kit can only be used in the Crypto Wastes (Sector 65).", user
        duration = exclusive.get("duration_minutes", 10)
        expires  = (datetime.utcnow() + timedelta(minutes=duration)).isoformat()
        user["scammer_active_expires"] = expires
        result_msg = (
            f"🦹 *Scammer Kit activated for {duration} minutes!*\n"
            f"You are now stealing Satoshi from unprotected miners.\n"
            f"You appear as 🦹 on the sector map.\n"
            f"Loot goes directly to your inventory."
        )

    # ── Market Insider ────────────────────────────────────────────────────
    elif item_key == "market_insider":
        if not target_sector_id or not supabase:
            return False, "❌ Specify a target sector.", user
        try:
            r = supabase.table("sector_state").select(
                "sector_id, occupancy"
            ).eq("sector_id", target_sector_id).execute()
            if not r.data:
                return False, f"❌ No data for Sector {target_sector_id}.", user
            from supabase_db import safe_json
            occupancy = safe_json(r.data[0].get("occupancy"), default={})
            lines = [f"📊 *Sector {target_sector_id} — Insider Report*"]
            for occ_key, occ in occupancy.items():
                if isinstance(occ, dict):
                    pname   = occ.get("player_name", "?")
                    pending = int(occ.get("pending_resources", 0))
                    node_k  = occ_key.split(":")[-1] if ":" in occ_key else occ_key
                    lines.append(f"  Node {node_k}: @{pname} — {pending} resources pending")
            result_msg = "\n".join(lines)
        except Exception as e:
            return False, f"❌ Error: {e}", user

    # ── Commander's Echo ──────────────────────────────────────────────────
    elif item_key == "commanders_echo":
        if not target_player_id or not supabase:
            return False, "❌ Specify a target player to echo.", user
        try:
            r = supabase.table(DB_TABLE).select(
                "user_id, username, skill_points_spent"
            ).eq("user_id", target_player_id).execute()
            if not r.data:
                return False, "❌ Target player not found.", user
            from supabase_db import safe_json
            target_skills = safe_json(r.data[0].get("skill_points_spent"), default={})
            target_name   = r.data[0].get("username", "?")

            # Save current skills and apply target's
            user["echo_original_skills"] = user.get("skill_points_spent", {})
            user["skill_points_spent"]   = target_skills
            duration = exclusive.get("duration_minutes", 60)
            user["echo_expires"] = (
                datetime.utcnow() + timedelta(minutes=duration)
            ).isoformat()
            result_msg = (
                f"🪞 *Commander's Echo active!*\n"
                f"Copied @{target_name}'s skill tree for {duration} minutes.\n"
                f"Your original build restores automatically."
            )
        except Exception as e:
            return False, f"❌ Error: {e}", user

    else:
        result_msg = (
            f"✅ *{exclusive.get('display_name','Item')} used.*\n"
            f"Effect applied."
        )

    # Consume item
    from supabase_db import remove_inventory_item
    user = remove_inventory_item(user, item_key)

    return True, result_msg, user


def check_echo_expiry(user: dict) -> dict:
    """
    Check if Commander's Echo has expired and restore original skills.
    Call on every user load.
    """
    echo_expires = user.get("echo_expires")
    if not echo_expires:
        return user
    try:
        exp = datetime.fromisoformat(echo_expires)
        if datetime.utcnow() >= exp:
            original = user.get("echo_original_skills", {})
            if original:
                user["skill_points_spent"]  = original
                user["echo_original_skills"] = {}
            user.pop("echo_expires", None)
            user["pending_notification"] = (
                "🪞 *Commander's Echo expired.* Your original skill build has been restored."
            )
    except Exception:
        pass
    return user


# ═══════════════════════════════════════════════════════════════════════════
#  DISPLAY FORMATTERS
# ═══════════════════════════════════════════════════════════════════════════

def format_market_board(
    listings: List[dict],
    viewer_id: str,
    in_hidden_sector: bool = False,
) -> str:
    """Format the Black Market listing board."""
    lines = [
        "🕶️ *THE BLACK MARKET*",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    if not in_hidden_sector:
        lines.append(
            "⚠️ *Hidden sector access required.*\n"
            "Teleport to any sector 10-59 to browse and trade.\n"
            "You can still view listings from here."
        )

    if not listings:
        lines.append("\n_No active listings. Be the first to sell something._")
    else:
        for listing in listings[:15]:
            emoji     = listing.get("item_emoji", "📦")
            name      = listing.get("item_name", "?")
            qty       = listing.get("item_qty", 1)
            price     = listing.get("price_gold", 0)
            per_unit  = listing.get("price_per_unit", price)
            seller    = listing.get("seller_name", "?")
            lid       = listing.get("listing_id", "")
            is_excl   = listing.get("is_exclusive", False)
            is_mine   = listing.get("seller_id") == viewer_id
            sector    = listing.get("sector_id", "?")

            excl_tag  = " ⭐" if is_excl else ""
            mine_tag  = " *(yours)*" if is_mine else ""

            try:
                exp     = datetime.fromisoformat(listing.get("expires_at", ""))
                hrs_left = max(0, int((exp - datetime.utcnow()).total_seconds() // 3600))
                exp_str = f"{hrs_left}h"
            except Exception:
                exp_str = "?"

            lines.append(
                f"\n  {emoji} *{name}*{excl_tag}{mine_tag} ×{qty}\n"
                f"     💰 {price} 🪙 total  ({per_unit} 🪙 each)\n"
                f"     Seller: @{seller}  |  S{sector}  |  {exp_str}\n"
                f"     `{lid}`"
            )

    lines.append(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def format_exclusive_catalog() -> str:
    """Show the Black Market exclusive item catalog."""
    lines = [
        "⭐ *BLACK MARKET EXCLUSIVES*",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "_These items only exist here. You will not find them elsewhere._\n",
    ]

    rarity_order = {"legendary": 0, "rare": 1, "uncommon": 2}
    sorted_items = sorted(
        EXCLUSIVE_ITEMS.items(),
        key=lambda x: rarity_order.get(x[1].get("rarity", "uncommon"), 3)
    )

    for item_key, item in sorted_items:
        rarity = item.get("rarity", "uncommon")
        rarity_emoji = {"legendary": "🟥", "rare": "🟪", "uncommon": "🟦"}.get(rarity, "⬜")
        lines.append(
            f"{rarity_emoji} {item['emoji']} *{item['display_name']}*\n"
            f"  _{item['description']}_\n"
            f"  Est. price: ~{item['base_price']} 🪙  |  Rarity: {rarity}\n"
        )

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("_Prices set by sellers. Market decides._")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
#  INLINE KEYBOARDS
# ═══════════════════════════════════════════════════════════════════════════

def kb_market_main(in_hidden_sector: bool = False) -> InlineKeyboardMarkup:
    """Main Black Market keyboard."""
    buttons = [
        [
            InlineKeyboardButton(text="📋 All Listings",    callback_data="market:browse:all"),
            InlineKeyboardButton(text="⭐ Exclusives",      callback_data="market:exclusives"),
        ],
        [
            InlineKeyboardButton(text="📦 My Listings",     callback_data="market:my_listings"),
        ],
    ]

    if in_hidden_sector:
        buttons.append([
            InlineKeyboardButton(text="🏷️ List Item",       callback_data="market:list_item"),
        ])
    else:
        buttons.append([
            InlineKeyboardButton(
                text="⚠️ Need hidden sector to sell",
                callback_data="market:need_hidden"
            ),
        ])

    buttons.append([InlineKeyboardButton(text="⬅️ Back", callback_data="menu_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_listing_actions(
    listing: dict,
    viewer_id: str,
    in_hidden_sector: bool,
) -> InlineKeyboardMarkup:
    """Actions for a specific listing."""
    lid     = listing.get("listing_id", "")
    is_mine = listing.get("seller_id") == viewer_id
    buttons = []

    if is_mine:
        buttons.append([InlineKeyboardButton(
            text="🗑️ Cancel Listing",
            callback_data=f"market:cancel:{lid}"
        )])
    elif in_hidden_sector:
        price = listing.get("price_gold", 0)
        buttons.append([InlineKeyboardButton(
            text=f"💰 Buy for {price} 🪙",
            callback_data=f"market:buy:{lid}"
        )])
    else:
        buttons.append([InlineKeyboardButton(
            text="⚠️ Need hidden sector to buy",
            callback_data="market:need_hidden"
        )])

    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="market:browse:all")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)