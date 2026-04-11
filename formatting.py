"""
formatting.py — ULTRA-IMMERSIVE Dynamic UI & ASCII Art for The 64
==================================================================
Every display element crafted to pull players deeper into the world.
Consistent visual language across ALL players and ALL interactions.
"""

# ══════════════════════════════════════════════════════════════════
#  CORE DIVIDERS — Visual hierarchy foundation
# ══════════════════════════════════════════════════════════════════

def divider(char: str = "━", width: int = 32) -> str:
    return char * width

def thin_divider() -> str:
    return "─" * 32

def double_divider() -> str:
    return "═" * 32

def star_divider() -> str:
    return "✦ ─────────────────────── ✦"

def section_break() -> str:
    return "\n" + divider() + "\n"


# ══════════════════════════════════════════════════════════════════
#  PROGRESS BARS — Visceral feedback on growth
# ══════════════════════════════════════════════════════════════════

def progress_bar(current: int, max_val: int, width: int = 10,
                  filled_char: str = "█", empty_char: str = "░",
                  show_percent: bool = True) -> str:
    if max_val <= 0:
        pct = 0
        filled = 0
    else:
        pct = min(100, int((current / max_val) * 100))
        filled = int((current / max_val) * width)
    empty = width - filled
    bar = f"[{filled_char * filled}{empty_char * empty}]"
    return f"{bar} {pct}%" if show_percent else bar

def xp_bar(current_xp: int, xp_needed: int = 100) -> str:
    """XP bar with level display."""
    pct = min(100, int((current_xp / xp_needed) * 100))
    filled = int((current_xp / xp_needed) * 12)
    empty = 12 - filled
    bar = "▰" * filled + "▱" * empty
    return f"[{bar}] {current_xp}/{xp_needed} XP"

def health_bar(current: int, maximum: int) -> str:
    """Color-coded health using emoji blocks."""
    pct = current / maximum if maximum > 0 else 0
    width = 8
    filled = int(pct * width)
    if pct > 0.6:
        icon = "🟩"
    elif pct > 0.3:
        icon = "🟨"
    else:
        icon = "🟥"
    empty_icon = "⬛"
    return f"{icon * filled}{empty_icon * (width - filled)} {current}/{maximum}"

def troop_bar(current: int, max_troops: int) -> str:
    """Troop strength visual."""
    ratio = current / max_troops if max_troops > 0 else 0
    filled = int(ratio * 8)
    bar = "⚔️" * filled + "·" * (8 - filled)
    return f"[{bar}] {current:,}/{max_troops:,}"


# ══════════════════════════════════════════════════════════════════
#  HEADERS & TITLES — Command presence in every header
# ══════════════════════════════════════════════════════════════════

def page_header(title: str, subtitle: str = "", icon: str = "⚔️") -> str:
    line = double_divider()
    txt = f"{line}\n{icon} *{title.upper()}*"
    if subtitle:
        txt += f"\n_{subtitle}_"
    txt += f"\n{line}"
    return txt

def section_header(title: str, icon: str = "▸") -> str:
    return f"\n{icon} *{title}*\n{thin_divider()}"

def status_header(icon: str, title: str, status: str) -> str:
    return f"{icon} *{title}* — {status}"

def broadcast(title: str, message: str) -> str:
    return (
        f"📡 *BROADCAST — {title.upper()}*\n"
        f"{divider()}\n"
        f"{message}\n"
        f"{divider()}"
    )


# ══════════════════════════════════════════════════════════════════
#  INVENTORY DISPLAY — Grouped, clean, numbered
# ══════════════════════════════════════════════════════════════════

ITEM_EMOJIS = {
    "shield":           "🛡️",
    "shield_potion":    "🧪",
    "wood_crate":       "🪵",
    "bronze_crate":     "🟫",
    "iron_crate":       "⚙️",
    "super_crate":      "💎",
    "teleport":         "🌀",
    "free_teleport":    "🌀",
    "fireball":         "🔥",
    "mousetrap":        "🪤",
    "food_ration":      "🍖",
    "war_horn":         "📯",
    "spy_kit":          "🔭",
    "repair_kit":       "🔧",
    "legendary_artifact": "⚔️",
    "mythical_crown":   "👑",
    "void_stone":       "🌑",
    "eternal_flame":    "🔥",
    "celestial_key":    "🗝️",
}

