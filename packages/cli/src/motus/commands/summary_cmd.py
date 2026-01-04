# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Compatibility shim for summary command exports."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.markup import escape

from .list_cmd import find_active_session, find_sessions
from .summary_cmd_core import (
    _process_claude_event,
    _process_codex_event,
    _process_gemini_message,
    analyze_session,
    generate_agent_context,
    summary_command,
)
from .summary_cmd_formatters import (
    DECISION_MARKERS,
    _extract_decision_from_text,
    extract_decisions,
)

try:
    from ..config import MC_STATE_DIR
except ImportError:
    MC_STATE_DIR = Path.home() / ".mc"

console = Console()

__all__ = [
    "DECISION_MARKERS",
    "MC_STATE_DIR",
    "_extract_decision_from_text",
    "_process_claude_event",
    "_process_codex_event",
    "_process_gemini_message",
    "analyze_session",
    "extract_decisions",
    "escape",
    "find_active_session",
    "find_sessions",
    "generate_agent_context",
    "summary_command",
]
