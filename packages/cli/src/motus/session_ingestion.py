# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Session cache ingestion helpers."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterator

from motus.logging import get_logger

from .commands.utils import extract_project_path
from .config import config
from .core.database import DatabaseManager
from .ingestors.common import (
    READ_RETRY_DELAY_SECONDS,
    get_claude_last_action,
    has_claude_completion_marker,
)

logger = get_logger(__name__)
MAX_READ_ATTEMPTS = 3


@dataclass(frozen=True)
class SyncResult:
    files_seen: int
    ingested: int
    unchanged: int
    partial: int
    corrupted: int
    skipped: int
    duration_seconds: float


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _parse_utc_iso(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError):
        return None


def _iter_claude_session_files(
    projects_dir: Path, *, full: bool, max_age_hours: int | None
) -> Iterator[tuple[Path, str]]:
    if not projects_dir.exists():
        return
    cutoff: datetime | None = None
    if not full and max_age_hours is not None:
        cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=max_age_hours)
    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue
        project_path = extract_project_path(project_dir.name)
        for jsonl_file in project_dir.glob("*.jsonl"):
            try:
                stat = jsonl_file.stat()
            except OSError:
                continue
            if cutoff is not None:
                modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                if modified < cutoff:
                    continue
            yield (jsonl_file, project_path)


def _hash_and_validate_jsonl(
    file_path: Path, *, max_ingest_file_bytes: int
) -> tuple[str, str, str | None]:
    """Compute SHA-256 and validate JSONL structure."""
    try:
        if file_path.is_symlink():
            return ("", "skipped", "symlink")
        file_size = file_path.stat().st_size
        if file_size > max_ingest_file_bytes:
            return ("", "skipped", f"too_large>{max_ingest_file_bytes}")
    except OSError as e:
        return ("", "skipped", f"os_error:{type(e).__name__}")
    for attempt in range(MAX_READ_ATTEMPTS):
        hasher = hashlib.sha256()
        invalid_line: tuple[int, str] | None = None
        partial_write = False
        try:
            with open(file_path, "rb") as f:
                for line_no, raw in enumerate(f, 1):
                    hasher.update(raw)
                    if not raw.strip():
                        continue
                    if not raw.endswith(b"\n"):
                        partial_write = True
                        break
                    try:
                        obj = json.loads(raw)
                    except json.JSONDecodeError as e:
                        invalid_line = (line_no, f"{e.msg} (pos {e.pos})")
                        break
                    if not isinstance(obj, dict):
                        invalid_line = (line_no, "not_object")
                        break
        except OSError as e:
            return ("", "skipped", f"os_error:{type(e).__name__}")
        if partial_write and attempt < MAX_READ_ATTEMPTS - 1:
            time.sleep(READ_RETRY_DELAY_SECONDS)
            continue
        if partial_write:
            return ("", "partial", "partial_write")
        if invalid_line is not None:
            line_no, msg = invalid_line
            return (hasher.hexdigest(), "corrupted", f"invalid_json:{line_no}:{msg}")
        return (hasher.hexdigest(), "active", None)
    return ("", "partial", "partial_write")


def _empty_result(start: float) -> SyncResult:
    return SyncResult(
        files_seen=0,
        ingested=0,
        unchanged=0,
        partial=0,
        corrupted=0,
        skipped=0,
        duration_seconds=time.monotonic() - start,
    )