ITEM_DISPLAY_NAMES = {
    "shield":           "War Shield",
    "shield_potion":    "Shield Potion",
    "wood_crate":       "Wood Crate",
    "bronze_crate":     "Bronze Crate",
    "iron_crate":       "Iron Crate",
    "super_crate":      "Super Crate",
    "teleport":         "Teleport Scroll",
    "free_teleport":    "Free Teleport",
    "fireball":         "Fireball",
    "mousetrap":        "Mousetrap",
    "food_ration":      "Food Ration",
    "war_horn":         "War Horn",
    "spy_kit":          "Spy Kit",
    "repair_kit":       "Repair Kit",
}

def group_items(items: list) -> dict:
    """Group a list of item dicts by type, keeping all IDs."""
    grouped = {}
    for item in items:
        itype = item.get("type", "unknown")
        # Strip 'locked_' prefix for display
        display_type = itype.replace("locked_", "")
        if display_type not in grouped:
            grouped[display_type] = {"count": 0, "ids": [], "sample": item}
        grouped[display_type]["count"] += 1
        grouped[display_type]["ids"].append(item.get("id"))
    return grouped

def format_grouped_inventory(items: list, slots_used: int, slots_total: int,
                               title: str = "🎒 INVENTORY") -> str:
    """
    Display inventory with all same-type items grouped together.
    Shows count and lets player choose to use one or all.
    """
    header = (
        f"{double_divider()}\n"
        f"{title}\n"
        f"📦 Slots: {slots_used}/{slots_total}  "
        f"{progress_bar(slots_used, slots_total, width=8, show_percent=False)}\n"
        f"{double_divider()}"
    )
    if not items:
        return header + "\n\n_Your backpack echoes with emptiness._\n\n_Use `!claims` to claim rewards._"

    grouped = group_items(items)
    lines = [header, ""]
    idx = 1
    for itype, data in grouped.items():
        emoji = ITEM_EMOJIS.get(itype, "📦")
        display = ITEM_DISPLAY_NAMES.get(itype, itype.replace("_", " ").title())
        count = data["count"]
        sample = data["sample"]
        xp = sample.get("xp_reward", 0)

        count_str = f"  ×{count}" if count > 1 else ""
        xp_str = f"  _(+{xp} XP)_" if xp else ""

        lines.append(f"`{idx}.` {emoji} *{display}*{count_str}{xp_str}")
        if count > 1:
            lines.append(f"     ├─ Use one: `!use {itype}`")
            lines.append(f"     └─ Use all: `!useall {itype}`")
        else:
            lines.append(f"     └─ Use: `!use {itype}`")
        idx += 1

    lines.append(f"\n{thin_divider()}")
    lines.append("💡 _Items stack. Use wisely — some expire._")
    return "\n".join(lines)

def format_grouped_unclaimed(items: list, title: str = "📬 UNCLAIMED REWARDS") -> str:
    """
    Display unclaimed items grouped by type.
    All items of same type appear once with a count.
    """
    header = (
        f"{double_divider()}\n"
        f"📬 *UNCLAIMED REWARDS*\n"
        f"_{len(items)} item(s) waiting for you_\n"
        f"{double_divider()}"
    )
    if not items:
        return header + "\n\n_No unclaimed rewards. Play to earn more!_"

    grouped = group_items(items)
    lines = [header, ""]
    idx = 1
    for itype, data in grouped.items():
        emoji = ITEM_EMOJIS.get(itype, "📦")
        display = ITEM_DISPLAY_NAMES.get(itype, itype.replace("_", " ").title())
        count = data["count"]
        sample = data["sample"]
        xp = sample.get("xp_reward", 0)
        first_id = data["ids"][0]

        count_str = f" ×{count}" if count > 1 else ""
        xp_str = f"  _(+{xp} XP each)_" if xp else ""

        lines.append(f"`{idx}.` {emoji} *{display}*{count_str}{xp_str}")
        if count > 1:
            lines.append(f"     ├─ Claim one: `!claim {first_id}`")
            lines.append(f"     └─ Claim all: `!claimall {itype}`")
        else:
            lines.append(f"     └─ `!claim {first_id}`")
        idx += 1

    lines.append(f"\n{thin_divider()}")
    lines.append("⚡ _Claim items to move them to your backpack._")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════
