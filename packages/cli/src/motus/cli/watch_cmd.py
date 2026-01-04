# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Compatibility shim for watch command exports."""

from __future__ import annotations

import sys

from .exit_codes import EXIT_ERROR

try:
    from rich.console import Console
    from rich.rule import Rule
except ImportError:
    sys.stderr.write("Missing dependency: rich\n")
    sys.stderr.write("Run: pip install rich\n")
    raise SystemExit(EXIT_ERROR)

Rule = Rule
console = Console()

from .watch_cmd_core import watch_command, watch_session  # noqa: E402
from .watch_cmd_handlers import analyze_session, generate_agent_context  # noqa: E402

__all__ = [
    "analyze_session",
    "console",
    "generate_agent_context",
    "Rule",
    "watch_command",
    "watch_session",
]
