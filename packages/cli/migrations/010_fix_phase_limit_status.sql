-- Migration: 010_fix_phase_limit_status
-- Version: 10
-- Description: Fix phase_limit trigger to use 'deferred' instead of non-existent 'cancelled'
--
-- ISSUE: Trigger used 'cancelled' status which doesn't exist in terminology
-- VALID: pending, in_progress, blocked, completed, deferred
-- FIX: Replace 'cancelled' with 'deferred'

-- UP

-- Drop the trigger with incorrect status
DROP TRIGGER IF EXISTS enforce_phase_limit;

-- Recreate with correct status value
-- POLICY: Maximum 50 active (non-completed, non-deferred) items per phase
CREATE TRIGGER IF NOT EXISTS enforce_phase_limit
BEFORE INSERT ON roadmap_items
BEGIN
    SELECT CASE
        WHEN (
            SELECT COUNT(*) FROM roadmap_items
            WHERE phase_key = NEW.phase_key
            AND status_key NOT IN ('completed', 'deferred')
            AND deleted_at IS NULL
        ) >= 50
        THEN RAISE(ABORT, 'POLICY: Maximum 50 active items per phase')
    END;
END;

-- DOWN

DROP TRIGGER IF EXISTS enforce_phase_limit;

-- Restore original (with cancelled) for rollback
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
