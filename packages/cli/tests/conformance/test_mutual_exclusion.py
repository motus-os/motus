"""Conformance test: Mutual exclusion.

From TEST_PLAN.md safety invariants:
  For any resource r, at most one active write lease exists containing r.

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


class TestMutualExclusion:
    """Mutual exclusion safety property tests."""

    def test_at_most_one_write_lease_per_resource(self, coordinator: Coordinator) -> None:
        """At most one active write lease exists for any resource."""
        resource = Resource(type="file", path="src/critical.py")

        # Multiple agents try to claim
        results = []
        for i in range(5):
            response = coordinator.claim(
                resources=[resource],
                mode="write",
                ttl_s=60,
                intent=f"agent-{i} edit",
                agent_id=f"agent-{i}",
            )
            results.append(response)

        # Exactly one should be granted
        granted = [r for r in results if r.decision.decision == "GRANTED"]
        busy = [r for r in results if r.decision.decision == "BUSY"]

        assert len(granted) == 1
        assert len(busy) == 4

        # All busy responses should reference the winning agent
        granted_agent = granted[0].lease.owner_agent_id
        for r in busy:
            assert r.decision.owner is not None
            assert r.decision.owner.agent_id == granted_agent

    def test_mutual_exclusion_across_claim_additional(self, coordinator: Coordinator) -> None:
        """Claim additional respects mutual exclusion."""
        resource_a = Resource(type="file", path="src/a.py")
        resource_b = Resource(type="file", path="src/b.py")

        # Agent 1 claims A
        claim1 = coordinator.claim(
            resources=[resource_a],
            mode="write",
            ttl_s=60,
            intent="edit a",
            agent_id="agent-1",
        )
        assert claim1.decision.decision == "GRANTED"

        # Agent 2 claims B
        claim2 = coordinator.claim(
            resources=[resource_b],
            mode="write",
            ttl_s=60,
            intent="edit b",
            agent_id="agent-2",
        )
        assert claim2.decision.decision == "GRANTED"

        # Agent 1 tries to expand to include B (already held by agent 2)
        expand = coordinator.claim_additional(
            lease_id=claim1.lease.lease_id,
            resources=[resource_b],
            mode="write",
        )

        assert expand.decision.decision == "BUSY"
        assert expand.decision.reason_code == "BUSY_WRITE_HELD"

    def test_force_release_restores_availability(self, coordinator: Coordinator) -> None:
        """Force release makes resources available again."""
        resource = Resource(type="file", path="src/stuck.py")

        # Agent 1 claims and "goes away"
        claim1 = coordinator.claim(
            resources=[resource],
            mode="write",
            ttl_s=3600,  # Long TTL
            intent="edit",
            agent_id="agent-1",
        )
        assert claim1.decision.decision == "GRANTED"

        # Agent 2 blocked
        claim2 = coordinator.claim(
            resources=[resource],
            mode="write",
            ttl_s=60,
            intent="edit",
            agent_id="agent-2",
        )
        assert claim2.decision.decision == "BUSY"

        # Human operator force releases
        force = coordinator.force_release(
            resource=resource,
            reason="Agent 1 is unresponsive",
            operator_id="human-operator",
        )
        # Per force-release-response.schema.json: just decision object
        assert force.decision.reason_code == "OVERRIDE_FORCE_RELEASE"
        assert force.decision.human_message  # REQUIRED per spec

        # Agent 2 can now claim
        claim2_retry = coordinator.claim(
            resources=[resource],
            mode="write",
            ttl_s=60,
            intent="edit",
            agent_id="agent-2",
        )
        assert claim2_retry.decision.decision == "GRANTED"

    def test_same_agent_can_reclaim_after_release(self, coordinator: Coordinator) -> None:
        """Same agent can reclaim resource after releasing it."""
        resource = Resource(type="file", path="src/main.py")

        # Agent claims
        claim1 = coordinator.claim(
            resources=[resource],
            mode="write",
            ttl_s=60,
            intent="edit round 1",
            agent_id="agent-1",
        )
        assert claim1.decision.decision == "GRANTED"

        # Release
        coordinator.release(
            lease_id=claim1.lease.lease_id,
            outcome="success",
        )

        # Same agent claims again
        claim2 = coordinator.claim(
            resources=[resource],
            mode="write",
            ttl_s=60,
            intent="edit round 2",
            agent_id="agent-1",
        )
        assert claim2.decision.decision == "GRANTED"

        # Different lease ID
        assert claim2.lease.lease_id != claim1.lease.lease_id
