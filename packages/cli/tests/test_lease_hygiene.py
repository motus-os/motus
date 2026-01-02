from __future__ import annotations

from datetime import datetime, timedelta, timezone

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
