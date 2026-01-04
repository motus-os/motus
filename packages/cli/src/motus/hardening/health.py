# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Health check framework and persistence.

Results are stored in the `health_check_results` table.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict

from motus.core.database import DatabaseManager, get_db_manager


class HealthStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


@dataclass(frozen=True)
class HealthResult:
    name: str
    status: HealthStatus
    message: str | None = None
    details: Dict[str, Any] | None = None
    duration_ms: float | None = None


HealthCheck = Callable[[], HealthResult]


class HealthChecker:
    def __init__(self, *, db: DatabaseManager | None = None) -> None:
        self._db = db or get_db_manager()
        self._checks: list[HealthCheck] = []

    def register(self, check: HealthCheck) -> None:
        self._checks.append(check)

    def run_all(self) -> list[HealthResult]:
        results: list[HealthResult] = []
        for check in self._checks:
            start = time.monotonic()
            try:
                result = check()
                duration_ms = (time.monotonic() - start) * 1000
                results.append(
                    HealthResult(
                        name=result.name,
                        status=result.status,
                        message=result.message,
                        details=result.details,
                        duration_ms=duration_ms,
                    )
                )
            except Exception as exc:
                duration_ms = (time.monotonic() - start) * 1000
                results.append(
                    HealthResult(
                        name=getattr(check, "__name__", "health_check"),
                        status=HealthStatus.FAIL,
                        message=str(exc),
                        details=None,
                        duration_ms=duration_ms,
                    )
                )
        return results

    def persist(self, results: list[HealthResult]) -> None:
        with self._db.transaction() as conn:
            for r in results:
                conn.execute(
                    """
                    INSERT INTO health_check_results
                        (check_name, status, message, details, duration_ms)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        r.name,
                        r.status.value,
                        r.message,
                        json.dumps(r.details, sort_keys=True) if r.details is not None else None,
                        r.duration_ms,
                    ),
                )
