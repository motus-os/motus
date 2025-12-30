"""Core tests for the Coordination API (6-call)."""

from __future__ import annotations

import pytest

from motus.context_cache import ContextCache
from motus.coordination.api import Coordinator
from motus.coordination.api.lease_store import LeaseStore
from motus.coordination.schemas import ClaimedResource as Resource


@pytest.fixture
def coordinator(tmp_path) -> Coordinator:
    """Create a Coordinator backed by temporary stores."""
    lease_store = LeaseStore(db_path=tmp_path / "leases.db")
    cache = ContextCache(db_path=tmp_path / "cache.db")
    return Coordinator(lease_store=lease_store, context_cache=cache)


def test_get_context_returns_lens_and_lease(coordinator: Coordinator) -> None:
    """Active lease returns a fresh Lens and lease state."""
    resource = Resource(type="file", path="src/main.py")
    claim = coordinator.claim(
        resources=[resource],
        mode="write",
        ttl_s=60,
        intent="edit file",
        agent_id="agent-1",
    )
    assert claim.decision.decision == "GRANTED"
    assert claim.lease is not None

    response = coordinator.get_context(
        lease_id=claim.lease.lease_id,
        intent="refresh context",
    )

    assert response.decision.decision == "GRANTED"
    assert response.decision.reason_code == "GRANTED_OK"
    assert response.decision.human_message
    assert response.lease is not None
    assert response.lease.lease_id == claim.lease.lease_id
    assert response.lens["intent"] == "refresh context"
    for key in (
        "lens_version",
        "tier",
        "cache_state_hash",
        "resource_specs",
        "policy_snippets",
        "tool_guidance",
        "recent_outcomes",
        "warnings",
    ):
        assert key in response.lens


def test_get_context_missing_lease_denied(coordinator: Coordinator) -> None:
    """Missing lease returns DENY_MISSING_LEASE and warning lens."""
    response = coordinator.get_context(
        lease_id="missing-lease",
        intent="refresh",
    )

    assert response.decision.decision == "DENIED"
    assert response.decision.reason_code == "DENY_MISSING_LEASE"
    assert response.decision.human_message
    assert response.lease is None
    assert response.lens["warnings"]
    assert response.lens["warnings"][0]["message"] == "Lease not found"


def test_status_records_event_idempotently(coordinator: Coordinator) -> None:
    """Status call records an event once, even on retries."""
    resource = Resource(type="file", path="src/status.py")
    claim = coordinator.claim(
        resources=[resource],
        mode="write",
        ttl_s=60,
        intent="update status",
        agent_id="agent-1",
    )
    assert claim.decision.decision == "GRANTED"
    assert claim.lease is not None

    lease_id = claim.lease.lease_id
    event_id = "evt-status-1"

    first = coordinator.status(
        lease_id=lease_id,
        event_id=event_id,
        event_type="progress",
        payload={"message": "working"},
    )
    assert first.accepted is True

    second = coordinator.status(
        lease_id=lease_id,
        event_id=event_id,
        event_type="progress",
        payload={"message": "working"},
    )
    assert second.accepted is True

    events = coordinator._lease_store.get_events(lease_id)
    assert sum(1 for event in events if event["event_id"] == event_id) == 1


def test_end_to_end_workflow_records_outcome_evidence_decision(
    coordinator: Coordinator,
) -> None:
    """Claim -> context -> outcome -> evidence -> decision -> release."""
    resource = Resource(type="file", path="src/workflow.py")
    claim = coordinator.claim(
        resources=[resource],
        mode="write",
        ttl_s=60,
        intent="verify workflow",
        agent_id="agent-1",
    )
    assert claim.decision.decision == "GRANTED"
    assert claim.lease is not None

    lease_id = claim.lease.lease_id

    context = coordinator.get_context(
        lease_id=lease_id,
        intent="refresh workflow",
    )
    assert context.decision.decision == "GRANTED"

    coordinator._context_cache.put_outcome(
        outcome_id="outcome-1",
        resource_type=resource.type,
        resource_path=resource.path,
        outcome={
            "id": "outcome-1",
            "summary": "workflow ok",
        },
    )

    evidence = coordinator.status(
        lease_id=lease_id,
        event_id="evt-evidence-1",
        event_type="checkpoint",
        payload={"evidence_ids": ["evidence-1"]},
    )
    assert evidence.accepted is True

    decision = coordinator.status(
        lease_id=lease_id,
        event_id="evt-decision-1",
        event_type="decision",
        payload={"decision": "accept"},
    )
    assert decision.accepted is True

    coordinator.get_context(
        lease_id=lease_id,
        intent="refresh outcomes",
    )

    outcomes = coordinator._context_cache.get_recent_outcomes([resource], limit=5)
    assert outcomes
    assert outcomes[0]["payload"]["summary"] == "workflow ok"

    release = coordinator.release(
        lease_id=lease_id,
        outcome="success",
        evidence_ids=["evidence-1"],
    )
    assert release.decision.reason_code == "RELEASED_OK"

    events = coordinator._lease_store.get_events(lease_id)
    release_events = [event for event in events if event["event_type"] == "LEASE_RELEASED"]
    assert release_events
    assert release_events[-1]["payload"]["evidence_ids"] == ["evidence-1"]