#  RESOURCE DISPLAY — Satisfying wealth visualization
# ══════════════════════════════════════════════════════════════════

RESOURCE_EMOJIS = {
    "wood":    "🪵",
    "bronze":  "🟫",
    "iron":    "⚙️",
    "diamond": "💎",
    "relics":  "🏺",
    "silver":  "🥈",
    "food":    "🍖",
}

def format_resources(resources: dict, food: int = 0, silver: int = 0) -> str:
    """Display resources in a clean, scannable format."""
    lines = []
    res_order = ["wood", "bronze", "iron", "diamond", "relics"]
    for res in res_order:
        amt = resources.get(res, 0)
        emoji = RESOURCE_EMOJIS.get(res, "📦")
        lines.append(f"  {emoji} {res.capitalize():<10} {amt:>6,}")
    if food:
        lines.append(f"  🍖 Food      {food:>9,}")
    if silver:
        lines.append(f"  🥈 Silver    {silver:>9,}")
    return "\n".join(lines)

def resource_change_line(resource: str, amount: int, prefix: str = "+") -> str:
    emoji = RESOURCE_EMOJIS.get(resource, "📦")
    sign = "+" if amount >= 0 else ""
    return f"  {emoji} {sign}{amount:,} {resource.capitalize()}"


# ══════════════════════════════════════════════════════════════════
#  BATTLE DISPLAYS — Drama in every clash
# ══════════════════════════════════════════════════════════════════

def battle_opener(attacker: str, defender: str, sector: str) -> str:
    return (
        f"⚔️ *BATTLE INITIATED*\n"
        f"{divider('═')}\n"
        f"🔴 *ATTACKER:* {attacker}\n"
        f"🔵 *DEFENDER:* {defender}\n"
        f"📍 *SECTOR:* {sector}\n"
        f"{divider('─')}\n"
        f"_Steel clashes. The sector holds its breath._\n"
        f"{divider('═')}"
    )

def battle_result(winner: str, loser: str, coins_stolen: int,
                   items: list = None, rounds: int = 0) -> str:
    result = (
        f"⚔️ *COMBAT REPORT*\n"
        f"{divider()}\n"
        f"🥇 *VICTOR:* {winner}\n"
        f"🥈 *DEFEATED:* {loser}\n"
        f"⏱️ *Rounds:* {rounds}\n"
        f"💰 *Plunder:* {coins_stolen:,} silver"
    )
    if items:
        result += f"\n📦 *Seized:* {', '.join(items)}"
    result += f"\n{divider()}"
    return result

def revenge_notification(attacker_name: str, hours_left: float) -> str:
    return (
        f"💢 *BLOOD DEBT ACTIVE*\n"
        f"{thin_divider()}\n"
        f"⚡ {attacker_name} humiliated you.\n"
        f"🕐 Revenge window: {hours_left:.0f}h remaining\n"
        f"🔥 Attack them now for *1.5× POWER*\n"
        f"{thin_divider()}\n"
        f"_Use `!attack @{attacker_name}` to claim your vengeance._"
    )

def attack_decision_screen(target_name: str, target_level: int,
                            enemy_troops: int, shield_status: str,
                            resources_at_stake: str,
                            is_revenge: bool = False) -> str:
    revenge_line = ""
    if is_revenge:
        revenge_line = "\n⚡ *REVENGE BONUS ACTIVE — 1.5× ATTACK POWER* ⚡\n"

    shield_line = "🛡️ ACTIVE — Fortified" if shield_status == "ACTIVE" else "❌ UNPROTECTED — Vulnerable"

    return (
        f"╔{'═'*34}╗\n"
        f"║  ⚔️  *DECISION POINT*  ⚔️       ║\n"
        f"╠{'═'*34}╣\n"
        f"║  🎯 Target: *{target_name[:18]:<18}*   ║\n"
        f"║  📊 Level:  {target_level:<22} ║\n"
        f"║  ⚔️  Troops: {enemy_troops:<21,} ║\n"
        f"║  🛡️  Shield: {shield_line[:20]:<20} ║\n"
        f"╠{'═'*34}╣\n"
        f"║  💰 At stake: {resources_at_stake[:18]:<18} ║\n"
        f"╚{'═'*34}╝"
        f"{revenge_line}\n"
        f"⚠️ _Once you attack, there is NO mercy._\n"
        f"└─ Confirm: `!attackconfirm @{target_name}`"
    )

