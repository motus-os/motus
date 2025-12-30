-- Migration: 001_initial_schema
-- Version: 1
-- Description: Initial schema with core tables for Phase 0

-- UP

-- 1. instance_config (instance identity)
CREATE TABLE instance_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Seed instance configuration
INSERT INTO instance_config (key, value) VALUES
('instance_id', lower(hex(randomblob(16)))),
('instance_name', 'default'),
('protocol_version', '1'),
('federation_enabled', 'false'),
('federation_upstream_url', ''),
('federation_api_key', ''),
('created_at', datetime('now'));

-- 2. terminology (naming definitions)
CREATE TABLE terminology (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL,           -- 'cr_status', 'plane', 'artifact_type'
    internal_key TEXT NOT NULL,     -- 'in_progress', 'ops_plane'
    display_name TEXT NOT NULL,     -- 'In Progress', 'Ops Plane'
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    deprecated_at TEXT,
    replaced_by TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    UNIQUE(domain, internal_key)
);

CREATE INDEX idx_terminology_lookup ON terminology(domain, internal_key);

-- Seed terminology data
INSERT INTO terminology (domain, internal_key, display_name, description, sort_order) VALUES
-- Planes
('plane', 'control_plane', 'Control Plane', 'Where decisions are made', 1),
('plane', 'ops_plane', 'Ops Plane', 'Where coordination happens', 2),
('plane', 'data_plane', 'Data Plane', 'Where work happens', 3),

-- Artifact types
('artifact', 'flight_rule', 'Flight Rule', 'Pre-computed decision (no thinking)', 1),
('artifact', 'playbook', 'Playbook', 'Domain guidance (MUST/SHOULD/MAY)', 2),
('artifact', 'cr', 'Change Request', 'Discrete work item', 3),
('artifact', 'adr', 'ADR', 'Architectural decision record', 4),

-- CR statuses
('cr_status', 'queue', 'Queue', 'Not started', 1),
('cr_status', 'in_progress', 'In Progress', 'Active work', 2),
('cr_status', 'review', 'Review', 'Awaiting review', 3),
('cr_status', 'done', 'Done', 'Completed', 4),

-- CR types
('cr_type', 'defect', 'Defect', 'Bug fix', 1),
('cr_type', 'enhancement', 'Enhancement', 'New capability', 2),
('cr_type', 'chore', 'Chore', 'Operational/maintenance', 3),
('cr_type', 'spec', 'Spec', 'Design work', 4),

-- Deprecated terms (for migration)
('artifact', 'dna', 'DNA', 'DEPRECATED: Use flight_rule', 99),
('artifact', 'skill_pack', 'Skill Pack', 'DEPRECATED: Use playbook', 99);

UPDATE terminology SET deprecated_at = datetime('now'), replaced_by = 'flight_rule'
WHERE internal_key = 'dna';
UPDATE terminology SET deprecated_at = datetime('now'), replaced_by = 'playbook'
WHERE internal_key = 'skill_pack';

-- 3. resource_quotas (runaway protection)
CREATE TABLE resource_quotas (
    resource_type TEXT PRIMARY KEY,
    soft_limit INTEGER NOT NULL,
    hard_limit INTEGER NOT NULL,
    current_usage INTEGER NOT NULL DEFAULT 0,
    last_warning_at TEXT,
    last_reset_at TEXT,
    reset_interval_hours INTEGER,   -- NULL = never auto-reset
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Default quotas
INSERT INTO resource_quotas (resource_type, soft_limit, hard_limit, reset_interval_hours) VALUES
('active_claims_per_agent', 10, 50, NULL),
('events_per_hour', 1000, 10000, 1),
('db_size_mb', 500, 1000, NULL),
('pending_outbox', 1000, 10000, NULL),
('concurrent_sessions', 5, 20, NULL);

-- 4. idempotency_keys (safe retries)
CREATE TABLE idempotency_keys (
    key TEXT PRIMARY KEY,
    operation TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    response TEXT,                  -- JSON
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'complete', 'failed')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,

    CHECK (expires_at > created_at)
);

CREATE INDEX idx_idempotency_expires ON idempotency_keys(expires_at);
CREATE INDEX idx_idempotency_status ON idempotency_keys(status) WHERE status = 'pending';

