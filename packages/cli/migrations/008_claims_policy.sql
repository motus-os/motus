-- Migration: 008_claims_policy
-- Version: 8
-- Description: Claims tracking + policy enforcement for deploys

-- UP

CREATE TABLE IF NOT EXISTS claims (
    id TEXT PRIMARY KEY,
    claim_text TEXT NOT NULL CHECK (LENGTH(claim_text) >= 5),
    page TEXT NOT NULL,
    claim_type TEXT NOT NULL CHECK (claim_type IN ('quantitative', 'qualitative')),
    test_file TEXT,
    test_function TEXT,
    test_status TEXT DEFAULT 'pending'
        CHECK (test_status IN ('pending', 'pass', 'fail', 'stale')),
    last_verified_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),

    -- POLICY: Quantitative claims MUST have test function
    CHECK (claim_type != 'quantitative' OR test_function IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_claims_status ON claims(test_status);
CREATE INDEX IF NOT EXISTS idx_claims_page ON claims(page);

CREATE TABLE IF NOT EXISTS deployment_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target TEXT NOT NULL CHECK (target IN ('website', 'pypi', 'docs')),
    version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'in_progress', 'success', 'failed', 'blocked')),
    triggered_by TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT
);

-- POLICY: Cannot deploy with failed claims
CREATE TRIGGER IF NOT EXISTS enforce_deploy_gate
BEFORE INSERT ON deployment_events
WHEN NEW.target = 'website'
BEGIN
    SELECT CASE
        WHEN EXISTS (
            SELECT 1 FROM claims
            WHERE test_status = 'fail'
            AND test_function IS NOT NULL
        )
        THEN RAISE(ABORT, 'POLICY: Cannot deploy - failed claims exist. Query v_deploy_blockers.')
    END;
END;

-- POLICY: Completed items are immutable (uses existing roadmap_items)
CREATE TRIGGER IF NOT EXISTS enforce_completed_immutable
BEFORE UPDATE ON roadmap_items
WHEN OLD.status_key = 'completed' AND NEW.status_key != 'completed'
BEGIN
    SELECT RAISE(ABORT, 'POLICY: Completed items cannot be modified');
END;

-- POLICY: Cardinality limit on active items per phase (uses existing roadmap_items)
CREATE TRIGGER IF NOT EXISTS enforce_phase_limit
BEFORE INSERT ON roadmap_items
BEGIN
    SELECT CASE
        WHEN (
            SELECT COUNT(*) FROM roadmap_items
            WHERE phase_key = NEW.phase_key
            AND status_key NOT IN ('completed', 'cancelled')
            AND deleted_at IS NULL
        ) >= 50
        THEN RAISE(ABORT, 'POLICY: Maximum 50 active items per phase')
    END;
END;

CREATE VIEW IF NOT EXISTS v_can_deploy AS
SELECT
    'website' as target,
    CASE
        WHEN EXISTS (SELECT 1 FROM claims WHERE test_status = 'fail')
        THEN 'BLOCKED'
        WHEN EXISTS (
            SELECT 1 FROM claims
            WHERE test_status = 'pending'
            AND claim_type = 'quantitative'
        )
        THEN 'PENDING'
        ELSE 'READY'
    END as status,
    (SELECT COUNT(*) FROM claims WHERE test_status = 'fail') as failed_count,
    (SELECT GROUP_CONCAT(id, ', ') FROM claims WHERE test_status = 'fail') as failed_claims;

CREATE VIEW IF NOT EXISTS v_claims_needing_tests AS
SELECT id, claim_text, page
FROM claims
WHERE claim_type = 'quantitative'
AND (test_function IS NULL OR test_status = 'pending');

CREATE VIEW IF NOT EXISTS v_deploy_blockers AS
SELECT
    id,
    claim_text,
    page,
    test_function,
    test_status,
    last_verified_at
FROM claims
WHERE test_status IN ('fail', 'stale')
ORDER BY last_verified_at ASC;

-- DOWN

DROP VIEW IF EXISTS v_deploy_blockers;
DROP VIEW IF EXISTS v_claims_needing_tests;
DROP VIEW IF EXISTS v_can_deploy;

DROP TRIGGER IF EXISTS enforce_phase_limit;
DROP TRIGGER IF EXISTS enforce_completed_immutable;
DROP TRIGGER IF EXISTS enforce_deploy_gate;

DROP INDEX IF EXISTS idx_claims_page;
DROP INDEX IF EXISTS idx_claims_status;

DROP TABLE IF EXISTS deployment_events;
DROP TABLE IF EXISTS claims;
