# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Protocol and shared behavior for ingestors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

from ..logging import get_logger
from ..protocols import (
    DEFAULT_THRESHOLDS,
    RawSession,
    SessionStatus,
    Source,
    StatusThresholds,
    UnifiedEvent,
)
from ..schema.events import ParsedEvent
from .base_helpers import (
    classify_risk,
    create_thinking_event,
    create_tool_event,
    extract_decisions_from_text,
    redact_tool_input,
    summarize_tool_input,
    validate_events,
)


class BaseBuilder(ABC):
    """Base class for all source ingestors."""

    def __init__(self, thresholds: StatusThresholds = DEFAULT_THRESHOLDS):
        self.thresholds = thresholds
        self._logger = get_logger(self.__class__.__name__)

    @property
    @abstractmethod
    def source_name(self) -> Source:
        """Return source identifier."""
        ...

    @abstractmethod
    def discover(self, max_age_hours: int = 24) -> List[RawSession]:
        """Find all sessions from this source within age limit."""
        ...

    @abstractmethod
    def parse_events(self, file_path: Path) -> List[UnifiedEvent]:
        """Parse transcript file into unified events."""
        ...

    def parse_line(self, raw_line: str, session_id: str) -> List[UnifiedEvent]:
        """Parse a single line of transcript into unified events."""
        return []

    def parse_events_validated(self, file_path: Path) -> List[ParsedEvent]:
        """Parse transcript into validated ParsedEvent instances."""
        return self._validate_events(self.parse_events(file_path))

    def parse_line_validated(self, raw_line: str, session_id: str) -> List[ParsedEvent]:
        """Parse a single line into validated ParsedEvent instances."""
        return self._validate_events(self.parse_line(raw_line, session_id))

    def _validate_events(self, events: List[UnifiedEvent]) -> List[ParsedEvent]:
        """Convert UnifiedEvents to ParsedEvents with validation."""
        return validate_events(events, self.source_name, self._logger)

    @abstractmethod
    def get_last_action(self, file_path: Path) -> str:
        """Get the last action from a session file."""
        ...

    @abstractmethod
    def has_completion_marker(self, file_path: Path) -> bool:
        """Check if session has a completion marker."""
        ...

    def compute_status(
        self,
        last_modified: datetime,
        now: datetime,
        last_action: str = "",
        has_completion: bool = True,
        project_path: str = "",
        running_projects: Optional[set] = None,
    ) -> tuple[SessionStatus, str]:
        """Compute session status based on modification time and process state."""
        age_seconds = (now - last_modified).total_seconds()

        has_running_process = False
        if running_projects is not None and project_path:
            has_running_process = project_path in running_projects or any(
                project_path in p for p in running_projects
            )

        if self.thresholds.crash_min_seconds < age_seconds < self.thresholds.crash_max_seconds:
            if last_action and any(k in last_action for k in ("Edit", "Write", "Bash")):
                if not has_completion:
                    return (SessionStatus.CRASHED, f"Stopped during: {last_action}")

        if age_seconds < self.thresholds.active_seconds:
            return (SessionStatus.ACTIVE, "Modified within 2 minutes")
        if age_seconds < self.thresholds.open_seconds:
            if has_running_process:
                return (SessionStatus.OPEN, "Process running, idle")
            return (SessionStatus.IDLE, "Modified within 30 minutes")
        if age_seconds < self.thresholds.idle_seconds:
            if has_running_process:
                return (SessionStatus.OPEN, "Process running, idle")
            return (SessionStatus.IDLE, "Modified within 2 hours")
        return (SessionStatus.ORPHANED, "No recent activity")

    def extract_thinking(self, file_path: Path) -> List[UnifiedEvent]:
        """Extract thinking/reasoning events."""
        return []

    def extract_decisions(self, file_path: Path) -> List[UnifiedEvent]:
        """Extract decision events from transcript."""
        return []

    def _extract_decisions_from_text(
        self,
        text: str,
        session_id: str,
        timestamp: Optional[datetime] = None,
    ) -> List[UnifiedEvent]:
        return extract_decisions_from_text(text, session_id, timestamp)

    def _create_thinking_event(
        self,
        content: str,
        session_id: str,
        timestamp: Optional[datetime] = None,
        model: Optional[str] = None,
    ) -> UnifiedEvent:
        return create_thinking_event(content, session_id, timestamp, model)

    def _create_tool_event(
        self,
        name: str,
        input_data: dict,
        session_id: str,
        timestamp: Optional[datetime] = None,
        output: Optional[str] = None,
        status: str = "success",
        risk_level=None,
        latency_ms: Optional[int] = None,
    ) -> UnifiedEvent:
        return create_tool_event(
            name,
            input_data,
            session_id,
            timestamp,
            output,
            status,
            risk_level,
            latency_ms,
            self._logger,
        )

    def _redact_tool_input(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return redact_tool_input(input_data)

    def _summarize_tool_input(self, name: str, input_data: dict) -> str:
        return summarize_tool_input(name, input_data)

    def _classify_risk(self, tool_name: str, input_data: dict) -> Any:
        return classify_risk(tool_name, input_data)
