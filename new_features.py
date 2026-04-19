# -*- coding: utf-8 -*-
"""
new_features.py — New Game Features (April 2026)
================================================
Guild system, command-based shopping, daily quests, sector resources, and vault system
"""

import time
import random
from datetime import datetime

# ─── GUILD / ALLIANCE MENU ───

def setup_guild_handlers(dp, _cmd, types, InlineKeyboardMarkup, InlineKeyboardButton, get_user, save_user):
    """Setup guild menu handlers"""
    
    @dp.callback_query(lambda q: q.data == "menu_guild")
    async def cb_menu_guild(callback: types.CallbackQuery):
        """Show guild/alliance menu."""
        u_id = str(callback.from_user.id)
        user = get_user(u_id)
        
        if not user:
            await callback.answer("User not found", show_alert=True)
            return
        
        guild = user.get("guild", {})
        guild_name = guild.get("name", "No Guild")
        guild_rank = guild.get("rank", "N/A")
        guild_members = guild.get("members", [])
        
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 View Guild", callback_data="guild_view")],
            [InlineKeyboardButton(text="👥 Members", callback_data="guild_members")],
            [InlineKeyboardButton(text="💳 Guild Treasury", callback_data="guild_treasury")],
            [InlineKeyboardButton(text="⚔️ Guild Wars", callback_data="guild_wars")],
            [InlineKeyboardButton(text="⬅️ Back", callback_data="menu_back")],
        ])
        
        await callback.message.edit_text(
            f"⚔️ *GUILD / ALLIANCE* ⚔️\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"**Guild:** {guild_name}\n"
            f"**Your Rank:** {guild_rank}\n"
            f"**Members:** {len(guild_members)}\n\n"
            f"_Unite with allies and dominate together._\n"
            f"━━━━━━━━━━━━━━━━━━━━",
            parse_mode="Markdown",
            reply_markup=markup
        )
        await callback.answer()


# ─── COMMAND-BASED SHOPPING SYSTEM ───

def get_shop_items():
    """Get all purchasable items with prices."""
    items = {
        # RESOURCES
        "wood": {"name": "🌲 Wood", "price": 10, "category": "resource"},
        "bronze": {"name": "🧱 Bronze", "price": 20, "category": "resource"},
        "iron": {"name": "⛓️ Iron", "price": 50, "category": "resource"},
        "diamond": {"name": "💎 Diamond", "price": 100, "category": "resource"},
        
        # SHIELDS
        "basic_shield": {"name": "🛡️ Basic Shield", "price": 500, "category": "shield", "effect": "10% damage reduction"},
        "iron_shield": {"name": "⚔️ Iron Shield", "price": 1500, "category": "shield", "effect": "25% damage reduction"},
        "legendary_shield": {"name": "💥 Legendary Shield", "price": 5000, "category": "shield", "effect": "50% damage reduction"},
        
        # WEAPONS (from weapon_system.py)
        "machine_gun_turret": {"name": "🔫 Machine Gun Turret", "price": 1000, "category": "weapon"},
        "plasma_cannon": {"name": "⚡ Plasma Cannon", "price": 2500, "category": "weapon"},
        "emp_blast": {"name": "💥 EMP Blast", "price": 800, "category": "weapon"},
        "xp_siphon": {"name": "🔋 XP Siphon", "price": 1200, "category": "weapon"},
        "silver_siphon": {"name": "💰 Silver Siphon", "price": 1500, "category": "weapon"},
        "resource_drain": {"name": "🌀 Resource Drain", "price": 2000, "category": "weapon"},
        
        # TRAPS
        "spike_trap": {"name": "🗡️ Spike Trap", "price": 300, "category": "trap"},
        "fire_trap": {"name": "🔥 Fire Trap", "price": 600, "category": "trap"},
        "poison_trap": {"name": "☠️ Poison Trap", "price": 800, "category": "trap"},
        "tesla_coil": {"name": "⚡ Tesla Coil", "price": 1500, "category": "trap"},
        
        # PERKS / BUFFS
        "2x_resources": {"name": "2️⃣ 2x Resources (1hr)", "price": 250, "category": "buff", "duration": 3600},
        "3x_xp": {"name": "💫 3x XP (1hr)", "price": 400, "category": "buff", "duration": 3600},
        "lucky_boost": {"name": "🍀 Lucky Boost (1hr)", "price": 350, "category": "buff", "duration": 3600},
        "speed_boost": {"name": "⚡ Speed Boost (1hr)", "price": 300, "category": "buff", "duration": 3600},
    }
    return items


