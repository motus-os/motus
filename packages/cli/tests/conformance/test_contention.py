"""Conformance test: Contention.

From TEST_PLAN.md:
  Two agents race a write claim on same file → one GRANTED, one BUSY_WRITE_HELD.

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


class TestContention:
    """Contention tests for write claim races."""

    def test_two_agents_race_write_claim(self, coordinator: Coordinator) -> None:
        """Two agents race for same resource: one GRANTED, one BUSY_WRITE_HELD."""
        resource = Resource(type="file", path="src/main.py")

        # Agent 1 claims the resource
        response1 = coordinator.claim(
            resources=[resource],
            mode="write",
            ttl_s=60,
            intent="edit file",
            agent_id="agent-1",
        )

        # Agent 1 should be granted
        assert response1.decision.decision == "GRANTED"
        assert response1.decision.reason_code == "GRANTED_OK"
        assert response1.decision.human_message  # REQUIRED per spec
        assert response1.lease is not None
        assert response1.lease.owner_agent_id == "agent-1"

        # Agent 2 tries to claim the same resource
        response2 = coordinator.claim(
            resources=[resource],
            mode="write",
            ttl_s=60,
            intent="edit file",
            agent_id="agent-2",
        )

        # Agent 2 should be blocked
        assert response2.decision.decision == "BUSY"
        assert response2.decision.reason_code == "BUSY_WRITE_HELD"
        assert response2.decision.human_message  # REQUIRED per spec
        assert response2.lease is None
        # Owner info in decision object
        assert response2.decision.owner is not None
        assert response2.decision.owner.agent_id == "agent-1"

    def test_disjoint_resources_both_granted(self, coordinator: Coordinator) -> None:
        """Non-overlapping resources both get granted."""
        resource_a = Resource(type="file", path="src/a.py")
        resource_b = Resource(type="file", path="src/b.py")

        # Agent 1 claims resource A
        response1 = coordinator.claim(
            resources=[resource_a],
            mode="write",
            ttl_s=60,
            intent="edit a.py",
            agent_id="agent-1",
        )
        assert response1.decision.decision == "GRANTED"

        # Agent 2 claims resource B (different file)
        response2 = coordinator.claim(
            resources=[resource_b],
            mode="write",
            ttl_s=60,
            intent="edit b.py",
            agent_id="agent-2",
        )
        assert response2.decision.decision == "GRANTED"

    def test_partial_overlap_blocked(self, coordinator: Coordinator) -> None:
        """Claim with partial overlap is blocked."""
        resource_a = Resource(type="file", path="src/a.py")
        resource_b = Resource(type="file", path="src/b.py")

        # Agent 1 claims A
        response1 = coordinator.claim(
            resources=[resource_a],
            mode="write",
            ttl_s=60,
            intent="edit a.py",
            agent_id="agent-1",
        )
        assert response1.decision.decision == "GRANTED"

        # Agent 2 tries to claim A and B (partial overlap with A)
        response2 = coordinator.claim(
            resources=[resource_a, resource_b],
            mode="write",
            ttl_s=60,
            intent="edit both",
            agent_id="agent-2",
        )
        assert response2.decision.decision == "BUSY"
        assert response2.decision.reason_code == "BUSY_WRITE_HELD"

    def test_read_after_write_blocked(self, coordinator: Coordinator) -> None:
        """Read claim on write-locked resource is blocked (default semantics)."""
        resource = Resource(type="file", path="src/main.py")

        # Agent 1 claims write
        response1 = coordinator.claim(
            resources=[resource],
            mode="write",
            ttl_s=60,
            intent="edit",
            agent_id="agent-1",
        )
        assert response1.decision.decision == "GRANTED"

        # Agent 2 tries to claim read
        response2 = coordinator.claim(
            resources=[resource],
            mode="read",
            ttl_s=60,
            intent="read",
            agent_id="agent-2",
        )
        # Default: reads blocked during write
        assert response2.decision.decision == "BUSY"
