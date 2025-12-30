-- Migration: 009_fix_deploy_gate
-- Version: 9
-- Description: Fix deploy gate to block PENDING quantitative claims + align trigger/view logic
--
-- ISSUE: GPT review found deploy gate only blocked 'fail', not 'pending' quantitative claims
-- ISSUE: Trigger logic diverged from v_can_deploy view logic
-- FIX: Trigger now blocks both 'fail' AND 'pending' quantitative claims

-- UP

-- Drop the broken trigger
DROP TRIGGER IF EXISTS enforce_deploy_gate;

-- Recreate with correct logic matching v_can_deploy view
-- POLICY: Cannot deploy website with:
--   1. Any failed claims (regardless of test_function)
--   2. Any pending quantitative claims (must be verified first)
CREATE TRIGGER IF NOT EXISTS enforce_deploy_gate
BEFORE INSERT ON deployment_events
WHEN NEW.target = 'website'
BEGIN
    SELECT CASE
        -- Block on ANY failed claim (align with view)
        WHEN EXISTS (
            SELECT 1 FROM claims
            WHERE test_status = 'fail'
        )
        THEN RAISE(ABORT, 'POLICY-001: Cannot deploy - failed claims exist. Run: pytest -k claim')
        -- Block on pending QUANTITATIVE claims (must be verified)
        WHEN EXISTS (
            SELECT 1 FROM claims
            WHERE test_status = 'pending'
            AND claim_type = 'quantitative'
        )
        THEN RAISE(ABORT, 'POLICY-002: Cannot deploy - pending quantitative claims. Run: MOTUS_TRACK_CLAIMS=1 pytest -k claim')
    END;
END;

-- DOWN

DROP TRIGGER IF EXISTS enforce_deploy_gate;

-- Restore original (broken) trigger for rollback
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