def setup_buy_command(dp, _cmd, types, get_user, save_user):
    """Setup /buy command handler"""
    
    @dp.message(_cmd("buy"))
    async def cmd_buy(message: types.Message):
        """Buy items from shop. Usage: /buy <item> <quantity>"""
        if message.chat.type != "private":
            await message.answer("❌ Shopping only in DMs. Use `/buy` in private.", parse_mode="Markdown")
            return
        
        u_id = str(message.from_user.id)
        user = get_user(u_id)
        
        if not user:
            await message.answer("❌ User not registered. Use `/start` first.", parse_mode="Markdown")
            return
        
        # Parse command: /buy wood 100
        parts = message.text.strip().lstrip("/!buy").strip().split()
        if len(parts) < 2:
            shop_items = get_shop_items()
            items_list = ""
            for key, info in list(shop_items.items())[:15]:
                items_list += f"{info['name']}: {info['price']} bitcoin\n"
            
            await message.answer(
                f"🛍️ *SHOP*\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"**Available Items:**\n{items_list}\n"
                f"_Usage: `/buy wood 100`_\n"
                f"━━━━━━━━━━━━━━━━━━━━",
                parse_mode="Markdown"
            )
            return
        
        item_name = parts[0].lower()
        try:
            quantity = int(parts[1])
        except ValueError:
            await message.answer("❌ Invalid quantity. Usage: `/buy wood 100`", parse_mode="Markdown")
            return
        
        if quantity <= 0:
            await message.answer("❌ Quantity must be positive.", parse_mode="Markdown")
            return
        
        shop_items = get_shop_items()
        if item_name not in shop_items:
            await message.answer(f"❌ Item '{item_name}' not found.", parse_mode="Markdown")
            return
        
        item_info = shop_items[item_name]
        total_cost = item_info["price"] * quantity
        bitcoin = user.get("bitcoin", 0)
        
        if bitcoin < total_cost:
            await message.answer(
                f"❌ Insufficient Bitcoin!\n\n"
                f"**Item:** {item_info['name']}\n"
                f"**Price:** {item_info['price']} per unit\n"
                f"**Quantity:** {quantity}\n"
                f"**Total Cost:** {total_cost:,}\n"
                f"**You Have:** {bitcoin:,}\n"
                f"**Needed:** {total_cost - bitcoin:,} more",
                parse_mode="Markdown"
            )
            return
        
        # Process purchase
        user["bitcoin"] -= total_cost
        
        # Add to inventory based on type
        if "inventory" not in user:
            user["inventory"] = []
        
        if item_info["category"] in ["shield", "weapon", "trap", "buff"]:
            user["inventory"].append({
                "id": item_name,
                "name": item_info["name"],
                "quantity": quantity,
                "purchased_at": int(time.time()),
                "category": item_info["category"]
            })
        elif item_info["category"] == "resource":
            # Add to resources
            if "base_resources" not in user:
                user["base_resources"] = {"resources": {}, "food": 0}
            if "resources" not in user["base_resources"]:
                user["base_resources"]["resources"] = {}
            
            user["base_resources"]["resources"][item_name] = user["base_resources"]["resources"].get(item_name, 0) + quantity
        
        save_user(u_id, user)
        
        await message.answer(
            f"✅ *Purchase Successful!*\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"**Item:** {item_info['name']}\n"
            f"**Quantity:** {quantity}\n"
            f"**Cost:** {total_cost:,} bitcoin\n"
            f"**New Balance:** {user['bitcoin']:,} bitcoin\n"
            f"━━━━━━━━━━━━━━━━━━━━",
            parse_mode="Markdown"
        )


# ─── DAILY QUESTS SYSTEM ───

