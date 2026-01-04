# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""CLI command: `motus handoffs` utilities."""

from __future__ import annotations

import os
import shutil
import time
from datetime import datetime
from pathlib import Path

from rich.console import Console

from motus.cli.exit_codes import EXIT_ERROR, EXIT_SUCCESS, EXIT_USAGE

console = Console()


def _resolve_root(arg_root: str | None) -> Path | None:
    if arg_root:
        return Path(arg_root).expanduser()
    env_root = os.environ.get("MOTUS_HANDOFF_ROOT", "").strip()
    if env_root:
        return Path(env_root).expanduser()
    return None


def _handoff_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return [p for p in root.iterdir() if p.is_file() and p.suffix == ".md"]


def _format_timestamp(ts: float) -> str:
    return datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%SZ")


def handoffs_list_command(args) -> int:
    root = _resolve_root(getattr(args, "root", None))
    if root is None:
        console.print("[red]Provide --root or set MOTUS_HANDOFF_ROOT[/red]")
        return EXIT_USAGE
    files = _handoff_files(root)
    if not files:
        console.print(f"No handoffs found in {root}")
        return EXIT_SUCCESS

    files_sorted = sorted(files, key=lambda p: p.stat().st_mtime)
    oldest = files_sorted[0].stat().st_mtime
    newest = files_sorted[-1].stat().st_mtime

    console.print(f"Handoff count: {len(files_sorted)}")
    console.print(f"Oldest: {_format_timestamp(oldest)}")
    console.print(f"Newest: {_format_timestamp(newest)}")
    for path in files_sorted:
        console.print(f"- {path.name}", markup=False)
    return EXIT_SUCCESS


def handoffs_check_command(args) -> int:
    root = _resolve_root(getattr(args, "root", None))
    if root is None:
        console.print("[red]Provide --root or set MOTUS_HANDOFF_ROOT[/red]")
        return EXIT_USAGE
    max_files = int(getattr(args, "max", 10))
    files = _handoff_files(root)
    if len(files) > max_files:
        console.print(
            f"[red]Handoff count {len(files)} exceeds limit {max_files}[/red]"
        )
        return EXIT_ERROR
    console.print(f"Handoff count OK: {len(files)} <= {max_files}")
    return EXIT_SUCCESS


def handoffs_archive_command(args) -> int:
    root = _resolve_root(getattr(args, "root", None))
    if root is None:
        console.print("[red]Provide --root or set MOTUS_HANDOFF_ROOT[/red]")
        return EXIT_USAGE
    if not root.exists():
        console.print(f"[red]Handoff root does not exist: {root}[/red]")
        return EXIT_ERROR

    days = int(getattr(args, "days", 7))
    cutoff = time.time() - days * 86400

    if root.name == "handoffs" and root.parent.name == ".ai":
        base = root.parent.parent
    else:
        base = root.parent
    archive_dir = base / ".ai-archive" / datetime.utcnow().strftime("%Y-%m-%d")
    archive_dir.mkdir(parents=True, exist_ok=True)

    moved = 0
    for path in _handoff_files(root):
        if path.stat().st_mtime < cutoff:
            shutil.move(str(path), str(archive_dir / path.name))
            moved += 1

    console.print(f"Archived {moved} files to {archive_dir}")
    return EXIT_SUCCESS
