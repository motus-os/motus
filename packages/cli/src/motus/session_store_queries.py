# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Query helpers for session store."""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _format_ts(ts: datetime) -> str:
    return ts.isoformat().replace("+00:00", "Z")


def _parse_ts(raw: str) -> datetime:
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


_OUTCOME_STATUS_MAP = {
    "success": "completed",
    "completed": "completed",
    "complete": "completed",
    "ok": "completed",
    "failed": "failed",
    "failure": "failed",
    "error": "failed",
    "abandoned": "abandoned",
    "cancelled": "abandoned",
    "canceled": "abandoned",
}

MAX_SESSION_RESULTS = max(1, int(os.environ.get("MC_SESSION_MAX_RESULTS", "5000")))


def _normalize_outcome(outcome: str) -> str:
    normalized = outcome.strip().lower()
    if not normalized:
        raise ValueError("outcome must be non-empty")
    if normalized not in _OUTCOME_STATUS_MAP:
        raise ValueError(f"unsupported outcome: {outcome}")
    return _OUTCOME_STATUS_MAP[normalized]


@dataclass(frozen=True, slots=True)
class SessionRecord:
    """Stored session metadata."""

    session_id: str
    cwd: Path
    agent_type: str
    created_at: datetime
    updated_at: datetime
    status: str
    outcome: str | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "SessionRecord":
        return cls(
            session_id=str(row["session_id"]),
            cwd=Path(row["cwd"]),
            agent_type=str(row["agent_type"]),
            created_at=_parse_ts(row["created_at"]),
            updated_at=_parse_ts(row["updated_at"]),
            status=str(row["status"]),
            outcome=row["outcome"],
        )


class SessionStoreQueries:
    """Query helpers for session store."""

    def _cache_get(self, key: str):
        cache = getattr(self, "_query_cache", None)
        if cache is None:
            return None
        return cache.get(key)

    def _cache_set(self, key: str, value):
        cache = getattr(self, "_query_cache", None)
        if cache is None:
            return
        cache.set(key, value)

    def get_session(self, session_id: str) -> SessionRecord | None:
        cache_key = f"sessions:one:{session_id}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        if row is None:
            return None
        record = SessionRecord.from_row(row)
        self._cache_set(cache_key, record)
        return record

    def get_active_sessions(self) -> list[SessionRecord]:
        cache_key = "sessions:active"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM sessions WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                ("active", MAX_SESSION_RESULTS),
            ).fetchall()
        result = [SessionRecord.from_row(row) for row in rows]
        self._cache_set(cache_key, result)
        return result

    def get_all_sessions(self) -> list[SessionRecord]:
        cache_key = "sessions:all"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?",
                (MAX_SESSION_RESULTS,),
            ).fetchall()
        result = [SessionRecord.from_row(row) for row in rows]
        self._cache_set(cache_key, result)
        return result

    def find_abandoned_sessions(self, threshold_hours: int = 24) -> list[SessionRecord]:
        if threshold_hours <= 0:
            raise ValueError("threshold_hours must be positive")

        offset_seconds = -threshold_hours * 3600

        cache_key = f"sessions:abandoned:{threshold_hours}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM sessions
                WHERE status = ? AND updated_at < mc_date_add(mc_now_iso(), ?)
                ORDER BY updated_at ASC
                LIMIT ?
                """,
                ("active", offset_seconds, MAX_SESSION_RESULTS),
            ).fetchall()

        result = [SessionRecord.from_row(row) for row in rows]
        self._cache_set(cache_key, result)
        return result
