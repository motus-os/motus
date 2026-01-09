from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from motus.claims import ClaimsRegister
from motus.coordination.claims import ClaimConflict, ClaimRegistry, ClaimRegistryError
from motus.coordination.namespace_acl import NamespaceACL
from motus.exceptions import SessionNotFoundError
from motus.session_store import SessionStore


def test_register_claim_creates_sequence_and_claim_file(tmp_path: Path) -> None:
    registry = ClaimRegistry(tmp_path)
    claim = registry.register_claim(
        task_id="CR-test-1",
        agent_id="agent-a",
        resources=[{"type": "file", "path": "foo.py"}],
    )
    assert not isinstance(claim, ClaimConflict)
    assert (tmp_path / "SEQUENCE").read_text(encoding="utf-8").strip() == "1"
    assert (tmp_path / f"{claim.claim_id}.json").exists()


def test_claim_ids_monotonic(tmp_path: Path) -> None:
    registry = ClaimRegistry(tmp_path)
    claim1 = registry.register_claim(
        task_id="CR-test-1",
        agent_id="agent-a",
        resources=[{"type": "file", "path": "foo.py"}],
    )
    assert not isinstance(claim1, ClaimConflict)

    registry.release_claim(claim1.claim_id)

    claim2 = registry.register_claim(
        task_id="CR-test-2",
        agent_id="agent-b",
        resources=[{"type": "file", "path": "bar.py"}],
    )
    assert not isinstance(claim2, ClaimConflict)
    assert claim2.claim_id.endswith("-0002")
    assert (tmp_path / "SEQUENCE").read_text(encoding="utf-8").strip() == "2"


def test_register_claim_conflicts_on_overlapping_resource(tmp_path: Path) -> None:
    registry = ClaimRegistry(tmp_path)
    claim1 = registry.register_claim(
        task_id="CR-test-1",
        agent_id="agent-a",
        resources=[{"type": "file", "path": "foo.py"}],
    )
    assert not isinstance(claim1, ClaimConflict)

    claim2 = registry.register_claim(
        task_id="CR-test-2",
        agent_id="agent-b",
        resources=[{"type": "file", "path": "foo.py"}],
    )
    assert isinstance(claim2, ClaimConflict)
    assert claim1.claim_id in str(claim2)


def test_release_claim_removes_claim_file(tmp_path: Path) -> None:
    registry = ClaimRegistry(tmp_path)
    claim = registry.register_claim(
        task_id="CR-test-1",
        agent_id="agent-a",
        resources=[{"type": "file", "path": "foo.py"}],
    )
    assert not isinstance(claim, ClaimConflict)

    registry.release_claim(claim.claim_id)
    assert (tmp_path / f"{claim.claim_id}.json").exists() is False


def test_idempotency_key_returns_existing_claim(tmp_path: Path) -> None:
    registry = ClaimRegistry(tmp_path)
    first = registry.register_claim(
        task_id="CR-test-1",
        agent_id="agent-a",
        resources=[{"type": "file", "path": "foo.py"}],
        idempotency_key="ik-1",
    )
    assert not isinstance(first, ClaimConflict)

    second = registry.register_claim(
        task_id="CR-test-1",
        agent_id="agent-a",
        resources=[{"type": "file", "path": "foo.py"}],
        idempotency_key="ik-1",
    )
    assert not isinstance(second, ClaimConflict)
    assert second.claim_id == first.claim_id
    assert (tmp_path / "SEQUENCE").read_text(encoding="utf-8").strip() == "1"


