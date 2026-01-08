# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""CLI command: `motus scratch` (scratch store)."""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

from rich.console import Console
from rich.table import Table

from motus.cli.exit_codes import EXIT_ERROR, EXIT_SUCCESS, EXIT_USAGE
from motus.scratch import ScratchEntryNotFoundError, ScratchPromotionError, ScratchStore

console = Console()
error_console = Console(stderr=True)


def _resolve_store(args: Namespace) -> ScratchStore:
    root = (getattr(args, "root", None) or "").strip()
    if root:
        return ScratchStore(Path(root).expanduser().resolve())
    return ScratchStore.from_cwd()


def scratch_add_command(args: Namespace) -> int:
    try:
        store = _resolve_store(args)
    except Exception as exc:
        error_console.print(str(exc), style="red", markup=False)
        return EXIT_USAGE

    title = (getattr(args, "title", None) or "").strip()
    body = getattr(args, "body", None)
    tags = list(getattr(args, "tag", []) or [])

    try:
        entry = store.create_entry(title=title, body=body, tags=tags)
    except Exception as exc:
        error_console.print(str(exc), style="red", markup=False)
        return EXIT_USAGE

    if getattr(args, "json", False):
        console.print(json.dumps(entry.to_json(), indent=2, sort_keys=True), markup=False)
    else:
        console.print(f"Scratch entry created: {entry.entry_id}", markup=False)
    return EXIT_SUCCESS


def scratch_list_command(args: Namespace) -> int:
    try:
        store = _resolve_store(args)
        entries = store.list_entries()
    except Exception as exc:
        error_console.print(str(exc), style="red", markup=False)
        return EXIT_USAGE

    status_filter = (getattr(args, "status", None) or "").strip()
    if status_filter:
        entries = [e for e in entries if e.status == status_filter]

    if getattr(args, "json", False):
        payload = {
            "entries": [e.to_json() for e in entries],
            "count": len(entries),
        }
        console.print(json.dumps(payload, indent=2, sort_keys=True), markup=False)
        return EXIT_SUCCESS

    table = Table(title="Scratch Entries", show_lines=False)
    table.add_column("ID", style="dim")
    table.add_column("Title")
    table.add_column("Status")
    table.add_column("Created")
    table.add_column("Updated")
    table.add_column("Roadmap", style="dim")

    for entry in entries:
        table.add_row(
            entry.entry_id,
            entry.title,
            entry.status,
            entry.created_at,
            entry.updated_at,
            entry.roadmap_item_id or "-",
        )

    console.print(table)
    return EXIT_SUCCESS


def scratch_show_command(args: Namespace) -> int:
    try:
        store = _resolve_store(args)
        entry_id = (getattr(args, "entry_id", None) or "").strip()
        if not entry_id:
            raise ValueError("entry_id is required")
        entry = store.load_entry(entry_id)
    except ScratchEntryNotFoundError as exc:
        error_console.print(str(exc), style="red", markup=False)
        return EXIT_ERROR
    except Exception as exc:
        error_console.print(str(exc), style="red", markup=False)
        return EXIT_USAGE

    if getattr(args, "json", False):
        console.print(json.dumps(entry.to_json(), indent=2, sort_keys=True), markup=False)
        return EXIT_SUCCESS

    console.print(f"Scratch Entry: {entry.entry_id}", markup=False)
    console.print(f"Title: {entry.title}", markup=False)
    console.print(f"Status: {entry.status}", markup=False)
    console.print(f"Created: {entry.created_at}", markup=False)
    console.print(f"Updated: {entry.updated_at}", markup=False)
    if entry.tags:
        console.print(f"Tags: {', '.join(entry.tags)}", markup=False)
    if entry.roadmap is not None:
        console.print(f"Roadmap: {entry.roadmap.item_id}", markup=False)
    if entry.body:
        console.print("", markup=False)
        console.print(entry.body, markup=False)
    return EXIT_SUCCESS


def scratch_promote_command(args: Namespace) -> int:
    try:
        store = _resolve_store(args)
        entry_id = (getattr(args, "entry_id", None) or "").strip()
        if not entry_id:
            raise ValueError("entry_id is required")
        phase_key = (getattr(args, "phase", None) or "").strip() or "phase_h"
        item_type = (getattr(args, "item_type", None) or "").strip() or "work"
        title = getattr(args, "title", None)
        description = getattr(args, "description", None)
        result = store.promote_to_roadmap(
            entry_id,
            phase_key=phase_key,
            item_type=item_type,
            title=title,
            description=description,
        )
    except ScratchPromotionError as exc:
        error_console.print(str(exc), style="red", markup=False)
        return EXIT_ERROR
    except Exception as exc:
        error_console.print(str(exc), style="red", markup=False)
        return EXIT_USAGE

    if getattr(args, "json", False):
        payload = {
            "entry_id": result.entry_id,
            "roadmap_id": result.roadmap_id,
            "decision_id": result.decision_id,
            "evidence_id": result.evidence_id,
        }
        console.print(json.dumps(payload, indent=2, sort_keys=True), markup=False)
    else:
        console.print(f"Promoted {result.entry_id} -> {result.roadmap_id}", markup=False)
    return EXIT_SUCCESS


def scratch_rebuild_index_command(args: Namespace) -> int:
    try:
        store = _resolve_store(args)
        index = store.rebuild_index()
    except Exception as exc:
        error_console.print(str(exc), style="red", markup=False)
        return EXIT_USAGE

    if getattr(args, "json", False):
        console.print(json.dumps(index.to_json(), indent=2, sort_keys=True), markup=False)
    else:
        console.print(f"Scratch index rebuilt ({len(index.entries)} entries)", markup=False)
    return EXIT_SUCCESS


__all__ = [
    "scratch_add_command",
    "scratch_list_command",
    "scratch_show_command",
    "scratch_promote_command",
    "scratch_rebuild_index_command",
]