-- 5. audit_log (immutable event log)
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,            -- 'agent:builder-1', 'system', 'user:ben'
    resource_type TEXT,
    resource_id TEXT,
    action TEXT NOT NULL,           -- 'create', 'update', 'delete', 'transition'
    old_value TEXT,                 -- JSON
    new_value TEXT,                 -- JSON
    context TEXT,                   -- JSON (session_id, namespace, etc.)
    instance_id TEXT NOT NULL,
    protocol_version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX idx_audit_resource ON audit_log(resource_type, resource_id);
CREATE INDEX idx_audit_actor ON audit_log(actor);

-- Immutability triggers (DNA-DB-SQLITE RULE 7)
CREATE TRIGGER audit_log_immutable
BEFORE UPDATE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'Audit log entries are immutable');
END;

CREATE TRIGGER audit_log_no_delete
BEFORE DELETE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'Audit log entries cannot be deleted');
END;

-- 6. health_check_results (diagnostics)
CREATE TABLE health_check_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    check_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pass', 'warn', 'fail')),
    message TEXT,
    details TEXT,                   -- JSON
    duration_ms REAL,
    checked_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_health_latest ON health_check_results(check_name, checked_at DESC);

-- Cleanup old results (keep 7 days)
CREATE TRIGGER health_check_cleanup
AFTER INSERT ON health_check_results
BEGIN
    DELETE FROM health_check_results
    WHERE checked_at < datetime('now', '-7 days');
END;

-- 7. circuit_breakers (graceful degradation)
CREATE TABLE circuit_breakers (
    name TEXT PRIMARY KEY,
    state TEXT NOT NULL DEFAULT 'closed'
        CHECK (state IN ('closed', 'open', 'half_open')),
    failure_count INTEGER NOT NULL DEFAULT 0,
    success_count INTEGER NOT NULL DEFAULT 0,
    last_failure_at TEXT,
    last_success_at TEXT,
    opened_at TEXT,
    failure_threshold INTEGER NOT NULL DEFAULT 5,
    recovery_timeout_seconds INTEGER NOT NULL DEFAULT 30,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT INTO circuit_breakers (name, failure_threshold, recovery_timeout_seconds) VALUES
('database', 3, 10),
('federation', 5, 60),
('file_system', 3, 30);

-- 8. extension_points (plugin architecture)
CREATE TABLE extension_points (
    point_name TEXT NOT NULL,
    handler_id TEXT NOT NULL,
    handler_type TEXT NOT NULL      -- 'builtin', 'plugin', 'hook'
        CHECK (handler_type IN ('builtin', 'plugin', 'hook')),
    handler_path TEXT,              -- Module path or hook script
    priority INTEGER NOT NULL DEFAULT 50,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    PRIMARY KEY (point_name, handler_id)
);

-- Built-in extension points
INSERT INTO extension_points (point_name, handler_id, handler_type, priority) VALUES
('pre_claim_acquire', 'quota_check', 'builtin', 10),
('pre_claim_acquire', 'namespace_acl', 'builtin', 20),
('post_claim_acquire', 'audit_log', 'builtin', 90),
('post_claim_acquire', 'federation_publish', 'builtin', 100),
('pre_command', 'health_check', 'builtin', 10),
('on_error', 'audit_log', 'builtin', 10),
('on_quota_warning', 'audit_log', 'builtin', 10);

-- DOWN

DROP TRIGGER IF EXISTS health_check_cleanup;
DROP TRIGGER IF EXISTS audit_log_no_delete;
DROP TRIGGER IF EXISTS audit_log_immutable;

DROP INDEX IF EXISTS idx_health_latest;
DROP INDEX IF EXISTS idx_audit_actor;
DROP INDEX IF EXISTS idx_audit_resource;
DROP INDEX IF EXISTS idx_audit_timestamp;
DROP INDEX IF EXISTS idx_idempotency_status;
DROP INDEX IF EXISTS idx_idempotency_expires;
DROP INDEX IF EXISTS idx_terminology_lookup;

DROP TABLE IF EXISTS extension_points;
DROP TABLE IF EXISTS circuit_breakers;
DROP TABLE IF EXISTS health_check_results;
DROP TABLE IF EXISTS audit_log;
DROP TABLE IF EXISTS idempotency_keys;
DROP TABLE IF EXISTS resource_quotas;
DROP TABLE IF EXISTS terminology;
DROP TABLE IF EXISTS instance_config;
