# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""CLI command: `motus db` maintenance utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rich.console import Console

from motus.cli.exit_codes import EXIT_ERROR, EXIT_SUCCESS
from motus.core.database import get_database_path, get_db_manager

console = Console()


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


def db_vacuum_command(args: Any) -> int:
    db_path = get_database_path()
    if not _db_exists(db_path):
        console.print("[red]Database not found. Run motus doctor first.[/red]")
        return EXIT_ERROR

    db = get_db_manager()
    conn = db.get_connection()
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
    conn = db.get_connection()
    conn.execute("ANALYZE")
    _record_preference(conn, "db.last_analyze", "analyze")
    console.print("ANALYZE completed", markup=False)
    return EXIT_SUCCESS


def _table_counts(conn, tables: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for name in tables:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            (name,),
        ).fetchone()
        if not row:
            continue
        count = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
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

    with db.connection() as conn:
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