def generate_daily_quests():
    """Generate 3-5 random daily quests."""
    quests = [
        {"id": "word_master", "name": "Word Master", "description": "Form 20 words in FUSION", "reward": {"bitcoin": 500, "gold": 0}, "progress": 0, "target": 20},
        {"id": "xp_seeker", "name": "XP Seeker", "description": "Earn 1000 XP", "reward": {"bitcoin": 300, "gold": 1}, "progress": 0, "target": 1000},
        {"id": "chess_champion", "name": "Chess Champion", "description": "Win 3 chess games", "reward": {"bitcoin": 600, "gold": 0}, "progress": 0, "target": 3},
        {"id": "treasure_hunter", "name": "Treasure Hunter", "description": "Collect 500 wood", "reward": {"bitcoin": 200, "gold": 0}, "progress": 0, "target": 500},
        {"id": "raid_expert", "name": "Raid Expert", "description": "Raid 5 bases", "reward": {"bitcoin": 400, "gold": 0}, "progress": 0, "target": 5},
    ]
    random.shuffle(quests)
    return quests[:4]


def setup_quests_command(dp, _cmd, types, get_user):
    """Setup /quests command"""
    
    @dp.message(_cmd("quests"))
    async def cmd_quests(message: types.Message):
        """Show daily quests."""
        if message.chat.type != "private":
            await message.answer("❌ Check quests in DMs. Use `/quests`", parse_mode="Markdown")
            return
        
        u_id = str(message.from_user.id)
        user = get_user(u_id)
        
        if not user:
            await message.answer("❌ User not registered.", parse_mode="Markdown")
            return
        
        quests = user.get("daily_quests", [])
        
        if not quests:
            await message.answer(
                "🎯 *DAILY QUESTS*\n\n"
                "_No quests today. Come back later!_",
                parse_mode="Markdown"
            )
            return
        
        quest_text = "🎯 *DAILY QUESTS*\n\n━━━━━━━━━━━━━━━━━━━━\n"
        for i, quest in enumerate(quests, 1):
            progress = quest.get("progress", 0)
            target = quest.get("target", 1)
            pct = int((progress / target) * 100)
            reward_bitcoin = quest.get("reward", {}).get("bitcoin", 0)
            reward_gold = quest.get("reward", {}).get("gold", 0)
            
            quest_text += f"**{i}. {quest['name']}**\n"
            quest_text += f"   {quest['description']}\n"
            quest_text += f"   Progress: {progress}/{target} ({pct}%)\n"
            quest_text += f"   Reward: {reward_bitcoin} bitcoin, {reward_gold} gold\n\n"
        
        quest_text += "━━━━━━━━━━━━━━━━━━━━"
        
        await message.answer(quest_text, parse_mode="Markdown")


# ─── SECTOR-SPECIFIC RESOURCES ───

SECTOR_RESOURCE_BONUSES = {
    1: {"resource": "wood", "bonus": 5},
    2: {"resource": "bronze", "bonus": 4},
    3: {"resource": "iron", "bonus": 3},
    4: {"resource": "diamond", "bonus": 7},
    5: {"resource": "gold", "bonus": 1},
    6: {"resource": "wood", "bonus": 8},
    7: {"resource": "iron", "bonus": 6},
    8: {"resource": "iron", "bonus": 10},
    9: {"resource": "diamond", "bonus": 4},
    10: {"resource": "bronze", "bonus": 9},
}

def get_sector_resource_bonus(sector_id: int, word_length: int) -> dict:
    """Get resource bonus for current sector when player forms a word."""
    bonus_info = SECTOR_RESOURCE_BONUSES.get(sector_id, {"resource": "wood", "bonus": 1})
    resource = bonus_info["resource"]
    base_bonus = bonus_info["bonus"]
    
    # Longer words = more resources
    amount = base_bonus * word_length
    
    return {resource: amount}


# ─── MONEY SYSTEM (BITCOIN + GOLD + VAULT) ───

def convert_silver_to_gold(user_id, silver_amount: int, get_user, save_user) -> bool:
    """Convert silver to gold at 1000:1 ratio. Gold cannot be stolen."""
    user = get_user(user_id)
    if not user:
        return False
    
    silver = user.get("silver", 0)
    if silver < silver_amount:
        return False
    
    gold_gained = silver_amount // 1000
    user["silver"] -= silver_amount
    user["gold"] = user.get("gold", 0) + gold_gained
    save_user(user_id, user)
    return True


