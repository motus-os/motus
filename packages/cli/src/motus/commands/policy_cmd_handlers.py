# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""CLI commands for Vault OS policy planning and enforcement."""

from __future__ import annotations

import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from motus.cli.exit_codes import EXIT_ERROR, EXIT_SUCCESS
from motus.coordination.trace import ensure_plan_trace_paths, write_pack_match_trace
from motus.exceptions import ConfigError
from motus.policy._runner_utils import _evidence_base_dir
from motus.policy.cleanup import prune_evidence_bundles
from motus.policy.load import load_vault_policy
from motus.policy.loader import compute_gate_plan, format_gate_plan
from motus.policy.verify import verify_evidence_bundle

from .policy_cmd_core import (
    _gate_counts_from_manifest,
    _print_gate_details,
    _record_policy_metric,
    _resolve_changed_files,
    console,
)


def policy_plan_command(args) -> None:
    """Compute and print a deterministic GatePlan for explicit inputs."""

    start = time.perf_counter()
    gates_planned = 0
    files_count = 0
    success = False

    try:
        repo_dir = Path(getattr(args, "repo", None) or Path.cwd()).expanduser().resolve()
        vault_dir_arg = getattr(args, "vault_dir", None)
        vault_dir = Path(vault_dir_arg).expanduser().resolve() if vault_dir_arg else None

        policy = load_vault_policy(vault_dir)
        changed_files, _source = _resolve_changed_files(args, repo_dir)
        files_count = len(changed_files)

        plan = compute_gate_plan(
            changed_files=changed_files,
            policy=policy,
            profile_id=getattr(args, "profile", None),
            pack_cap=getattr(args, "pack_cap", None),
        )
        gates_planned = len(plan.gates)
        created_at = datetime.now(timezone.utc).isoformat()
        plan_id = uuid.uuid4().hex
        trace_paths = ensure_plan_trace_paths(
            repo_dir=repo_dir,
            plan_id=plan_id,
            created_at=created_at,
        )
        write_pack_match_trace(
            changed_files=changed_files,
            policy=policy,
            created_at=created_at,
            output_paths=trace_paths,
            plan_id=plan_id,
        )

        if getattr(args, "json", False):
            console.print(json.dumps(plan.to_dict(), indent=2, sort_keys=True), markup=False)
            success = True
            return

        console.print(format_gate_plan(plan), markup=False)
        _print_gate_details(plan, policy)
        success = True
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        _record_policy_metric(
            "policy_plan",
            elapsed_ms,
            success,
            {"gates_planned": gates_planned, "files_count": files_count},
        )


def policy_run_command(args) -> int:
    """Execute required gates and emit an evidence bundle. Returns an exit code."""

    start = time.perf_counter()
    timings_ms: dict[str, float] = {}
    gates_run = 0
    gates_passed = 0
    gates_failed = 0
    success = False

    try:
        repo_dir = Path(getattr(args, "repo", None) or Path.cwd()).expanduser().resolve()
        vault_dir_arg = getattr(args, "vault_dir", None)
        vault_dir = Path(vault_dir_arg).expanduser().resolve() if vault_dir_arg else None

        evidence_dir_arg = getattr(args, "evidence_dir", None)
        evidence_dir = Path(evidence_dir_arg).expanduser().resolve() if evidence_dir_arg else None

        t0 = time.perf_counter()
        policy = load_vault_policy(vault_dir)
        t1 = time.perf_counter()
        timings_ms["load_policy_ms"] = (t1 - t0) * 1000

        changed_files, source = _resolve_changed_files(args, repo_dir)
        t2 = time.perf_counter()
        timings_ms["resolve_changed_ms"] = (t2 - t1) * 1000

        plan = compute_gate_plan(
            changed_files=changed_files,
            policy=policy,
            profile_id=getattr(args, "profile", None),
            pack_cap=getattr(args, "pack_cap", None),
        )
        t3 = time.perf_counter()
        timings_ms["plan_ms"] = (t3 - t2) * 1000
        gates_run = len(plan.gates)

        from motus.policy.runner import run_gate_plan

        result = run_gate_plan(
            plan=plan,
            declared_files=changed_files,
            declared_files_source=source,
            repo_dir=repo_dir,
            vault_dir=policy.vault_dir,
            evidence_dir=evidence_dir,
            policy=policy,
        )
        t4 = time.perf_counter()
        timings_ms["run_ms"] = (t4 - t3) * 1000

        gates_run, gates_passed, gates_failed = _gate_counts_from_manifest(
            result.manifest_path, gates_run
        )
        t5 = time.perf_counter()
        timings_ms["gate_counts_ms"] = (t5 - t4) * 1000
        success = result.exit_code == 0

        if getattr(args, "json", False):
            console.print(result.manifest_path.read_text(encoding="utf-8"), markup=False)
        else:
            console.print(f"exit_code: {result.exit_code}", markup=False)
            console.print(f"evidence_dir: {result.evidence_dir}", markup=False)
            console.print(f"manifest: {result.manifest_path}", markup=False)
            console.print(f"summary: {result.summary_path}", markup=False)

        return result.exit_code
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        _record_policy_metric(
            "policy_run",
            elapsed_ms,
            success,
            {
                "gates_run": gates_run,
                "gates_passed": gates_passed,
                "gates_failed": gates_failed,
                **timings_ms,
            },
        )


