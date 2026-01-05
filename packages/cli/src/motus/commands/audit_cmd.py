# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""CLI command: `motus audit` utilities."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from rich.console import Console

from motus.cli.exit_codes import EXIT_SUCCESS, EXIT_USAGE
from motus.core.database_connection import get_db_manager
from motus.observability.audit import AuditEvent, AuditLogger

console = Console()


@dataclass(frozen=True, slots=True)
class AuditFinding:
    finding_id: str
    title: str
    description: str
    severity: str
    evidence: list[str]


def _get_agent_id() -> str:
    return os.environ.get("MC_AGENT_ID", "").strip() or "user"


def _get_actor() -> str:
    agent_id = _get_agent_id()
    if agent_id == "user":
        return "user"
    return f"agent:{agent_id}"


def _utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _next_id(conn, *, prefix: str, table: str, column: str = "id") -> str:
    like = f"{prefix}-%"
    row = conn.execute(
        f"SELECT {column} FROM {table} WHERE {column} LIKE ? ORDER BY {column} DESC LIMIT 1",
        (like,),
    ).fetchone()
    if row and row[0]:
        last = str(row[0])
        try:
            suffix = int(last.rsplit("-", 1)[-1])
        except ValueError:
            suffix = 0
    else:
        suffix = 0
    return f"{prefix}-{suffix + 1:03d}"


def _next_finding_id(conn) -> str:
    prefix = f"AF-{_utc_today()}"
    row = conn.execute(
        """
        SELECT resource_id
        FROM audit_log
        WHERE resource_type = ? AND resource_id LIKE ?
        ORDER BY resource_id DESC
        LIMIT 1
        """,
        ("audit_finding", f"{prefix}-%"),
    ).fetchone()
    if row and row[0]:
        last = str(row[0])
        try:
            suffix = int(last.rsplit("-", 1)[-1])
        except ValueError:
            suffix = 0
    else:
        suffix = 0
    return f"{prefix}-{suffix + 1:03d}"


