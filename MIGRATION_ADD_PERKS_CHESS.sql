-- Migration: Add Jammer Perk System columns to players table
-- Run this in Supabase SQL Editor to fix the active_perks column error

-- Add active_perks column to store active perk data
ALTER TABLE players
ADD COLUMN IF NOT EXISTS active_perks JSONB DEFAULT '{}'::jsonb;

-- Add bitcoin column (renamed from silver for new economy)
ALTER TABLE players
ADD COLUMN IF NOT EXISTS bitcoin INT DEFAULT 0;

-- Add chess_stats column for chess leaderboard
ALTER TABLE players
ADD COLUMN IF NOT EXISTS chess_stats JSONB DEFAULT '{
  "wins": 0,
  "losses": 0,
  "draws": 0,
  "rating": 1000,
  "games_played": 0,
  "lichess_username": null,
  "recent_games": [],
  "challenges_sent": [],
  "challenges_received": [],
  "streak": 0,
  "best_streak": 0
}'::jsonb;

-- Create indexes for new columns for faster queries
CREATE INDEX IF NOT EXISTS idx_players_active_perks ON players USING GIN(active_perks);
CREATE INDEX IF NOT EXISTS idx_players_chess_stats ON players USING GIN(chess_stats);
CREATE INDEX IF NOT EXISTS idx_players_bitcoin ON players(bitcoin DESC);

-- Verify the changes
SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'players' ORDER BY ordinal_position;
