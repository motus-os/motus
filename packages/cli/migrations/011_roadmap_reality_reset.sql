-- Migration: 011_roadmap_reality_reset
-- Version: 11
-- Description: Soft-delete old roadmap items and create v0.1.0/v0.2.0 reflecting reality
-- Date: 2025-12-28
-- Context: Previous roadmaps mixed vision with reality. This migration aligns the database
--          with what actually exists: Python CLI (39K lines) + governance layer.
--          Rust kernel (GPT Pro specs) becomes v0.2.0.
--
-- KERNEL-SCHEMA.md timing: To be applied directly before or after monorepo migration.
-- This migration focuses on DATA ALIGNMENT only, not schema changes.

-- UP

-- ============================================================================
-- PHASE 1: Soft-delete all existing roadmap data
-- ============================================================================

UPDATE roadmap_items
SET deleted_at = datetime('now')
WHERE deleted_at IS NULL
  AND created_by LIKE 'migration:%';

-- ============================================================================
-- PHASE 2: Roadmap seed items removed
-- ============================================================================
-- Seed data does not belong in user installs. Any roadmap seeding should be
-- done via explicit dev tooling, not migrations.

-- ============================================================================
-- AUDIT LOG
-- ============================================================================
-- No audit log entry here. Migrations should not inject user-facing roadmap
-- data or record false counts.

-- ============================================================================
-- DOWN
-- (rollback - run manually if needed)
-- ============================================================================
-- DELETE FROM roadmap_items WHERE created_by = 'migration:011';
-- UPDATE roadmap_items SET deleted_at = NULL WHERE deleted_at IS NOT NULL;
