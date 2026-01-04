# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Protocol enums used by ingestors, orchestrator, and UIs."""

from __future__ import annotations

from enum import Enum


class SessionStatus(str, Enum):
    """Session lifecycle status."""

    ACTIVE = "active"  # Modified within 2 minutes
    OPEN = "open"  # Modified within 30 minutes
    IDLE = "idle"  # Modified within 2 hours
    ORPHANED = "orphaned"  # No recent activity
    CRASHED = "crashed"  # Stopped during risky operation


class EventType(str, Enum):
    """Types of events that can occur in a session."""

    THINKING = "thinking"
    TOOL = "tool"
    TOOL_RESULT = "tool_result"
    DECISION = "decision"
    FILE_CHANGE = "file_change"
    FILE_READ = "file_read"
    FILE_MODIFIED = "file_modified"
    AGENT_SPAWN = "agent_spawn"
    ERROR = "error"
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    USER_MESSAGE = "user_message"
    RESPONSE = "response"


class RiskLevel(str, Enum):
    """Risk level for operations."""

    SAFE = "safe"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ToolStatus(str, Enum):
    """Status of a tool execution."""

    SUCCESS = "success"
    ERROR = "error"
    PENDING = "pending"
    CANCELLED = "cancelled"


class FileOperation(str, Enum):
    """Type of file operation."""

    READ = "read"
    WRITE = "write"
    EDIT = "edit"
    DELETE = "delete"


class Source(str, Enum):
    """Session source (which CLI/SDK created it)."""

    CLAUDE = "claude"
    CODEX = "codex"
    GEMINI = "gemini"
    SDK = "sdk"
