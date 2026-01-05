# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""The 6-Call API Facade - canonical Work Compiler interface.

This module provides the public interface for the Motus Work Compiler protocol.
The 6 calls represent the complete lifecycle of task execution:

    claim_work -> get_context -> [work] -> put_outcome -> record_evidence -> release_work

Usage:
    from motus.api import WorkCompiler

    # Create compiler instance
    wc = WorkCompiler()

    # Claim work
    result = wc.claim_work(
        task_id="RI-A-001",
        resources=[{"type": "file", "path": "src/main.py"}],
        intent="implement feature X",
        agent_id="agent-001",
    )

    if result.decision.decision == "GRANTED":
        lease_id = result.lease.lease_id

        # Get context (Lens)
        ctx = wc.get_context(lease_id)

        # Do work...

        # Record outcome
        wc.put_outcome(lease_id, outcome_type="file", path="src/main.py")

        # Record evidence
        wc.record_evidence(lease_id, evidence_type="test_result", artifacts={"passed": True})

        # Record decision
        wc.record_decision(lease_id, decision="Used pattern X because Y")

        # Release when done
        wc.release_work(lease_id, outcome="success")

Protocol Notes:
    - All calls are idempotent where possible
    - Lease provides time-bounded access to resources
    - Context (Lens) can be refreshed mid-execution
    - Evidence and decisions are append-only
    - Release finalizes the lease and attaches proof artifacts
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from motus.config import config
from motus.config_loader import load_config
from motus.context_cache import ContextCache
from motus.coordination.api import Coordinator, GetContextResponse
from motus.coordination.api.lease_store import LeaseStore
from motus.coordination.api.types import (
    ClaimResponse,
    LeaseMode,
    Outcome,
    ReleaseResponse,
    make_decision,
)
from motus.coordination.schemas import ClaimedResource as Resource
from motus.core.database_connection import get_db_manager
from motus.lens.compiler import assemble_lens
from motus.logging import get_logger


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _generate_id(prefix: str) -> str:
    from motus.core.sqlite_udfs import mc_id

    seed = uuid.uuid4().hex
    return mc_id(prefix, seed)


_kernel_logger = get_logger("motus.api.kernel")
_ADHOC_PREFIX = "ADHOC-"


def _is_adhoc_work_id(work_id: str) -> bool:
    return work_id.startswith(_ADHOC_PREFIX)


def _metrics_enabled() -> bool:
    try:
        return load_config().metrics_enabled
    except Exception:
        return True


def _map_release_outcome(outcome: Outcome) -> str | None:
    if outcome == "success":
        return "completed"
    if outcome == "failure":
        return "failed"
    if outcome == "partial":
        return "handed_off"
    if outcome == "aborted":
        return "failed"
    return None


def _persist_decision(
    decision_id: str,
    lease_id: str,
    decision_type: str,
    decision_summary: str,
    *,
    work_id: str | None = None,
    attempt_id: str | None = None,
    rationale: str | None = None,
    alternatives_considered: list[str] | None = None,
    constraints: list[str] | None = None,
    decided_by: str = "agent",
    supersedes_decision_id: str | None = None,
) -> bool:
    """Persist a decision to the decisions table (KERNEL-SCHEMA v0.1.3)."""
    try:
        db = get_db_manager()
        with db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO decisions (
                    id, work_id, attempt_id, lease_id, decision_type, decision_summary,
                    rationale, alternatives_considered, constraints, decided_by,
                    supersedes_decision_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision_id,
                    work_id,
                    attempt_id,
                    lease_id,
                    decision_type,
                    decision_summary,
                    rationale,
                    json.dumps(alternatives_considered or []),
                    json.dumps(constraints or []),
                    decided_by,
                    supersedes_decision_id,
                ),
            )
        return True
    except Exception as e:
        _kernel_logger.warning(f"Failed to persist decision: {e}")
        return False


def _persist_evidence(
    evidence_id: str,
    lease_id: str,
    evidence_type: str,
    *,
    work_id: str | None = None,
    attempt_id: str | None = None,
    artifacts: dict[str, Any] | None = None,
    test_results: dict[str, Any] | None = None,
    diff_summary: str | None = None,
    log_excerpt: str | None = None,
    created_by: str = "agent",
) -> bool:
    """Persist evidence to the evidence table (KERNEL-SCHEMA v0.1.3)."""
    try:
        payload = {
            "evidence_type": evidence_type,
            "artifacts": artifacts or {},
            "test_results": test_results or {},
            "diff_summary": diff_summary,
            "log_excerpt": log_excerpt,
        }
        payload_json = json.dumps(
            payload, sort_keys=True, separators=(",", ":")
        )
        sha256 = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        uri = f"evidence:{evidence_id}"
        db = get_db_manager()
        with db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO evidence (
                    id, work_id, attempt_id, lease_id, evidence_type, uri, sha256,
                    artifacts, test_results, diff_summary, log_excerpt, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evidence_id,
                    work_id,
                    attempt_id,
                    lease_id,
                    evidence_type,
                    uri,
                    sha256,
                    json.dumps(artifacts or {}),
                    json.dumps(test_results) if test_results else None,
                    diff_summary,
                    log_excerpt,
                    created_by,
                ),
            )
        return True
    except Exception as e:
        _kernel_logger.warning(f"Failed to persist evidence: {e}")
        return False


