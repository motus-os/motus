-- Migration: 018_add_standards_doc_path
-- Version: 18
-- Description: Add doc_path to standards table

-- UP

ALTER TABLE standards ADD COLUMN doc_path TEXT;

-- DOWN
-- NOTE: SQLite doesn't support DROP COLUMN easily.
-- Rollback would require table recreation.
