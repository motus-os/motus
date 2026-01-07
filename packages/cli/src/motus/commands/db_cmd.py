# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""CLI command: `motus db` maintenance utilities."""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich.console import Console

from motus.cli.exit_codes import EXIT_ERROR, EXIT_SUCCESS
from motus.core.database import get_database_path, get_db_manager
from motus.core.database_connection import configure_connection
from motus.migration.path_migration import (
    CANONICAL_DIRNAME,
    LEGACY_DIRNAME,
    find_legacy_workspace_dir,
)

console = Console()
_SAFE_TABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _db_exists(db_path: Path) -> bool:
    return db_path.exists()


def _record_preference(conn, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO preferences (key, value, source)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            source = excluded.source,
            set_at = datetime('now')
        """,
        (key, value, "cli"),
    )


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _pid_alive(pid: int | None) -> bool | None:
    if pid is None:
        return None
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False


def _try_acquire_write_lock(db_path: Path) -> bool:
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(
            str(db_path),
            isolation_level=None,
            check_same_thread=False,
            timeout=0.1,
        )
        configure_connection(conn, set_row_factory=False)
        conn.execute("PRAGMA busy_timeout = 200")
        conn.execute("BEGIN IMMEDIATE")
        if conn.in_transaction:
            conn.rollback()
        return True
    except sqlite3.OperationalError as exc:
        if "database is locked" in str(exc).lower():
            return False
        raise
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def db_vacuum_command(args: Any) -> int:
    db_path = get_database_path()
    if not _db_exists(db_path):
        console.print("[red]Database not found. Run motus doctor first.[/red]")
        return EXIT_ERROR

    db = get_db_manager()
    with db.connection() as conn:
        conn.execute("VACUUM")
        if getattr(args, "full", False):
            conn.execute("ANALYZE")
        db.checkpoint_wal()
        _record_preference(conn, "db.last_vacuum", "vacuum")
    console.print("VACUUM completed", markup=False)
    return EXIT_SUCCESS


def db_analyze_command(args: Any) -> int:
    db_path = get_database_path()
    if not _db_exists(db_path):
        console.print("[red]Database not found. Run motus doctor first.[/red]")
        return EXIT_ERROR

    db = get_db_manager()
    with db.connection() as conn:
        conn.execute("ANALYZE")
        _record_preference(conn, "db.last_analyze", "analyze")
    console.print("ANALYZE completed", markup=False)
    return EXIT_SUCCESS


def _table_counts(conn, tables: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for name in tables:
        if not _SAFE_TABLE_RE.fullmatch(name):
            continue
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            (name,),
        ).fetchone()
        if not row:
            continue
        count = conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        counts[name] = int(count)
    return counts


def db_stats_command(args: Any) -> int:
    db_path = get_database_path()
    if not _db_exists(db_path):
        console.print("[red]Database not found. Run motus doctor first.[/red]")
        return EXIT_ERROR

    db = get_db_manager()
    file_size = db_path.stat().st_size
    wal_size = db.get_wal_size()

    with db.connection(read_only=True) as conn:
        counts = _table_counts(
            conn,
            [
                "roadmap_items",
                "change_requests",
                "audit_log",
                "coordination_leases",
                "evidence",
            ],
        )
        vacuum_row = conn.execute(
            "SELECT value FROM preferences WHERE key = ?",
            ("db.last_vacuum",),
        ).fetchone()
        analyze_row = conn.execute(
            "SELECT value FROM preferences WHERE key = ?",
            ("db.last_analyze",),
        ).fetchone()

    payload = {
        "db_path": str(db_path),
        "db_size_bytes": file_size,
        "wal_size_bytes": wal_size,
        "table_counts": counts,
        "last_vacuum": vacuum_row[0] if vacuum_row else None,
        "last_analyze": analyze_row[0] if analyze_row else None,
    }

    if getattr(args, "json", False):
        console.print_json(json.dumps(payload, sort_keys=True))
        return EXIT_SUCCESS

    console.print(f"DB: {db_path}", markup=False)
    console.print(f"Size: {file_size} bytes", markup=False)
    console.print(f"WAL: {wal_size} bytes", markup=False)
    for name, count in counts.items():
        console.print(f"{name}: {count}", markup=False)
    if payload["last_vacuum"]:
        console.print(f"Last vacuum: {payload['last_vacuum']}", markup=False)
    if payload["last_analyze"]:
        console.print(f"Last analyze: {payload['last_analyze']}", markup=False)
    return EXIT_SUCCESS


def db_checkpoint_command(args: Any) -> int:
    db_path = get_database_path()
    if not _db_exists(db_path):
        console.print("[red]Database not found. Run motus doctor first.[/red]")
        return EXIT_ERROR

    db = get_db_manager()
    db.checkpoint_wal()
    console.print("WAL checkpoint complete", markup=False)
    return EXIT_SUCCESS


def db_lock_info_command(args: Any) -> int:
    db = get_db_manager()
    info = db.lock_info()
    if not info:
        console.print("No lock registry found", markup=False)
        return EXIT_SUCCESS

    started_at = _parse_iso(str(info.get("started_at") or ""))
    age_s = None
    if started_at is not None:
        age_s = (datetime.now(timezone.utc) - started_at).total_seconds()

    pid = info.get("pid")
    alive = _pid_alive(pid if isinstance(pid, int) else None)

    payload = dict(info)
    payload["age_seconds"] = int(age_s) if age_s is not None else None
    payload["pid_alive"] = alive

    if getattr(args, "json", False):
        console.print_json(json.dumps(payload, sort_keys=True))
        return EXIT_SUCCESS

    console.print(f"Lock status: {payload.get('status')}", markup=False)
    console.print(f"PID: {pid} (alive={alive})", markup=False)
    console.print(f"Thread: {payload.get('thread')}", markup=False)
    console.print(f"Command: {payload.get('command')}", markup=False)
    if age_s is not None:
        console.print(f"Age: {int(age_s)}s", markup=False)
    console.print(f"DB: {payload.get('db_path')}", markup=False)
    console.print(f"Registry: {payload.get('lock_registry_path')}", markup=False)
    return EXIT_SUCCESS


def db_wait_command(args: Any) -> int:
    db_path = get_database_path()
    if not _db_exists(db_path):
        console.print("[red]Database not found. Run motus doctor first.[/red]")
        return EXIT_ERROR

    max_seconds = float(getattr(args, "max_seconds", 30) or 30)
    interval = float(getattr(args, "interval", 0.2) or 0.2)
    deadline = time.monotonic() + max_seconds

    while True:
        if _try_acquire_write_lock(db_path):
            console.print("Write lock available", markup=False)
            return EXIT_SUCCESS
        if time.monotonic() >= deadline:
            console.print("Timed out waiting for write lock", markup=False)
            return EXIT_ERROR
        time.sleep(interval)


def db_recover_command(args: Any) -> int:
    db_path = get_database_path()
    if not _db_exists(db_path):
        console.print("[red]Database not found. Run motus doctor first.[/red]")
        return EXIT_ERROR

    db = get_db_manager()
    info = db.lock_info()
    if info:
        pid = info.get("pid")
        alive = _pid_alive(pid if isinstance(pid, int) else None)
        if alive:
            console.print("Active lock holder detected; recovery aborted", markup=False)
            return EXIT_ERROR

    if not _try_acquire_write_lock(db_path):
        console.print("Database still locked; recovery aborted", markup=False)
        return EXIT_ERROR

    from motus.core.layered_config import get_config

    backup_dir = Path(
        get_config().get_value("database.backup_dir", "~/.motus/backups")
    ).expanduser()
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_dir / f"coordination.db.{timestamp}.bak"
    shutil.copy2(db_path, backup_path)

    for suffix in ("-wal", "-shm"):
        aux = Path(str(db_path) + suffix)
        if aux.exists():
            aux.unlink()

    conn = sqlite3.connect(
        str(db_path),
        isolation_level=None,
        check_same_thread=False,
        timeout=1.0,
    )
    try:
        configure_connection(conn, set_row_factory=False)
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()

    console.print(f"Recovery complete. Backup: {backup_path}", markup=False)
    return EXIT_SUCCESS


def _dir_is_empty(path: Path) -> bool:
    return path.exists() and path.is_dir() and not any(path.iterdir())


def _collect_entries(root: Path) -> set[Path]:
    entries: set[Path] = set()
    for current_root, dirs, files in os.walk(root, followlinks=False):
        current_path = Path(current_root)
        rel_root = current_path.relative_to(root)
        for name in files:
            entries.add(rel_root / name)
        for name in list(dirs):
            candidate = current_path / name
            if candidate.is_symlink():
                entries.add(rel_root / name)
                dirs.remove(name)
    return entries


def _migrate_tree(
    source: Path,
    target: Path,
    *,
    dry_run: bool,
    force: bool,
    remove_legacy: bool,
) -> tuple[bool, str]:
    if not source.exists():
        return True, f"SKIP: {source} not found"
    if not source.is_dir():
        return False, f"FAIL: {source} is not a directory"

    if target.exists():
        if not target.is_dir():
            return False, f"FAIL: {target} exists and is not a directory"
        if not force and not _dir_is_empty(target):
            return False, (
                f"FAIL: {target} already exists and is not empty. "
                "Re-run with --force to overwrite."
            )

    entries = _collect_entries(source)
    if dry_run:
        return True, f"DRY RUN: would copy {len(entries)} entries from {source} to {target}"

    try:
        shutil.copytree(
            source,
            target,
            symlinks=True,
            dirs_exist_ok=target.exists(),
        )
    except (OSError, shutil.Error) as e:
        return False, f"FAIL: copy failed ({source} -> {target}): {e}"

    missing = entries - _collect_entries(target)
    if missing:
        example = sorted(missing)[0]
        return False, (
            f"FAIL: migration incomplete; missing {len(missing)} entries (e.g., {example})"
        )

    if remove_legacy:
        try:
            shutil.rmtree(source)
        except OSError as e:
            return False, f"FAIL: copied but failed to remove legacy path: {e}"
        return True, f"OK: migrated {source} -> {target} and removed legacy"

    return True, f"OK: migrated {source} -> {target}"


def db_migrate_path_command(args: Any) -> int:
    """Migrate legacy .mc paths to .motus."""
    dry_run = bool(getattr(args, "dry_run", False))
    force = bool(getattr(args, "force", False))
    remove_legacy = bool(getattr(args, "remove_legacy", False))
    global_only = bool(getattr(args, "global_only", False))
    workspace_only = bool(getattr(args, "workspace_only", False))

    results: list[tuple[bool, str]] = []

    if not workspace_only:
        global_source = Path.home() / LEGACY_DIRNAME
        global_target = Path.home() / CANONICAL_DIRNAME
        results.append(
            _migrate_tree(
                global_source,
                global_target,
                dry_run=dry_run,
                force=force,
                remove_legacy=remove_legacy,
            )
        )

    if not global_only:
        legacy_workspace = find_legacy_workspace_dir(Path.cwd())
        if legacy_workspace is None:
            results.append((True, "SKIP: no legacy workspace .mc directory found"))
        else:
            workspace_target = legacy_workspace.parent / CANONICAL_DIRNAME
            results.append(
                _migrate_tree(
                    legacy_workspace,
                    workspace_target,
                    dry_run=dry_run,
                    force=force,
                    remove_legacy=remove_legacy,
                )
            )

    ok = True
    for success, message in results:
        if not success:
            ok = False
            console.print(message, style="red", markup=False)
        else:
            console.print(message, markup=False)

    return EXIT_SUCCESS if ok else EXIT_ERROR
