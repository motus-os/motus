# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Protocol dataclass definitions and thresholds."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Literal, Optional

from .protocols_enums import Source


@dataclass
class RawSession:
    """
    Raw session data before status computation.

    Builders return this from discover(), then compute_status() produces UnifiedSession.
    """

    session_id: str
    source: Source
    file_path: Path
    project_path: str
    last_modified: datetime
    size: int = 0
    created_at: Optional[datetime] = None


@dataclass
class SessionHealth:
    """
    Health metrics for a session.

    Powers CLI health widget and Web dashboard health indicators.
    """

    session_id: str

    health_score: int
    health_label: Literal["On Track", "Needs Attention", "At Risk", "Stalled"]

    tool_calls: int = 0
    decisions: int = 0
    files_modified: int = 0
    risky_operations: int = 0
    thinking_blocks: int = 0

    duration_seconds: int = 0
    last_activity_seconds: int = 0

    current_goal: str = ""
    working_memory: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "session_id": self.session_id,
            "health_score": self.health_score,
            "health_label": self.health_label,
            "tool_calls": self.tool_calls,
            "decisions": self.decisions,
            "files_modified": self.files_modified,
            "risky_operations": self.risky_operations,
            "thinking_blocks": self.thinking_blocks,
            "duration_seconds": self.duration_seconds,
            "last_activity_seconds": self.last_activity_seconds,
            "current_goal": self.current_goal,
            "working_memory": self.working_memory,
        }


@dataclass
class TeleportBundle:
    """
    Portable context for cross-session transfer.

    Used by `motus teleport` to transfer context between sessions/models.
    """

    source_session: str
    source_model: str
    timestamp: datetime

    intent: str
    decisions: List[str]
    files_touched: List[str]
    hot_files: List[str]
    pending_todos: List[str]
    last_action: str

    warnings: List[str] = field(default_factory=list)

    planning_docs: Dict[str, str] = field(default_factory=dict)

    def to_markdown(self) -> str:
        """Format as markdown for injection into target session."""
        lines = [
            f"## Context Teleported from Session {self.source_session[:8]}",
            "",
            f"**Original Task:** {self.intent}",
            f"**Model:** {self.source_model}",
            f"**Teleported:** {self.timestamp.strftime('%Y-%m-%d %H:%M')}",
            "",
        ]

        if self.decisions:
            lines.append("### Decisions Made")
            for d in self.decisions:
                lines.append(f"- {d}")
            lines.append("")

        if self.files_touched:
            lines.append("### Files Touched")
            for f in self.files_touched:
                lines.append(f"- {f}")
            lines.append("")

        if self.pending_todos:
            lines.append("### Pending Work")
            for t in self.pending_todos:
                lines.append(f"- [ ] {t}")
            lines.append("")

        if self.last_action:
            lines.append("### Last Action")
            lines.append(self.last_action)
            lines.append("")

        if self.warnings:
            for w in self.warnings:
                lines.append(f"⚠️ {w}")
            lines.append("")

        if self.planning_docs:
            lines.append("### Planning Context")
            lines.append("")
            for doc_name, content in sorted(self.planning_docs.items()):
                lines.append(f"#### {doc_name}")
                lines.append("")
                preview = content.strip()
                if len(preview) > 500:
                    preview = preview[:500] + "..."
                lines.append(preview)
                lines.append("")

        return "\n".join(lines)

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "source_session": self.source_session,
            "source_model": self.source_model,
            "timestamp": self.timestamp.isoformat(),
            "intent": self.intent,
            "decisions": self.decisions,
            "files_touched": self.files_touched,
            "hot_files": self.hot_files,
            "pending_todos": self.pending_todos,
            "last_action": self.last_action,
            "warnings": self.warnings,
            "planning_docs": self.planning_docs,
        }


@dataclass
class StatusThresholds:
    """
    Configurable thresholds for status assignment.

    All sources use the same thresholds for uniform behavior.
    """

    active_seconds: int = 120
    open_seconds: int = 1800
    idle_seconds: int = 7200
    crash_min_seconds: int = 60
    crash_max_seconds: int = 300


DEFAULT_THRESHOLDS = StatusThresholds()
