-- AEGIS C4ISR Database Initialization Script
-- PostgreSQL 16+

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For text search
CREATE EXTENSION IF NOT EXISTS "btree_gin"; -- For multi-column indexes

-- Set row-level security
ALTER DATABASE aegis_c4isr SET row_security = on;

-- Seed default channels
INSERT INTO channels (id, name, description, channel_type, classification, min_role, is_active)
VALUES
    (uuid_generate_v4(), 'Command Net', 'Command and control communications', 'COMMAND', 'SECRET', 'OPERATOR', true),
    (uuid_generate_v4(), 'Alpha Team', 'Alpha team tactical channel', 'TACTICAL', 'SECRET', 'OPERATOR', true),
    (uuid_generate_v4(), 'Bravo Team', 'Bravo team tactical channel', 'TACTICAL', 'SECRET', 'OPERATOR', true),
    (uuid_generate_v4(), 'Drone Ops', 'Drone operations coordination', 'TACTICAL', 'CONFIDENTIAL', 'OPERATOR', true),
    (uuid_generate_v4(), 'Intel Desk', 'Intelligence analysis and sharing', 'INTEL', 'TOP SECRET', 'ANALYST', true),
    (uuid_generate_v4(), 'Emergency', 'Emergency broadcast channel', 'EMERGENCY', 'UNCLASSIFIED', 'VIEWER', true)
ON CONFLICT DO NOTHING;

-- Seed default COMMANDER account
-- Password: AEGIS@Command2026! (CHANGE IMMEDIATELY IN PRODUCTION)
-- Password hash generated with bcrypt rounds=12
INSERT INTO users (id, callsign, email, full_name, password_hash, role, clearance, totp_secret, mfa_enabled, is_active)
VALUES (
    uuid_generate_v4(),
    'CDR.ADMIN',
    'commander@aegis.mil',
    'System Administrator',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYqGo8sSXGC',  -- CHANGE THIS
    'COMMANDER',
    'TOP SECRET',
    NULL,
    false,
    true
)
ON CONFLICT (callsign) DO NOTHING;

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_units_sector ON units(sector);
CREATE INDEX IF NOT EXISTS idx_units_status ON units(status);
CREATE INDEX IF NOT EXISTS idx_threats_severity ON threats(severity);
CREATE INDEX IF NOT EXISTS idx_threats_status ON threats(status);
CREATE INDEX IF NOT EXISTS idx_threats_detected_at ON threats(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_channel_sent ON messages(channel_id, sent_at DESC);
CREATE INDEX IF NOT EXISTS idx_cyber_events_severity ON cyber_events(severity);
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_drones_status ON drones(status);

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO aegis_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO aegis_admin;

-- Success message
DO $$
BEGIN
    RAISE NOTICE '✓ AEGIS C4ISR database initialized successfully';
    RAISE NOTICE '⚠ WARNING: Change default COMMANDER password immediately!';
    RAISE NOTICE '  Default credentials: CDR.ADMIN / AEGIS@Command2026!';
END $$;
