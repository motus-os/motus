# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Roadmap command handlers.

Provides CLI access to the frictionless roadmap API.
Database is source of truth. ROADMAP.md is backup/export.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from rich.console import Console
from rich.table import Table

from ..core.database_connection import get_db_manager
from ..core.roadmap import RoadmapAPI, RoadmapResponse
from ..logging import get_logger

logger = get_logger(__name__)
console = Console()


def _get_agent_id() -> str:
    """Get agent ID from env or default."""
    return os.environ.get("MC_AGENT_ID", "default")


def _print_response(response: RoadmapResponse, as_json: bool = False) -> int:
    """Print response in appropriate format."""
    if as_json:
        output = {
            "success": response.success,
            "message": response.message,
            "action": response.action,
            "command": response.command,
            "blockers": response.blockers,
            "data": response.data if not hasattr(response.data, "__dict__") else None,
        }
        console.print_json(json.dumps(output, default=str))
    else:
        if response.success:
            console.print(f"[green]{response.message}[/green]")
        else:
            console.print(f"[red]{response.message}[/red]")

        if response.blockers:
            console.print("\n[yellow]Blockers:[/yellow]")
            for b in response.blockers:
                console.print(f"  - {b}")

        if response.action:
            console.print(f"\n[dim]Next: {response.action}[/dim]")
        if response.command:
            console.print(f"[dim]Run: {response.command}[/dim]")

    return 0 if response.success else 1


def _map_status_to_lifecycle(status: str) -> str:
    """Map status_key to KERNEL-SCHEMA lifecycle_status terminology.

    KERNEL-SCHEMA v0.1.3 uses lifecycle_status with values:
    pending, in_progress, blocked, completed

    Legacy status_key values map as:
    - pending -> pending
    - in_progress -> in_progress
    - blocked -> blocked
    - completed -> completed
    - review -> in_progress (review is a sub-state of in_progress)
    - superseded -> completed (superseded items are effectively done)
    - deferred -> pending (deferred items return to pending)
    """
    mapping = {
        "pending": "pending",
        "in_progress": "in_progress",
        "blocked": "blocked",
        "completed": "completed",
        "review": "in_progress",
        "superseded": "completed",
        "deferred": "pending",
    }
    return mapping.get(status, status)


def _map_item_type_to_task_type(item_type: str) -> str:
    """Map item_type to KERNEL-SCHEMA task_type terminology.

    KERNEL-SCHEMA v0.1.3 task_type values:
    action, milestone, deliverable, gate, decision, risk, assumption, issue, dependency

    Legacy item_type values map as:
    - work -> action
    - gate -> gate
    - holding -> decision (holding patterns become decisions)
    - integration -> deliverable (integration items produce deliverables)
    """
    mapping = {
        "work": "action",
        "gate": "gate",
        "holding": "decision",
        "integration": "deliverable",
    }
    return mapping.get(item_type, item_type)


def cmd_roadmap_list(args: Any) -> int:
    """List all roadmap items by phase."""
    db = get_db_manager()

    include_deleted = getattr(args, "all", False)
    phase_filter = getattr(args, "phase", None)
    as_json = getattr(args, "json", False)

    with db.connection() as conn:
        query = """
            SELECT ri.id, ri.title, ri.phase_key, ri.status_key, ri.item_type, ri.deleted_at,
                   COUNT(rd.depends_on_id) as dep_count
            FROM roadmap_items ri
            LEFT JOIN roadmap_dependencies rd ON rd.item_id = ri.id
            WHERE 1=1
        """
        params: list[Any] = []

        if not include_deleted:
            query += " AND deleted_at IS NULL"

        if phase_filter:
            query += " AND phase_key = ?"
            params.append(phase_filter)

        query += """
            GROUP BY ri.id, ri.title, ri.phase_key, ri.status_key, ri.item_type, ri.deleted_at
            ORDER BY ri.phase_key, ri.status_key, ri.id
        """

        rows = conn.execute(query, params).fetchall()

    if as_json:
        items = [
            {
                "id": r["id"],
                "title": r["title"],
                "phase": r["phase_key"],
                # KERNEL-SCHEMA v0.1.3 terminology
                "lifecycle_status": _map_status_to_lifecycle(r["status_key"]),
                "task_type": _map_item_type_to_task_type(r["item_type"] if r["item_type"] else "work"),
                # Legacy fields (for backward compatibility)
                "status": r["status_key"],
                "deleted": r["deleted_at"] is not None,
            }
            for r in rows
        ]
        console.print_json(json.dumps({"items": items, "count": len(items)}))
        return 0

    # Group by phase
    phases: dict[str, list] = {}
    for row in rows:
        phase = row["phase_key"]
        if phase not in phases:
            phases[phase] = []
        phases[phase].append(row)

    # Print summary
    total = len(rows)
    completed = sum(1 for r in rows if r["status_key"] == "completed")
    deleted = sum(1 for r in rows if r["deleted_at"])

    console.print(f"\n[bold]Roadmap: {total} items[/bold]")
    console.print(f"  Completed: {completed}  |  Active: {total - completed - deleted}")
    if deleted:
        console.print(f"  [dim]Deleted: {deleted}[/dim]")
    console.print()

    # Print by phase
    for phase in sorted(phases.keys()):
        items = phases[phase]
        phase_completed = sum(1 for i in items if i["status_key"] == "completed")

        table = Table(title=f"{phase} ({phase_completed}/{len(items)} done)")
        table.add_column("ID", style="dim")
        table.add_column("Title")
        table.add_column("Type", style="dim")
        table.add_column("Lifecycle")

        for item in items:
            # Map to KERNEL-SCHEMA terminology
            lifecycle = _map_status_to_lifecycle(item["status_key"])
            task_type = _map_item_type_to_task_type(item["item_type"] if item["item_type"] else "work")

            # Format lifecycle status for display
            if item["deleted_at"]:
                lifecycle_display = "[dim strikethrough]deleted[/dim strikethrough]"
            elif lifecycle == "completed":
                lifecycle_display = "[green]completed[/green]"
            elif lifecycle == "in_progress":
                lifecycle_display = "[yellow]in_progress[/yellow]"
            elif lifecycle == "blocked":
                lifecycle_display = "[red]blocked[/red]"
            else:
                lifecycle_display = lifecycle

            # Format task type
            type_display = f"[dim]{task_type}[/dim]"
            if task_type == "gate":
                type_display = "[magenta]gate[/magenta]"

            table.add_row(item["id"], item["title"], type_display, lifecycle_display)

        console.print(table)
        console.print()

    return 0


