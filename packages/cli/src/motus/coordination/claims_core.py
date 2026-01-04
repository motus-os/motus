# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from motus.atomic_io import atomic_write_json
from motus.coordination.namespace_acl import NamespaceACL
from motus.coordination.schemas import CLAIM_RECORD_SCHEMA, ClaimedResource, ClaimRecord

from .claims_validation import (
    ClaimRegistryError,
    _ClaimStorage,
    _norm_namespace,
    _resources_overlap,
    _utcnow,
)

# Lock for atomic check-and-claim operations (prevents race conditions)
# One lock per namespace to minimize contention
_namespace_locks: dict[str, threading.Lock] = {}
_namespace_locks_lock = threading.Lock()
NAMESPACE_LOCK_TIMEOUT_SECONDS = float(os.environ.get("MC_CLAIM_LOCK_TIMEOUT", "5"))


def _get_namespace_lock(namespace: str) -> threading.Lock:
    """Get or create a lock for a specific namespace."""
    with _namespace_locks_lock:
        if namespace not in _namespace_locks:
            _namespace_locks[namespace] = threading.Lock()
        return _namespace_locks[namespace]


@dataclass(frozen=True, slots=True)
class ClaimConflict:
    conflicts: list[ClaimRecord]

    def __str__(self) -> str:
        claim_ids = ", ".join(sorted(c.claim_id for c in self.conflicts))
        return f"CONFLICT: resources already claimed by [{claim_ids}]"


