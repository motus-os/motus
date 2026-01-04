# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Project + global memory for Motus.

Project memory is stored under `<project_root>/.mc/memory.db`.
Global memory is stored under `~/.motus/global.db`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from motus.core.bootstrap import ensure_database_at_path
from motus.core.database import DatabaseManager

from .schema import DetectedPattern, LearnedPattern
from .skills import get_unlocked_skills, record_progress, skill_deltas_for_command


@dataclass(frozen=True)
class _Paths:
    project_root: Path
    project_db: Path
    global_db: Path


def _project_db_path(project_root: Path) -> Path:
    return project_root / ".mc" / "memory.db"


def _default_global_db_path() -> Path:
    return Path.home() / ".motus" / "global.db"


class ProjectMemory:
    """Project Memory interface (Phase 0)."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        global_root: str | Path | None = None,
    ) -> None:
        self._paths = self._resolve_paths(project_root, global_root=global_root)
        self._project_db = DatabaseManager(self._paths.project_db)
        self._global_db = DatabaseManager(self._paths.global_db)
        self._active_session_id: int | None = None

        ensure_database_at_path(self._paths.project_db)
        ensure_database_at_path(self._paths.global_db)

    @staticmethod
    def _resolve_paths(project_root: str | Path, *, global_root: str | Path | None) -> _Paths:
        project_root_path = Path(project_root).resolve()
        project_db = _project_db_path(project_root_path)

        if global_root is None:
            global_db = _default_global_db_path()
        else:
            root = Path(global_root).expanduser().resolve()
            global_db = root / "global.db"

        return _Paths(project_root=project_root_path, project_db=project_db, global_db=global_db)

    @property
    def project_db_path(self) -> Path:
        return self._paths.project_db

    @property
    def global_db_path(self) -> Path:
        return self._paths.global_db

    def close(self) -> None:
        self._project_db.checkpoint_and_close()
        self._global_db.checkpoint_and_close()

    def record_detection(
        self,
        pattern_type: str,
        value: str,
        confidence: str,
        *,
        detected_from: str | None = None,
    ) -> None:
        if confidence not in {"high", "medium", "low"}:
            raise ValueError("confidence must be one of: high, medium, low")

        with self._project_db.transaction() as conn:
            self._ensure_active_session(conn)
            conn.execute(
                """
                INSERT INTO detected_patterns
                    (pattern_type, pattern_value, confidence, detected_from, detected_at)
                VALUES (?, ?, ?, ?, datetime('now'))
                ON CONFLICT(pattern_type, pattern_value) DO UPDATE SET
                    confidence = excluded.confidence,
                    detected_from = excluded.detected_from,
                    detected_at = excluded.detected_at
            """,
                (pattern_type, value, confidence, detected_from),
            )
            self._increment_learnings(conn, delta=1)

    def learn_pattern(self, pattern_type: str, value: str, source: str) -> None:
        if source not in {"detection", "user_input", "observation"}:
            raise ValueError("source must be one of: detection, user_input, observation")

        with self._project_db.transaction() as conn:
            self._ensure_active_session(conn)
            conn.execute(
                """
                INSERT INTO learned_patterns
                    (pattern_type, pattern_value, source, frequency, learned_at, last_seen_at)
                VALUES (?, ?, ?, 1, datetime('now'), datetime('now'))
                ON CONFLICT(pattern_type, pattern_value) DO UPDATE SET
                    frequency = learned_patterns.frequency + 1,
                    source = excluded.source,
                    last_seen_at = datetime('now')
            """,
                (pattern_type, value, source),
            )
            self._increment_learnings(conn, delta=1)

    def get_patterns(self, pattern_type: str) -> list[LearnedPattern]:
        with self._project_db.connection() as conn:
            cursor = conn.execute(
                """
                SELECT pattern_type, pattern_value, learned_at, source, frequency, last_seen_at
                FROM learned_patterns
                WHERE pattern_type = ?
                ORDER BY frequency DESC, last_seen_at DESC
            """,
                (pattern_type,),
            )
            return [
                LearnedPattern(
                    pattern_type=row[0],
                    pattern_value=row[1],
                    learned_at=row[2],
                    source=row[3],
                    frequency=row[4],
                    last_seen_at=row[5],
                )
                for row in cursor.fetchall()
            ]

    def get_detections(self, pattern_type: str) -> list[DetectedPattern]:
        with self._project_db.connection() as conn:
            cursor = conn.execute(
                """
                SELECT pattern_type, pattern_value, confidence, detected_from, detected_at, last_confirmed_at
                FROM detected_patterns
                WHERE pattern_type = ?
                ORDER BY detected_at DESC
            """,
                (pattern_type,),
            )
            return [
                DetectedPattern(
                    pattern_type=row[0],
                    pattern_value=row[1],
                    confidence=row[2],
                    detected_from=row[3],
                    detected_at=row[4],
                    last_confirmed_at=row[5],
                )
                for row in cursor.fetchall()
            ]

    def is_first_session(self) -> bool:
        with self._project_db.connection() as conn:
            row = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()
            count = int(row[0]) if row else 0
            return count == 0

    def get_session_count(self) -> int:
        with self._project_db.connection() as conn:
            row = conn.execute("SELECT COUNT(*) FROM sessions WHERE ended_at IS NOT NULL").fetchone()
            return int(row[0]) if row else 0

    def start_session(self) -> int:
        with self._project_db.transaction() as conn:
            if self._active_session_id is not None:
                return self._active_session_id
            conn.execute("INSERT INTO sessions (started_at) VALUES (datetime('now'))")
            session_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            self._active_session_id = session_id
            return session_id

    def end_session(self) -> None:
        if self._active_session_id is None:
            return
        session_id = self._active_session_id
        with self._project_db.transaction() as conn:
            conn.execute(
                "UPDATE sessions SET ended_at = datetime('now') WHERE id = ? AND ended_at IS NULL",
                (session_id,),
            )
        self._active_session_id = None

    def record_command(self, command: str) -> None:
        normalized = " ".join(command.strip().split())
        if not normalized:
            return

        with self._project_db.transaction() as conn:
            self._ensure_active_session(conn)
            conn.execute(
                "UPDATE sessions SET commands_run = commands_run + 1 WHERE id = ?",
                (self._active_session_id,),
            )

        deltas = skill_deltas_for_command(normalized)
        if not deltas:
            return

        with self._global_db.transaction() as conn:
            for skill_name, delta in deltas.items():
                record_progress(conn, skill_name=skill_name, delta=delta)

    def get_unlocked_skills(self) -> list[str]:
        with self._global_db.connection() as conn:
            return get_unlocked_skills(conn)

    def unlock_skill(self, skill_name: str) -> bool:
        with self._global_db.transaction() as conn:
            return record_progress(conn, skill_name=skill_name, delta=0)

    def _ensure_active_session(self, conn) -> None:
        if self._active_session_id is not None:
            return
        conn.execute("INSERT INTO sessions (started_at) VALUES (datetime('now'))")
        session_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        self._active_session_id = session_id

    def _increment_learnings(self, conn, *, delta: int) -> None:
        if self._active_session_id is None:
            return
        conn.execute(
            "UPDATE sessions SET learnings_captured = learnings_captured + ? WHERE id = ?",
            (delta, self._active_session_id),
        )

