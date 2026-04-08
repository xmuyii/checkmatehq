-- SQL Setup Script for The 64 Game on Supabase
-- Execute this in your Supabase SQL Editor

-- Create players table with proper schema
CREATE TABLE IF NOT EXISTS players (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT UNIQUE NOT NULL,
    username TEXT NOT NULL,
    all_time_points INT DEFAULT 0,
    weekly_points INT DEFAULT 0,
    week_start TIMESTAMPTZ DEFAULT NOW(),
    total_words INT DEFAULT 0,
    silver INT DEFAULT 0,
    xp INT DEFAULT 0,
    level INT DEFAULT 1,
    backpack_slots INT DEFAULT 5,
    backpack_image TEXT DEFAULT 'normal_backpack',
    inventory JSONB DEFAULT '[]'::jsonb,
    unclaimed_items JSONB DEFAULT '[]'::jsonb,
    sector INT,
    completed_tutorial BOOLEAN DEFAULT FALSE,
    last_level INT DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_players_user_id ON players(user_id);
CREATE INDEX IF NOT EXISTS idx_players_weekly_points ON players(weekly_points DESC);
CREATE INDEX IF NOT EXISTS idx_players_all_time_points ON players(all_time_points DESC);

-- Enable Row-Level Security (RLS) for security
ALTER TABLE players ENABLE ROW LEVEL SECURITY;

-- Create policy allowing service role write access (for bot)
CREATE POLICY "service_role_full_access" ON players
    FOR ALL
    USING (auth.uid()::text IS NOT NULL OR current_setting('role') = 'authenticated')
    WITH CHECK (true);

-- If you want public read access to leaderboards:
CREATE POLICY "public_read_leaderboard" ON players
    FOR SELECT
    USING (true);

-- Also create a weekly leaderboard view for efficiency
CREATE OR REPLACE VIEW weekly_leaderboard AS
SELECT user_id, username, weekly_points, level
FROM players
ORDER BY weekly_points DESC
LIMIT 10;

CREATE OR REPLACE VIEW alltime_leaderboard AS
SELECT user_id, username, all_time_points, total_words, level
FROM players
ORDER BY all_time_points DESC
LIMIT 10;

-- Create updated_at trigger for automatic timestamp updates
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_players_updated_at BEFORE UPDATE ON players
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Test insert (optional - remove after testing)
-- INSERT INTO players (user_id, username) VALUES ('test_user_123', 'TestPlayer')
-- ON CONFLICT (user_id) DO UPDATE SET username = 'TestPlayer';
