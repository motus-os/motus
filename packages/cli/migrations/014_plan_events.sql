-- Migration: 014_plan_events
-- Version: 14
-- Description: Add plan_events table for PPP event log
-- Date: 2025-12-30
-- CR: P0-021
--
-- CHANGE SUMMARY:
-- 1. Create plan_events table (canonical event log)
-- 2. Add indexes for item, timestamp, and source lookups

-- ============================================================================
-- PHASE 1: Schema Change - Create plan_events table
-- ============================================================================

-- UP

CREATE TABLE plan_events (
    event_id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    ts TEXT NOT NULL,
    actor TEXT NOT NULL,
    actor_type TEXT NOT NULL CHECK (actor_type IN ('user', 'service', 'agent', 'system')),
    source TEXT NOT NULL,
    event_type TEXT NOT NULL,
    item_id TEXT,
    external_id TEXT,
    payload TEXT NOT NULL,
    expected_version TEXT,
    conflict_policy TEXT,

    -- Audit
    received_at TEXT NOT NULL DEFAULT (datetime('now')),
    processed_at TEXT,
    process_result TEXT CHECK (process_result IN ('applied', 'rejected', 'conflict') OR process_result IS NULL)
);

-- ============================================================================
-- PHASE 2: Indexes
-- ============================================================================

CREATE INDEX idx_plan_events_item ON plan_events(item_id);
CREATE INDEX idx_plan_events_ts ON plan_events(ts);
CREATE INDEX idx_plan_events_source ON plan_events(source);

-- ============================================================================
-- PHASE 3: Verification Queries (run these to confirm)
-- ============================================================================

-- PRAGMA table_info(plan_events);
-- Expected: columns match PPP-0.1 plan_events schema

-- SELECT COUNT(*) FROM plan_events;
-- Expected: 0 before event ingestion

-- ============================================================================
-- AUDIT LOG
-- ============================================================================

INSERT INTO audit_log (event_type, actor, resource_type, action, new_value, instance_id, protocol_version)
SELECT
    'schema_change',
    'migration:014_plan_events',
    'plan_events',
    'create_table',
    json_object(
        'indexes', json_array('idx_plan_events_item', 'idx_plan_events_ts', 'idx_plan_events_source')
    ),
    COALESCE((SELECT value FROM instance_config WHERE key = 'instance_id'), 'unknown'),
    1;

-- ============================================================================
-- DOWN
-- ============================================================================

DROP INDEX IF EXISTS idx_plan_events_source;
DROP INDEX IF EXISTS idx_plan_events_ts;
DROP INDEX IF EXISTS idx_plan_events_item;
DROP TABLE IF EXISTS plan_events;
