# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Shared utilities for CLI commands."""

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from ..schema.events import RiskLevel
from .models import (
    DESTRUCTIVE_PATTERNS,
    RISK_LEVELS,
    SENSITIVE_PATTERNS,
    TaskEvent,
    ThinkingEvent,
    ToolEvent,
)

# Common secret patterns to redact
SECRET_PATTERNS = [
    (r"sk-[a-zA-Z0-9]{20,}", "[REDACTED_OPENAI_KEY]"),
    (r"sk-or-[a-zA-Z0-9-]{20,}", "[REDACTED_OPENROUTER_KEY]"),
    (r"ghp_[a-zA-Z0-9]{36}", "[REDACTED_GITHUB_TOKEN]"),
    (r"gho_[a-zA-Z0-9]{36}", "[REDACTED_GITHUB_OAUTH]"),
    (r"AKIA[0-9A-Z]{16}", "[REDACTED_AWS_KEY]"),
    (r"xox[baprs]-[a-zA-Z0-9-]{10,}", "[REDACTED_SLACK_TOKEN]"),
    (r"eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*", "[REDACTED_JWT]"),
    (r'(?i)password[\s]*[=:]\s*["\']?[^\s"\']+', "password=[REDACTED]"),
    (r'(?i)api[_-]?key[\s]*[=:]\s*["\']?[^\s"\']+', "api_key=[REDACTED]"),
    (r'(?i)secret[\s]*[=:]\s*["\']?[^\s"\']+', "secret=[REDACTED]"),
    (r'(?i)token[\s]*[=:]\s*["\']?[a-zA-Z0-9_-]{20,}', "token=[REDACTED]"),
]


def redact_secrets(text: str) -> str:
    """Redact common secret patterns from text.

    This prevents accidental exposure of API keys, tokens, and passwords
    in the dashboard, summaries, and exports.
    """
    if not text:
        return text

    result = text
    for pattern, replacement in SECRET_PATTERNS:
        result = re.sub(pattern, replacement, result)
    return result


def assess_risk(tool_name: str, tool_input: dict) -> RiskLevel:
    """Assess risk level of an operation.

    Returns: RiskLevel enum (SAFE, MEDIUM, HIGH, or CRITICAL)
    """
    base_risk = RISK_LEVELS.get(tool_name, RiskLevel.SAFE)

    # Check for destructive bash commands
    if tool_name == "Bash":
        command = tool_input.get("command", "").lower()
        for pattern in DESTRUCTIVE_PATTERNS:
            if pattern in command:
                return RiskLevel.CRITICAL

    # Check for sensitive file paths in Write/Edit operations
    if tool_name in ("Write", "Edit"):
        file_path = tool_input.get("file_path", "").lower()
        for sensitive in SENSITIVE_PATTERNS:
            if sensitive in file_path:
                return RiskLevel.HIGH

    return base_risk


def extract_project_path(project_dir_name: str, truncate: bool = False) -> str:
    """Extract actual project path from Claude's encoded directory name.

    Handles both formats:
    - With session ID: abc123-home-user-projects-project
    - Leading dash: -home-user-projects-project

    Security: Validates path to prevent traversal attacks.

    Args:
        project_dir_name: The encoded directory name
        truncate: If True, return only last 2 path components for display

    Returns:
        Full path like /home/user/projects/project, or truncated like projects/project
    """
    if not project_dir_name:
        return ""

    # Security: Reject excessively long paths (max 4096 chars)
    if len(project_dir_name) > 4096:
        return ""

    # Security: Reject paths containing null bytes
    if "\0" in project_dir_name:
        return ""

    # Security: Reject any input containing path traversal sequences
    if ".." in project_dir_name:
        return ""

    # Handle leading dash format: -home-user-projects-project
    if project_dir_name.startswith("-"):
        # Validate format: session IDs should be alphanumeric with hyphens
        # Skip first char (the leading dash) and check rest
        if not all(c.isalnum() or c in ("-", "_") for c in project_dir_name[1:]):
            return ""
        full_path = "/" + project_dir_name[1:].replace("-", "/")
    else:
        # Handle session ID prefix format: abc123-home-user-projects-project
        parts = project_dir_name.split("-")
        if len(parts) <= 1:
            return project_dir_name

        # Validate session ID format (first part should be alphanumeric)
        if parts[0] and not parts[0].isalnum():
            return ""

        # Check if the second part is a known root path indicator
        # If not, this is likely a plain name like "my-project", return as-is
        if len(parts) > 1 and parts[1] not in ("Users", "home", "var", "tmp"):
            return project_dir_name

        # Skip the session ID prefix (first part)
        path_parts = parts[1:]

        # Reconstruct path
        full_path = "/" + "/".join(path_parts)

    # Security: Normalize path and verify no traversal occurred
    try:
        resolved = Path(full_path).resolve()
        # Verify the resolved path still starts with expected prefix
        # (resolve() would have expanded any .. sequences)
        resolved_str = str(resolved)
        if not resolved_str.startswith("/"):
            return ""
        full_path = resolved_str
    except (ValueError, RuntimeError, OSError):
        return ""

    if truncate:
        path_split = full_path.split("/")
        if len(path_split) > 3:
            return "/".join(path_split[-2:])

    return full_path


def format_age(modified: datetime) -> str:
    """Format age of a session in human-readable form."""
    age = datetime.now() - modified

    if age < timedelta(minutes=1):
        return "just now"
    elif age < timedelta(hours=1):
        minutes = int(age.total_seconds() / 60)
        return f"{minutes}m ago"
    elif age < timedelta(days=1):
        hours = int(age.total_seconds() / 3600)
        return f"{hours}h ago"
    else:
        days = age.days
        return f"{days}d ago"


def parse_content_block(block: dict) -> Optional[ThinkingEvent | ToolEvent | TaskEvent]:
    """Parse a content block from Claude's transcript."""
    block_type = block.get("type")

    if block_type == "thinking":
        return ThinkingEvent(content=block.get("thinking", ""), timestamp=datetime.now())

    if block_type == "tool_use":
        tool_input = block.get("input", {})
        tool_name = block.get("name", "unknown")

        # Check for Task/subagent
        if tool_name == "Task":
            return TaskEvent(
                description=tool_input.get("description", ""),
                prompt=tool_input.get("prompt", ""),  # Full prompt - no truncation
                subagent_type=tool_input.get("subagent_type", ""),
                model=tool_input.get("model"),
                timestamp=datetime.now(),
            )

        return ToolEvent(
            name=tool_name,
            input=tool_input,
            timestamp=datetime.now(),
            risk_level=assess_risk(tool_name, tool_input),
        )

    return None


def get_risk_style(risk_level: RiskLevel | str) -> tuple[str, str]:
    """Get color and icon for risk level.

    Args:
        risk_level: RiskLevel enum or string representation

    Returns:
        Tuple of (color, icon)
    """
    # Convert RiskLevel enum to string value if needed
    if isinstance(risk_level, RiskLevel):
        risk_str = risk_level.value
    else:
        risk_str = risk_level

    styles = {
        "critical": ("red", "⚠️"),
        "high": ("red", "⚠️"),
        "medium": ("yellow", "⚡"),
        "safe": ("green", "✓"),
    }
    return styles.get(risk_str, ("white", "•"))
