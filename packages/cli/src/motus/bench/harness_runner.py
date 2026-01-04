# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Benchmark harness to compare baseline vs Motus-enforced runs."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Callable, Sequence

from motus.bench._git_utils import (
    _git_diff_numstat,
    _git_status_delta_paths,
    _git_status_name_status,
    _is_git_worktree,
    _normalize_repo_rel_path,
)
from motus.policy.load import load_vault_policy
from motus.policy.loader import compute_gate_plan
from motus.policy.run import run_gate_plan
from motus.policy.verify import verify_evidence_bundle

from .harness_types import (
    BENCHMARK_REPORT_VERSION,
    BenchmarkReport,
    BenchmarkTask,
    DeltaScope,
    EnforcementOutcome,
    TaskResult,
    TrialResult,
    VerificationOutcome,
    _default_now_iso,
)


class BenchmarkHarness:
    def __init__(
        self,
        *,
        vault_dir: Path,
        profile_id: str = "personal",
        now_iso: Callable[[], str] = _default_now_iso,
        monotonic_ns: Callable[[], int] | None = None,
        evidence_run_id: Callable[[str, str], str] | None = None,
    ) -> None:
        self._vault_dir = vault_dir
        self._policy = load_vault_policy(vault_dir)
        self._profile_id = profile_id
        self._now_iso = now_iso
        self._monotonic_ns = monotonic_ns or __import__("time").monotonic_ns
        self._evidence_run_id = evidence_run_id or (lambda task_id, mode: f"{task_id}-{mode}")

    def run(
        self,
        *,
        tasks: Sequence[BenchmarkTask],
        output_path: Path | None = None,
    ) -> BenchmarkReport:
        ordered = sorted(tasks, key=lambda t: t.task_id)
        results: list[TaskResult] = []

        with tempfile.TemporaryDirectory(prefix="motus-bench-") as tmp:
            root = Path(tmp)
            for task in ordered:
                baseline_repo = root / task.task_id / "baseline" / "repo"
                motus_repo = root / task.task_id / "motus" / "repo"

                baseline = self._run_trial(
                    task=task,
                    mode="baseline",
                    repo_dir=baseline_repo,
                )
                motus = self._run_trial(
                    task=task,
                    mode="motus",
                    repo_dir=motus_repo,
                )
                results.append(
                    TaskResult(
                        task_id=task.task_id,
                        description=task.description,
                        declared_scope=tuple(
                            _normalize_repo_rel_path(p) for p in task.declared_scope if p
                        ),
                        baseline=baseline,
                        motus=motus,
                    )
                )

        report = BenchmarkReport(version=BENCHMARK_REPORT_VERSION, tasks=tuple(results))
        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(report.to_json() + "\n", encoding="utf-8")
        return report

    def _run_trial(self, *, task: BenchmarkTask, mode: str, repo_dir: Path) -> TrialResult:
        repo_dir.mkdir(parents=True, exist_ok=True)
        task.build_fixture(repo_dir)

        declared_scope = tuple(_normalize_repo_rel_path(p) for p in task.declared_scope if p)
        scope_set = set(declared_scope)

        t0 = self._monotonic_ns()
        task.apply_changes(repo_dir)
        task_ok = task.evaluate(repo_dir)
        analysis: dict | None = None
        if task.analyze is not None:
            analysis = task.analyze(repo_dir)
        delta_paths: tuple[str, ...] = ()
        untracked_delta_paths: tuple[str, ...] = ()
        diff_name_status = ()
        diff_numstat = ()
        churn_added = 0
        churn_deleted = 0
        if _is_git_worktree(repo_dir):
            delta = _git_status_delta_paths(repo_dir)
            delta_paths = tuple(delta)
            untracked_delta_paths = tuple(sorted(set(delta) - scope_set))
            diff_name_status = tuple(_git_status_name_status(repo_dir))
            numstat_entries, churn_added, churn_deleted = _git_diff_numstat(repo_dir)
            diff_numstat = tuple(numstat_entries)

        delta_scope = DeltaScope(
            delta_paths=delta_paths, untracked_delta_paths=untracked_delta_paths
        )

        if mode == "baseline":
            t1 = self._monotonic_ns()
            duration_ms = int((t1 - t0) / 1_000_000)
            return TrialResult(
                mode="baseline",
                task_ok=task_ok,
                duration_ms=duration_ms,
                delta_scope=delta_scope,
                diff_name_status=diff_name_status,
                diff_numstat=diff_numstat,
                churn_lines_added=churn_added,
                churn_lines_deleted=churn_deleted,
                analysis=analysis,
                enforcement=None,
            )

        plan = compute_gate_plan(
            changed_files=list(declared_scope) or ["."],
            policy=self._policy,
            profile_id=self._profile_id,
        )
        run_id = self._evidence_run_id(task.task_id, mode)
        run_result = run_gate_plan(
            plan=plan,
            declared_files=declared_scope,
            declared_files_source="files",
            repo_dir=repo_dir,
            vault_dir=self._vault_dir,
            policy=self._policy,
            run_id=run_id,
            created_at=self._now_iso(),
        )
        verification = verify_evidence_bundle(
            evidence_dir=run_result.evidence_dir, vault_dir=self._vault_dir
        )
        manifest = json.loads(run_result.manifest_path.read_text(encoding="utf-8"))
        untracked = manifest.get("untracked_delta_paths") or []
        untracked_count = len(untracked) if isinstance(untracked, list) else 0

        enforcement = EnforcementOutcome(
            exit_code=run_result.exit_code,
            verification=VerificationOutcome.from_result(verification),
            gate_count=len(getattr(plan, "gates", [])),
            untracked_delta_count=untracked_count,
        )
        t1 = self._monotonic_ns()
        duration_ms = int((t1 - t0) / 1_000_000)
        return TrialResult(
            mode="motus",
            task_ok=task_ok,
            duration_ms=duration_ms,
            delta_scope=delta_scope,
            diff_name_status=diff_name_status,
            diff_numstat=diff_numstat,
            churn_lines_added=churn_added,
            churn_lines_deleted=churn_deleted,
            analysis=analysis,
            enforcement=enforcement,
        )
