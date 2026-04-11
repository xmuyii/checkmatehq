"""
formatting.py — Dynamic UI & ASCII Art for Checkmate HQ
========================================================
Makes the game FEEL alive with visual feedback, progress bars, and dynamic announcements.
"""

def progress_bar(current: int, max_val: int, width: int = 5, filled_char: str = "⬛", empty_char: str = "⬜") -> str:
    """Generate a visual progress bar. E.g.: [ ⬛⬛⬛⬜⬜ ] 60%"""
    if max_val == 0:
        percentage = 0
    else:
        percentage = int((current / max_val) * 100)
    
    filled = int((current / max_val) * width) if max_val > 0 else 0
    empty = width - filled
    bar = f"[ {filled_char * filled}{empty_char * empty} ]"
    return f"{bar} {percentage}%"


def divider(char: str = "━", width: int = 30) -> str:
    """Create a clean divider line."""
    return char * width


def broadcast(title: str, message: str) -> str:
    """Format a broadcast/alert message."""
    return (
        f"📡 *BROADCAST*\n"
        f"{divider()}\n"
        f"*{title.upper()}*\n"
        f"{message}\n"
        f"{divider()}"
    )


def event_box(icon: str, title: str, details: str) -> str:
    """Format an event notification."""
    return (
        f"{icon} *{title}*\n"
        f"├─ {details}"
    )


def status_header(icon: str, title: str, status: str) -> str:
    """Format a status header with icon."""
    return f"{icon} *{title}* — {status}"


def power_display(user_name: str, power: int, bonus: int = 0) -> str:
    """Display power level with visual feedback."""
    icon = "⚔️" if power < 500 else "🔥" if power < 1000 else "👑"
    modifier = f" (+{bonus})" if bonus > 0 else ""
    return f"{icon} *{user_name}* — Power: {power}{modifier}"


def battle_result(winner: str, loser: str, coins_stolen: int, items: list = None) -> str:
    """Format a battle result announcement."""
    result = (
        f"⚔️ *COMBAT REPORT*\n"
        f"{divider()}\n"
        f"🥇 *VICTOR:* {winner}\n"
        f"🥈 *DEFEATED:* {loser}\n"
        f"💰 *LOOT:* {coins_stolen} coins stolen"
    )
    if items:
        result += f"\n📦 *ITEMS:* {', '.join(items)}"
    result += f"\n{divider()}"
    return result


def shield_status_visual(status: str, remaining_time: str = "") -> str:
    """Visual shield status indicator."""
    if status == "ACTIVE":
        return f"🛡️ *ACTIVE* _(Protected)_"
    elif status == "DISRUPTED":
        return f"⚡ *DISRUPTED* _(1 attack remaining)_"
    elif status == "INACTIVE":
        if remaining_time:
            return f"❌ *INACTIVE* _(Cooldown: {remaining_time})_"
        return f"❌ *INACTIVE* _(Ready to activate)_"
    return f"❓ *UNKNOWN*"


def round_start_header(word1: str, word2: str, round_num: int = None) -> str:
    """Dramatic round start message."""
    header = f"🃏 *NEW ROUND*\n{divider()}\n"
    if round_num:
        header += f"Round #{round_num}\n\n"
    header += (
        f"📝 *FUSION WORD PAIR*\n"
        f"`{word1.upper()}` + `{word2.upper()}`\n"
        f"{divider()}\n"
        f"⏱️ *120 SECONDS* — Go.\n"
    )
    return header


def round_end_summary(top_scores: list, total_rounds: int = None) -> str:
    """Dramatic round end with leaderboard."""
    result = f"🏆 *ROUND COMPLETE*\n{divider()}\n"
    
    medals = ["🥇", "🥈", "🥉"]
    for i, (name, pts) in enumerate(top_scores[:3]):
        medal = medals[i] if i < 3 else f"{i+1}."
        result += f"{medal} {name} — {pts} pts\n"
    
    result += divider()
    if total_rounds:
        result += f"\n📊 Total Rounds Played: {total_rounds}"
    
    return result


def level_up_announcement(name: str, level: int, bonus_item: str = None) -> str:
    """Level-up celebration."""
    announcement = (
        f"🎊 *LEVEL UP!*\n"
        f"{divider()}\n"
        f"🎉 {name} reached *LEVEL {level}*\n"
    )
    if bonus_item:
        announcement += f"📦 Bonus: {bonus_item}\n"
    announcement += f"{divider()}"
    return announcement


