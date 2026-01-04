# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Pydantic models for events."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from ..policy.forensics_boundary import apply_forensics_boundary
from .event_types import AgentSource, EventType, RiskLevel


def _generate_event_id() -> str:
    return str(uuid4())


class ToolUseData(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")
    tool_name: str = Field(min_length=1, description="Tool name")
    tool_input: dict[str, Any] | str | None = Field(default=None, description="Tool input payload")
    tool_output: str | None = Field(default=None, description="Tool output")
    tool_use_id: str | None = Field(default=None, description="Tool use identifier")
    tool_status: str | None = Field(default=None, description="Tool status")
    tool_latency_ms: int | None = Field(default=None, description="Tool execution time in milliseconds")


class ThinkingData(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")
    content: str = Field(default="", description="Thinking content")
    reasoning: str | None = Field(default=None, description="Reasoning text")


class ParsedEvent(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", validate_default=True)
    event_id: str = Field(min_length=1, description="Unique identifier for this event")
    session_id: str = Field(min_length=1, description="Session this event belongs to")
    event_type: EventType = Field(description="Category of event")
    source: AgentSource = Field(description="AI agent that produced this event")
    timestamp: datetime = Field(description="When the event occurred")
    model: str | None = Field(default=None, description="AI model that generated this event")
    risk_level: RiskLevel = Field(default=RiskLevel.SAFE, description="Risk level for UI color coding")
    content: str = Field(default="", description="Human-readable description or content")
    tool_name: str | None = Field(default=None, description="Name of tool if TOOL_USE/TOOL_RESULT")
    tool_input: dict[str, Any] | str | None = Field(
        default=None, description="Input parameters to tool (dict or JSON string)"
    )
    tool_output: str | None = Field(default=None, description="Output from tool execution")
    tool_use_id: str | None = Field(default=None, description="Unique ID linking tool_use to tool_result")
    tool_status: str | None = Field(
        default=None, description="Status of tool execution: success, error, pending, cancelled"
    )
    tool_latency_ms: int | None = Field(default=None, description="Tool execution time in milliseconds")
    file_path: str | None = Field(default=None, description="File path if event involves a file")
    file_operation: str | None = Field(
        default=None, description="Type of file operation: read, write, edit, delete"
    )
    lines_added: int = Field(default=0, description="Lines added in file modification")
    lines_removed: int = Field(default=0, description="Lines removed in file modification")
    files_affected: list[str] = Field(default_factory=list, description="List of files affected by this event")
    decision_text: str | None = Field(default=None, description="Text of decision made")
    reasoning: str | None = Field(default=None, description="Reasoning behind decision")
    spawn_type: str | None = Field(default=None, description="Type of spawned agent if AGENT_SPAWN")
    spawn_prompt: str | None = Field(default=None, description="Prompt given to spawned agent")
    spawn_model: str | None = Field(default=None, description="Model used by spawned agent")
    agent_description: str | None = Field(default=None, description="Description of spawned agent")
    tokens_used: int | None = Field(default=None, description="Number of tokens used in this event")
    cache_hit: bool | None = Field(default=None, description="Whether this event was served from cache")
    is_error: bool = Field(default=False, description="Whether this event represents an error")
    error_message: str | None = Field(default=None, description="Error message if is_error=True")
    raw_data: dict[str, Any] | None = Field(default=None, description="Original unparsed data for debugging")

    def to_dict(self) -> dict[str, Any]:
        data = self.model_dump()
        data["timestamp"] = self.timestamp.isoformat()
        data["event_type"] = self.event_type.value
        data["source"] = self.source.value
        data["risk_level"] = self.risk_level.value
        return data

    def short_id(self) -> str:
        return self.event_id[:8] if len(self.event_id) > 8 else self.event_id


def unified_to_parsed(event: Any, source: AgentSource = AgentSource.UNKNOWN) -> ParsedEvent | None:
    from ..protocols import EventType as ProtocolEventType
    from ..protocols import RiskLevel as ProtocolRiskLevel

    try:
        event_type_map = {
            ProtocolEventType.THINKING: EventType.THINKING,
            ProtocolEventType.TOOL: EventType.TOOL_USE,
            ProtocolEventType.TOOL_RESULT: EventType.TOOL_RESULT,
            ProtocolEventType.DECISION: EventType.DECISION,
            ProtocolEventType.AGENT_SPAWN: EventType.AGENT_SPAWN,
            ProtocolEventType.ERROR: EventType.ERROR,
            ProtocolEventType.SESSION_START: EventType.SESSION_START,
            ProtocolEventType.SESSION_END: EventType.SESSION_END,
            ProtocolEventType.USER_MESSAGE: EventType.USER_MESSAGE,
            ProtocolEventType.RESPONSE: EventType.ASSISTANT_MESSAGE,
            ProtocolEventType.FILE_CHANGE: EventType.TOOL_USE,
            ProtocolEventType.FILE_READ: EventType.TOOL_USE,
            ProtocolEventType.FILE_MODIFIED: EventType.TOOL_USE,
        }
        risk_level_map = {
            ProtocolRiskLevel.SAFE: RiskLevel.SAFE,
            ProtocolRiskLevel.MEDIUM: RiskLevel.MEDIUM,
            ProtocolRiskLevel.HIGH: RiskLevel.HIGH,
            ProtocolRiskLevel.CRITICAL: RiskLevel.CRITICAL,
        }
        proto_event_type = getattr(event, "event_type", None)
        schema_event_type = event_type_map.get(proto_event_type, EventType.THINKING)
        proto_risk = getattr(event, "risk_level", None)
        schema_risk = risk_level_map.get(proto_risk, RiskLevel.SAFE) if proto_risk else RiskLevel.SAFE
        raw_data = apply_forensics_boundary(getattr(event, "raw_data", None))
        return ParsedEvent(
            event_id=str(getattr(event, "event_id", "")),
            session_id=str(getattr(event, "session_id", "")),
            event_type=schema_event_type,
            source=source,
            timestamp=getattr(event, "timestamp", datetime.now()),
            model=getattr(event, "model", None),
            risk_level=schema_risk,
            content=str(getattr(event, "content", "")),
            tool_name=getattr(event, "tool_name", None),
            tool_input=getattr(event, "tool_input", None),
            tool_output=getattr(event, "tool_output", None),
            tool_status=(
                getattr(event, "tool_status", None).value if getattr(event, "tool_status", None) else None
            ),
            tool_latency_ms=getattr(event, "tool_latency_ms", None),
            file_path=getattr(event, "file_path", None),
            file_operation=(
                getattr(event, "file_operation", None).value if getattr(event, "file_operation", None) else None
            ),
            lines_added=getattr(event, "lines_added", 0),
            lines_removed=getattr(event, "lines_removed", 0),
            files_affected=getattr(event, "files_affected", []),
            decision_text=getattr(event, "decision_text", None),
            reasoning=getattr(event, "reasoning", None),
            spawn_type=getattr(event, "agent_type", None),
            spawn_prompt=getattr(event, "agent_prompt", None),
            spawn_model=getattr(event, "agent_model", None),
            agent_description=getattr(event, "agent_description", None),
            tokens_used=getattr(event, "tokens_used", None),
            cache_hit=getattr(event, "cache_hit", None),
            is_error=getattr(event, "event_type", None) == ProtocolEventType.ERROR,
            raw_data=raw_data,
        )
    except Exception as e:
        from ..logging import get_logger

        logger = get_logger(__name__)
        logger.debug(f"Failed to convert UnifiedEvent to ParsedEvent: {e}")
        return None


class SessionInfo(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")
    session_id: str = Field(min_length=1, description="Unique session identifier")
    source: AgentSource = Field(description="AI agent that ran this session")
    project_path: str = Field(default="", description="Working directory for the session")
    start_time: datetime | None = Field(default=None, description="When the session started")
    end_time: datetime | None = Field(default=None, description="When the session ended")
    last_event_time: datetime | None = Field(default=None, description="Timestamp of most recent event")
    event_count: int = Field(default=0, ge=0, description="Number of events in the session")
    is_active: bool = Field(default=False, description="Whether session is still running")
    model: str | None = Field(default=None, description="AI model used in session")
    size_bytes: int = Field(default=0, ge=0, description="Approximate size of session data")

    def to_dict(self) -> dict[str, Any]:
        data = self.model_dump()
        data["source"] = self.source.value
        if self.start_time:
            data["start_time"] = self.start_time.isoformat()
        if self.end_time:
            data["end_time"] = self.end_time.isoformat()
        if self.last_event_time:
            data["last_event_time"] = self.last_event_time.isoformat()
        return data

    def short_id(self) -> str:
        return self.session_id[:8] if len(self.session_id) > 8 else self.session_id
