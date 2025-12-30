-- Migration: 003_session_cache
-- Version: 3
-- Description: Session SQLite cache for fast `mc list` and related queries

-- UP

-- Session-file cache metadata (one row per session JSONL file)
-- NOTE: We intentionally avoid the table name "sessions" because migration 002
-- already uses it for a different purpose (project memory history).
CREATE TABLE IF NOT EXISTS session_file_cache (
    id TEXT PRIMARY KEY,              -- Session ID (file stem)
    source TEXT NOT NULL,             -- 'claude', 'codex', 'gemini', ...
    file_path TEXT UNIQUE NOT NULL,   -- Source file path
    file_hash TEXT NOT NULL,          -- SHA-256 of file content (hex)
    file_mtime_ns INTEGER NOT NULL,   -- File modification time (ns since epoch)
    file_size_bytes INTEGER NOT NULL, -- File size in bytes
    ingested_at TEXT NOT NULL,        -- When we ingested (UTC)

    -- Extracted metadata (best-effort)
    project_path TEXT,
    model TEXT,
    total_turns INTEGER,
    total_tokens INTEGER,

    -- Fast-path status inputs (avoid re-reading JSONL on `mc list`)
    last_action TEXT NOT NULL DEFAULT '',
    has_completion INTEGER NOT NULL DEFAULT 0
        CHECK (has_completion IN (0, 1)),
    parse_error TEXT,

    -- Status
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'archived', 'corrupted', 'partial', 'skipped'))
);

CREATE INDEX IF NOT EXISTS idx_session_file_cache_mtime ON session_file_cache(file_mtime_ns);
CREATE INDEX IF NOT EXISTS idx_session_file_cache_project ON session_file_cache(project_path);
CREATE INDEX IF NOT EXISTS idx_session_file_cache_status ON session_file_cache(status);

-- Optional: event index (metadata only; full content remains in JSONL)
CREATE TABLE IF NOT EXISTS session_event_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES session_file_cache(id),
    sequence INTEGER NOT NULL,
    type TEXT NOT NULL,
    timestamp TEXT,
    content_preview TEXT,
    content_hash TEXT,
    tool_name TEXT,
    token_count INTEGER,

    UNIQUE(session_id, sequence)
);

CREATE INDEX IF NOT EXISTS idx_session_event_cache_session ON session_event_cache(session_id);
CREATE INDEX IF NOT EXISTS idx_session_event_cache_type ON session_event_cache(type);

-- Sync state (tracks sync timestamps and debug counters)
CREATE TABLE IF NOT EXISTS session_cache_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- DOWN

DROP TABLE IF EXISTS session_cache_state;
DROP INDEX IF EXISTS idx_session_event_cache_type;
DROP INDEX IF EXISTS idx_session_event_cache_session;
DROP TABLE IF EXISTS session_event_cache;
DROP INDEX IF EXISTS idx_session_file_cache_status;
DROP INDEX IF EXISTS idx_session_file_cache_project;
DROP INDEX IF EXISTS idx_session_file_cache_mtime;
DROP TABLE IF EXISTS session_file_cache;
