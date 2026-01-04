# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Compatibility shim for CLI output exports."""

from __future__ import annotations

from .output_converters import (
    get_last_error,
    get_session_errors,
    unified_event_to_legacy,
    unified_session_to_session_info,
)
from .output_types import (
    ErrorEvent,
    FileChange,
    SessionInfo,
    SessionStats,
    TaskEvent,
    ThinkingEvent,
    ToolEvent,
    console,
)

__all__ = [
    "ThinkingEvent",
    "ToolEvent",
    "TaskEvent",
    "ErrorEvent",
    "FileChange",
    "SessionStats",
    "SessionInfo",
    "unified_session_to_session_info",
    "unified_event_to_legacy",
    "get_last_error",
    "get_session_errors",
    "console",
]