def _persist_outcome(
    outcome_id: str,
    lease_id: str,
    outcome_type: str,
    *,
    work_id: str | None = None,
    attempt_id: str | None = None,
    path: str | None = None,
    description: str | None = None,
    metadata: dict[str, Any] | None = None,
    created_by: str = "agent",
) -> bool:
    """Persist outcome to the kernel_outcomes table."""
    try:
        db = get_db_manager()
        with db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO kernel_outcomes (
                    id, work_id, attempt_id, lease_id, outcome_type, path, description,
                    metadata, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    outcome_id,
                    work_id,
                    attempt_id,
                    lease_id,
                    outcome_type,
                    path,
                    description,
                    json.dumps(metadata or {}),
                    created_by,
                ),
            )
        return True
    except Exception as e:
        _kernel_logger.warning(f"Failed to persist outcome: {e}")
        return False


def _persist_attempt(
    attempt_id: str,
    work_id: str,
    worker_id: str,
    *,
    worker_type: str = "agent",
) -> bool:
    """Persist an attempt row for a claim (KERNEL-SCHEMA v0.1.3)."""
    try:
        db = get_db_manager()
        with db.transaction() as conn:
            item = conn.execute(
                "SELECT 1 FROM roadmap_items WHERE id = ?",
                (work_id,),
            ).fetchone()
            if item is None:
                if not _is_adhoc_work_id(work_id):
                    _kernel_logger.warning(
                        f"Refusing to create ad hoc roadmap item without ADHOC- prefix: {work_id}"
                    )
                    return False
                conn.execute(
                    """
                    INSERT INTO roadmap_items (id, phase_key, title, created_by)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        work_id,
                        "phase_f",
                        f"Ad hoc work item {work_id}",
                        "work_compiler",
                    ),
                )

            conn.execute(
                """
                INSERT INTO attempts (id, work_id, worker_id, worker_type)
                VALUES (?, ?, ?, ?)
                """,
                (attempt_id, work_id, worker_id, worker_type),
            )
        return True
    except Exception as e:
        _kernel_logger.warning(f"Failed to persist attempt: {e}")
        return False


# =============================================================================
# Response Types for 6-Call API
# =============================================================================


@dataclass
class OutcomeResponse:
    """Response from put_outcome()."""

    accepted: bool
    outcome_id: str | None = None
    message: str = ""


@dataclass
class EvidenceResponse:
    """Response from record_evidence()."""

    accepted: bool
    evidence_id: str | None = None
    message: str = ""


@dataclass
class DecisionResponse:
    """Response from record_decision()."""

    accepted: bool
    decision_id: str | None = None
    message: str = ""


@dataclass
class DraftDecisionResponse:
    """Response from emit_draft_decision()."""

    accepted: bool
    draft_id: str | None = None
    message: str = ""


# =============================================================================
# Work Compiler - The 6-Call API
# =============================================================================


class WorkCompiler:
    """The 6-Call Work Compiler API.

    This is the canonical interface for the Motus Work Compiler protocol.
    It wraps the lower-level Coordinator with the exact 6-call semantics
    defined in the terminology.

    The 6 calls:
        1. claim_work - Reserve a roadmap item, get lease
        2. get_context - Assemble lens: task, standards, file policy, dependencies
        3. put_outcome - Register primary deliverable(s) produced
        4. record_evidence - Store verification artifacts (tests, diffs, logs)
        5. record_decision - Append-only decision logging (why X, not Y)
        6. release_work - End lease, record disposition
    """

    def __init__(
        self,
        coordinator: Coordinator | None = None,
        *,
        policy_version: str = "v1.0.0",
    ) -> None:
        """Initialize Work Compiler.

        Args:
            coordinator: Coordinator instance. Creates default if None.
            policy_version: Current policy version.
        """
        if coordinator is None:
            lease_store = LeaseStore(db_path=config.paths.coordination_db_path)
            context_cache = ContextCache(db_path=config.paths.context_cache_db_path)
            self._coordinator = Coordinator(
                lease_store=lease_store,
                context_cache=context_cache,
                policy_version=policy_version,
            )
        else:
            self._coordinator = coordinator

        self._outcomes: dict[str, list[dict[str, Any]]] = {}
        self._evidence: dict[str, list[dict[str, Any]]] = {}
        self._decisions: dict[str, list[dict[str, Any]]] = {}
        self._draft_decisions: dict[str, dict[str, Any]] = {}
        self._lease_task_ids: dict[str, str] = {}  # PA-099: lease_id -> task_id
        self._lease_attempt_ids: dict[str, str] = {}

    def _cache_lease_metadata(
        self,
        lease_id: str,
        work_id: str | None,
        attempt_id: str | None,
    ) -> None:
        if work_id:
            self._lease_task_ids[lease_id] = work_id
        if attempt_id:
            self._lease_attempt_ids[lease_id] = attempt_id

    def _roadmap_item_exists(self, work_id: str) -> bool | None:
        try:
            db = get_db_manager()
            with db.readonly_connection() as conn:
                row = conn.execute(
                    "SELECT 1 FROM roadmap_items WHERE id = ? AND deleted_at IS NULL",
                    (work_id,),
                ).fetchone()
            return row is not None
        except Exception as exc:
            _kernel_logger.warning(
                f"Work ID validation skipped for {work_id}: {exc}"
            )
            return None

    def _resolve_lease_metadata(
        self,
        lease_id: str,
        lease: Any | None,
    ) -> tuple[str | None, str | None]:
        work_id = lease.work_id if lease is not None else None
        attempt_id = lease.attempt_id if lease is not None else None

        if work_id is None:
            work_id = self._lease_task_ids.get(lease_id)
        if attempt_id is None:
            attempt_id = self._lease_attempt_ids.get(lease_id)
        if attempt_id is None:
            attempt_id = lease_id

        return work_id, attempt_id

    def _clear_lease_metadata(self, lease_id: str) -> None:
        self._lease_task_ids.pop(lease_id, None)
        self._lease_attempt_ids.pop(lease_id, None)

    def _record_metric(
        self,
        operation: str,
        start_time: float,
        *,
        success: bool,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not _metrics_enabled():
            return
        try:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            db = get_db_manager()
            db.record_metric(
                operation=operation,
                elapsed_ms=elapsed_ms,
                success=success,
                metadata=metadata,
            )
        except Exception as exc:
            _kernel_logger.warning(f"Failed to record metric {operation}: {exc}")

    def _finalize_attempt(self, lease_id: str, lease: Any | None, outcome: Outcome) -> None:
        work_id, attempt_id = self._resolve_lease_metadata(lease_id, lease)
        if attempt_id is None:
            return

        attempt_outcome = _map_release_outcome(outcome)
        ended_at = _utcnow().isoformat()

        try:
            db = get_db_manager()
            with db.transaction() as conn:
                if attempt_outcome == "completed":
                    evidence = conn.execute(
                        "SELECT 1 FROM evidence WHERE attempt_id = ? LIMIT 1",
                        (attempt_id,),
                    ).fetchone()
                    if evidence is None:
                        conn.execute(
                            "UPDATE attempts SET ended_at = ? WHERE id = ? AND ended_at IS NULL",
                            (ended_at, attempt_id),
                        )
                        return

                if attempt_outcome:
                    conn.execute(
                        "UPDATE attempts SET ended_at = ?, outcome = ? WHERE id = ? AND ended_at IS NULL",
                        (ended_at, attempt_outcome, attempt_id),
                    )
                else:
                    conn.execute(
                        "UPDATE attempts SET ended_at = ? WHERE id = ? AND ended_at IS NULL",
                        (ended_at, attempt_id),
                    )
        except Exception as exc:
            _kernel_logger.warning(f"Failed to finalize attempt {attempt_id}: {exc}")

    # =========================================================================
    # 1. claim_work
    # =========================================================================

    def claim_work(
        self,
        task_id: str,
        resources: list[dict[str, str]] | list[Resource],
        intent: str,
        agent_id: str,
        *,
        mode: LeaseMode = "write",
        ttl_s: int = 3600,
    ) -> ClaimResponse:
        """Reserve a roadmap item and get a lease.

        This is the entry point for starting work. A successful claim:
        - Reserves the resources for exclusive access
        - Creates a snapshot for rollback
        - Assembles initial context (Lens)

        Args:
            task_id: Roadmap item ID (e.g., "RI-A-001", "PA-047").
            resources: Files/resources the task will operate on.
            intent: Description of what the task will do.
            agent_id: ID of the agent claiming work.
            mode: "read" or "write" (default "write").
            ttl_s: Time-to-live in seconds (default 1 hour).

        Returns:
            ClaimResponse with decision, lens, and lease (if granted).

        Example:
            result = wc.claim_work(
                task_id="PA-047",
                resources=[{"type": "file", "path": "src/lens/interface.py"}],
                intent="Define Lens assembly interface",
                agent_id="claude-worker-001",
            )
            if result.decision.decision == "GRANTED":
                lease_id = result.lease.lease_id
        """
        # Normalize resources
        normalized = [
            r if isinstance(r, Resource) else Resource(type=r["type"], path=r["path"])
            for r in resources
        ]

        work_id_exists = self._roadmap_item_exists(task_id)
        if work_id_exists is False and not _is_adhoc_work_id(task_id):
            now = _utcnow()
            lens = assemble_lens(
                policy_version=self._coordinator._policy_version,
                resources=normalized,
                intent=f"[{task_id}] {intent}",
                cache_state_hash=self._coordinator._context_cache.state_hash(),
                timestamp=now,
            )
            decision = make_decision(
                decision="DENIED",
                reason_code="DENY_INVALID_WORK_ID",
                suggested_next_actions=[
                    "Use an existing roadmap item ID",
                    "Prefix ad hoc tasks with ADHOC-",
                ],
            )
            self._record_metric(
                "work_compiler.claim_work",
                time.perf_counter(),
                success=False,
                metadata={
                    "work_id": task_id,
                    "agent_id": agent_id,
                    "mode": mode,
                    "resource_count": len(normalized),
                    "decision": decision.decision,
                    "reason_code": decision.reason_code,
                },
            )
            return ClaimResponse(decision=decision, lens=dict(lens), lease=None)

        attempt_id = _generate_id("attempt")

        start_time = time.perf_counter()
        try:
            result = self._coordinator.claim(
                resources=normalized,
                mode=mode,
                ttl_s=ttl_s,
                intent=f"[{task_id}] {intent}",
                agent_id=agent_id,
                work_id=task_id,
                attempt_id=attempt_id,
            )
        except Exception as exc:
            self._record_metric(
                "work_compiler.claim_work",
                start_time,
                success=False,
                metadata={
                    "work_id": task_id,
                    "attempt_id": attempt_id,
                    "agent_id": agent_id,
                    "mode": mode,
                    "resource_count": len(normalized),
                    "error": type(exc).__name__,
                },
            )
            raise

        # Add missing_prereqs to lens for immediate visibility (PA-078)
        if result.decision.decision == "GRANTED":
            # PA-099/PA-107: Track lease metadata + create attempt row
            if result.lease:
                result.lease.work_id = task_id
                result.lease.attempt_id = attempt_id
                self._cache_lease_metadata(
                    result.lease.lease_id,
                    task_id,
                    attempt_id,
                )
                _persist_attempt(
                    attempt_id=attempt_id,
                    work_id=task_id,
                    worker_id=agent_id,
                )

            try:
                from motus.core.roadmap import get_missing_prereqs

                prereqs = get_missing_prereqs(task_id)
                result.lens["missing_prereqs"] = [
                    {
                        "prereq_type": p.prereq_type,
                        "prereq_id": p.prereq_id,
                        "prereq_status": p.prereq_status,
                        "prereq_title": p.prereq_title,
                    }
                    for p in prereqs
                ]
            except Exception:
                result.lens["missing_prereqs"] = []

        self._record_metric(
            "work_compiler.claim_work",
            start_time,
            success=result.decision.decision == "GRANTED",
            metadata={
                "work_id": task_id,
                "attempt_id": attempt_id,
                "agent_id": agent_id,
                "mode": mode,
                "resource_count": len(normalized),
                "decision": result.decision.decision,
                "reason_code": result.decision.reason_code,
                "lease_id": result.lease.lease_id if result.lease else None,
            },
        )

        return result

    # =========================================================================
    # 2. get_context
    # =========================================================================

    def get_context(
        self,
        lease_id: str,
        intent: str | None = None,
        task_id: str | None = None,
    ) -> GetContextResponse:
        """Assemble fresh context (Lens) for an active lease.

        Call this to:
        - Get updated context mid-execution
        - Refresh stale data in the Lens
        - Load additional context after claiming

        Args:
            lease_id: Active lease ID from claim_work().
            intent: Optional updated intent description.
            task_id: Optional task ID to include missing_prereqs.

        Returns:
            GetContextResponse with decision, lens, and current lease state.
            If task_id is provided, lens includes missing_prereqs list.

        Example:
            ctx = wc.get_context(lease_id, task_id="PA-047")
            if ctx.decision.decision == "GRANTED":
                resource_specs = ctx.lens.get("resource_specs", [])
                missing_prereqs = ctx.lens.get("missing_prereqs", [])
        """
        start_time = time.perf_counter()
        try:
            result = self._coordinator.get_context(lease_id, intent=intent)
        except Exception as exc:
            self._record_metric(
                "work_compiler.get_context",
                start_time,
                success=False,
                metadata={
                    "lease_id": lease_id,
                    "task_id": task_id,
                    "error": type(exc).__name__,
                },
            )
            raise

        # Add missing_prereqs if task_id provided
        if task_id and result.decision.decision == "GRANTED":
            try:
                from motus.core.roadmap import get_missing_prereqs

                prereqs = get_missing_prereqs(task_id)
                result.lens["missing_prereqs"] = [
                    {
                        "prereq_type": p.prereq_type,
                        "prereq_id": p.prereq_id,
                        "prereq_status": p.prereq_status,
                        "prereq_title": p.prereq_title,
                    }
                    for p in prereqs
                ]
            except Exception:
                # Best-effort: don't fail if roadmap db unavailable
                result.lens["missing_prereqs"] = []

        self._record_metric(
            "work_compiler.get_context",
            start_time,
            success=result.decision.decision == "GRANTED",
            metadata={
                "lease_id": lease_id,
                "task_id": task_id,
                "decision": result.decision.decision,
                "reason_code": result.decision.reason_code,
            },
        )

        return result

    # =========================================================================
    # 3. put_outcome
    # =========================================================================

    def put_outcome(
        self,
        lease_id: str,
        outcome_type: str,
        *,
        path: str | None = None,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> OutcomeResponse:
        """Register a primary deliverable produced by the task.

        Outcomes are the artifacts produced by work (files created/modified,
        APIs implemented, etc.). Unlike evidence (which proves work was done
        correctly), outcomes describe WHAT was delivered.

        Args:
            lease_id: Active lease ID.
            outcome_type: Type of outcome (file, api, config, schema, etc.).
            path: Path or identifier for the outcome.
            description: Human-readable description.
            metadata: Additional structured data.

        Returns:
            OutcomeResponse with acceptance status and outcome_id.

        Example:
            wc.put_outcome(
                lease_id,
                outcome_type="file",
                path="src/lens/interface.py",
                description="Defined LensAssembler protocol",
            )
        """
        start_time = time.perf_counter()
        # Get lease to validate it's active
        lease = self._coordinator._lease_store.get_lease(lease_id)
        if lease is None:
            self._record_metric(
                "work_compiler.put_outcome",
                start_time,
                success=False,
                metadata={
                    "lease_id": lease_id,
                    "outcome_type": outcome_type,
                    "error": "lease_not_found",
                },
            )
            return OutcomeResponse(
                accepted=False,
                message="Lease not found",
            )
        if lease.status != "active":
            self._record_metric(
                "work_compiler.put_outcome",
                start_time,
                success=False,
                metadata={
                    "lease_id": lease_id,
                    "outcome_type": outcome_type,
                    "lease_status": lease.status,
                    "error": "lease_not_active",
                },
            )
            return OutcomeResponse(
                accepted=False,
                message=f"Lease is {lease.status}, not active",
            )

        # Create outcome record
        outcome_id = _generate_id("outcome")
        now = _utcnow()

        outcome_record = {
            "outcome_id": outcome_id,
            "lease_id": lease_id,
            "outcome_type": outcome_type,
            "path": path,
            "description": description,
            "metadata": metadata or {},
            "recorded_at": now.isoformat(),
        }

        # Store in memory (will be attached on release)
        if lease_id not in self._outcomes:
            self._outcomes[lease_id] = []
        self._outcomes[lease_id].append(outcome_record)

        # Record event
        self._coordinator._lease_store.record_event(
            lease_id=lease_id,
            event_type="OUTCOME_REGISTERED",
            payload=outcome_record,
        )

        # Persist to kernel table (PA-061)
        work_id, attempt_id = self._resolve_lease_metadata(lease_id, lease)
        _persist_outcome(
            outcome_id=outcome_id,
            lease_id=lease_id,
            outcome_type=outcome_type,
            work_id=work_id,
            attempt_id=attempt_id,
            path=path,
            description=description,
            metadata=metadata,
        )

        self._record_metric(
            "work_compiler.put_outcome",
            start_time,
            success=True,
            metadata={
                "lease_id": lease_id,
                "outcome_id": outcome_id,
                "outcome_type": outcome_type,
                "work_id": work_id,
                "attempt_id": attempt_id,
            },
        )

        return OutcomeResponse(
            accepted=True,
            outcome_id=outcome_id,
            message=f"Outcome registered: {outcome_type}",
        )

    # =========================================================================
    # 4. record_evidence
    # =========================================================================

    def record_evidence(
        self,
        lease_id: str,
        evidence_type: str,
        *,
        artifacts: dict[str, Any] | None = None,
        test_results: dict[str, Any] | None = None,
        diff_summary: str | None = None,
        log_excerpt: str | None = None,
    ) -> EvidenceResponse:
        """Store verification artifacts proving work was done correctly.

        Evidence provides proof that:
        - Tests pass
        - Changes are valid
        - Work meets requirements

        Args:
            lease_id: Active lease ID.
            evidence_type: Type of evidence (test_result, build_artifact, diff, log,
                attestation, screenshot, reference, document, policy_bundle, other).
            artifacts: Structured evidence data.
            test_results: Test execution results.
            diff_summary: Summary of changes made.
            log_excerpt: Relevant log output.

        Returns:
            EvidenceResponse with acceptance status and evidence_id.

        Example:
            wc.record_evidence(
                lease_id,
                evidence_type="test_result",
                test_results={"passed": 44, "failed": 0, "skipped": 2},
            )
        """
        start_time = time.perf_counter()
        # Get lease to validate it's active
        lease = self._coordinator._lease_store.get_lease(lease_id)
        if lease is None:
            self._record_metric(
                "work_compiler.record_evidence",
                start_time,
                success=False,
                metadata={
                    "lease_id": lease_id,
                    "evidence_type": evidence_type,
                    "error": "lease_not_found",
                },
            )
            return EvidenceResponse(
                accepted=False,
                message="Lease not found",
            )
        if lease.status != "active":
            self._record_metric(
                "work_compiler.record_evidence",
                start_time,
                success=False,
                metadata={
                    "lease_id": lease_id,
                    "evidence_type": evidence_type,
                    "lease_status": lease.status,
                    "error": "lease_not_active",
                },
            )
            return EvidenceResponse(
                accepted=False,
                message=f"Lease is {lease.status}, not active",
            )

        # Create evidence record
        evidence_id = _generate_id("evidence")
        now = _utcnow()

        evidence_record = {
            "evidence_id": evidence_id,
            "lease_id": lease_id,
            "evidence_type": evidence_type,
            "artifacts": artifacts or {},
            "test_results": test_results,
            "diff_summary": diff_summary,
            "log_excerpt": log_excerpt,
            "recorded_at": now.isoformat(),
        }

        # Store in memory (will be attached on release)
        if lease_id not in self._evidence:
            self._evidence[lease_id] = []
        self._evidence[lease_id].append(evidence_record)

        # Record event
        self._coordinator._lease_store.record_event(
            lease_id=lease_id,
            event_type="EVIDENCE_RECORDED",
            payload=evidence_record,
        )

        # Persist to kernel table (PA-061, PA-099)
        work_id, attempt_id = self._resolve_lease_metadata(lease_id, lease)
        _persist_evidence(
            evidence_id=evidence_id,
            lease_id=lease_id,
            evidence_type=evidence_type,
            work_id=work_id,
            attempt_id=attempt_id,
            artifacts=artifacts,
            test_results=test_results,
            diff_summary=diff_summary,
            log_excerpt=log_excerpt,
        )

        self._record_metric(
            "work_compiler.record_evidence",
            start_time,
            success=True,
            metadata={
                "lease_id": lease_id,
                "evidence_id": evidence_id,
                "evidence_type": evidence_type,
                "work_id": work_id,
                "attempt_id": attempt_id,
            },
        )

        return EvidenceResponse(
            accepted=True,
            evidence_id=evidence_id,
            message=f"Evidence recorded: {evidence_type}",
        )

    # =========================================================================
    # 5. record_decision
    # =========================================================================

    def record_decision(
        self,
        lease_id: str,
        decision: str,
        *,
        rationale: str | None = None,
        alternatives_considered: list[str] | None = None,
        constraints: list[str] | None = None,
    ) -> DecisionResponse:
        """Append a decision to the task's decision log.

        Decisions capture WHY choices were made (not what was done).
        This creates an append-only log for audit and learning.

        Args:
            lease_id: Active lease ID.
            decision: The decision made (short summary).
            rationale: Why this decision was made.
            alternatives_considered: Other options that were evaluated.
            constraints: Constraints that influenced the decision.

        Returns:
            DecisionResponse with acceptance status and decision_id.

        Example:
            wc.record_decision(
                lease_id,
                decision="Used Protocol instead of ABC",
                rationale="Protocol is more flexible for dependency injection",
                alternatives_considered=["ABC", "TypedDict"],
            )
        """
        start_time = time.perf_counter()
        # Get lease to validate it's active
        lease = self._coordinator._lease_store.get_lease(lease_id)
        if lease is None:
            self._record_metric(
                "work_compiler.record_decision",
                start_time,
                success=False,
                metadata={
                    "lease_id": lease_id,
                    "error": "lease_not_found",
                },
            )
            return DecisionResponse(
                accepted=False,
                message="Lease not found",
            )
        if lease.status != "active":
            self._record_metric(
                "work_compiler.record_decision",
                start_time,
                success=False,
                metadata={
                    "lease_id": lease_id,
                    "lease_status": lease.status,
                    "error": "lease_not_active",
                },
            )
            return DecisionResponse(
                accepted=False,
                message=f"Lease is {lease.status}, not active",
            )

        # Create decision record
        decision_id = _generate_id("decision")
        now = _utcnow()

        decision_record = {
            "decision_id": decision_id,
            "lease_id": lease_id,
            "decision": decision,
            "rationale": rationale,
            "alternatives_considered": alternatives_considered or [],
            "constraints": constraints or [],
            "recorded_at": now.isoformat(),
        }

        # Store in memory (append-only)
        if lease_id not in self._decisions:
            self._decisions[lease_id] = []
        self._decisions[lease_id].append(decision_record)

        # Record event
        self._coordinator._lease_store.record_event(
            lease_id=lease_id,
            event_type="DECISION_LOGGED",
            payload=decision_record,
        )

        # Persist to kernel table (PA-061, PA-099)
        work_id, attempt_id = self._resolve_lease_metadata(lease_id, lease)
        _persist_decision(
            decision_id=decision_id,
            lease_id=lease_id,
            decision_type="approval",  # Default type for record_decision
            decision_summary=decision,
            work_id=work_id,
            attempt_id=attempt_id,
            rationale=rationale,
            alternatives_considered=alternatives_considered,
            constraints=constraints,
        )

        self._record_metric(
            "work_compiler.record_decision",
            start_time,
            success=True,
            metadata={
                "lease_id": lease_id,
                "decision_id": decision_id,
                "work_id": work_id,
                "attempt_id": attempt_id,
            },
        )

        return DecisionResponse(
            accepted=True,
            decision_id=decision_id,
            message="Decision logged",
        )

    # =========================================================================
    # 6. release_work
    # =========================================================================

    def release_work(
        self,
        lease_id: str,
        outcome: Outcome,
        *,
        handoff: dict[str, Any] | None = None,
        rollback: Literal["auto", "skip"] = "auto",
    ) -> ReleaseResponse:
        """End the lease and record final disposition.

        This finalizes the task execution:
        - Attaches all recorded outcomes, evidence, and decisions
        - Optionally performs rollback on failure
        - Makes resources available for other agents

        Args:
            lease_id: Lease ID to release.
            outcome: Final outcome ("success", "failure", "partial", "aborted").
            handoff: Optional data for next agent.
            rollback: "auto" (rollback on failure) or "skip" (no rollback).

        Returns:
            ReleaseResponse with decision and final lease state.

        Example:
            result = wc.release_work(lease_id, outcome="success")
            if result.decision.reason_code == "RELEASED_OK":
                print("Work completed successfully")
        """
        start_time = time.perf_counter()
        # Gather all evidence IDs for this lease
        evidence_ids = [
            e["evidence_id"] for e in self._evidence.get(lease_id, [])
        ]

        # Include outcomes and decisions in handoff
        combined_handoff = handoff or {}
        if lease_id in self._outcomes:
            combined_handoff["outcomes"] = self._outcomes[lease_id]
        if lease_id in self._decisions:
            combined_handoff["decisions"] = self._decisions[lease_id]

        result = self._coordinator.release(
            lease_id=lease_id,
            outcome=outcome,
            handoff=combined_handoff if combined_handoff else None,
            evidence_ids=evidence_ids if evidence_ids else None,
            rollback=rollback,
        )

        if result.lease is not None:
            self._finalize_attempt(lease_id, result.lease, outcome)

        work_id = None
        attempt_id = None
        if result.lease is not None:
            work_id, attempt_id = self._resolve_lease_metadata(lease_id, result.lease)

        # Clean up in-memory storage
        self._outcomes.pop(lease_id, None)
        self._evidence.pop(lease_id, None)
        self._decisions.pop(lease_id, None)
        self._clear_lease_metadata(lease_id)  # PA-099

        self._record_metric(
            "work_compiler.release_work",
            start_time,
            success=result.decision.decision == "GRANTED",
            metadata={
                "lease_id": lease_id,
                "work_id": work_id,
                "attempt_id": attempt_id,
                "outcome": outcome,
                "decision": result.decision.decision,
                "reason_code": result.decision.reason_code,
                "evidence_count": len(evidence_ids),
            },
        )

        return result

    # =========================================================================
    # Utility methods
    # =========================================================================

    def get_outcomes(self, lease_id: str) -> list[dict[str, Any]]:
        """Get all outcomes recorded for a lease."""
        return list(self._outcomes.get(lease_id, []))

    def get_evidence(self, lease_id: str) -> list[dict[str, Any]]:
        """Get all evidence recorded for a lease."""
        return list(self._evidence.get(lease_id, []))

    def get_decisions(self, lease_id: str) -> list[dict[str, Any]]:
        """Get all decisions logged for a lease."""
        return list(self._decisions.get(lease_id, []))

    def cleanup_leases(self) -> int:
        """Expire stale leases and return count."""
        return self._coordinator.cleanup_stale_leases()

    def get_draft_decisions(self, lease_id: str) -> list[dict[str, Any]]:
        """Get all pending draft decisions for a lease."""
        return [
            d for d in self._draft_decisions.values()
            if d.get("lease_id") == lease_id
        ]

    # =========================================================================
    # Draft Decision Methods (PA-051)
    # =========================================================================

    def emit_draft_decision(
        self,
        lease_id: str,
        decision: str,
        *,
        rationale: str | None = None,
        alternatives_considered: list[str] | None = None,
        constraints: list[str] | None = None,
    ) -> DraftDecisionResponse:
        """Emit a draft decision for later approval.

        Draft decisions allow agents to propose decisions that require
        explicit approval before being recorded. This enables human-in-the-loop
        review of key decisions.

        Args:
            lease_id: Active lease ID.
            decision: The proposed decision (short summary).
            rationale: Why this decision is proposed.
            alternatives_considered: Other options evaluated.
            constraints: Constraints influencing the decision.

        Returns:
            DraftDecisionResponse with draft_id for later approval.

        Example:
            draft = wc.emit_draft_decision(
                lease_id,
                decision="Propose using PostgreSQL over SQLite",
                rationale="Need concurrent writes in production",
                alternatives_considered=["SQLite", "MySQL"],
            )
            # Later, after review:
            wc.approve_draft(draft.draft_id)
        """
        # Get lease to validate it's active
        lease = self._coordinator._lease_store.get_lease(lease_id)
        if lease is None:
            return DraftDecisionResponse(
                accepted=False,
                message="Lease not found",
            )
        if lease.status != "active":
            return DraftDecisionResponse(
                accepted=False,
                message=f"Lease is {lease.status}, not active",
            )

        # Create draft record
        draft_id = _generate_id("draft")
        now = _utcnow()

        draft_record = {
            "draft_id": draft_id,
            "lease_id": lease_id,
            "decision": decision,
            "rationale": rationale,
            "alternatives_considered": alternatives_considered or [],
            "constraints": constraints or [],
            "created_at": now.isoformat(),
            "status": "pending",
        }

        # Store draft
        self._draft_decisions[draft_id] = draft_record

        # Record event
        self._coordinator._lease_store.record_event(
            lease_id=lease_id,
            event_type="DRAFT_DECISION_EMITTED",
            payload=draft_record,
        )

        # Persist to kernel table (PA-061, PA-099)
        work_id, attempt_id = self._resolve_lease_metadata(lease_id, lease)
        _persist_decision(
            decision_id=draft_id,
            lease_id=lease_id,
            decision_type="draft_emitted",
            decision_summary=decision,
            work_id=work_id,
            attempt_id=attempt_id,
            rationale=rationale,
            alternatives_considered=alternatives_considered,
            constraints=constraints,
        )

        return DraftDecisionResponse(
            accepted=True,
            draft_id=draft_id,
            message="Draft decision emitted, awaiting approval",
        )

    def approve_draft(
        self,
        draft_id: str,
        *,
        approver_id: str | None = None,
        approval_note: str | None = None,
    ) -> DecisionResponse:
        """Approve a draft decision and record it.

        Finalizes a draft decision by calling record_decision with the
        draft's contents. The draft is marked as approved and removed
        from pending drafts.

        Args:
            draft_id: Draft ID from emit_draft_decision().
            approver_id: Optional identifier of the approver.
            approval_note: Optional note about why it was approved.

        Returns:
            DecisionResponse from the underlying record_decision call.

        Example:
            result = wc.approve_draft(
                draft.draft_id,
                approver_id="human-reviewer",
                approval_note="Confirmed after architecture review",
            )
        """
        # Get the draft
        draft = self._draft_decisions.get(draft_id)
        if draft is None:
            return DecisionResponse(
                accepted=False,
                message="Draft not found",
            )

        if draft.get("status") != "pending":
            return DecisionResponse(
                accepted=False,
                message=f"Draft is {draft.get('status')}, not pending",
            )

        # Record the decision
        result = self.record_decision(
            lease_id=draft["lease_id"],
            decision=draft["decision"],
            rationale=draft.get("rationale"),
            alternatives_considered=draft.get("alternatives_considered"),
            constraints=draft.get("constraints"),
        )

        if result.accepted:
            # Mark draft as approved
            draft["status"] = "approved"
            draft["approved_at"] = _utcnow().isoformat()
            draft["approver_id"] = approver_id
            draft["approval_note"] = approval_note
            draft["decision_id"] = result.decision_id

            # Record approval event
            self._coordinator._lease_store.record_event(
                lease_id=draft["lease_id"],
                event_type="DRAFT_DECISION_APPROVED",
                payload={
                    "draft_id": draft_id,
                    "decision_id": result.decision_id,
                    "approver_id": approver_id,
                    "approval_note": approval_note,
                },
            )

            # Persist approval to kernel table (PA-061, PA-099)
            draft_lease_id = draft["lease_id"]
            lease = self._coordinator._lease_store.get_lease(draft_lease_id)
            work_id, attempt_id = self._resolve_lease_metadata(draft_lease_id, lease)
            _persist_decision(
                decision_id=_generate_id("approval"),
                lease_id=draft_lease_id,
                decision_type="draft_approved",
                decision_summary=f"Approved draft: {draft['decision']}",
                work_id=work_id,
                attempt_id=attempt_id,
                rationale=approval_note,
                decided_by=approver_id or "agent",
                supersedes_decision_id=draft_id,  # Links to original draft
            )

            # Remove from pending drafts
            del self._draft_decisions[draft_id]

        return result

    def reject_draft(
        self,
        draft_id: str,
        *,
        rejector_id: str | None = None,
        rejection_reason: str | None = None,
    ) -> DraftDecisionResponse:
        """Reject a draft decision.

        Marks a draft decision as rejected without recording it.
        The draft is removed from pending drafts.

        Args:
            draft_id: Draft ID from emit_draft_decision().
            rejector_id: Optional identifier of who rejected.
            rejection_reason: Reason for rejection.

        Returns:
            DraftDecisionResponse indicating rejection was recorded.

        Example:
            wc.reject_draft(
                draft.draft_id,
                rejector_id="human-reviewer",
                rejection_reason="SQLite sufficient for current scale",
            )
        """
        # Get the draft
        draft = self._draft_decisions.get(draft_id)
        if draft is None:
            return DraftDecisionResponse(
                accepted=False,
                message="Draft not found",
            )

        if draft.get("status") != "pending":
            return DraftDecisionResponse(
                accepted=False,
                message=f"Draft is {draft.get('status')}, not pending",
            )

        # Record rejection event
        self._coordinator._lease_store.record_event(
            lease_id=draft["lease_id"],
            event_type="DRAFT_DECISION_REJECTED",
            payload={
                "draft_id": draft_id,
                "rejector_id": rejector_id,
                "rejection_reason": rejection_reason,
            },
        )

        # Persist rejection to kernel table (PA-061, PA-099)
        draft_lease_id = draft["lease_id"]
        lease = self._coordinator._lease_store.get_lease(draft_lease_id)
        work_id, attempt_id = self._resolve_lease_metadata(draft_lease_id, lease)
        _persist_decision(
            decision_id=_generate_id("rejection"),
            lease_id=draft_lease_id,
            decision_type="draft_rejected",
            decision_summary=f"Rejected draft: {draft['decision']}",
            work_id=work_id,
            attempt_id=attempt_id,
            rationale=rejection_reason,
            decided_by=rejector_id or "agent",
            supersedes_decision_id=draft_id,  # Links to original draft
        )

        # Remove from pending drafts
        del self._draft_decisions[draft_id]

        return DraftDecisionResponse(
            accepted=True,
            draft_id=draft_id,
            message=f"Draft rejected: {rejection_reason or 'no reason given'}",
        )
