# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""
Motus Web UI - Health calculation utilities.

This module now contains only the calculate_health function.
Other functionality has been split into:
- app.py: FastAPI app and server
- routes.py: HTTP route handlers
- websocket.py: WebSocket handlers
- state.py: Session state management
- formatters.py: Event formatting
"""

from typing import Optional


def calculate_health(ctx: dict, drift_state: Optional[dict] = None) -> dict:
    """
    Pure Python health calculation. Zero dependencies.

    Returns health score (0-100) and status based on:
    - Error rate (errors hurt health)
    - Activity productivity (edits/writes vs reads)
    - Decision consistency
    - Tool efficiency
    """
    if not ctx:
        return {"health": 50, "status": "waiting", "metrics": {}, "drift": None}

    # Friction score: starts at 100, drops 15 per friction point (gentler)
    # Friction is normal - it's Claude working through challenges
    friction_count = ctx.get("friction_count", 0)
    friction_score = max(0, 100 - (friction_count * 15))

    # Activity score: productive tools (Edit, Write) vs total
    tools = ctx.get("tool_count", {})
    total_tools = sum(tools.values()) if tools else 0
    productive = tools.get("Edit", 0) + tools.get("Write", 0)
    read_heavy = tools.get("Read", 0) + tools.get("Glob", 0) + tools.get("Grep", 0)

    if total_tools == 0:
        activity_score = 50  # No activity yet
    elif productive > 0:
        activity_score = min(100, 60 + (productive * 8))  # Productive work
    elif read_heavy > 5:
        activity_score = 70  # Research phase, acceptable
    else:
        activity_score = 50

    # Progress score: files modified = progress
    files_modified = len(ctx.get("files_modified", []))
    progress_score = min(100, 40 + (files_modified * 15))

    # Decision score: having decisions = clarity
    decisions = ctx.get("decisions", [])
    decision_score = min(100, 50 + (len(decisions) * 10))

    # Weighted health calculation (friction matters less than before)
    health = int(
        friction_score * 0.20  # Friction is normal, lower weight
        + activity_score * 0.30  # Productivity matters more
        + progress_score * 0.30  # Actual progress matters more
        + decision_score * 0.20  # Clarity of intent
    )
    health = max(10, min(95, health))  # Clamp to 10-95

    # Status determination - use gentler language
    if friction_count > 3:
        status = "working_through_it"
    elif health >= 75:
        status = "on_track"
    elif health >= 50:
        status = "exploring"
    else:
        status = "needs_attention"

    drift_info = None
    _ = drift_state

    return {
        "health": health,
        "status": status,
        "drift": drift_info,
        "metrics": {
            "friction": friction_score,
            "activity": activity_score,
            "progress": progress_score,
            "decisions": decision_score,
        },
    }