def test_expired_claims_ignored_by_conflict_check(tmp_path: Path) -> None:
    registry = ClaimRegistry(tmp_path)
    claim = registry.register_claim(
        task_id="CR-test-1",
        agent_id="agent-a",
        resources=[{"type": "file", "path": "foo.py"}],
        lease_duration_s=1,
    )
    assert not isinstance(claim, ClaimConflict)

    # Force expiry by rewriting expires_at in the claim file.
    payload_path = tmp_path / f"{claim.claim_id}.json"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    expired_at = datetime.now(timezone.utc) - timedelta(seconds=5)
    payload["expires_at"] = expired_at.isoformat().replace("+00:00", "Z")
    payload_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    claim2 = registry.register_claim(
        task_id="CR-test-2",
        agent_id="agent-b",
        resources=[{"type": "file", "path": "foo.py"}],
    )
    assert not isinstance(claim2, ClaimConflict)


def test_renew_claim_extends_expires_at(tmp_path: Path) -> None:
    registry = ClaimRegistry(tmp_path, lease_duration_s=1)
    claim = registry.register_claim(
        task_id="CR-test-1",
        agent_id="agent-a",
        resources=[{"type": "file", "path": "foo.py"}],
    )
    assert not isinstance(claim, ClaimConflict)

    renewed = registry.renew_claim(claim.claim_id, lease_duration_s=3600)
    assert renewed.expires_at > claim.expires_at


def test_directory_claim_conflicts_with_file_inside(tmp_path: Path) -> None:
    registry = ClaimRegistry(tmp_path)
    claim1 = registry.register_claim(
        task_id="CR-test-1",
        agent_id="agent-a",
        resources=[{"type": "directory", "path": "src/motus"}],
    )
    assert not isinstance(claim1, ClaimConflict)

    claim2 = registry.register_claim(
        task_id="CR-test-2",
        agent_id="agent-b",
        resources=[{"type": "file", "path": "src/motus/cli.py"}],
    )
    assert isinstance(claim2, ClaimConflict)


def test_malformed_claim_file_is_skipped(tmp_path: Path) -> None:
    registry = ClaimRegistry(tmp_path)
    (tmp_path / "cl-2025-12-18-0001.json").write_text("{not json", encoding="utf-8")

    assert registry.check_claims([{"type": "file", "path": "foo.py"}]) == []


def test_namespace_scopes_conflict_detection(tmp_path: Path) -> None:
    registry = ClaimRegistry(tmp_path)
    claim1 = registry.register_claim(
        task_id="CR-test-1",
        agent_id="agent-a",
        namespace="emmaus",
        resources=[{"type": "file", "path": "foo.py"}],
    )
    assert not isinstance(claim1, ClaimConflict)

    claim2 = registry.register_claim(
        task_id="CR-test-2",
        agent_id="agent-b",
        namespace="motus-core",
        resources=[{"type": "file", "path": "foo.py"}],
    )
    assert not isinstance(claim2, ClaimConflict)

    claim3 = registry.register_claim(
        task_id="CR-test-3",
        agent_id="agent-c",
        namespace="emmaus",
        resources=[{"type": "file", "path": "foo.py"}],
    )
    assert isinstance(claim3, ClaimConflict)


def test_namespace_acl_blocks_unauthorized_agents(tmp_path: Path) -> None:
    acl = NamespaceACL.from_dict(
        {
            "namespaces": {
                "motus-core": {
                    "agents": [{"pattern": "builder-*", "permission": "write"}],
                },
                "emmaus": {
                    "agents": [{"pattern": "emmaus-*", "permission": "write"}],
                },
            },
            "global_admins": [{"pattern": "opus-*"}],
        }
    )
    registry = ClaimRegistry(tmp_path, namespace_acl=acl)

    claim = registry.register_claim(
        task_id="CR-test-1",
        agent_id="builder-1",
        namespace="motus-core",
        resources=[{"type": "file", "path": "foo.py"}],
    )
    assert not isinstance(claim, ClaimConflict)

    with pytest.raises(ClaimRegistryError, match="not authorized"):
        registry.register_claim(
            task_id="CR-test-2",
            agent_id="builder-1",
            namespace="emmaus",
            resources=[{"type": "file", "path": "bar.py"}],
        )

    claim2 = registry.register_claim(
        task_id="CR-test-3",
        agent_id="opus-1",
        namespace="emmaus",
        resources=[{"type": "file", "path": "bar.py"}],
    )
    assert not isinstance(claim2, ClaimConflict)


