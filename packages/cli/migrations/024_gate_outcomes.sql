-- Migration: 024_gate_outcomes
-- Version: 24
-- Description: Add Work Ledger gate outcomes table
-- Date: 2026-01-13
-- CR: RI-REF-023
--
-- CHANGE SUMMARY:
-- 1. Add gate_outcomes table (append-only)
-- 2. Index by work_id, step_id, gate_id

-- =========================================================================
-- UP
-- =========================================================================

CREATE TABLE IF NOT EXISTS gate_outcomes (
    id TEXT PRIMARY KEY,
    gate_id TEXT NOT NULL,
    result TEXT NOT NULL
        CHECK (result IN ('pass', 'fail')),
    reason TEXT,
    policy_ref TEXT,
    decided_by TEXT NOT NULL,
    decided_at TEXT NOT NULL DEFAULT (datetime('now')),
    work_id TEXT NOT NULL REFERENCES roadmap_items(id),
    step_id TEXT REFERENCES work_steps(id)
);

CREATE INDEX IF NOT EXISTS idx_gate_outcomes_work ON gate_outcomes(work_id);
CREATE INDEX IF NOT EXISTS idx_gate_outcomes_step ON gate_outcomes(step_id);
CREATE INDEX IF NOT EXISTS idx_gate_outcomes_gate ON gate_outcomes(gate_id);

CREATE TRIGGER IF NOT EXISTS gate_outcomes_no_update
BEFORE UPDATE ON gate_outcomes
BEGIN
    SELECT RAISE(ABORT, 'KERNEL: Gate outcomes are immutable. Create new outcomes instead.');
END;

CREATE TRIGGER IF NOT EXISTS gate_outcomes_no_delete
BEFORE DELETE ON gate_outcomes
BEGIN
    SELECT RAISE(ABORT, 'KERNEL: Gate outcomes cannot be deleted.');
END;

INSERT INTO audit_log (event_type, actor, resource_type, action, new_value, instance_id, protocol_version)
SELECT
    'schema_change',
    'migration:024_gate_outcomes',
    'work_ledger',
    'add_table',
    json_object(
        'table', 'gate_outcomes'
    ),
    COALESCE((SELECT value FROM instance_config WHERE key = 'instance_id'), 'unknown'),
    1;

-- =========================================================================
-- DOWN
-- =========================================================================

DROP TRIGGER IF EXISTS gate_outcomes_no_delete;
DROP TRIGGER IF EXISTS gate_outcomes_no_update;
DROP INDEX IF EXISTS idx_gate_outcomes_gate;
DROP INDEX IF EXISTS idx_gate_outcomes_step;
DROP INDEX IF EXISTS idx_gate_outcomes_work;
DROP TABLE IF EXISTS gate_outcomes;
