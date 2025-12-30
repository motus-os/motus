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
  AND id NOT LIKE 'RI-A-0%'
  AND id NOT LIKE 'RI-B-0%'
  AND id NOT LIKE 'RI-C-0%'
  AND id NOT LIKE 'RI-D-0%'
  AND id NOT LIKE 'RI-E-0%'
  AND id NOT LIKE 'RI-020-%';

-- ============================================================================
-- PHASE 2: Create v0.1.0 roadmap items (PYTHON CLI + GOVERNANCE)
-- ============================================================================

-- ============================================================================
-- PHASE A: Foundation (Database + API wiring)
-- ============================================================================

INSERT OR IGNORE INTO roadmap_items (id, phase_key, title, description, status_key, owner, sort_order, scope, created_by) VALUES
('RI-A-001', 'phase_a', 'Apply KERNEL-SCHEMA.md v0.1.2', 'Create migration with 6-table kernel + 3 metadata tables + views', 'pending', NULL, 10, 'system', 'migration:011'),
('RI-A-002', 'phase_a', 'Test kernel schema with existing CLI', 'Verify tables work with current Python code', 'pending', NULL, 20, 'system', 'migration:011'),
('RI-A-003', 'phase_a', 'Wire 6-call API to CLI commands', 'claim_work, get_context, put_outcome, record_evidence, record_decision, release_work', 'pending', NULL, 30, 'system', 'migration:011'),
('RI-A-010', 'phase_a', 'Audit CLI commands against schema', 'mc list, mc history, mc sync, mc web', 'pending', NULL, 40, 'system', 'migration:011'),
('RI-A-011', 'phase_a', 'Remove dead code paths', 'Code referencing old schema', 'pending', NULL, 50, 'system', 'migration:011'),
('RI-A-020', 'phase_a', 'Create schema documentation', 'Document kernel.db and userland.db', 'pending', NULL, 60, 'system', 'migration:011'),
('RI-A-021', 'phase_a', 'Create API documentation', 'Document 6-call API with examples', 'pending', NULL, 70, 'system', 'migration:011');

-- ============================================================================
-- PHASE B: Testing & Hardening
-- ============================================================================

INSERT OR IGNORE INTO roadmap_items (id, phase_key, title, description, status_key, owner, sort_order, scope, created_by) VALUES
('RI-B-001', 'phase_b', 'Unit tests for kernel schema', 'Test triggers, views, constraints', 'pending', NULL, 10, 'system', 'migration:011'),
('RI-B-002', 'phase_b', 'Integration tests for 6-call API', 'End-to-end: claim -> work -> evidence -> decision -> release', 'pending', NULL, 20, 'system', 'migration:011'),
('RI-B-003', 'phase_b', 'Snapshot tests for CLI output', 'Deterministic output verification', 'pending', NULL, 30, 'system', 'migration:011'),
('RI-B-010', 'phase_b', 'Security review', 'Permissions, secrets, attack surface', 'pending', NULL, 40, 'system', 'migration:011'),
('RI-B-011', 'phase_b', 'Performance benchmarks', 'Verify SLOs', 'pending', NULL, 50, 'system', 'migration:011');

-- ============================================================================
-- PHASE C: Monorepo Migration
-- ============================================================================

INSERT OR IGNORE INTO roadmap_items (id, phase_key, title, description, status_key, owner, sort_order, scope, created_by) VALUES
('RI-C-001', 'phase_c', 'Execute MIGRATION-MANIFEST.md Phase 1', 'Copy GPT Pro specs to vault (14 files)', 'pending', NULL, 10, 'system', 'migration:011'),
('RI-C-002', 'phase_c', 'Execute MIGRATION-MANIFEST.md Phase 2-6', 'Handoffs, specs, CRs, archive', 'pending', NULL, 20, 'system', 'migration:011'),
('RI-C-003', 'phase_c', 'Create motus-os/motus monorepo', 'PUBLIC repo - code only', 'pending', NULL, 30, 'system', 'migration:011'),
('RI-C-010', 'phase_c', 'Move Python CLI to monorepo', 'Preserve git history', 'pending', NULL, 40, 'system', 'migration:011'),
('RI-C-011', 'phase_c', 'Move website to monorepo', 'packages/website/', 'pending', NULL, 50, 'system', 'migration:011'),
('RI-C-012', 'phase_c', 'Configure CI/CD', 'GitHub Actions', 'pending', NULL, 60, 'system', 'migration:011'),
('RI-C-020', 'phase_c', 'Fresh clone verification', 'New user can clone + build + test', 'pending', NULL, 70, 'system', 'migration:011'),
('RI-C-021', 'phase_c', 'Archive old repos', 'Archive legacy repos -> read-only', 'pending', NULL, 80, 'system', 'migration:011'),
('RI-C-030', 'phase_c', 'Decide: KERNEL-SCHEMA before or after monorepo', 'Timing decision for schema migration', 'pending', NULL, 5, 'system', 'migration:011'),
('RI-C-031', 'phase_c', 'Apply KERNEL-SCHEMA.md if before monorepo', 'Or defer to Phase D', 'pending', NULL, 6, 'system', 'migration:011');

