-- LoadSuite PostgreSQL Schema
-- Run this after creating the database in cPanel

-- =============================================================================
-- Users table (for future auth expansion)
-- =============================================================================
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(64) PRIMARY KEY,
    email VARCHAR(255) UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Insert default user for anonymous/demo usage
INSERT INTO users (id, email) VALUES ('default', NULL)
ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- User Preferences
-- =============================================================================
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id VARCHAR(64) PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    equipment_types TEXT[],  -- Array of strings
    max_deadhead_miles REAL,
    max_weight_lbs INTEGER,
    min_weight_lbs INTEGER,
    cost_per_mile REAL,
    preferred_lanes TEXT[],  -- Array of 'origin:destination' strings
    home_base VARCHAR(128),
    hazmat_endorsed BOOLEAN,
    min_broker_rating REAL,
    min_rpm REAL,
    greenlight_threshold REAL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- Loads (cached from external sources or synthetic)
-- =============================================================================
CREATE TABLE IF NOT EXISTS loads (
    id VARCHAR(64) PRIMARY KEY,
    
    -- Origin
    origin_city VARCHAR(128) NOT NULL,
    origin_state VARCHAR(8) NOT NULL,
    
    -- Destination
    dest_city VARCHAR(128) NOT NULL,
    dest_state VARCHAR(8) NOT NULL,
    
    -- Timing
    pickup_start TIMESTAMPTZ NOT NULL,
    pickup_end TIMESTAMPTZ NOT NULL,
    delivery_start TIMESTAMPTZ NOT NULL,
    delivery_end TIMESTAMPTZ NOT NULL,
    
    -- Load details
    equipment VARCHAR(64) NOT NULL,
    weight_lbs INTEGER NOT NULL CHECK (weight_lbs >= 0),
    hazmat BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Financials
    distance_miles REAL NOT NULL CHECK (distance_miles >= 0),
    deadhead_miles REAL NOT NULL DEFAULT 0 CHECK (deadhead_miles >= 0),
    rate_total_usd REAL NOT NULL CHECK (rate_total_usd >= 0),
    rpm REAL NOT NULL CHECK (rpm >= 0),
    
    -- Broker
    broker_name VARCHAR(255) NOT NULL,
    broker_rating REAL NOT NULL CHECK (broker_rating >= 0 AND broker_rating <= 5),
    
    -- Flags
    detention BOOLEAN NOT NULL DEFAULT FALSE,
    multi_stop BOOLEAN NOT NULL DEFAULT FALSE,
    lane_history BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Other
    commodity VARCHAR(255),
    posted_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Soft delete support
    deleted_at TIMESTAMPTZ
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_loads_origin_state ON loads(origin_state);
CREATE INDEX IF NOT EXISTS idx_loads_dest_state ON loads(dest_state);
CREATE INDEX IF NOT EXISTS idx_loads_equipment ON loads(equipment);
CREATE INDEX IF NOT EXISTS idx_loads_pickup_start ON loads(pickup_start);
CREATE INDEX IF NOT EXISTS idx_loads_rpm ON loads(rpm);
CREATE INDEX IF NOT EXISTS idx_loads_posted_at ON loads(posted_at);

-- =============================================================================
-- Watchlist Items
-- =============================================================================
CREATE TABLE IF NOT EXISTS watchlist_items (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_type VARCHAR(16) NOT NULL CHECK (item_type IN ('load', 'lane')),
    load_id VARCHAR(64),
    lane VARCHAR(255),  -- 'origin:destination' format
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Ensure load_id is set for 'load' type, lane for 'lane' type
    CONSTRAINT watchlist_item_type_check CHECK (
        (item_type = 'load' AND load_id IS NOT NULL) OR
        (item_type = 'lane' AND lane IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_watchlist_user ON watchlist_items(user_id);
CREATE INDEX IF NOT EXISTS idx_watchlist_load ON watchlist_items(load_id) WHERE load_id IS NOT NULL;

-- =============================================================================
-- Alert Rules
-- =============================================================================
CREATE TABLE IF NOT EXISTS alert_rules (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    conditions JSONB NOT NULL DEFAULT '[]',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_triggered TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_alert_rules_user ON alert_rules(user_id);
CREATE INDEX IF NOT EXISTS idx_alert_rules_enabled ON alert_rules(user_id, enabled) WHERE enabled = TRUE;

-- =============================================================================
-- Filter Presets
-- =============================================================================
CREATE TABLE IF NOT EXISTS filter_presets (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    filters JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_filter_presets_user ON filter_presets(user_id);

-- =============================================================================
-- Market Data Cache (for future market integration)
-- =============================================================================
CREATE TABLE IF NOT EXISTS market_data_cache (
    lane_key VARCHAR(255) PRIMARY KEY,  -- 'origin_city_state:dest_city_state'
    avg_rate_per_mile REAL,
    load_to_truck_ratio REAL,
    trend VARCHAR(16),  -- 'rising', 'falling', 'stable'
    confidence REAL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_market_data_expires ON market_data_cache(expires_at);

-- =============================================================================
-- Helper function for updated_at triggers
-- =============================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers
CREATE TRIGGER update_user_preferences_updated_at
    BEFORE UPDATE ON user_preferences
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_loads_updated_at
    BEFORE UPDATE ON loads
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
