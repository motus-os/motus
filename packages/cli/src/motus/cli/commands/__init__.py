# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Command implementations for CLI (list, context, summary, teleport, etc).

PERFORMANCE: Rich and other heavy imports deferred to function level.
"""

import sys

from ..exit_codes import EXIT_ERROR
from .commands_context import context_command
from .commands_session import list_sessions, summary_command, teleport_command

_console = None


def _get_console():
    """Get or create Rich console instance."""
    global _console
    if _console is None:
        try:
            from rich.console import Console

            _console = Console()
        except ImportError:
            sys.stderr.write("Missing dependency: rich\n")
            sys.stderr.write("Run: pip install rich\n")
            raise SystemExit(EXIT_ERROR)
    return _console


__all__ = [
    "context_command",
    "summary_command",
    "teleport_command",
    "list_sessions",
]
