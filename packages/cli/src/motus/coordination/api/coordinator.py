# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Coordinator: The 6-call Coordination API implementation."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from motus.config import config
from motus.context_cache import ContextCache
from motus.coordination.api.lease_store import LeaseStore
from motus.coordination.api.types import (
    ClaimAdditionalResponse,
    ClaimResponse,
    DecisionEnum,
    DecisionOwner,
    EventType,
    ForceReleaseResponse,
    GetContextResponse,
    LeaseMode,
    LeaseStatus,
    LockInfo,
    Outcome,
    PeekResponse,
    ReleaseResponse,
    StatusResponse,
    make_decision,
)
from motus.coordination.schemas import ClaimedResource as Resource
from motus.lens.compiler import assemble_lens, set_cache_reader
from motus.observability.roles import Role, get_agent_role


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _hash_inputs(data: dict[str, Any]) -> str:
    """Hash inputs for certificate."""
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def _generate_snapshot_id() -> str:
    """Generate a snapshot ID."""
    return f"snap-{uuid.uuid4().hex[:12]}"


class Coordinator:
    """The 6-call Coordination API.

    Implements:
    - peek: Scout resources without locking
    - claim: Acquire lease with snapshot + Lens
    - status: Append structured events
    - claim_additional: Expand scope mid-lease
    - release: Finalize with outcome + evidence
    - force_release: Human break-glass override
    """

    def __init__(
        self,
        lease_store: LeaseStore | None = None,
        context_cache: ContextCache | None = None,
        policy_version: str = "v1.0.0",
    ) -> None:
        """Initialize Coordinator.

        Args:
            lease_store: Lease storage backend. Creates persistent store if None.
            context_cache: Context Cache for Lens assembly. Creates persistent store if None.
            policy_version: Current policy version.
        """
        if lease_store is None:
            self._lease_store = LeaseStore(db_path=config.paths.coordination_db_path)
        else:
            self._lease_store = lease_store
        if context_cache is None:
            self._context_cache = ContextCache(db_path=config.paths.context_cache_db_path)
        else:
            self._context_cache = context_cache
        self._policy_version = policy_version

        # Wire Context Cache to Lens compiler
        set_cache_reader(self._context_cache)

    # =========================================================================
    # 6.1 peek
    # =========================================================================

    def peek(
        self,
        resources: list[Resource],
        intent: str,
        lens_level: int = 0,
    ) -> PeekResponse:
        """Scout resources without locking.

        Args:
            resources: Resources to check.
            intent: What the agent plans to do.
            lens_level: Lens tier (0, 1, or 2).

        Returns:
            PeekResponse with lock status and Lens.
        """
        self._lease_store.expire_stale_leases()
        now = _utcnow()

        # Check for existing write leases
        write_leases = self._lease_store.get_active_leases_for_resources(resources, mode="write")

        # Build locks array per spec
        locks: list[LockInfo] = []
        owner_info: DecisionOwner | None = None
        ttl_remaining_s: int | None = None

        for lease in write_leases:
            for r in lease.resources:
                locks.append(
                    LockInfo(
                        resource=r,
                        mode=lease.mode,
                        owner_agent_id=lease.owner_agent_id,
                        expires_at=lease.expires_at,
                        lease_id=lease.lease_id,
                    )
                )
            # Track first owner for decision
            if owner_info is None:
                owner_info = DecisionOwner(
                    agent_id=lease.owner_agent_id,
                    lease_id=lease.lease_id,
                )
                ttl_remaining_s = max(0, int((lease.expires_at - now).total_seconds()))

        # Determine decision
        if locks:
            decision_enum: DecisionEnum = "BUSY"
            reason_code = "BUSY_WRITE_HELD"
        else:
            decision_enum = "GRANTED"
            reason_code = "GRANTED_OK"

        # Assemble Lens (REQUIRED per spec)
        lens = assemble_lens(
            policy_version=self._policy_version,
            resources=resources,
            intent=intent,
            cache_state_hash=self._context_cache.state_hash(),
            timestamp=now,
        )
        lens_payload = dict(lens)

        # Build decision object with human_message
        decision = make_decision(
            decision=decision_enum,
            reason_code=reason_code,
            rules_fired=["check_write_locks"] if locks else [],
            owner=owner_info,
            ttl_remaining_s=ttl_remaining_s,
        )

        return PeekResponse(
            decision=decision,
            lens=lens_payload,
            locks=locks,
        )

    # =========================================================================
    # 6.2 claim
    # =========================================================================

    # Maximum TTL: 7 days (prevent overflow and resource exhaustion)
    MAX_TTL_SECONDS = 7 * 24 * 60 * 60  # 604800 seconds

    def claim(
        self,
        resources: list[Resource],
        mode: LeaseMode,
        ttl_s: int,
        intent: str,
        agent_id: str,
        work_id: str | None = None,
        attempt_id: str | None = None,
        lens_level: int = 0,
    ) -> ClaimResponse:
        """Acquire a lease with snapshot and Lens.

        Args:
            resources: Resources to claim.
            mode: read or write.
            ttl_s: Time-to-live in seconds (must be > 0, max 7 days).
            intent: What the agent plans to do.
            agent_id: ID of the requesting agent.
            work_id: Optional work item identifier for lease metadata.
            attempt_id: Optional attempt identifier for lease metadata.
            lens_level: Lens tier (0, 1, or 2).
        Returns:
            ClaimResponse with lease and Lens if granted.
        """
        now = _utcnow()

        # Assemble Lens first (REQUIRED per spec, even for failures)
        lens = assemble_lens(
            policy_version=self._policy_version,
            resources=resources,
            intent=intent,
            cache_state_hash=self._context_cache.state_hash(),
            timestamp=now,
        )
        lens_payload = dict(lens)

        # Validate agent_id
        if not agent_id or not agent_id.strip():
            decision = make_decision(
                decision="DENIED",
                reason_code="DENY_INVALID_AGENT_ID",
                rules_fired=["validate_agent_id"],
            )
            return ClaimResponse(decision=decision, lens=lens_payload)

        # Validate TTL (must be positive, capped at MAX_TTL_SECONDS)
        if ttl_s <= 0:
            decision = make_decision(
                decision="DENIED",
                reason_code="DENY_INVALID_TTL",
                rules_fired=["validate_ttl"],
            )
            return ClaimResponse(decision=decision, lens=lens_payload)

        # Cap TTL to prevent overflow and resource exhaustion
        ttl_s = min(ttl_s, self.MAX_TTL_SECONDS)

        # Validate resources
        if not resources:
            decision = make_decision(
                decision="DENIED",
                reason_code="DENY_INVALID_RESOURCES",
                rules_fired=["validate_resources"],
            )
            return ClaimResponse(decision=decision, lens=lens_payload)

        self._lease_store.expire_stale_leases()

        # Check for conflicting leases
        if mode == "write":
            conflicts = self._lease_store.get_active_leases_for_resources(resources, mode="write")
        else:
            conflicts = self._lease_store.get_active_leases_for_resources(resources, mode="write")

        if conflicts:
            first_conflict = conflicts[0]
            decision = make_decision(
                decision="BUSY",
                reason_code="BUSY_WRITE_HELD",
                rules_fired=["mutual_exclusion"],
                owner=DecisionOwner(
                    agent_id=first_conflict.owner_agent_id,
                    lease_id=first_conflict.lease_id,
                ),
                ttl_remaining_s=max(0, int((first_conflict.expires_at - now).total_seconds())),
            )
            return ClaimResponse(decision=decision, lens=lens_payload)

        # Create snapshot
        snapshot_id = _generate_snapshot_id()

        lens_hash = lens_payload.get("lens_hash")
        lens_digest = lens_hash if isinstance(lens_hash, str) else ""

        # Create lease
        lease = self._lease_store.create_lease(
            owner_agent_id=agent_id,
            mode=mode,
            resources=resources,
            ttl_s=ttl_s,
            snapshot_id=snapshot_id,
            policy_version=self._policy_version,
            lens_digest=lens_digest,
            work_id=work_id,
            attempt_id=attempt_id,
        )

        # Record claim event
        event_payload = {
            "agent_id": agent_id,
            "mode": mode,
            "resources": [f"{r.type}:{r.path}" for r in resources],
            "intent": intent,
        }
        if work_id:
            event_payload["work_id"] = work_id
        if attempt_id:
            event_payload["attempt_id"] = attempt_id
        self._lease_store.record_event(
            lease_id=lease.lease_id,
            event_type="LEASE_CLAIMED",
            payload=event_payload,
        )

        decision = make_decision(
            decision="GRANTED",
            reason_code="GRANTED_OK",
            rules_fired=["mutual_exclusion", "create_snapshot", "assemble_lens"],
        )

        return ClaimResponse(
            decision=decision,
            lens=lens_payload,
            lease=lease,
        )

    # =========================================================================
    # get_context - Lens assembly interface (PA-047)
    # =========================================================================

    def get_context(
        self,
        lease_id: str,
        intent: str | None = None,
        lens_level: int = 0,
    ) -> GetContextResponse:
        """Assemble a fresh Lens for an existing lease.

        This is the public interface for context refresh. Agents call this to:
        - Get updated context mid-execution
        - Refresh stale data in their Lens
        - Load additional context after claiming

        Args:
            lease_id: Active lease ID from a prior claim().
            intent: Optional updated intent (uses original if not provided).
            lens_level: Lens tier (0=minimal, 1=standard, 2=full).

        Returns:
            GetContextResponse with fresh Lens and current lease state.

        Note:
            Unlike claim(), this does NOT acquire a new lease. The lease must
            already exist and be active. Use claim() first, then get_context()
            as needed to refresh.
        """
        self._lease_store.expire_stale_leases()
        now = _utcnow()

        # Get existing lease
        lease = self._lease_store.get_lease(lease_id)

        # Handle missing/inactive lease
        if lease is None:
            # Return empty lens with DENIED decision
            decision = make_decision(
                decision="DENIED",
                reason_code="DENY_MISSING_LEASE",
                rules_fired=["validate_lease"],
            )
            return GetContextResponse(
                decision=decision,
                lens={
                    "lens_version": "v1",
                    "tier": "tier0",
                    "policy_version": self._policy_version,
                    "intent": intent or "unknown",
                    "cache_state_hash": "",
                    "assembled_at": now.isoformat(),
                    "lens_hash": "",
                    "warnings": [{"message": "Lease not found"}],
                    "resource_specs": [],
                    "policy_snippets": [],
                    "tool_guidance": [],
                    "recent_outcomes": [],
                },
            )

        if lease.status != "active":
            decision = make_decision(
                decision="DENIED",
                reason_code="DENY_MISSING_LEASE",
                rules_fired=["validate_lease_active"],
            )
            return GetContextResponse(
                decision=decision,
                lens={
                    "lens_version": "v1",
                    "tier": "tier0",
                    "policy_version": self._policy_version,
                    "intent": intent or "unknown",
                    "cache_state_hash": "",
                    "assembled_at": now.isoformat(),
                    "lens_hash": "",
                    "warnings": [{"message": f"Lease is {lease.status}, not active"}],
                    "resource_specs": [],
                    "policy_snippets": [],
                    "tool_guidance": [],
                    "recent_outcomes": [],
                },
                lease=lease,
            )

        # Determine intent - use provided or infer from lease context
        resolved_intent = intent if intent else "context refresh"

        # Assemble fresh Lens using the lease's resources
        lens = assemble_lens(
            policy_version=self._policy_version,
            resources=lease.resources,
            intent=resolved_intent,
            cache_state_hash=self._context_cache.state_hash(),
            timestamp=now,
        )
        lens_payload = dict(lens)

        # Record context refresh event
        self._lease_store.record_event(
            lease_id=lease_id,
            event_type="CONTEXT_REFRESH",
            payload={
                "intent": resolved_intent,
                "lens_hash": lens_payload.get("lens_hash", ""),
                "lens_level": lens_level,
            },
        )

        decision = make_decision(
            decision="GRANTED",
            reason_code="GRANTED_OK",
            rules_fired=["validate_lease", "assemble_lens"],
        )

        return GetContextResponse(
            decision=decision,
            lens=lens_payload,
            lease=lease,
        )

    # =========================================================================
    # 6.3 status
    # =========================================================================

    def status(
        self,
        lease_id: str,
        event_id: str,
        event_type: EventType,
        payload: dict[str, Any],
    ) -> StatusResponse:
        """Append a structured event to a lease.

        Args:
            lease_id: Lease to update.
            event_id: Unique event ID (for idempotency).
            event_type: Type of event.
            payload: Event payload.

        Returns:
            StatusResponse per status-response.schema.json.
        """
        # Check if event already exists (idempotent - still accepted)
        if self._lease_store.event_exists(event_id):
            return StatusResponse(accepted=True)

        self._lease_store.expire_stale_leases()

        # Get and validate lease
        lease = self._lease_store.get_lease(lease_id)
        if lease is None or lease.status != "active":
            return StatusResponse(accepted=False)

        # Record the event
        self._lease_store.record_event(
            lease_id=lease_id,
            event_type=event_type,
            payload=payload,
            event_id=event_id,
        )

        # Handle heartbeat - extend deadline
        if event_type == "heartbeat":
            self._lease_store.update_heartbeat(lease_id)

        # Handle checkpoint - optionally refresh Lens
        lens_delta = None
        if event_type == "checkpoint":
            # TODO: Compute Lens delta
            pass

        return StatusResponse(accepted=True, lens_delta=lens_delta)

    # =========================================================================
    # 6.4 claim_additional
    # =========================================================================

    def claim_additional(
        self,
        lease_id: str,
        resources: list[Resource],
        mode: LeaseMode,
    ) -> ClaimAdditionalResponse:
        """Expand lease scope mid-operation.

        Args:
            lease_id: Existing lease to expand.
            resources: Additional resources to claim.
            mode: Mode for new resources.

        Returns:
            ClaimAdditionalResponse per claim-additional-response.schema.json.
        """
        self._lease_store.expire_stale_leases()
        now = _utcnow()

        # Get existing lease
        lease = self._lease_store.get_lease(lease_id)

        # Assemble Lens (REQUIRED per spec, even for failures)
        all_resources = (lease.resources if lease else []) + resources
        lens = assemble_lens(
            policy_version=self._policy_version,
            resources=all_resources,
            intent="expanded scope",
            cache_state_hash=self._context_cache.state_hash(),
            timestamp=now,
        )
        lens_payload = dict(lens)

        if lease is None or lease.status != "active":
            decision = make_decision(
                decision="DENIED",
                reason_code="DENY_MISSING_LEASE",
                rules_fired=["validate_lease"],
            )
            return ClaimAdditionalResponse(decision=decision, lens=lens_payload)

        # Check for conflicts on new resources
        conflicts = self._lease_store.get_active_leases_for_resources(resources, mode="write")
        conflicts = [c for c in conflicts if c.lease_id != lease_id]

        if conflicts:
            first_conflict = conflicts[0]
            decision = make_decision(
                decision="BUSY",
                reason_code="BUSY_WRITE_HELD",
                rules_fired=["mutual_exclusion"],
                owner=DecisionOwner(
                    agent_id=first_conflict.owner_agent_id,
                    lease_id=first_conflict.lease_id,
                ),
                ttl_remaining_s=max(0, int((first_conflict.expires_at - now).total_seconds())),
            )
            return ClaimAdditionalResponse(decision=decision, lens=lens_payload)

        # Add resources to lease
        updated_lease = self._lease_store.add_resources_to_lease(lease_id, resources)
        if updated_lease is None:
            decision = make_decision(
                decision="DENIED",
                reason_code="DENY_MISSING_LEASE",
                rules_fired=["validate_lease"],
            )
            return ClaimAdditionalResponse(decision=decision, lens=lens_payload)

        # Record scope change event
        self._lease_store.record_event(
            lease_id=lease_id,
            event_type="SCOPE_CHANGE",
            payload={
                "added_resources": [f"{r.type}:{r.path}" for r in resources],
                "mode": mode,
            },
        )

        decision = make_decision(
            decision="GRANTED",
            reason_code="GRANTED_OK",
            rules_fired=["mutual_exclusion", "expand_scope", "refresh_lens"],
        )

        return ClaimAdditionalResponse(
            decision=decision,
            lens=lens_payload,
            lease=updated_lease,
        )

    # =========================================================================
    # 6.5 release
    # =========================================================================

    def release(
        self,
        lease_id: str,
        outcome: Outcome,
        handoff: dict[str, Any] | None = None,
        evidence_ids: list[str] | None = None,
        rollback: Literal["auto", "skip"] = "auto",
    ) -> ReleaseResponse:
        """Finalize a lease with outcome and evidence.

        Args:
            lease_id: Lease to release.
            outcome: Final outcome (success, failure, partial, aborted).
            handoff: Optional handoff data for next agent.
            evidence_ids: Evidence artifacts to attach.
            rollback: Rollback behavior (auto or skip).

        Returns:
            ReleaseResponse per release-response.schema.json.
        """
        self._lease_store.expire_stale_leases()
        # Get lease
        lease = self._lease_store.get_lease(lease_id)

        # Handle missing lease
        if lease is None:
            decision = make_decision(
                decision="DENIED",
                reason_code="LEASE_NOT_FOUND",
                rules_fired=["validate_lease"],
            )
            return ReleaseResponse(decision=decision, lease=None)

        # Handle idempotent release (lease exists but already released/expired/aborted)
        if lease.status in ("released", "expired", "aborted"):
            decision = make_decision(
                decision="GRANTED",
                reason_code="RELEASED_IDEMPOTENT_REPLAY",
                rules_fired=["idempotent_check"],
            )
            return ReleaseResponse(decision=decision, lease=lease)

        # Determine if rollback was requested (unsupported in v0.1.x)
        rollback_requested = rollback == "auto" and outcome in ("failure", "aborted")
        rollback_success = None
        rollback_performed = False
        rollback_reason = "unsupported" if rollback_requested else None

        # Update lease status
        final_status: LeaseStatus = "aborted" if outcome == "aborted" else "released"
        self._lease_store.release_lease(lease_id, outcome, final_status)

        # Record release event
        self._lease_store.record_event(
            lease_id=lease_id,
            event_type="LEASE_RELEASED",
            payload={
                "outcome": outcome,
                "rollback_requested": rollback_requested,
                "rollback_performed": rollback_performed,
                "rollback_success": rollback_success,
                "rollback_reason": rollback_reason,
                "evidence_ids": evidence_ids or [],
                "handoff": handoff,
            },
        )

        # Determine reason code
        if rollback_requested:
            reason_code = "RELEASED_ROLLBACK_UNSUPPORTED"
        else:
            reason_code = "RELEASED_OK"

        decision = make_decision(
            decision="GRANTED",
            reason_code=reason_code,
            rules_fired=["release_lease", "record_outcome"]
            + (["rollback_unsupported"] if rollback_requested else []),
        )

        # Get updated lease for response
        final_lease = self._lease_store.get_lease(lease_id)

        return ReleaseResponse(decision=decision, lease=final_lease)

    # =========================================================================
    # 6.6 force_release
    # =========================================================================

    def force_release(
        self,
        resource: Resource,
        reason: str,
        operator_id: str,
    ) -> ForceReleaseResponse:
        """Human break-glass override to release resources.

        Args:
            resource: Resource to force-release.
            reason: Human-provided reason.
            operator_id: ID of the human operator.

        Returns:
            ForceReleaseResponse per force-release-response.schema.json.
        """
        operator_role = get_agent_role(operator_id)
        if operator_role not in {Role.OPERATOR, Role.ARCHITECT}:
            decision = make_decision(
                decision="DENIED",
                reason_code="DENY_POLICY",
                rules_fired=["force_release_auth"],
            )
            return ForceReleaseResponse(decision=decision)

        self._lease_store.expire_stale_leases()
        # Find active leases holding this resource
        affected = self._lease_store.get_active_leases_for_resources([resource])

        if not affected:
            decision = make_decision(
                decision="GRANTED",
                reason_code="RELEASED_IDEMPOTENT_REPLAY",
                rules_fired=["check_locks"],
            )
            return ForceReleaseResponse(decision=decision)

        # Release all affected leases
        affected_ids: list[str] = []
        for lease in affected:
            self._lease_store.release_lease(lease.lease_id, "aborted", "aborted")

            # Record policy override event
            self._lease_store.record_event(
                lease_id=lease.lease_id,
                event_type="POLICY_OVERRIDE",
                payload={
                    "operator_id": operator_id,
                    "reason": reason,
                    "override_type": "force_release",
                },
            )
            affected_ids.append(lease.lease_id)

        decision = make_decision(
            decision="GRANTED",
            reason_code="OVERRIDE_FORCE_RELEASE",
            rules_fired=["force_release_override"],
        )

        return ForceReleaseResponse(decision=decision)

    # =========================================================================
    # Maintenance
    # =========================================================================

    def cleanup_stale_leases(self) -> int:
        """Expire stale leases and return the count."""
        expired = self._lease_store.expire_stale_leases()
        return len(expired)
