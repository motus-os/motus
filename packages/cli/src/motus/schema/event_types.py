# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Enums for event schema."""

from __future__ import annotations

from enum import Enum


class EventType(str, Enum):
    """Types of events that can occur in an AI coding session."""

    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    THINKING = "thinking"
    DECISION = "decision"
    AGENT_SPAWN = "agent_spawn"
    AGENT_RESULT = "agent_result"
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    USER_MESSAGE = "user_message"
    ASSISTANT_MESSAGE = "assistant_message"
    ERROR = "error"


class AgentSource(str, Enum):
    """Source AI agent that generated the event."""

    CLAUDE = "claude"
    CODEX = "codex"
    GEMINI = "gemini"
    UNKNOWN = "unknown"


class RiskLevel(str, Enum):
    """Risk level classification for tool operations."""

    SAFE = "safe"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ToolCategory(str, Enum):
    """Coarse classification of tool behavior."""

    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    NETWORK = "network"
    OTHER = "other"