def setup_vault_command(dp, _cmd, types, get_user, save_user):
    """Setup /vault command"""
    
    @dp.message(_cmd("vault"))
    async def cmd_vault(message: types.Message):
        """Manage vault (deposit money safely)."""
        if message.chat.type != "private":
            await message.answer("❌ Manage vault in DMs. Use `/vault`", parse_mode="Markdown")
            return
        
        u_id = str(message.from_user.id)
        user = get_user(u_id)
        
        if not user:
            await message.answer("❌ User not registered.", parse_mode="Markdown")
            return
        
        parts = message.text.strip().lstrip("/!vault").strip().split()
        
        if not parts or parts[0] == "status":
            vault = user.get("vault", {"bitcoin": 0, "gold": 0})
            player_bitcoin = user.get("bitcoin", 0)
            player_gold = user.get("gold", 0)
            
            await message.answer(
                f"🏦 *VAULT*\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"**Vault (Safe Storage):**\n"
                f"  💳 Bitcoin: {vault.get('bitcoin', 0):,}\n"
                f"  👑 Gold: {vault.get('gold', 0)}\n\n"
                f"**Account (Can be stolen):**\n"
                f"  💳 Bitcoin: {player_bitcoin:,}\n"
                f"  👑 Gold: {player_gold} (Cannot be stolen)\n\n"
                f"_Usage: `/vault deposit bitcoin 500`_\n"
                f"_Usage: `/vault withdraw gold 10`_\n"
                f"━━━━━━━━━━━━━━━━━━━━",
                parse_mode="Markdown"
            )
            return
        
        if len(parts) < 3:
            await message.answer("❌ Usage: `/vault deposit bitcoin 500`", parse_mode="Markdown")
            return
        
        action = parts[0].lower()
        currency = parts[1].lower()
        try:
            amount = int(parts[2])
        except ValueError:
            await message.answer("❌ Invalid amount.", parse_mode="Markdown")
            return
        
        if amount <= 0 or currency not in ["bitcoin", "gold"]:
            await message.answer("❌ Amount must be positive and currency must be 'bitcoin' or 'gold'.", parse_mode="Markdown")
            return
        
        vault = user.get("vault", {"bitcoin": 0, "gold": 0})
        
        if action == "deposit":
            player_amount = user.get(currency, 0)
            if player_amount < amount:
                await message.answer(f"❌ You only have {player_amount} {currency}.", parse_mode="Markdown")
                return
            
            user[currency] -= amount
            vault[currency] = vault.get(currency, 0) + amount
            user["vault"] = vault
            save_user(u_id, user)
            
            await message.answer(
                f"✅ *Deposited {amount} {currency} to vault.*\n\n"
                f"Your new safe balance: {vault[currency]:,}",
                parse_mode="Markdown"
            )
        
        elif action == "withdraw":
            vault_amount = vault.get(currency, 0)
            if vault_amount < amount:
                await message.answer(f"❌ Vault only has {vault_amount} {currency}.", parse_mode="Markdown")
                return
            
            user[currency] = user.get(currency, 0) + amount
            vault[currency] -= amount
            user["vault"] = vault
            save_user(u_id, user)
            
            await message.answer(
                f"✅ *Withdrew {amount} {currency} from vault.*",
                parse_mode="Markdown"
            )
        
        else:
            await message.answer("❌ Action must be 'deposit' or 'withdraw'.", parse_mode="Markdown")


# ─── CHESS INTEGRATION ───

def setup_chess_command(dp, _cmd, types, get_user, save_user):
    """Setup /chess command"""
    
    @dp.message(_cmd("chess"))
    async def cmd_chess(message: types.Message):
        """Start a chess game via Lichess API."""
        if message.chat.type == "private":
            await message.answer("🎮 Type `!chess` in the **group** to challenge someone.", parse_mode="Markdown")
            return
        
        u_id = str(message.from_user.id)
        user = get_user(u_id)
        
        if not user:
            await message.answer("❌ Player not registered. Use `/start` in DM.", parse_mode="Markdown")
            return
        
        await message.answer(
            f"♟️ *CHESS CHALLENGE*\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"**{user.get('username')} challenges!**\n\n"
            f"🔗 [Play on Lichess](https://lichess.org)\n\n"
            f"_First to choose white/black will be recorded!_\n"
            f"━━━━━━━━━━━━━━━━━━━━",
            parse_mode="Markdown"
        )
        
        if "chess_games" not in user:
            user["chess_games"] = []
        user["chess_games"].append({
            "initiated_at": int(time.time()),
            "initiator_id": u_id,
            "status": "waiting"
        })
        save_user(u_id, user)
