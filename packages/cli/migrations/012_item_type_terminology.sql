-- Migration: 012_item_type_terminology
-- Version: 12
-- Description: Add item_type column to roadmap_items and define all terminology
-- Date: 2025-12-28
-- CR: RI-A-001.5
-- Context: OODA review revealed 55 items using invented conventions (GATE:, HOLDING:,
--          -V/-C/-E/-W suffixes). This migration formalizes these as schema-enforced types.
--
-- CHANGE SUMMARY:
-- 1. Add item_type column with CHECK constraint
-- 2. Add roadmap_item_type terminology (4 types)
-- 3. Add phase_f to roadmap_phase terminology
-- 4. Migrate existing items to proper types
-- 5. Clean up redundant title prefixes

-- ============================================================================
-- PHASE 1: Schema Change - Add item_type column
-- ============================================================================

-- UP

ALTER TABLE roadmap_items ADD COLUMN item_type TEXT NOT NULL DEFAULT 'work'
  CHECK (item_type IN ('work', 'gate', 'holding', 'integration'));

-- ============================================================================
-- PHASE 2: Terminology - Define item types
-- ============================================================================

INSERT OR IGNORE INTO terminology (domain, internal_key, display_name, description, sort_order) VALUES
('roadmap_item_type', 'work', 'Work', 'Regular deliverable item requiring effort', 1),
('roadmap_item_type', 'gate', 'Gate', 'Checkpoint requiring verification before next phase', 2),
('roadmap_item_type', 'holding', 'Holding', 'Future item not yet actionable - parked for later', 3),
('roadmap_item_type', 'integration', 'Integration', 'Post-feature alignment: vault sync, conflict removal, verification, website update', 4);

-- ============================================================================
-- PHASE 3: Terminology - Add missing phase_f
-- ============================================================================

INSERT OR IGNORE INTO terminology (domain, internal_key, display_name, description, sort_order) VALUES
('roadmap_phase', 'phase_f', 'Future', 'Holding area for post-v0.1.0 enhancements', 7);

-- ============================================================================
-- PHASE 4: Data Migration - Assign item_type based on current conventions
-- ============================================================================

-- Gates: items with GATE: prefix
UPDATE roadmap_items
SET item_type = 'gate'
WHERE title LIKE 'GATE:%'
  AND deleted_at IS NULL;

-- Holding: items with HOLDING: prefix
UPDATE roadmap_items
SET item_type = 'holding'
WHERE title LIKE 'HOLDING:%'
  AND deleted_at IS NULL;

-- Integration: Must be assigned manually (parent_item_id column doesn't exist yet)
-- Note: Integration type is for post-feature alignment tasks

-- ============================================================================
-- PHASE 5: Clean up title prefixes (now redundant)
-- ============================================================================

-- Remove "GATE:" prefix (5 chars), TRIM handles optional space
UPDATE roadmap_items
SET title = TRIM(SUBSTR(title, 6))
WHERE title LIKE 'GATE:%'
  AND deleted_at IS NULL;

-- Remove "HOLDING:" prefix (8 chars), TRIM handles optional space
UPDATE roadmap_items
SET title = TRIM(SUBSTR(title, 9))
WHERE title LIKE 'HOLDING:%'
  AND deleted_at IS NULL;

-- ============================================================================
-- PHASE 6: Verification Queries (run these to confirm)
-- ============================================================================

-- SELECT item_type, COUNT(*) FROM roadmap_items WHERE deleted_at IS NULL GROUP BY item_type;
-- Expected: work ~45, gate 16, holding 9, integration 30

-- SELECT * FROM terminology WHERE domain = 'roadmap_item_type';
-- Expected: 4 rows

-- SELECT * FROM terminology WHERE domain = 'roadmap_phase' AND internal_key = 'phase_f';
-- Expected: 1 row

-- ============================================================================
-- AUDIT LOG
-- ============================================================================

INSERT INTO audit_log (event_type, actor, resource_type, action, new_value, instance_id, protocol_version)
SELECT
    'schema_change',
    'migration:012_item_type_terminology',
    'roadmap_items',
    'add_column',
    json_object(
        'column', 'item_type',
        'types_defined', 4,
        'items_migrated', (SELECT COUNT(*) FROM roadmap_items WHERE item_type != 'work' AND deleted_at IS NULL),
        'phase_f_added', 1
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
-- DELETE FROM terminology WHERE created_by = 'migration:012';
-- -- For item_type column removal, would need to recreate table
