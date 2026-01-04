# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Helpers for gate execution logging and trace events."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from motus.coordination.trace import DecisionTraceWriter, hash_files, hash_json
from motus.policy.contracts import GateResult


@dataclass(frozen=True)
class GateLogPaths:
    stdout_path: Path
    stderr_path: Path
    meta_path: Path
    stdout_rel: str
    stderr_rel: str
    meta_rel: str


def gate_log_paths(paths, idx: int, gate_id: str) -> GateLogPaths:
    stdout_path = paths.logs_dir / f"{idx:03d}-{gate_id}.stdout.txt"
    stderr_path = paths.logs_dir / f"{idx:03d}-{gate_id}.stderr.txt"
    meta_path = paths.logs_dir / f"{idx:03d}-{gate_id}.meta.txt"

    stdout_rel = stdout_path.relative_to(paths.root_dir).as_posix()
    stderr_rel = stderr_path.relative_to(paths.root_dir).as_posix()
    meta_rel = meta_path.relative_to(paths.root_dir).as_posix()

    return GateLogPaths(
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        meta_path=meta_path,
        stdout_rel=stdout_rel,
        stderr_rel=stderr_rel,
        meta_rel=meta_rel,
    )


def write_logs(log_paths: GateLogPaths, stdout_text: str, stderr_text: str, meta_text: str) -> None:
    log_paths.stdout_path.write_text(stdout_text, encoding="utf-8")
    log_paths.stderr_path.write_text(stderr_text, encoding="utf-8")
    log_paths.meta_path.write_text(meta_text, encoding="utf-8")


def _emit_trace_event(
    *,
    trace_writer: DecisionTraceWriter,
    run_id: str,
    gate_id: str,
    gate_kind: str | None,
    status: str,
    exit_code: int,
    duration_ms: int,
    command_display: str | None,
    log_paths: GateLogPaths,
    declared_files: Sequence[str],
    declared_files_source: str,
    plan_hash: str,
) -> None:
    inputs = {
        "run_id": run_id,
        "gate_id": gate_id,
        "gate_kind": gate_kind,
        "command": command_display,
        "declared_files": list(declared_files),
        "declared_files_source": declared_files_source,
        "plan_hash": plan_hash,
    }
    outputs_hash = hash_files(
        [log_paths.stdout_path, log_paths.stderr_path, log_paths.meta_path],
        extra=f"exit_code:{exit_code}",
    )
    event = {
        "event_id": f"evt-{uuid.uuid4().hex}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "step": f"gate/{gate_id}",
        "status": status,
        "reason_codes": [],
        "inputs_hash": hash_json(inputs),
        "outputs_hash": outputs_hash,
        "evidence_refs": [log_paths.stdout_rel, log_paths.stderr_rel, log_paths.meta_rel],
        "duration_ms": duration_ms,
    }
    trace_writer.append_event(event)


def record_result(
    *,
    results: list[GateResult],
    trace_writer: DecisionTraceWriter,
    run_id: str,
    gate_id: str,
    gate_kind: str | None,
    status: str,
    exit_code: int,
    duration_ms: int,
    command_display: str | None,
    log_paths: GateLogPaths,
    declared_files: Sequence[str],
    declared_files_source: str,
    plan_hash: str,
) -> None:
    results.append(
        GateResult(
            gate_id=gate_id,
            status=status,
            exit_code=exit_code,
            duration_ms=duration_ms,
            log_paths=[log_paths.stdout_rel, log_paths.stderr_rel, log_paths.meta_rel],
        )
    )
    _emit_trace_event(
        trace_writer=trace_writer,
        run_id=run_id,
        gate_id=gate_id,
        gate_kind=gate_kind,
        status=status,
        exit_code=exit_code,
        duration_ms=duration_ms,
        command_display=command_display,
        log_paths=log_paths,
        declared_files=declared_files,
        declared_files_source=declared_files_source,
        plan_hash=plan_hash,
    )
