# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Circuit breaker implementation backed by the Motus database.

State is stored in the `circuit_breakers` table (Phase 0 schema).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional, TypeVar

from motus.core.database import DatabaseManager, get_db_manager

T = TypeVar("T")


class CircuitOpenError(RuntimeError):
    """Raised when a circuit is open and calls are rejected."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(value: str | None) -> Optional[datetime]:
    if not value:
        return None
    # Accept both sqlite datetime('now') format and ISO8601.
    # Example sqlite: "2025-12-19 09:21:00"
    if "T" not in value and value.endswith("Z") is False and " " in value:
        try:
            dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _format_ts(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class CircuitBreakerState:
    name: str
    state: str
    failure_count: int
    success_count: int
    opened_at: Optional[datetime]
    failure_threshold: int
    recovery_timeout_seconds: int

    @property
    def is_open(self) -> bool:
        return self.state == "open"

    @property
    def is_half_open(self) -> bool:
        return self.state == "half_open"

    @property
    def is_closed(self) -> bool:
        return self.state == "closed"


class CircuitBreaker:
    """Database-backed circuit breaker for a named subsystem/service."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(
        self,
        name: str,
        *,
        db: DatabaseManager | None = None,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        self.name = name
        self._db = db or get_db_manager()
        self._now = now
        self.ensure_exists()

    def ensure_exists(self) -> None:
        with self._db.transaction() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO circuit_breakers (name) VALUES (?)",
                (self.name,),
            )

    def get_state(self) -> CircuitBreakerState:
        with self._db.connection() as conn:
            row = conn.execute(
                """
                SELECT
                    name, state, failure_count, success_count,
                    opened_at, failure_threshold, recovery_timeout_seconds
                FROM circuit_breakers
                WHERE name = ?
                """,
                (self.name,),
            ).fetchone()
            if not row:
                raise KeyError(f"circuit_breakers missing row for {self.name!r}")

        return CircuitBreakerState(
            name=row["name"],
            state=row["state"],
            failure_count=int(row["failure_count"]),
            success_count=int(row["success_count"]),
            opened_at=_parse_ts(row["opened_at"]),
            failure_threshold=int(row["failure_threshold"]),
            recovery_timeout_seconds=int(row["recovery_timeout_seconds"]),
        )

    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute `func` under circuit breaker control."""
        self._maybe_transition_open_to_half_open()

        state = self.get_state()
        if state.is_open:
            raise CircuitOpenError(f"{self.name} circuit is open")

        try:
            result = func(*args, **kwargs)
        except Exception as exc:
            self.record_failure()
            raise exc
        else:
            self.record_success()
            return result

    def record_success(self) -> None:
        now = _format_ts(self._now())
        with self._db.transaction() as conn:
            conn.execute(
                """
                UPDATE circuit_breakers
                SET
                    state = ?,
                    failure_count = 0,
                    success_count = success_count + 1,
                    last_success_at = ?,
                    last_failure_at = last_failure_at,
                    opened_at = NULL,
                    updated_at = ?
                WHERE name = ?
                """,
                (self.CLOSED, now, now, self.name),
            )

    def record_failure(self) -> None:
        now_dt = self._now()
        now = _format_ts(now_dt)

        with self._db.transaction() as conn:
            row = conn.execute(
                """
                SELECT state, failure_count, failure_threshold
                FROM circuit_breakers
                WHERE name = ?
                """,
                (self.name,),
            ).fetchone()
            if not row:
                raise KeyError(f"circuit_breakers missing row for {self.name!r}")

            failure_count = int(row["failure_count"]) + 1
            threshold = int(row["failure_threshold"])
            next_state = row["state"]
            opened_at = None

            if failure_count >= threshold:
                next_state = self.OPEN
                opened_at = now

            conn.execute(
                """
                UPDATE circuit_breakers
                SET
                    state = ?,
                    failure_count = ?,
                    last_failure_at = ?,
                    opened_at = COALESCE(?, opened_at),
                    updated_at = ?
                WHERE name = ?
                """,
                (next_state, failure_count, now, opened_at, now, self.name),
            )

    def _maybe_transition_open_to_half_open(self) -> None:
        now_dt = self._now()
        now = _format_ts(now_dt)

        with self._db.transaction() as conn:
            row = conn.execute(
                """
                SELECT state, opened_at, recovery_timeout_seconds
                FROM circuit_breakers
                WHERE name = ?
                """,
                (self.name,),
            ).fetchone()
            if not row:
                raise KeyError(f"circuit_breakers missing row for {self.name!r}")

            if row["state"] != self.OPEN:
                return

            opened_at = _parse_ts(row["opened_at"])
            timeout_s = int(row["recovery_timeout_seconds"])
            if opened_at is None:
                return

            if now_dt >= opened_at + timedelta(seconds=timeout_s):
                conn.execute(
                    """
                    UPDATE circuit_breakers
                    SET state = ?, updated_at = ?
                    WHERE name = ?
                    """,
                    (self.HALF_OPEN, now, self.name),
                )
