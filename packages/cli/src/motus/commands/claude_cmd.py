# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""CLI command: `motus claude` for safe CLAUDE.md injection."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from rich.console import Console

from motus.cli.exit_codes import EXIT_ERROR, EXIT_SUCCESS, EXIT_USAGE

BLOCK_START = "<!-- MOTUS-AGENT-INSTRUCTIONS START -->"
BLOCK_END = "<!-- MOTUS-AGENT-INSTRUCTIONS END -->"

console = Console()


def _build_claude_block(link_path: str) -> str:
    body = "\n".join(
        [
            "# Motus Agent Instructions (managed)",
            f"See {link_path} for the full guide.",
        ]
    )
    return "\n".join([BLOCK_START, body, BLOCK_END, ""])


def _build_instructions_block() -> str:
    body = "\n".join(
        [
            "# Motus Agent Instructions",
            "",
            "This repository uses Motus to coordinate agent work.",
            "Use the Motus CLI as the source of truth for changes and evidence.",
            "",
            "Recommended workflow:",
            "- Run `motus health capture` before changes and `motus health compare` after.",
            "- Run `motus verify clean` for a clean-room sanity check.",
            "- Review evidence with `motus activity list`.",
            "",
            "If Motus cannot be run, record the reason in the task log.",
        ]
    )
    return "\n".join([BLOCK_START, body, BLOCK_END, ""])


def _apply_managed_block(
    content: str,
    block: str,
    *,
    allow_append: bool,
    force: bool,
) -> tuple[str, str]:
    if BLOCK_START in content and BLOCK_END in content:
        start = content.index(BLOCK_START)
        end = content.index(BLOCK_END) + len(BLOCK_END)
        existing = content[start:end].strip()
        desired = block.strip()
        if existing == desired:
            return content, "unchanged"
        if not force:
            return content, "conflict"
        updated = content[:start] + block + content[end:]
        return updated, "updated"

    if content.strip() and not allow_append and not force:
        return content, "conflict"

    if content.strip():
        updated = content.rstrip("\n") + "\n\n" + block
    else:
        updated = block
    return updated, "added"


def _write_managed_file(
    path: Path,
    block: str,
    *,
    allow_append: bool,
    force: bool,
    dry_run: bool,
    stdout: bool,
    label: str,
) -> tuple[int, str]:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    updated, status = _apply_managed_block(
        existing,
        block,
        allow_append=allow_append,
        force=force,
    )

    if status == "conflict":
        console.print(
            f"[red]{label}: managed block conflict (use --force to override)[/red]"
        )
        return EXIT_ERROR, status

    if stdout and label == "CLAUDE.md":
        console.print(updated, markup=False)
        return EXIT_SUCCESS, status

    if dry_run or stdout:
        console.print(f"{label}: {status} (dry-run)", markup=False)
        return EXIT_SUCCESS, status

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(updated, encoding="utf-8")
    console.print(f"{label}: {status}", markup=False)
    return EXIT_SUCCESS, status


def claude_command(args: Namespace) -> int:
    root = Path(getattr(args, "path", ".")).expanduser().resolve()
    claude_path = getattr(args, "claude_path", None)
    docs_path = getattr(args, "docs_path", "docs/AGENT-INSTRUCTIONS.md")

    claude_file = Path(claude_path).expanduser().resolve() if claude_path else root / "CLAUDE.md"
    docs_file = root / docs_path

    link_target = docs_file
    try:
        link_path = str(link_target.relative_to(root))
    except ValueError:
        link_path = str(link_target)

    claude_block = _build_claude_block(link_path)
    docs_block = _build_instructions_block()

    dry_run = bool(getattr(args, "dry_run", False))
    stdout = bool(getattr(args, "stdout", False))
    force = bool(getattr(args, "force", False))
    no_docs = bool(getattr(args, "no_docs", False))

    if stdout and dry_run:
        console.print("[red]Use either --stdout or --dry-run, not both.[/red]")
        return EXIT_USAGE

    status_code, _ = _write_managed_file(
        claude_file,
        claude_block,
        allow_append=True,
        force=force,
        dry_run=dry_run,
        stdout=stdout,
        label="CLAUDE.md",
    )
    if status_code != EXIT_SUCCESS:
        return status_code

    if no_docs or stdout:
        return EXIT_SUCCESS

    status_code, _ = _write_managed_file(
        docs_file,
        docs_block,
        allow_append=False,
        force=force,
        dry_run=dry_run,
        stdout=False,
        label="docs/AGENT-INSTRUCTIONS.md",
    )
    return status_code
