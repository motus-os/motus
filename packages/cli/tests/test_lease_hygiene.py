from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from motus.context_cache import ContextCache
from motus.coordination.api.coordinator import Coordinator
from motus.coordination.api.lease_store import LeaseStore
from motus.coordination.schemas import ClaimedResource as Resource


def _expire_lease(store: LeaseStore, lease_id: str) -> None:
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    past_iso = past.strftime("%Y-%m-%dT%H:%M:%SZ")
    store._conn.execute(
        """
        UPDATE coordination_leases
        SET expires_at = ?, heartbeat_deadline = ?, updated_at = ?
        WHERE lease_id = ?
        """,
        (past_iso, past_iso, past_iso, lease_id),
    )
    store._conn.commit()


def test_get_context_expires_stale_lease(tmp_path):
    lease_store = LeaseStore(db_path=tmp_path / "coordination.db")
    context_cache = ContextCache(db_path=tmp_path / "context.db")
    coordinator = Coordinator(lease_store=lease_store, context_cache=context_cache)

    claim = coordinator.claim(
        resources=[Resource(type="file", path="README.md")],
        mode="write",
        ttl_s=60,
        intent="test stale lease",
        agent_id="agent-1",
    )
    lease_id = claim.lease.lease_id

    _expire_lease(lease_store, lease_id)

    response = coordinator.get_context(lease_id)

    assert response.decision.decision == "DENIED"
    assert response.lease is not None
    assert response.lease.status == "expired"

    # Confirm stale lease no longer blocks claims
    claim2 = coordinator.claim(
        resources=[Resource(type="file", path="README.md")],
        mode="write",
        ttl_s=60,
        intent="test new lease",
        agent_id="agent-2",
    )
    assert claim2.decision.decision == "GRANTED"


def test_lease_store_write_txn_rolls_back(tmp_path):
    store = LeaseStore(db_path=tmp_path / "leases.db")

    with pytest.raises(RuntimeError):
        with store._write_txn() as conn:
            conn.execute("CREATE TABLE test_txn (id INTEGER PRIMARY KEY)")
            raise RuntimeError("boom")

    assert store._conn.in_transaction is False
    store.close()


def test_lease_store_db_lock_timeout(tmp_path, monkeypatch):
    monkeypatch.setenv("MOTUS_LEASE_WRITE_LOCK_TIMEOUT", "0.2")
    db_path = tmp_path / "leases.db"

    store_a = LeaseStore(db_path=db_path)
    store_b = LeaseStore(db_path=db_path)

    store_a._conn.execute("BEGIN IMMEDIATE")
    try:
        with pytest.raises(RuntimeError) as excinfo:
            store_b.create_lease(
                owner_agent_id="agent-1",
                mode="write",
                resources=[Resource(type="file", path="/lock.txt")],
                ttl_s=300,
                snapshot_id="snap-1",
                policy_version="v1",
                lens_digest="abc123",
            )
        assert "[LEASE-LOCK-002]" in str(excinfo.value)
    finally:
        if store_a._conn.in_transaction:
            store_a._conn.rollback()
        store_a.close()
        store_b.close()