def _fetch_finding(conn, finding_id: str) -> AuditFinding:
    row = conn.execute(
        """
        SELECT new_value
        FROM audit_log
        WHERE resource_type = ? AND resource_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        ("audit_finding", finding_id),
    ).fetchone()
    if not row or not row[0]:
        raise ValueError(f"Audit finding not found: {finding_id}")
    payload = json.loads(row[0])
    return AuditFinding(
        finding_id=str(payload.get("finding_id") or finding_id),
        title=str(payload.get("title") or ""),
        description=str(payload.get("description") or ""),
        severity=str(payload.get("severity") or "medium"),
        evidence=list(payload.get("evidence") or []),
    )


def _severity_to_cr_type(severity: str) -> str:
    severity_norm = severity.lower().strip()
    if severity_norm in {"high", "critical"}:
        return "defect"
    return "enhancement"


def _format_description(finding: AuditFinding) -> str:
    parts = [f"[AuditFinding:{finding.finding_id}] {finding.description}".strip()]
    if finding.evidence:
        parts.append("Evidence:")
        parts.extend(f"- {item}" for item in finding.evidence)
    return "\n".join(p for p in parts if p)


def audit_add_command(args: Any) -> int:
    title = (getattr(args, "title", "") or "").strip()
    if not title:
        console.print("[red]Title is required[/red]")
        return EXIT_USAGE

    description = (getattr(args, "description", "") or "").strip()
    severity = (getattr(args, "severity", "medium") or "medium").lower().strip()
    evidence = list(getattr(args, "evidence", []) or [])

    if severity not in {"low", "medium", "high", "critical"}:
        console.print("[red]Severity must be low|medium|high|critical[/red]")
        return EXIT_USAGE

    db = get_db_manager()
    with db.connection() as conn:
        finding_id = _next_finding_id(conn)

    finding = {
        "finding_id": finding_id,
        "title": title,
        "description": description,
        "severity": severity,
        "evidence": evidence,
        "created_by": _get_agent_id(),
    }

    AuditLogger().emit(
        AuditEvent(
            event_type="audit.finding",
            actor=_get_actor(),
            action="create",
            resource_type="audit_finding",
            resource_id=finding_id,
            new_value=finding,
        )
    )

    if getattr(args, "json", False):
        console.print_json(json.dumps({"finding_id": finding_id, **finding}))
    else:
        console.print(f"Audit finding created: {finding_id}")
    return EXIT_SUCCESS


def audit_promote_command(args: Any) -> int:
    finding_id = (getattr(args, "finding_id", "") or "").strip()
    if not finding_id:
        console.print("[red]finding_id is required[/red]")
        return EXIT_USAGE

    promote_cr = bool(getattr(args, "cr", False))
    promote_roadmap = bool(getattr(args, "roadmap", False))
    if not promote_cr and not promote_roadmap:
        console.print("[red]Specify --cr and/or --roadmap[/red]")
        return EXIT_USAGE

    db = get_db_manager()
    with db.connection() as conn:
        finding = _fetch_finding(conn, finding_id)

        cr_id = None
        if promote_cr:
            cr_prefix = f"CR-{_utc_today()}"
            cr_id = _next_id(conn, prefix=cr_prefix, table="change_requests")
            cr_title = (getattr(args, "title", None) or "").strip() or f"Audit: {finding.title}"
            cr_description = (getattr(args, "description", None) or "").strip() or _format_description(finding)
            cr_type = _severity_to_cr_type(finding.severity)
            conn.execute(
                """
                INSERT INTO change_requests (
                    id, title, description, status_key, type_key, size, owner
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cr_id,
                    cr_title,
                    cr_description,
                    "queue",
                    cr_type,
                    "M",
                    _get_agent_id(),
                ),
            )
            AuditLogger().emit(
                AuditEvent(
                    event_type="audit.promote",
                    actor=_get_actor(),
                    action="create",
                    resource_type="change_request",
                    resource_id=cr_id,
                    context={"finding_id": finding_id},
                )
            )

        if promote_roadmap:
            phase_key = (getattr(args, "phase", "phase_h") or "phase_h").strip()
            item_type = (getattr(args, "item_type", "work") or "work").strip()
            roadmap_prefix = f"RI-AUD-{_utc_today()}"
            roadmap_id = _next_id(conn, prefix=roadmap_prefix, table="roadmap_items")

            resolved_cr_id = (getattr(args, "cr_id", None) or "").strip() or cr_id
            if not resolved_cr_id:
                row = conn.execute(
                    """
                    SELECT id FROM change_requests
                    WHERE description LIKE ? AND deleted_at IS NULL
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (f"%AuditFinding:{finding_id}%",),
                ).fetchone()
                if row:
                    resolved_cr_id = row[0]

            if not resolved_cr_id:
                raise ValueError("No CR found for finding; pass --cr-id or run --cr first")

            rm_title = (getattr(args, "title", None) or "").strip() or f"Audit: {finding.title}"
            rm_description = (getattr(args, "description", None) or "").strip() or _format_description(finding)

            conn.execute(
                """
                INSERT INTO roadmap_items (
                    id, phase_key, title, description, status_key, owner, item_type, cr_id, created_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    roadmap_id,
                    phase_key,
                    rm_title,
                    rm_description,
                    "pending",
                    _get_agent_id(),
                    item_type,
                    resolved_cr_id,
                    _get_agent_id(),
                ),
            )
            AuditLogger().emit(
                AuditEvent(
                    event_type="audit.promote",
                    actor=_get_actor(),
                    action="create",
                    resource_type="roadmap_item",
                    resource_id=roadmap_id,
                    context={"finding_id": finding_id, "cr_id": resolved_cr_id},
                )
            )

    if getattr(args, "json", False):
        payload = {
            "finding_id": finding_id,
            "cr_id": cr_id,
        }
        console.print_json(json.dumps(payload))
    else:
        if promote_cr:
            console.print(f"CR created for finding {finding_id}: {cr_id}")
        if promote_roadmap:
            console.print(f"Roadmap item created for finding {finding_id}")

    return EXIT_SUCCESS


def audit_list_command(args: Any) -> int:
    limit = getattr(args, "limit", 50)
    as_json = getattr(args, "json", False)

    db = get_db_manager()
    with db.connection(read_only=True) as conn:
        rows = conn.execute(
            """
            SELECT resource_id, new_value, timestamp
            FROM audit_log
            WHERE resource_type = ? AND action = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            ("audit_finding", "create", int(limit)),
        ).fetchall()

    findings = []
    for row in rows:
        payload = {}
        if row[1]:
            try:
                payload = json.loads(row[1])
            except json.JSONDecodeError:
                payload = {}
        findings.append(
            {
                "finding_id": row[0],
                "title": payload.get("title"),
                "severity": payload.get("severity"),
                "created_at": row[2],
            }
        )

    if as_json:
        console.print_json(json.dumps({"items": findings, "count": len(findings)}))
        return EXIT_SUCCESS

    if not findings:
        console.print("No audit findings recorded.")
        return EXIT_SUCCESS

    for item in findings:
        console.print(
            f"{item['finding_id']}: {item['title']} ({item['severity']})",
            markup=False,
        )
    return EXIT_SUCCESS
