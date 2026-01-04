# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Shared helpers for policy CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from rich.console import Console

from motus.exceptions import ConfigError, SubprocessError, SubprocessTimeoutError
from motus.logging import get_logger
from motus.subprocess_utils import GIT_SHORT_TIMEOUT_SECONDS, run_subprocess

console = Console()
logger = get_logger(__name__)


def _gate_counts_from_manifest(manifest_path: Path, fallback_run: int) -> tuple[int, int, int]:
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        results = data.get("gate_results", [])
        gates_run = len(results)
        gates_passed = sum(1 for r in results if r.get("status") == "pass")
        gates_failed = sum(1 for r in results if r.get("status") == "fail")
        return gates_run, gates_passed, gates_failed
    except Exception as e:
        logger.debug(
            "Policy metrics manifest parse failed",
            error_type=type(e).__name__,
            error=str(e),
        )
        return fallback_run, 0, 0


def _record_policy_metric(operation: str, elapsed_ms: float, success: bool, metadata: dict) -> None:
    try:
        from motus.core.database import get_db_manager

        db = get_db_manager()
        db.record_metric(
            operation,
            elapsed_ms,
            success=success,
            metadata=metadata,
        )
    except Exception as e:
        logger.debug(
            "Policy metrics recording failed",
            error_type=type(e).__name__,
            error=str(e),
        )


def _as_repo_relative_paths(files: Sequence[str], repo_dir: Path) -> list[str]:
    result: list[str] = []
    repo_dir_resolved = repo_dir.resolve()
    for raw in files:
        path = Path(raw).expanduser()
        if path.is_absolute():
            try:
                result.append(path.resolve().relative_to(repo_dir_resolved).as_posix())
                continue
            except ValueError:
                result.append(path.as_posix())
                continue
        result.append(path.as_posix())
    return result


def _changed_files_from_git_diff(repo_dir: Path, base: str, head: str) -> list[str]:
    try:
        proc = run_subprocess(
            ["git", "diff", "--name-only", base, head],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout_seconds=GIT_SHORT_TIMEOUT_SECONDS,
            what="git diff --name-only",
        )
    except FileNotFoundError as e:
        raise ConfigError("git is required for --git-diff", details=str(e)) from e
    except SubprocessTimeoutError as e:
        raise ConfigError("git diff timed out", details=str(e)) from e
    except SubprocessError as e:
        raise ConfigError("git diff failed to execute", details=str(e)) from e

    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        raise ConfigError(
            "git diff failed",
            details=stderr or f"exit_code={proc.returncode}",
        )

    return [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]


def _resolve_changed_files(args, repo_dir: Path) -> tuple[list[str], str]:
    files: list[str] | None = getattr(args, "files", None)
    git_diff: Sequence[str] | None = getattr(args, "git_diff", None)

    if files:
        return _as_repo_relative_paths(files, repo_dir), "files"
    if git_diff:
        if len(git_diff) != 2:
            raise ConfigError(
                "Invalid --git-diff usage", details="Expected: --git-diff <base> <head>"
            )
        return _changed_files_from_git_diff(repo_dir, git_diff[0], git_diff[1]), "git-diff"

    raise ConfigError(
        "No change input provided",
        details="Provide one of: --files <file>... OR --git-diff <base> <head>",
    )


def _print_gate_details(plan, policy) -> None:
    gate_by_id = {g.id: g for g in policy.gate_registry.gates}
    console.print("gate_details:", markup=False)
    for gate_id in plan.gates:
        gate = gate_by_id.get(gate_id)
        if gate is None:
            console.print(f"  - {gate_id}: (missing in registry)", markup=False)
            continue
        console.print(
            f"  - {gate.id}: kind={gate.kind} tier={gate.tier} desc={gate.description}",
            markup=False,
        )
