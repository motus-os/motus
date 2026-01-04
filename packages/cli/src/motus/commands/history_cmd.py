# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""History command for Motus."""

import time

from rich import box
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from ..logging import get_logger

console = Console()
logger = get_logger(__name__)


def _record_history_metric(
    elapsed_ms: float, session_count: int, event_count: int, success: bool
) -> None:
    try:
        from motus.core.database import get_db_manager

        db = get_db_manager()
        db.record_metric(
            "history_query",
            elapsed_ms,
            success=success,
            metadata={"session_count": session_count, "event_count": event_count},
        )
    except Exception as e:
        logger.debug(
            "History metrics recording failed",
            error_type=type(e).__name__,
            error=str(e),
        )


def history_command(max_sessions: int = 10, max_events: int = 50) -> None:
    """Display command history for recent sessions.

    Shows a summary of recent tool calls and actions across sessions.

    Args:
        max_sessions: Maximum number of sessions to include (default 10).
        max_events: Maximum events to show per session (default 50).
    """
    start = time.perf_counter()
    session_count = 0
    event_count = 0
    success = False

    try:
        from ..orchestrator import get_orchestrator
        from ..protocols import EventType
    except ImportError:
        console.print("[red]Error: Could not import orchestrator.[/red]")
        return

    try:
        orchestrator = get_orchestrator()
        sessions = orchestrator.discover_all(max_age_hours=48)
        session_count = len(sessions)

        if not sessions:
            console.print("[yellow]No recent sessions found.[/yellow]")
            console.print("[dim]Sessions from the last 48 hours will appear here.[/dim]")
            success = True
            return

        # Collect recent events across sessions
        all_events = []

        for session in sessions[:max_sessions]:
            try:
                events = orchestrator.get_events(session)
                for event in events[-max_events:]:
                    all_events.append((session, event))
            except Exception as e:
                logger.debug(
                    f"Failed to get events for session {session.session_id[:8]}: {e}"
                )
                continue

        event_count = len(all_events)
        if not all_events:
            console.print("[yellow]No recent history found.[/yellow]")
            console.print(
                "[dim]Tool calls and actions will appear here once sessions have activity.[/dim]"
            )
            success = True
            return

        # Sort by timestamp (newest first)
        all_events.sort(key=lambda x: x[1].timestamp, reverse=True)

        # Create table
        table = Table(
            title="Recent History",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan",
        )

        table.add_column("Time", style="dim", width=8)
        table.add_column("Session", style="blue", width=10)
        table.add_column("Source", style="magenta", width=8)
        table.add_column("Type", style="green", width=12)
        table.add_column("Details", style="white", no_wrap=False)

        # Display up to 30 most recent events
        for session, event in all_events[:30]:
            time_str = event.timestamp.strftime("%H:%M:%S")
            session_short = escape(session.session_id[:8])
            source = escape(session.source.value.upper())

            # Format event type and details
            event_type = (
                event.event_type.value
                if hasattr(event.event_type, "value")
                else str(event.event_type)
            )
            event_type_label = escape(event_type)

            details = ""
            if event.event_type == EventType.TOOL:
                tool_name = event.tool_name or "?"
                if event.tool_input:
                    # Extract key info from tool input
                    if "file_path" in event.tool_input:
                        details = f"{tool_name}: {event.tool_input['file_path']}"
                    elif "command" in event.tool_input:
                        cmd = event.tool_input["command"][:60]
                        details = f"{tool_name}: {cmd}..."
                    elif "pattern" in event.tool_input:
                        details = f"{tool_name}: {event.tool_input['pattern']}"
                    elif "query" in event.tool_input:
                        details = f"{tool_name}: {event.tool_input['query']}"
                    else:
                        details = tool_name
                else:
                    details = tool_name
            elif event.event_type == EventType.THINKING:
                content = event.content[:80] if event.content else ""
                details = f"{content}..." if len(event.content or "") > 80 else content
            elif event.event_type == EventType.AGENT_SPAWN:
                agent_type = event.agent_type or "unknown"
                model = event.agent_model or event.model or "?"
                details = f"{agent_type} ({model})"
            elif event.event_type == EventType.DECISION:
                details = event.content[:80] if event.content else ""
            elif event.event_type == EventType.ERROR:
                details = (
                    f"[red]{escape(event.content[:60])}[/red]"
                    if event.content
                    else "[red]Error[/red]"
                )
            else:
                details = event.content[:60] if event.content else ""

            if event.event_type != EventType.ERROR:
                details = escape(details)

            # Color-code by event type
            type_style = {
                "tool": "green",
                "thinking": "magenta",
                "agent_spawn": "yellow",
                "decision": "cyan",
                "error": "red",
                "response": "blue",
            }.get(event_type.lower(), "white")

            table.add_row(
                time_str,
                session_short,
                source,
                f"[{type_style}]{event_type_label}[/{type_style}]",
                details,
            )

        console.print(table)

        # Summary
        console.print()
        console.print(
            f"[dim]Showing {min(30, len(all_events))} of {len(all_events)} events from {len(sessions)} sessions[/dim]"
        )
        console.print("[dim]Use 'motus watch <session_id>' to follow a specific session[/dim]")
        success = True
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        _record_history_metric(elapsed_ms, session_count, event_count, success)