def sync_session_cache(
    *,
    db: DatabaseManager,
    lock_path: Path,
    lock: Callable[..., Iterator[bool]],
    full: bool,
    max_age_hours: int | None,
    force: bool,
    autosync_min_interval_seconds: int,
    max_ingest_file_bytes: int,
) -> SyncResult:
    """Sync session metadata into SQLite."""
    start = time.monotonic()
    projects_dir = config.paths.projects_dir
    if not projects_dir.exists():
        return _empty_result(start)
    lock_timeout = 30 if full else 5
    with lock(lock_path, timeout_seconds=lock_timeout) as have_lock:
        if not have_lock:
            if full:
                raise RuntimeError(
                    f"Session cache lock busy after {lock_timeout}s: {lock_path}"
                )
            logger.info("Session cache locked; skipping ingestion", lock_path=str(lock_path))
            return _empty_result(start)
        if not full and not force and autosync_min_interval_seconds > 0:
            try:
                with db.connection() as conn:
                    row = conn.execute(
                        "SELECT value FROM session_cache_state WHERE key = ?",
                        ("session_cache:last_sync",),
                    ).fetchone()
                if row is not None and row[0]:
                    last_sync = _parse_utc_iso(str(row[0]))
                    if last_sync is not None:
                        age_s = (datetime.now(tz=timezone.utc) - last_sync).total_seconds()
                        if age_s < autosync_min_interval_seconds:
                            return _empty_result(start)
            except Exception as e:
                logger.debug(
                    "Cache operation failed",
                    error=str(e),
                    error_type=type(e).__name__,
                )
        files_iter = _iter_claude_session_files(
            projects_dir, full=full, max_age_hours=max_age_hours
        )
        files_seen = 0
        with db.connection() as conn:
            existing = {
                row["file_path"]: int(row["file_mtime_ns"])
                for row in conn.execute(
                    "SELECT file_path, file_mtime_ns FROM session_file_cache WHERE source = ?",
                    ("claude",),
                ).fetchall()
            }
        ingested = unchanged = partial = corrupted = skipped = 0
        with db.transaction() as conn:
            for file_path, project_path in files_iter:
                files_seen += 1
                session_id = file_path.stem
                file_path_str = str(file_path)
                try:
                    stat = file_path.stat()
                    mtime_ns = stat.st_mtime_ns
                    size_bytes = stat.st_size
                except OSError:
                    skipped += 1
                    continue
                prev_mtime = existing.get(file_path_str)
                if prev_mtime is not None and prev_mtime == mtime_ns:
                    unchanged += 1
                    continue
                file_hash, status, parse_error = _hash_and_validate_jsonl(
                    file_path, max_ingest_file_bytes=max_ingest_file_bytes
                )
                if status == "partial":
                    partial += 1
                    continue
                if status == "skipped":
                    skipped += 1
                    continue
                if status == "corrupted":
                    corrupted += 1
                last_action = get_claude_last_action(file_path)
                has_completion = has_claude_completion_marker(file_path)
                conn.execute(
                    """
                    INSERT INTO session_file_cache (
                        id, source, file_path, file_hash, file_mtime_ns, file_size_bytes, ingested_at,
                        project_path, model, total_turns, total_tokens,
                        last_action, has_completion, parse_error, status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        file_path = excluded.file_path,
                        file_hash = excluded.file_hash,
                        file_mtime_ns = excluded.file_mtime_ns,
                        file_size_bytes = excluded.file_size_bytes,
                        ingested_at = excluded.ingested_at,
                        project_path = excluded.project_path,
                        last_action = excluded.last_action,
                        has_completion = excluded.has_completion,
                        parse_error = excluded.parse_error,
                        status = excluded.status
                    """,
                    (
                        session_id,
                        "claude",
                        file_path_str,
                        file_hash,
                        int(mtime_ns),
                        int(size_bytes),
                        _utc_now_iso(),
                        project_path,
                        last_action,
                        1 if has_completion else 0,
                        parse_error,
                        status,
                    ),
                )
                ingested += 1
            conn.execute(
                """
                INSERT INTO session_cache_state (key, value, updated_at)
                VALUES (?, ?, datetime('now'))
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                ("session_cache:last_sync", _utc_now_iso()),
            )
    return SyncResult(
        files_seen=files_seen,
        ingested=ingested,
        unchanged=unchanged,
        partial=partial,
        corrupted=corrupted,
        skipped=skipped,
        duration_seconds=time.monotonic() - start,
    )
