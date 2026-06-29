# -*- coding: utf-8 -*-
"""
supabase_db_patch.py — Patch instructions for supabase_db.py
=============================================================
This file contains the EXACT changes to make to supabase_db.py
to wire in Phase 1 & 2 systems. Do NOT copy this file as-is —
apply the changes described below to the existing supabase_db.py.

CHANGE 1: Add import at the top of supabase_db.py
──────────────────────────────────────────────────
Add after existing imports:

    from teleport_system import on_user_load

CHANGE 2: Modify get_user() to call on_user_load
─────────────────────────────────────────────────
Find your existing get_user() function. It likely looks like:

    def get_user(user_id: str) -> dict | None:
        try:
            r = supabase.table(DB_TABLE).select("*").eq("user_id", str(user_id)).execute()
            if r.data:
                return r.data[0]
            return None
        except Exception as e:
            print(f"[DB ERROR] get_user: {e}")
            return None

Change it to:

    def get_user(user_id: str) -> dict | None:
        try:
            r = supabase.table(DB_TABLE).select("*").eq("user_id", str(user_id)).execute()
            if r.data:
                user = r.data[0]
                # Run all passive migrations and ticks on every load
                user = on_user_load(user)
                return user
            return None
        except Exception as e:
            print(f"[DB ERROR] get_user: {e}")
            return None

CHANGE 3: Add a getter-pattern helper used by teleport/march systems
─────────────────────────────────────────────────────────────────────
Some systems need to both get AND save users via a single callable.
Add this function anywhere in supabase_db.py:

    def get_or_save_user(user_id: str, data: dict | None) -> dict | None:
        '''
        If data is None: acts as getter — returns user dict.
        If data is dict: acts as setter — saves and returns None.
        Used by systems that need to inject DB access without circular imports.
        '''
        if data is None:
            return get_user(user_id)
        else:
            save_user(user_id, data)
            return None

CHANGE 4: register_user() — ensure credits field is set
────────────────────────────────────────────────────────
(This was the bug that blocked all Fusion players.)
Make sure register_user() includes credits: 0 in the initial record:

    def register_user(user_id, username, ...):
        user_data = {
            "user_id":      str(user_id),
            "username":     username,
            "credits":      0,           # ← REQUIRED — was missing, caused NULL errors
            "xp":           0,
            "level":        1,
            "bitcoin":      0,
            "military":     {"pawns": 5},
            "buildings":    {},
            "researches":   {},
            "inventory":    {},          # ← New stacked format from day one
            "unclaimed_items": [],
            "teleport_charges": 0,
            "home_sector":  None,        # Set when player chooses base plot
            "commander_location": {"sector_id": 1},  # Start in Sector 1
            "base_shielded": False,
            "shield_expires_at": None,
            "active_suit":  None,
            "energy":       100,         # Start with 100 energy
            "energy_last_regen": None,
            "march_queue":  [],
            "research_queue": {},
            "banishments":  {},
            "visas":        {},
            "alliance_id":  None,
            "alliance_role": None,
        }
        ...

THAT'S IT. Four changes to supabase_db.py.
Everything else in Phase 1 & 2 is self-contained.
"""

# ═══════════════════════════════════════════════════════════════════════════
#  STANDALONE VALIDATION — Run this to test all Phase 2 systems together
# ═══════════════════════════════════════════════════════════════════════════

