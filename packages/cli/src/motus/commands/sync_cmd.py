# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Sync command for session SQLite cache."""

from __future__ import annotations

from argparse import Namespace

from rich.console import Console
from rich.markup import escape

from motus.cli.exit_codes import EXIT_ERROR, EXIT_SUCCESS

from ..core.bootstrap import ensure_database
from ..session_cache import SessionSQLiteCache

console = Console()


def sync_command(args: Namespace) -> int:
    """Sync session cache into SQLite.

    Args:
        args: argparse namespace with:
          - full: bool
          - max_age_hours: int | None
    """
    ensure_database()

    full = bool(getattr(args, "full", False))
    max_age_hours = getattr(args, "max_age_hours", None)
    if max_age_hours is not None:
        try:
            max_age_hours = int(max_age_hours)
        except (TypeError, ValueError):
            max_age_hours = None

    cache = SessionSQLiteCache()
    try:
        result = cache.sync(full=full, max_age_hours=None if full else max_age_hours, force=True)
    except RuntimeError as e:
        console.print(f"[red]Sync failed:[/red] {escape(str(e))}")
        return EXIT_ERROR

    console.print(
        f"Ingested {result.ingested} sessions in {result.duration_seconds:.2f}s "
        f"(seen={result.files_seen}, unchanged={result.unchanged}, partial={result.partial}, "
        f"corrupted={result.corrupted}, skipped={result.skipped})"
    )
    return EXIT_SUCCESS
