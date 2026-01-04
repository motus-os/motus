# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Event handlers and callbacks for watch command."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Optional

from .formatters import format_error, format_task, format_thinking, format_tool
from .output import (
    ErrorEvent,
    SessionInfo,
    SessionStats,
    TaskEvent,
    ThinkingEvent,
    ToolEvent,
    unified_event_to_legacy,
)

try:
    from ..logging import get_logger

    logger = get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)  # type: ignore[assignment]

if TYPE_CHECKING:
    from .. import protocols


def record_watch_metric(
    elapsed_ms: float, session_id: str, duration_seconds: int, success: bool
) -> None:
    """Record watch_session metrics to the database if available."""
    try:
        from motus.core.database import get_db_manager

        db = get_db_manager()
        db.record_metric(
            "watch_session",
            elapsed_ms,
            success=success,
            metadata={
                "session_id": session_id,
                "duration_seconds": duration_seconds,
            },
        )
    except Exception as e:
        logger.debug(
            "Watch metrics recording failed",
            error_type=type(e).__name__,
            error=str(e),
        )


def apply_event_stats(legacy_event, stats: SessionStats) -> None:
    """Update stats from a legacy event without rendering."""
    if isinstance(legacy_event, ThinkingEvent):
        stats.thinking_count += 1
    elif isinstance(legacy_event, TaskEvent):
        stats.agent_count += 1
    elif isinstance(legacy_event, ToolEvent):
        stats.tool_count += 1
        if legacy_event.name in ("Write", "Edit"):
            fp = legacy_event.input.get("file_path", "")
            if fp:
                stats.files_modified.add(fp)
        if legacy_event.risk_level in ("high", "critical"):
            stats.high_risk_ops += 1


def render_event(legacy_event, stats: SessionStats, console) -> bool:
    """Render a legacy event to the console."""
    if isinstance(legacy_event, ThinkingEvent):
        console.print(format_thinking(legacy_event, stats))
    elif isinstance(legacy_event, TaskEvent):
        console.print(format_task(legacy_event, stats))
    elif isinstance(legacy_event, ToolEvent):
        console.print(format_tool(legacy_event, stats))
    elif isinstance(legacy_event, ErrorEvent):
        console.print(format_error(legacy_event, stats))
    else:
        return False
    return True


def build_activity_status(stats: SessionStats, is_active: bool, last_activity: float) -> str:
    """Build the status line for watch polling output."""
    idle_secs = int(time.time() - last_activity)
    activity = "● LIVE" if is_active else f"○ idle ({idle_secs}s)"
    return (
        f"[dim]💭{stats.thinking_count} ⚡{stats.tool_count} "
        f"🤖{stats.agent_count} │ {activity}[/dim]"
    )


def analyze_session(
    session: SessionInfo, unified_session: Optional["protocols.UnifiedSession"] = None
) -> SessionStats:
    """Analyze a session and return stats."""
    from ..orchestrator import get_orchestrator

    stats = SessionStats()

    try:
        orchestrator = get_orchestrator()

        if unified_session is None:
            unified_sessions = orchestrator.discover_all(max_age_hours=168)
            for sess in unified_sessions:
                if sess.session_id == session.session_id or sess.file_path == session.file_path:
                    unified_session = sess
                    break

        if not unified_session:
            return stats

        unified_events = orchestrator.get_events(unified_session)

        for unified_event in unified_events:
            legacy_event = unified_event_to_legacy(unified_event)
            if legacy_event:
                apply_event_stats(legacy_event, stats)

    except Exception as e:
        stats.errors.append(str(e))

    return stats


def generate_agent_context(
    session: SessionInfo, unified_session: Optional["protocols.UnifiedSession"] = None
) -> str:
    """Generate a context summary that can be injected into AI agent prompts."""
    stats = analyze_session(session, unified_session)

    context = f"""## Motus Session Context

**Session ID:** {session.session_id[:12]}
**Duration:** Since {session.last_modified.strftime("%H:%M:%S")}
**Transcript Size:** {session.size // 1024}KB

### Activity Summary
- **Thinking blocks:** {stats.thinking_count}
- **Tool calls:** {stats.tool_count}
- **Agents spawned:** {stats.agent_count}
- **Files modified:** {len(stats.files_modified)}
- **High-risk operations:** {stats.high_risk_ops}

### Files You've Modified
{chr(10).join(f"- {f}" for f in list(stats.files_modified)[:10]) if stats.files_modified else "None yet"}

### Recommendations
"""

    if stats.high_risk_ops > 3:
        context += (
            "- ⚠️ Multiple high-risk operations detected. Consider pausing for human review.\n"
        )

    if stats.tool_count > 50 and stats.thinking_count < 5:
        context += (
            "- 💭 High tool usage with low thinking. Consider more deliberation before acting.\n"
        )

    if len(stats.files_modified) > 10:
        context += "- 📁 Many files modified. Consider committing a checkpoint.\n"

    if stats.agent_count > 5:
        context += "- 🤖 Multiple subagents spawned. Ensure coordination between agents.\n"

    return context