def run_phase2_validation():
    """
    Self-contained validation of all Phase 2 systems.
    Run with: python3 supabase_db_patch.py
    """
    import sys, types
    sys.path.insert(0, '.')

    # Mock supabase_db
    mock_db = types.ModuleType('supabase_db')
    mock_db.get_user  = lambda uid: None
    mock_db.save_user = lambda uid, data: None
    sys.modules['supabase_db'] = mock_db

    # Mock sectors_system
    mock_sec = types.ModuleType('sectors_system')
    mock_sec.get_sector_info = lambda sid: {
        "name": f"Sector {sid}", "emoji": "🌍", "lore": "Ancient lands."
    }
    sys.modules['sectors_system'] = mock_sec

    from datetime import datetime, timedelta

    print("=" * 55)
    print("PHASE 2 VALIDATION")
    print("=" * 55)

    # ── 1. March Queue ────────────────────────────────────────
    print("\n1. MARCH QUEUE")
    from march_queue import (
        create_march, get_arrived_marches, format_march_queue_display,
        apply_speedup_to_march, cancel_march, purge_old_marches
    )

    user = {
        "user_id": "p1", "username": "TestCommander",
        "military": {"footmen": 200, "archers": 100, "lancers": 50},
        "inventory": {"speedup_5m": {"qty": 3, "display": "5min Speedup", "emoji": "⏩", "category": "utility"}},
        "researches": {"siege_tactics": True, "basic_military": True},
        "march_queue": [],
    }

    ok, msg, user = create_march(
        user, "occupy", 3, "A", "The Ironjaw Tunnels",
        {"footmen": 50, "archers": 20}, "same_sector"
    )
    print(f"  Create march (occupy): {'✅' if ok else '❌'} {msg[:60]}")
    assert ok, "march creation failed"
    assert user["military"]["footmen"] == 150, "troops not deducted"

    # Apply speedup
    march_id = user["march_queue"][0]["march_id"]
    ok2, msg2, user = apply_speedup_to_march(user, march_id, "speedup_5m")
    print(f"  Apply speedup: {'✅' if ok2 else '❌'} {msg2[:60]}")
    assert ok2
    assert user["inventory"]["speedup_5m"]["qty"] == 2, "speedup not consumed"

    # Cancel march
    ok3, msg3, user = cancel_march(user, march_id)
    print(f"  Cancel march: {'✅' if ok3 else '❌'} {msg3[:60]}")
    assert ok3
    assert user["military"]["footmen"] == 200, "troops not returned"
    print("  March queue: PASS ✅")

    # ── 2. Suit System ────────────────────────────────────────
    print("\n2. SUIT SYSTEM")
    from suit_system import (
        equip_suit, get_active_suit, is_protected_against,
        can_enter_node, format_suit_status, apply_hazard_penalty,
        get_suit_time_remaining
    )

    user2 = {
        "user_id": "p2", "username": "SuitTester",
        "researches": {"hazard_awareness": True},
        "inventory": {
            "basic_suit": {"qty": 2, "display": "Basic Suit", "emoji": "🧪", "category": "protective_item"}
        },
        "active_suit": None,
        "military": {"footmen": 100},
        "home_sector": 1,
        "commander_location": {"sector_id": 6},
        "current_node": None,
    }

    ok, msg, user2 = equip_suit(user2, "basic_suit")
    print(f"  Equip basic_suit: {'✅' if ok else '❌'} {msg[:60]}")
    assert ok
    assert user2["inventory"]["basic_suit"]["qty"] == 1, "suit not consumed"
    assert get_active_suit(user2) is not None, "suit not active"

    protected = is_protected_against(user2, "lethal_heat")
    print(f"  Protected vs lethal_heat: {'✅' if protected else '❌'}")
    assert protected

    not_protected = is_protected_against(user2, "void_radiation")
    print(f"  Not protected vs void_radiation: {'✅' if not not_protected else '❌'}")
    assert not not_protected

    # Stack prevention
    ok2, msg2, user2 = equip_suit(user2, "basic_suit")
    print(f"  Stack prevention: {'✅' if not ok2 else '❌'}")
    assert not ok2, "should not allow stacking"

    suit_display = format_suit_status(user2)
    print(f"  Suit display: {suit_display[:60]}")
    assert "remaining" in suit_display
    print("  Suit system: PASS ✅")

    # ── 3. Teleport System ────────────────────────────────────
    print("\n3. TELEPORT SYSTEM")
    from teleport_system import (
        claim_daily_teleports, get_daily_claim_status,
        can_teleport_to, purchase_teleport_charges,
        format_teleport_menu, post_sector_chat, read_sector_chat,
        get_sector_intelligence_from_chat, set_alliance_safe_sector,
        set_visa_policy, check_visa_required, format_charge_status
    )

    user3 = {
        "user_id": "p3", "username": "TeleportTester",
        "teleport_charges": 0,
        "researches": {},
        "banishments": {},
        "inventory": {},
        "home_sector": 1,
    }

    # Claim daily
    ok, msg, user3 = claim_daily_teleports(user3)
    print(f"  Claim daily: {'✅' if ok else '❌'} {msg[:60]}")
    assert ok
    assert user3["teleport_charges"] == 3

    # Double claim
    ok2, msg2, user3 = claim_daily_teleports(user3)
    print(f"  Double claim blocked: {'✅' if not ok2 else '❌'}")
    assert not ok2

    # Can teleport check
    can, reason = can_teleport_to(user3, 1)
    print(f"  Can teleport to S1: {'✅' if can else '❌'}")
    assert can

    # Research-locked sector
    can2, reason2 = can_teleport_to(user3, 9)
    print(f"  S9 locked (no void_theory): {'✅' if not can2 else '❌'} {reason2[:50]}")
    assert not can2

    # Sector chat
    sector_state = {"sector_chat": [], "active_jam": None}
    sector_state, _ = post_sector_chat(sector_state, "p3", "TeleportTester", "Anyone here?")
    sector_state, _ = post_sector_chat(sector_state, "p4", "OtherPlayer", "Just arrived!")
    sector_state, _ = post_sector_chat(sector_state, "SYSTEM", "SYSTEM", "Phase changed: Iron Surge", is_system=True)

    chat_display = read_sector_chat(sector_state, "p3", user3, limit=10)
    print(f"  Sector chat ({len(sector_state['sector_chat'])} msgs): ✅")
    assert len(sector_state["sector_chat"]) == 3

    # Intelligence from chat
    intel = get_sector_intelligence_from_chat(sector_state)
    print(f"  Chat intel extracted: {list(intel.keys())} ✅")
    assert "p3" in intel and "p4" in intel

    # Alliance safe zone
    leader = {"user_id": "l1", "username": "AllianceLeader", "alliance_role": "LEADER"}
    alliance = {"safe_sectors": []}
    ok3, msg3, alliance = set_alliance_safe_sector(leader, 3, alliance, safe=True)
    print(f"  Set safe zone: {'✅' if ok3 else '❌'} {msg3[:50]}")
    assert 3 in alliance["safe_sectors"]

    # Visa policy
    sector_state2 = {"dominance": {"ruler_id": "l1", "ruler_name": "AllianceLeader"}}
    ok4, msg4, sector_state2 = set_visa_policy(leader, 3, sector_state2, [2, 4])
    print(f"  Set visa policy: {'✅' if ok4 else '❌'} {msg4[:50]}")
    assert sector_state2["dominance"]["visa_policy"]["enabled"]

    # Visa check
    user_from_s2 = {"user_id": "p5", "home_sector": 2, "visas": {}}
    needs_visa, visa_msg = check_visa_required(user_from_s2, 3, sector_state2)
    print(f"  Visa required for S2 player: {'✅' if needs_visa else '❌'}")
    assert needs_visa

    user_from_s1 = {"user_id": "p6", "home_sector": 1, "visas": {}}
    needs_visa2, _ = check_visa_required(user_from_s1, 3, sector_state2)
    print(f"  S1 player exempt from visa: {'✅' if not needs_visa2 else '❌'}")
    assert not needs_visa2

    print("  Teleport system: PASS ✅")

    # ── 4. on_user_load migration ─────────────────────────────
    print("\n4. ON_USER_LOAD / MIGRATION")
    from teleport_system import on_user_load

    old_user = {
        "user_id": "p7",
        "username": "OldFormatPlayer",
        "unclaimed_items": [
            {"key": "xp_small", "amount": 21},
            {"key": "xp_small", "amount": 21},
            {"key": "iron",     "amount": 5},
            {"key": "iron",     "amount": 3},
            {"key": "basic_suit", "amount": 1},
        ],
        "researches": {},
        "research_queue": {},
        "base_resources": {"resources": {"wood": 100}},
        "energy": 50,
        "energy_last_regen": None,
    }

    migrated = on_user_load(old_user)
    print(f"  Inventory migrated: {'✅' if isinstance(migrated['inventory'], dict) else '❌'}")
    assert isinstance(migrated["inventory"], dict)
    assert migrated["inventory"]["xp_small"]["qty"] == 42, f"got {migrated['inventory'].get('xp_small')}"
    assert migrated["inventory"]["iron"]["qty"] == 8
    assert migrated["unclaimed_items"] == []
    print(f"  XP stacked: xp_small ×{migrated['inventory']['xp_small']['qty']} ✅")
    print(f"  Iron stacked: iron ×{migrated['inventory']['iron']['qty']} ✅")
    print("  Migration: PASS ✅")

    print("\n" + "=" * 55)
    print("ALL PHASE 2 TESTS PASSED ✅")
    print("=" * 55)
    print("\nFiles ready to deploy:")
    print("  phase2/march_queue.py")
    print("  phase2/suit_system.py")
    print("  phase2/teleport_system.py")
    print("  Apply 4 changes from supabase_db_patch.py to supabase_db.py")


if __name__ == "__main__":
    run_phase2_validation()
