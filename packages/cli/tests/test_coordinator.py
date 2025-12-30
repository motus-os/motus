"""Tests for Coordinator defaults."""

from __future__ import annotations

from motus.coordination.api import Coordinator
from motus.coordination.schemas import ClaimedResource as Resource


def test_leases_persist_across_instances(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "coordination.db"
    monkeypatch.setenv("MC_DB_PATH", str(db_path))

    coordinator_a = Coordinator()
    resource = Resource(type="file", path="src/persistent.txt")
    claim = coordinator_a.claim(
        resources=[resource],
        mode="write",
        ttl_s=300,
        intent="persist lease",
        agent_id="agent-a",
    )
    assert claim.decision.decision == "GRANTED"

    coordinator_b = Coordinator()
    claim_b = coordinator_b.claim(
        resources=[resource],
        mode="write",
        ttl_s=300,
        intent="competing lease",
        agent_id="agent-b",
    )
    assert claim_b.decision.decision == "BUSY"
    assert claim_b.decision.owner is not None
    assert claim_b.decision.owner.agent_id == "agent-a"


def test_context_cache_persists_across_instances(tmp_path, monkeypatch) -> None:
    """Context cache data should survive across Coordinator instances."""
    db_path = tmp_path / "coordination.db"
    cache_path = tmp_path / "context_cache.db"
    monkeypatch.setenv("MC_DB_PATH", str(db_path))
    monkeypatch.setenv("MC_CONTEXT_CACHE_DB_PATH", str(cache_path))

    # First coordinator - add data to context cache
    coordinator_a = Coordinator()
    coordinator_a._context_cache.put_resource_spec(
        resource_type="file",
        resource_path="test.txt",
        spec={"content": "hello"},
    )

    # Verify it was written
    resource = Resource(type="file", path="test.txt")
    spec = coordinator_a._context_cache.get_resource_spec(resource)
    assert spec is not None
    assert spec["payload"]["content"] == "hello"

    # Second coordinator - should see the same data
    coordinator_b = Coordinator()
    spec_b = coordinator_b._context_cache.get_resource_spec(resource)
    assert spec_b is not None
    assert spec_b["payload"]["content"] == "hello"
