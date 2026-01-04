# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Entry point, argument parsing, and command dispatch for CLI."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from types import ModuleType
from typing import Optional

from rich.console import Console

try:
    from ..logging import get_logger

    logger = get_logger(__name__)
except ImportError:
    import logging

    logger = logging.getLogger(__name__)  # type: ignore[assignment]

from ..config import ARCHIVE_DIR, MC_STATE_DIR
from .commands.dispatch import dispatch_command
from .commands.registry import build_parser
from .help import compute_visible_help_tier, first_command_token, print_top_level_help
from .session_utils import (
    archive_session as _archive_session,
)
from .session_utils import (
    delete_session as _delete_session,
)
from .session_utils import (
    find_active_session as _find_active_session,
)
from .session_utils import (
    find_sdk_traces as _find_sdk_traces,
)
from .session_utils import (
    find_sessions as _find_sessions,
)
from .session_utils import (
    get_running_claude_projects as _get_running_claude_projects,
)
from .session_utils import (
    is_claude_process_running as _is_claude_process_running,
)

# Ensure directories exist
MC_STATE_DIR.mkdir(exist_ok=True)
ARCHIVE_DIR.mkdir(exist_ok=True)

# Rich console instances
console = Console()
error_console = Console(stderr=True)

# Lazy import of orchestrator to avoid circular imports
_orchestrator_module: Optional[ModuleType] = None
_protocols_module: Optional[ModuleType] = None


def _get_orchestrator():
    """Lazy import of orchestrator to get the singleton instance."""
    global _orchestrator_module
    if _orchestrator_module is None:
        try:
            from .. import orchestrator as _orch

            _orchestrator_module = _orch
        except ImportError:
            return None
    return _orchestrator_module.get_orchestrator()


def _get_protocol_types():
    """Lazy import of protocol types for type comparisons."""
    global _protocols_module
    if _protocols_module is None:
        try:
            from .. import protocols as _proto

            _protocols_module = _proto
        except ImportError:
            return None
    return _protocols_module


# For backward compatibility, import these if possible (but don't fail)
try:
    from ..orchestrator import get_orchestrator
    from ..protocols import EventType, UnifiedEvent, UnifiedSession
except ImportError:
    # Set to None - functions that need these should use _get_orchestrator() and _get_protocol_types()
    get_orchestrator = None  # type: ignore[assignment,misc]
    EventType = None  # type: ignore[assignment,misc]
    UnifiedEvent = None  # type: ignore[assignment,misc]
    UnifiedSession = None  # type: ignore[assignment,misc]


def is_claude_process_running(project_path: str = "") -> bool:
    """Check if a Claude Code process is actively running."""
    return _is_claude_process_running(project_path)


def archive_session(session_file: Path) -> bool:
    """Archive a session file to Motus state directory archive."""
    return _archive_session(
        session_file,
        archive_dir=ARCHIVE_DIR,
        move=shutil.move,
        logger=logger,
    )


def delete_session(session_file: Path) -> bool:
    """Permanently delete a session file."""
    return _delete_session(session_file, logger=logger)


def get_running_claude_projects() -> set[str]:
    """Get project paths where Claude processes are currently running."""
    return _get_running_claude_projects()


def find_sessions(max_age_hours: int = 2):
    """Find recent sessions from all sources (Claude, Codex, Gemini, SDK)."""
    return _find_sessions(max_age_hours=max_age_hours)


# Backward compatibility alias
find_claude_sessions = find_sessions


def find_active_session():
    """Find the most recently active session from any source."""
    return _find_active_session()


def find_sdk_traces() -> list[dict]:
    """Find SDK trace files."""
    return _find_sdk_traces(MC_STATE_DIR)


# PERFORMANCE: Commands loaded lazily on first use
# Module-level names exist for test compatibility but imports are deferred


def list_sessions(args=None):
    """Lazy wrapper for list command."""
    from ..commands.list_cmd import list_sessions as _list_sessions

    fast = bool(getattr(args, "fast", False)) if args is not None else False
    return _list_sessions(fast=fast)


def summary_command(session_id=None):
    """Lazy wrapper for summary command."""
    from .commands import summary_command as _summary_command

    return _summary_command(session_id)


def teleport_command(args):
    """Lazy wrapper for teleport command."""
    from .commands import teleport_command as _teleport_command

    return _teleport_command(args)


def watch_command(args):
    """Lazy wrapper for watch command."""
    from .watch_cmd import watch_command as _watch_command

    return _watch_command(args)


def main():
    """Main entry point."""
    argv = sys.argv[1:]
    command_token = first_command_token(argv)
    help_all = "--help-all" in argv
    if command_token is None and (help_all or "--help" in argv or "-h" in argv or not argv):
        print_top_level_help(console, 3 if help_all else compute_visible_help_tier())
        return

    bundle = build_parser()
    args = bundle.parser.parse_args()

    dispatch_command(
        args,
        bundle=bundle,
        console=console,
        error_console=error_console,
        logger=logger,
        list_sessions=list_sessions,
        watch_command=watch_command,
        summary_command=summary_command,
        teleport_command=teleport_command,
    )


if __name__ == "__main__":
    main()
