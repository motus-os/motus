# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Session claims registry backed by SessionStore."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from motus.exceptions import SessionNotFoundError
from motus.session_store import SessionRecord, SessionStore, _format_ts, _parse_ts, _utc_now


class ClaimError(ValueError):
    """Raised when claim inputs are invalid."""


@dataclass(frozen=True, slots=True)
class ClaimRecord:
    claim_id: str
    session_id: str
    claim_type: str
    payload: dict[str, Any]
    created_at: datetime
    verified: bool
    verified_at: datetime | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "ClaimRecord":
        payload = json.loads(row["payload_json"])
        verified_at = row["verified_at"]
        return cls(
            claim_id=str(row["claim_id"]),
            session_id=str(row["session_id"]),
            claim_type=str(row["claim_type"]),
            payload=payload,
            created_at=_parse_ts(row["created_at"]),
            verified=bool(row["verified"]),
            verified_at=_parse_ts(verified_at) if verified_at else None,
        )


class ClaimsRegister:
    """Register and verify session claims."""

    def __init__(self, store: SessionStore) -> None:
        self._store = store
        self._init_schema()

    def _init_schema(self) -> None:
        with self._store._connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS claims (
                    claim_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    claim_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    verified INTEGER NOT NULL DEFAULT 0,
                    verified_at TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_claims_session ON claims(session_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_claims_verified ON claims(session_id, verified)"
            )

    def register_claim(self, session_id: str, claim_type: str, payload: dict[str, Any]) -> str:
        if not claim_type or not claim_type.strip():
            raise ClaimError("claim_type must be non-empty")
        if not isinstance(payload, dict):
            raise ClaimError("payload must be a dict")

        session = self._store.get_session(session_id)
        if session is None:
            raise SessionNotFoundError("session not found", session_id=session_id)

        try:
            payload_json = json.dumps(payload, sort_keys=True)
        except (TypeError, ValueError) as exc:
            raise ClaimError("payload must be JSON serializable") from exc

        claim_id = f"claim_{uuid.uuid4().hex}"
        created_at = _format_ts(_utc_now())

        with self._store._connection() as conn:
            conn.execute(
                """
                INSERT INTO claims (
                    claim_id, session_id, claim_type, payload_json, created_at, verified, verified_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    claim_id,
                    session_id,
                    claim_type,
                    payload_json,
                    created_at,
                    0,
                    None,
                ),
            )

        self._store.touch_session(session_id)
        return claim_id

    def verify_claim(self, claim_id: str) -> bool:
        now = _format_ts(_utc_now())
        with self._store._connection() as conn:
            row = conn.execute(
                "SELECT session_id FROM claims WHERE claim_id = ?", (claim_id,)
            ).fetchone()
            if row is None:
                return False
            session_id = str(row["session_id"])
            conn.execute(
                """
                UPDATE claims
                SET verified = 1, verified_at = ?
                WHERE claim_id = ?
                """,
                (now, claim_id),
            )

        self._store.touch_session(session_id)
        return True

    def get_session_claims(self, session_id: str) -> list[ClaimRecord]:
        with self._store._connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM claims
                WHERE session_id = ?
                ORDER BY created_at ASC
                """,
                (session_id,),
            ).fetchall()

        return [ClaimRecord.from_row(row) for row in rows]

    def get_session(self, session_id: str) -> SessionRecord | None:
        return self._store.get_session(session_id)
