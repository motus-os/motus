# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Core protocol dataclasses used across ingestors and surfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .protocols_enums import (
    EventType,
    FileOperation,
    RiskLevel,
    SessionStatus,
    Source,
    ToolStatus,
)


@dataclass
class UnifiedEvent:
    """
    Source-agnostic event representation.

    This is what all ingestors produce and all surfaces consume.
    Each event has a type and common fields, plus type-specific optional fields.
    """

    event_id: str
    session_id: str
    timestamp: datetime

    event_type: EventType

    content: str
    raw_data: Dict = field(default_factory=dict)

    tool_name: Optional[str] = None
    tool_input: Optional[Dict] = None
    tool_output: Optional[str] = None
    tool_use_id: Optional[str] = None
    tool_status: Optional[ToolStatus] = None
    risk_level: Optional[RiskLevel] = None
    tool_latency_ms: Optional[int] = None

    decision_text: Optional[str] = None
    reasoning: Optional[str] = None
    files_affected: List[str] = field(default_factory=list)

    file_path: Optional[str] = None
    file_operation: Optional[FileOperation] = None
    lines_added: int = 0
    lines_removed: int = 0

    agent_type: Optional[str] = None
    agent_description: Optional[str] = None
    agent_prompt: Optional[str] = None
    agent_model: Optional[str] = None
    parent_event_id: Optional[str] = None
    agent_depth: int = 0

    model: Optional[str] = None
    tokens_used: Optional[int] = None
    cache_hit: Optional[bool] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "event_id": self.event_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type.value,
            "content": self.content,
            "raw_data": self.raw_data,
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
            "tool_output": self.tool_output,
            "tool_use_id": self.tool_use_id,
            "tool_status": self.tool_status.value if self.tool_status else None,
            "risk_level": self.risk_level.value if self.risk_level else None,
            "tool_latency_ms": self.tool_latency_ms,
            "decision_text": self.decision_text,
            "reasoning": self.reasoning,
            "files_affected": self.files_affected,
            "file_path": self.file_path,
            "file_operation": self.file_operation.value if self.file_operation else None,
            "lines_added": self.lines_added,
            "lines_removed": self.lines_removed,
            "agent_type": self.agent_type,
            "agent_description": self.agent_description,
            "agent_prompt": self.agent_prompt,
            "agent_model": self.agent_model,
            "parent_event_id": self.parent_event_id,
            "agent_depth": self.agent_depth,
            "model": self.model,
            "tokens_used": self.tokens_used,
            "cache_hit": self.cache_hit,
        }


@dataclass
class UnifiedSession:
    """
    Source-agnostic session representation.

    This is what all ingestors produce and all surfaces consume.
    """

    session_id: str
    source: Source
    file_path: Path
    project_path: str

    created_at: datetime
    last_modified: datetime

    status: SessionStatus
    status_reason: str

    file_size_bytes: int = 0

    event_count: int = 0
    tool_count: int = 0
    decision_count: int = 0
    file_change_count: int = 0
    thinking_count: int = 0

    last_action: str = ""
    working_on: str = ""

    parent_event_id: Optional[str] = None
    agent_depth: int = 0

    files_read: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)

    @property
    def is_active(self) -> bool:
        """Convenience property for backwards compatibility."""
        return self.status == SessionStatus.ACTIVE

    @property
    def age_seconds(self) -> float:
        """Seconds since last modification."""
        from . import protocols_models as _protocols_models

        return (_protocols_models.datetime.now() - self.last_modified).total_seconds()

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "session_id": self.session_id,
            "source": self.source.value,
            "file_path": str(self.file_path),
            "project_path": self.project_path,
            "file_size_bytes": self.file_size_bytes,
            "created_at": self.created_at.isoformat(),
            "last_modified": self.last_modified.isoformat(),
            "status": self.status.value,
            "status_reason": self.status_reason,
            "event_count": self.event_count,
            "tool_count": self.tool_count,
            "decision_count": self.decision_count,
            "file_change_count": self.file_change_count,
            "thinking_count": self.thinking_count,
            "last_action": self.last_action,
            "working_on": self.working_on,
            "parent_event_id": self.parent_event_id,
            "agent_depth": self.agent_depth,
            "files_read": self.files_read,
            "files_modified": self.files_modified,
            "is_active": self.is_active,
            "age_seconds": self.age_seconds,
        }
