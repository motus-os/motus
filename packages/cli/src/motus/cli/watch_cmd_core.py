# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Watch command implementations for real-time session monitoring."""

from __future__ import annotations

import importlib
import time
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from rich.markup import escape

from motus.config import config

from .exit_codes import EXIT_ERROR
from .formatters import create_header, create_summary_table
from .output import (
    SessionInfo,
    SessionStats,
    unified_event_to_legacy,
    unified_session_to_session_info,
)
from .watch_cmd_handlers import build_activity_status, record_watch_metric, render_event

if TYPE_CHECKING:
    from .. import protocols


def _get_watch_module():
    return importlib.import_module("motus.cli.watch_cmd")


def watch_session(
    session: SessionInfo, unified_session: Optional["protocols.UnifiedSession"] = None
):
    """Watch a Claude session in real-time."""
    from ..orchestrator import get_orchestrator

    watch_module = _get_watch_module()
    console = watch_module.console
    rule = watch_module.Rule

    start = time.perf_counter()
    success = False

    console.clear()
    stats = SessionStats(start_time=datetime.now())

    console.print(create_header(session))
    console.print()

    console.print("[dim]Loading recent activity...[/dim]\n")

    orchestrator = get_orchestrator()

    if unified_session is None:
        unified_sessions = orchestrator.discover_all(max_age_hours=168)
        for sess in unified_sessions:
            if sess.session_id == session.session_id or sess.file_path == session.file_path:
                unified_session = sess
                break

    if not unified_session:
        console.print("[red]Error: Session not found in orchestrator[/red]")
        return

    all_unified_events = orchestrator.get_events(unified_session)
    recent_events = []
    for unified_event in all_unified_events:
        legacy_event = unified_event_to_legacy(unified_event)
        if legacy_event:
            recent_events.append(legacy_event)

    history_stats = SessionStats()

    for event in recent_events[-8:]:
        render_event(event, history_stats, console)
        console.print()

    last_position = len(all_unified_events)
    last_activity = time.time()

    console.print(rule("[bold green]Watching for new activity[/bold green]", style="green"))
    console.print()

    watch_timeout_seconds = config.tui.watch_max_seconds
    deadline = None
    if watch_timeout_seconds > 0:
        deadline = time.monotonic() + watch_timeout_seconds

    poll_count = 0
    is_active = False
    timed_out = False

    try:
        while True:
            if deadline is not None and time.monotonic() >= deadline:
                timed_out = True
                break
            has_new_content = False
            new_events = []

            all_unified_events = orchestrator.get_events(unified_session, refresh=True)

            if len(all_unified_events) > last_position:
                has_new_content = True
                for unified_event in all_unified_events[last_position:]:
                    legacy_event = unified_event_to_legacy(unified_event)
                    if legacy_event:
                        new_events.append(legacy_event)
                last_position = len(all_unified_events)

            if has_new_content:
                last_activity = time.time()
                is_active = True
                for event in new_events:
                    render_event(event, stats, console)
                    console.print()
            else:
                idle_time = time.time() - last_activity
                if idle_time > 3:
                    is_active = False

            poll_count += 1
            if poll_count % 10 == 0:
                status = build_activity_status(stats, is_active, last_activity)
                console.print(status, end="\r")

            time.sleep(0.3)

    except KeyboardInterrupt:
        console.print("\n")
        console.print(rule("[dim]Session ended[/dim]"))
        console.print(create_summary_table(stats))
        success = True
    finally:
        if timed_out:
            console.print("\n")
            console.print(rule("[dim]Watch timeout reached[/dim]"))
            console.print(create_summary_table(stats))
            success = True
        elapsed_ms = (time.perf_counter() - start) * 1000
        duration_seconds = int(elapsed_ms / 1000)
        record_watch_metric(elapsed_ms, session.session_id, duration_seconds, success)


def watch_command(args):
    """Watch command handler."""
    from ..orchestrator import get_orchestrator

    session_id = getattr(args, "session_id", None)

    orchestrator = get_orchestrator()
    max_age = 48 if session_id else 1
    unified_sessions = orchestrator.discover_all(max_age_hours=max_age)

    if not unified_sessions:
        watch_module = _get_watch_module()
        console = watch_module.console
        console.print("[yellow]No active session found.[/yellow]")
        console.print("Use 'motus list' to see available sessions.")
        raise SystemExit(EXIT_ERROR)

    unified = None
    if session_id:
        for sess in unified_sessions:
            if sess.session_id.startswith(session_id):
                unified = sess
                break
        if not unified:
            watch_module = _get_watch_module()
            console = watch_module.console
            console.print(f"[red]Session not found: {escape(session_id)}[/red]")
            console.print("Use 'motus list' to see available sessions.")
            raise SystemExit(EXIT_ERROR)
    else:
        unified = unified_sessions[0]

    session = unified_session_to_session_info(unified)
    watch_module = _get_watch_module()
    watch_module.watch_session(session, unified)
