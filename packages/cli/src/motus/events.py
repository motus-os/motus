# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Lightweight event dataclasses for the tracer SDK and tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class ThinkingEvent:
    """Represents an AI thinking/reasoning block."""

    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    session_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict for this thinking event."""
        data: dict[str, Any] = {
            "type": "thinking",
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
        }
        if self.session_id:
            data["session_id"] = self.session_id
        return data


@dataclass
class ToolEvent:
    """Represents a tool call event."""

    name: str
    input: dict
    timestamp: datetime = field(default_factory=datetime.now)
    output: Any | None = None
    status: str = "success"
    risk_level: str = "safe"
    duration_ms: int | None = None
    session_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict for this tool event."""
        data: dict[str, Any] = {
            "type": "tool",
            "name": self.name,
            "input": self.input,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status,
            "risk_level": self.risk_level,
        }
        if self.output is not None:
            data["output"] = self.output
        if self.duration_ms is not None:
            data["duration_ms"] = self.duration_ms
        if self.session_id:
            data["session_id"] = self.session_id
        return data


@dataclass
class DecisionEvent:
    """Represents a decision event."""

    decision: str
    reasoning: str | None = None
    alternatives: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    session_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict for this decision event."""
        data: dict[str, Any] = {
            "type": "decision",
            "decision": self.decision,
            "reasoning": self.reasoning,
            "alternatives": self.alternatives,
            "timestamp": self.timestamp.isoformat(),
        }
        if self.session_id:
            data["session_id"] = self.session_id
        return data


@dataclass
class AgentSpawnEvent:
    """Represents a subagent spawn event."""

    agent_type: str
    description: str
    prompt: str = ""
    model: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    session_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict for this agent spawn event."""
        data: dict[str, Any] = {
            "type": "spawn",
            "agent_type": self.agent_type,
            "description": self.description,
            "prompt": self.prompt,
            "model": self.model,
            "timestamp": self.timestamp.isoformat(),
        }
        if self.session_id:
            data["session_id"] = self.session_id
        return data


@dataclass
class FileChangeEvent:
    """Represents a file change event."""

    path: str
    operation: str
    lines_added: int = 0
    lines_removed: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    session_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict for this file change event."""
        data: dict[str, Any] = {
            "type": "file_change",
            "path": self.path,
            "operation": self.operation,
            "lines_added": self.lines_added,
            "lines_removed": self.lines_removed,
            "timestamp": self.timestamp.isoformat(),
        }
        if self.session_id:
            data["session_id"] = self.session_id
        return data


__all__ = [
    "ThinkingEvent",
    "ToolEvent",
    "DecisionEvent",
    "AgentSpawnEvent",
    "FileChangeEvent",
]