def format_scout_report_display(target_name: str, military: dict, resources: dict,
                                  level: int, shield: str, lied: bool = False) -> str:
    lines = [
        f"🕵️ *INTELLIGENCE DOSSIER*",
        f"{divider('═')}",
        f"🎯 Target: *{target_name}* (Level {level})",
        f"🛡️ Shield: {shield}",
        f"{thin_divider()}",
    ]
    if military:
        lines.append("⚔️ *MILITARY FORCES:*")
        total = 0
        for unit, count in military.items():
            lines.append(f"  • {unit.capitalize()}: {count:,}")
            total += count
        lines.append(f"  ▸ Total: *{total:,} troops*")
    else:
        lines.append("⚔️ *MILITARY:* No troops detected")

    if resources:
        lines.append(f"{thin_divider()}")
        lines.append("💰 *BASE RESOURCES:*")
        for res, amt in resources.items():
            emoji = RESOURCE_EMOJIS.get(res, "📦")
            lines.append(f"  {emoji} {res.capitalize()}: {amt:,}")

    if lied:
        lines.append(f"\n{thin_divider()}")
        lines.append("⚠️ _Intel integrity: QUESTIONABLE (30% lie chance)_")

    lines.append(divider('═'))
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════
#  TRAINING & MILITARY DISPLAY
# ══════════════════════════════════════════════════════════════════

UNIT_EMOJIS = {
    "footmen":      "👹",
    "archers":      "🏹",
    "lancers":      "🗡️",
    "castellans":   "🏰",
    "pawns":        "👣",
    "militia":      "🪖",
    "soldier":      "⚔️",
    "knight":       "🛡️",
    "paladin":      "✝️",
    "warlord":      "💀",
}

def format_military_status(military: dict, food: int = 0, food_upkeep: float = 0) -> str:
    if not military or all(v == 0 for v in military.values()):
        return (
            f"⚔️ *MILITARY STATUS*\n"
            f"{thin_divider()}\n"
            f"_No troops stationed. Your base stands undefended._\n"
            f"Use `!train [unit] [amount]` to recruit."
        )
    lines = [
        f"⚔️ *MILITARY STATUS*",
        f"{divider()}",
    ]
    total = 0
    for unit, count in military.items():
        if count > 0:
            emoji = UNIT_EMOJIS.get(unit.lower(), "⚔️")
            lines.append(f"  {emoji} {unit.capitalize():<14} {count:>5,}")
            total += count
    lines.append(f"{thin_divider()}")
    lines.append(f"  ▸ Total Forces: *{total:,}*")
    if food_upkeep > 0:
        food_hours = int(food / food_upkeep) if food_upkeep > 0 else 0
        lines.append(f"  🍖 Food Remaining: {food:,}  _{food_hours}h supply_")
    return "\n".join(lines)

def format_training_queue(queue: list) -> str:
    from datetime import datetime
    if not queue:
        return "✅ *Training Queue:* Empty — all troops ready."

    lines = ["⚔️ *TRAINING IN PROGRESS*", thin_divider()]
    now = datetime.utcnow()

    for item in queue:
        unit = item.get("unit_type", "troops")
        amount = item.get("amount", 1)
        emoji = UNIT_EMOJIS.get(unit.lower(), "⚔️")
        try:
            completes = datetime.fromisoformat(item["completes_at"])
            remaining = max(0, (completes - now).total_seconds())
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            total_time = max(1, (completes - datetime.fromisoformat(item["started_at"])).total_seconds())
            elapsed = total_time - remaining
            pct = min(100, int((elapsed / total_time) * 100))
            bar_filled = int(pct / 10)
            bar = "█" * bar_filled + "░" * (10 - bar_filled)
            time_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
            lines.append(f"  {emoji} {amount}× {unit.capitalize()}")
            lines.append(f"     [{bar}] {pct}% — {time_str} left")
        except Exception:
            lines.append(f"  {emoji} {amount}× {unit.capitalize()} — _processing..._")

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════
#  PLAYER PROFILE — Deep identity display
# ══════════════════════════════════════════════════════════════════

