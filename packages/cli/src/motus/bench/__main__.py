# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

from __future__ import annotations

import argparse
import os
import statistics
import sys
from pathlib import Path

from motus.bench.adversarial_suite_v0_1 import (
    adversarial_suite_v0_1,
    score_adversarial_task,
)
from motus.bench.harness import BenchmarkHarness, BenchmarkReport
from motus.bench.kernel_suite_v0_1 import kernel_suite_v0_1


def _mean(values: list[int]) -> float:
    return float(sum(values)) / float(len(values)) if values else 0.0


def _median(values: list[int]) -> float:
    return float(statistics.median(values)) if values else 0.0


def _write_markdown_summary(*, report: BenchmarkReport, path: Path) -> None:
    payload = report.to_dict()
    tasks = payload.get("tasks") or []

    baseline_ok = sum(1 for t in tasks if t.get("baseline", {}).get("ok") is True)
    motus_ok = sum(1 for t in tasks if t.get("motus", {}).get("ok") is True)

    baseline_durations = [int(t.get("baseline", {}).get("duration_ms") or 0) for t in tasks]
    motus_durations = [int(t.get("motus", {}).get("duration_ms") or 0) for t in tasks]

    scope_creep_observed = sum(
        1 for t in tasks if t.get("baseline", {}).get("delta_scope", {}).get("in_scope") is False
    )

    blocked_scope_creep = sum(
        1
        for t in tasks
        if int(t.get("motus", {}).get("enforcement", {}).get("untracked_delta_count") or 0) > 0
    )
    blocked_checks = sum(
        1
        for t in tasks
        if (
            t.get("motus", {}).get("enforcement") is not None
            and int(t.get("motus", {}).get("enforcement", {}).get("exit_code") or 0) != 0
            and int(t.get("motus", {}).get("enforcement", {}).get("untracked_delta_count") or 0)
            == 0
        )
    )

    lines: list[str] = []
    lines.append("# Kernel 0.1.1 Benchmark Report (v0.1)")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- Tasks: {len(tasks)}")
    lines.append(f"- Baseline ok: {baseline_ok}/{len(tasks)}")
    lines.append(f"- Motus ok: {motus_ok}/{len(tasks)}")
    lines.append(f"- Scope creep observed (baseline delta out-of-scope): {scope_creep_observed}")
    lines.append(f"- Prevented scope creep (Motus untracked deltas blocked): {blocked_scope_creep}")
    lines.append(f"- Prevented failing checks (Motus gate failures, in-scope): {blocked_checks}")
    lines.append("")
    lines.append("## Friction (duration_ms)")
    lines.append(
        f"- Baseline mean/median: {_mean(baseline_durations):.2f} / {_median(baseline_durations):.2f}"
    )
    lines.append(
        f"- Motus mean/median: {_mean(motus_durations):.2f} / {_median(motus_durations):.2f}"
    )
    lines.append(
        f"- Overhead mean/median: {_mean(motus_durations) - _mean(baseline_durations):.2f} / {_median(motus_durations) - _median(baseline_durations):.2f}"
    )
    lines.append("")
    lines.append("## Notes")
    lines.append("- Baseline does not run gates (simulates ungoverned completion).")
    lines.append("- Motus runs Vault gates + reconciliation and produces verifiable evidence.")
    lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_adversarial_markdown_summary(*, report: BenchmarkReport, path: Path) -> None:
    payload = report.to_dict()
    tasks = payload.get("tasks") or []

    def _severity_counts(mode: str) -> dict[str, int]:
        counts: dict[str, int] = {"S0": 0, "S1": 0, "S2": 0, "S3": 0}
        for task in tasks:
            scores = score_adversarial_task(task)
            severity = (scores.get(mode) or {}).get("severity") or "S2"
            if severity not in counts:
                counts[severity] = 0
            counts[severity] += 1
        return counts

    baseline_counts = _severity_counts("baseline")
    motus_counts = _severity_counts("motus")

    baseline_durations = [int(t.get("baseline", {}).get("duration_ms") or 0) for t in tasks]
    motus_durations = [int(t.get("motus", {}).get("duration_ms") or 0) for t in tasks]

    lines: list[str] = []
    lines.append("# Adversarial Benchmark Report (v0.1)")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- Tasks: {len(tasks)}")
    lines.append(f"- Baseline S0/S1: {baseline_counts['S0']}/{baseline_counts['S1']}")
    lines.append(f"- Motus S0/S1: {motus_counts['S0']}/{motus_counts['S1']}")
    lines.append("")
    lines.append("## Friction (duration_ms)")
    lines.append(
        f"- Baseline mean/median: {_mean(baseline_durations):.2f} / {_median(baseline_durations):.2f}"
    )
    lines.append(
        f"- Motus mean/median: {_mean(motus_durations):.2f} / {_median(motus_durations):.2f}"
    )
    lines.append(
        f"- Overhead mean/median: {_mean(motus_durations) - _mean(baseline_durations):.2f} / "
        f"{_median(motus_durations) - _median(baseline_durations):.2f}"
    )
    lines.append("")
    lines.append("## Per-task")
    lines.append("| Task | Baseline | Motus | Key issues |")
    lines.append("|------|----------|-------|------------|")
    for task in tasks:
        scores = score_adversarial_task(task)
        b = scores.get("baseline") or {}
        m = scores.get("motus") or {}
        issues = ", ".join(m.get("issues") or b.get("issues") or [])
        lines.append(
            f"| {task.get('task_id')} | {b.get('severity')} | {m.get('severity')} | {issues} |"
        )
    lines.append("")
    lines.append("## Notes")
    lines.append("- Baseline does not run gates (simulates ungoverned completion).")
    lines.append("- Motus runs Vault gates + reconciliation and produces verifiable evidence.")
    lines.append(
        "- Severity is artifact-only (diff/scope + tripwire analysis + enforcement outcome)."
    )
    lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m motus.bench")
    parser.add_argument(
        "--vault-dir", type=Path, default=None, help="Path to Vault root (or set MC_VAULT_DIR)."
    )
    parser.add_argument(
        "--profile-id", default="personal", help="Vault profile id (default: personal)."
    )
    parser.add_argument(
        "--suite",
        default="kernel-0.1",
        choices=("kernel-0.1", "adversarial-0.1"),
        help="Benchmark suite to run (default: kernel-0.1).",
    )
    parser.add_argument("--output", type=Path, required=True, help="Where to write report JSON.")
    parser.add_argument(
        "--markdown", type=Path, default=None, help="Optional markdown summary output path."
    )
    args = parser.parse_args(argv)

    vault_dir = args.vault_dir or Path(os.environ.get("MC_VAULT_DIR", "")).expanduser()
    if not str(vault_dir).strip() or not vault_dir.exists():
        parser.error("Vault dir not found. Provide --vault-dir or set MC_VAULT_DIR.")

    harness = BenchmarkHarness(vault_dir=vault_dir, profile_id=args.profile_id)
    tasks = kernel_suite_v0_1() if args.suite == "kernel-0.1" else adversarial_suite_v0_1()
    report = harness.run(tasks=tasks, output_path=args.output)
    if args.markdown is not None:
        if args.suite == "adversarial-0.1":
            _write_adversarial_markdown_summary(report=report, path=args.markdown)
        else:
            _write_markdown_summary(report=report, path=args.markdown)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
