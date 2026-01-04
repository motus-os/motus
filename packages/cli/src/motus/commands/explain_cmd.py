# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""CLI command: `motus explain` (decision trace timeline)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from rich.console import Console
from rich.markup import escape
from rich.table import Table

from motus.cli.exit_codes import EXIT_ERROR, EXIT_SUCCESS, EXIT_USAGE
from motus.orient.fs_resolver import find_motus_dir
from motus.policy._runner_utils import _evidence_base_dir

console = Console()
MAX_TRACE_BYTES = int(os.environ.get("MC_TRACE_MAX_BYTES", "5242880"))


def _find_decision_trace(repo_dir: Path, run_id: str) -> Path | None:
    evidence_dir = _evidence_base_dir(repo_dir, None) / run_id
    candidate = evidence_dir / "decision_trace.jsonl"
    if candidate.exists():
        return candidate

    base_dir = find_motus_dir(repo_dir) or (repo_dir / ".mc")
    traces_dir = base_dir / "traces"
    if traces_dir.exists():
        matches = list(traces_dir.rglob(f"decision_trace_{run_id}.jsonl"))
        if matches:
            return matches[0]
    return None


def explain_command(args) -> int:
    run_id = getattr(args, "run_id", None)
    if not run_id:
        console.print("Missing <run_id>", style="red", markup=False)
        return EXIT_USAGE

    repo_dir = Path(getattr(args, "repo", None) or Path.cwd()).expanduser().resolve()
    trace_path = _find_decision_trace(repo_dir, run_id)
    if trace_path is None:
        console.print(
            f"Decision trace not found for run_id={escape(run_id)}",
            style="red",
            markup=False,
        )
        return EXIT_ERROR

    try:
        if trace_path.stat().st_size > MAX_TRACE_BYTES:
            console.print(
                "Decision trace too large to load. "
                "Set MC_TRACE_MAX_BYTES to override.",
                style="red",
                markup=False,
            )
            return EXIT_ERROR
    except OSError:
        console.print("Failed to read decision trace file metadata", style="red", markup=False)
        return EXIT_ERROR

    lines = trace_path.read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in lines if line.strip()]
    if not events:
        console.print("Decision trace is empty", style="red", markup=False)
        return EXIT_ERROR

    console.print(f"Decision Trace for run_id={escape(run_id)}", markup=False)
    console.print(f"Trace: {trace_path}", markup=False)

    table = Table(title="Timeline")
    table.add_column("Step", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Reason Codes", style="yellow")
    table.add_column("Evidence", style="dim")

    first_failed = None
    for event in events:
        status = str(event.get("status", "unknown"))
        if first_failed is None and status == "fail":
            first_failed = event
        reason_codes = ", ".join(event.get("reason_codes", []) or []) or "-"
        evidence_refs = ", ".join(event.get("evidence_refs", []) or [])
        table.add_row(
            str(event.get("step", "")),
            status,
            reason_codes,
            evidence_refs,
        )

    console.print(table)

    if first_failed:
        console.print(
            f"First failing gate: {first_failed.get('step', 'unknown')}",
            style="red",
            markup=False,
        )
        reason_codes = first_failed.get("reason_codes", []) or []
        if reason_codes:
            console.print(
                f"Reason codes: {', '.join(reason_codes)}",
                style="red",
                markup=False,
            )

    return EXIT_SUCCESS
