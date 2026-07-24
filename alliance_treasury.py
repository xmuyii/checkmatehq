# -*- coding: utf-8 -*-
"""
alliance_treasury.py — Alliance Treasury System
=================================================
The financial backbone of every alliance. Members deposit resources
and gold, the treasury funds upgrades, war bonuses, and the alliance shop.

TREASURY MECHANICS:
  Members can deposit gold, resources, or AP to the treasury.
  Leaders can spend from the treasury on:
    - Alliance shop restocks (suits at 20% discount for members)
    - War bonuses (temporary +% power for all members)
    - Settlement contributions (growing the private sector)
    - Alliance upgrades (increase member cap, unlock features)

ALLIANCE SHOP:
  Leader uses treasury to stock the shop.
  Members buy from the shop at discount vs the main store.
  Shop resets weekly unless restocked.

ALLIANCE TIERS (funded by AP):
  Tier 1 — Pact       (5 members)   — 0 AP
  Tier 2 — Brotherhood (10 members) — 500 AP
  Tier 3 — Legion     (20 members)  — 2000 AP
  Tier 4 — Dominion   (35 members)  — 5000 AP
  Tier 5 — Empire     (50 members)  — 10000 AP
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import json

ALLIANCE_TIERS = {
    1: {"name": "Pact",        "emoji": "🤝", "max_members": 5,  "ap_required": 0,     "power_bonus": 0.00},
    2: {"name": "Brotherhood", "emoji": "⚔️", "max_members": 10, "ap_required": 500,   "power_bonus": 0.05},
    3: {"name": "Legion",      "emoji": "🛡️", "max_members": 20, "ap_required": 2000,  "power_bonus": 0.10},
    4: {"name": "Dominion",    "emoji": "👑", "max_members": 35, "ap_required": 5000,  "power_bonus": 0.15},
    5: {"name": "Empire",      "emoji": "🌟", "max_members": 50, "ap_required": 10000, "power_bonus": 0.20},
}

TREASURY_SPEND_OPTIONS = {
    "restock_suits": {
        "name":  "🧪 Restock Alliance Shop (Suits)",
        "desc":  "Stock 5× Basic + 3× Hazmat + 1× Void suits for members at 20% discount.",
        "cost":  {"gold": 800},
        "effect": "restock_suits",
    },
    "war_bonus": {
        "name":  "⚔️ War Power Bonus (2h)",
        "desc":  "All members get +20% power for 2 hours.",
        "cost":  {"gold": 1500},
        "effect": "war_power_bonus",
        "duration_hours": 2,
    },
    "shield_members": {
        "name":  "🛡️ Shield All Members (4h)",
        "desc":  "Give every member a 4-hour base shield.",
        "cost":  {"gold": 2000},
        "effect": "shield_members",
        "duration_hours": 4,
    },
    "upgrade_tier": {
        "name":  "⬆️ Upgrade Alliance Tier",
        "desc":  "Spend AP to unlock the next alliance tier.",
        "cost":  {"ap": 0},   # Set dynamically based on current tier
        "effect": "upgrade_tier",
    },
    "speedup_pack": {
        "name":  "⏩ Buy Speedup Pack for Treasury",
        "desc":  "Add 10× 30-minute speedups to the alliance shop.",
        "cost":  {"gold": 500},
        "effect": "restock_speedups",
    },
}

# ═══════════════════════════════════════════════════════════════════════════
#  TREASURY MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

def get_treasury(alliance: dict) -> dict:
    t = alliance.get("treasury", {})
    if not isinstance(t, dict):
        t = {}
    t.setdefault("gold", 0)
    t.setdefault("resources", {})
    t.setdefault("ap_reserve", 0)
    return t


def deposit_gold(
    alliance: dict,
    user: dict,
    amount: int,
) -> Tuple[bool, str, dict, dict]:
    """
    Member deposits gold into the treasury.
    Returns (success, message, updated_user, updated_alliance)
    """
    if amount <= 0:
        return False, "❌ Amount must be positive.", user, alliance

    gold = user.get("gold", 0) or 0

    if gold < amount:
        return False, f"❌ You only have {gold} 🪙.", user, alliance

    # Deduct from user
    user["gold"] = gold - amount

    # Add to treasury
    treasury = get_treasury(alliance)
    treasury["gold"] = treasury.get("gold", 0) + amount
    alliance["treasury"] = treasury

    # Log the contribution
    contrib = alliance.get("contributions", []) or []
    contrib.insert(0, {
        "player_id":   user.get("user_id", ""),
        "player_name": user.get("username", "?"),
        "type":        "gold",
        "amount":      amount,
        "timestamp":   datetime.utcnow().isoformat(),
    })
    alliance["contributions"] = contrib[:50]

    return True, (
        f"💰 Deposited *{amount} 🪙* to alliance treasury.\n"
        f"Treasury total: {treasury['gold']} 🪙"
    ), user, alliance


def deposit_resources(
    alliance: dict,
    user: dict,
    resource_key: str,
    amount: int,
) -> Tuple[bool, str, dict, dict]:
    """Member deposits resources into the treasury."""
    base_res  = user.get("base_resources", {}) or {}
    resources = base_res.get("resources", {}) or {}
    have      = resources.get(resource_key, 0)

    if amount <= 0:
        return False, "❌ Amount must be positive.", user, alliance
    if have < amount:
        return False, f"❌ Only have {have} {resource_key}.", user, alliance

    resources[resource_key] = have - amount
    base_res["resources"]   = resources
    user["base_resources"]  = base_res

    treasury = get_treasury(alliance)
    tres_res = treasury.get("resources", {})
    tres_res[resource_key] = tres_res.get(resource_key, 0) + amount
    treasury["resources"]  = tres_res
    alliance["treasury"]   = treasury

    # Record contribution toward alliance missions
    try:
        from alliance_missions import record_mission_progress
        alliance, completed = record_mission_progress(
            alliance, user.get("user_id", ""),
            "contribute_treasury", amount, resource=resource_key
        )
    except Exception:
        pass

    return True, (
        f"📦 Deposited *{amount} {resource_key}* to treasury."
    ), user, alliance


def spend_treasury(
    alliance: dict,
    leader_user: dict,
    spend_key: str,
    supabase=None,
    DB_TABLE: str = "players",
    bot=None,
) -> Tuple[bool, str, dict]:
    """
    Leader spends from treasury.
    Returns (success, message, updated_alliance)
    """
    role = leader_user.get("alliance_role", "MEMBER")
    if role not in ("LEADER", "OFFICER"):
        return False, "❌ Only leaders and officers can spend treasury funds.", alliance

    option   = TREASURY_SPEND_OPTIONS.get(spend_key)
    if not option:
        return False, "❌ Invalid spending option.", alliance

    treasury = get_treasury(alliance)
    cost     = dict(option["cost"])

    # Dynamic AP cost for tier upgrade
    if spend_key == "upgrade_tier":
        current_tier = _get_alliance_tier(alliance)
        if current_tier >= 5:
            return False, "❌ Alliance already at maximum tier (Empire).", alliance
        next_tier_data = ALLIANCE_TIERS.get(current_tier + 1, {})
        cost = {"ap": next_tier_data.get("ap_required", 9999)}

    # Check treasury balance
    for currency, amount in cost.items():
        if currency == "gold":
            if treasury.get("gold", 0) < amount:
                return False, (
                    f"❌ Treasury needs {amount} 🪙. Has {treasury.get('gold',0)} 🪙."
                ), alliance
        elif currency == "ap":
            ap = alliance.get("alliance_points", 0)
            if ap < amount:
                return False, (
                    f"❌ Alliance needs {amount} AP. Has {ap} AP."
                ), alliance

    # Deduct
    for currency, amount in cost.items():
        if currency == "gold":
            treasury["gold"] = treasury.get("gold", 0) - amount
        elif currency == "ap":
            alliance["alliance_points"] = alliance.get("alliance_points", 0) - amount

    alliance["treasury"] = treasury
    effect = option["effect"]
    msg    = ""

    # Apply effect
    if effect == "restock_suits":
        shop = alliance.get("alliance_shop", {}) or {}
        shop["basic_suit"]   = shop.get("basic_suit", 0) + 5
        shop["hazmat_suit"]  = shop.get("hazmat_suit", 0) + 3
        shop["void_suit"]    = shop.get("void_suit", 0) + 1
        shop["restocked_at"] = datetime.utcnow().isoformat()
        alliance["alliance_shop"] = shop
        msg = (
            "🧪 *Alliance Shop restocked!*\n"
            "Members can now buy suits at 20% discount."
        )

    elif effect == "restock_speedups":
        shop = alliance.get("alliance_shop", {}) or {}
        shop["speedup_30m"]  = shop.get("speedup_30m", 0) + 10
        shop["restocked_at"] = datetime.utcnow().isoformat()
        alliance["alliance_shop"] = shop
        msg = "⏩ *10× 30m speedups added to alliance shop!*"

    elif effect == "war_power_bonus":
        hours  = option.get("duration_hours", 2)
        exp    = (datetime.utcnow() + timedelta(hours=hours)).isoformat()
        buffs  = alliance.get("active_buffs", {}) or {}
        buffs["war_power_bonus"]          = 500   # Power value added to all members
        buffs["war_power_bonus_expires"]  = exp
        alliance["active_buffs"] = buffs
        msg = f"⚔️ *+20% power bonus active for {hours} hours* for all members!"

    elif effect == "shield_members":
        hours  = option.get("duration_hours", 4)
        if supabase and DB_TABLE:
            members = alliance.get("members", [])
            exp     = (datetime.utcnow() + timedelta(hours=hours)).isoformat()
            for pid in members:
                try:
                    supabase.table(DB_TABLE).update({
                        "base_shielded":    True,
                        "shield_expires_at": exp,
                    }).eq("user_id", pid).execute()
                except Exception:
                    pass
        msg = f"🛡️ *4-hour shields granted to all {len(alliance.get('members',[]))} members!*"

    elif effect == "upgrade_tier":
        current_tier = _get_alliance_tier(alliance)
        new_tier     = current_tier + 1
        tier_data    = ALLIANCE_TIERS.get(new_tier, {})
        alliance["tier"]           = new_tier
        alliance["tier_name"]      = tier_data.get("name", "?")
        alliance["max_members"]    = tier_data.get("max_members", 5)
        alliance["power_bonus_pct"] = tier_data.get("power_bonus", 0)
        msg = (
            f"🎉 *Alliance upgraded to {tier_data.get('emoji','')} "
            f"{tier_data.get('name','')}!*\n"
            f"Max members: {tier_data.get('max_members',5)}\n"
            f"Power bonus: +{int(tier_data.get('power_bonus',0)*100)}% for all members"
        )

    return True, msg, alliance


def buy_from_alliance_shop(
    alliance: dict,
    user: dict,
    item_key: str,
) -> Tuple[bool, str, dict, dict]:
    """
    Member buys an item from the alliance shop at 20% discount.
    Returns (success, message, updated_user, updated_alliance)
    """
    shop = alliance.get("alliance_shop", {}) or {}
    if shop.get(item_key, 0) <= 0:
        return False, f"❌ {item_key} is out of stock in the alliance shop.", user, alliance

    # Get price from store_system (20% discount)
    try:
        from store_system import STORE_ITEMS, purchase_item
        base_item = STORE_ITEMS.get(item_key, {})
        if not base_item:
            return False, "❌ Unknown item.", user, alliance

        # Apply 20% discount
        discounted = dict(base_item)
        discounted["price"] = max(1, int(base_item["price"] * 0.80))
        discounted["name"]  = f"[Alliance] {base_item['name']}"

        # Temporarily patch price
        from store_system import STORE_ITEMS as SI
        orig_price    = SI[item_key]["price"]
        SI[item_key]["price"] = discounted["price"]

        ok, msg, user = purchase_item(user, item_key)

        SI[item_key]["price"] = orig_price   # Restore

    except Exception as e:
        return False, f"❌ Shop error: {e}", user, alliance

    if ok:
        shop[item_key] = shop[item_key] - 1
        alliance["alliance_shop"] = shop
        msg = f"🛍️ Bought from alliance shop (20% off)!\n{msg}"

    return ok, msg, user, alliance


def _get_alliance_tier(alliance: dict) -> int:
    return min(5, max(1, int(alliance.get("tier", 1) or 1)))


# ═══════════════════════════════════════════════════════════════════════════
#  DISPLAY FORMATTERS
# ═══════════════════════════════════════════════════════════════════════════

def format_treasury(alliance: dict, is_leader: bool = False) -> str:
    treasury = get_treasury(alliance)
    tier     = _get_alliance_tier(alliance)
    tier_data = ALLIANCE_TIERS.get(tier, ALLIANCE_TIERS[1])
    ap       = alliance.get("alliance_points", 0)
    members  = len(alliance.get("members", []))

    lines = [
        f"🏦 *ALLIANCE TREASURY*",
        f"━━━━━━━━━━━━━━━━━━━━━━━━",
        f"{tier_data['emoji']} *{tier_data['name']}* (Tier {tier})",
        f"Members: {members}/{tier_data['max_members']}",
        f"Power Bonus: +{int(tier_data['power_bonus']*100)}%",
        f"",
        f"💰 Gold: *{treasury.get('gold',0):,} 🪙*",
        f"🏆 Alliance Points: *{ap:,}*",
    ]

    res = treasury.get("resources", {})
    if res:
        lines.append("\n📦 *Stored Resources:*")
        for rkey, amt in res.items():
            if amt > 0:
                lines.append(f"  {rkey}: {amt:,}")

    # Alliance shop stock
    shop = alliance.get("alliance_shop", {}) or {}
    if any(v > 0 for v in shop.values() if isinstance(v, int)):
        lines.append("\n🛍️ *Alliance Shop (20% off):*")
        for ikey, qty in shop.items():
            if isinstance(qty, int) and qty > 0:
                try:
                    from store_system import STORE_ITEMS
                    item = STORE_ITEMS.get(ikey, {})
                    name = item.get("name", ikey)
                    orig = item.get("price", 0)
                    disc = max(1, int(orig * 0.80))
                    lines.append(f"  {name} ×{qty} — {disc} 🪙 (was {orig})")
                except Exception:
                    lines.append(f"  {ikey}: {qty}")

    # Active buffs
    buffs = alliance.get("active_buffs", {}) or {}
    if buffs.get("war_power_bonus"):
        exp_str = buffs.get("war_power_bonus_expires", "?")
        try:
            exp     = datetime.fromisoformat(exp_str)
            rem     = max(0, (exp - datetime.utcnow()).total_seconds())
            h, m    = divmod(int(rem // 60), 60)
            time_str = f"{h}h {m}m"
        except Exception:
            time_str = "?"
        lines.append(f"\n⚔️ *War Bonus Active:* +20% power ({time_str})")

    # Recent contributions
    contribs = alliance.get("contributions", [])[:5]
    if contribs:
        lines.append("\n📋 *Recent Contributions:*")
        for c in contribs:
            name = c.get("player_name", "?")
            amt  = c.get("amount", 0)
            ctype = c.get("type", "?")
            lines.append(f"  @{name}: +{amt} {ctype}")

    if is_leader:
        lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("_Tap Treasury Actions to spend._")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def format_alliance_shop(alliance: dict) -> str:
    shop = alliance.get("alliance_shop", {}) or {}
    stocked = {k: v for k, v in shop.items()
               if isinstance(v, int) and v > 0}

    lines = ["🛍️ *ALLIANCE SHOP*\n━━━━━━━━━━━━━━━━━━━━━━━━"]

    if not stocked:
        lines.append(
            "_Shop is empty._\n"
            "Ask your alliance leader to restock using treasury funds."
        )
    else:
        lines.append("_All items 20% cheaper than the main store._\n")
        for ikey, qty in stocked.items():
            try:
                from store_system import STORE_ITEMS
                item = STORE_ITEMS.get(ikey, {})
                name = item.get("name", ikey)
                orig = item.get("price", 0)
                disc = max(1, int(orig * 0.80))
                curr = {"gold": "🪙", "bitcoin": "₿"}.get(item.get("currency","gold"), "🪙")
                lines.append(f"  {name} ×{qty} — {disc}{curr} _(was {orig})_")
            except Exception:
                lines.append(f"  {ikey}: {qty}")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
#  KEYBOARDS
# ═══════════════════════════════════════════════════════════════════════════

def kb_treasury(alliance: dict, user: dict) -> InlineKeyboardMarkup:
    is_leader = user.get("alliance_role") in ("LEADER", "OFFICER")
    buttons   = [
        [
            InlineKeyboardButton("💰 Deposit Gold",      callback_data="treasury:deposit_gold"),
            InlineKeyboardButton("📦 Deposit Resources", callback_data="treasury:deposit_res"),
        ],
        [
            InlineKeyboardButton("🛍️ Alliance Shop",     callback_data="treasury:shop"),
        ],
    ]
    if is_leader:
        buttons.append([
            InlineKeyboardButton("💸 Treasury Actions",  callback_data="treasury:spend_menu"),
            InlineKeyboardButton("⬆️ Upgrade Tier",      callback_data="treasury:spend:upgrade_tier"),
        ])
    buttons.append([InlineKeyboardButton("⬅️ Alliance", callback_data="menu_guild")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_spend_menu() -> InlineKeyboardMarkup:
    buttons = []
    for key, opt in TREASURY_SPEND_OPTIONS.items():
        cost_str = " + ".join(f"{v} {k}" for k, v in opt["cost"].items())
        buttons.append([InlineKeyboardButton(
            text=f"{opt['name']} [{cost_str}]",
            callback_data=f"treasury:spend:{key}"
        )])
    buttons.append([InlineKeyboardButton("⬅️ Treasury", callback_data="treasury:view")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_alliance_shop(alliance: dict) -> InlineKeyboardMarkup:
    shop    = alliance.get("alliance_shop", {}) or {}
    stocked = {k: v for k, v in shop.items()
               if isinstance(v, int) and v > 0}
    buttons = []
    for ikey, qty in stocked.items():
        try:
            from store_system import STORE_ITEMS
            item = STORE_ITEMS.get(ikey, {})
            name = item.get("name", ikey)
            disc = max(1, int(item.get("price", 0) * 0.80))
            buttons.append([InlineKeyboardButton(
                text=f"Buy {name} ({disc}🪙) ×{qty} left",
                callback_data=f"treasury:buy:{ikey}"
            )])
        except Exception:
            pass
    buttons.append([InlineKeyboardButton("⬅️ Treasury", callback_data="treasury:view")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)