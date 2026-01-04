# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Claims policy API for deploy readiness."""

from __future__ import annotations

from dataclasses import dataclass

from .database_connection import get_db_manager


@dataclass
class DeployStatus:
    """Deployment readiness response."""

    can_deploy: bool
    status: str
    blockers: list[str]
    action: str
    command: str


def can_deploy() -> DeployStatus:
    """Check if website can be deployed (all claims verified)."""
    db = get_db_manager()
    with db.connection() as conn:
        row = conn.execute("SELECT * FROM v_can_deploy").fetchone()

        if row["status"] == "BLOCKED":
            failed_claims = row["failed_claims"].split(", ") if row["failed_claims"] else []
            return DeployStatus(
                can_deploy=False,
                status="BLOCKED",
                blockers=failed_claims,
                action=f"Fix {row['failed_count']} failing claim tests",
                command="pytest -k claim",
            )
        if row["status"] == "PENDING":
            return DeployStatus(
                can_deploy=False,
                status="PENDING",
                blockers=[],
                action="Run tests to verify pending claims",
                command="pytest -k claim",
            )
        return DeployStatus(
            can_deploy=True,
            status="READY",
            blockers=[],
            action="Deploy when ready",
            command="make deploy",
        )
