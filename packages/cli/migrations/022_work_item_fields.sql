-- Migration: 022_work_item_fields
-- Version: 22
-- Description: Add Work Ledger fields to roadmap_items
-- Date: 2026-01-13
-- CR: RI-REF-021
--
-- CHANGE SUMMARY:
-- 1. Add Work Item alignment fields (mode, work_type, routing_class, program_ref)
-- 2. Add confidence/substate fields
-- 3. Add claim/release timing fields
-- 4. Add indexes for work_type and program_ref

-- =========================================================================
-- UP
-- =========================================================================

ALTER TABLE roadmap_items ADD COLUMN mode TEXT NOT NULL DEFAULT 'bypass'
  CHECK (mode IN ('bypass', 'expanded'));

ALTER TABLE roadmap_items ADD COLUMN work_type TEXT NOT NULL DEFAULT 'planning';

ALTER TABLE roadmap_items ADD COLUMN routing_class TEXT NOT NULL DEFAULT 'deterministic'
  CHECK (routing_class IN ('deterministic', 'review'));

ALTER TABLE roadmap_items ADD COLUMN program_ref TEXT;
ALTER TABLE roadmap_items ADD COLUMN intent TEXT;

ALTER TABLE roadmap_items ADD COLUMN confidence_level TEXT
  CHECK (confidence_level IN ('routine', 'important', 'critical', 'irreversible'));

ALTER TABLE roadmap_items ADD COLUMN confidence_score INTEGER
  CHECK (confidence_score BETWEEN 0 AND 100);

ALTER TABLE roadmap_items ADD COLUMN substate TEXT
  CHECK (substate IN ('waiting_on_dependency', 'blocked_on_decision'));

ALTER TABLE roadmap_items ADD COLUMN claimed_at TEXT;
ALTER TABLE roadmap_items ADD COLUMN released_at TEXT;
ALTER TABLE roadmap_items ADD COLUMN lease_expires_at TEXT;

CREATE INDEX IF NOT EXISTS idx_roadmap_work_type
ON roadmap_items(work_type)
WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_roadmap_program_ref
ON roadmap_items(program_ref)
WHERE deleted_at IS NULL;

-- =========================================================================
-- AUDIT LOG
-- =========================================================================

INSERT INTO audit_log (event_type, actor, resource_type, action, new_value, instance_id, protocol_version)
SELECT
    'schema_change',
    'migration:022_work_item_fields',
    'roadmap_items',
    'add_columns',
    json_object(
        'columns', json_array(
            'mode',
            'work_type',
            'routing_class',
            'program_ref',
            'intent',
            'confidence_level',
            'confidence_score',
            'substate',
            'claimed_at',
            'released_at',
            'lease_expires_at'
        ),
        'indexes', json_array('idx_roadmap_work_type', 'idx_roadmap_program_ref')
    ),
    COALESCE((SELECT value FROM instance_config WHERE key = 'instance_id'), 'unknown'),
    1;

-- =========================================================================
-- DOWN
-- =========================================================================
-- NOTE: SQLite doesn't support DROP COLUMN easily.
-- Rollback requires table recreation.
--
-- DROP INDEX IF EXISTS idx_roadmap_program_ref;
-- DROP INDEX IF EXISTS idx_roadmap_work_type;
