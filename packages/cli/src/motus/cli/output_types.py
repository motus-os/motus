# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Output data structures for CLI."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    from rich.console import Console
except ImportError:
    Console = None  # type: ignore[assignment,misc]

console = Console() if Console else None


@dataclass
class ThinkingEvent:
    content: str
    timestamp: datetime


@dataclass
class ToolEvent:
    name: str
    input: dict
    timestamp: datetime
    status: str = "running"
    output: Optional[str] = None
    risk_level: str = "safe"


@dataclass
class TaskEvent:
    """Rich Task/subagent event with full details."""

    description: str
    prompt: str
    subagent_type: str
    model: Optional[str]
    timestamp: datetime


@dataclass
class ErrorEvent:
    """Represents an error during session execution."""

    message: str
    timestamp: datetime
    error_type: str = "unknown"  # "tool_error", "api_error", "safety", "parse_error"
    tool_name: Optional[str] = None  # Tool that caused error, if applicable
    recoverable: bool = True


@dataclass
class FileChange:
    """Track file modifications for checkpoint awareness."""

    path: str
    operation: str
    timestamp: datetime


@dataclass
class SessionStats:
    """Track session statistics."""

    thinking_count: int = 0
    tool_count: int = 0
    agent_count: int = 0
    error_count: int = 0
    files_modified: set = field(default_factory=set)
    high_risk_ops: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    errors: list = field(default_factory=list)


@dataclass
class SessionInfo:
    session_id: str
    file_path: Path
    last_modified: datetime
    size: int
    is_active: bool = False
    project_path: str = ""  # Actual project path
    status: str = "idle"  # active, idle, crashed
    last_action: str = ""  # Last tool/action for crash recovery
    source: str = "claude"  # "claude", "codex", "gemini", "sdk"
