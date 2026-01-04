# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Session cache query helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .core.database import DatabaseManager


@dataclass(frozen=True)
class CachedSession:
    session_id: str
    file_path: Path
    project_path: str
    file_mtime_ns: int
    file_size_bytes: int
    last_action: str
    has_completion: bool
    status: str

    @property
    def last_modified(self) -> datetime:
        # Keep naive datetime to match existing builder/discovery behavior.
        return datetime.fromtimestamp(self.file_mtime_ns / 1e9)


def query_session_cache(*, db: DatabaseManager, max_age_hours: int) -> list[CachedSession]:
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=max_age_hours)
    cutoff_ns = int(cutoff.timestamp() * 1e9)

    with db.connection() as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                file_path,
                project_path,
                file_mtime_ns,
                file_size_bytes,
                last_action,
                has_completion,
                status
            FROM session_file_cache
            WHERE source = ?
              AND file_mtime_ns >= ?
              AND status NOT IN ('corrupted', 'partial', 'skipped')
            ORDER BY file_mtime_ns DESC
            """,
            ("claude", cutoff_ns),
        ).fetchall()

    return [
        CachedSession(
            session_id=row["id"],
            file_path=Path(row["file_path"]),
            project_path=row["project_path"] or "",
            file_mtime_ns=int(row["file_mtime_ns"]),
            file_size_bytes=int(row["file_size_bytes"]),
            last_action=row["last_action"] or "",
            has_completion=bool(row["has_completion"]),
            status=row["status"] or "active",
        )
        for row in rows
    ]