def cmd_roadmap_ready(args: Any) -> int:
    """Show items ready to work on."""
    api = RoadmapAPI(_get_agent_id())
    response = api.ready()
    as_json = getattr(args, "json", False)

    if as_json:
        return _print_response(response, as_json=True)

    if not response.data:
        console.print("[yellow]No items ready - all have blocking dependencies[/yellow]")
        console.print("[dim]Run: motus roadmap --phase phase_c[/dim]")
        return 0

    table = Table(title=f"Ready to Work ({len(response.data)} items)")
    table.add_column("ID", style="cyan")
    table.add_column("Title")
    table.add_column("Rank", justify="right")

    for item in response.data:
        table.add_row(item.id, item.title, f"{item.rank:.1f}")

    console.print(table)
    console.print(f"\n[dim]{response.action}[/dim]")
    console.print(f"[dim]Run: {response.command}[/dim]")

    return 0


def cmd_roadmap_claim(args: Any) -> int:
    """Claim an item for work.

    DEPRECATED: Use `motus work claim` instead for full Work Compiler support.
    This command will be removed in v0.2.0.
    """
    console.print(
        "[yellow]DEPRECATED: 'motus roadmap claim' will be removed in v0.2.0[/yellow]"
    )
    console.print("[yellow]Use 'motus work claim <id> --intent \"...\"' instead[/yellow]")
    console.print()

    agent_id = getattr(args, "agent", None) or _get_agent_id()
    api = RoadmapAPI(agent_id)
    response = api.claim(args.item_id)
    return _print_response(response)


def cmd_roadmap_complete(args: Any) -> int:
    """Mark item as complete."""
    api = RoadmapAPI(_get_agent_id())
    response = api.complete(args.item_id)
    return _print_response(response)


def cmd_roadmap_status(args: Any) -> int:
    """Get detailed status of an item."""
    api = RoadmapAPI(_get_agent_id())
    response = api.status(args.item_id)
    as_json = getattr(args, "json", False)
    return _print_response(response, as_json=as_json)


def cmd_roadmap_release(args: Any) -> int:
    """Release claim without completing."""
    api = RoadmapAPI(_get_agent_id())
    response = api.release(args.item_id)
    return _print_response(response)


def cmd_roadmap_my_work(args: Any) -> int:
    """Show items assigned to this agent."""
    api = RoadmapAPI(_get_agent_id())
    response = api.my_work()
    as_json = getattr(args, "json", False)

    if as_json:
        return _print_response(response, as_json=True)

    if not response.data:
        console.print("[dim]No items assigned to you[/dim]")
        console.print("[dim]Run: motus roadmap ready[/dim]")
        return 0

    table = Table(title=f"Your Work ({len(response.data)} items)")
    table.add_column("ID", style="cyan")
    table.add_column("Title")
    table.add_column("Lifecycle")

    for item in response.data:
        lifecycle = _map_status_to_lifecycle(item.status)
        table.add_row(item.id, item.title, lifecycle)

    console.print(table)
    console.print(f"\n[dim]{response.action}[/dim]")

    return 0


