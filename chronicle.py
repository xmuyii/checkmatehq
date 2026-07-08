# -*- coding: utf-8 -*-
"""
chronicle.py — The Commander's Chronicle
=========================================
A weekly auto-generated server newspaper summarising the biggest
events, top performers, ruler changes, notable battles, and
Gamemaster commentary. Published every Monday at 00:00 UTC.

SECTIONS:
  1. Opening dispatch (Gamemaster voice)
  2. The Week in Numbers (server stats)
  3. Sector Report (ruler changes, dominance shifts)
  4. Top Commanders (XP, kills, resources, dominance)
  5. Alliance Standings (AP, war record)
  6. The Bounty Files (top hunters, biggest bounties)
  7. Notable Events (Void collapses, rug pulls, fortress captures)
  8. Closing dispatch (Gamemaster flavour)

DELIVERY:
  Sent as a DM to every player active in the last 7 days.
  Also pinned in the main group chat.
  Stored in chronicle_history.json for reference.

TONE:
  Written as the Gamemaster — a strategic AI narrator.
  Dry wit. Military dispatch style. Never neutral.
  The Chronicle remembers everything and respects nothing.
"""

import json
import os
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

CHRONICLE_FILE   = "chronicle_history.json"
CHRONICLE_WEEK_FILE = "chronicle_current_week.json"

# ═══════════════════════════════════════════════════════════════════════════
#  DATA COLLECTION
# ═══════════════════════════════════════════════════════════════════════════

def collect_weekly_data(supabase, DB_TABLE: str = "players") -> dict:
    """
    Pull all data needed for the Chronicle from the database.
    Called once at Chronicle generation time.
    """
    now    = datetime.utcnow()
    week_start = (now - timedelta(days=7)).isoformat()
    data   = {
        "generated_at": now.isoformat(),
        "week_start":   week_start,
        "players":      [],
        "alliances":    {},
        "sector_rulers":[],
        "bounties":     [],
        "war_history":  None,
        "total_battles": 0,
        "total_resources_collected": 0,
    }

    # Active players this week
    try:
        r = supabase.table(DB_TABLE).select(
            "user_id, username, level, xp, military, dominance_scores, "
            "hunter_kills, hunter_earnings, is_bounty_hunter, "
            "alliance_id, prestige, last_active, inventory, base_resources"
        ).gte("last_active", week_start).execute()
        data["players"] = r.data or []
    except Exception as e:
        print(f"[CHRONICLE] Player fetch error: {e}")

    # Alliances
    try:
        with open("alliances.json") as f:
            data["alliances"] = json.load(f)
    except Exception:
        data["alliances"] = {}

    # Sector rulers from sector_state
    try:
        rs = supabase.table("sector_state").select(
            "sector_id, dominance"
        ).execute()
        for row in (rs.data or []):
            sid = row.get("sector_id")
            dom = row.get("dominance", {})
            if not isinstance(dom, dict):
                try:
                    dom = json.loads(dom) if dom else {}
                except Exception:
                    dom = {}
            ruler_id   = dom.get("ruler_id")
            ruler_name = dom.get("ruler_name")
            if ruler_id and ruler_name:
                data["sector_rulers"].append({
                    "sector_id":   sid,
                    "ruler_id":    ruler_id,
                    "ruler_name":  ruler_name,
                    "cycle_score": dom.get("cycle_score", 0),
                })
    except Exception as e:
        print(f"[CHRONICLE] Sector state error: {e}")

    # Bounties this week
    try:
        rb = supabase.table("bounty_board").select("*").gte(
            "posted_at", week_start
        ).execute()
        data["bounties"] = rb.data or []
    except Exception:
        data["bounties"] = []

    # War history
    try:
        if os.path.exists("sector_war.json"):
            with open("sector_war.json") as f:
                war = json.load(f)
            if war.get("status") == "completed":
                data["war_history"] = war
    except Exception:
        pass

    return data


