# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Idempotency keys for safe retries (database-backed)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Optional

from motus.core.database import DatabaseManager, get_db_manager


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


class IdempotencyState(str, Enum):
    PENDING = "pending"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass(frozen=True)
class IdempotencyRecord:
    key: str
    operation: str
    request_hash: str
    status: IdempotencyState
    response: Optional[dict[str, Any]]
    expires_at: datetime

    @property
    def is_expired(self) -> bool:
        return self.expires_at <= _utc_now()


class IdempotencyManager:
    def __init__(
        self,
        *,
        db: DatabaseManager | None = None,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._db = db or get_db_manager()
        self._now = now

    def make_key(self, *, operation: str, request_hash: str) -> str:
        digest = hashlib.sha256(f"{operation}:{request_hash}".encode("utf-8")).hexdigest()[:32]
        return f"idem_{digest}"

    def get(self, key: str) -> Optional[IdempotencyRecord]:
        with self._db.connection() as conn:
            row = conn.execute(
                """
                SELECT key, operation, request_hash, response, status, expires_at
                FROM idempotency_keys
                WHERE key = ?
                """,
                (key,),
            ).fetchone()
            if not row:
                return None

        expires_at = _parse_ts(row["expires_at"])
        if expires_at is None:
            return None

        response = json.loads(row["response"]) if row["response"] else None
        return IdempotencyRecord(
            key=row["key"],
            operation=row["operation"],
            request_hash=row["request_hash"],
            status=IdempotencyState(row["status"]),
            response=response,
            expires_at=expires_at,
        )

    def get_or_create(
        self,
        *,
        operation: str,
        request_hash: str,
        ttl_seconds: int,
        key: str | None = None,
    ) -> IdempotencyRecord:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be >= 1")

        now_dt = self._now()
        expires_at = now_dt + timedelta(seconds=ttl_seconds)
        expires_at_s = _format_ts(expires_at)

        idem_key = key or self.make_key(operation=operation, request_hash=request_hash)

        with self._db.transaction() as conn:
            # Best-effort prune of expired entry for the same key.
            conn.execute(
                "DELETE FROM idempotency_keys WHERE key = ? AND expires_at <= ?",
                (idem_key, _format_ts(now_dt)),
            )

            conn.execute(
                """
                INSERT OR IGNORE INTO idempotency_keys
                    (key, operation, request_hash, status, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    idem_key,
                    operation,
                    request_hash,
                    IdempotencyState.PENDING.value,
                    _format_ts(now_dt),
                    expires_at_s,
                ),
            )

        record = self.get(idem_key)
        if record is None:
            raise RuntimeError("failed to read idempotency record after insert")
        return record

    def complete(self, key: str, response: dict[str, Any]) -> None:
        with self._db.transaction() as conn:
            conn.execute(
                """
                UPDATE idempotency_keys
                SET response = ?, status = ?
                WHERE key = ?
                """,
                (json.dumps(response, sort_keys=True), IdempotencyState.COMPLETE.value, key),
            )

    def fail(self, key: str, error: dict[str, Any]) -> None:
        with self._db.transaction() as conn:
            conn.execute(
                """
                UPDATE idempotency_keys
                SET response = ?, status = ?
                WHERE key = ?
                """,
                (json.dumps(error, sort_keys=True), IdempotencyState.FAILED.value, key),
            )
