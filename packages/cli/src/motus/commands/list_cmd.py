# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""List sessions command."""

import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.markup import escape
from rich.table import Table

from ..logging import get_logger
from ..session_store import SessionStore
from .models import SessionInfo
from .utils import format_age

console = Console()
logger = get_logger(__name__)

# Claude projects directory
CLAUDE_DIR = Path.home() / ".claude"
PROJECTS_DIR = CLAUDE_DIR / "projects"


def _unified_to_session_info(session) -> SessionInfo:
    """Convert UnifiedSession (from orchestrator) to SessionInfo."""
    # Prefer cached file size when available to avoid per-file stat calls.
    size = int(getattr(session, "file_size_bytes", 0) or 0)
    if size <= 0:
        try:
            size = session.file_path.stat().st_size if session.file_path.exists() else 0
        except OSError:
            size = 0

    return SessionInfo(
        session_id=session.session_id,
        file_path=session.file_path,
        last_modified=session.last_modified,
        size=size,
        is_active=session.status.value == "active",
        project_path=session.project_path or "",
        status=session.status.value,
        last_action=session.last_action or "",
        source=session.source.value,
    )


def _record_to_session_info(record) -> SessionInfo:
    """Convert SessionRecord to SessionInfo."""
    updated_at = record.updated_at.replace(tzinfo=None)
    return SessionInfo(
        session_id=record.session_id,
        file_path=record.cwd,
        last_modified=updated_at,
        size=0,
        is_active=record.status == "active",
        project_path=str(record.cwd),
        status=record.status,
        last_action="",
        source=record.agent_type or "claude",
    )


def _record_list_metric(source: str, elapsed_ms: float, count: int) -> None:
    try:
        from motus.core.bootstrap import ensure_database
        from motus.core.database import get_database_path, get_db_manager

        if not get_database_path().exists():
            ensure_database()
        db = get_db_manager()
        db.record_metric(
            "list_sessions",
            elapsed_ms,
            metadata={"source": source, "count": count},
        )
    except Exception as e:
        logger.debug(
            "List metrics recording failed",
            error_type=type(e).__name__,
            error=str(e),
        )


def _filter_recent_records(
    records: list, max_age_hours: int
) -> list:
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=max_age_hours)
    filtered = []
    for record in records:
        updated_at = record.updated_at
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        if updated_at >= cutoff:
            filtered.append(record)
    return filtered


def _load_sessions(max_age_hours: int, fast: bool) -> list[SessionInfo]:
    start = time.perf_counter()
    if os.environ.get("MC_USE_SQLITE", "1") != "0":  # SQLite default, MC_USE_SQLITE=0 for JSON
        store = SessionStore()
        records = _filter_recent_records(store.get_all_sessions(), max_age_hours)
        sessions = [_record_to_session_info(record) for record in records]
        source = "sqlite"
    else:
        from motus.orchestrator import get_orchestrator

        orchestrator = get_orchestrator()
        unified_sessions = orchestrator.discover_all(
            max_age_hours=max_age_hours,
            skip_process_detection=fast,
        )
        store = SessionStore()
        for unified in unified_sessions:
            try:
                store.persist_from_unified(unified)
            except Exception as e:
                logger.debug(
                    "Session store persist failed",
                    session_id=unified.session_id,
                    error_type=type(e).__name__,
                    error=str(e),
                )
        sessions = [_unified_to_session_info(s) for s in unified_sessions]
        source = "json"
    elapsed_ms = (time.perf_counter() - start) * 1000
    _record_list_metric(source, elapsed_ms, len(sessions))
    return sessions


def find_sessions(max_age_hours: int = 2, fast: bool = False) -> list[SessionInfo]:
    """
    Find recent sessions from all sources (Claude, Codex, Gemini, SDK).

    Uses SessionOrchestrator to discover and return sessions from all supported sources.
    All sources are treated equally - no primary/secondary distinction.
    """
    return _load_sessions(max_age_hours=max_age_hours, fast=fast)


# Backward compatibility alias
find_claude_sessions = find_sessions


def find_active_session() -> Optional[SessionInfo]:
    """Find the most recently active session from any source."""
    sessions = find_sessions(max_age_hours=1)
    active = [s for s in sessions if s.is_active]
    return active[0] if active else (sessions[0] if sessions else None)


def list_sessions(max_age_hours: int = 24, fast: bool = False):
    """List recent sessions from all sources (Claude, Codex, Gemini, SDK)."""
    sessions = _load_sessions(max_age_hours=max_age_hours, fast=fast)

    if not sessions:
        console.print("[dim]No recent sessions found.[/dim]")
        console.print(f"[dim]Looking in: {escape(str(PROJECTS_DIR))}[/dim]")
        return

    table = Table(title=f"Recent Sessions (last {max_age_hours}h)")
    table.add_column("Status", style="cyan", width=8)
    table.add_column("Source", width=8)
    table.add_column("Project", style="green")
    table.add_column("Session ID", style="dim")
    table.add_column("Age", justify="right")
    table.add_column("Size", justify="right")
    table.add_column("Last Action", style="yellow")

    # Source badge colors
    source_badges = {
        "claude": "[bold magenta]Claude[/bold magenta]",
        "codex": "[bold green]Codex[/bold green]",
        "gemini": "[bold blue]Gemini[/bold blue]",
        "sdk": "[bold yellow]SDK[/bold yellow]",
    }

    for session in sessions:
        status_icon = "🟢" if session.is_active else "⚪"
        status = f"{status_icon} {escape(session.status)}"

        # Get source badge with fallback
        source = getattr(session, "source", "claude") or "claude"
        source_badge = source_badges.get(source, f"[dim]{escape(source)}[/dim]")

        project_name = (
            escape(session.project_path.split("/")[-1])
            if session.project_path
            else "unknown"
        )

        size_kb = session.size / 1024
        size_str = f"{size_kb:.1f}KB" if size_kb < 1000 else f"{size_kb / 1024:.1f}MB"

        table.add_row(
            status,
            source_badge,
            project_name,
            escape(session.session_id[:12]),
            format_age(session.last_modified),
            size_str,
            escape(session.last_action) if session.last_action else "-",
        )

    console.print(table)

    # Show hint for active sessions
    active = [s for s in sessions if s.is_active]
    if active:
        console.print()
        console.print(
            "[green]💡 Tip:[/green] Run [bold]motus watch[/bold] to monitor the active session"
        )