def _compute_stats(data: dict) -> dict:
    """Compute derived statistics from raw data."""
    players  = data.get("players", [])
    bounties = data.get("bounties", [])

    stats = {
        "active_players":    len(players),
        "total_kills":       sum(p.get("hunter_kills", 0) for p in players),
        "total_bounties":    len(bounties),
        "bounties_claimed":  sum(1 for b in bounties if b.get("status") == "claimed"),
        "total_gold_bounties": sum(b.get("reward_gold", 0) for b in bounties),

        # Top by XP gained
        "top_xp": sorted(
            [p for p in players if p.get("username")],
            key=lambda x: x.get("xp", 0), reverse=True
        )[:5],

        # Top by kills
        "top_hunters": sorted(
            [p for p in players if p.get("is_bounty_hunter") and p.get("hunter_kills", 0) > 0],
            key=lambda x: x.get("hunter_kills", 0), reverse=True
        )[:5],

        # Top by dominance total
        "top_dominance": sorted(
            [p for p in players if p.get("dominance_scores")],
            key=lambda x: sum(
                v for v in (x.get("dominance_scores") or {}).values()
                if isinstance(v, (int, float))
            ),
            reverse=True
        )[:5],

        # Top hunters by earnings
        "top_earners": sorted(
            [p for p in players if p.get("hunter_earnings", 0) > 0],
            key=lambda x: x.get("hunter_earnings", 0), reverse=True
        )[:3],

        # Highest value bounty claimed this week
        "biggest_bounty": max(
            (b for b in bounties if b.get("status") == "claimed"),
            key=lambda b: b.get("reward_gold", 0),
            default=None
        ),
    }

    # Alliance standings
    alliances = data.get("alliances", {})
    alliance_list = []
    for aid, a in alliances.items():
        ap       = a.get("alliance_points", 0)
        members  = len(a.get("members", []))
        name     = a.get("name", "?")
        alliance_list.append({"id": aid, "name": name, "ap": ap, "members": members})

    stats["top_alliances"] = sorted(
        alliance_list, key=lambda x: x["ap"], reverse=True
    )[:5]

    return stats


# ═══════════════════════════════════════════════════════════════════════════
#  CHRONICLE GENERATION
# ═══════════════════════════════════════════════════════════════════════════

# Gamemaster voice lines for the Chronicle
OPENING_DISPATCHES = [
    "Another week logged in the annals of Zero Dominus. The Commander has reviewed the records. Here is what mattered.",
    "Seven days. Countless battles. One Chronicle. The strong are noted. The dead are remembered. The cowardly are not mentioned.",
    "The week is over. The Chronicle begins. What follows is the official record of who did what, and what it cost them.",
    "Commanders. The weekly debrief is ready. Read it. Learn from it. The next seven days will not be forgiving.",
    "Zero Dominus does not forget. The Chronicle remembers every move made this week. Every kill. Every surrender. Every fortune lost to a rug pull.",
]

CLOSING_DISPATCHES = [
    "That is the week. The Commander expects more next time. Dismissed.",
    "The Chronicle is complete. Resume operations. There are sectors to control and enemies to dismantle.",
    "Seven more days begin now. The Chronicle will be watching. Make them count.",
    "End of weekly dispatch. The strong will be stronger. The weak will find reasons. Neither matters to the Chronicle.",
    "The record is sealed. What you do this week will appear in the next one. Choose accordingly.",
]

RULER_FLAVOUR = [
    "holds the throne with an iron grip",
    "rules from a position of total dominance",
    "sits unchallenged — so far",
    "claimed the throne and hasn't looked back",
    "rules with the confidence of someone who knows where your base is",
]

NO_RULER_FLAVOUR = [
    "remains ungoverned — an opportunity for the bold",
    "has no ruler. A power vacuum. Someone should fix that.",
    "is contested territory. No clear winner yet.",
]


