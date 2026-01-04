# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Print a session's recent events (`motus feed`)."""

from __future__ import annotations

from rich.markup import escape

from motus.cli.exit_codes import EXIT_ERROR

from ..orchestrator import get_orchestrator
from .utils import redact_secrets


def feed_session(session_id: str, *, tail_lines: int = 200) -> None:
    """Print recent events for a session (prefix match supported)."""
    from rich.console import Console

    console = Console()
    orchestrator = get_orchestrator()
    sessions = orchestrator.discover_all(max_age_hours=168)

    target = None
    for s in sessions:
        if s.session_id == session_id or s.session_id.startswith(session_id):
            target = s
            break

    if target is None:
        console.print(f"[red]Session not found:[/red] {escape(session_id)}")
        console.print("Use `motus list` to see available sessions.")
        raise SystemExit(EXIT_ERROR)

    tail_lines = max(10, min(int(tail_lines), 5000))
    events = orchestrator.get_events_tail(target, n_lines=tail_lines)

    for ev in events:
        ts = ev.timestamp.strftime("%H:%M:%S")
        line = f"{ts} [{ev.event_type.value}] {ev.content}"
        console.print(redact_secrets(line), markup=False)
