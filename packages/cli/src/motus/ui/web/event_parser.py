# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Event parsing utilities for Motus Web UI.

This module handles all event parsing logic extracted from server.py:
- Reading session files with byte positions
- JSONL line parsing
- Claude/Codex/Gemini format handling
- Event batching for history/backfill
"""

from motus.logging import get_logger
from motus.orchestrator import get_orchestrator
from motus.tail_reader import get_file_stats, tail_lines
from motus.ui.web.event_handlers import build_session_intents, parse_user_intent_from_line
from motus.ui.web.parse_utils import (
    build_backfill_events,
    paginate_events,
    parse_incremental_session,
    parse_lines,
)

logger = get_logger(__name__)


def parse_session_history(
    session_id: str,
    offset: int = 0,
    batch_size: int = 200,
    format_callback=None,
) -> dict:
    """Parse historical events from a session file."""
    orchestrator = get_orchestrator()
    target_session = orchestrator.get_session(session_id)

    if not target_session:
        return {
            "events": [],
            "total_events": 0,
            "has_more": False,
            "offset": offset,
            "error": "Session not found or file not readable",
        }

    try:
        source = target_session.source.value
        file_path = target_session.file_path
        stats = get_file_stats(file_path)
        estimated_total = stats.get("line_count", 0)

        lines_to_read = batch_size + offset + 100
        raw_lines = tail_lines(file_path, n_lines=lines_to_read)

        builder = orchestrator.get_builder(target_session.source)
        all_events = parse_lines(
            raw_lines,
            builder=builder,
            session_id=session_id,
            project_path=target_session.project_path,
            source=source,
            format_callback=format_callback,
            max_events=batch_size + offset + 10,
        )
        history_events = paginate_events(all_events, offset, batch_size)
        has_more = len(all_events) > (offset + batch_size) or estimated_total > len(all_events)

        return {
            "events": history_events,
            "total_events": estimated_total,
            "has_more": has_more,
            "offset": offset,
            "error": None,
        }

    except OSError as e:
        logger.debug(
            "Error reading session file during history load",
            error_type=type(e).__name__,
            error=str(e),
        )
        return {
            "events": [],
            "total_events": 0,
            "has_more": False,
            "offset": offset,
            "error": f"Error reading session: {str(e)}",
        }
    except Exception as e:
        logger.warning(
            "Unexpected error loading session history",
            error_type=type(e).__name__,
            error=str(e),
        )
        return {
            "events": [],
            "total_events": 0,
            "has_more": False,
            "offset": offset,
            "error": "Unexpected error loading session",
        }


def parse_backfill_events(
    sessions: list,
    limit: int = 30,
    format_callback=None,
) -> list:
    """Parse historical events for backfill from multiple sessions."""
    orchestrator = get_orchestrator()
    return build_backfill_events(orchestrator, sessions, limit, format_callback)


def parse_incremental_events(
    session,
    last_pos: int,
    line_callback=None,
    format_callback=None,
) -> tuple[list, int]:
    """Parse new events from a session file incrementally."""
    orchestrator = get_orchestrator()
    return parse_incremental_session(
        orchestrator,
        session,
        last_pos,
        line_callback,
        format_callback,
    )


def parse_session_intents(session_id: str) -> dict:
    """Extract user intents and stats from a session."""
    orchestrator = get_orchestrator()
    target_session = orchestrator.get_session(session_id)

    if not target_session:
        return {"error": "Session not found"}

    try:
        events = orchestrator.get_events_tail_validated(target_session, n_lines=500)
        result = build_session_intents(events)
        result["error"] = None
        return result
    except Exception as e:
        logger.warning(
            "Error extracting intents for session",
            session_id=session_id,
            error_type=type(e).__name__,
            error=str(e),
        )
        return {"error": str(e)}


__all__ = [
    "parse_backfill_events",
    "parse_incremental_events",
    "parse_session_history",
    "parse_session_intents",
    "parse_user_intent_from_line",
]
