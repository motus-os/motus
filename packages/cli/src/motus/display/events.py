# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Display-ready dataclasses for Motus.

All string fields are PRE-ESCAPED and safe to render directly.
Consumers should never need to escape these values.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class DisplayRiskLevel(Enum):
    """Risk level classification for display events."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class DisplayEvent:
    """Pre-escaped, display-ready event. ALL strings safe to render.

    Attributes:
        event_id: Unique event identifier
        session_id: Full session identifier
        short_session_id: First 8 characters of session_id
        timestamp_display: Human-readable timestamp (e.g., "14:32:45")
        event_type: Event classification (e.g., "thinking", "tool_use", "agent_spawn")
        risk_level: Risk assessment for this event
        icon: Display icon for the event (pre-escaped)
        title: Event title (pre-escaped)
        details: List of detail lines (all pre-escaped)
        tool_name: Tool name if tool_use event (pre-escaped)
        file_path: File path if applicable (pre-escaped)
        parent_event_id: Parent event for subagent hierarchy
        is_subagent: Whether this event is from a subagent
        subagent_depth: Nesting depth in agent hierarchy (0 = root)
        full_content: Full untruncated content (pre-escaped, for expand/collapse)
    """

    # Identity
    event_id: str
    session_id: str
    short_session_id: str

    # Timing
    timestamp_display: str

    # Classification
    event_type: str
    risk_level: DisplayRiskLevel

    # Content (ALL PRE-ESCAPED)
    icon: str
    title: str
    details: List[str]

    # Tool-specific (optional)
    tool_name: Optional[str] = None
    file_path: Optional[str] = None

    # Agent hierarchy
    parent_event_id: Optional[str] = None
    is_subagent: bool = False
    subagent_depth: int = 0

    # Expandable content
    full_content: Optional[str] = None
    content: Optional[str] = None  # General content field (pre-escaped)
    raw_data: Optional[dict] = None  # Raw event data for special handling


@dataclass(frozen=True)
class DisplaySession:
    """Pre-escaped, display-ready session.

    Attributes:
        session_id: Full session identifier
        short_id: First 8 characters of session_id
        source: Session source identifier (e.g., "claude", "codex", "gemini")
        source_icon: Icon representing the source (pre-escaped)
        status: Current session status (e.g., "active", "idle", "crashed")
        status_icon: Icon representing the status (pre-escaped)
        project_path: Full project path (pre-escaped)
        project_name: Last component of project path (pre-escaped)
        event_count: Total number of events in this session
        health_score: Session health from 0-100
        time_ago: Human-readable time since last activity (e.g., "2m", "1h", "3d")
    """

    session_id: str
    short_id: str
    source: str
    source_icon: str
    status: str
    status_icon: str
    project_path: str
    project_name: str
    event_count: int
    health_score: int
    time_ago: str = ""
