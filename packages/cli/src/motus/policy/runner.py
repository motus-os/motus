# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Gate runner for Vault OS / Motus OS evidence bundles."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from motus.coordination.trace import (
    DecisionTraceWriter,
    ensure_trace_paths,
    write_handoff_artifact,
    write_last_run_id,
    write_pack_match_trace,
)
from motus.exceptions import SubprocessError, SubprocessTimeoutError
from motus.logging import get_logger
from motus.policy._runner_utils import (
    _evidence_base_dir,
    _git_source_state,
    _git_status_delta_paths,
    _is_git_worktree,
    _normalize_scope_path,
    _now_iso_utc,
    _plan_inline_for_manifest,
    _profile_requires_permits,
    _profile_requires_reconciliation,
    _profile_requires_signature,
    _signing_env,
)
from motus.policy.evidence import build_manifest, ensure_evidence_dirs, write_summary
from motus.policy.load import load_vault_policy
from motus.policy.runner_gates import run_gates
from motus.policy.verifiability import compute_run_hash

EVIDENCE_MANIFEST_VERSION = "1.0.0"

logger = get_logger(__name__)


@dataclass(frozen=True)
class RunResult:
    exit_code: int
    evidence_dir: Path
    manifest_path: Path
    summary_path: Path


def run_gate_plan(
    *,
    plan,
    declared_files: Sequence[str],
    declared_files_source: str = "files",
    repo_dir: Path,
    vault_dir: Path | None = None,
    evidence_dir: Path | None = None,
    policy=None,
    gate_command_overrides: Mapping[str, Sequence[str] | str] | None = None,
    run_id: str | None = None,
    created_at: str | None = None,
) -> RunResult:
    """Run required gates and write an evidence bundle (always, pass or fail)."""

    resolved_policy = policy or load_vault_policy(vault_dir)
    resolved_run_id = run_id or uuid.uuid4().hex
    created_at_iso = created_at or _now_iso_utc()

    evidence_base_dir = _evidence_base_dir(repo_dir, evidence_dir)
    evidence_run_dir = evidence_base_dir / resolved_run_id
    paths = ensure_evidence_dirs(evidence_run_dir)
    trace_paths = ensure_trace_paths(
        repo_dir=repo_dir,
        evidence_dir=paths.root_dir,
        run_id=resolved_run_id,
        created_at=created_at_iso,
    )
    write_last_run_id(trace_paths.last_run_id_path, resolved_run_id)
    trace_writer = DecisionTraceWriter(trace_paths.decision_trace_paths)

    profile_id = getattr(plan, "profile_id", None)
    requires_signature = _profile_requires_signature(profile_id)
    requires_permits = _profile_requires_permits(profile_id)
    signing_key_id, signing_key = _signing_env()

    plan_dict_for_hash = (
        plan.to_dict() if hasattr(plan, "to_dict") else _plan_inline_for_manifest(plan)
    )
    plan_hash = compute_run_hash(plan_dict_for_hash)

    write_pack_match_trace(
        changed_files=declared_files,
        policy=resolved_policy,
        created_at=created_at_iso,
        output_paths=trace_paths.pack_match_trace_paths,
        run_id=resolved_run_id,
    )

    outcome = run_gates(
        plan=plan,
        policy=resolved_policy,
        declared_files=declared_files,
        declared_files_source=declared_files_source,
        repo_dir=repo_dir,
        paths=paths,
        trace_writer=trace_writer,
        run_id=resolved_run_id,
        created_at_iso=created_at_iso,
        plan_hash=plan_hash,
        gate_command_overrides=gate_command_overrides,
        requires_signature=requires_signature,
        requires_permits=requires_permits,
        signing_key_id=signing_key_id,
        signing_key=signing_key,
    )

    results = outcome.results
    overall_exit = outcome.exit_code

    normalized_scope = sorted({_normalize_scope_path(p) for p in declared_files if p})
    scope_set = set(normalized_scope)

    requires_reconciliation = _profile_requires_reconciliation(profile_id)
    workspace_delta_paths: list[str] | None = None
    untracked_delta_paths: list[str] | None = None
    reconciliation_note: str | None = None

    if _is_git_worktree(repo_dir):
        try:
            dirty_paths = _git_status_delta_paths(repo_dir)
            delta_set = set(dirty_paths)
            if declared_files_source == "git-diff":
                delta_set |= scope_set
            workspace_delta_paths = sorted(delta_set)
            untracked_delta_paths = sorted(delta_set - scope_set)
            if untracked_delta_paths:
                overall_exit = overall_exit or 1
                reconciliation_note = f"untracked_delta_paths={len(untracked_delta_paths)}"
        except (SubprocessError, SubprocessTimeoutError, ValueError) as e:
            overall_exit = overall_exit or 1
            reconciliation_note = f"workspace reconciliation failed: {e}"
            logger.warning(
                "Workspace reconciliation failed",
                repo_dir=str(repo_dir),
                error_type=type(e).__name__,
                error=str(e),
            )
    else:
        if requires_reconciliation:
            overall_exit = overall_exit or 1
        reconciliation_note = "workspace reconciliation unavailable (not a git worktree)"

    source_state = _git_source_state(repo_dir) if _is_git_worktree(repo_dir) else None

    write_summary(
        paths,
        results=results,
        workspace_delta_paths=workspace_delta_paths,
        untracked_delta_paths=untracked_delta_paths,
        reconciliation_note=reconciliation_note,
    )

    build_manifest(
        version=EVIDENCE_MANIFEST_VERSION,
        run_id=resolved_run_id,
        created_at=created_at_iso,
        repo_dir=repo_dir,
        policy=resolved_policy,
        plan=plan,
        results=results,
        paths=paths,
        evidence_base_dir=evidence_base_dir,
        workspace_delta_paths=workspace_delta_paths,
        untracked_delta_paths=untracked_delta_paths,
        source_state=source_state,
        signing_key_id=signing_key_id,
        signing_key=signing_key,
    )

    if overall_exit != 0:
        first_failed = next(
            (event for event in trace_writer.events if event.get("status") == "fail"), None
        )
        first_failed_gate = first_failed.get("step") if first_failed else None
        reason_codes = first_failed.get("reason_codes", []) if first_failed else []
        summary = (
            f"Policy run failed at {first_failed_gate}"
            if first_failed_gate
            else "Policy run failed"
        )
        write_handoff_artifact(
            output_paths=trace_paths.handoff_paths,
            run_id=resolved_run_id,
            summary=summary,
            first_failed_gate=first_failed_gate,
            reason_codes=reason_codes,
            trace_path=trace_paths.decision_trace_paths[0].as_posix(),
            manifest_path=paths.manifest_path.as_posix(),
            summary_path=paths.summary_path.as_posix(),
        )

    return RunResult(
        exit_code=overall_exit,
        evidence_dir=paths.root_dir,
        manifest_path=paths.manifest_path,
        summary_path=paths.summary_path,
    )
