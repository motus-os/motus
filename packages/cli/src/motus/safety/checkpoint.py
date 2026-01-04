# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Checkpoint and rollback functionality."""

import json
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from motus.atomic_io import atomic_write_json
from motus.exceptions import SubprocessError, SubprocessTimeoutError
from motus.subprocess_utils import (
    GIT_LONG_TIMEOUT_SECONDS,
    GIT_SHORT_TIMEOUT_SECONDS,
    run_subprocess,
)

console = Console()


@dataclass
class Checkpoint:
    """A saved state checkpoint."""

    id: str
    message: str
    timestamp: str
    stash_ref: Optional[str] = None
    files_snapshot: list[str] = field(default_factory=list)


def get_checkpoints_file(project_dir: Optional[Path] = None) -> Path:
    """Get the checkpoints file for a project."""
    if project_dir is None:
        project_dir = Path.cwd()

    mc_project_dir = project_dir / ".mc"
    mc_project_dir.mkdir(exist_ok=True)
    return mc_project_dir / "checkpoints.json"


def load_checkpoints(project_dir: Optional[Path] = None) -> list[Checkpoint]:
    """Load checkpoints for a project."""
    cp_file = get_checkpoints_file(project_dir)
    if not cp_file.exists():
        return []

    try:
        data = json.loads(cp_file.read_text())
        return [Checkpoint(**cp) for cp in data]
    except (json.JSONDecodeError, TypeError):
        return []


def save_checkpoints(checkpoints: list[Checkpoint], project_dir: Optional[Path] = None):
    """Save checkpoints for a project."""
    cp_file = get_checkpoints_file(project_dir)
    data = [asdict(cp) for cp in checkpoints]
    atomic_write_json(cp_file, data)


def checkpoint_command(message: str = "checkpoint"):
    """Create a checkpoint of the current state.

    Uses git stash to save uncommitted changes.
    """
    # Check if we're in a git repo
    try:
        result = run_subprocess(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            timeout_seconds=GIT_SHORT_TIMEOUT_SECONDS,
            what="git rev-parse",
        )
    except (SubprocessTimeoutError, SubprocessError) as e:
        console.print(f"[red]Error: {e}[/red]")
        return False
    if result.returncode != 0:
        console.print("[red]Error: Not in a git repository[/red]")
        return False

    # Get list of modified files
    try:
        result = run_subprocess(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout_seconds=GIT_SHORT_TIMEOUT_SECONDS,
            what="git status",
        )
    except (SubprocessTimeoutError, SubprocessError) as e:
        console.print(f"[red]Error: {e}[/red]")
        return False
    modified_files = [line[3:] for line in result.stdout.strip().split("\n") if line.strip()]

    if not modified_files:
        console.print("[yellow]No changes to checkpoint[/yellow]")
        return False

    # Create timestamp-based ID
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    cp_id = f"mc-{timestamp}"

    # Create git stash with message
    stash_message = f"mc-checkpoint: {message}"
    try:
        result = run_subprocess(
            ["git", "stash", "push", "-m", stash_message, "--include-untracked"],
            capture_output=True,
            text=True,
            timeout_seconds=GIT_LONG_TIMEOUT_SECONDS,
            what="git stash push",
        )
    except (SubprocessTimeoutError, SubprocessError) as e:
        console.print(f"[red]Failed to create checkpoint: {e}[/red]")
        return False

    if result.returncode != 0:
        console.print(f"[red]Failed to create checkpoint: {result.stderr}[/red]")
        return False

    # Get the stash reference
    try:
        result = run_subprocess(
            ["git", "stash", "list", "--format=%gd %s"],
            capture_output=True,
            text=True,
            timeout_seconds=GIT_SHORT_TIMEOUT_SECONDS,
            what="git stash list",
        )
    except (SubprocessTimeoutError, SubprocessError):
        result = subprocess.CompletedProcess(
            args=["git", "stash", "list"], returncode=1, stdout="", stderr=""
        )
    stash_ref = None
    for line in result.stdout.strip().split("\n"):
        if stash_message in line:
            stash_ref = line.split()[0]
            break

    # Save checkpoint metadata
    checkpoint = Checkpoint(
        id=cp_id,
        message=message,
        timestamp=datetime.now().isoformat(),
        stash_ref=stash_ref,
        files_snapshot=modified_files,
    )

    checkpoints = load_checkpoints()
    checkpoints.insert(0, checkpoint)  # Most recent first
    save_checkpoints(checkpoints)

    console.print(
        Panel(
            f"[green]Checkpoint created: {cp_id}[/green]\n"
            f"[dim]Message: {message}[/dim]\n"
            f"[dim]Files: {len(modified_files)}[/dim]",
            title="[bold green]✓ Checkpoint[/bold green]",
            border_style="green",
        )
    )

    # Immediately restore working state (stash pop)
    try:
        run_subprocess(
            ["git", "stash", "pop", "--quiet"],
            capture_output=True,
            timeout_seconds=GIT_LONG_TIMEOUT_SECONDS,
            what="git stash pop",
        )
    except (SubprocessTimeoutError, SubprocessError):
        # Best-effort: checkpoint metadata is still persisted.
        pass

    console.print("[dim]Working state preserved. Use 'motus rollback' to restore.[/dim]")
    return True


