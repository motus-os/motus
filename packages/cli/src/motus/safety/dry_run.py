# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Dry run simulation for destructive commands."""

import glob
import os
import shlex
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from motus.exceptions import SubprocessError, SubprocessTimeoutError
from motus.subprocess_utils import GIT_SHORT_TIMEOUT_SECONDS, run_subprocess

console = Console()

MAX_RM_SCAN_FILES = int(os.environ.get("MC_RM_MAX_FILES", "20000"))
MAX_RM_SCAN_DEPTH = int(os.environ.get("MC_RM_MAX_DEPTH", "20"))


@dataclass
class DryRunResult:
    """Result of a dry-run simulation."""

    supported: bool
    command: str
    action: str = ""
    targets: list[str] = field(default_factory=list)
    size_bytes: int = 0
    reversible: bool = True
    message: str = ""
    risk: str = "unknown"

class _RmScanBudget:
    def __init__(self, max_files: int) -> None:
        self.max_files = max_files
        self.count = 0
        self.truncated = False
        self.files: list[str] = []
        self.total_size = 0

    def add(self, path: Path) -> None:
        if self.count >= self.max_files:
            self.truncated = True
            return
        self.count += 1
        self.files.append(str(path))
        try:
            self.total_size += path.stat().st_size
        except OSError:
            pass


def _walk_dir(path: Path, budget: _RmScanBudget, max_depth: int) -> None:
    root = path.resolve()
    root_depth = len(root.parts)
    for current_root, dirs, files in os.walk(root):
        depth = len(Path(current_root).parts) - root_depth
        if depth >= max_depth:
            dirs[:] = []
        for name in files:
            budget.add(Path(current_root) / name)
            if budget.truncated:
                return
        if budget.truncated:
            return


def dry_run_rm(args: list[str]) -> DryRunResult:
    """Simulate rm command."""
    budget = _RmScanBudget(MAX_RM_SCAN_FILES)
    recursive = "-r" in args or "-rf" in args or "-fr" in args

    for arg in args:
        if arg.startswith("-"):
            continue

        if budget.truncated:
            break

        path = Path(arg)
        if path.exists():
            if path.is_dir() and recursive:
                _walk_dir(path, budget, MAX_RM_SCAN_DEPTH)
            elif path.is_file():
                budget.add(path)
        else:
            # Try glob expansion
            for match in glob.glob(arg, recursive=recursive):
                if budget.truncated:
                    break
                p = Path(match)
                if p.is_file():
                    budget.add(p)
                elif p.is_dir() and recursive:
                    _walk_dir(p, budget, MAX_RM_SCAN_DEPTH)

    total_size = budget.total_size
    count_label = f"{budget.count}+" if budget.truncated else str(budget.count)
    size_label = f">= {total_size // 1024}KB" if budget.truncated else f"{total_size // 1024}KB"

    return DryRunResult(
        supported=True,
        command=f"rm {' '.join(args)}",
        action="DELETE",
        targets=budget.files[:20],  # Limit display
        size_bytes=total_size,
        reversible=False,
        message=f"Would delete {count_label} files ({size_label})",
        risk="high" if budget.truncated or budget.count > 10 or total_size > 10_000_000 else "medium",
    )


def dry_run_git_reset(args: list[str]) -> DryRunResult:
    """Simulate git reset command."""
    hard = "--hard" in args

    # Get list of files that would be affected
    try:
        result = run_subprocess(
            ["git", "diff", "--name-only"],
            capture_output=True,
            text=True,
            timeout_seconds=GIT_SHORT_TIMEOUT_SECONDS,
            what="git diff --name-only",
        )
    except (SubprocessTimeoutError, SubprocessError) as e:
        return DryRunResult(
            supported=False,
            command=f"git reset {' '.join(args)}",
            message=str(e),
        )
    staged = result.stdout.strip().split("\n") if result.stdout.strip() else []

    try:
        result = run_subprocess(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            timeout_seconds=GIT_SHORT_TIMEOUT_SECONDS,
            what="git diff --cached --name-only",
        )
    except (SubprocessTimeoutError, SubprocessError) as e:
        return DryRunResult(
            supported=False,
            command=f"git reset {' '.join(args)}",
            message=str(e),
        )
    cached = result.stdout.strip().split("\n") if result.stdout.strip() else []

    affected = list(set(staged + cached))

    return DryRunResult(
        supported=True,
        command=f"git reset {' '.join(args)}",
        action="RESET",
        targets=affected,
        reversible=not hard,
        message=f"Would {'DISCARD' if hard else 'unstage'} changes to {len(affected)} files",
        risk="high" if hard else "medium",
    )


