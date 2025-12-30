-- Migration: 019_kernel_leases
-- Version: 19
-- Description: Add kernel leases table per KERNEL-SCHEMA v0.1.3

-- UP

CREATE TABLE IF NOT EXISTS leases (
    id TEXT PRIMARY KEY,

    -- What's locked
    resource_type TEXT NOT NULL,  -- 'file', 'capability', 'work_item', etc.
    resource_id TEXT NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('read', 'write', 'exclusive')),

    -- Who holds it
    worker_id TEXT NOT NULL,
    attempt_id TEXT REFERENCES attempts(id),

    -- Timing
    acquired_at TEXT NOT NULL DEFAULT (datetime('now')),
    ttl_seconds INTEGER NOT NULL,
    expires_at TEXT NOT NULL,
    last_heartbeat TEXT,

    -- Release
    released_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_leases_resource ON leases(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_leases_worker ON leases(worker_id);
CREATE INDEX IF NOT EXISTS idx_leases_active ON leases(resource_type, resource_id)
    WHERE released_at IS NULL AND expires_at > datetime('now');

-- Lease exclusivity enforcement via triggers (not UNIQUE constraint)

-- Cannot acquire exclusive if any active lease exists
CREATE TRIGGER IF NOT EXISTS leases_exclusive_check
BEFORE INSERT ON leases
WHEN NEW.mode = 'exclusive'
BEGIN
    SELECT CASE
        WHEN EXISTS (
            SELECT 1 FROM leases
            WHERE resource_type = NEW.resource_type
              AND resource_id = NEW.resource_id
              AND released_at IS NULL
              AND expires_at > datetime('now')
        )
        THEN RAISE(ABORT, 'KERNEL: Cannot acquire exclusive lease - resource has active leases')
    END;
END;

-- Cannot acquire write if exclusive exists
CREATE TRIGGER IF NOT EXISTS leases_write_check
BEFORE INSERT ON leases
WHEN NEW.mode = 'write'
BEGIN
    SELECT CASE
        WHEN EXISTS (
            SELECT 1 FROM leases
            WHERE resource_type = NEW.resource_type
              AND resource_id = NEW.resource_id
              AND mode = 'exclusive'
              AND released_at IS NULL
              AND expires_at > datetime('now')
        )
        THEN RAISE(ABORT, 'KERNEL: Cannot acquire write lease - exclusive lease active')
    END;
END;

-- Cannot acquire any lease if exclusive exists (covers read too)
CREATE TRIGGER IF NOT EXISTS leases_any_check
BEFORE INSERT ON leases
WHEN NEW.mode IN ('read', 'write')
BEGIN
    SELECT CASE
        WHEN EXISTS (
            SELECT 1 FROM leases
            WHERE resource_type = NEW.resource_type
              AND resource_id = NEW.resource_id
              AND mode = 'exclusive'
              AND released_at IS NULL
              AND expires_at > datetime('now')
        )
        THEN RAISE(ABORT, 'KERNEL: Cannot acquire lease - exclusive lease active on resource')
    END;
END;

-- DOWN
DROP TRIGGER IF EXISTS leases_any_check;
DROP TRIGGER IF EXISTS leases_write_check;
DROP TRIGGER IF EXISTS leases_exclusive_check;
DROP INDEX IF EXISTS idx_leases_active;
DROP INDEX IF EXISTS idx_leases_worker;
DROP INDEX IF EXISTS idx_leases_resource;
DROP TABLE IF EXISTS leases;
