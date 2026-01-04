# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Resource quota management backed by the Motus database."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from motus.core.database import DatabaseManager, get_db_manager


class QuotaExceededError(RuntimeError):
    """Raised when a hard limit would be exceeded."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _format_ts(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_ts(value: str | None) -> Optional[datetime]:
    if not value:
        return None
    if "T" not in value and " " in value:
        try:
            dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


@dataclass(frozen=True)
class Quota:
    resource_type: str
    soft_limit: int
    hard_limit: int
    current_usage: int
    reset_interval_hours: Optional[int]
    last_reset_at: Optional[datetime]


@dataclass(frozen=True)
class ConsumeResult:
    quota: Quota
    new_usage: int
    warned: bool


class QuotaManager:
    def __init__(
        self,
        *,
        db: DatabaseManager | None = None,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._db = db or get_db_manager()
        self._now = now

    def get_quota(self, resource_type: str) -> Quota:
        with self._db.connection() as conn:
            row = conn.execute(
                """
                SELECT
                    resource_type, soft_limit, hard_limit, current_usage,
                    reset_interval_hours, last_reset_at
                FROM resource_quotas
                WHERE resource_type = ?
                """,
                (resource_type,),
            ).fetchone()
            if not row:
                raise KeyError(f"resource_quotas missing row for {resource_type!r}")

        return Quota(
            resource_type=row["resource_type"],
            soft_limit=int(row["soft_limit"]),
            hard_limit=int(row["hard_limit"]),
            current_usage=int(row["current_usage"]),
            reset_interval_hours=(
                int(row["reset_interval_hours"]) if row["reset_interval_hours"] is not None else None
            ),
            last_reset_at=_parse_ts(row["last_reset_at"]),
        )

    def consume(self, resource_type: str, amount: int = 1) -> ConsumeResult:
        if amount <= 0:
            raise ValueError("amount must be >= 1")

        now_dt = self._now()
        now = _format_ts(now_dt)

        with self._db.transaction() as conn:
            row = conn.execute(
                """
                SELECT soft_limit, hard_limit, current_usage, reset_interval_hours, last_reset_at
                FROM resource_quotas
                WHERE resource_type = ?
                """,
                (resource_type,),
            ).fetchone()
            if not row:
                raise KeyError(f"resource_quotas missing row for {resource_type!r}")

            soft = int(row["soft_limit"])
            hard = int(row["hard_limit"])
            current = int(row["current_usage"])

            reset_hours = int(row["reset_interval_hours"]) if row["reset_interval_hours"] is not None else None
            last_reset_at = _parse_ts(row["last_reset_at"])
            if reset_hours is not None:
                if last_reset_at is None:
                    conn.execute(
                        """
                        UPDATE resource_quotas
                        SET last_reset_at = ?
                        WHERE resource_type = ?
                        """,
                        (now, resource_type),
                    )
                else:
                    if now_dt >= last_reset_at + timedelta(hours=reset_hours):
                        current = 0
                        conn.execute(
                            """
                            UPDATE resource_quotas
                            SET current_usage = 0, last_reset_at = ?
                            WHERE resource_type = ?
                            """,
                            (now, resource_type),
                        )

            new_usage = current + amount
            if new_usage > hard:
                raise QuotaExceededError(
                    f"{resource_type} quota exceeded: {new_usage} > hard_limit {hard}"
                )

            warned = new_usage > soft
            conn.execute(
                """
                UPDATE resource_quotas
                SET current_usage = ?, last_warning_at = CASE WHEN ? THEN ? ELSE last_warning_at END
                WHERE resource_type = ?
                """,
                (new_usage, 1 if warned else 0, now, resource_type),
            )

        quota = self.get_quota(resource_type)
        return ConsumeResult(quota=quota, new_usage=new_usage, warned=warned)

    def release(self, resource_type: str, amount: int = 1) -> int:
        if amount <= 0:
            raise ValueError("amount must be >= 1")

        with self._db.transaction() as conn:
            row = conn.execute(
                "SELECT current_usage FROM resource_quotas WHERE resource_type = ?",
                (resource_type,),
            ).fetchone()
            if not row:
                raise KeyError(f"resource_quotas missing row for {resource_type!r}")

            current = int(row["current_usage"])
            new_usage = max(0, current - amount)
            conn.execute(
                "UPDATE resource_quotas SET current_usage = ? WHERE resource_type = ?",
                (new_usage, resource_type),
            )
        return new_usage

