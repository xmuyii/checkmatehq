# -*- coding: utf-8 -*-
"""
sector_cycles.py — Sector Phase Cycle Engine
=============================================
Every geographical sector runs an independent time loop.
Phases rotate on a fixed schedule creating environmental changes
that force player decisions: stay and profit, or flee and survive.

DESIGN PHILOSOPHY (Sellers' Systems Approach):
  Every phase is a LOOP with:
    - A visible countdown (players can plan)
    - A resource incentive (reason to stay)
    - A risk cost (reason to leave)
    - A counter-item (agency to stay anyway)
    - An emergent social layer (sector chat fills with warnings/bragging)

  The best phases create MEMORABLE MOMENTS:
    "I survived the lava flow with 4 seconds left on my hazmat"
    "I lost 200 satoshi to a rug pull because I wanted one more minute"
    "Our whole alliance got wiped by the void collapse"

PHASE TYPES:
  calm       — Normal yield, no hazard. Boring but safe.
  surge      — Multiplied yield. Race to collect before it ends.
  hazard     — Suit required or penalties apply. High risk, hidden reward.
  predator   — Boss spawns on node. Multi-player kill for shared loot.
  event      — Rare special phase. Server-wide announcement.
  lockdown   — Nobody enters or leaves without penalty. Siege mode.

CYCLE INDEPENDENCE:
  Each sector's cycle offset is seeded by sector_id so they never
  all surge or crash simultaneously. Players can't be everywhere.
  They have to choose which sector's surge to chase.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import math

# ═══════════════════════════════════════════════════════════════════════════
#  SECTOR CYCLE DEFINITIONS
#  Each sector has a unique loop personality.
#  cycle_duration_minutes: full loop length
#  phases: ordered list, each runs for duration_pct of total cycle
#  Phases loop continuously from game start.
# ═══════════════════════════════════════════════════════════════════════════

SECTOR_CYCLES: Dict[int, dict] = {

    # ── SECTOR 1: Badlands-8 ─────────────────────────────────────────────
    # Beginner sector. Gentle loop. Teaches the phase mechanic safely.
    # The dust storm is forgiving — no suit required, just lower yield.
    # The iron surge is the first taste of "rush to collect" gameplay.
    1: {
        "cycle_duration_minutes": 60,
        "lore_cycle_name": "The Badlands Rotation",
        "phases": [
            {
                "name": "Calm",
                "emoji": "🏜️",
                "type": "calm",
                "duration_pct": 0.40,
                "resource_multiplier": 1.0,
                "hazard": None,
                "requires_suit": False,
                "dominance_multiplier": 1.0,
                "warning_before_secs": 120,
                "warning_msg": "⚠️ Badlands-8: Dust Storm approaching in 2 minutes. Mining yield will halve.",
                "arrival_msg": "💨 Dust Storm hits Badlands-8. Visibility reduced, yield halved.",
                "flavor": "The heat shimmers. A good time to mine undisturbed.",
            },
            {
                "name": "Dust Storm",
                "emoji": "🌪️",
                "type": "hazard_light",
                "duration_pct": 0.25,
                "resource_multiplier": 0.5,
                "hazard": "dust",        # Not lethal — just punishing
                "requires_suit": False,  # No suit needed — just worse yield
                "dominance_multiplier": 0.8,
                "warning_before_secs": 90,
                "warning_msg": "⚡ Dust Storm clearing in 90 seconds. Iron Surge incoming — prepare to collect!",
                "arrival_msg": "🌪️ Dust Storm in Badlands-8. Yield at 50%. Suit not required but yield is poor.",
                "flavor": "Sand fills every crack. You can barely see your own hands.",
                "dust_penalty": {
                    "resource_drain_pct": 0.05,   # 5% of pending per tick — soft penalty
                    "tick_seconds": 60,
                },
            },
            {
                "name": "Iron Surge",
                "emoji": "⚡",
                "type": "surge",
                "duration_pct": 0.35,
                "resource_multiplier": 3.0,
                "hazard": None,
                "requires_suit": False,
                "dominance_multiplier": 2.0,   # Rush to hold nodes during surge
                "warning_before_secs": 120,
                "warning_msg": "⚠️ Iron Surge ending in 2 minutes. Collect NOW before yield drops.",
                "arrival_msg": "⚡ IRON SURGE in Badlands-8! x3 iron yield for 21 minutes. Get to your nodes!",
                "flavor": "The iron veins glow orange. This is what you came for.",
                "event_chance": 0.15,    # 15% chance this surge spawns a predator
                "predator_type": "dust_raider",
            },
        ],
    },

    # ── SECTOR 2: Crimson Wastes ──────────────────────────────────────────
    # Mid-difficulty. The Fire Rain is the first real hazard requiring a suit.
    # Bronze Fever is deliberately addictive — yields feel amazing.
    # The Raider Surge spawns a predator every single time.
    2: {
        "cycle_duration_minutes": 75,
        "lore_cycle_name": "The Crimson Rotation",
        "phases": [
            {
                "name": "Smouldering",
                "emoji": "🔴",
                "type": "calm",
                "duration_pct": 0.35,
                "resource_multiplier": 1.2,
                "hazard": None,
                "requires_suit": False,
                "dominance_multiplier": 1.0,
                "warning_before_secs": 120,
                "warning_msg": "⚠️ Crimson Wastes: Fire Rain imminent. Equip Basic Suit or leave.",
                "arrival_msg": "🔴 Crimson Wastes is smouldering. Slightly elevated yields. Enjoy it.",
                "flavor": "The ash tastes like bronze. The ground is warm underfoot.",
            },
            {
                "name": "Fire Rain",
                "emoji": "🌧️🔥",
                "type": "hazard",
                "duration_pct": 0.25,
                "resource_multiplier": 0.0,
                "hazard": "lethal_heat",
                "requires_suit": True,
                "suit_type": "basic_suit",
                "dominance_multiplier": 0.5,
                "warning_before_secs": 120,
                "warning_msg": "🔥 Fire Rain clearing. Bronze Fever incoming. STAY if you have a suit ready.",
                "arrival_msg": "🌧️🔥 FIRE RAIN in Crimson Wastes! Lethal heat. Basic Suit required. "
                               "Unprotected players take troop losses every 30 seconds.",
                "flavor": "Burning droplets hit the ground like hammers. The air itself is on fire.",
            },
            {
                "name": "Bronze Fever",
                "emoji": "🧱✨",
                "type": "surge",
                "duration_pct": 0.25,
                "resource_multiplier": 5.0,
                "hazard": None,
                "requires_suit": False,
                "dominance_multiplier": 3.0,
                "warning_before_secs": 90,
                "warning_msg": "⚠️ Bronze Fever ends in 90 seconds. Collect everything NOW.",
                "arrival_msg": "🧱✨ BRONZE FEVER! x5 bronze yield for ~19 minutes. "
                               "This is the richest phase in the Crimson Wastes.",
                "flavor": "The ore practically falls into your hands. You almost don't want it to end.",
                "addiction_note": "Players who mine through Fire Rain to reach Bronze Fever "
                                  "earn ~4x more than those who played it safe. Intended.",
            },
            {
                "name": "Raider Surge",
                "emoji": "👹",
                "type": "predator",
                "duration_pct": 0.15,
                "resource_multiplier": 1.0,
                "hazard": None,
                "requires_suit": False,
                "dominance_multiplier": 1.5,
                "warning_before_secs": 60,
                "warning_msg": "👹 Crimson Raiders incoming in 60 seconds. Team up to fight them!",
                "arrival_msg": "👹 CRIMSON RAIDERS! A predator has appeared. "
                               "Multiple players can hit it — loot split by damage dealt.",
                "predator_type": "dust_raider",
                "predator_guaranteed": True,   # Always spawns, not chance-based
                "flavor": "They come from the red dust. Always hungry. Always angry.",
            },
        ],
    },

    # ── SECTOR 3: Obsidian Peaks ──────────────────────────────────────────
    # The first sector with a TRULY dangerous phase and a suit requirement.
    # Iron Surge here is the best non-vault iron source in the game.
    # The Obsidian Collapse is instant and devastating — no warning phase.
    # Players who sleep on the timer get buried.
    3: {
        "cycle_duration_minutes": 90,
        "lore_cycle_name": "The Volcanic Rotation",
        "phases": [
            {
                "name": "Cooling Period",
                "emoji": "💨",
                "type": "calm",
                "duration_pct": 0.30,
                "resource_multiplier": 1.4,
                "hazard": None,
                "requires_suit": False,
                "dominance_multiplier": 1.0,
                "warning_before_secs": 180,
                "warning_msg": "⛰️ Obsidian Peaks: Volcanic Activity imminent in 3 minutes. Prepare Hazmat or evacuate.",
                "arrival_msg": "💨 Cooling period in Obsidian Peaks. Elevated yields. The mountains are quiet... for now.",
                "flavor": "The obsidian glitters in the cooler air. You can almost forget the peaks are alive.",
            },
            {
                "name": "Iron Surge",
                "emoji": "⚡⛏️",
                "type": "surge",
                "duration_pct": 0.25,
                "resource_multiplier": 4.0,
                "hazard": None,
                "requires_suit": False,
                "dominance_multiplier": 2.5,
                "warning_before_secs": 120,
                "warning_msg": "⚠️ Iron Surge ending in 2 minutes! Volcanic Activity follows immediately.",
                "arrival_msg": "⚡ IRON SURGE — OBSIDIAN PEAKS! x4 iron yield. "
                               "WARNING: Volcanic Activity begins immediately after this phase.",
                "flavor": "The mountain bleeds iron. Fill your packs fast — the calm is always temporary here.",
                "tension_note": "The surge ends directly into the hazard. No gap. Rush or die.",
            },
            {
                "name": "Volcanic Activity",
                "emoji": "🌋",
                "type": "hazard",
                "duration_pct": 0.30,
                "resource_multiplier": 0.0,
                "hazard": "lethal_heat",
                "requires_suit": True,
                "suit_type": "hazmat_suit",   # Basic suit not enough here
                "dominance_multiplier": 0.3,
                "warning_before_secs": 120,
                "warning_msg": "🌋 Volcanic Activity clearing. Obsidian Collapse imminent — THIS IS YOUR LAST WARNING.",
                "arrival_msg": "🌋 VOLCANIC ACTIVITY in Obsidian Peaks! Hazmat Suit required. "
                               "Basic Suit insufficient — will be burned through in 60 seconds.",
                "flavor": "The mountain is angry. The obsidian cracks. You can hear it breathing.",
                "suit_drain_multiplier": 2.0,  # Suits drain 2x faster here
            },
            {
                "name": "Obsidian Collapse",
                "emoji": "💥",
                "type": "lockdown",
                "duration_pct": 0.15,
                "resource_multiplier": 0.0,
                "hazard": "lethal_heat",
                "requires_suit": True,
                "suit_type": "hazmat_suit",
                "dominance_multiplier": 0.0,
                "warning_before_secs": 0,      # NO WARNING — instant transition from Volcanic
                "warning_msg": "",
                "arrival_msg": "💥 OBSIDIAN COLLAPSE! The peak is caving. All unprotected players "
                               "are being AUTO-EJECTED. Even suits take damage.",
                "flavor": "The mountain falls in on itself. There is nowhere to run.",
                "force_eject_unprotected": True,   # Instant eject, no tick countdown
                "suit_drain_multiplier": 3.0,
                "even_suits_take_damage": True,   # Suit duration drains 3x speed
            },
        ],
    },

    # ── SECTOR 6: Molten Gorge ────────────────────────────────────────────
    # The most dramatic loop in the base game.
    # Cooling Pools → safe but mediocre.
    # Lava Surge → dangerous but rich if you have a suit.
    # Relic Eruption → the entire reason anyone comes here.
    #   Relics rain from the lava but you need a hazmat suit to survive.
    #   Players WILL die here. That's the point. The relic income makes it worth it.
    # Total Eclipse → Everyone leaves. No choice. The phase kills suits.
    6: {
        "cycle_duration_minutes": 45,
        "lore_cycle_name": "The Eruption Cycle",
        "phases": [
            {
                "name": "Cooling Pools",
                "emoji": "💧",
                "type": "calm",
                "duration_pct": 0.30,
                "resource_multiplier": 1.5,
                "hazard": None,
                "requires_suit": False,
                "dominance_multiplier": 1.0,
                "warning_before_secs": 90,
                "warning_msg": "🌋 Molten Gorge: Lava Surge in 90 seconds. Last chance to equip Hazmat.",
                "arrival_msg": "💧 Cooling Pools phase — Molten Gorge is temporarily survivable. "
                               "Stone and relic yields elevated.",
                "flavor": "The lava has retreated. It feels almost safe. It is not.",
            },
            {
                "name": "Lava Surge",
                "emoji": "🌋🔥",
                "type": "hazard",
                "duration_pct": 0.35,
                "resource_multiplier": 2.5,
                "hazard": "lethal_heat",
                "requires_suit": True,
                "suit_type": "hazmat_suit",
                "dominance_multiplier": 1.5,
                "warning_before_secs": 60,
                "warning_msg": "🌋 Lava receding. RELIC ERUPTION in 60 seconds — the richest phase. Stay if you dare.",
                "arrival_msg": "🌋🔥 LAVA SURGE in Molten Gorge! Hazmat required. x2.5 yield. "
                               "Troops without protection dying every 30 seconds.",
                "flavor": "The gorge fills with living fire. Your suit is the only thing between you and nothing.",
            },
            {
                "name": "Relic Eruption",
                "emoji": "🏺🌋",
                "type": "surge",
                "duration_pct": 0.25,
                "resource_multiplier": 6.0,   # Absurd yield — deliberately enticing
                "hazard": "lethal_heat",
                "requires_suit": True,
                "suit_type": "hazmat_suit",
                "dominance_multiplier": 4.0,
                "warning_before_secs": 60,
                "warning_msg": "⚠️ RELIC ERUPTION ending in 60 seconds. Total Eclipse follows — EVERYONE MUST LEAVE.",
                "arrival_msg": "🏺🌋 RELIC ERUPTION! Ancient relics surfacing through the lava. x6 relic yield. "
                               "Hazmat still required. This is why you came to Molten Gorge.",
                "flavor": "Something ancient is being born from the fire. Or re-born. You grab what you can.",
                "unique_drop": "molten_relic",
                "unique_drop_chance": 0.08,
                "greed_trap": "Players will push their hazmat timer here. "
                              "The eruption is 11 minutes. A hazmat suit lasts 20. "
                              "If you entered during Lava Surge (35% of 45min = 15min in), "
                              "you have 5 minutes left on your suit during eruption. Decide.",
            },
            {
                "name": "Total Eclipse",
                "emoji": "⚫",
                "type": "lockdown",
                "duration_pct": 0.10,
                "resource_multiplier": 0.0,
                "hazard": "lethal_heat",
                "requires_suit": False,    # Suits don't help — nothing helps
                "dominance_multiplier": 0.0,
                "warning_before_secs": 0,  # No warning — eruption transitions directly
                "warning_msg": "",
                "arrival_msg": "⚫ TOTAL ECLIPSE — Molten Gorge has gone dark. "
                               "ALL players auto-ejected. No suit survives this. "
                               "Resources auto-collected on departure.",
                "flavor": "The gorge closes. The mountain takes back what is hers.",
                "force_eject_all": True,   # Even suited players ejected
                "suit_negated": True,
            },
        ],
    },

    # ── SECTOR 9: Void Canyon ─────────────────────────────────────────────
    # The endgame loop. Fastest cycle. Most punishing.
    # Void Rift → the only time to mine. Void Suit required.
    # Reality Collapse → instant death for everyone including suited players.
    # No warning. No mercy. The canyon decides.
    9: {
        "cycle_duration_minutes": 30,
        "lore_cycle_name": "The Void Rotation",
        "phases": [
            {
                "name": "Void Rift",
                "emoji": "🌑✨",
                "type": "surge",
                "duration_pct": 0.60,
                "resource_multiplier": 5.0,
                "hazard": "void_radiation",
                "requires_suit": True,
                "suit_type": "void_suit",
                "dominance_multiplier": 3.0,
                "warning_before_secs": 180,
                "warning_msg": "🌑 VOID CANYON: Reality Collapse in 3 minutes. "
                               "Final warning. Collect and teleport.",
                "arrival_msg": "🌑✨ VOID RIFT OPEN — Cosmic resources available. "
                               "Void Suit required. x5 yield. Reality holds... for now.",
                "flavor": "The rift breathes. You breathe with it. You are the only living thing here.",
                "cosmic_dust_bonus": True,   # Bitcoin nodes active only during this phase
            },
            {
                "name": "Reality Collapse",
                "emoji": "💀🌑",
                "type": "lockdown",
                "duration_pct": 0.40,
                "resource_multiplier": 0.0,
                "hazard": "reality_distortion",
                "requires_suit": False,
                "dominance_multiplier": 0.0,
                "warning_before_secs": 0,
                "warning_msg": "",
                "arrival_msg": "💀 REALITY COLLAPSE — Void Canyon implodes. "
                               "ALL PLAYERS AUTO-EJECTED. Void Suits disintegrated. "
                               "Resources auto-collected. No exceptions.",
                "flavor": "Reality folds. You don't die here — you simply stop being.",
                "force_eject_all": True,
                "suit_negated": True,
                "server_announcement": True,   # Server-wide notification when this fires
                "server_msg": "🌑 VOID CANYON HAS COLLAPSED — All Void Runners have been expelled.",
            },
        ],
    },

    # ── SECTOR 65: The Crypto Wastes ──────────────────────────────────────
    # The funniest loop in the game. Financial trauma as gameplay.
    # Bull Run → everyone rushes in, greedy.
    # Sideways → boring, but also relaxed and safe.
    # Crypto Scammer → a PLAYER with the scammer_kit buff becomes the hazard.
    #   If no player has the buff, an NPC scammer spawns instead.
    # Rug Pull → satoshi converts to dust. Fast. Brutal. Funny in retrospect.
    # Market Crash → only Cold Wallet survives. Everyone else loses 50% then exits.
    # The loop is 20 minutes — fast enough that you can watch your crypto die
    # in real time and understand exactly why you should have sold earlier.
    65: {
        "cycle_duration_minutes": 20,
        "lore_cycle_name": "The Market Cycle",
        "phases": [
            {
                "name": "Bull Run",
                "emoji": "📈🐂",
                "type": "surge",
                "duration_pct": 0.30,
                "resource_multiplier": 3.0,
                "hazard": None,
                "requires_suit": False,
                "dominance_multiplier": 2.0,
                "warning_before_secs": 60,
                "warning_msg": "📊 Bull Run peaking. Sideways market next — yields normalize.",
                "arrival_msg": "📈 BULL RUN in Crypto Wastes! x3 Satoshi yield. "
                               "Everyone is getting rich. For now.",
                "flavor": "Numbers go up. You feel invincible. This is exactly how they get you.",
                "server_announcement": True,
                "server_msg": "📈 BULL RUN in the Crypto Wastes! Satoshi yield tripled for 6 minutes.",
            },
            {
                "name": "Sideways Market",
                "emoji": "📊",
                "type": "calm",
                "duration_pct": 0.20,
                "resource_multiplier": 1.0,
                "hazard": None,
                "requires_suit": False,
                "dominance_multiplier": 1.0,
                "warning_before_secs": 60,
                "warning_msg": "⚠️ Crypto Wastes: A scammer has been spotted in the sector.",
                "arrival_msg": "📊 Sideways market. Normal yields. Enjoy the calm. "
                               "Something is coming.",
                "flavor": "Consolidation. Everyone is watching the charts. Nobody is leaving.",
            },
            {
                "name": "Scammer Alert",
                "emoji": "🦹",
                "type": "predator",
                "duration_pct": 0.20,
                "resource_multiplier": 0.0,
                "hazard": "crypto_scammer",
                "requires_suit": True,
                "suit_type": "bitcoin_format",
                "dominance_multiplier": 0.8,
                "warning_before_secs": 60,
                "warning_msg": "⚠️ Scammer being neutralized. Rug Pull incoming — "
                               "Bitcoin Format or Cold Wallet REQUIRED.",
                "arrival_msg": "🦹 CRYPTO SCAMMER active in the Crypto Wastes! "
                               "Unprotected wallets drained 100 Satoshi per 30 seconds. "
                               "Bitcoin Format blocks this. Fight the scammer to end phase early.",
                "flavor": "They say they have insider info. They say it's guaranteed. "
                          "Your Satoshi is leaving your wallet right now.",
                "predator_type": "crypto_scammer",
                "predator_can_be_player": True,   # A player with scammer_kit BECOMES the scammer
                "scammer_kit_required": "scammer_kit",
                "player_scammer_bonus": {
                    "steals_satoshi_per_tick": 150,   # More than NPC scammer
                    "loot_kept_by_player": True,
                },
            },
            {
                "name": "Rug Pull",
                "emoji": "🚨📉",
                "type": "hazard",
                "duration_pct": 0.15,
                "resource_multiplier": 0.0,
                "hazard": "rug_pull",
                "requires_suit": True,
                "suit_type": "bitcoin_format",
                "dominance_multiplier": 0.5,
                "warning_before_secs": 30,
                "warning_msg": "🚨 RUG PULL happening NOW. Cold Wallet survives. Nothing else does.",
                "arrival_msg": "🚨 RUG PULL — The developers pulled the liquidity. "
                               "Unprotected Satoshi converting to Crypto Dust every 15 seconds. "
                               "Bitcoin Format protects you. Cold Wallet protects you. "
                               "Nothing else does.",
                "flavor": "The floor disappears. The team has deleted their social media. "
                          "Your Satoshi is becoming beautiful worthless dust.",
                "convert_rate_secs": 15,   # Faster than normal 30-sec tick
                "greed_trap": "Players who survived Scammer Alert think they're safe. "
                              "Bitcoin Format protects from scammers AND rug pulls. "
                              "But players who forgot to equip after the scammer phase lose everything.",
            },
            {
                "name": "Market Crash",
                "emoji": "📉💀",
                "type": "lockdown",
                "duration_pct": 0.15,
                "resource_multiplier": 0.0,
                "hazard": "market_crash",
                "requires_suit": True,
                "suit_type": "cold_wallet",   # Only cold wallet survives crash
                "dominance_multiplier": 0.0,
                "warning_before_secs": 0,     # No warning — rug pull leads directly here
                "warning_msg": "",
                "arrival_msg": "📉💀 MARKET CRASH — 90% price collapse. "
                               "Only Cold Wallet holders survive intact. "
                               "All others lose 50% Satoshi then are force-ejected.",
                "flavor": "This is fine. Everything is fine. The number is just... lower now. "
                          "Much lower. Zero, actually.",
                "force_eject_unprotected": True,
                "crash_drain_pct": 0.50,   # 50% loss before eject
                "server_announcement": True,
                "server_msg": "📉 MARKET CRASH in the Crypto Wastes. "
                              "Unprotected miners have been liquidated.",
            },
        ],
    },

    # ── HIDDEN SECTORS 10-59: Procedural cycles ───────────────────────────
    # Generated on-the-fly from sector_id seed.
    # No two hidden sectors have the same cycle length or phase order.
    # This makes exploration genuinely surprising.
    # Defined via get_hidden_sector_cycle() below.
}


# ═══════════════════════════════════════════════════════════════════════════
#  CYCLE ENGINE — Pure time calculation, no state storage
#  Phases are computed from epoch time + sector offset.
#  No background scheduler needed.
# ═══════════════════════════════════════════════════════════════════════════

# Game epoch — when the cycle clock started
# Set this to your bot launch date in production
GAME_EPOCH = datetime(2026, 1, 1, 0, 0, 0)


def get_cycle_config(sector_id: int) -> dict:
    """
    Get the cycle configuration for a sector.
    For hidden sectors (10-59) generates a procedural cycle.
    """
    if sector_id in SECTOR_CYCLES:
        return SECTOR_CYCLES[sector_id]

    # Vault sectors (60-64) — slow calm cycle, mostly safe
    if 60 <= sector_id <= 64:
        return _get_vault_cycle(sector_id)

    # Hidden sectors (10-59) — procedurally generated
    if 10 <= sector_id <= 59:
        return _get_hidden_sector_cycle(sector_id)

    # Default fallback
    return SECTOR_CYCLES[1]


def get_current_phase(sector_id: int, now: datetime = None) -> dict:
    """
    Calculate the current phase for a sector based on current time.
    Pure computation — no database read required.

    Returns full phase dict with added timing fields:
        phase_index:          int — which phase in the list
        phase_elapsed_secs:   float — seconds into this phase
        phase_remaining_secs: float — seconds until next phase
        phase_pct:            float — 0.0 to 1.0 progress through phase
        next_phase:           dict — the next phase definition
        time_remaining_str:   str — human-readable countdown
    """
    if now is None:
        now = datetime.utcnow()

    config = get_cycle_config(sector_id)
    cycle_duration_secs = config["cycle_duration_minutes"] * 60

    # Offset each sector's start to stagger cycles
    # Sector 1 starts at epoch, sector 2 at +7min, sector 3 at +14min etc.
    offset_secs = (sector_id * 7 * 60) % cycle_duration_secs
    elapsed_total = (now - GAME_EPOCH).total_seconds() + offset_secs
    position_in_cycle = elapsed_total % cycle_duration_secs

    phases = config["phases"]
    accumulated = 0.0

    for i, phase in enumerate(phases):
        phase_duration_secs = phase["duration_pct"] * cycle_duration_secs
        if position_in_cycle < accumulated + phase_duration_secs:
            phase_elapsed   = position_in_cycle - accumulated
            phase_remaining = phase_duration_secs - phase_elapsed
            next_phase      = phases[(i + 1) % len(phases)]

            return {
                **phase,
                "phase_index":          i,
                "phase_duration_secs":  phase_duration_secs,
                "phase_elapsed_secs":   phase_elapsed,
                "phase_remaining_secs": phase_remaining,
                "phase_pct":            phase_elapsed / phase_duration_secs,
                "next_phase":           next_phase,
                "time_remaining_str":   _format_seconds(int(phase_remaining)),
                "cycle_name":           config.get("lore_cycle_name", "Unknown Cycle"),
            }
        accumulated += phase_duration_secs

    # Should never reach here
    return {**phases[0], "phase_remaining_secs": cycle_duration_secs,
            "time_remaining_str": _format_seconds(cycle_duration_secs)}


def get_phase_warning(sector_id: int, now: datetime = None) -> Optional[str]:
    """
    Check if any phase is close to ending and a warning should be sent.
    Returns warning message string if warning threshold is crossed, else None.
    Called periodically (e.g., on every user action in the sector).
    """
    phase = get_current_phase(sector_id, now)
    remaining = phase.get("phase_remaining_secs", 999)
    warning_threshold = phase.get("warning_before_secs", 120)

    if warning_threshold > 0 and remaining <= warning_threshold:
        # Only warn once per threshold crossing
        # The caller tracks whether this warning has been sent already
        return phase.get("warning_msg")

    return None


def is_hazardous(sector_id: int, now: datetime = None) -> Tuple[bool, Optional[str]]:
    """
    Check if the current phase is hazardous.
    Returns (is_hazardous, hazard_type)
    """
    phase = get_current_phase(sector_id, now)
    hazard = phase.get("hazard")
    return bool(hazard), hazard


def get_resource_multiplier(sector_id: int, now: datetime = None) -> float:
    """Get the current resource yield multiplier for a sector."""
    phase = get_current_phase(sector_id, now)
    return phase.get("resource_multiplier", 1.0)


def should_force_eject_all(sector_id: int, now: datetime = None) -> bool:
    """Check if current phase forces ALL players out (even suited)."""
    phase = get_current_phase(sector_id, now)
    return phase.get("force_eject_all", False)


def should_spawn_predator(sector_id: int, now: datetime = None) -> Tuple[bool, Optional[str]]:
    """
    Check if current phase should spawn a predator.
    Returns (should_spawn, predator_type)
    """
    phase = get_current_phase(sector_id, now)
    if phase.get("type") != "predator":
        # Check event chance for non-predator phases
        event_chance = phase.get("event_chance", 0)
        if event_chance > 0:
            import random
            if random.random() < event_chance:
                return True, phase.get("predator_type")
        return False, None

    if phase.get("predator_guaranteed"):
        return True, phase.get("predator_type")

    return False, None


def get_suit_drain_multiplier(sector_id: int, now: datetime = None) -> float:
    """
    Some phases drain suit timers faster.
    Returns multiplier (1.0 = normal, 2.0 = suit expires twice as fast).
    """
    phase = get_current_phase(sector_id, now)
    return phase.get("suit_drain_multiplier", 1.0)


def is_suit_negated(sector_id: int, now: datetime = None) -> bool:
    """Check if the current phase negates all suit protection (e.g., Total Eclipse)."""
    phase = get_current_phase(sector_id, now)
    return phase.get("suit_negated", False)


def get_dominance_multiplier(sector_id: int, now: datetime = None) -> float:
    """Get the dominance score multiplier for the current phase."""
    phase = get_current_phase(sector_id, now)
    return phase.get("dominance_multiplier", 1.0)


# ═══════════════════════════════════════════════════════════════════════════
#  PHASE TRANSITION PROCESSING
#  Called when a phase changes — handles server announcements,
#  predator spawns, and force-eject notifications.
# ═══════════════════════════════════════════════════════════════════════════

def process_phase_transition(
    sector_id: int,
    old_phase_name: str,
    new_phase: dict,
    sector_state: dict,
    log_sector_event_fn,
    broadcast_fn,           # callable(message) — sends to bot group or server
    get_all_sector_players_fn,  # callable(sector_id, sector_state) -> list of player dicts
    save_user_fn,
) -> Tuple[dict, List[str]]:
    """
    Handle everything that happens when a sector transitions to a new phase.
    Returns (updated_sector_state, list_of_player_ids_to_notify)
    """
    phase_name = new_phase.get("name", "Unknown")
    phase_emoji = new_phase.get("emoji", "🌍")
    arrival_msg = new_phase.get("arrival_msg", "")

    notify_players = []

    # Log the transition
    log_sector_event_fn(
        sector_id,
        f"{phase_emoji} Phase changed → *{phase_name}*"
    )

    # Server-wide announcement for high-impact phases
    if new_phase.get("server_announcement") and broadcast_fn:
        server_msg = new_phase.get("server_msg", arrival_msg)
        broadcast_fn(server_msg)

    # Post to sector chat
    from teleport_system import post_sector_chat
    sector_state, _ = post_sector_chat(
        sector_state, "SYSTEM", "SYSTEM", arrival_msg, is_system=True
    )

    # Update sector state with current phase
    sector_state["current_phase"] = {
        "name":               phase_name,
        "emoji":              phase_emoji,
        "type":               new_phase.get("type", "calm"),
        "hazard":             new_phase.get("hazard"),
        "requires_suit":      new_phase.get("requires_suit", False),
        "suit_type":          new_phase.get("suit_type"),
        "resource_multiplier": new_phase.get("resource_multiplier", 1.0),
        "force_eject_all":    new_phase.get("force_eject_all", False),
        "suit_negated":       new_phase.get("suit_negated", False),
        "started_at":         datetime.utcnow().isoformat(),
    }

    # Handle force-eject-all phases (Total Eclipse, Reality Collapse)
    if new_phase.get("force_eject_all"):
        players = get_all_sector_players_fn(sector_id, sector_state)
        for player in players:
            pid = player.get("user_id", "")
            notify_players.append(pid)
            # Auto-collect before ejecting
            _auto_eject_player(player, sector_id, sector_state, save_user_fn)

    # Handle predator spawn
    spawn, pred_type = should_spawn_predator(sector_id)
    if spawn and pred_type:
        sector_state = _spawn_predator(sector_state, sector_id, pred_type)
        from sector_nodes import SECTOR_NODES
        nodes = SECTOR_NODES.get(sector_id, {})
        log_sector_event_fn(
            sector_id,
            f"👹 *{pred_type.replace('_', ' ').title()}* has spawned! "
            f"Use `!attack predator [node]` to fight it."
        )

    return sector_state, notify_players


def _auto_eject_player(
    user: dict,
    sector_id: int,
    sector_state: dict,
    save_user_fn,
) -> dict:
    """Force-eject a player from a sector, auto-collecting resources first."""
    from sector_nodes import auto_collect_on_departure, clear_node_occupant

    player_id    = user.get("user_id", "")
    current_node = user.get("current_node")

    if current_node and current_node.get("sector_id") == sector_id:
        node_key     = current_node.get("node_key", "")
        sector_state, user, collected = auto_collect_on_departure(
            sector_state, sector_id, node_key, player_id, user
        )

    # Return to home sector
    home_sector = user.get("home_sector", 1)
    user["commander_location"] = {"sector_id": home_sector}
    user["current_node"] = None
    user["active_suit"]  = None   # Phase kills all suits

    user["pending_notification"] = (
        f"💀 *AUTO-EJECTED from Sector {sector_id}*\n"
        f"The phase transition left no survivors.\n"
        f"Resources auto-collected. You've been returned to Sector {home_sector}."
    )

    save_user_fn(player_id, user)
    return user


def _spawn_predator(sector_state: dict, sector_id: int, pred_type: str) -> dict:
    """Spawn a predator on a random available node in the sector."""
    from sector_nodes import SECTOR_NODES, NODE_TYPES

    nodes    = SECTOR_NODES.get(sector_id, {})
    occupancy = sector_state.get("occupancy", {})

    # Find a resource node (not base plot, not PvP node) that has an occupant
    # Predators prefer occupied nodes — they disrupt ongoing mining
    occupied_resource_nodes = []
    for node_key, node in nodes.items():
        if node.get("type") in ("iron_mine", "stone_quarry", "relic_cache", "crypto_mine"):
            occ_key = f"{sector_id}:{node_key}"
            if occ_key in occupancy:
                occupied_resource_nodes.append(node_key)

    import random
    if occupied_resource_nodes:
        target_node = random.choice(occupied_resource_nodes)
    else:
        # Spawn on any resource node
        resource_nodes = [k for k, n in nodes.items()
                          if n.get("type") not in ("base_plot", "pvp_node")]
        if not resource_nodes:
            return sector_state
        target_node = random.choice(resource_nodes)

    from sector_nodes import PREDATORS
    pred_def = PREDATORS.get(pred_type, {})

    pred_key = f"predator:{sector_id}:{target_node}"
    if "active_predators" not in sector_state:
        sector_state["active_predators"] = {}

    sector_state["active_predators"][pred_key] = {
        "type":      pred_type,
        "name":      pred_def.get("name", pred_type),
        "emoji":     pred_def.get("emoji", "👾"),
        "hp":        pred_def.get("hp", 200),
        "max_hp":    pred_def.get("hp", 200),
        "sector_id": sector_id,
        "node_key":  target_node,
        "spawned_at": datetime.utcnow().isoformat(),
        "damage_log": {},
    }

    return sector_state


# ═══════════════════════════════════════════════════════════════════════════
#  HIDDEN SECTOR PROCEDURAL GENERATION
# ═══════════════════════════════════════════════════════════════════════════

def _get_hidden_sector_cycle(sector_id: int) -> dict:
    """
    Generate a deterministic but varied cycle for hidden sectors.
    Uses sector_id as a seed so the same sector always has the same loop.
    Hidden sectors are genuinely surprising on first visit.
    """
    # Seed from sector_id — deterministic
    seed = sector_id * 137 + 42   # Simple hash
    cycle_duration = 45 + (seed % 45)   # 45 to 90 minutes

    # Phase templates to mix
    templates = [
        {"name": "Quiet",        "emoji": "🔒", "type": "calm",
         "duration_pct": 0.40, "resource_multiplier": 1.0 + (seed % 5) * 0.1,
         "hazard": None, "requires_suit": False, "dominance_multiplier": 1.0,
         "warning_before_secs": 90, "warning_msg": f"⚠️ Hidden Sector {sector_id}: Conditions changing.",
         "arrival_msg": f"🔒 Hidden Sector {sector_id} — quiet phase. This place keeps its secrets."},
        {"name": "Resource Bloom", "emoji": "✨", "type": "surge",
         "duration_pct": 0.30, "resource_multiplier": 2.0 + (seed % 3) * 0.5,
         "hazard": None, "requires_suit": False, "dominance_multiplier": 1.5,
         "warning_before_secs": 90, "warning_msg": f"⚠️ Hidden Sector {sector_id}: Bloom ending soon.",
         "arrival_msg": f"✨ Hidden Sector {sector_id} — Resource Bloom active. Why is nobody else here?"},
        {"name": "Anomaly",      "emoji": "⚡", "type": "hazard",
         "duration_pct": 0.30, "resource_multiplier": 0.0,
         "hazard": "toxic_gas" if seed % 2 == 0 else "lethal_heat",
         "requires_suit": True,
         "suit_type": "basic_suit",
         "dominance_multiplier": 0.5,
         "warning_before_secs": 120,
         "warning_msg": f"⚠️ Hidden Sector {sector_id}: Anomaly clearing. Safe conditions returning.",
         "arrival_msg": f"⚡ Anomaly active in Hidden Sector {sector_id}. Basic Suit required."},
    ]

    return {
        "cycle_duration_minutes": cycle_duration,
        "lore_cycle_name": f"Hidden Cycle {sector_id}",
        "phases": templates,
    }


def _get_vault_cycle(sector_id: int) -> dict:
    """Vault sectors (60-64) — high yield, slow cycle, mostly safe."""
    return {
        "cycle_duration_minutes": 120,
        "lore_cycle_name": "The Vault Cycle",
        "phases": [
            {
                "name": "Vault Open",
                "emoji": "🏆",
                "type": "surge",
                "duration_pct": 0.70,
                "resource_multiplier": 5.0,
                "hazard": None,
                "requires_suit": False,
                "dominance_multiplier": 3.0,
                "warning_before_secs": 300,
                "warning_msg": "⚠️ Vault closing in 5 minutes. Collect everything.",
                "arrival_msg": "🏆 VAULT OPEN — High-value resources available. x5 yield.",
            },
            {
                "name": "Vault Sealed",
                "emoji": "🔐",
                "type": "lockdown",
                "duration_pct": 0.30,
                "resource_multiplier": 0.0,
                "hazard": None,
                "requires_suit": False,
                "dominance_multiplier": 0.0,
                "warning_before_secs": 180,
                "warning_msg": "🔐 Vault reopening in 3 minutes.",
                "arrival_msg": "🔐 Vault sealed. Come back when it reopens.",
                "force_eject_all": True,
            },
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════
#  PHASE STATUS DISPLAY
# ═══════════════════════════════════════════════════════════════════════════

def format_phase_status(sector_id: int, now: datetime = None) -> str:
    """Format current phase status for dashboard display."""
    phase = get_current_phase(sector_id, now)
    name      = phase.get("name", "Unknown")
    emoji     = phase.get("emoji", "🌍")
    remaining = phase.get("time_remaining_str", "?")
    multiplier = phase.get("resource_multiplier", 1.0)
    hazard    = phase.get("hazard")
    next_ph   = phase.get("next_phase", {})
    next_name = next_ph.get("name", "Unknown")
    next_emoji = next_ph.get("emoji", "")

    lines = [f"{emoji} *{name}* — {remaining} remaining"]

    if multiplier != 1.0:
        mult_str = f"x{multiplier:.1f}" if multiplier != int(multiplier) else f"x{int(multiplier)}"
        lines.append(f"📊 Yield: *{mult_str}*")

    if hazard:
        lines.append(f"⚠️ Hazard: *{hazard.replace('_', ' ').title()}*")
        suit_type = phase.get("suit_type")
        if suit_type:
            from resource_registry import get_display_name
            lines.append(f"🧪 Required: *{get_display_name(suit_type)}*")

    lines.append(f"⏭️ Next: {next_emoji} {next_name}")

    return "\n".join(lines)


def format_full_cycle_view(sector_id: int, now: datetime = None) -> str:
    """Show the full cycle with all phases and current position marked."""
    config = get_cycle_config(sector_id)
    phases = config["phases"]
    cycle_duration = config["cycle_duration_minutes"]
    current = get_current_phase(sector_id, now)
    current_idx = current.get("phase_index", 0)
    cycle_name = config.get("lore_cycle_name", "Cycle")

    lines = [
        f"🔄 *{cycle_name}* ({cycle_duration} min total)",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    for i, phase in enumerate(phases):
        name     = phase.get("name", "?")
        emoji    = phase.get("emoji", "")
        dur_min  = int(phase["duration_pct"] * cycle_duration)
        ptype    = phase.get("type", "calm")
        hazard   = phase.get("hazard")
        mult     = phase.get("resource_multiplier", 1.0)

        # Current phase marker
        if i == current_idx:
            remaining = int(current.get("phase_remaining_secs", 0))
            marker = f"  ◀ NOW ({_format_seconds(remaining)} left)"
        else:
            marker = ""

        suit_tag = ""
        if hazard and phase.get("requires_suit"):
            suit_tag = " 🧪"
        elif hazard:
            suit_tag = " ⚠️"

        mult_tag = ""
        if mult > 1.0:
            mult_tag = f" x{mult:.0f}"
        elif mult == 0.0:
            mult_tag = " ✗"

        lines.append(
            f"  {emoji} *{name}* ({dur_min}m){suit_tag}{mult_tag}{marker}"
        )

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def _format_seconds(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        m = seconds // 60
        s = seconds % 60
        return f"{m}m {s}s" if s else f"{m}m"
    else:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h}h {m}m"
