# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Work command handlers.

Implements CLI access to the 6-call Work Compiler API.
"""

from __future__ import annotations

import json
import os
from typing import Any, Literal

from rich.console import Console

from ..api import WorkCompiler
from ..coordination.schemas import ClaimedResource as Resource
from ..core.database_connection import get_db_manager
from ..logging import get_logger

logger = get_logger(__name__)
console = Console()


def _get_agent_id() -> str:
    """Get agent ID from env or default."""
    return os.environ.get("MC_AGENT_ID", "default")


def _get_work_compiler() -> WorkCompiler:
    """Get singleton WorkCompiler instance."""
    return WorkCompiler()


def _parse_resource(spec: str) -> Resource:
    """Parse TYPE:PATH resource spec into Resource."""
    if ":" not in spec:
        # Default to file type
        return Resource(type="file", path=spec)
    type_part, path_part = spec.split(":", 1)
    return Resource(type=type_part, path=path_part)


def cmd_work_claim(args: Any) -> int:
    """Handle: motus work claim <task_id>"""
    wc = _get_work_compiler()
    agent_id = getattr(args, "agent", None) or _get_agent_id()
    as_json = getattr(args, "json", False)

    # Parse resources
    resource_specs = getattr(args, "resources", None) or []
    resources = [_parse_resource(r) for r in resource_specs]

    # If no resources specified, use task_id as placeholder
    if not resources:
        resources = [Resource(type="task", path=args.task_id)]

    intent = getattr(args, "intent", None) or f"Work on {args.task_id}"
    ttl_s = getattr(args, "ttl", 3600)

    result = wc.claim_work(
        task_id=args.task_id,
        resources=resources,
        intent=intent,
        agent_id=agent_id,
        ttl_s=ttl_s,
    )

    if as_json:
        output = {
            "decision": result.decision.decision,
            "reason_code": result.decision.reason_code,
            "lease_id": result.lease.lease_id if result.lease else None,
            "message": result.decision.human_message,
        }
        console.print_json(json.dumps(output))
        return 0 if result.decision.decision == "GRANTED" else 1

    if result.decision.decision == "GRANTED":
        console.print(f"[green]Claimed: {args.task_id}[/green]")
        console.print(f"[cyan]Lease ID: {result.lease.lease_id}[/cyan]")
        console.print(f"[dim]Expires: {result.lease.expires_at.isoformat()}[/dim]")
        console.print(f"\n[dim]Next: motus work context {result.lease.lease_id}[/dim]")
    else:
        console.print(f"[red]{result.decision.human_message}[/red]")
        if result.decision.owner:
            console.print(f"[yellow]Held by: {result.decision.owner.agent_id}[/yellow]")

    return 0 if result.decision.decision == "GRANTED" else 1


def cmd_work_context(args: Any) -> int:
    """Handle: motus work context <lease_id>"""
    wc = _get_work_compiler()
    as_json = getattr(args, "json", False)
    intent = getattr(args, "intent", None)

    result = wc.get_context(args.lease_id, intent=intent)

    if as_json:
        output = {
            "decision": result.decision.decision,
            "reason_code": result.decision.reason_code,
            "lens": result.lens,
            "lease_status": result.lease.status if result.lease else None,
        }
        console.print_json(json.dumps(output, default=str))
        return 0 if result.decision.decision == "GRANTED" else 1

    if result.decision.decision == "GRANTED":
        console.print("[green]Context assembled[/green]")
        console.print(f"[dim]Lens version: {result.lens.get('lens_version', 'unknown')}[/dim]")
        console.print(f"[dim]Policy version: {result.lens.get('policy_version', 'unknown')}[/dim]")

        # Show resource specs count
        resource_specs = result.lens.get("resource_specs", [])
        policy_snippets = result.lens.get("policy_snippets", [])
        console.print(f"\nResources: {len(resource_specs)}")
        console.print(f"Policy snippets: {len(policy_snippets)}")

        # Show warnings if any
        warnings = result.lens.get("warnings", [])
        if warnings:
            console.print("\n[yellow]Warnings:[/yellow]")
            for w in warnings:
                console.print(f"  - {w.get('message', str(w))}")
    else:
        console.print(f"[red]{result.decision.human_message}[/red]")

    return 0 if result.decision.decision == "GRANTED" else 1


def cmd_work_outcome(args: Any) -> int:
    """Handle: motus work outcome <lease_id> <type>"""
    wc = _get_work_compiler()
    as_json = getattr(args, "json", False)

    result = wc.put_outcome(
        args.lease_id,
        args.outcome_type,
        path=getattr(args, "path", None),
        description=getattr(args, "description", None),
    )

    if as_json:
        output = {
            "accepted": result.accepted,
            "outcome_id": result.outcome_id,
            "message": result.message,
        }
        console.print_json(json.dumps(output))
        return 0 if result.accepted else 1

    if result.accepted:
        console.print(f"[green]Outcome registered: {result.outcome_id}[/green]")
        console.print(f"[dim]Type: {args.outcome_type}[/dim]")
    else:
        console.print(f"[red]{result.message}[/red]")

    return 0 if result.accepted else 1


def cmd_work_evidence(args: Any) -> int:
    """Handle: motus work evidence <lease_id> <type>"""
    wc = _get_work_compiler()
    as_json = getattr(args, "json", False)

    # Build test results if provided
    test_results = None
    if any([getattr(args, "passed", None), getattr(args, "failed", None), getattr(args, "skipped", None)]):
        test_results = {
            "passed": getattr(args, "passed", 0) or 0,
            "failed": getattr(args, "failed", 0) or 0,
            "skipped": getattr(args, "skipped", 0) or 0,
        }

    result = wc.record_evidence(
        args.lease_id,
        args.evidence_type,
        test_results=test_results,
        diff_summary=getattr(args, "diff", None),
        log_excerpt=getattr(args, "log", None),
    )

    if as_json:
        output = {
            "accepted": result.accepted,
            "evidence_id": result.evidence_id,
            "message": result.message,
        }
        console.print_json(json.dumps(output))
        return 0 if result.accepted else 1

    if result.accepted:
        console.print(f"[green]Evidence recorded: {result.evidence_id}[/green]")
        console.print(f"[dim]Type: {args.evidence_type}[/dim]")
    else:
        console.print(f"[red]{result.message}[/red]")

    return 0 if result.accepted else 1


def cmd_work_decision(args: Any) -> int:
    """Handle: motus work decision <lease_id> <text>"""
    wc = _get_work_compiler()
    as_json = getattr(args, "json", False)

    result = wc.record_decision(
        args.lease_id,
        args.decision_text,
        rationale=getattr(args, "rationale", None),
        alternatives_considered=getattr(args, "alternatives", None),
    )

    if as_json:
        output = {
            "accepted": result.accepted,
            "decision_id": result.decision_id,
            "message": result.message,
        }
        console.print_json(json.dumps(output))
        return 0 if result.accepted else 1

    if result.accepted:
        console.print(f"[green]Decision logged: {result.decision_id}[/green]")
    else:
        console.print(f"[red]{result.message}[/red]")

    return 0 if result.accepted else 1


def cmd_work_release(args: Any) -> int:
    """Handle: motus work release <lease_id> <outcome>"""
    wc = _get_work_compiler()
    as_json = getattr(args, "json", False)
    rollback: Literal["auto", "skip"] = "skip" if getattr(args, "no_rollback", False) else "auto"

    result = wc.release_work(
        args.lease_id,
        args.outcome,
        rollback=rollback,
    )

    if as_json:
        output = {
            "decision": result.decision.decision,
            "reason_code": result.decision.reason_code,
            "message": result.decision.human_message,
            "lease_status": result.lease.status if result.lease else None,
        }
        console.print_json(json.dumps(output, default=str))
        return 0 if result.decision.decision == "GRANTED" else 1

    if result.decision.decision == "GRANTED":
        console.print(f"[green]Released: {result.decision.reason_code}[/green]")
        if result.lease:
            console.print(f"[dim]Final status: {result.lease.status}[/dim]")
    else:
        console.print(f"[red]{result.decision.human_message}[/red]")

    return 0 if result.decision.decision == "GRANTED" else 1


def cmd_work_status(args: Any) -> int:
    """Handle: motus work status <lease_id>"""
    wc = _get_work_compiler()
    as_json = getattr(args, "json", False)

    # Get context to see lease status
    result = wc.get_context(args.lease_id)

    # Get recorded items
    outcomes = wc.get_outcomes(args.lease_id)
    evidence = wc.get_evidence(args.lease_id)
    decisions = wc.get_decisions(args.lease_id)

    if as_json:
        output = {
            "lease_id": args.lease_id,
            "lease_status": result.lease.status if result.lease else "not_found",
            "outcomes": outcomes,
            "evidence": evidence,
            "decisions": decisions,
        }
        console.print_json(json.dumps(output, default=str))
        return 0

    if result.lease is None:
        console.print(f"[red]Lease not found: {args.lease_id}[/red]")
        return 1

    console.print(f"[bold]Lease: {args.lease_id}[/bold]")
    console.print(f"Status: {result.lease.status}")
    console.print(f"Agent: {result.lease.owner_agent_id}")
    console.print(f"Expires: {result.lease.expires_at.isoformat()}")

    if outcomes:
        console.print(f"\n[cyan]Outcomes ({len(outcomes)}):[/cyan]")
        for o in outcomes:
            console.print(f"  - {o['outcome_type']}: {o.get('path', o.get('description', 'N/A'))}")

    if evidence:
        console.print(f"\n[cyan]Evidence ({len(evidence)}):[/cyan]")
        for e in evidence:
            console.print(f"  - {e['evidence_type']}: {e['evidence_id']}")

    if decisions:
        console.print(f"\n[cyan]Decisions ({len(decisions)}):[/cyan]")
        for d in decisions:
            console.print(f"  - {d['decision']}")

    return 0


def cmd_work_cleanup(args: Any) -> int:
    """Handle: motus work cleanup"""
    wc = _get_work_compiler()
    as_json = getattr(args, "json", False)

    expired_count = wc.cleanup_leases()

    if as_json:
        output = {
            "expired_count": expired_count,
        }
        console.print_json(json.dumps(output))
        return 0

    console.print(f"[green]Expired leases: {expired_count}[/green]")
    return 0


def cmd_work_list(args: Any) -> int:
    """Handle: motus work list"""
    db = get_db_manager()
    as_json = getattr(args, "json", False)
    include_all = getattr(args, "all", False)

    with db.readonly_connection() as conn:
        table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'coordination_leases'"
        ).fetchone()
        if table is None:
            if as_json:
                console.print_json(json.dumps({"items": [], "count": 0}))
            else:
                console.print("[yellow]No leases found.[/yellow]")
            return 0

        if include_all:
            query = """
                SELECT lease_id, owner_agent_id, work_id, issued_at, expires_at, status
                FROM coordination_leases
                ORDER BY issued_at DESC
            """
            params: tuple[Any, ...] = ()
        else:
            query = """
                SELECT lease_id, owner_agent_id, work_id, issued_at, expires_at, status
                FROM coordination_leases
                WHERE status = 'active'
                AND expires_at > mc_now_iso()
                AND heartbeat_deadline > mc_now_iso()
                ORDER BY issued_at DESC
            """
            params = ()

        rows = conn.execute(query, params).fetchall()

    items = [
        {
            "lease_id": r["lease_id"],
            "task_id": r["work_id"],
            "agent_id": r["owner_agent_id"],
            "claimed_at": r["issued_at"],
            "expires_at": r["expires_at"],
            "status": r["status"],
        }
        for r in rows
    ]

    if as_json:
        console.print_json(json.dumps({"items": items, "count": len(items)}))
        return 0

    if not items:
        console.print("[yellow]No leases found.[/yellow]")
        return 0

    from rich.table import Table

    table = Table(title="Active Leases" if not include_all else "Leases")
    table.add_column("Lease ID", style="dim")
    table.add_column("Task ID")
    table.add_column("Agent")
    table.add_column("Claimed")
    table.add_column("Expires")
    table.add_column("Status", style="dim")

    for item in items:
        table.add_row(
            item["lease_id"],
            item["task_id"] or "-",
            item["agent_id"],
            item["claimed_at"],
            item["expires_at"],
            item["status"],
        )

    console.print(table)
    return 0


def handle_work_command(args: Any) -> int:
    """Dispatch work subcommand."""
    subcommand = getattr(args, "work_command", None)

    if subcommand == "claim":
        return cmd_work_claim(args)
    elif subcommand == "context":
        return cmd_work_context(args)
    elif subcommand == "outcome":
        return cmd_work_outcome(args)
    elif subcommand == "evidence":
        return cmd_work_evidence(args)
    elif subcommand == "decision":
        return cmd_work_decision(args)
    elif subcommand == "release":
        return cmd_work_release(args)
    elif subcommand == "status":
        return cmd_work_status(args)
    elif subcommand == "cleanup":
        return cmd_work_cleanup(args)
    elif subcommand == "list":
        return cmd_work_list(args)
    else:
        console.print(
            "[yellow]Usage: motus work <claim|context|outcome|evidence|decision|release|status|cleanup|list>[/yellow]"
        )
        console.print("\nThe 6-call Work Compiler protocol:")
        console.print("  1. motus work claim <task_id>     - Claim work, get lease")
        console.print("  2. motus work context <lease_id>  - Get context (Lens)")
        console.print("  3. motus work outcome <lease_id>  - Register deliverable")
        console.print("  4. motus work evidence <lease_id> - Record verification")
        console.print("  5. motus work decision <lease_id> - Log decision")
        console.print("  6. motus work release <lease_id>  - Release with outcome")
        return 0
