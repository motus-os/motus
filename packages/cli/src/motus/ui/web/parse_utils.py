# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Parsing helpers for Motus Web UI event streams."""

from collections.abc import Iterable
from typing import Any, Callable, Optional

from motus.logging import get_logger

logger = get_logger(__name__)

FormatCallback = Callable[[Any, str, str, str], Optional[dict]]
LineCallback = Callable[[str, str, str], None]


def _format_event(
    event: Any,
    session_id: str,
    project_path: str,
    source: str,
    format_callback: Optional[FormatCallback],
) -> Any | None:
    if format_callback:
        event_data = format_callback(event, session_id, project_path, source=source)
        return event_data if event_data else None
    return event


def append_formatted_events(
    target: list,
    events: Iterable[Any],
    *,
    session_id: str,
    project_path: str,
    source: str,
    format_callback: Optional[FormatCallback],
) -> None:
    for event in events:
        event_data = _format_event(event, session_id, project_path, source, format_callback)
        if event_data is not None:
            target.append(event_data)


def parse_lines(
    lines: Iterable[str],
    *,
    builder,
    session_id: str,
    project_path: str,
    source: str,
    format_callback: Optional[FormatCallback],
    line_callback: Optional[LineCallback] = None,
    max_events: int | None = None,
) -> list:
    events = []
    if not builder:
        return events

    for line in lines:
        if max_events is not None and len(events) >= max_events:
            break
        if not line.strip():
            continue
        try:
            if line_callback:
                line_callback(line, session_id, project_path)
            parsed = builder.parse_line(line, session_id)
            for event in parsed:
                event_data = _format_event(event, session_id, project_path, source, format_callback)
                if event_data is not None:
                    events.append(event_data)
        except Exception as e:
            logger.debug(f"Failed to parse line in session {session_id[:8]}: {e}")
            continue

    return events


def paginate_events(all_events: list, offset: int, batch_size: int) -> list:
    if offset > 0:
        end_idx = max(0, len(all_events) - offset)
        start_idx = max(0, end_idx - batch_size)
        page = all_events[start_idx:end_idx]
    else:
        page = all_events[-batch_size:]

    return list(reversed(page))


def read_recent_lines(file_path, read_bytes: int = 10000) -> list[str]:
    file_size = file_path.stat().st_size
    read_start = max(0, file_size - read_bytes)

    with open(file_path, "r") as handle:
        handle.seek(read_start)
        content = handle.read()

    return content.strip().split("\n") if content else []


def read_incremental_lines(file_path, last_pos: int) -> tuple[list[str], int]:
    with open(file_path, "r") as handle:
        handle.seek(last_pos)
        content = handle.read()
        new_pos = handle.tell()

    return content.strip().split("\n") if content else [], new_pos


def build_backfill_events(
    orchestrator,
    sessions: list,
    limit: int,
    format_callback: Optional[FormatCallback],
) -> list:
    backfill_events = []
    for session in sessions[:5]:
        try:
            source = session.source.value
            builder = orchestrator.get_builder(session.source)
            if source in ("codex", "gemini"):
                events = orchestrator.get_events(session)[-10:]
                append_formatted_events(backfill_events, events, session_id=session.session_id, project_path=session.project_path, source=source, format_callback=format_callback)
            else:
                lines = read_recent_lines(session.file_path, read_bytes=10000)
                backfill_events.extend(parse_lines(lines, builder=builder, session_id=session.session_id, project_path=session.project_path, source=source, format_callback=format_callback))
        except OSError as e:
            logger.warning("Error reading session file", file_path=str(session.file_path), error_type=type(e).__name__, error=str(e))
        except Exception as e:
            logger.warning("Unexpected error processing session", session_id=session.session_id, error_type=type(e).__name__, error=str(e))
    return backfill_events[-limit:]


def parse_incremental_session(
    orchestrator,
    session,
    last_pos: int,
    line_callback: Optional[LineCallback],
    format_callback: Optional[FormatCallback],
) -> tuple[list, int]:
    source = session.source.value
    try:
        current_size = session.file_path.stat().st_size
    except OSError as e:
        logger.warning("Error reading session file stats", file_path=str(session.file_path), error_type=type(e).__name__, error=str(e))
        return [], last_pos

    builder = orchestrator.get_builder(session.source)

    if source == "gemini":
        if current_size != last_pos:
            all_events = orchestrator.get_events(session, refresh=True)
            events = []
            append_formatted_events(events, all_events, session_id=session.session_id, project_path=session.project_path, source=source, format_callback=format_callback)
            return events, current_size
        return [], last_pos

    if current_size > last_pos:
        try:
            lines, new_pos = read_incremental_lines(session.file_path, last_pos)
        except OSError as e:
            logger.warning("Error reading session file", file_path=str(session.file_path), error_type=type(e).__name__, error=str(e))
            return [], last_pos

        events = parse_lines(
            lines,
            builder=builder,
            session_id=session.session_id,
            project_path=session.project_path,
            source=source,
            format_callback=format_callback,
            line_callback=line_callback,
        )
        return events, new_pos

    return [], last_pos
