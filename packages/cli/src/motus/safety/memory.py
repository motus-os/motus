# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Cross-session memory for learning."""

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table

from motus.atomic_io import atomic_write_json

console = Console()


@dataclass
class MemoryEntry:
    """A memory entry for cross-session learning."""

    timestamp: str
    file: str
    event: str  # "test_failure", "fix", "error", "lesson"
    details: str
    test_file: Optional[str] = None


def get_memory_file(project_dir: Optional[Path] = None) -> Path:
    """Get the memory file for a project."""
    if project_dir is None:
        project_dir = Path.cwd()

    mc_project_dir = project_dir / ".mc"
    mc_project_dir.mkdir(exist_ok=True)
    return mc_project_dir / "memory.json"


def load_memory(project_dir: Optional[Path] = None) -> list[MemoryEntry]:
    """Load memory entries for a project."""
    mem_file = get_memory_file(project_dir)
    if not mem_file.exists():
        return []

    try:
        data = json.loads(mem_file.read_text())
        return [MemoryEntry(**entry) for entry in data]
    except (json.JSONDecodeError, TypeError):
        return []


def save_memory(entries: list[MemoryEntry], project_dir: Optional[Path] = None):
    """Save memory entries for a project."""
    mem_file = get_memory_file(project_dir)
    data = [asdict(entry) for entry in entries]
    atomic_write_json(mem_file, data)


def record_memory(
    file: str,
    event: str,
    details: str,
    test_file: Optional[str] = None,
    project_dir: Optional[Path] = None,
):
    """Record a memory entry."""
    entry = MemoryEntry(
        timestamp=datetime.now().isoformat(),
        file=file,
        event=event,
        details=details,
        test_file=test_file,
    )

    entries = load_memory(project_dir)
    entries.insert(0, entry)

    # Keep only last 100 entries
    entries = entries[:100]
    save_memory(entries, project_dir)

    return entry


def get_file_memories(file: str, project_dir: Optional[Path] = None) -> list[MemoryEntry]:
    """Get memories related to a specific file."""
    entries = load_memory(project_dir)
    return [e for e in entries if e.file == file or e.test_file == file]


def memory_command(file: Optional[str] = None):
    """Show memory for the project or a specific file."""
    entries = load_memory()

    if file:
        entries = get_file_memories(file)

    if not entries:
        console.print("[yellow]No memories recorded yet[/yellow]")
        console.print("[dim]Memories are recorded when tests fail or fixes are applied[/dim]")
        return

    table = Table(title=f"Memory{f' for {file}' if file else ''}")
    table.add_column("Age", style="dim", width=8)
    table.add_column("File", style="cyan")
    table.add_column("Event", style="yellow")
    table.add_column("Details", style="white")

    for entry in entries[:15]:
        try:
            dt = datetime.fromisoformat(entry.timestamp)
            age = datetime.now() - dt
            if age.total_seconds() < 3600:
                age_str = f"{int(age.total_seconds() / 60)}m"
            elif age.total_seconds() < 86400:
                age_str = f"{int(age.total_seconds() / 3600)}h"
            else:
                age_str = f"{int(age.total_seconds() / 86400)}d"
        except (ValueError, TypeError):
            age_str = "?"

        table.add_row(
            age_str,
            Path(entry.file).name,
            entry.event,
            entry.details[:50],
        )

    console.print(table)


def remember_command(file: str, event: str, details: str):
    """Manually record a memory."""
    record_memory(file, event, details)
    console.print(f"[green]✓ Remembered:[/green] {event} for {file}")