def territory_claimed(territory: str, claimer: str, benefits: str = "") -> str:
    """Territory capture announcement."""
    announcement = (
        f"🚩 *TERRITORY CLAIMED*\n"
        f"{divider()}\n"
        f"{territory.upper()} is now controlled by {claimer}\n"
    )
    if benefits:
        announcement += f"━━━━━━━━━━━━━━━\n💎 Benefits: {benefits}\n"
    announcement += divider()
    return announcement


def military_deployment(unit_type: str, count: int, target: str = None, rank_required: int = None) -> str:
    """Military deployment announcement."""
    deploy = f"⚔️ *MILITARY DEPLOYMENT*\n{divider()}\n"
    deploy += f"📋 Unit: {count}x {unit_type}\n"
    if rank_required:
        deploy += f"🎖️ Rank Required: {rank_required}\n"
    if target:
        deploy += f"🎯 Target: {target}\n"
    deploy += divider()
    return deploy


def warning_box(warning: str) -> str:
    """Format a warning message."""
    return (
        f"⚠️ *WARNING*\n"
        f"{divider()}\n"
        f"{warning}\n"
        f"{divider()}"
    )


def loading_bar(message: str = "LOADING...", steps: int = 5, current_step: int = 3) -> str:
    """Show loading progress."""
    filled = "⬛" * current_step
    empty = "⬜" * (steps - current_step)
    return f"[ {filled}{empty} ] {message}"


def separator(icon: str = "━") -> str:
    """Fancy divider."""
    return icon * 35


def faction_banner(faction_name: str, members: int, power: int) -> str:
    """Display faction/alliance banner."""
    return (
        f"🚩 *{faction_name.upper()}* FACTION\n"
        f"{divider()}\n"
        f"👥 Members: {members}\n"
        f"⚔️ Combined Power: {power}\n"
        f"{divider()}"
    )


def achievement_unlocked(achievement: str, reward: str) -> str:
    """Achievement announcement."""
    return (
        f"🏅 *ACHIEVEMENT UNLOCKED!*\n"
        f"{divider()}\n"
        f"_{achievement}_\n"
        f"🎁 Reward: {reward}\n"
        f"{divider()}"
    )


def countdown_timer(seconds_remaining: int) -> str:
    """Dramatic countdown display."""
    if seconds_remaining > 60:
        display = f"{seconds_remaining // 60}m {seconds_remaining % 60}s"
    else:
        display = f"{seconds_remaining}s"
    
    if seconds_remaining <= 30:
        return f"⏰ *{display}* ⚠️ TIME RUNNING OUT!"
    elif seconds_remaining <= 60:
        return f"⏱️ *{display}* — Hurry!"
    else:
        return f"⏳ *{display}*"


def sector_status(sector_name: str, resource: str, resource_emoji: str, price_change: str, overlord: str) -> str:
    """Generate hourly sector status broadcast to keep chat alive."""
    return (
        f"{divider('━', 35)}\n"
        f"📡 *SCANNING SECTORS...*\n"
        f"{divider('━', 35)}\n\n"
        f"{resource_emoji} *{resource}* is plentiful in *{sector_name}*.\n"
        f"📈 *MARKET UPDATE:* Silver is {price_change}.\n"
        f"👑 *Current Overlord:* {overlord}\n\n"
        f"{divider('━', 35)}"
    )


# Example usage in game events
EXAMPLE_MESSAGES = {
    "round_start": round_start_header("FUSION", "COMBAT", round_num=42),
    "round_end": round_end_summary([("AlphaPlayer", 450), ("BetaPlayer", 380), ("GammaPlayer", 320)]),
    "level_up": level_up_announcement("DarkKnight", 15, "Super Crate"),
    "broadcast": broadcast("ZONE B CAPTURED", "[SECTOR 8] has claimed territory"),
    "military": military_deployment("LANCER", 2, "Enemy Base", rank_required=20),
    "battle": battle_result("DragonSlayer", "FallenKnight", 2500, ["Gold Helm", "Shield"]),
    "shield": warning_box("Your shield will deactivate in 2 hours. Prepare for war."),
}
