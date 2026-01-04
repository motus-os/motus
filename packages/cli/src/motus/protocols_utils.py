# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Utility functions operating over protocol models."""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal

from .protocols_enums import EventType, RiskLevel, SessionStatus
from .protocols_models import (
    DEFAULT_THRESHOLDS,
    SessionHealth,
    StatusThresholds,
    UnifiedEvent,
    UnifiedSession,
)


def compute_status(
    last_modified: datetime,
    now: datetime,
    last_action: str = "",
    has_completion: bool = True,
    thresholds: StatusThresholds = DEFAULT_THRESHOLDS,
) -> tuple[SessionStatus, str]:
    """
    Compute session status based on modification time.

    This is the UNIFORM status logic used by all sources.
    """
    age_seconds = (now - last_modified).total_seconds()

    # Check for crash first (1-5 min, risky op, no completion)
    if thresholds.crash_min_seconds < age_seconds < thresholds.crash_max_seconds:
        if last_action and any(k in last_action for k in ("Edit", "Write", "Bash")):
            if not has_completion:
                return (SessionStatus.CRASHED, f"Stopped during: {last_action}")

    # Standard status based on age
    if age_seconds < thresholds.active_seconds:
        return (SessionStatus.ACTIVE, "Modified within 2 minutes")
    elif age_seconds < thresholds.open_seconds:
        return (SessionStatus.OPEN, "Modified within 30 minutes")
    elif age_seconds < thresholds.idle_seconds:
        return (SessionStatus.IDLE, "Modified within 2 hours")
    else:
        return (SessionStatus.ORPHANED, "No recent activity")


def compute_health(
    session: UnifiedSession,
    events: List[UnifiedEvent],
) -> SessionHealth:
    """Compute health metrics for a session."""
    # Count event types
    tool_calls = sum(1 for e in events if e.event_type == EventType.TOOL)
    decisions = sum(1 for e in events if e.event_type == EventType.DECISION)
    files_modified = len(session.files_modified)
    thinking_blocks = sum(1 for e in events if e.event_type == EventType.THINKING)
    risky_operations = sum(
        1
        for e in events
        if e.event_type == EventType.TOOL and e.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
    )

    # Compute health score (simple heuristic)
    # Start at 100, deduct for issues
    score = 100

    # Deduct for too many risky operations
    if risky_operations > 5:
        score -= min(30, risky_operations * 3)

    # Deduct for stalled sessions
    if session.status == SessionStatus.CRASHED:
        score -= 40
    elif session.status == SessionStatus.ORPHANED:
        score -= 20
    elif session.age_seconds > 600:  # 10 min without activity
        score -= 10

    # Deduct for low productivity (few tool calls)
    if tool_calls < 3 and session.age_seconds > 300:
        score -= 10

    score = max(0, min(100, score))

    # Determine label
    if score >= 80:
        label: Literal["On Track", "Needs Attention", "At Risk", "Stalled"] = "On Track"
    elif score >= 60:
        label = "Needs Attention"
    elif score >= 40:
        label = "At Risk"
    else:
        label = "Stalled"

    # Working memory: recent files and decisions
    working_memory = []
    working_memory.extend(session.files_modified[-5:])
    recent_decisions = [e.decision_text for e in events if e.event_type == EventType.DECISION][-3:]
    working_memory.extend([d for d in recent_decisions if d])

    return SessionHealth(
        session_id=session.session_id,
        health_score=score,
        health_label=label,
        tool_calls=tool_calls,
        decisions=decisions,
        files_modified=files_modified,
        risky_operations=risky_operations,
        thinking_blocks=thinking_blocks,
        duration_seconds=int(session.age_seconds),
        last_activity_seconds=int(session.age_seconds),
        current_goal=session.working_on,
        working_memory=working_memory,
    )
