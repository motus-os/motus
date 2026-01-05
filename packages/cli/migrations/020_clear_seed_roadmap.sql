-- Migration: 020_clear_seed_roadmap
-- Version: 20
-- Description: Remove internal roadmap seed items from public installs
-- Date: 2026-01-05
--
-- Rationale: Migration 011 seeds internal roadmap items for development.
-- Public installs must start with an empty roadmap. This migration removes
-- items created by migration:011 while preserving user-created items.

-- UP

-- Audit trail (capture count before deletion)
INSERT INTO audit_log (event_type, actor, resource_type, action, new_value, instance_id, protocol_version)
SELECT
    'roadmap_cleanup',
    'migration:020_clear_seed_roadmap',
    'roadmap',
    'delete_seeded_items',
    json_object(
        'deleted_items', (
            SELECT COUNT(*) FROM roadmap_items
            WHERE created_by IN ('migration:011', 'migration:011_roadmap_reality_reset')
        )
    ),
    COALESCE((SELECT value FROM instance_config WHERE key = 'instance_id'), 'unknown'),
    1;

-- Remove any assignments/dependencies tied to seeded items first (FK safety)
DELETE FROM roadmap_assignments
WHERE item_id IN (
    SELECT id FROM roadmap_items
    WHERE created_by IN ('migration:011', 'migration:011_roadmap_reality_reset')
);

DELETE FROM roadmap_dependencies
WHERE item_id IN (
    SELECT id FROM roadmap_items
    WHERE created_by IN ('migration:011', 'migration:011_roadmap_reality_reset')
)
   OR depends_on_id IN (
    SELECT id FROM roadmap_items
    WHERE created_by IN ('migration:011', 'migration:011_roadmap_reality_reset')
);

-- Remove seeded roadmap items
DELETE FROM roadmap_items
WHERE created_by IN ('migration:011', 'migration:011_roadmap_reality_reset');

-- DOWN
-- No automatic rollback. Seed data removal is intentional for public installs.