def generate_chronicle(data: dict) -> str:
    """
    Generate the full Chronicle text from collected data.
    Returns a formatted Markdown string ready to send.
    """
    stats      = _compute_stats(data)
    now        = datetime.utcnow()
    week_num   = now.isocalendar()[1]
    year       = now.year

    lines = []

    # ── HEADER ────────────────────────────────────────────────────────────
    lines += [
        f"📰 *THE COMMANDER'S CHRONICLE*",
        f"*Week {week_num}, {year}*",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"",
        f"_{random.choice(OPENING_DISPATCHES)}_",
        f"",
    ]

    # ── SECTION 1: THE WEEK IN NUMBERS ────────────────────────────────────
    lines += [
        f"📊 *THE WEEK IN NUMBERS*",
        f"━━━━━━━━━━━━━━━━━━━━━━━━",
        f"  👤 Active Commanders: *{stats['active_players']}*",
        f"  ⚔️ Bounty Kills: *{stats['total_kills']}*",
        f"  🎯 Bounties Posted: *{stats['total_bounties']}*",
        f"  💰 Gold Paid in Bounties: *{stats['total_gold_bounties']:,} 🪙*",
        f"  🏹 Bounties Claimed: *{stats['bounties_claimed']}*",
        f"",
    ]

    # ── SECTION 2: SECTOR REPORT ──────────────────────────────────────────
    lines += [
        f"🌍 *SECTOR REPORT*",
        f"━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    rulers = data.get("sector_rulers", [])
    if rulers:
        from teleport_system import SECTOR_QUICK_INFO
        for r in sorted(rulers, key=lambda x: x.get("sector_id", 0))[:10]:
            sid        = r.get("sector_id")
            ruler_name = r.get("ruler_name", "Unknown")
            score      = r.get("cycle_score", 0)
            try:
                info   = SECTOR_QUICK_INFO.get(sid, {})
                sname  = info.get("name", f"Sector {sid}")
                semoji = info.get("emoji", "🌍")
            except Exception:
                sname  = f"Sector {sid}"
                semoji = "🌍"
            flavour = random.choice(RULER_FLAVOUR)
            lines.append(
                f"  {semoji} *{sname}* — @{ruler_name} {flavour} ({score} pts)"
            )
    else:
        lines.append("  _No sector rulers recorded this week._")

    lines.append("")

    # ── SECTION 3: TOP COMMANDERS ─────────────────────────────────────────
    lines += [
        f"🎖️ *TOP COMMANDERS*",
        f"━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    if stats["top_xp"]:
        lines.append("*By Experience:*")
        for i, p in enumerate(stats["top_xp"][:3]):
            medal = ["🥇", "🥈", "🥉"][i]
            lines.append(
                f"  {medal} @{p.get('username','?')} — "
                f"Level {p.get('level',1)}, {p.get('xp',0):,} XP"
            )

    if stats["top_dominance"]:
        lines.append("\n*By Sector Dominance:*")
        for i, p in enumerate(stats["top_dominance"][:3]):
            medal  = ["🥇", "🥈", "🥉"][i]
            dom    = p.get("dominance_scores", {})
            if not isinstance(dom, dict):
                dom = {}
            total_dom = sum(v for v in dom.values() if isinstance(v, (int, float)))
            lines.append(
                f"  {medal} @{p.get('username','?')} — {int(total_dom):,} dominance pts"
            )

    lines.append("")

    # ── SECTION 4: ALLIANCE STANDINGS ─────────────────────────────────────
    lines += [
        f"👥 *ALLIANCE STANDINGS*",
        f"━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    if stats["top_alliances"]:
        for i, a in enumerate(stats["top_alliances"]):
            medal = ["🥇", "🥈", "🥉", "4.", "5."][i]
            lines.append(
                f"  {medal} *{a['name']}* — {a['ap']:,} AP  |  {a['members']} members"
            )
    else:
        lines.append("  _No alliances recorded._")

    lines.append("")

    # ── SECTION 5: THE BOUNTY FILES ───────────────────────────────────────
    lines += [
        f"💀 *THE BOUNTY FILES*",
        f"━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    if stats["top_hunters"]:
        lines.append("*Top Hunters This Week:*")
        for i, p in enumerate(stats["top_hunters"][:3]):
            medal = ["🥇", "🥈", "🥉"][i]
            lines.append(
                f"  {medal} @{p.get('username','?')} — "
                f"{p.get('hunter_kills',0)} kills, "
                f"{p.get('hunter_earnings',0):,} 🪙 earned"
            )
    else:
        lines.append("  _No bounty kills recorded this week._\n  _The hunters slept. The targets are grateful._")

    biggest = stats.get("biggest_bounty")
    if biggest:
        lines.append(
            f"\n*Biggest Claimed Bounty:*\n"
            f"  💰 @{biggest.get('claimed_by_name','?')} collected "
            f"{biggest.get('reward_gold',0):,} 🪙 from "
            f"@{biggest.get('target_name','?')}"
        )

    lines.append("")

    # ── SECTION 6: NOTABLE EVENTS ─────────────────────────────────────────
    lines += [
        f"📋 *NOTABLE EVENTS*",
        f"━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    events_noted = False

    # War result
    war = data.get("war_history")
    if war and war.get("status") == "completed":
        from sector_war import format_war_history
        lines.append(format_war_history(war))
        events_noted = True

    # Sector War active
    try:
        from sector_war import get_active_war
        active_war = get_active_war()
        if active_war:
            a_name = active_war.get("alliance_a_name", "?")
            b_name = active_war.get("alliance_b_name", "?")
            score_a = active_war.get("score_a", 0)
            score_b = active_war.get("score_b", 0)
            lines.append(
                f"⚔️ *Sector War in progress:* {a_name} vs {b_name}\n"
                f"   Score: {score_a:,} — {score_b:,}"
            )
            events_noted = True
    except Exception:
        pass

    if not events_noted:
        events_noted_lines = [
            "_A quiet week. Suspiciously quiet._",
            "_No major events recorded. Either nothing happened or someone deleted the evidence._",
            "_The sectors were calm. This never lasts._",
        ]
        lines.append(random.choice(events_noted_lines))

    lines.append("")

    # ── CLOSING ───────────────────────────────────────────────────────────
    lines += [
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"_{random.choice(CLOSING_DISPATCHES)}_",
        f"",
        f"📰 *The Commander's Chronicle*  |  Week {week_num}",
    ]

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
#  DELIVERY
# ═══════════════════════════════════════════════════════════════════════════

async def publish_chronicle(bot, supabase, DB_TABLE: str = "players",
                             group_chat_id: int = None) -> int:
    """
    Generate and deliver the Chronicle to all active players.
    Also posts to the main group chat.
    Returns count of players notified.
    """
    import asyncio

    print("[CHRONICLE] Generating weekly Chronicle...")
    data       = collect_weekly_data(supabase, DB_TABLE)
    chronicle  = generate_chronicle(data)

    # Save to history
    _save_chronicle(chronicle, data)

    sent = 0
    cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()

    try:
        r = supabase.table(DB_TABLE).select("user_id").gte(
            "last_active", cutoff
        ).execute()
        players = r.data or []

        for p in players:
            uid = p.get("user_id")
            if not uid:
                continue
            try:
                await bot.send_message(
                    int(uid), chronicle, parse_mode="Markdown"
                )
                sent += 1
            except Exception:
                pass
            await asyncio.sleep(0.05)

    except Exception as e:
        print(f"[CHRONICLE] Delivery error: {e}")

    # Post to group
    if group_chat_id:
        try:
            msg = await bot.send_message(
                group_chat_id, chronicle, parse_mode="Markdown"
            )
            try:
                await bot.pin_chat_message(group_chat_id, msg.message_id)
            except Exception:
                pass
        except Exception as e:
            print(f"[CHRONICLE] Group post error: {e}")

    print(f"[CHRONICLE] Published to {sent} players")
    return sent


def _save_chronicle(text: str, data: dict):
    """Save the generated Chronicle to history."""
    try:
        history = []
        if os.path.exists(CHRONICLE_FILE):
            with open(CHRONICLE_FILE) as f:
                history = json.load(f)
        if not isinstance(history, list):
            history = []

        history.insert(0, {
            "generated_at": data.get("generated_at"),
            "text":         text,
            "active_players": data.get("players", []).__len__(),
        })
        history = history[:12]  # Keep last 12 weeks

        with open(CHRONICLE_FILE, "w") as f:
            json.dump(history, f, indent=2)

    except Exception as e:
        print(f"[CHRONICLE] Save error: {e}")


def get_last_chronicle() -> Optional[str]:
    """Get the most recently published Chronicle text."""
    try:
        if not os.path.exists(CHRONICLE_FILE):
            return None
        with open(CHRONICLE_FILE) as f:
            history = json.load(f)
        if history and isinstance(history, list):
            return history[0].get("text")
    except Exception:
        pass
    return None


def should_publish_now() -> bool:
    """
    Check if it's time to publish the Chronicle.
    Publishes Monday at 00:00 UTC.
    Called by scheduler every 60 seconds — uses a flag file to prevent double-publish.
    """
    now         = datetime.utcnow()
    flag_file   = "chronicle_published_week.txt"
    week_key    = f"{now.year}-W{now.isocalendar()[1]}"

    # Check if already published this week
    if os.path.exists(flag_file):
        with open(flag_file) as f:
            last = f.read().strip()
        if last == week_key:
            return False

    # Monday = weekday 0, within first 2 minutes of midnight
    if now.weekday() == 0 and now.hour == 0 and now.minute < 2:
        with open(flag_file, "w") as f:
            f.write(week_key)
        return True

    return False


def format_chronicle_preview() -> str:
    """Short preview for players who haven't read the Chronicle yet."""
    last = get_last_chronicle()
    if not last:
        return "📰 No Chronicle published yet. Check back Monday."
    # First 400 chars as preview
    preview = last[:400].strip()
    if len(last) > 400:
        preview += "...\n\n_Open the full Chronicle to read more._"
    return preview
