"""CLI command: `mc doctor` (health diagnostics)."""

from __future__ import annotations

import json
from typing import Any, Dict

from rich.console import Console

from motus.cli.exit_codes import EXIT_ERROR, EXIT_SUCCESS
from motus.core import get_db_manager, verify_schema_version
from motus.hardening.health import HealthChecker, HealthResult, HealthStatus


def _db_check() -> HealthResult:
    db = get_db_manager()
    with db.connection() as conn:
        verify_schema_version(conn)
        status, wal_size = db.check_wal_size()
    if status == "ok":
        return HealthResult(
            name="database",
            status=HealthStatus.PASS,
            message="database OK",
            details={"wal_status": status, "wal_size_bytes": wal_size},
        )
    return HealthResult(
        name="database",
        status=HealthStatus.WARN,
        message="WAL size warning" if status == "warning" else "WAL checkpoint forced",
        details={"wal_status": status, "wal_size_bytes": wal_size},
    )


def doctor_command(*, json_output: bool = False) -> int:
    console = Console()
    checker = HealthChecker()
    checker.register(_db_check)
    results = checker.run_all()
    checker.persist(results)

    worst = HealthStatus.PASS
    for r in results:
        if r.status == HealthStatus.FAIL:
            worst = HealthStatus.FAIL
            break
        if r.status == HealthStatus.WARN:
            worst = HealthStatus.WARN

    if json_output:
        payload: Dict[str, Any] = {
            "status": worst.value,
            "checks": [
                {
                    "name": r.name,
                    "status": r.status.value,
                    "message": r.message,
                    "details": r.details,
                    "duration_ms": r.duration_ms,
                }
                for r in results
            ],
        }
        console.print(json.dumps(payload, sort_keys=True), markup=False)
    else:
        for r in results:
            msg = f"{r.name}: {r.status.value}"
            if r.message:
                msg += f" - {r.message}"
            console.print(msg, markup=False)
        console.print(f"overall: {worst.value}", markup=False)

    return EXIT_SUCCESS if worst != HealthStatus.FAIL else EXIT_ERROR
