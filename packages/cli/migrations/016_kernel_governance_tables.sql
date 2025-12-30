-- Migration 016: Add kernel governance tables (KERNEL-SCHEMA v0.1.3)
-- Purpose: Align kernel governance schema with KERNEL-SCHEMA v0.1.3
-- Notes: Legacy kernel_* tables retained for compatibility with current API usage.

-- UP

-- =============================================================================
-- KERNEL SCHEMA v0.1.3 (spec tables)
-- =============================================================================

-- Metadata table: compiled_contracts (self-sufficient audit)
CREATE TABLE IF NOT EXISTS compiled_contracts (
    contract_hash TEXT PRIMARY KEY,
    compiled_json TEXT NOT NULL,
    source_refs_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TRIGGER IF NOT EXISTS compiled_contracts_no_update
BEFORE UPDATE ON compiled_contracts
BEGIN
    SELECT RAISE(ABORT, 'KERNEL: Compiled contracts are immutable');
END;

CREATE TRIGGER IF NOT EXISTS compiled_contracts_no_delete
BEFORE DELETE ON compiled_contracts
BEGIN
    SELECT RAISE(ABORT, 'KERNEL: Compiled contracts cannot be deleted');
END;

-- Table 1: attempts (execution instances)
CREATE TABLE IF NOT EXISTS attempts (
    id TEXT PRIMARY KEY,
    work_id TEXT NOT NULL REFERENCES roadmap_items(id),

    -- Worker identity
    worker_id TEXT NOT NULL,
    worker_type TEXT NOT NULL CHECK (worker_type IN ('agent', 'human', 'system')),

    -- Compiled contract (frozen at claim time)
    contract_hash TEXT REFERENCES compiled_contracts(contract_hash),
    context_hash TEXT,

    -- Strategy and role
    strategy_id TEXT,
    role TEXT,

    -- Handoff chain
    handoff_from_attempt_id TEXT REFERENCES attempts(id),
    handoff_reason TEXT,

    -- Execution state
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    ended_at TEXT,
    outcome TEXT CHECK (outcome IN ('completed', 'blocked', 'failed', 'handed_off')),

    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_attempts_work ON attempts(work_id);
CREATE INDEX IF NOT EXISTS idx_attempts_worker ON attempts(worker_id);
CREATE INDEX IF NOT EXISTS idx_attempts_active ON attempts(work_id) WHERE ended_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_attempts_contract ON attempts(contract_hash);

-- Cannot create attempt for work that has an active attempt
CREATE TRIGGER IF NOT EXISTS attempts_no_double_claim
BEFORE INSERT ON attempts
BEGIN
    SELECT CASE
        WHEN EXISTS (
            SELECT 1 FROM attempts a
            WHERE a.work_id = NEW.work_id
              AND a.ended_at IS NULL
        )
        THEN RAISE(ABORT, 'KERNEL: Work already has active attempt. Use handoff instead of new claim.')
    END;
END;

-- Cannot create attempt for work with unresolved blockers
CREATE TRIGGER IF NOT EXISTS attempts_no_claim_blocked
BEFORE INSERT ON attempts
BEGIN
    SELECT CASE
        WHEN EXISTS (
            SELECT 1 FROM blockers b
            WHERE b.work_id = NEW.work_id
              AND b.resolved_at IS NULL
        )
        THEN RAISE(ABORT, 'KERNEL: Work has unresolved blockers. Resolve blockers before claiming.')
    END;
END;

-- Handoff attempts must have a reason
CREATE TRIGGER IF NOT EXISTS attempts_handoff_requires_reason
BEFORE INSERT ON attempts
WHEN NEW.handoff_from_attempt_id IS NOT NULL
BEGIN
    SELECT CASE
        WHEN NEW.handoff_reason IS NULL OR NEW.handoff_reason = ''
        THEN RAISE(ABORT, 'KERNEL: Handoff requires explanation in handoff_reason field')
    END;
END;

-- Completing an attempt requires evidence
CREATE TRIGGER IF NOT EXISTS attempts_completion_requires_evidence
BEFORE UPDATE OF outcome ON attempts
WHEN NEW.outcome = 'completed' AND OLD.outcome IS NULL
BEGIN
    SELECT CASE
        WHEN NOT EXISTS (
            SELECT 1 FROM evidence e
            WHERE e.attempt_id = NEW.id
        )
        THEN RAISE(ABORT, 'KERNEL: Cannot mark attempt completed without evidence. Use record_evidence() first.')
    END;
END;

-- Blocking an attempt requires a blocker record
CREATE TRIGGER IF NOT EXISTS attempts_blocked_requires_blocker
BEFORE UPDATE OF outcome ON attempts
WHEN NEW.outcome = 'blocked' AND OLD.outcome IS NULL
BEGIN
    SELECT CASE
        WHEN NOT EXISTS (
            SELECT 1 FROM blockers b
            WHERE b.attempt_id = NEW.id
              AND b.resolved_at IS NULL
        )
        THEN RAISE(ABORT, 'KERNEL: Cannot mark attempt blocked without blocker record. Use create_blocker() first.')
    END;
END;

-- Table 2: decisions (append-only governance)
CREATE TABLE IF NOT EXISTS decisions (
    id TEXT PRIMARY KEY,
    work_id TEXT REFERENCES roadmap_items(id),
    attempt_id TEXT REFERENCES attempts(id),
    lease_id TEXT,

    -- Decision type
    decision_type TEXT NOT NULL CHECK (decision_type IN (
        'approval',
        'waiver',
        'review_passed',
        'review_rejected',
        'plan_committed',
        'completion_accepted',
        'escalation',
        'revocation',
        'draft_emitted',
        'draft_approved',
        'draft_rejected'
    )),

    -- Legacy fields (compatibility)
    decision_summary TEXT,
    rationale TEXT,
    alternatives_considered TEXT,
    constraints TEXT,

    -- Spec fields
    subject_hash TEXT,
    authority TEXT NOT NULL DEFAULT 'system',
    outcome TEXT NOT NULL DEFAULT 'recorded',
    reason TEXT,
    conditions TEXT,

    -- Relationship to other decisions
    supersedes_decision_id TEXT REFERENCES decisions(id),
    related_decision_id TEXT REFERENCES decisions(id),

    -- Immutable record
    decided_by TEXT NOT NULL DEFAULT 'system',
    decided_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_decisions_work ON decisions(work_id);
CREATE INDEX IF NOT EXISTS idx_decisions_type ON decisions(decision_type);
CREATE INDEX IF NOT EXISTS idx_decisions_attempt ON decisions(attempt_id);
CREATE INDEX IF NOT EXISTS idx_decisions_supersedes ON decisions(supersedes_decision_id);

-- ABSOLUTE IMMUTABILITY: No updates allowed
CREATE TRIGGER IF NOT EXISTS decisions_no_update
BEFORE UPDATE ON decisions
BEGIN
    SELECT RAISE(ABORT, 'KERNEL: Decision records are immutable. Create a new decision with supersedes_decision_id instead.');
END;

-- No deletes either
CREATE TRIGGER IF NOT EXISTS decisions_no_delete
BEFORE DELETE ON decisions
BEGIN
    SELECT RAISE(ABORT, 'KERNEL: Decision records cannot be deleted.');
END;

-- Table 3: evidence (artifact registry)
CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    work_id TEXT NOT NULL REFERENCES roadmap_items(id),
    attempt_id TEXT REFERENCES attempts(id),
    lease_id TEXT,

    -- Artifact identity
    evidence_type TEXT NOT NULL CHECK (evidence_type IN (
        'test_result', 'build_artifact', 'diff', 'log', 'attestation',
        'screenshot', 'reference', 'document', 'policy_bundle', 'other'
    )),
    uri TEXT NOT NULL,
    sha256 TEXT NOT NULL,

    -- Metadata
    title TEXT,
    description TEXT,
    size_bytes INTEGER,

    -- Legacy fields (compatibility)
    artifacts TEXT,
    test_results TEXT,
    diff_summary TEXT,
    log_excerpt TEXT,

    -- Provenance
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_evidence_work ON evidence(work_id);
CREATE INDEX IF NOT EXISTS idx_evidence_attempt ON evidence(attempt_id);
CREATE INDEX IF NOT EXISTS idx_evidence_type ON evidence(evidence_type);
CREATE INDEX IF NOT EXISTS idx_evidence_hash ON evidence(sha256);

-- Evidence is immutable
CREATE TRIGGER IF NOT EXISTS evidence_no_update
BEFORE UPDATE ON evidence
BEGIN
    SELECT RAISE(ABORT, 'KERNEL: Evidence records are immutable. Create new evidence instead.');
END;

CREATE TRIGGER IF NOT EXISTS evidence_no_delete
BEFORE DELETE ON evidence
BEGIN
    SELECT RAISE(ABORT, 'KERNEL: Evidence records cannot be deleted.');
END;

-- Table 4: blockers (runtime execution issues)
CREATE TABLE IF NOT EXISTS blockers (
    id TEXT PRIMARY KEY,
    work_id TEXT NOT NULL REFERENCES roadmap_items(id),
    attempt_id TEXT REFERENCES attempts(id),

    -- Blocker details
    reason_code TEXT NOT NULL CHECK (reason_code IN (
        'missing_approval',
        'missing_info',
        'missing_dependency',
        'missing_resource',
        'missing_credential',
        'technical_failure',
        'external_wait',
        'other'
    )),
    title TEXT NOT NULL,
    description TEXT,

    -- What's needed to unblock
    needs TEXT,

    -- Severity
    severity TEXT DEFAULT 'blocking' CHECK (severity IN ('blocking', 'warning')),

    -- Link to planning item if applicable
    related_planning_item_id TEXT REFERENCES roadmap_items(id),

    -- Creation
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    -- Resolution
    resolved_at TEXT,
    resolved_by TEXT,
    resolution TEXT
);

CREATE INDEX IF NOT EXISTS idx_blockers_work ON blockers(work_id);
CREATE INDEX IF NOT EXISTS idx_blockers_attempt ON blockers(attempt_id);
CREATE INDEX IF NOT EXISTS idx_blockers_open ON blockers(work_id) WHERE resolved_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_blockers_reason ON blockers(reason_code);

-- Resolution is one-way
CREATE TRIGGER IF NOT EXISTS blockers_resolution_immutable
BEFORE UPDATE OF resolved_at, resolved_by, resolution
ON blockers
WHEN OLD.resolved_at IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'KERNEL: Blocker resolution is immutable');
END;

-- Resolving a blocker requires evidence or waiver
CREATE TRIGGER IF NOT EXISTS blockers_resolution_requires_justification
BEFORE UPDATE OF resolved_at ON blockers
WHEN NEW.resolved_at IS NOT NULL AND OLD.resolved_at IS NULL
BEGIN
    SELECT CASE
        WHEN NEW.resolution IS NULL OR NEW.resolution = ''
        THEN RAISE(ABORT, 'KERNEL: Blocker resolution requires explanation in resolution field')
        WHEN NOT EXISTS (
            SELECT 1 FROM evidence e
            WHERE e.work_id = OLD.work_id
              AND e.created_at > OLD.created_at
        ) AND NOT EXISTS (
            SELECT 1 FROM decisions d
            WHERE d.work_id = OLD.work_id
              AND d.decision_type = 'waiver'
              AND d.decided_at > OLD.created_at
        )
        THEN RAISE(ABORT, 'KERNEL: Blocker resolution requires evidence or waiver decision')
    END;
END;

-- Metadata table: work_required_capabilities (normalized truth)
CREATE TABLE IF NOT EXISTS work_required_capabilities (
    work_id TEXT NOT NULL REFERENCES roadmap_items(id),
    capability_id TEXT NOT NULL,
    required_at TEXT NOT NULL DEFAULT (datetime('now')),
    required_by TEXT,
    PRIMARY KEY (work_id, capability_id)
);

CREATE INDEX IF NOT EXISTS idx_work_caps_capability ON work_required_capabilities(capability_id);

-- NOTE: Lease schema alignment is handled in PA-062 to avoid conflicts with
-- the existing LeaseStore schema in coordination.db.

-- =============================================================================
-- LEGACY KERNEL TABLES (compatibility)
-- =============================================================================

-- Table: kernel_decisions (legacy)
CREATE TABLE IF NOT EXISTS kernel_decisions (
    id TEXT PRIMARY KEY,
    work_id TEXT REFERENCES roadmap_items(id),
    attempt_id TEXT,
    lease_id TEXT,

    -- Decision type
    decision_type TEXT NOT NULL CHECK (decision_type IN (
        'approval',
        'waiver',
        'review_passed',
        'review_rejected',
        'plan_committed',
        'completion_accepted',
        'escalation',
        'revocation',
        'draft_emitted',
        'draft_approved',
        'draft_rejected'
    )),

    -- What was decided
    decision_summary TEXT NOT NULL,
    rationale TEXT,
    alternatives_considered TEXT,
    constraints TEXT,

    -- Outcome
    outcome TEXT NOT NULL DEFAULT 'recorded',
    conditions TEXT,

    -- Relationship to other decisions
    supersedes_decision_id TEXT REFERENCES kernel_decisions(id),
    related_decision_id TEXT REFERENCES kernel_decisions(id),

    -- Immutable record
    decided_by TEXT NOT NULL,
    decided_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_kernel_decisions_work ON kernel_decisions(work_id);
CREATE INDEX IF NOT EXISTS idx_kernel_decisions_lease ON kernel_decisions(lease_id);
CREATE INDEX IF NOT EXISTS idx_kernel_decisions_type ON kernel_decisions(decision_type);
CREATE INDEX IF NOT EXISTS idx_kernel_decisions_supersedes ON kernel_decisions(supersedes_decision_id);

CREATE TRIGGER IF NOT EXISTS kernel_decisions_no_update
BEFORE UPDATE ON kernel_decisions
BEGIN
    SELECT RAISE(ABORT, 'KERNEL: Decision records are immutable. Create a new decision with supersedes_decision_id instead.');
END;

CREATE TRIGGER IF NOT EXISTS kernel_decisions_no_delete
BEFORE DELETE ON kernel_decisions
BEGIN
    SELECT RAISE(ABORT, 'KERNEL: Decision records cannot be deleted.');
END;

-- Table: kernel_evidence (legacy)
CREATE TABLE IF NOT EXISTS kernel_evidence (
    id TEXT PRIMARY KEY,
    work_id TEXT REFERENCES roadmap_items(id),
    attempt_id TEXT,
    lease_id TEXT,

    -- Artifact identity
    evidence_type TEXT NOT NULL CHECK (evidence_type IN (
        'test_result', 'build_artifact', 'diff', 'log', 'attestation',
        'screenshot', 'reference', 'document', 'policy_bundle', 'other'
    )),
    uri TEXT,
    sha256 TEXT,

    -- Metadata
    title TEXT,
    description TEXT,
    artifacts TEXT,
    test_results TEXT,
    diff_summary TEXT,
    log_excerpt TEXT,

    -- Provenance
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_kernel_evidence_work ON kernel_evidence(work_id);
CREATE INDEX IF NOT EXISTS idx_kernel_evidence_lease ON kernel_evidence(lease_id);
CREATE INDEX IF NOT EXISTS idx_kernel_evidence_type ON kernel_evidence(evidence_type);
CREATE INDEX IF NOT EXISTS idx_kernel_evidence_hash ON kernel_evidence(sha256);

CREATE TRIGGER IF NOT EXISTS kernel_evidence_no_update
BEFORE UPDATE ON kernel_evidence
BEGIN
    SELECT RAISE(ABORT, 'KERNEL: Evidence records are immutable. Create new evidence instead.');
END;

CREATE TRIGGER IF NOT EXISTS kernel_evidence_no_delete
BEFORE DELETE ON kernel_evidence
BEGIN
    SELECT RAISE(ABORT, 'KERNEL: Evidence records cannot be deleted.');
END;

-- Table: kernel_outcomes (legacy)
CREATE TABLE IF NOT EXISTS kernel_outcomes (
    id TEXT PRIMARY KEY,
    work_id TEXT REFERENCES roadmap_items(id),
    attempt_id TEXT,
    lease_id TEXT,

    -- Outcome details
    outcome_type TEXT NOT NULL,
    path TEXT,
    description TEXT,
    metadata TEXT,

    -- Provenance
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_kernel_outcomes_work ON kernel_outcomes(work_id);
CREATE INDEX IF NOT EXISTS idx_kernel_outcomes_lease ON kernel_outcomes(lease_id);
CREATE INDEX IF NOT EXISTS idx_kernel_outcomes_type ON kernel_outcomes(outcome_type);

CREATE TRIGGER IF NOT EXISTS kernel_outcomes_no_update
BEFORE UPDATE ON kernel_outcomes
BEGIN
    SELECT RAISE(ABORT, 'KERNEL: Outcome records are immutable.');
END;

CREATE TRIGGER IF NOT EXISTS kernel_outcomes_no_delete
BEFORE DELETE ON kernel_outcomes
BEGIN
    SELECT RAISE(ABORT, 'KERNEL: Outcome records cannot be deleted.');
END;
