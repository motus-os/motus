# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Session-related utilities shared by CLI commands."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable


def is_claude_process_running(project_path: str = "") -> bool:
    """Check if a Claude Code process is actively running."""
    from ..orchestrator import get_orchestrator

    orchestrator = get_orchestrator()
    if not project_path:
        return len(orchestrator.get_running_projects()) > 0
    return orchestrator.is_project_active(project_path)


def archive_session(
    session_file: Path,
    *,
    archive_dir: Path,
    move,
    logger,
) -> bool:
    """Archive a session file to Motus state directory archive."""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"{session_file.stem}_{timestamp}.jsonl"
        archive_path = archive_dir / archive_name

        move(str(session_file), str(archive_path))
        logger.info(f"Archived session to {archive_path}")
        return True
    except OSError as e:
        logger.warning(
            f"Failed to archive session {session_file}: {e}",
        )
        return False
    except Exception as e:
        logger.error(
            f"Unexpected error archiving session {session_file}: {e}",
        )
        return False


def delete_session(session_file: Path, *, logger) -> bool:
    """Permanently delete a session file."""
    try:
        session_file.unlink()
        logger.info(f"Deleted session {session_file}")
        return True
    except OSError as e:
        logger.warning(
            f"Failed to delete session {session_file}: {e}",
        )
        return False
    except Exception as e:
        logger.error(
            f"Unexpected error deleting session {session_file}: {e}",
        )
        return False


def get_running_claude_projects() -> set[str]:
    """Get project paths where Claude processes are currently running."""
    from ..orchestrator import get_orchestrator

    orchestrator = get_orchestrator()
    return orchestrator.get_running_projects()


def find_sessions(max_age_hours: int = 2):
    """Find recent sessions from all sources (Claude, Codex, Gemini, SDK)."""
    from ..orchestrator import get_orchestrator
    from .output import unified_session_to_session_info

    orchestrator = get_orchestrator()
    unified_sessions = orchestrator.discover_all(max_age_hours=max_age_hours)

    session_infos = []
    for unified in unified_sessions:
        session_info = unified_session_to_session_info(unified)
        if unified.status.value in ("crashed", "open"):
            builder = orchestrator.get_builder(unified.source)
            if builder:
                session_info.last_action = builder.get_last_action(unified.file_path)
        session_infos.append(session_info)

    return session_infos


def find_active_session():
    """Find the most recently active session from any source."""
    from ..orchestrator import get_orchestrator
    from .output import unified_session_to_session_info

    orchestrator = get_orchestrator()
    unified_sessions = orchestrator.discover_all(max_age_hours=1)

    if unified_sessions:
        unified = unified_sessions[0]
        session_info = unified_session_to_session_info(unified)
        builder = orchestrator.get_builder(unified.source)
        if builder:
            session_info.last_action = builder.get_last_action(unified.file_path)
        return session_info

    return None


def find_sdk_traces(mc_state_dir: Path) -> list[dict]:
    """Find SDK trace files."""
    from ._traces import find_sdk_traces_in_dir

    return find_sdk_traces_in_dir(mc_state_dir)


def iter_session_helpers() -> Iterable[str]:
    """Expose helper names for __all__ maintenance."""
    return [
        "archive_session",
        "delete_session",
        "find_active_session",
        "find_sessions",
        "find_sdk_traces",
        "get_running_claude_projects",
        "is_claude_process_running",
    ]
