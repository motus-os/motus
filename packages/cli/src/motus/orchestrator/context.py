# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""
Context aggregation for session analysis.

This module provides utilities for extracting and aggregating
context information from session events.
"""

from collections import Counter
from pathlib import Path
from typing import Dict, List, Set

from ..protocols import EventType, UnifiedEvent

__all__ = ["aggregate_context"]


def aggregate_context(events: List[UnifiedEvent]) -> Dict:
    """
    Get aggregated context from a list of events.

    Analyzes events to extract:
    - Files read/modified
    - Decisions made
    - Tool usage patterns
    - Thinking summaries

    Args:
        events: List of UnifiedEvent objects to analyze.

    Returns:
        Dict containing:
        - files_read: List of files read
        - files_modified: List of files modified
        - decisions: List of decisions made
        - tool_counts: Counter of tool usage
        - thinking_summaries: Recent thinking content
    """
    files_read: Set[str] = set()
    files_modified: Set[str] = set()
    decisions: List[str] = []
    tool_counts: Counter = Counter()
    thinking: List[str] = []

    for event in events:
        if event.event_type == EventType.FILE_READ and event.file_path:
            files_read.add(Path(event.file_path).name)
        elif event.event_type == EventType.FILE_MODIFIED and event.file_path:
            files_modified.add(Path(event.file_path).name)
        elif event.event_type == EventType.DECISION and event.decision_text:
            decisions.append(event.decision_text)
        elif event.event_type == EventType.TOOL and event.tool_name:
            tool_counts[event.tool_name] += 1
        elif event.event_type == EventType.THINKING:
            thinking.append(event.content[:200])

    return {
        "files_read": sorted(files_read),
        "files_modified": sorted(files_modified),
        "decisions": decisions[-10:],  # Last 10 decisions
        "tool_counts": dict(tool_counts.most_common(10)),
        "thinking_summaries": thinking[-5:],  # Last 5 thinking blocks
    }