def policy_verify_command(args) -> int:
    """Verify an evidence bundle (hashes + signature). Returns an exit code."""

    evidence_arg = getattr(args, "evidence", None)
    if not evidence_arg:
        raise ConfigError("Missing --evidence")
    evidence_dir = Path(evidence_arg).expanduser().resolve()

    vault_dir_arg = getattr(args, "vault_dir", None)
    vault_dir = Path(vault_dir_arg).expanduser().resolve() if vault_dir_arg else None

    result = verify_evidence_bundle(evidence_dir=evidence_dir, vault_dir=vault_dir)

    if getattr(args, "json", False):
        console.print(json.dumps(result.to_dict(), indent=2, sort_keys=True), markup=False)
    else:
        status = "PASS" if result.ok else "FAIL"
        console.print(f"status: {status}", markup=False)
        if result.reason_codes:
            console.print("reason_codes:", markup=False)
            for code in result.reason_codes:
                console.print(f"  - {code}", markup=False)
        if result.message:
            console.print(f"message: {result.message}", markup=False)

    return EXIT_SUCCESS if result.ok else EXIT_ERROR


def policy_prune_command(args) -> int:
    """Prune old evidence bundles under `.mc/evidence/`."""

    repo_dir = Path(getattr(args, "repo", None) or Path.cwd()).expanduser().resolve()
    evidence_dir_arg = getattr(args, "evidence_dir", None)
    evidence_dir = Path(evidence_dir_arg).expanduser().resolve() if evidence_dir_arg else None

    evidence_base_dir = _evidence_base_dir(repo_dir, evidence_dir)

    keep = int(getattr(args, "keep", 10))
    older_than_raw = getattr(args, "older_than", None)
    older_than = int(older_than_raw) if older_than_raw is not None else None
    dry_run = bool(getattr(args, "dry_run", False))

    result = prune_evidence_bundles(
        evidence_base_dir=evidence_base_dir,
        keep=keep,
        older_than_days=older_than,
        dry_run=dry_run,
    )

    console.print(f"evidence_base_dir: {result.evidence_base_dir}", markup=False)
    console.print(f"bundles_found: {result.bundles_found}", markup=False)
    console.print(f"bundles_kept: {result.bundles_kept}", markup=False)

    if dry_run:
        console.print(f"would_delete: {result.bundles_deleted}", markup=False)
    else:
        console.print(f"deleted: {result.bundles_deleted}", markup=False)

    console.print(f"reclaimed_bytes: {result.reclaimed_bytes}", markup=False)
    if result.deleted_run_ids:
        label = "would_delete_run_ids" if dry_run else "deleted_run_ids"
        console.print(f"{label}:", markup=False)
        for run_id in result.deleted_run_ids:
            console.print(f"  - {run_id}", markup=False)

    return EXIT_SUCCESS


def _main(argv: Sequence[str] | None = None) -> int:
    """Internal test helper for direct invocation."""
    _ = argv
    console.print(
        "policy_cmd is dispatched by motus.cli.core",
        style="red",
        markup=False,
    )
    return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
