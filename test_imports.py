#!/usr/bin/env python
"""Quick test to verify all imports work."""

try:
    print("Testing imports...")
    from base_layout import (
        render_tactical_map, render_scouting_intel, get_sector_by_id,
        place_building_in_sector, upgrade_building_in_sector, 
        complete_upgrade_in_sector, parse_callback_data, 
        initialize_user_base_layout, generate_sector_buttons, 
        COMPASS_SECTORS, EMOJI_MAPPING, SECTOR_THREAT_LEVEL,
        get_default_base_layout
    )
    print("✅ base_layout imports OK")
    
    from tactical_base_handlers import router
    print("✅ tactical_base_handlers imports OK")
    
    from supabase_db import get_user, save_user
    print("✅ supabase_db imports OK")
    
    from build_system import BUILDING_TYPES, calculate_building_cost, get_build_time
    print("✅ build_system imports OK")
    
    print("\n✅✅✅ ALL IMPORTS SUCCESSFUL! ✅✅✅")
    
except Exception as e:
    print(f"\n❌ Import Error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
