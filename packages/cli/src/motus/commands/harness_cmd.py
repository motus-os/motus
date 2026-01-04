# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""
Harness detection command for Motus v0.3.0.
"""

import json
from dataclasses import asdict
from pathlib import Path

from rich import box
from rich.console import Console
from rich.markup import escape
from rich.table import Table

console = Console()


def harness_command(save: bool = False) -> None:
    """Detect and display test harness for current directory.

    Args:
        save: If True, save harness config to .mc/harness.json
    """
    from ..harness import detect_harness

    repo_path = Path.cwd()
    harness = detect_harness(repo_path)

    # Check if anything was detected
    has_commands = any(
        [
            harness.test_command,
            harness.lint_command,
            harness.build_command,
            harness.smoke_test,
        ]
    )

    if not has_commands:
        console.print("[yellow]No test harness detected[/yellow]")
        console.print(
            "[dim]Looking for: pyproject.toml, package.json, Cargo.toml, Makefile, CI configs[/dim]"
        )
        return

    # Display detected commands
    table = Table(title="Detected Test Harness", box=box.SIMPLE)
    table.add_column("Type", style="cyan", width=15)
    table.add_column("Command", style="green")
    table.add_column("Confidence", style="dim", width=10)

    if harness.test_command:
        table.add_row("Test", harness.test_command, "high")
    if harness.lint_command:
        table.add_row("Lint", harness.lint_command, "high")
    if harness.build_command:
        table.add_row("Build", harness.build_command, "high")
    if harness.smoke_test:
        table.add_row("Smoke Test", harness.smoke_test, "medium")

    console.print(table)

    # Save to .mc/harness.json if requested
    if save:
        mc_dir = repo_path / ".mc"
        mc_dir.mkdir(exist_ok=True)
        harness_file = mc_dir / "harness.json"

        try:
            with open(harness_file, "w") as f:
                json.dump(asdict(harness), f, indent=2)
            console.print(f"\n[green]✓ Saved to {escape(str(harness_file))}[/green]")
        except (OSError, IOError) as e:
            console.print(f"\n[red]Failed to save: {escape(str(e))}[/red]")
