-- Migration: 017_minify_bool_columns
-- Version: 17
-- Description: Rename boolean columns to is_* and enforce CHECK constraints

-- UP

BEGIN IMMEDIATE;

DROP VIEW IF EXISTS v_standards_summary;

-- extension_points.enabled -> is_enabled
ALTER TABLE extension_points RENAME TO extension_points_old;

CREATE TABLE extension_points (
    point_name TEXT NOT NULL,
    handler_id TEXT NOT NULL,
    handler_type TEXT NOT NULL
        CHECK (handler_type IN ('builtin', 'plugin', 'hook')),
    handler_path TEXT,
    priority INTEGER NOT NULL DEFAULT 50,
    is_enabled INTEGER NOT NULL DEFAULT 1 CHECK (is_enabled IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    PRIMARY KEY (point_name, handler_id)
);

INSERT INTO extension_points (
    point_name, handler_id, handler_type, handler_path,
    priority, is_enabled, created_at
)
SELECT
    point_name, handler_id, handler_type, handler_path,
    priority, enabled, created_at
FROM extension_points_old;

DROP TABLE extension_points_old;

-- standard_assignments.inherited -> is_inherited
ALTER TABLE standard_assignments RENAME TO standard_assignments_old;

CREATE TABLE standard_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    standard_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    is_inherited INTEGER NOT NULL DEFAULT 0 CHECK (is_inherited IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (standard_id) REFERENCES standards(id),
    UNIQUE(standard_id, entity_type, entity_id)
);

INSERT INTO standard_assignments (
    id, standard_id, entity_type, entity_id, is_inherited, created_at
)
SELECT
    id, standard_id, entity_type, entity_id, inherited, created_at
FROM standard_assignments_old;

DROP TABLE standard_assignments_old;

CREATE INDEX idx_assignments_entity ON standard_assignments(entity_type, entity_id);
CREATE INDEX idx_assignments_standard ON standard_assignments(standard_id);

CREATE VIEW v_standards_summary AS
SELECT
    s.id,
    s.name,
    t_level.display_name as level,
    t_check.display_name as check_type,
    s.is_blocking,
    COUNT(sa.id) as assignments,
    s.created_at
FROM standards s
LEFT JOIN terminology t_level ON t_level.domain = 'standard_level' AND t_level.internal_key = s.level_key
LEFT JOIN terminology t_check ON t_check.domain = 'check_type' AND t_check.internal_key = s.check_type_key
LEFT JOIN standard_assignments sa ON sa.standard_id = s.id
WHERE s.deleted_at IS NULL
GROUP BY s.id, s.name, t_level.display_name, t_check.display_name, s.is_blocking, s.created_at
ORDER BY t_level.sort_order, s.sort_order;

-- metrics.success -> is_success
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    operation TEXT NOT NULL,
    elapsed_ms REAL NOT NULL,
    success INTEGER NOT NULL DEFAULT 1 CHECK (success IN (0, 1)),
    metadata TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    created_by TEXT DEFAULT NULL,
    updated_by TEXT DEFAULT NULL,
    deleted_at TEXT DEFAULT NULL,
    deleted_by TEXT DEFAULT NULL,
    deletion_reason TEXT DEFAULT NULL
);

ALTER TABLE metrics RENAME TO metrics_old;

CREATE TABLE metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    operation TEXT NOT NULL,
    elapsed_ms REAL NOT NULL,
    is_success INTEGER NOT NULL DEFAULT 1 CHECK (is_success IN (0, 1)),
    metadata TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    created_by TEXT DEFAULT NULL,
    updated_by TEXT DEFAULT NULL,
    deleted_at TEXT DEFAULT NULL,
    deleted_by TEXT DEFAULT NULL,
    deletion_reason TEXT DEFAULT NULL
);

INSERT INTO metrics (
    id, timestamp, operation, elapsed_ms, is_success, metadata,
    created_at, updated_at, created_by, updated_by,
    deleted_at, deleted_by, deletion_reason
)
SELECT
    id, timestamp, operation, elapsed_ms, success, metadata,
    created_at, updated_at, created_by, updated_by,
    deleted_at, deleted_by, deletion_reason
FROM metrics_old;

DROP TABLE metrics_old;

CREATE INDEX idx_metrics_created_at ON metrics(created_at);
CREATE INDEX idx_metrics_updated_at ON metrics(updated_at);
CREATE INDEX idx_metrics_deleted_at ON metrics(deleted_at);

COMMIT;

-- DOWN
-- NOTE: Rollback would require rebuilding tables with original column names.
