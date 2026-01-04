# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""SQLite-backed session cache for fast session listing.

Design: JSONL files are the source of truth; SQLite is a cache/index.
If the cache is unavailable, callers should fall back to JSONL parsing.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from motus.logging import get_logger

from .core.database import DatabaseManager
from .session_ingestion import SyncResult, sync_session_cache
from .session_query import CachedSession, query_session_cache

logger = get_logger(__name__)

DEFAULT_LOCK_PATH = Path("~/.motus/sync.lock").expanduser()
DEFAULT_AUTOSYNC_MIN_INTERVAL_SECONDS = 30
MAX_INGEST_FILE_BYTES = 1_000_000_000  # 1GB hard stop (adversarial safety)


@contextmanager
def _advisory_lock(lock_path: Path, *, timeout_seconds: int) -> Iterator[bool]:
    """Best-effort advisory lock using fcntl (POSIX only)."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        f = open(lock_path, "a+", encoding="utf-8")
    except OSError as e:
        logger.debug(
            "Cache operation failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        yield False
        return

    acquired = False
    try:
        try:
            import fcntl  # POSIX only

            deadline = time.monotonic() + timeout_seconds
            while time.monotonic() < deadline:
                try:
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                    break
                except BlockingIOError:
                    time.sleep(0.05)
        except Exception as e:
            logger.debug(
                "Cache operation failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            acquired = False

        yield acquired
    finally:
        try:
            if acquired:
                import fcntl

                fcntl.flock(f, fcntl.LOCK_UN)
        except Exception as e:
            logger.debug(
                "Cache operation failed",
                error=str(e),
                error_type=type(e).__name__,
            )
        try:
            f.close()
        except Exception as e:
            logger.debug(
                "Cache operation failed",
                error=str(e),
                error_type=type(e).__name__,
            )

class SessionSQLiteCache:
    """SQLite cache for Claude sessions (initial implementation)."""

    def __init__(
        self,
        *,
        db_path: Path | None = None,
        lock_path: Path = DEFAULT_LOCK_PATH,
    ) -> None:
        self._db = DatabaseManager(db_path) if db_path is not None else DatabaseManager()
        self._lock_path = lock_path

    def sync(
        self,
        *,
        full: bool,
        max_age_hours: int | None = None,
        force: bool = False,
        autosync_min_interval_seconds: int = DEFAULT_AUTOSYNC_MIN_INTERVAL_SECONDS,
    ) -> SyncResult:
        """Sync session metadata into SQLite.

        - Full sync ingests all session files.
        - Incremental sync ingests only files that are new/changed, optionally constrained by age.
        """
        return sync_session_cache(
            db=self._db,
            lock_path=self._lock_path,
            lock=_advisory_lock,
            full=full,
            max_age_hours=max_age_hours,
            force=force,
            autosync_min_interval_seconds=autosync_min_interval_seconds,
            max_ingest_file_bytes=MAX_INGEST_FILE_BYTES,
        )

    def query(self, *, max_age_hours: int) -> list[CachedSession]:
        return query_session_cache(db=self._db, max_age_hours=max_age_hours)


__all__ = [
    "SessionSQLiteCache",
    "SyncResult",
    "CachedSession",
    "DEFAULT_LOCK_PATH",
    "DEFAULT_AUTOSYNC_MIN_INTERVAL_SECONDS",
    "MAX_INGEST_FILE_BYTES",
]