def dry_run_git_clean(args: list[str]) -> DryRunResult:
    """Simulate git clean command."""
    # Use git's built-in dry run
    try:
        result = run_subprocess(
            ["git", "clean", "-n"] + [a for a in args if a not in ["-f", "-d", "-fd"]],
            capture_output=True,
            text=True,
            timeout_seconds=GIT_SHORT_TIMEOUT_SECONDS,
            what="git clean -n",
        )
    except (SubprocessTimeoutError, SubprocessError) as e:
        return DryRunResult(
            supported=False,
            command=f"git clean {' '.join(args)}",
            message=str(e),
        )

    files = []
    for line in result.stdout.strip().split("\n"):
        if line.startswith("Would remove "):
            files.append(line.replace("Would remove ", ""))

    return DryRunResult(
        supported=True,
        command=f"git clean {' '.join(args)}",
        action="DELETE",
        targets=files,
        reversible=False,
        message=f"Would remove {len(files)} untracked files",
        risk="high" if len(files) > 5 else "medium",
    )


def dry_run_mv(args: list[str]) -> DryRunResult:
    """Simulate mv command."""
    # Simple case: mv src dst
    non_flag_args = [a for a in args if not a.startswith("-")]

    if len(non_flag_args) < 2:
        return DryRunResult(
            supported=False,
            command=f"mv {' '.join(args)}",
            message="Cannot parse mv arguments",
        )

    src, dst = non_flag_args[-2], non_flag_args[-1]

    return DryRunResult(
        supported=True,
        command=f"mv {' '.join(args)}",
        action="MOVE",
        targets=[f"{src} → {dst}"],
        reversible=True,
        message=f"Would move {src} to {dst}",
        risk="low",
    )


def dry_run_command(command: str):
    """Simulate a command and show what would happen.

    Supports: rm, git reset, git clean, mv
    """
    try:
        parts = shlex.split(command)
    except ValueError:
        parts = command.split()

    if not parts:
        console.print("[red]Empty command[/red]")
        return

    base_cmd = parts[0]
    args = parts[1:]

    result: DryRunResult

    if base_cmd == "rm":
        result = dry_run_rm(args)
    elif base_cmd == "git" and args and args[0] == "reset":
        result = dry_run_git_reset(args[1:])
    elif base_cmd == "git" and args and args[0] == "clean":
        result = dry_run_git_clean(args[1:])
    elif base_cmd == "mv":
        result = dry_run_mv(args)
    else:
        result = DryRunResult(
            supported=False,
            command=command,
            message=f"Cannot simulate '{base_cmd}'. Proceed with caution.",
            risk="unknown",
        )

    # Display result
    if result.supported:
        risk_color = {
            "low": "green",
            "medium": "yellow",
            "high": "red",
        }.get(result.risk, "white")

        content = f"[bold]{result.action}[/bold]\n"
        content += f"[{risk_color}]Risk: {result.risk.upper()}[/{risk_color}]\n"
        content += f"{result.message}\n\n"

        if result.targets:
            content += "[dim]Targets:[/dim]\n"
            for target in result.targets[:10]:
                content += f"  • {target}\n"
            if len(result.targets) > 10:
                content += f"  [dim]... and {len(result.targets) - 10} more[/dim]\n"

        if not result.reversible:
            content += "\n[red]⚠ NOT REVERSIBLE[/red]"

        console.print(
            Panel(
                content,
                title=f"[bold]Dry Run: {command[:50]}[/bold]",
                border_style=risk_color,
            )
        )
    else:
        console.print(
            Panel(
                f"[yellow]{result.message}[/yellow]\n\n"
                f"[dim]Supported commands: rm, git reset, git clean, mv[/dim]",
                title="[bold yellow]Cannot Simulate[/bold yellow]",
                border_style="yellow",
            )
        )
