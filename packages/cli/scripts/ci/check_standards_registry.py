#!/usr/bin/env python3
"""Validate standards registry seed data and versioning."""
from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

from motus.core.migrations_schema import _apply_audit_columns, parse_migration_file


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _apply_migrations(conn: sqlite3.Connection, migrations_dir: Path) -> None:
    for migration_path in sorted(migrations_dir.glob("*.sql")):
        migration = parse_migration_file(migration_path)
        if migration.up_sql.strip():
            conn.executescript(migration.up_sql)
        if migration.name == "add_audit_columns":
            _apply_audit_columns(conn)


def _collect_ids(rows: list[sqlite3.Row]) -> set[str]:
    return {str(row[0]) for row in rows}


def main() -> int:
    repo_root = _repo_root()
    migrations_dir = repo_root / "packages" / "cli" / "migrations"
    if not migrations_dir.exists():
        print(f"ERROR: migrations dir missing: {migrations_dir}", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "standards.db"
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            _apply_migrations(conn, migrations_dir)
        except Exception as exc:
            print(f"ERROR: failed to apply migrations: {exc}", file=sys.stderr)
            return 2

        standards = conn.execute(
            "SELECT id FROM standards WHERE deleted_at IS NULL ORDER BY id"
        ).fetchall()
        if not standards:
            print("ERROR: standards registry is empty", file=sys.stderr)
            return 1

        versions = conn.execute(
            "SELECT entity_id FROM entity_versions WHERE entity_type = 'standard'"
        ).fetchall()

        standard_ids = _collect_ids(standards)
        versioned_ids = _collect_ids(versions)
        missing_versions = sorted(standard_ids - versioned_ids)
        if missing_versions:
            print("ERROR: standards missing version records:", file=sys.stderr)
            for standard_id in missing_versions:
                print(f"  - {standard_id}", file=sys.stderr)
            return 1

        trigger_rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'trigger' "
            "AND name IN ('standards_version_seed', 'standards_version_capture')"
        ).fetchall()
        trigger_names = _collect_ids(trigger_rows)
        missing_triggers = {
            "standards_version_seed",
            "standards_version_capture",
        } - trigger_names
        if missing_triggers:
            print("ERROR: standards versioning triggers missing:", file=sys.stderr)
            for trigger in sorted(missing_triggers):
                print(f"  - {trigger}", file=sys.stderr)
            return 1

    print("OK: standards registry seeded and versioned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
