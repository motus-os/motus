# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Show session details (`motus show`)."""

from __future__ import annotations

from rich.markup import escape

from motus.cli.exit_codes import EXIT_ERROR

from ..orchestrator import get_orchestrator


def show_session(session_id: str) -> None:
    """Show details for a single session (prefix match supported)."""
    from rich.console import Console
    from rich.panel import Panel

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

    builder = orchestrator.get_builder(target.source)
    last_action = builder.get_last_action(target.file_path) if builder else ""

    payload = target.to_dict()
    payload["last_action"] = last_action

    content = "\n".join(f"- {k}: {v}" for k, v in payload.items())
    content = escape(content)
    console.print(
        Panel(content, title=f"[bold]Session {escape(target.session_id[:12])}[/bold]")
    )
