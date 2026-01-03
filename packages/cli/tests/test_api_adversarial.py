"""Adversarial tests for the Coordination API.

Tests designed to try to break the API with:
- Malformed inputs
- Edge cases
- Boundary conditions
- State manipulation
"""

import threading

import pytest

from motus.coordination.api.coordinator import Coordinator
from motus.coordination.schemas import ClaimedResource as Resource


@pytest.fixture
def coordinator(tmp_path):
    """Create a Coordinator with temp storage."""
    from motus.context_cache import ContextCache
    from motus.coordination.api.lease_store import LeaseStore

    lease_store = LeaseStore(tmp_path / "leases.db")
    cache = ContextCache(db_path=tmp_path / "cache.db")
    return Coordinator(lease_store=lease_store, context_cache=cache)


class TestInputValidation:
    """Test API handles invalid inputs gracefully."""

    def test_empty_resources_peek(self, coordinator):
        """peek with empty resources should return GRANTED (nothing to lock)."""
        resp = coordinator.peek(resources=[], intent="check")
        # Empty resources is a valid peek - nothing to check
        assert resp.decision.decision == "GRANTED"

    def test_empty_resources_claim(self, coordinator):
        """claim with empty resources should be denied."""
        resp = coordinator.claim(
            resources=[],
            mode="write",
            ttl_s=300,
            intent="test",
            agent_id="agent-1",
        )
        assert resp.decision.decision == "DENIED"
        assert resp.decision.reason_code == "DENY_INVALID_RESOURCES"

    def test_very_long_path(self, coordinator):
        """API should handle very long paths without crashing."""
        long_path = "x" * 100_000  # 100KB path
        resp = coordinator.peek(
            resources=[Resource(type="file", path=long_path)],
            intent="test",
        )
        # Should not crash
        assert resp.decision.decision in ("GRANTED", "BUSY")

    def test_null_byte_in_path(self, coordinator):
        """API should handle null bytes in paths."""
        resp = coordinator.peek(
            resources=[Resource(type="file", path="test\x00.txt")],
            intent="test",
        )
        # Should not crash
        assert resp.decision is not None

    def test_unicode_edge_cases(self, coordinator):
        """API should handle unicode edge cases."""
        # RTL override, high unicode, null
        weird_path = "\u202e\uffff"
        resp = coordinator.peek(
            resources=[Resource(type="file", path=weird_path)],
            intent="test",
        )
        assert resp.decision is not None


class TestTTLValidation:
    """Test TTL boundary conditions."""

    def test_negative_ttl_rejected(self, coordinator):
        """Negative TTL should be rejected."""
        resp = coordinator.claim(
            resources=[Resource(type="file", path="test.txt")],
            mode="write",
            ttl_s=-1,
            intent="test",
            agent_id="agent-1",
        )
        assert resp.decision.decision == "DENIED"
        assert resp.decision.reason_code == "DENY_INVALID_TTL"
        assert resp.lease is None

    def test_zero_ttl_rejected(self, coordinator):
        """Zero TTL should be rejected."""
        resp = coordinator.claim(
            resources=[Resource(type="file", path="test.txt")],
            mode="write",
            ttl_s=0,
            intent="test",
            agent_id="agent-1",
        )
        assert resp.decision.decision == "DENIED"
        assert resp.decision.reason_code == "DENY_INVALID_TTL"

    def test_huge_ttl_capped(self, coordinator):
        """Huge TTL should be capped, not overflow."""
        resp = coordinator.claim(
            resources=[Resource(type="file", path="test.txt")],
            mode="write",
            ttl_s=2**62,  # Very large but not quite overflow
            intent="test",
            agent_id="agent-1",
        )
        # Should succeed with capped TTL
        assert resp.decision.decision == "GRANTED"
        assert resp.lease is not None
        # TTL should be capped at MAX_TTL_SECONDS (7 days)
        max_ttl = Coordinator.MAX_TTL_SECONDS
        actual_ttl = (resp.lease.expires_at - resp.lease.issued_at).total_seconds()
        assert actual_ttl <= max_ttl + 1  # +1 for timing tolerance


class TestAgentIdValidation:
    """Test agent_id validation."""

    def test_empty_agent_id_rejected(self, coordinator):
        """Empty agent_id should be rejected."""
        resp = coordinator.claim(
            resources=[Resource(type="file", path="test.txt")],
            mode="write",
            ttl_s=300,
            intent="test",
            agent_id="",
        )
        assert resp.decision.decision == "DENIED"
        assert resp.decision.reason_code == "DENY_INVALID_AGENT_ID"

    def test_whitespace_agent_id_rejected(self, coordinator):
        """Whitespace-only agent_id should be rejected."""
        resp = coordinator.claim(
            resources=[Resource(type="file", path="test.txt")],
            mode="write",
            ttl_s=300,
            intent="test",
            agent_id="   ",
        )
        assert resp.decision.decision == "DENIED"
        assert resp.decision.reason_code == "DENY_INVALID_AGENT_ID"

    def test_xss_in_agent_id_accepted(self, coordinator):
        """XSS in agent_id should be stored (escaping at render time)."""
        resp = coordinator.claim(
            resources=[Resource(type="file", path="test.txt")],
            mode="write",
            ttl_s=300,
            intent="test",
            agent_id="<script>alert(1)</script>",
        )
        # Should be accepted - escaping happens at render time
        assert resp.decision.decision == "GRANTED"


