"""Conformance test: Release idempotency.

From TEST_PLAN.md:
  Call release twice → second returns RELEASED_IDEMPOTENT_REPLAY.

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


class TestReleaseIdempotency:
    """Release idempotency tests."""

    def test_release_twice_idempotent(self, coordinator: Coordinator) -> None:
        """Calling release twice returns RELEASED_IDEMPOTENT_REPLAY on second call."""
        resource = Resource(type="file", path="src/main.py")

        # Claim the resource
        claim_response = coordinator.claim(
            resources=[resource],
            mode="write",
            ttl_s=60,
            intent="edit",
            agent_id="agent-1",
        )
        assert claim_response.decision.decision == "GRANTED"
        lease_id = claim_response.lease.lease_id

        # First release - should succeed
        release1 = coordinator.release(
            lease_id=lease_id,
            outcome="success",
        )
        # Per release-response.schema.json: decision object
        assert release1.decision.reason_code == "RELEASED_OK"
        assert release1.decision.human_message  # REQUIRED per spec

        # Second release - should be idempotent
        release2 = coordinator.release(
            lease_id=lease_id,
            outcome="success",
        )
        assert release2.decision.reason_code == "RELEASED_IDEMPOTENT_REPLAY"

    def test_release_nonexistent_lease_idempotent(self, coordinator: Coordinator) -> None:
        """Releasing a nonexistent lease returns idempotent response."""
        release_response = coordinator.release(
            lease_id="nonexistent-lease-123",
            outcome="success",
        )
        assert release_response.decision.reason_code == "RELEASED_IDEMPOTENT_REPLAY"

    def test_resource_available_after_release(self, coordinator: Coordinator) -> None:
        """Resource becomes claimable after release."""
        resource = Resource(type="file", path="src/main.py")

        # Agent 1 claims
        claim1 = coordinator.claim(
            resources=[resource],
            mode="write",
            ttl_s=60,
            intent="edit",
            agent_id="agent-1",
        )
        assert claim1.decision.decision == "GRANTED"

        # Agent 2 blocked
        claim2_blocked = coordinator.claim(
            resources=[resource],
            mode="write",
            ttl_s=60,
            intent="edit",
            agent_id="agent-2",
        )
        assert claim2_blocked.decision.decision == "BUSY"

        # Agent 1 releases
        coordinator.release(
            lease_id=claim1.lease.lease_id,
            outcome="success",
        )

        # Agent 2 can now claim
        claim2_success = coordinator.claim(
            resources=[resource],
            mode="write",
            ttl_s=60,
            intent="edit",
            agent_id="agent-2",
        )
        assert claim2_success.decision.decision == "GRANTED"

    def test_release_with_rollback_on_failure(self, coordinator: Coordinator) -> None:
        """Release with failure outcome triggers rollback (indicated in decision)."""
        resource = Resource(type="file", path="src/main.py")

        # Claim
        claim = coordinator.claim(
            resources=[resource],
            mode="write",
            ttl_s=60,
            intent="edit",
            agent_id="agent-1",
        )
        assert claim.decision.decision == "GRANTED"

        # Release with failure
        release = coordinator.release(
            lease_id=claim.lease.lease_id,
            outcome="failure",
            rollback="auto",
        )

        # Per release-response.schema.json: decision object
        # Rollback status is in the reason_code
        assert release.decision.reason_code == "RELEASED_ROLLBACK_OK"
        assert release.decision.human_message  # REQUIRED per spec