def test_idempotency_key_scoped_to_namespace(tmp_path: Path) -> None:
    registry = ClaimRegistry(tmp_path)

    claim1 = registry.register_claim(
        task_id="CR-test-1",
        agent_id="agent-a",
        namespace="alpha",
        resources=[{"type": "file", "path": "foo.py"}],
        idempotency_key="ik-1",
    )
    assert not isinstance(claim1, ClaimConflict)

    claim2 = registry.register_claim(
        task_id="CR-test-2",
        agent_id="agent-b",
        namespace="beta",
        resources=[{"type": "file", "path": "foo.py"}],
        idempotency_key="ik-1",
    )
    assert not isinstance(claim2, ClaimConflict)
    assert claim2.claim_id != claim1.claim_id


def test_namespace_acl_allowed_namespaces(tmp_path: Path) -> None:
    _ = tmp_path
    acl = NamespaceACL.from_dict(
        {
            "namespaces": {
                "motus-core": {"agents": [{"pattern": "builder-*", "permission": "write"}]},
                "emmaus": {"agents": [{"pattern": "emmaus-*", "permission": "write"}]},
            },
            "global_admins": [{"pattern": "opus-*"}],
        }
    )

    assert acl.get_allowed_namespaces("builder-1") == ["motus-core"]
    assert acl.get_allowed_namespaces("emmaus-1") == ["emmaus"]
    assert acl.get_allowed_namespaces("opus-1") == ["emmaus", "motus-core"]


def test_list_claims_respects_namespace_acl_visibility(tmp_path: Path) -> None:
    acl = NamespaceACL.from_dict(
        {
            "namespaces": {
                "motus-core": {"agents": [{"pattern": "builder-*", "permission": "write"}]},
                "emmaus": {"agents": [{"pattern": "emmaus-*", "permission": "write"}]},
            },
            "global_admins": [{"pattern": "opus-*"}],
        }
    )
    registry = ClaimRegistry(tmp_path, namespace_acl=acl)

    c1 = registry.register_claim(
        task_id="CR-test-1",
        agent_id="builder-1",
        namespace="motus-core",
        resources=[{"type": "resource", "path": "r1"}],
    )
    assert not isinstance(c1, ClaimConflict)

    c2 = registry.register_claim(
        task_id="CR-test-2",
        agent_id="emmaus-1",
        namespace="emmaus",
        resources=[{"type": "resource", "path": "r2"}],
    )
    assert not isinstance(c2, ClaimConflict)

    as_builder = registry.list_claims(requesting_agent_id="builder-1")
    assert {c.claim_id for c in as_builder} == {c1.claim_id}

    as_opus = registry.list_claims(requesting_agent_id="opus-1", all_namespaces=True)
    assert {c.claim_id for c in as_opus} == {c1.claim_id, c2.claim_id}

    with pytest.raises(ClaimRegistryError, match="not authorized"):
        registry.list_claims(requesting_agent_id="builder-1", namespace="emmaus")


def test_session_claim_register_and_verify(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.db")
    session_id = store.create_session(tmp_path, "codex")
    register = ClaimsRegister(store)

    claim_id = register.register_claim(
        session_id=session_id,
        claim_type="benchmark",
        payload={"passed": 3, "total": 4},
    )
    assert claim_id.startswith("claim_")

    claims = register.get_session_claims(session_id)
    assert len(claims) == 1
    assert claims[0].verified is False

    assert register.verify_claim(claim_id) is True
    updated = register.get_session_claims(session_id)[0]
    assert updated.verified is True


def test_session_claim_register_requires_session(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.db")
    register = ClaimsRegister(store)

    with pytest.raises(SessionNotFoundError):
        register.register_claim(
            session_id="missing-session",
            claim_type="note",
            payload={"value": "data"},
        )
