-- Migration: 023_work_steps_artifacts
-- Version: 23
-- Description: Add Work Ledger steps + artifacts tables
-- Date: 2026-01-13
-- CR: RI-REF-022
--
-- CHANGE SUMMARY:
-- 1. Add work_steps table (sequence, ooda_tag, confidence)
-- 2. Add work_artifacts table (artifact registry aligned)
-- 3. Seed Work Ledger artifact types in terminology

-- =========================================================================
-- UP
-- =========================================================================

CREATE TABLE IF NOT EXISTS work_steps (
    id TEXT PRIMARY KEY,
    work_id TEXT NOT NULL REFERENCES roadmap_items(id),
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'in_progress', 'blocked', 'completed')),
    owner TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    action_type TEXT,
    ooda_tag TEXT
        CHECK (ooda_tag IN ('observe', 'orient', 'decide', 'act')),
    confidence_level TEXT
        CHECK (confidence_level IN ('routine', 'important', 'critical', 'irreversible')),
    confidence_score INTEGER
        CHECK (confidence_score BETWEEN 0 AND 100),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    started_at TEXT,
    completed_at TEXT,
    UNIQUE (work_id, sequence)
);

CREATE INDEX IF NOT EXISTS idx_work_steps_work ON work_steps(work_id);
CREATE INDEX IF NOT EXISTS idx_work_steps_status ON work_steps(status);

CREATE TABLE IF NOT EXISTS work_artifacts (
    id TEXT PRIMARY KEY,
    artifact_type TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    hash TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    work_id TEXT NOT NULL REFERENCES roadmap_items(id),
    step_id TEXT REFERENCES work_steps(id)
);

CREATE INDEX IF NOT EXISTS idx_work_artifacts_work ON work_artifacts(work_id);
CREATE INDEX IF NOT EXISTS idx_work_artifacts_step ON work_artifacts(step_id);
CREATE INDEX IF NOT EXISTS idx_work_artifacts_type ON work_artifacts(artifact_type);
CREATE INDEX IF NOT EXISTS idx_work_artifacts_hash ON work_artifacts(hash);

CREATE TRIGGER IF NOT EXISTS work_artifacts_no_update
BEFORE UPDATE ON work_artifacts
BEGIN
    SELECT RAISE(ABORT, 'KERNEL: Work artifacts are immutable. Create new artifacts instead.');
END;

CREATE TRIGGER IF NOT EXISTS work_artifacts_no_delete
BEFORE DELETE ON work_artifacts
BEGIN
    SELECT RAISE(ABORT, 'KERNEL: Work artifacts cannot be deleted.');
END;

INSERT OR IGNORE INTO terminology (domain, internal_key, display_name, description, sort_order) VALUES
('artifact_type', 'evidence', 'Evidence', 'Verification artifact or proof', 1),
('artifact_type', 'receipt', 'Receipt', 'Signed completion receipt', 2),
('artifact_type', 'charter_ref', 'Charter Ref', 'Program charter reference', 3),
('artifact_type', 'template_ref', 'Template Ref', 'Workflow template reference', 4),
('artifact_type', 'standard_ref', 'Standard Ref', 'Standard or policy reference', 5),
('artifact_type', 'reflection_note', 'Reflection Note', 'Reflection on work execution', 6),
('artifact_type', 'decision_note', 'Decision Note', 'Decision rationale note', 7),
('artifact_type', 'learning_note', 'Learning Note', 'Learned outcome summary', 8),
('artifact_type', 'cr_ref', 'CR Ref', 'Change request reference', 9),
('artifact_type', 'pr_ref', 'PR Ref', 'Pull request reference', 10),
('artifact_type', 'routing_manifest', 'Routing Manifest', 'Routing decision record', 11),
('artifact_type', 'sign_off', 'Sign Off', 'Reviewer approval record', 12),
('artifact_type', 'waiver', 'Waiver', 'Policy bypass record', 13);

INSERT INTO audit_log (event_type, actor, resource_type, action, new_value, instance_id, protocol_version)
SELECT
    'schema_change',
    'migration:023_work_steps_artifacts',
    'work_ledger',
    'add_tables',
    json_object(
        'tables', json_array('work_steps', 'work_artifacts'),
        'artifact_types', 13
    ),
    COALESCE((SELECT value FROM instance_config WHERE key = 'instance_id'), 'unknown'),
    1;

-- =========================================================================
-- DOWN
-- =========================================================================

DROP TRIGGER IF EXISTS work_artifacts_no_delete;
DROP TRIGGER IF EXISTS work_artifacts_no_update;
DROP INDEX IF EXISTS idx_work_artifacts_hash;
DROP INDEX IF EXISTS idx_work_artifacts_type;
DROP INDEX IF EXISTS idx_work_artifacts_step;
DROP INDEX IF EXISTS idx_work_artifacts_work;
DROP TABLE IF EXISTS work_artifacts;
DROP INDEX IF EXISTS idx_work_steps_status;
DROP INDEX IF EXISTS idx_work_steps_work;
DROP TABLE IF EXISTS work_steps;
