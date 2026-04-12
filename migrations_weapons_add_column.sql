-- Migration: Add weapons column to players table if it doesn't exist
-- This stores weapon inventory as JSON: {"weapon_id": charges_remaining}
-- Example: {"machine_gun_turret": 1, "plasma_cannon": 2}

ALTER TABLE players 
ADD COLUMN IF NOT EXISTS weapons jsonb DEFAULT '{}'::jsonb;

-- Create an index for faster queries
CREATE INDEX IF NOT EXISTS idx_players_weapons ON players USING gin(weapons);

-- Example weapons structure (for reference):
-- {
--   "machine_gun_turret": 1,
--   "plasma_cannon": 2,
--   "emp_blast": 3,
--   "xp_siphon": 1
-- }
