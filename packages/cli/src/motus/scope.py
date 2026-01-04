# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""
Scope Creep Monitor for Motus v0.3.

Monitors file touches vs intent to detect scope drift.
Alerts when an agent is modifying more files than expected.

Features:
- Track file touches from session transcript
- Compare against intent.priority_files
- Calculate drift percentage
- Alert when threshold exceeded
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from .exceptions import SubprocessError, SubprocessTimeoutError
from .intent import Intent, load_intent
from .logging import get_logger
from .orchestrator import get_orchestrator
from .schema.events import EventType
from .subprocess_utils import GIT_SHORT_TIMEOUT_SECONDS, run_subprocess

logger = get_logger(__name__)


@dataclass
class ScopeStatus:
    """Current scope status for a session.

    Attributes:
        expected_files: Files specified in intent.priority_files
        touched_files: Files actually modified in the session
        unexpected_files: Files touched but not in priority_files
        drift_percentage: Percentage of touches outside expected scope
        threshold: Configured threshold for alerting (default: 150%)
        alert: Whether drift exceeds threshold
    """

    expected_files: list[str] = field(default_factory=list)
    touched_files: list[str] = field(default_factory=list)
    unexpected_files: list[str] = field(default_factory=list)
    drift_percentage: float = 0.0
    threshold: float = 150.0  # Default: 150% = 1.5x expected files
    alert: bool = False
    timestamp: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "expected_files": self.expected_files,
            "touched_files": self.touched_files,
            "unexpected_files": self.unexpected_files,
            "drift_percentage": self.drift_percentage,
            "threshold": self.threshold,
            "alert": self.alert,
            "timestamp": self.timestamp,
        }


def get_touched_files_from_session(session_path: Path) -> set[str]:
    """Extract files touched from a session transcript.

    Args:
        session_path: Path to session transcript file

    Returns:
        Set of file paths that were modified during the session
    """
    orchestrator = get_orchestrator()

    # Find the session by file path
    # We need to discover sessions and find one that matches the path
    sessions = orchestrator.discover_all(max_age_hours=168)  # Last week
    session = None
    for s in sessions:
        if str(s.file_path) == str(session_path):
            session = s
            break

    if not session:
        # If session not found, return empty set
        return set()

    # Get events from the session
    events = orchestrator.get_events(session)

    # Extract files modified by filtering TOOL_USE events with Edit/Write tools
    touched = set()
    for event in events:
        if event.event_type == EventType.TOOL_USE and event.tool_name in ("Edit", "Write"):
            if event.file_path:
                touched.add(event.file_path)

    return touched


def get_touched_files_from_git(repo_path: Path) -> set[str]:
    """Get files modified in current git working directory.

    This provides a more accurate view of what's been changed,
    regardless of what the transcript shows.

    Args:
        repo_path: Path to git repository

    Returns:
        Set of file paths that are modified/staged/untracked
    """
    try:
        result = run_subprocess(
            ["git", "status", "--porcelain"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout_seconds=GIT_SHORT_TIMEOUT_SECONDS,
            what="git status",
        )
    except (SubprocessTimeoutError, SubprocessError) as e:
        logger.debug("git status failed for scope check", error=str(e))
        return set()

    if result.returncode != 0:
        return set()

    files = set()
    for line in result.stdout.strip().split("\n"):
        if line.strip():
            # Format is "XY filename" where XY is status code
            # Strip first 3 characters to get filename
            filename = line[3:].strip()
            # Handle renamed files (format: "R  old -> new")
            if " -> " in filename:
                filename = filename.split(" -> ")[1]
            # Exclude .mc/ directory
            if not filename.startswith(".mc/"):
                files.add(filename)

    return files


def calculate_scope_status(
    intent: Intent,
    touched_files: set[str],
    threshold: float = 150.0,
) -> ScopeStatus:
    """Calculate scope drift status.

    Args:
        intent: Intent object with priority_files
        touched_files: Set of files actually touched
        threshold: Alert threshold percentage (default: 150%)

    Returns:
        ScopeStatus with drift analysis
    """
    expected = set(intent.priority_files) if intent.priority_files else set()
    touched = touched_files

    # Files outside expected scope
    unexpected = touched - expected

    # Calculate drift percentage
    # If no expected files, any touch is 100% drift
    if len(expected) == 0:
        if len(touched) == 0:
            drift_pct = 0.0
        else:
            drift_pct = 100.0  # All files are unexpected
    else:
        # Drift = (total touched / expected) * 100
        drift_pct = (len(touched) / len(expected)) * 100

    # Check if we should alert
    alert = drift_pct > threshold

    return ScopeStatus(
        expected_files=sorted(expected),
        touched_files=sorted(touched),
        unexpected_files=sorted(unexpected),
        drift_percentage=drift_pct,
        threshold=threshold,
        alert=alert,
        timestamp=datetime.now().isoformat(),
    )


def check_scope(
    session_path: Optional[Path] = None,
    repo_path: Optional[Path] = None,
    mc_dir: Optional[Path] = None,
    threshold: float = 150.0,
    use_git: bool = True,
) -> ScopeStatus:
    """Check current scope status.

    Can use either session transcript or git status to determine touched files.
    Loads intent from .mc/intent.yaml if available.

    Args:
        session_path: Path to session transcript (optional)
        repo_path: Path to git repository (defaults to cwd)
        mc_dir: Path to .mc directory (defaults to repo_path/.mc)
        threshold: Alert threshold percentage
        use_git: If True, use git status instead of session transcript

    Returns:
        ScopeStatus with current drift analysis
    """
    if repo_path is None:
        repo_path = Path.cwd()

    if mc_dir is None:
        mc_dir = repo_path / ".mc"

    # Load intent
    intent = load_intent(mc_dir)
    if intent is None:
        # Create empty intent if none exists
        intent = Intent(task="Unknown task")
        logger.debug("No intent found, using empty intent")

    # Get touched files
    if use_git:
        touched = get_touched_files_from_git(repo_path)
    elif session_path:
        touched = get_touched_files_from_session(session_path)
    else:
        touched = set()

    return calculate_scope_status(intent, touched, threshold)


def format_scope_report(status: ScopeStatus) -> str:
    """Format scope status as a readable report.

    Args:
        status: ScopeStatus to format

    Returns:
        Formatted string report
    """
    lines = []

    # Header with alert status
    if status.alert:
        lines.append("SCOPE ALERT: Drift exceeds threshold!")
        lines.append("")

    # Summary stats
    lines.append(f"Files touched: {len(status.touched_files)}")
    lines.append(f"Expected files: {len(status.expected_files)}")
    lines.append(f"Unexpected files: {len(status.unexpected_files)}")
    lines.append(f"Drift: {status.drift_percentage:.0f}% (threshold: {status.threshold:.0f}%)")
    lines.append("")

    # List unexpected files if any
    if status.unexpected_files:
        lines.append("Files outside priority_files:")
        for f in status.unexpected_files[:10]:  # Limit to 10
            lines.append(f"  - {f}")
        if len(status.unexpected_files) > 10:
            lines.append(f"  ... and {len(status.unexpected_files) - 10} more")

    return "\n".join(lines)
