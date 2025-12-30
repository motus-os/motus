-- Migration: 002_project_memory
-- Version: 2
-- Description: Project memory tables (project + global stores)

-- UP

-- 1. detected_patterns (auto-detection results)
CREATE TABLE detected_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_type TEXT NOT NULL,
    pattern_value TEXT NOT NULL,
    confidence TEXT NOT NULL CHECK (confidence IN ('high', 'medium', 'low')),
    detected_from TEXT,
    detected_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_confirmed_at TEXT,
    UNIQUE(pattern_type, pattern_value)
);

CREATE INDEX idx_detected_patterns_type ON detected_patterns(pattern_type);
CREATE INDEX idx_detected_patterns_last_seen ON detected_patterns(detected_at);

-- 2. learned_patterns (accumulated project memory)
CREATE TABLE learned_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_type TEXT NOT NULL,
    pattern_value TEXT NOT NULL,
    learned_at TEXT NOT NULL DEFAULT (datetime('now')),
    source TEXT NOT NULL CHECK (source IN ('detection', 'user_input', 'observation')),
    frequency INTEGER NOT NULL DEFAULT 1 CHECK (frequency >= 1),
    last_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(pattern_type, pattern_value)
);

CREATE INDEX idx_learned_patterns_type ON learned_patterns(pattern_type);
CREATE INDEX idx_learned_patterns_frequency ON learned_patterns(pattern_type, frequency DESC);

-- 3. preferences (explicit user settings; global by default)
CREATE TABLE preferences (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    set_at TEXT NOT NULL DEFAULT (datetime('now')),
    source TEXT NOT NULL CHECK (source IN ('cli', 'config_file', 'learned'))
);

-- 4. ground_rules (non-negotiable rules; global by default)
CREATE TABLE ground_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_type TEXT NOT NULL,
    rule_value TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    source TEXT NOT NULL CHECK (source IN ('default', 'user_defined', 'imported')),
    UNIQUE(rule_type, rule_value)
);

CREATE INDEX idx_ground_rules_type ON ground_rules(rule_type);

-- 5. skills (progress/unlocks; global by default)
CREATE TABLE skills (
    skill_name TEXT PRIMARY KEY,
    unlocked_at TEXT,
    progress_count INTEGER NOT NULL DEFAULT 0 CHECK (progress_count >= 0),
    unlock_threshold INTEGER NOT NULL CHECK (unlock_threshold >= 0)
);

-- 6. sessions (per-project history)
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    ended_at TEXT,
    commands_run INTEGER NOT NULL DEFAULT 0 CHECK (commands_run >= 0),
    learnings_captured INTEGER NOT NULL DEFAULT 0 CHECK (learnings_captured >= 0),
    CHECK (ended_at IS NULL OR ended_at >= started_at)
);

CREATE INDEX idx_sessions_started ON sessions(started_at DESC);

-- DOWN

DROP INDEX IF EXISTS idx_sessions_started;
DROP TABLE IF EXISTS sessions;

DROP TABLE IF EXISTS skills;

DROP INDEX IF EXISTS idx_ground_rules_type;
DROP TABLE IF EXISTS ground_rules;

DROP TABLE IF EXISTS preferences;

DROP INDEX IF EXISTS idx_learned_patterns_frequency;
DROP INDEX IF EXISTS idx_learned_patterns_type;
DROP TABLE IF EXISTS learned_patterns;

DROP INDEX IF EXISTS idx_detected_patterns_last_seen;
DROP INDEX IF EXISTS idx_detected_patterns_type;
DROP TABLE IF EXISTS detected_patterns;
