-- Migration: 013_add_roadmap_external_fields
-- Version: 13
-- Description: Add external_id/external_url/raw_status/raw_type to roadmap_items
-- Date: 2025-12-30
-- CR: P0-020
--
-- CHANGE SUMMARY:
-- 1. Add provider linkage columns to roadmap_items
-- 2. Index external_id for lookups

-- ============================================================================
-- PHASE 1: Schema Change - Add provider linkage columns
-- ============================================================================

-- UP

ALTER TABLE roadmap_items ADD COLUMN external_id TEXT;
ALTER TABLE roadmap_items ADD COLUMN external_url TEXT;
ALTER TABLE roadmap_items ADD COLUMN raw_status TEXT;
ALTER TABLE roadmap_items ADD COLUMN raw_type TEXT;

-- ============================================================================
-- PHASE 2: Indexes
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_roadmap_external_id
ON roadmap_items(external_id)
WHERE deleted_at IS NULL;

-- ============================================================================
-- PHASE 3: Verification Queries (run these to confirm)
-- ============================================================================

-- PRAGMA table_info(roadmap_items);
-- Expected: external_id, external_url, raw_status, raw_type columns present

-- SELECT COUNT(*) FROM roadmap_items WHERE external_id IS NOT NULL;
-- Expected: 0 until external providers are integrated

-- ============================================================================
-- AUDIT LOG
-- ============================================================================

INSERT INTO audit_log (event_type, actor, resource_type, action, new_value, instance_id, protocol_version)
SELECT
    'schema_change',
    'migration:013_add_roadmap_external_fields',
    'roadmap_items',
    'add_columns',
    json_object(
        'columns', json_array('external_id', 'external_url', 'raw_status', 'raw_type'),
        'indexes', json_array('idx_roadmap_external_id')
    ),
    COALESCE((SELECT value FROM instance_config WHERE key = 'instance_id'), 'unknown'),
    1;

-- ============================================================================
-- DOWN
-- (rollback - run manually if needed)
-- ============================================================================
-- NOTE: SQLite doesn't support DROP COLUMN easily.
-- Rollback would require table recreation.
--
-- DROP INDEX IF EXISTS idx_roadmap_external_id;
