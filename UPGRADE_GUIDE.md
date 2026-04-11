# THE 64 — UPGRADE GUIDE
## What Changed & How to Integrate

---

### 1. `formatting.py` — Complete Rewrite
**Replace your existing file entirely.**

Key additions:
- `format_grouped_inventory(items, slots_used, slots_total)` — Groups all same-type items together with count. Shows `×3` style. Provides `!use` and `!useall` commands per group.
- `format_grouped_unclaimed(items)` — Same grouping for unclaimed items. Shows `!claim ID` and `!claimall TYPE`.
- `format_full_profile(profile, military)` — Deep profile with XP bar, resources, army.
- `format_training_queue(queue)` — Progress bars per training item.
- `attack_decision_screen(...)` — Pre-battle tension screen.
- `format_scout_report_display(...)` — Clean intelligence dossier.
- `gamemaster_says(message, mood)` — Consistent GM voice.
- `health_bar`, `xp_bar`, `troop_bar` — Richer progress indicators.

---

### 2. `training_system.py` — Troops now cost XP + Resources + Silver
**Replace your existing file entirely.**

Key changes:
- **Every unit now requires BOTH resources AND XP** to train.
- `UNITS` dict defines all stats, costs, food upkeep, and lore per unit.
- `check_training_cost()` validates level gate + all resource types atomically.
- `deduct_training_cost()` deducts wood/bronze/iron/XP/silver in one call.
- `format_unit_catalog(player_level, user)` — Shows all units with lock status.
- Barracks level now grants a **training speed bonus** (5% faster per level).
- Training queue stored in memory `TRAINING_QUEUES` dict — persist to DB if needed.

**Bot command wiring example:**
```python
# !train lancers 5
ok, msg = add_to_training_queue(user_id, "lancers", 5)
await message.reply(msg, parse_mode="Markdown")
```

---

### 3. `revenge_system.py` — Full PvP Engine + Scout Overhaul
**Replace your existing file entirely.**

Key additions:
- `simulate_pvp_battle(attacker_id, defender_id)` — Full stat-based battle simulation using troop stats, wall bonuses, watchtower, revenge multiplier. Automatically handles loot, troop losses, XP rewards, and saving both players.
- `format_full_battle_report(result, is_attacker)` — Generates different report for attacker vs defender perspective.
- `get_revenge_multiplier(user_id, target_id)` — Returns 1.5× if attacking the revenge target.
- `check_incoming_scouts(player_id)` — Shows incoming scout alerts with counter-intel options.
- Scout system now uses in-memory `ACTIVE_SCOUTS` dict (5-minute missions).
- `set_mousetraps`, `activate_firewall`, `set_displayed_stats` all preserved and improved.

**Bot command wiring example:**
```python
# !attack @username
result = simulate_pvp_battle(attacker_id, defender_id)
attacker_report = format_full_battle_report(result, is_attacker=True)
defender_report = format_full_battle_report(result, is_attacker=False)
await bot.send_message(attacker_id, attacker_report, parse_mode="Markdown")
await bot.send_message(defender_id, defender_report, parse_mode="Markdown")
```

---

### 4. `immersive_systems.py` — Deepened Narrative
**Replace your existing file entirely.**

Key additions:
- `format_sector_arrival(sector_id, player_name)` — Atmospheric sector entry.
- `get_influence_tier(level)` — Returns title + description for player's power level.
- `format_victory_ascension` / `format_defeat_devastation` — Updated templates.
- `get_gm_comment(event)` — Dynamic GameMaster commentary for any event type.
- `format_achievement_unlock(achievement_id)` — Clean achievement banner.
- `ACHIEVEMENTS` dict — 6 core achievements defined.

---

### 5. `supabase_db_extensions.py` — New DB Functions
**Merge these functions into your existing `supabase_db.py`.**

New functions:
- `get_grouped_unclaimed(user_id)` — Returns grouped dict for the new UI.
- `claim_all_by_type(user_id, item_type)` — Claim every item of a type in one tap.
- `use_item(user_id, item_type)` — Use one item, apply its effect immediately.
- `use_all_items_of_type(user_id, item_type)` — Use all of a type, stack effects.
- `add_resources(user_id, resources_dict, food)` — Bulk resource addition.
- `deduct_resources(user_id, resources_dict)` — Atomic multi-resource deduction.

**New bot commands to wire up:**
```python
# !claimall wood_crate
ok, msg = claim_all_by_type(user_id, "wood_crate")

# !use shield
ok, msg, effect = use_item(user_id, "shield")

# !useall wood_crate
ok, msg = use_all_items_of_type(user_id, "wood_crate")
```

---

### Inventory Grouping — How It Works

Before (flat list):
```
1. 🪵 Wood Crate
2. 🪵 Wood Crate  
3. 🪵 Wood Crate
4. 🛡️ Shield
```

After (grouped):
```
1. 🪵 Wood Crate ×3  (+75 XP each)
     ├─ Use one: !use wood_crate
     └─ Use all: !useall wood_crate
2. 🛡️ War Shield
     └─ Use: !use shield
```

Same logic applies to `!claims` (unclaimed items) via `format_grouped_unclaimed()`.

---

### Training — What's New

**Before:** Troops only cost wood/bronze/iron.
**After:** Troops cost resources + XP + silver (varies by tier).

| Unit       | Level Req | Wood | Bronze | Iron | XP  | Silver |
|------------|-----------|------|--------|------|-----|--------|
| Pawns      | 1         | 2    | 0      | 0    | 0   | 0      |
| Footmen    | 1         | 5    | 1      | 0    | 10  | 0      |
| Archers    | 2         | 8    | 2      | 0    | 25  | 0      |
| Lancers    | 4         | 0    | 10     | 3    | 50  | 50     |
| Castellans | 7         | 0    | 5      | 15   | 100 | 150    |
| Warlords   | 12        | 0    | 0      | 30   | 250 | 500    |

This makes training a meaningful decision — not just resource spam.