def list_checkpoints_command():
    """List available checkpoints."""
    checkpoints = load_checkpoints()

    if not checkpoints:
        console.print("[yellow]No checkpoints found[/yellow]")
        console.print("[dim]Create one with: motus checkpoint 'before refactor'[/dim]")
        return

    table = Table(title="Checkpoints")
    table.add_column("ID", style="cyan")
    table.add_column("Message", style="white")
    table.add_column("Files", justify="right")
    table.add_column("Age", style="dim")

    for cp in checkpoints[:10]:  # Show last 10
        try:
            dt = datetime.fromisoformat(cp.timestamp)
            age = datetime.now() - dt
            if age.total_seconds() < 3600:
                age_str = f"{int(age.total_seconds() / 60)}m"
            else:
                age_str = f"{int(age.total_seconds() / 3600)}h"
        except (ValueError, TypeError):
            age_str = "?"

        table.add_row(
            cp.id,
            cp.message[:40],
            str(len(cp.files_snapshot)),
            age_str,
        )

    console.print(table)
    console.print("\n[dim]Rollback with: motus rollback <id>[/dim]")


def rollback_command(checkpoint_id: Optional[str] = None):
    """Rollback to a checkpoint.

    If no ID provided, shows diff against most recent checkpoint.
    """
    checkpoints = load_checkpoints()

    if not checkpoints:
        console.print("[red]No checkpoints found[/red]")
        return False

    if checkpoint_id is None:
        # Show diff against most recent
        cp = checkpoints[0]
        console.print(f"[yellow]Most recent checkpoint: {cp.id}[/yellow]")
        console.print(f"[dim]Message: {cp.message}[/dim]")
        console.print(f"[dim]Files: {', '.join(cp.files_snapshot[:5])}...[/dim]")
        console.print("\n[dim]To rollback, run: motus rollback {cp.id}[/dim]")
        return True

    # Find the checkpoint
    target = None
    for cp in checkpoints:
        if cp.id == checkpoint_id or checkpoint_id in cp.id:
            target = cp
            break

    if not target:
        console.print(f"[red]Checkpoint not found: {checkpoint_id}[/red]")
        return False

    # Stash current changes first (safety)
    try:
        run_subprocess(
            ["git", "stash", "push", "-m", "mc-rollback-safety", "--include-untracked"],
            capture_output=True,
            timeout_seconds=GIT_LONG_TIMEOUT_SECONDS,
            what="git stash push",
        )
    except (SubprocessTimeoutError, SubprocessError) as e:
        console.print(f"[red]Failed to stash current state: {e}[/red]")
        return False

    # Find and apply the checkpoint stash
    if target.stash_ref:
        try:
            result = run_subprocess(
                ["git", "stash", "apply", target.stash_ref],
                capture_output=True,
                text=True,
                timeout_seconds=GIT_LONG_TIMEOUT_SECONDS,
                what="git stash apply",
            )
        except (SubprocessTimeoutError, SubprocessError) as e:
            console.print(f"[red]Failed to apply checkpoint: {e}[/red]")
            return False
        if result.returncode != 0:
            console.print(f"[red]Failed to apply checkpoint: {result.stderr}[/red]")
            # Restore safety stash
            try:
                run_subprocess(
                    ["git", "stash", "pop", "--quiet"],
                    capture_output=True,
                    timeout_seconds=GIT_LONG_TIMEOUT_SECONDS,
                    what="git stash pop",
                )
            except (SubprocessTimeoutError, SubprocessError):
                pass
            return False

    console.print(
        Panel(
            f"[green]Rolled back to: {target.id}[/green]\n"
            f"[dim]Your previous state is saved in git stash[/dim]",
            title="[bold green]✓ Rollback[/bold green]",
            border_style="green",
        )
    )
    return True