class ClaimRegistry(_ClaimStorage):
    """Filesystem-backed claim registry."""

    def __init__(
        self,
        root_dir: str | Path,
        *,
        lease_duration_s: int = 3600,
        namespace_acl: NamespaceACL | None = None,
    ) -> None:
        super().__init__(root_dir, namespace_acl=namespace_acl)
        self._lease_duration_s = int(lease_duration_s)

    def check_claims(
        self,
        resources: list[dict[str, str]] | list[ClaimedResource],
        *,
        namespace: str | None = None,
    ) -> list[ClaimRecord]:
        now = _utcnow()
        requested_namespace = _norm_namespace(namespace)
        requested = [
            (r if isinstance(r, ClaimedResource) else ClaimedResource(type=r["type"], path=r["path"]))
            for r in resources
        ]
        conflicts: list[ClaimRecord] = []
        for claim_path in self._list_claim_files():
            claim = self._load_claim(claim_path)
            if claim.schema != CLAIM_RECORD_SCHEMA:
                continue
            if claim.status != "active":
                continue
            if self._is_expired(claim, now=now):
                continue
            if _norm_namespace(claim.namespace) != requested_namespace:
                continue
            for have in claim.claimed_resources:
                if any(_resources_overlap(have, want) for want in requested):
                    conflicts.append(claim)
                    break
        return conflicts

    def list_claims(
        self,
        *,
        requesting_agent_id: str,
        namespace: str | None = None,
        all_namespaces: bool = False,
    ) -> list[ClaimRecord]:
        now = _utcnow()
        requested_namespace = _norm_namespace(namespace) if namespace is not None else None
        allowed_namespaces: set[str] | None = None
        if self._acl is not None:
            if all_namespaces and not self._acl.is_global_admin(requesting_agent_id):
                raise ClaimRegistryError("only global admins may list claims across all namespaces")
            if requested_namespace is not None and not self._acl.can_access(
                requesting_agent_id, requested_namespace
            ):
                raise ClaimRegistryError(
                    f"agent {requesting_agent_id} not authorized for namespace {requested_namespace}"
                )
            if self._acl.is_global_admin(requesting_agent_id):
                allowed_namespaces = None
            else:
                allowed_namespaces = set(self._acl.get_allowed_namespaces(requesting_agent_id))
        claims: list[ClaimRecord] = []
        for claim_path in self._list_claim_files():
            claim = self._load_claim(claim_path)
            if claim.schema != CLAIM_RECORD_SCHEMA:
                continue
            if claim.status != "active":
                continue
            if self._is_expired(claim, now=now):
                continue
            claim_namespace = _norm_namespace(claim.namespace)
            if requested_namespace is not None and claim_namespace != requested_namespace:
                continue
            if allowed_namespaces is not None and claim_namespace not in allowed_namespaces:
                continue
            claims.append(claim)
        claims.sort(key=lambda c: (c.expires_at, c.claim_id))
        return claims

    def register_claim(
        self,
        *,
        task_id: str,
        agent_id: str,
        resources: list[dict[str, str]] | list[ClaimedResource],
        task_type: str = "CR",
        namespace: str | None = None,
        session_id: str = "unknown",
        idempotency_key: str | None = None,
        lease_duration_s: int | None = None,
    ) -> ClaimRecord | ClaimConflict:
        self._root.mkdir(parents=True, exist_ok=True)
        now = _utcnow()
        lease_s = self._lease_duration_s if lease_duration_s is None else int(lease_duration_s)
        resolved_namespace = _norm_namespace(namespace)
        if self._acl is not None and not self._acl.can_access(agent_id, resolved_namespace):
            raise ClaimRegistryError(f"agent {agent_id} not authorized for namespace {resolved_namespace}")

        # Helper for idempotency check (used in double-check pattern)
        def find_existing_claim_by_key() -> ClaimRecord | None:
            if idempotency_key is None:
                return None
            for claim_path in self._list_claim_files():
                claim = self._load_claim(claim_path)
                if (
                    claim.schema == CLAIM_RECORD_SCHEMA
                    and claim.status == "active"
                    and not self._is_expired(claim, now=now)
                    and claim.idempotency_key == idempotency_key
                    and _norm_namespace(claim.namespace) == resolved_namespace
                ):
                    return claim
            return None

        # Fast path: check outside lock (optimization for common case)
        existing = find_existing_claim_by_key()
        if existing is not None:
            return existing

        # Atomic check-and-claim with namespace-scoped locking
        lock = _get_namespace_lock(resolved_namespace)
        acquired = lock.acquire(timeout=NAMESPACE_LOCK_TIMEOUT_SECONDS)
        if not acquired:
            raise ClaimRegistryError(
                f"timeout acquiring claim lock for namespace {resolved_namespace}"
            )
        try:
            # Double-check inside lock (prevents race condition)
            # Two threads with same key could both pass the fast path check
            existing = find_existing_claim_by_key()
            if existing is not None:
                return existing

            conflicts = self.check_claims(resources, namespace=resolved_namespace)
            if conflicts:
                return ClaimConflict(conflicts=conflicts)
            seq = self._next_sequence()
            claim_id = f"cl-{now.date().isoformat()}-{seq:04d}"
            normalized_resources = [
                (r if isinstance(r, ClaimedResource) else ClaimedResource(type=r["type"], path=r["path"]))
                for r in resources
            ]
            record = ClaimRecord(
                schema=CLAIM_RECORD_SCHEMA,
                claim_id=claim_id,
                agent_id=agent_id,
                session_id=session_id,
                task_id=task_id,
                task_type=task_type,
                namespace=resolved_namespace,
                claimed_resources=normalized_resources,
                claimed_at=now,
                expires_at=now + timedelta(seconds=lease_s),
                lease_duration_s=lease_s,
                status="active",
                idempotency_key=idempotency_key,
            )
            atomic_write_json(self._claim_path(claim_id), record.to_json())
            return record
        finally:
            lock.release()

    def renew_claim(self, claim_id: str, *, lease_duration_s: int | None = None) -> ClaimRecord:
        now = _utcnow()
        lease_s = self._lease_duration_s if lease_duration_s is None else int(lease_duration_s)
        claim_path = self._claim_path(claim_id)
        claim = self._load_claim(claim_path)
        if claim.status != "active":
            raise ClaimRegistryError(f"cannot renew non-active claim: {claim_id}")
        renewed = ClaimRecord(
            schema=claim.schema,
            claim_id=claim.claim_id,
            agent_id=claim.agent_id,
            session_id=claim.session_id,
            task_id=claim.task_id,
            task_type=claim.task_type,
            namespace=claim.namespace,
            claimed_resources=claim.claimed_resources,
            claimed_at=claim.claimed_at,
            expires_at=now + timedelta(seconds=lease_s),
            lease_duration_s=lease_s,
            status=claim.status,
            idempotency_key=claim.idempotency_key,
        )
        atomic_write_json(claim_path, renewed.to_json())
        return renewed

    def release_claim(self, claim_id: str) -> None:
        try:
            self._claim_path(claim_id).unlink()
        except FileNotFoundError:
            return
