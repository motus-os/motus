"""Tests for draft decision functionality (PA-051)."""

from __future__ import annotations

import pytest

from motus.api import WorkCompiler, DraftDecisionResponse, DecisionResponse


@pytest.fixture
def wc(tmp_path):
    """Create WorkCompiler with temp DB."""
    from motus.config import config
    from motus.context_cache import ContextCache
    from motus.coordination.api import Coordinator
    from motus.coordination.api.lease_store import LeaseStore

    # Use temp paths
    db_path = tmp_path / "coordination.db"
    cache_path = tmp_path / "context_cache.db"

    lease_store = LeaseStore(db_path=str(db_path))
    context_cache = ContextCache(db_path=str(cache_path))
    coordinator = Coordinator(
        lease_store=lease_store,
        context_cache=context_cache,
        policy_version="v1.0.0",
    )
    return WorkCompiler(coordinator=coordinator)


@pytest.fixture
def active_lease(wc):
    """Get an active lease for testing."""
    from motus.coordination.schemas import ClaimedResource

    result = wc.claim_work(
        task_id="ADHOC-TEST-001",
        resources=[ClaimedResource(type="file", path="test.py")],
        intent="Test task",
        agent_id="test-agent",
    )
    assert result.decision.decision == "GRANTED"
    return result.lease.lease_id


class TestEmitDraftDecision:
    """Tests for emit_draft_decision method."""

    def test_emit_draft_decision_success(self, wc, active_lease):
        """Should emit draft decision and return draft_id."""
        result = wc.emit_draft_decision(
            lease_id=active_lease,
            decision="Use Protocol over ABC",
            rationale="More flexible for DI",
            alternatives_considered=["ABC", "TypedDict"],
            constraints=["Must support runtime checks"],
        )

        assert isinstance(result, DraftDecisionResponse)
        assert result.accepted is True
        assert result.draft_id is not None
        assert result.draft_id.startswith("draft-")
        assert "awaiting approval" in result.message

    def test_emit_draft_decision_invalid_lease(self, wc):
        """Should reject draft for non-existent lease."""
        result = wc.emit_draft_decision(
            lease_id="invalid-lease-id",
            decision="Test decision",
        )

        assert result.accepted is False
        assert "Lease not found" in result.message

    def test_get_draft_decisions(self, wc, active_lease):
        """Should return pending drafts for lease."""
        # Emit two drafts
        wc.emit_draft_decision(active_lease, "Decision 1")
        wc.emit_draft_decision(active_lease, "Decision 2")

        drafts = wc.get_draft_decisions(active_lease)
        assert len(drafts) == 2
        assert all(d["status"] == "pending" for d in drafts)


class TestApproveDraft:
    """Tests for approve_draft method."""

    def test_approve_draft_success(self, wc, active_lease):
        """Should approve draft and record decision."""
        # Emit draft
        draft = wc.emit_draft_decision(
            lease_id=active_lease,
            decision="Use Protocol",
            rationale="Better flexibility",
        )

        # Approve it
        result = wc.approve_draft(
            draft.draft_id,
            approver_id="reviewer-001",
            approval_note="Looks good",
        )

        assert isinstance(result, DecisionResponse)
        assert result.accepted is True
        assert result.decision_id is not None

        # Draft should be removed from pending
        assert len(wc.get_draft_decisions(active_lease)) == 0

        # Decision should be recorded
        decisions = wc.get_decisions(active_lease)
        assert len(decisions) == 1
        assert decisions[0]["decision"] == "Use Protocol"

    def test_approve_invalid_draft(self, wc):
        """Should reject approval of non-existent draft."""
        result = wc.approve_draft("invalid-draft-id")

        assert result.accepted is False
        assert "Draft not found" in result.message


class TestRejectDraft:
    """Tests for reject_draft method."""

    def test_reject_draft_success(self, wc, active_lease):
        """Should reject draft and remove from pending."""
        # Emit draft
        draft = wc.emit_draft_decision(
            lease_id=active_lease,
            decision="Use PostgreSQL",
        )

        # Reject it
        result = wc.reject_draft(
            draft.draft_id,
            rejector_id="reviewer-001",
            rejection_reason="SQLite sufficient",
        )

        assert isinstance(result, DraftDecisionResponse)
        assert result.accepted is True
        assert "rejected" in result.message

        # Draft should be removed
        assert len(wc.get_draft_decisions(active_lease)) == 0

        # No decision should be recorded
        assert len(wc.get_decisions(active_lease)) == 0

    def test_reject_invalid_draft(self, wc):
        """Should handle rejection of non-existent draft."""
        result = wc.reject_draft("invalid-draft-id")

        assert result.accepted is False
        assert "Draft not found" in result.message
