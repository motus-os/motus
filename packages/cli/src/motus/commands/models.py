# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Shared models for CLI commands."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..schema.events import RiskLevel


@dataclass
class ThinkingEvent:
    """Represents an AI thinking/reasoning block."""

    content: str
    timestamp: datetime


@dataclass
class ToolEvent:
    """Represents a tool call event."""

    name: str
    input: dict
    timestamp: datetime
    status: str = "running"
    output: Optional[str] = None
    risk_level: RiskLevel | str = RiskLevel.SAFE


@dataclass
class TaskEvent:
    """Rich Task/subagent event with full details."""

    description: str
    prompt: str
    subagent_type: str
    model: Optional[str]
    timestamp: datetime


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
    """Information about a Claude/Codex session."""

    session_id: str
    file_path: Path
    last_modified: datetime
    size: int
    is_active: bool = False
    project_path: str = ""
    status: str = "idle"  # active, idle, crashed
    last_action: str = ""
    source: str = "claude"  # claude, codex, sdk


# Risk levels for operations
RISK_LEVELS = {
    "Write": RiskLevel.MEDIUM,
    "Edit": RiskLevel.MEDIUM,
    "Bash": RiskLevel.HIGH,
    "Task": RiskLevel.SAFE,
    "Read": RiskLevel.SAFE,
    "Glob": RiskLevel.SAFE,
    "Grep": RiskLevel.SAFE,
    "WebFetch": RiskLevel.SAFE,
    "WebSearch": RiskLevel.SAFE,
    "TodoWrite": RiskLevel.SAFE,
}

# High-risk bash patterns
DESTRUCTIVE_PATTERNS = [
    "rm ",
    "rm -",
    "rmdir",
    "delete",
    "drop ",
    "truncate",
    "git reset --hard",
    "git clean",
    "force push",
    "--force",
    "sudo",
    "chmod 777",
    "> /dev/",
    "mkfs",
    "dd if=",
]

# Sensitive file path patterns
SENSITIVE_PATTERNS = [
    ".env",
    "credentials",
    "secret",
    "password",
    "key",
    ".git/",
]
