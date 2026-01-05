# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Types for the Coordination API."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from motus.coordination.schemas import ClaimedResource as Resource

# Reason codes from spec
ReasonCode = Literal[
    # GRANTED
    "GRANTED_OK",
    # BUSY (contention)
    "BUSY_WRITE_HELD",
    "BUSY_READERS_PRESENT",
    "BUSY_QUEUEING",
    "BUSY_PRIORITY_PREEMPTED",
    # DENIED (policy/safety)
    "DENY_POLICY",
    "DENY_INVALID_RESOURCES",
    "DENY_INVALID_TTL",
    "DENY_INVALID_AGENT_ID",
    "DENY_INVALID_WORK_ID",
    "DENY_CONFLICTING_MODE",
    "DENY_MISSING_LEASE",
    "DENY_SNAPSHOT_FAILED",
    "DENY_SANDBOX_UNSAFE",
    # TIMED_OUT
    "TIMED_OUT_WAIT",
    "TIMED_OUT_INTERNAL",
    # RELEASE outcomes
    "RELEASED_OK",
    "RELEASED_IDEMPOTENT_REPLAY",
    "RELEASED_ROLLBACK_OK",
    "RELEASED_ROLLBACK_FAILED",
    # OVERRIDES
    "OVERRIDE_FORCE_RELEASE",
    "OVERRIDE_STOP_AGENT",
]

LeaseMode = Literal["read", "write"]
LeaseStatus = Literal["active", "released", "expired", "aborted"]
Outcome = Literal["success", "failure", "partial", "aborted"]
EventType = Literal["heartbeat", "progress", "blocker", "decision", "checkpoint"]
DecisionEnum = Literal["GRANTED", "DENIED", "BUSY", "TIMED_OUT"]


# =============================================================================
# Decision Object (per decision.schema.json)
# =============================================================================


@dataclass
class DecisionOwner:
    """Owner info when decision is BUSY."""

    agent_id: str
    lease_id: str | None = None


@dataclass
class Decision:
    """Decision object per decision.schema.json.

    REQUIRED fields: decision, reason_code, human_message
    """

    decision: DecisionEnum
    reason_code: str
    human_message: str  # REQUIRED per spec!
    policy_rules_fired: list[str] = field(default_factory=list)
    owner: DecisionOwner | None = None
    suggested_next_actions: list[str] = field(default_factory=list)
    ttl_remaining_s: int | None = None


# =============================================================================
# Lock Info (for peek response)
# =============================================================================


@dataclass
class LockInfo:
    """Lock info per peek-response.schema.json locks array item."""

    resource: Resource
    mode: LeaseMode
    owner_agent_id: str
    expires_at: datetime
    lease_id: str | None = None


# =============================================================================
# Human Message Generator (required by spec)
# =============================================================================

HUMAN_MESSAGES: dict[str, str] = {
    "GRANTED_OK": "Access granted.",
    "BUSY_WRITE_HELD": "Resource is locked by another agent.",
    "BUSY_READERS_PRESENT": "Resource has active readers.",
    "BUSY_QUEUEING": "Request is queued.",
    "BUSY_PRIORITY_PREEMPTED": "Request was preempted by higher priority.",
    "DENY_POLICY": "Denied by policy.",
    "DENY_INVALID_RESOURCES": "Invalid resource specification.",
    "DENY_INVALID_TTL": "TTL must be a positive integer (max 7 days).",
    "DENY_INVALID_AGENT_ID": "Agent ID must be a non-empty string.",
    "DENY_INVALID_WORK_ID": "Work ID not found. Use ADHOC- prefix for ad hoc work.",
    "DENY_CONFLICTING_MODE": "Conflicting access mode.",
    "DENY_MISSING_LEASE": "No active lease found.",
    "DENY_SNAPSHOT_FAILED": "Snapshot creation failed.",
    "DENY_SANDBOX_UNSAFE": "Operation not safe in sandbox.",
    "TIMED_OUT_WAIT": "Wait timed out.",
    "TIMED_OUT_INTERNAL": "Internal timeout.",
    "RELEASED_OK": "Lease released successfully.",
    "RELEASED_IDEMPOTENT_REPLAY": "Lease already released (idempotent).",
    "RELEASED_ROLLBACK_OK": "Rollback completed successfully.",
    "RELEASED_ROLLBACK_FAILED": "Rollback failed.",
    "OVERRIDE_FORCE_RELEASE": "Force released by operator.",
    "OVERRIDE_STOP_AGENT": "Agent stopped by operator.",
}


