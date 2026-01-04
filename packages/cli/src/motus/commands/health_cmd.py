# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""CLI command: `motus health` utilities."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from rich.console import Console

from motus.cli.exit_codes import EXIT_ERROR, EXIT_SUCCESS, EXIT_USAGE

console = Console()


def _find_cli_root(start: Path) -> Path | None:
    for base in [start, *start.parents]:
        direct = base / "scripts" / "ci" / "health_ledger.py"
        if direct.exists():
            return base
        nested = base / "packages" / "cli" / "scripts" / "ci" / "health_ledger.py"
        if nested.exists():
            return base / "packages" / "cli"
    return None


def _run_health_ledger(
    cli_root: Path,
    *,
    write_baseline: bool,
    skip_security: bool,
) -> tuple[int, Path]:
    output_path = cli_root / "artifacts" / "health.json"
    cmd = [
        sys.executable,
        "scripts/ci/health_ledger.py",
        "--output",
        str(output_path),
    ]
    if write_baseline:
        cmd.append("--write-baseline")
    if skip_security:
        cmd.append("--skip-security")

    proc = subprocess.run(cmd, cwd=str(cli_root))
    return proc.returncode, output_path


def _load_health_payload(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _append_history(cli_root: Path, payload: dict[str, Any]) -> None:
    history_path = cli_root / "docs" / "quality" / "health-history.jsonl"
    history_path.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "captured_at": payload.get("timestamp") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tests": payload.get("tests"),
        "coverage": payload.get("coverage"),
        "security": payload.get("security"),
        "lint": payload.get("lint"),
        "typecheck": payload.get("typecheck"),
        "policy_run": payload.get("policy_run"),
    }
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def health_capture_command(args) -> int:
    cli_root = _find_cli_root(Path.cwd())
    if cli_root is None:
        console.print("[red]health_ledger.py not found; run from repo root[/red]")
        return EXIT_USAGE

    rc, output_path = _run_health_ledger(
        cli_root,
        write_baseline=True,
        skip_security=getattr(args, "skip_security", False),
    )
    if rc != 0:
        return rc

    payload = _load_health_payload(output_path)
    if payload is None:
        console.print(f"[red]Missing health output at {output_path}[/red]")
        return EXIT_ERROR

    _append_history(cli_root, payload)
    console.print("Health baseline captured", style="green")
    return EXIT_SUCCESS


def health_compare_command(args) -> int:
    cli_root = _find_cli_root(Path.cwd())
    if cli_root is None:
        console.print("[red]health_ledger.py not found; run from repo root[/red]")
        return EXIT_USAGE

    rc, _ = _run_health_ledger(
        cli_root,
        write_baseline=False,
        skip_security=getattr(args, "skip_security", False),
    )
    return rc


def health_history_command(args) -> int:
    cli_root = _find_cli_root(Path.cwd())
    if cli_root is None:
        console.print("[red]health_ledger.py not found; run from repo root[/red]")
        return EXIT_USAGE

    history_path = cli_root / "docs" / "quality" / "health-history.jsonl"
    if not history_path.exists():
        console.print("No health history found.")
        return EXIT_SUCCESS

    try:
        limit = int(getattr(args, "limit", 10))
    except (TypeError, ValueError):
        limit = 10

    lines = history_path.read_text(encoding="utf-8").splitlines()
    if not lines:
        console.print("No health history found.")
        return EXIT_SUCCESS

    for line in lines[-limit:]:
        console.print(line, markup=False)

    return EXIT_SUCCESS
