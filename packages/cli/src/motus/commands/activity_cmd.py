# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""CLI command: `motus activity` utilities."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from rich.console import Console

from motus.cli.exit_codes import EXIT_SUCCESS
from motus.observability.activity import load_activity_events

console = Console()


def _resolve_activity_dir() -> Path:
    override = os.environ.get("MOTUS_ACTIVITY_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    motus_dir = _find_motus_dir(Path.cwd())
    if motus_dir is not None:
        return motus_dir / "state" / "ledger"
    return Path.home() / ".motus" / "state" / "ledger"


def _find_motus_dir(start: Path) -> Path | None:
    for base in [start, *start.parents]:
        motus_dir = base / ".motus"
        if motus_dir.exists() and motus_dir.is_dir():
            return motus_dir
    return None


def activity_list_command(args: Any) -> int:
    ledger_dir = _resolve_activity_dir()
    limit = getattr(args, "limit", 50)
    try:
        limit_int = int(limit)
    except (TypeError, ValueError):
        limit_int = 50

    events = load_activity_events(ledger_dir, limit=limit_int)
    if not events:
        console.print("No activity ledger entries found.")
        return EXIT_SUCCESS

    for event in events:
        print(json.dumps(event, sort_keys=True))
    return EXIT_SUCCESS


def activity_status_command(args: Any) -> int:
    ledger_dir = _resolve_activity_dir()
    if not ledger_dir.exists():
        console.print("Activity ledger not initialized.")
        return EXIT_SUCCESS
    path = ledger_dir / "activity.jsonl"
    if not path.exists():
        console.print("Activity ledger file not found.")
        return EXIT_SUCCESS

    console.print(f"Ledger: {path}", markup=False)
    console.print(f"Size: {path.stat().st_size} bytes", markup=False)
    return EXIT_SUCCESS
