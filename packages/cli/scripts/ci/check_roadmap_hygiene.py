#!/usr/bin/env python3
"""Roadmap hygiene checks for coordination.db."""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]


def _migrations_dir() -> Path:
    candidates = [
        ROOT / "packages" / "cli" / "migrations",
        ROOT / "migrations",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _extract_up_sql(raw: str) -> str:
    lines: list[str] = []
    for line in raw.splitlines():
        if line.strip().upper().startswith("-- DOWN"):
            break
        lines.append(line)
    return "\n".join(lines).strip()


def _bootstrap_db(db_path: Path) -> None:
    migrations = _migrations_dir()
    if not migrations.exists():
        raise FileNotFoundError(f"Migrations directory not found: {migrations}")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        for path in sorted(migrations.glob("*.sql")):
            raw = path.read_text(encoding="utf-8")
            up_sql = _extract_up_sql(raw)
            if not up_sql:
                continue
            conn.executescript(up_sql)
    finally:
        conn.close()


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ? LIMIT 1",
        (table,),
    ).fetchone()
    return row is not None


def _sample(rows: list[sqlite3.Row], *, limit: int = 3) -> str:
    return ", ".join(str(dict(row)) for row in rows[:limit])


def _run_checks(conn: sqlite3.Connection) -> tuple[list[str], list[str]]:
    conn.row_factory = sqlite3.Row
    errors: list[str] = []
    warnings: list[str] = []

    required_tables = ["roadmap_items", "roadmap_dependencies", "terminology"]
    for table in required_tables:
        if not _table_exists(conn, table):
            errors.append(f"Missing required table: {table}")

    if errors:
        return errors, warnings

    dup_row = conn.execute(
        """
        SELECT COUNT(*) AS total, COUNT(DISTINCT id) AS unique_ids
        FROM roadmap_items
        WHERE deleted_at IS NULL
        """
    ).fetchone()
    if dup_row and dup_row["total"] != dup_row["unique_ids"]:
        errors.append("Duplicate roadmap item IDs detected")

    invalid_phases = conn.execute(
        """
        SELECT ri.id, ri.phase_key
        FROM roadmap_items ri
        LEFT JOIN terminology t
          ON t.domain = 'roadmap_phase' AND t.internal_key = ri.phase_key
        WHERE ri.deleted_at IS NULL AND t.internal_key IS NULL
        """
    ).fetchall()
    if invalid_phases:
        errors.append(f"Invalid roadmap phases: {_sample(invalid_phases)}")

    invalid_statuses = conn.execute(
        """
        SELECT ri.id, ri.status_key
        FROM roadmap_items ri
        LEFT JOIN terminology t
          ON t.domain = 'roadmap_status' AND t.internal_key = ri.status_key
        WHERE ri.deleted_at IS NULL AND t.internal_key IS NULL
        """
    ).fetchall()
    if invalid_statuses:
        errors.append(f"Invalid roadmap statuses: {_sample(invalid_statuses)}")

    missing_deps = conn.execute(
        """
        SELECT rd.item_id, rd.depends_on_id, rd.dependency_type
        FROM roadmap_dependencies rd
        LEFT JOIN roadmap_items ri
          ON ri.id = rd.item_id AND ri.deleted_at IS NULL
        LEFT JOIN roadmap_items dep
          ON dep.id = rd.depends_on_id AND dep.deleted_at IS NULL
        WHERE ri.id IS NULL OR dep.id IS NULL
        """
    ).fetchall()
    if missing_deps:
        errors.append(f"Missing dependency references: {_sample(missing_deps)}")

    orphaned_refs = conn.execute(
        """
        SELECT rd.item_id, rd.depends_on_id
        FROM roadmap_dependencies rd
        JOIN roadmap_items dep ON dep.id = rd.depends_on_id
        WHERE dep.deleted_at IS NOT NULL
        """
    ).fetchall()
    if orphaned_refs:
        warnings.append(f"Dependencies point at deleted items: {_sample(orphaned_refs)}")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Roadmap hygiene checks")
    parser.add_argument("--db", help="Path to coordination.db")
    parser.add_argument("--strict", action="store_true", help="Fail on hygiene issues")
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="Create a temporary database from migrations if missing",
    )
    args = parser.parse_args()

    db_path: Path | None = None
    temp_dir: tempfile.TemporaryDirectory[str] | None = None

    if args.db:
        db_path = Path(args.db).expanduser().resolve()
    elif args.bootstrap:
        temp_dir = tempfile.TemporaryDirectory(prefix="motus-roadmap-")
        db_path = Path(temp_dir.name) / "coordination.db"
        _bootstrap_db(db_path)
    else:
        env_path = os.environ.get("MOTUS_DATABASE__PATH", "").strip()
        if env_path:
            db_path = Path(env_path).expanduser().resolve()
        else:
            db_path = Path("~/.motus/coordination.db").expanduser()

    if args.bootstrap and db_path is not None and not db_path.exists():
        _bootstrap_db(db_path)

    if db_path is None or not db_path.exists():
        message = f"coordination.db not found at {db_path}"
        if args.strict:
            print(f"FAIL: {message}", file=sys.stderr)
            return 1
        print(f"WARN: {message}")
        return 0

    conn = sqlite3.connect(str(db_path))
    try:
        errors, warnings = _run_checks(conn)
    finally:
        conn.close()
        if temp_dir is not None:
            temp_dir.cleanup()

    if warnings:
        for warn in warnings:
            print(f"WARNING: {warn}")

    if errors:
        print("Roadmap hygiene check failed:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1 if args.strict else 0

    print("Roadmap hygiene check: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
