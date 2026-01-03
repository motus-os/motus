# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Test harness detection."""

from pathlib import Path

from rich.console import Console
from rich.table import Table

console = Console()


def detect_test_harness() -> dict:
    """Detect test commands from project configuration.

    This is a wrapper around the comprehensive harness.detect_harness()
    that maintains backward compatibility with the dict format.
    """
    from ..harness import detect_harness

    cwd = Path.cwd()
    harness_obj = detect_harness(cwd)

    # Convert to legacy dict format for backward compatibility
    detected_from = []
    if harness_obj.test_command:
        # Infer source from command patterns
        if "pytest" in harness_obj.test_command:
            detected_from.append("pyproject.toml")
        elif "npm test" in harness_obj.test_command:
            detected_from.append("package.json")
        elif "cargo test" in harness_obj.test_command:
            detected_from.append("Cargo.toml")
        elif "make test" in harness_obj.test_command:
            detected_from.append("Makefile")

    return {
        "test_command": harness_obj.test_command,
        "lint_command": harness_obj.lint_command,
        "build_command": harness_obj.build_command,
        "detected_from": detected_from,
    }


def find_related_tests(source_file: str) -> list[str]:
    """Find test files related to a source file."""
    source_path = Path(source_file)
    base_name = source_path.stem
    cwd = Path.cwd()

    # Common patterns for test file naming
    patterns = [
        f"test_{base_name}.py",
        f"{base_name}_test.py",
        f"tests/test_{base_name}.py",
        f"tests/{base_name}_test.py",
        f"test/test_{base_name}.py",
        f"**/test_{base_name}.py",
        f"**/{base_name}_test.py",
    ]

    related = []
    for pattern in patterns:
        # Use cwd.glob() to bound search to current directory, not entire filesystem
        related.extend(str(p) for p in cwd.glob(pattern))

    return list(set(related))


def test_harness_command():
    """Show detected test harness configuration."""
    harness = detect_test_harness()

    if not harness["detected_from"]:
        console.print("[yellow]No test configuration detected[/yellow]")
        console.print("[dim]Looking for: pyproject.toml, package.json, Makefile[/dim]")
        return

    table = Table(title="Detected Test Harness")
    table.add_column("Type", style="cyan")
    table.add_column("Command", style="green")

    if harness["test_command"]:
        table.add_row("Test", harness["test_command"])
    if harness["lint_command"]:
        table.add_row("Lint", harness["lint_command"])
    if harness["build_command"]:
        table.add_row("Build", harness["build_command"])

    console.print(table)
    console.print(f"\n[dim]Detected from: {', '.join(harness['detected_from'])}[/dim]")