-- ============================================================================
-- PHASE D: Release Preparation
-- ============================================================================

INSERT OR IGNORE INTO roadmap_items (id, phase_key, title, description, status_key, owner, sort_order, scope, created_by) VALUES
('RI-D-001', 'phase_d', 'Write README.md for public consumption', 'Clear getting-started', 'pending', NULL, 10, 'system', 'migration:011'),
('RI-D-002', 'phase_d', 'Write CHANGELOG for v0.1.0', 'Document what shipped', 'pending', NULL, 20, 'system', 'migration:011'),
('RI-D-010', 'phase_d', 'PyPI package preparation', 'pip install motus works', 'pending', NULL, 30, 'system', 'migration:011'),
('RI-D-011', 'phase_d', 'License verification', 'Dependencies compatible', 'pending', NULL, 40, 'system', 'migration:011'),
('RI-D-020', 'phase_d', 'Release checklist execution', 'All green', 'pending', NULL, 50, 'system', 'migration:011');

-- ============================================================================
-- PHASE E: v0.1.0 Launch
-- ============================================================================

INSERT OR IGNORE INTO roadmap_items (id, phase_key, title, description, status_key, owner, sort_order, scope, created_by) VALUES
('RI-E-001', 'phase_e', 'Tag v0.1.0 release', 'Git tag + GitHub release', 'pending', NULL, 10, 'system', 'migration:011'),
('RI-E-002', 'phase_e', 'Publish to PyPI', 'pip install motus', 'pending', NULL, 20, 'system', 'migration:011'),
('RI-E-003', 'phase_e', 'Website announcement', 'motusos.ai launch', 'pending', NULL, 30, 'system', 'migration:011');

-- ============================================================================
-- PHASE 3: Create v0.2.0 roadmap items (RUST KERNEL - Future)
-- ============================================================================

INSERT OR IGNORE INTO roadmap_items (id, phase_key, title, description, status_key, owner, sort_order, scope, created_by) VALUES
('RI-020-001', 'phase_a', 'Design Rust crate structure', 'Based on MOTUS-SPEC-V0.1.md types', 'pending', NULL, 10, 'system', 'migration:011'),
('RI-020-002', 'phase_a', 'Implement WorkReceipt schema', 'Canonical JSON, SHA-256', 'pending', NULL, 20, 'system', 'migration:011'),
('RI-020-003', 'phase_a', 'Implement Merkle root computation', 'Domain separators per spec', 'pending', NULL, 30, 'system', 'migration:011'),
('RI-020-004', 'phase_a', 'Implement FSM-0.1 state machine', 'Lock level transitions', 'pending', NULL, 40, 'system', 'migration:011'),
('RI-020-005', 'phase_a', 'Implement verify_bundle()', 'Bundle verification', 'pending', NULL, 50, 'system', 'migration:011'),
('RI-020-010', 'phase_b', 'Human-side checks (MOTUS-HUMAN-SPEC)', 'EMPATHY, PURPOSE, HUMILITY, PERSPECTIVE, TRUTH, FITNESS', 'pending', NULL, 60, 'system', 'migration:011'),
('RI-020-011', 'phase_b', 'Golden bundle tests', 'Run MOTUS-GOLDEN-BUNDLES-V0.1.zip fixtures', 'pending', NULL, 70, 'system', 'migration:011'),
('RI-020-020', 'phase_c', 'Python bindings (PyO3)', 'motus-py wrapper', 'pending', NULL, 80, 'system', 'migration:011'),
('RI-020-021', 'phase_c', 'Migration path from v0.1.0', 'Preserve kernel.db data', 'pending', NULL, 90, 'system', 'migration:011');

-- ============================================================================
-- AUDIT LOG
-- ============================================================================

INSERT INTO audit_log (event_type, actor, resource_type, action, new_value, instance_id, protocol_version)
SELECT
    'roadmap_reset',
    'migration:011_roadmap_reality_reset',
    'roadmap',
    'reset',
    json_object(
        'reason', 'Align roadmap with reality: Python CLI = v0.1.0, Rust kernel = v0.2.0',
        'v010_items', 28,
        'v020_items', 9
    ),
    COALESCE((SELECT value FROM instance_config WHERE key = 'instance_id'), 'unknown'),
    1;

-- ============================================================================
-- DOWN
-- (rollback - run manually if needed)
-- ============================================================================
-- DELETE FROM roadmap_items WHERE created_by = 'migration:011';
-- UPDATE roadmap_items SET deleted_at = NULL WHERE deleted_at IS NOT NULL;