def cmd_roadmap_export(args: Any) -> int:
    """Export roadmap to markdown."""
    db = get_db_manager()
    include_deleted = getattr(args, "include_deleted", False)
    output_file = getattr(args, "output", None)

    with db.connection() as conn:
        query = """
            SELECT id, title, phase_key, status_key, deleted_at
            FROM roadmap_items
            WHERE 1=1
        """
        if not include_deleted:
            query += " AND deleted_at IS NULL"
        # Sort: pending items first (alphabetically), then completed
        query += " ORDER BY phase_key, CASE WHEN status_key = 'completed' THEN 1 ELSE 0 END, id"

        rows = conn.execute(query).fetchall()

    # Group by phase
    phases: dict[str, list] = {}
    for row in rows:
        phase = row["phase_key"]
        if phase not in phases:
            phases[phase] = []
        phases[phase].append(row)

    # Generate markdown
    lines = [
        "# Roadmap Export",
        "",
        f"**Generated**: {datetime.now().isoformat()}",
        f"**Total Items**: {len(rows)}",
        "",
        "---",
        "",
    ]

    for phase in sorted(phases.keys()):
        items = phases[phase]
        completed = sum(1 for i in items if i["status_key"] == "completed")
        lines.append(f"## {phase} ({completed}/{len(items)} complete)")
        lines.append("")

        for item in items:
            checkbox = "[x]" if item["status_key"] == "completed" else "[ ]"
            deleted = " ~~DELETED~~" if item["deleted_at"] else ""
            lines.append(f"- {checkbox} {item['id']}: {item['title']}{deleted}")

        lines.append("")

    content = "\n".join(lines)

    if output_file:
        with open(output_file, "w") as f:
            f.write(content)
        console.print(f"[green]Exported to {output_file}[/green]")
    else:
        console.print(content)

    return 0


def cmd_roadmap_delete(args: Any) -> int:
    """Soft-delete an item (rebaseline)."""
    db = get_db_manager()
    item_id = args.item_id
    reason = getattr(args, "reason", None)

    with db.transaction() as conn:
        # Check item exists
        item = conn.execute(
            "SELECT id, title, deleted_at FROM roadmap_items WHERE id = ?",
            (item_id,),
        ).fetchone()

        if not item:
            console.print(f"[red]Item '{item_id}' not found[/red]")
            return 1

        if item["deleted_at"]:
            console.print("[yellow]Item already deleted[/yellow]")
            return 0

        # Soft delete
        conn.execute(
            """
            UPDATE roadmap_items
            SET deleted_at = datetime('now'),
                deleted_by = ?,
                deletion_reason = ?
            WHERE id = ?
            """,
            (_get_agent_id(), reason or "rebaseline", item_id),
        )

    console.print(f"[green]Deleted: {item['title']}[/green]")
    console.print("[dim]Item removed from active roadmap but kept for audit[/dim]")

    return 0


def cmd_roadmap_review(args: Any) -> int:
    """Request review for a roadmap item."""
    db = get_db_manager()
    item_id = args.item_id
    comment = getattr(args, "comment", None)
    as_json = getattr(args, "json", False)

    with db.transaction() as conn:
        item = conn.execute(
            "SELECT id, title, status_key, deleted_at FROM roadmap_items WHERE id = ?",
            (item_id,),
        ).fetchone()

        if not item:
            if as_json:
                console.print_json(json.dumps({"success": False, "error": "Item not found"}))
            else:
                console.print(f"[red]Item '{item_id}' not found[/red]")
            return 1

        if item["deleted_at"]:
            if as_json:
                console.print_json(json.dumps({"success": False, "error": "Item is deleted"}))
            else:
                console.print("[red]Item is deleted[/red]")
            return 1

        if item["status_key"] == "completed":
            if as_json:
                console.print_json(
                    json.dumps({"success": True, "message": "Item already completed"})
                )
            else:
                console.print("[yellow]Item already completed[/yellow]")
            return 0

        if item["status_key"] == "review":
            if as_json:
                console.print_json(
                    json.dumps({"success": True, "message": "Item already in review"})
                )
            else:
                console.print("[yellow]Item already in review[/yellow]")
            return 0

        conn.execute(
            "UPDATE roadmap_items SET status_key = 'review', updated_at = datetime('now') WHERE id = ?",
            (item_id,),
        )

    if as_json:
        console.print_json(
            json.dumps(
                {
                    "success": True,
                    "item_id": item["id"],
                    "title": item["title"],
                    "lifecycle_status": "in_progress",
                    "message": "Review requested",
                    "comment": comment,
                }
            )
        )
    else:
        console.print(f"[green]Review requested: {item['title']}[/green]")
        if comment:
            console.print(f"[dim]Comment: {comment}[/dim]")
        console.print("[dim]Status changed to 'review' (lifecycle: in_progress)[/dim]")

    return 0


def handle_roadmap_command(args: Any) -> int:
    """Dispatch roadmap subcommand."""
    subcommand = getattr(args, "roadmap_command", None)

    if subcommand == "ready":
        return cmd_roadmap_ready(args)
    elif subcommand == "claim":
        return cmd_roadmap_claim(args)
    elif subcommand == "complete":
        return cmd_roadmap_complete(args)
    elif subcommand == "status":
        return cmd_roadmap_status(args)
    elif subcommand == "release":
        return cmd_roadmap_release(args)
    elif subcommand == "my-work":
        return cmd_roadmap_my_work(args)
    elif subcommand == "export":
        return cmd_roadmap_export(args)
    elif subcommand == "delete":
        return cmd_roadmap_delete(args)
    else:
        # Default: list all items
        return cmd_roadmap_list(args)