def human_message_for(reason_code: str) -> str:
    """Get human-readable message for a reason code."""
    return HUMAN_MESSAGES.get(reason_code, f"Unknown: {reason_code}")


def make_decision(
    decision: DecisionEnum,
    reason_code: str,
    rules_fired: list[str] | None = None,
    owner: DecisionOwner | None = None,
    suggested_next_actions: list[str] | None = None,
    ttl_remaining_s: int | None = None,
) -> Decision:
    """Factory for creating Decision objects with auto-generated human_message."""
    return Decision(
        decision=decision,
        reason_code=reason_code,
        human_message=human_message_for(reason_code),
        policy_rules_fired=rules_fired or [],
        owner=owner,
        suggested_next_actions=suggested_next_actions or [],
        ttl_remaining_s=ttl_remaining_s,
    )


# =============================================================================
# Policy Certificate (internal, not in spec)
# =============================================================================


@dataclass(frozen=True)
class PolicyDecisionCertificate:
    """Immutable proof of a policy decision (internal use)."""

    policy_version: str
    inputs_hash: str
    rules_evaluated: tuple[str, ...]
    rules_fired: tuple[str, ...]
    reason_code: str
    decision: DecisionEnum  # Simple enum, not complex Decision object
    certificate_hash: str


@dataclass
class Lease:
    """A time-bounded capability granting access to resources."""

    lease_id: str
    owner_agent_id: str
    mode: LeaseMode
    resources: list[Resource]
    issued_at: datetime
    expires_at: datetime
    heartbeat_deadline: datetime
    snapshot_id: str
    policy_version: str
    lens_digest: str
    work_id: str | None = None
    attempt_id: str | None = None
    status: LeaseStatus = "active"
    outcome: Outcome | None = None

    def is_expired(self, now: datetime) -> bool:
        """Check if lease is expired."""
        return now >= self.expires_at or now >= self.heartbeat_deadline


@dataclass
class PeekResponse:
    """Response from peek() per peek-response.schema.json.

    REQUIRED: decision, lens
    OPTIONAL: locks
    """

    decision: Decision  # Complex object with human_message
    lens: dict[str, Any]  # REQUIRED per spec (not optional!)
    locks: list[LockInfo] = field(default_factory=list)  # Array of lock info


@dataclass
class ClaimResponse:
    """Response from claim() per claim-response.schema.json.

    REQUIRED: decision, lens
    OPTIONAL: lease
    """

    decision: Decision  # Complex object with human_message
    lens: dict[str, Any]  # REQUIRED per spec
    lease: Lease | None = None  # Present if GRANTED


@dataclass
class GetContextResponse:
    """Response from get_context().

    REQUIRED: decision, lens
    OPTIONAL: lease
    """

    decision: Decision  # Complex object with human_message
    lens: dict[str, Any]  # REQUIRED - the assembled Lens
    lease: Lease | None = None  # The current lease state


@dataclass
class StatusResponse:
    """Response from status() per status-response.schema.json.

    REQUIRED: accepted
    OPTIONAL: lens_delta
    """

    accepted: bool  # REQUIRED per spec - was event accepted?
    lens_delta: dict[str, Any] | None = None  # Optional Lens delta


@dataclass
class ClaimAdditionalResponse:
    """Response from claim_additional() per claim-additional-response.schema.json.

    REQUIRED: decision, lens
    OPTIONAL: lease
    """

    decision: Decision  # Complex object with human_message
    lens: dict[str, Any]  # REQUIRED per spec
    lease: Lease | None = None  # Present if GRANTED


@dataclass
class ReleaseResponse:
    """Response from release() per release-response.schema.json.

    REQUIRED: decision
    OPTIONAL: lease
    """

    decision: Decision  # Complex object with human_message
    lease: Lease | None = None  # Final lease state


@dataclass
class ForceReleaseResponse:
    """Response from force_release() per force-release-response.schema.json.

    REQUIRED: decision
    """

    decision: Decision  # Complex object with human_message
