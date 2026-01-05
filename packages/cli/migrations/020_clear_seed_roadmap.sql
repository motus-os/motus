-- Migration: 020_clear_seed_roadmap
-- Version: 20
-- Description: Remove internal roadmap seed items from public installs
-- Date: 2026-01-05
--
-- Rationale: Migration 011 seeds internal roadmap items for development.
-- Public installs must start with an empty roadmap. This migration removes
-- items created by migration:011 while preserving user-created items.

-- UP

-- Audit trail intentionally skipped here.
-- This migration must be safe even when audit_log is absent (legacy upgrade tests).

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
