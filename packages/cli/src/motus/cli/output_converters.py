# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Conversion helpers for CLI output."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

try:
    from ..logging import get_logger

    logger = get_logger(__name__)
except ImportError:
    import logging

    logger = logging.getLogger(__name__)  # type: ignore[assignment]

if TYPE_CHECKING:
    from .. import protocols

from .output_types import ErrorEvent, SessionInfo, TaskEvent, ThinkingEvent, ToolEvent


def unified_session_to_session_info(unified: "protocols.UnifiedSession") -> SessionInfo:
    """Convert a UnifiedSession to legacy SessionInfo for CLI display."""
    from ..protocols import SessionStatus

    status_map = {
        SessionStatus.ACTIVE: "active",
        SessionStatus.OPEN: "open",
        SessionStatus.CRASHED: "crashed",
        SessionStatus.IDLE: "idle",
        SessionStatus.ORPHANED: "orphaned",
    }

    status_str = status_map.get(unified.status, "idle")
    is_active = unified.status == SessionStatus.ACTIVE

    try:
        size = unified.file_path.stat().st_size
    except OSError:
        size = 0

    last_action = ""

    return SessionInfo(
        session_id=unified.session_id,
        file_path=unified.file_path,
        last_modified=unified.last_modified,
        size=size,
        is_active=is_active,
        project_path=unified.project_path,
        status=status_str,
        last_action=last_action,
        source=unified.source.value,
    )


def unified_event_to_legacy(event) -> ThinkingEvent | ToolEvent | TaskEvent | ErrorEvent | None:
    """Convert a UnifiedEvent to legacy event types for CLI display."""
    try:
        from ..protocols import EventType
    except ImportError:
        EventType = None  # type: ignore[assignment,misc]  # noqa: N806

    try:
        evt_type = event.event_type.value
    except AttributeError:
        evt_type = event.event_type

    if evt_type == (EventType.THINKING.value if hasattr(EventType, "THINKING") else "thinking"):
        return ThinkingEvent(
            content=event.content,
            timestamp=event.timestamp,
        )

    if evt_type == (EventType.TOOL.value if hasattr(EventType, "TOOL") else "tool"):
        return ToolEvent(
            name=event.tool_name or "unknown",
            input=event.tool_input or {},
            timestamp=event.timestamp,
            risk_level=event.risk_level.value if event.risk_level else "safe",
            status=event.tool_status.value if event.tool_status else "running",
            output=event.tool_output,
        )

    if evt_type == (
        EventType.AGENT_SPAWN.value if hasattr(EventType, "AGENT_SPAWN") else "spawn"
    ):
        return TaskEvent(
            description=event.agent_description or event.content,
            prompt=event.agent_prompt or "",
            subagent_type=event.agent_type or "unknown",
            model=event.agent_model or event.model,
            timestamp=event.timestamp,
        )

    if evt_type == (EventType.ERROR.value if hasattr(EventType, "ERROR") else "error"):
        return ErrorEvent(
            message=event.content,
            timestamp=event.timestamp,
            error_type=event.raw_data.get("error_type", "unknown") if event.raw_data else "unknown",
            tool_name=event.tool_name,
        )

    return None


def get_last_error(file_path: Path, source: str = "claude") -> Optional[ErrorEvent]:
    """Get the most recent error from a session file."""
    from ..orchestrator import get_orchestrator

    errors = []

    try:
        orchestrator = get_orchestrator()
        builder = orchestrator._get_builder_for_file(file_path)

        if not builder:
            return None

        from ..protocols import SessionStatus, Source, UnifiedSession

        try:
            stat = file_path.stat()
            last_modified = datetime.fromtimestamp(stat.st_mtime)
        except OSError:
            return None

        unified_session = UnifiedSession(
            session_id=file_path.stem,
            file_path=file_path,
            last_modified=last_modified,
            created_at=last_modified,
            source=Source(source.lower()),
            status=SessionStatus.IDLE,
            status_reason="idle",
            project_path="",
        )

        unified_events = orchestrator.get_events(unified_session)

        for unified_event in unified_events:
            legacy_event = unified_event_to_legacy(unified_event)
            if isinstance(legacy_event, ErrorEvent):
                errors.append(legacy_event)

    except Exception as e:
        logger.debug(f"Error extracting last error: {e}")
        pass

    return errors[-1] if errors else None


def get_session_errors(file_path: Path, source: str = "claude") -> list[ErrorEvent]:
    """Get all errors from a session file, newest last."""
    from ..orchestrator import get_orchestrator

    errors = []

    try:
        orchestrator = get_orchestrator()
        builder = orchestrator._get_builder_for_file(file_path)

        if not builder:
            return []

        from ..protocols import SessionStatus, Source, UnifiedSession

        try:
            stat = file_path.stat()
            last_modified = datetime.fromtimestamp(stat.st_mtime)
        except OSError:
            return []

        unified_session = UnifiedSession(
            session_id=file_path.stem,
            file_path=file_path,
            last_modified=last_modified,
            created_at=last_modified,
            source=Source(source.lower()),
            status=SessionStatus.IDLE,
            status_reason="idle",
            project_path="",
        )

        unified_events = orchestrator.get_events(unified_session)

        for unified_event in unified_events:
            legacy_event = unified_event_to_legacy(unified_event)
            if isinstance(legacy_event, ErrorEvent):
                errors.append(legacy_event)

    except Exception as e:
        logger.debug(f"Error extracting session errors: {e}")

    return errors