def format_full_profile(profile: dict, military: dict = None) -> str:
    name = profile.get("username", "Unknown")
    level = profile.get("level", 1)
    xp = profile.get("xp", 0)
    xp_progress = profile.get("xp_progress", xp % 100)
    silver = profile.get("silver", 0)
    sector = profile.get("sector_display", "Unassigned")
    shield = "🛡️ PROTECTED" if profile.get("shielded") else "❌ EXPOSED"
    base_name = profile.get("base_name", "Unknown Base")
    resources = profile.get("base_resources", {})
    food = profile.get("base_food", 0)
    weekly = profile.get("weekly_points", 0)
    alltime = profile.get("all_time_points", 0)
    inv_count = profile.get("inventory_count", 0)
    slots = profile.get("backpack_slots", 5)
    unclaimed = profile.get("unclaimed_count", 0)

    # Rank icon by level
    if level >= 20:
        rank_icon = "👑"
    elif level >= 15:
        rank_icon = "💀"
    elif level >= 10:
        rank_icon = "🔥"
    elif level >= 5:
        rank_icon = "⚔️"
    else:
        rank_icon = "🪖"

    xp_bar_str = xp_bar(xp_progress, 100)

    lines = [
        f"{double_divider()}",
        f"{rank_icon} *{name.upper()}*",
        f"_{base_name}_",
        f"{double_divider()}",
        f"",
        f"📊 *STATS*",
        f"  Level   : {level}  {xp_bar_str}",
        f"  Silver  : {silver:,} 🥈",
        f"  Sector  : {sector}",
        f"  Shield  : {shield}",
        f"",
        f"🏆 *SCORE*",
        f"  Weekly  : {weekly:,} pts",
        f"  All-Time: {alltime:,} pts",
        f"",
        f"💰 *BASE RESOURCES*",
        format_resources(resources, food=food),
        f"",
        f"🎒 *BACKPACK* {inv_count}/{slots}",
    ]
    if unclaimed > 0:
        lines.append(f"  📬 {unclaimed} unclaimed reward(s) — `!claims`")
    if military:
        total_troops = sum(military.values())
        lines.append(f"")
        lines.append(f"⚔️ *ARMY* {total_troops:,} troops")
        for unit, count in military.items():
            if count > 0:
                emoji = UNIT_EMOJIS.get(unit.lower(), "⚔️")
                lines.append(f"  {emoji} {unit.capitalize()}: {count:,}")

    lines.append(f"{double_divider()}")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════
#  EVENT BANNERS — Announcements that demand attention
# ══════════════════════════════════════════════════════════════════

def level_up_announcement(name: str, level: int, bonus_item: str = None) -> str:
    rank = "LEGEND" if level >= 20 else "VETERAN" if level >= 10 else "WARRIOR"
    lines = [
        f"🎊 *LEVEL UP!*",
        f"{divider('═')}",
        f"🎉 *{name}* reached *LEVEL {level}*",
        f"🏷️ New Title: _{rank}_",
    ]
    if bonus_item:
        lines.append(f"🎁 Bonus: {bonus_item}")
    lines.append(divider('═'))
    return "\n".join(lines)

def territory_claimed(territory: str, claimer: str, benefits: str = "") -> str:
    lines = [
        f"🚩 *TERRITORY CLAIMED*",
        f"{divider()}",
        f"*{territory.upper()}* now under {claimer}",
    ]
    if benefits:
        lines += [thin_divider(), f"💎 Benefits: {benefits}"]
    lines.append(divider())
    return "\n".join(lines)

def shield_status_visual(status: str, remaining_time: str = "") -> str:
    if status == "ACTIVE":
        return "🛡️ *ACTIVE* — _All attacks deflected_"
    elif status == "DISRUPTED":
        return "⚡ *DISRUPTED* — _1 attack exposed_"
    elif status == "INACTIVE":
        rt = f"Cooldown: {remaining_time}" if remaining_time else "Ready to activate"
        return f"❌ *INACTIVE* — _{rt}_"
    return "❓ *UNKNOWN*"

def round_start_header(word1: str, word2: str, round_num: int = None,
                        sector: str = None, score_mult: float = 1.0) -> str:
    mult_str = f"  ×{score_mult:.1f} pts/word" if score_mult != 1.0 else ""
    header = f"🃏 *NEW ROUND*\n{divider()}\n"
    if round_num:
        header += f"Round #{round_num}\n"
    if sector:
        header += f"📍 Sector: {sector}{mult_str}\n"
    header += (
        f"\n📝 *FUSION WORD PAIR*\n"
        f"`{word1.upper()}` + `{word2.upper()}`\n"
        f"{divider()}\n"
        f"⏱️ *120 SECONDS* — Go.\n"
    )
    return header

