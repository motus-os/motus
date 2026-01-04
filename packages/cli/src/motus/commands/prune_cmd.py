# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Session pruning command."""

import shutil
from datetime import datetime, timedelta
from pathlib import Path

from rich.console import Console
from rich.markup import escape
from rich.prompt import Confirm

from .list_cmd import find_claude_sessions

try:
    from ..config import ARCHIVE_DIR, MC_STATE_DIR
except ImportError:
    from pathlib import Path

    MC_STATE_DIR = Path.home() / ".mc"
    ARCHIVE_DIR = MC_STATE_DIR / "archive"

console = Console()


def archive_session(session_file: Path) -> bool:
    """Archive a session file to the archive directory."""
    try:
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

        # Create dated subdirectory
        date_dir = ARCHIVE_DIR / datetime.now().strftime("%Y-%m-%d")
        date_dir.mkdir(exist_ok=True)

        # Copy to archive
        dest = date_dir / session_file.name
        shutil.copy2(session_file, dest)

        # Remove original
        session_file.unlink()

        return True

    except (OSError, IOError, shutil.Error):
        return False


def delete_session(session_file: Path) -> bool:
    """Permanently delete a session file."""
    try:
        session_file.unlink()
        return True
    except (OSError, IOError):
        return False


def prune_command(older_than_hours: int = 2, archive: bool = True, force: bool = False):
    """Prune old sessions (archive or delete)."""
    sessions = find_claude_sessions(max_age_hours=168)  # Get all from last week

    cutoff = datetime.now() - timedelta(hours=older_than_hours)
    old_sessions = [s for s in sessions if s.last_modified < cutoff and not s.is_active]

    if not old_sessions:
        console.print(f"[green]No sessions older than {older_than_hours}h to prune.[/green]")
        return

    console.print(
        f"Found [bold]{len(old_sessions)}[/bold] sessions older than {older_than_hours}h:"
    )
    for session in old_sessions[:10]:
        project = session.project_path.split("/")[-1] if session.project_path else "unknown"
        console.print(f"  - {escape(project)} ({escape(session.session_id[:8])})")

    if len(old_sessions) > 10:
        console.print(f"  ... and {len(old_sessions) - 10} more", markup=False)

    action = "archive" if archive else "delete"

    if not force:
        if not Confirm.ask(f"\n{action.title()} these {len(old_sessions)} sessions?"):
            console.print("[dim]Cancelled.[/dim]")
            return

    success = 0
    failed = 0

    for session in old_sessions:
        if archive:
            result = archive_session(session.file_path)
        else:
            result = delete_session(session.file_path)

        if result:
            success += 1
        else:
            failed += 1

    console.print()
    console.print(f"[green]✓ {action.title()}d {success} sessions[/green]")
    if failed:
        console.print(f"[red]✗ Failed: {failed} sessions[/red]")

    if archive:
        console.print(f"[dim]Archived to: {escape(str(ARCHIVE_DIR))}[/dim]")
