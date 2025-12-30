"""Core session store logic."""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import timezone
from pathlib import Path
from typing import TYPE_CHECKING, Iterator

from motus.config import config
from motus.core import configure_connection
from motus.exceptions import SessionNotFoundError

from .session_store_queries import SessionStoreQueries, _format_ts, _normalize_outcome, _utc_now

if TYPE_CHECKING:
    from motus.protocols import UnifiedSession

DEFAULT_DB_NAME = "session_store.db"

def _resolve_db_path(db_path: Path | str | None) -> tuple[str, bool]:
    if db_path is None:
        path = config.paths.state_dir / DEFAULT_DB_NAME
        path.parent.mkdir(parents=True, exist_ok=True)
        return (str(path), False)

    if isinstance(db_path, Path):
        path = db_path.expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        return (str(path), False)

    if db_path.startswith("file:"):
        return (db_path, True)

    if db_path != ":memory:":
        path = Path(db_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        return (str(path), False)

    return (db_path, False)


def _generate_session_id(timestamp: str, agent_type: str, context: bytes) -> str:
    try:
        from motus.session_identity import generate_session_id

        return generate_session_id(timestamp, agent_type, context)
    except ImportError:
        pass

    return f"mot_ses_{timestamp}_{agent_type}_{uuid.uuid4().hex[:8]}"


class SessionStore(SessionStoreQueries):
    """SQLite-backed session lifecycle store."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._db_path, self._use_uri = _resolve_db_path(db_path)
        self._init_schema()

    @property
    def db_path(self) -> str:
        return self._db_path

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(
            self._db_path, isolation_level=None, uri=self._use_uri, check_same_thread=False
        )
        configure_connection(conn)
        try:
            yield conn
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    cwd TEXT NOT NULL,
                    agent_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    outcome TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON sessions(updated_at)"
            )

    def create_session(self, cwd: Path, agent_type: str) -> str:
        if not agent_type or not agent_type.strip():
            raise ValueError("agent_type must be non-empty")

        cwd_path = Path(cwd)
        now = _utc_now()
        timestamp = now.strftime("%Y%m%dT%H%M%SZ")
        context = str(cwd_path).encode("utf-8")

        for _ in range(3):
            session_id = _generate_session_id(timestamp, agent_type, context)
            with self._connection() as conn:
                try:
                    conn.execute(
                        """
                        INSERT INTO sessions (
                            session_id, cwd, agent_type, created_at, updated_at, status, outcome
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            session_id,
                            str(cwd_path),
                            agent_type,
                            _format_ts(now),
                            _format_ts(now),
                            "active",
                            None,
                        ),
                    )
                except sqlite3.IntegrityError:
                    continue
            return session_id

        raise ValueError("failed to generate unique session id")

    def complete_session(self, session_id: str, outcome: str) -> None:
        status = _normalize_outcome(outcome)
        now = _utc_now()
        with self._connection() as conn:
            cursor = conn.execute(
                """
                UPDATE sessions
                SET status = ?, outcome = ?, updated_at = ?
                WHERE session_id = ?
                """,
                (status, status, _format_ts(now), session_id),
            )
            if cursor.rowcount == 0:
                raise SessionNotFoundError("session not found", session_id=session_id)

    def touch_session(self, session_id: str) -> None:
        now = _utc_now()
        with self._connection() as conn:
            cursor = conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                (_format_ts(now), session_id),
            )
            if cursor.rowcount == 0:
                raise SessionNotFoundError("session not found", session_id=session_id)

    def persist_from_unified(self, session: "UnifiedSession") -> None:
        """Persist a UnifiedSession to the store."""
        agent_type = (
            session.source.value if hasattr(session.source, "value") else str(session.source)
        )
        cwd = Path(session.project_path) if session.project_path else session.file_path.parent
        created_at = session.created_at or session.last_modified or _utc_now()
        updated_at = session.last_modified or session.created_at or _utc_now()
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        status = session.status.value if hasattr(session.status, "value") else str(session.status)

        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO sessions (
                    session_id, cwd, agent_type, created_at, updated_at, status, outcome
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    cwd = excluded.cwd,
                    agent_type = excluded.agent_type,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    status = excluded.status,
                    outcome = excluded.outcome
                """,
                (
                    session.session_id,
                    str(cwd),
                    agent_type,
                    _format_ts(created_at),
                    _format_ts(updated_at),
                    status,
                    None,
                ),
            )