def round_end_summary(top_scores: list, total_rounds: int = None) -> str:
    result = f"🏆 *ROUND COMPLETE*\n{divider()}\n"
    medals = ["🥇", "🥈", "🥉"]
    for i, (name, pts) in enumerate(top_scores[:3]):
        medal = medals[i] if i < 3 else f"{i+1}."
        result += f"{medal} *{name}* — {pts} pts\n"
    result += divider()
    if total_rounds:
        result += f"\n📊 Total Rounds: {total_rounds}"
    return result

def warning_box(warning: str) -> str:
    return (
        f"⚠️ *WARNING*\n"
        f"{thin_divider()}\n"
        f"{warning}\n"
        f"{thin_divider()}"
    )

def countdown_timer(seconds_remaining: int) -> str:
    if seconds_remaining > 60:
        display = f"{seconds_remaining // 60}m {seconds_remaining % 60}s"
    else:
        display = f"{seconds_remaining}s"
    if seconds_remaining <= 30:
        return f"⏰ *{display}* ⚠️ FINAL COUNTDOWN!"
    elif seconds_remaining <= 60:
        return f"⏱️ *{display}* — Hurry!"
    return f"⏳ *{display}*"

def sector_status(sector_name: str, resource: str, resource_emoji: str,
                   price_change: str, overlord: str) -> str:
    return (
        f"{divider('━', 32)}\n"
        f"📡 *SCANNING SECTORS...*\n"
        f"{divider('━', 32)}\n\n"
        f"{resource_emoji} *{resource}* floods *{sector_name}*.\n"
        f"📈 *MARKET:* Silver is {price_change}.\n"
        f"👑 *Overlord:* {overlord}\n\n"
        f"{divider('━', 32)}"
    )

def power_display(user_name: str, power: int, bonus: int = 0) -> str:
    icon = "⚔️" if power < 500 else "🔥" if power < 1000 else "👑"
    modifier = f" (+{bonus})" if bonus > 0 else ""
    return f"{icon} *{user_name}* — Power: {power:,}{modifier}"

def separator(icon: str = "━") -> str:
    return icon * 32

def faction_banner(faction_name: str, members: int, power: int) -> str:
    return (
        f"🚩 *{faction_name.upper()}*\n"
        f"{divider()}\n"
        f"👥 Members: {members}\n"
        f"⚔️ Power: {power:,}\n"
        f"{divider()}"
    )

def achievement_unlocked(achievement: str, reward: str) -> str:
    return (
        f"🏅 *ACHIEVEMENT UNLOCKED!*\n"
        f"{divider()}\n"
        f"_{achievement}_\n"
        f"🎁 Reward: {reward}\n"
        f"{divider()}"
    )

def military_deployment(unit_type: str, count: int, target: str = None,
                          rank_required: int = None) -> str:
    deploy = f"⚔️ *DEPLOYMENT*\n{thin_divider()}\n"
    deploy += f"📋 {count}× {unit_type}\n"
    if rank_required:
        deploy += f"🎖️ Rank Required: {rank_required}\n"
    if target:
        deploy += f"🎯 Target: {target}\n"
    return deploy

def loading_bar(message: str = "LOADING...", steps: int = 5, current_step: int = 3) -> str:
    filled = "⬛" * current_step
    empty = "⬜" * (steps - current_step)
    return f"[{filled}{empty}] {message}"

# ══════════════════════════════════════════════════════════════════
#  GAMEMASTER DIALOGUE — Voice of authority
# ══════════════════════════════════════════════════════════════════

def gamemaster_says(message: str, mood: str = "neutral") -> str:
    """Wrap a message as a GameMaster quote."""
    mood_prefix = {
        "neutral": "🃏",
        "impressed": "🃏 ✨",
        "angry": "🃏 💢",
        "cryptic": "🃏 🌑",
        "encouraging": "🃏 ⚡",
        "warning": "🃏 ⚠️",
    }.get(mood, "🃏")
    return f"{mood_prefix} *GameMaster:* \"{message}\""

def help_tip(command: str, description: str) -> str:
    return f"  `{command}` — {description}"
