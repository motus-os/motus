# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Generic action helpers for builder transcripts."""

from __future__ import annotations

from typing import Callable, Iterable, Optional

from .common_io import JsonDict


def find_last_action(
    items: Iterable[JsonDict], select_action: Callable[[JsonDict], Optional[str]]
) -> str:
    """Find the last action by scanning items in reverse-chronological order."""
    for item in items:
        action = select_action(item)
        if action:
            return action
    return ""


def detect_completion_marker(
    items: Iterable[JsonDict],
    *,
    is_tool_call: Callable[[JsonDict], bool],
    is_response_after_tool: Callable[[JsonDict], bool],
) -> bool:
    """Detect a completion marker: a response occurring after a tool call."""
    found_tool_call = False
    found_response_after_tool = False

    for item in items:
        if is_tool_call(item):
            found_tool_call = True
            if found_response_after_tool:
                return True
        elif found_tool_call and is_response_after_tool(item):
            found_response_after_tool = True

    return found_response_after_tool