class TestInvalidLeaseIds:
    """Test handling of invalid lease IDs."""

    def test_nonexistent_lease_release(self, coordinator):
        """release with nonexistent lease_id should be idempotent."""
        resp = coordinator.release(lease_id="does-not-exist", outcome="success")
        assert resp.decision.decision == "DENIED"
        assert resp.decision.reason_code == "LEASE_NOT_FOUND"

    def test_malformed_lease_status(self, coordinator):
        """status with malformed lease_id should return accepted=False."""
        resp = coordinator.status(
            lease_id="!@#$%^&*()",
            event_id="evt-1",
            event_type="heartbeat",
            payload={},
        )
        assert resp.accepted is False

    def test_empty_lease_status(self, coordinator):
        """status with empty lease_id should return accepted=False."""
        resp = coordinator.status(
            lease_id="",
            event_id="evt-1",
            event_type="heartbeat",
            payload={},
        )
        assert resp.accepted is False


class TestStateManipulation:
    """Test state manipulation edge cases."""

    def test_double_release_idempotent(self, coordinator):
        """Double release should be idempotent."""
        # Create lease
        claim_resp = coordinator.claim(
            resources=[Resource(type="file", path="double.txt")],
            mode="write",
            ttl_s=300,
            intent="test",
            agent_id="agent-1",
        )
        assert claim_resp.lease is not None
        lease_id = claim_resp.lease.lease_id

        # First release
        resp1 = coordinator.release(lease_id=lease_id, outcome="success")
        assert resp1.decision.decision == "GRANTED"

        # Second release (idempotent)
        resp2 = coordinator.release(lease_id=lease_id, outcome="success")
        assert resp2.decision.decision == "GRANTED"
        assert resp2.decision.reason_code == "RELEASED_IDEMPOTENT_REPLAY"

    def test_status_after_release_rejected(self, coordinator):
        """status on released lease should be rejected."""
        # Create and release lease
        claim_resp = coordinator.claim(
            resources=[Resource(type="file", path="status-test.txt")],
            mode="write",
            ttl_s=300,
            intent="test",
            agent_id="agent-1",
        )
        assert claim_resp.lease is not None
        lease_id = claim_resp.lease.lease_id

        coordinator.release(lease_id=lease_id, outcome="success")

        # Status after release
        resp = coordinator.status(
            lease_id=lease_id,
            event_id="evt-after-release",
            event_type="heartbeat",
            payload={},
        )
        assert resp.accepted is False

    def test_claim_additional_after_release_rejected(self, coordinator):
        """claim_additional on released lease should be denied."""
        # Create and release lease
        claim_resp = coordinator.claim(
            resources=[Resource(type="file", path="additional-test.txt")],
            mode="write",
            ttl_s=300,
            intent="test",
            agent_id="agent-1",
        )
        assert claim_resp.lease is not None
        lease_id = claim_resp.lease.lease_id

        coordinator.release(lease_id=lease_id, outcome="success")

        # Try to expand released lease
        resp = coordinator.claim_additional(
            lease_id=lease_id,
            resources=[Resource(type="file", path="more.txt")],
            mode="write",
        )
        assert resp.decision.decision == "DENIED"
        assert resp.decision.reason_code == "DENY_MISSING_LEASE"


class TestConcurrency:
    """Test concurrent access patterns.

    Note: Full concurrent transaction safety is deferred to v0.2.0.
    The LeaseStore uses check_same_thread=False but doesn't have full
    transaction locking yet. These tests are skipped until that work is done.
    See CR-2025-12-26-010-concurrent-transaction-safety.md
    """

    @pytest.mark.skip(reason="Concurrent transaction safety deferred to v0.2.0")
    def test_concurrent_claims_same_resource(self, coordinator):
        """Concurrent claims for same resource - exactly one wins."""
        resources = [Resource(type="file", path="contested.txt")]
        results = []
        errors = []

        def claim(agent_id: str):
            try:
                resp = coordinator.claim(
                    resources=resources,
                    mode="write",
                    ttl_s=300,
                    intent="test",
                    agent_id=agent_id,
                )
                results.append((agent_id, resp))
            except Exception as e:
                errors.append((agent_id, e))

        threads = [
            threading.Thread(target=claim, args=(f"agent-{i}",)) for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Unexpected errors: {errors}"
        assert len(results) == 5

        # Count grants vs busy
        granted = [r for _, r in results if r.decision.decision == "GRANTED"]
        busy = [r for _, r in results if r.decision.decision == "BUSY"]

        assert len(granted) == 1, f"Expected exactly 1 grant, got {len(granted)}"
        assert len(busy) == 4

    @pytest.mark.skip(reason="Concurrent transaction safety deferred to v0.2.0")
    def test_concurrent_claims_different_resources(self, coordinator):
        """Concurrent claims for different resources - all win."""
        results = []
        errors = []

        def claim(agent_id: str, path: str):
            try:
                resp = coordinator.claim(
                    resources=[Resource(type="file", path=path)],
                    mode="write",
                    ttl_s=300,
                    intent="test",
                    agent_id=agent_id,
                )
                results.append((agent_id, resp))
            except Exception as e:
                errors.append((agent_id, e))

        threads = [
            threading.Thread(target=claim, args=(f"agent-{i}", f"file-{i}.txt"))
            for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(results) == 5

        granted = [r for _, r in results if r.decision.decision == "GRANTED"]
        assert len(granted) == 5, "All claims for different resources should succeed"
