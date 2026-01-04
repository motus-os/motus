# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Gate execution for policy runs."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping, Sequence

from motus.coordination.trace import DecisionTraceWriter
from motus.exceptions import SubprocessError, SubprocessTimeoutError
from motus.policy._runner_utils import (
    _find_gate,
    _normalize_scope_path,
    _parse_command_segments,
    _parse_iso_datetime,
    _pick_harness_command,
    _run_command_segments,
)
from motus.policy.contracts import GateResult, VaultPolicyBundle
from motus.policy.permit import (
    PermitValidationError,
    issue_permit_hmac_sha256,
    validate_permit_hmac_sha256,
)
from motus.policy.runner_gate_support import (
    gate_log_paths,
    record_result,
    write_logs,
)


@dataclass(frozen=True)
class GateRunOutcome:
    results: list[GateResult]
    exit_code: int
def run_gates(
    *,
    plan,
    policy: VaultPolicyBundle,
    declared_files: Sequence[str],
    declared_files_source: str,
    repo_dir: Path,
    paths,
    trace_writer: DecisionTraceWriter,
    run_id: str,
    created_at_iso: str,
    plan_hash: str,
    gate_command_overrides: Mapping[str, Sequence[str] | str] | None,
    requires_signature: bool,
    requires_permits: bool,
    signing_key_id: str | None,
    signing_key: str | None,
) -> GateRunOutcome:
    results: list[GateResult] = []
    overall_exit = 0
    override_map = dict(gate_command_overrides or {})
    if requires_signature and (signing_key is None or signing_key_id is None):
        msg = (
            "Run blocked: evidence signing is required for this profile.\n"
            "Set MC_EVIDENCE_KEY_ID and MC_EVIDENCE_SIGNING_KEY.\n"
        )
        for idx, gate_id in enumerate(plan.gates, start=1):
            log_paths = gate_log_paths(paths, idx, gate_id)
            write_logs(log_paths, "", "", msg)
            record_result(
                results=results,
                trace_writer=trace_writer,
                run_id=run_id,
                gate_id=gate_id,
                gate_kind=None,
                status="fail",
                exit_code=127,
                duration_ms=0,
                command_display=None,
                log_paths=log_paths,
                declared_files=declared_files,
                declared_files_source=declared_files_source,
                plan_hash=plan_hash,
            )
        return GateRunOutcome(results=results, exit_code=1)
    scope_set: set[str] | None = None
    if requires_permits:
        normalized_scope = sorted({_normalize_scope_path(p) for p in declared_files if p})
        scope_set = set(normalized_scope)
    created_at_dt = _parse_iso_datetime(created_at_iso) or datetime.now(timezone.utc)
    permit_expires_at = (created_at_dt + timedelta(minutes=30)).isoformat()
    for idx, gate_id in enumerate(plan.gates, start=1):
        gate_def = _find_gate(policy, gate_id)
        log_paths = gate_log_paths(paths, idx, gate_id)
        if gate_def is None:
            msg = f"Unresolvable gate: gate_id={gate_id!r} not found in gate registry.\n"
            write_logs(log_paths, "", "", msg)
            record_result(
                results=results,
                trace_writer=trace_writer,
                run_id=run_id,
                gate_id=gate_id,
                gate_kind=None,
                status="fail",
                exit_code=127,
                duration_ms=0,
                command_display=None,
                log_paths=log_paths,
                declared_files=declared_files,
                declared_files_source=declared_files_source,
                plan_hash=plan_hash,
            )
            overall_exit = overall_exit or 1
            continue

        if gate_def.kind == "intake":
            write_logs(
                log_paths,
                "",
                "",
                f"Gate `{gate_id}` ({gate_def.kind}) is manual/internal in v0.1.\n",
            )
            record_result(
                results=results,
                trace_writer=trace_writer,
                run_id=run_id,
                gate_id=gate_id,
                gate_kind=gate_def.kind,
                status="pass",
                exit_code=0,
                duration_ms=0,
                command_display="manual",
                log_paths=log_paths,
                declared_files=declared_files,
                declared_files_source=declared_files_source,
                plan_hash=plan_hash,
            )
            continue

        command: Sequence[str] | str | None
        if gate_def.kind == "command":
            command = override_map.get(gate_id)
        else:
            command = _pick_harness_command(gate_def.kind, repo_dir)

        if command is None:
            msg = (
                f"Unresolvable gate: gate_id={gate_id!r} kind={gate_def.kind!r} "
                "could not be resolved to a runnable command.\n"
            )
            write_logs(log_paths, "", "", msg)
            record_result(
                results=results,
                trace_writer=trace_writer,
                run_id=run_id,
                gate_id=gate_id,
                gate_kind=gate_def.kind,
                status="fail",
                exit_code=127,
                duration_ms=0,
                command_display=None,
                log_paths=log_paths,
                declared_files=declared_files,
                declared_files_source=declared_files_source,
                plan_hash=plan_hash,
            )
            overall_exit = overall_exit or 1
            continue

        t0 = time.monotonic()
        command_display = command if isinstance(command, str) else " ".join(command)
        try:
            segments = _parse_command_segments(command)
            permit = None
            tool_id = f"gate:{gate_id}"
            if requires_permits:
                if signing_key is None:
                    raise PermitValidationError(
                        "PERMIT.MISSING_KEY",
                        "missing MC_EVIDENCE_SIGNING_KEY for permit signing",
                    )
                permit = issue_permit_hmac_sha256(
                    permit_id=uuid.uuid4().hex,
                    run_id=run_id,
                    tool_id=tool_id,
                    plan_hash=plan_hash,
                    issued_at=created_at_iso,
                    expires_at=permit_expires_at,
                    cwd=str(repo_dir),
                    argv_segments=segments,
                    scope_paths=sorted(scope_set or set()),
                    signing_key=signing_key,
                    key_id=signing_key_id,
                )
                validate_permit_hmac_sha256(
                    permit,
                    expected_run_id=run_id,
                    expected_tool_id=tool_id,
                    expected_plan_hash=plan_hash,
                    expected_cwd=str(repo_dir),
                    expected_argv_segments=segments,
                    expected_scope_paths=sorted(scope_set or set()),
                    signing_key=signing_key,
                    now=created_at_dt,
                )
            exit_code = _run_command_segments(
                segments=segments,
                cwd=repo_dir,
                stdout_path=log_paths.stdout_path,
                stderr_path=log_paths.stderr_path,
            )
        except SubprocessTimeoutError as e:
            duration_ms = int((time.monotonic() - t0) * 1000)
            write_logs(
                log_paths,
                "",
                str(e) + "\n",
                f"Command timed out: {command_display}\n",
            )
            record_result(
                results=results,
                trace_writer=trace_writer,
                run_id=run_id,
                gate_id=gate_id,
                gate_kind=gate_def.kind,
                status="fail",
                exit_code=124,
                duration_ms=duration_ms,
                command_display=command_display,
                log_paths=log_paths,
                declared_files=declared_files,
                declared_files_source=declared_files_source,
                plan_hash=plan_hash,
            )
            overall_exit = overall_exit or 1
            continue
        except (SubprocessError, Exception) as e:
            duration_ms = int((time.monotonic() - t0) * 1000)
            write_logs(
                log_paths,
                "",
                str(e) + "\n",
                f"Command failed to execute: {command_display}\n",
            )
            record_result(
                results=results,
                trace_writer=trace_writer,
                run_id=run_id,
                gate_id=gate_id,
                gate_kind=gate_def.kind,
                status="fail",
                exit_code=127,
                duration_ms=duration_ms,
                command_display=command_display,
                log_paths=log_paths,
                declared_files=declared_files,
                declared_files_source=declared_files_source,
                plan_hash=plan_hash,
            )
            overall_exit = overall_exit or 1
            continue

        duration_ms = int((time.monotonic() - t0) * 1000)
        meta_lines = []
        if requires_permits:
            meta_lines.append(f"permit_tool_id: {tool_id}")
            meta_lines.append(f"permit_plan_hash: {plan_hash}")
            meta_lines.append(f"permit_expires_at: {permit_expires_at}")
            if permit is not None:
                meta_lines.append(f"permit_id: {permit.permit_id}")
                meta_lines.append(f"permit_hash: {permit.permit_hash}")
                meta_lines.append(f"permit_signature: {permit.signature}")
                if permit.key_id is not None:
                    meta_lines.append(f"permit_key_id: {permit.key_id}")

        meta_lines.extend(
            [
                f"command: {command_display}",
                f"exit_code: {exit_code}",
                f"duration_ms: {duration_ms}",
            ]
        )
        log_paths.meta_path.write_text("\n".join(meta_lines) + "\n", encoding="utf-8")

        status = "pass" if exit_code == 0 else "fail"
        if exit_code != 0:
            overall_exit = overall_exit or 1

        record_result(
            results=results,
            trace_writer=trace_writer,
            run_id=run_id,
            gate_id=gate_id,
            gate_kind=gate_def.kind,
            status=status,
            exit_code=exit_code,
            duration_ms=duration_ms,
            command_display=command_display,
            log_paths=log_paths,
            declared_files=declared_files,
            declared_files_source=declared_files_source,
            plan_hash=plan_hash,
        )

    return GateRunOutcome(results=results, exit_code=overall_exit)
