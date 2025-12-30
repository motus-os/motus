"""Conformance test: Capability gating.

From TEST_PLAN.md:
  Attempt a write tool without lease → DENY_MISSING_LEASE.

Updated 2025-12-23 to match schema-compliant response types.
"""

from __future__ import annotations

import pytest

from motus.coordination.api import Coordinator
from motus.coordination.api.lease_store import LeaseStore
from motus.coordination.schemas import ClaimedResource as Resource


@pytest.fixture
def coordinator() -> Coordinator:
    """Create a fresh coordinator for each test."""
    return Coordinator(lease_store=LeaseStore(db_path=":memory:"))


class TestCapabilityGating:
    """Capability gating tests - no write without lease."""

    def test_status_without_lease_denied(self, coordinator: Coordinator) -> None:
        """Status call on nonexistent lease is rejected (accepted=False)."""
        response = coordinator.status(
            lease_id="nonexistent-lease",
            event_id="evt-123",
            event_type="progress",
            payload={"message": "working..."},
        )

        # Per status-response.schema.json: just accepted boolean
        assert response.accepted is False

    def test_claim_additional_without_lease_denied(self, coordinator: Coordinator) -> None:
        """Claim additional on nonexistent lease returns DENY_MISSING_LEASE."""
        resource = Resource(type="file", path="src/extra.py")

        response = coordinator.claim_additional(
            lease_id="nonexistent-lease",
            resources=[resource],
            mode="write",
        )

        # Per claim-additional-response.schema.json: decision object
        assert response.decision.reason_code == "DENY_MISSING_LEASE"
        assert response.decision.decision == "DENIED"
        assert response.decision.human_message  # REQUIRED per spec

    def test_status_on_released_lease_denied(self, coordinator: Coordinator) -> None:
        """Status call on released lease is rejected (accepted=False)."""
        resource = Resource(type="file", path="src/main.py")

        # Claim and release
        claim = coordinator.claim(
            resources=[resource],
            mode="write",
            ttl_s=60,
            intent="edit",
            agent_id="agent-1",
        )
        coordinator.release(
            lease_id=claim.lease.lease_id,
            outcome="success",
        )

        # Try to use released lease
        response = coordinator.status(
            lease_id=claim.lease.lease_id,
            event_id="evt-after-release",
            event_type="progress",
            payload={"message": "too late"},
        )

        # Per status-response.schema.json: just accepted boolean
        assert response.accepted is False

    def test_claim_additional_on_released_lease_denied(self, coordinator: Coordinator) -> None:
        """Claim additional on released lease returns DENY_MISSING_LEASE."""
        resource = Resource(type="file", path="src/main.py")
        extra = Resource(type="file", path="src/extra.py")

        # Claim and release
        claim = coordinator.claim(
            resources=[resource],
            mode="write",
            ttl_s=60,
            intent="edit",
            agent_id="agent-1",
        )
        coordinator.release(
            lease_id=claim.lease.lease_id,
            outcome="success",
        )

        # Try to expand released lease
        response = coordinator.claim_additional(
            lease_id=claim.lease.lease_id,
            resources=[extra],
            mode="write",
        )

        # Per claim-additional-response.schema.json: decision object
        assert response.decision.reason_code == "DENY_MISSING_LEASE"
        assert response.decision.decision == "DENIED"

    def test_peek_always_allowed(self, coordinator: Coordinator) -> None:
        """Peek is always allowed (scout without lease)."""
        resource = Resource(type="file", path="src/main.py")

        # Peek without any lease
        response = coordinator.peek(
            resources=[resource],
            intent="check status",
        )

        # Per peek-response.schema.json: decision object with human_message
        assert response.decision.decision in ("GRANTED", "BUSY")
        assert response.decision.reason_code in ("GRANTED_OK", "BUSY_WRITE_HELD")
        assert response.decision.human_message  # REQUIRED per spec
        assert response.lens  # REQUIRED per spec
