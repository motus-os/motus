from __future__ import annotations

import sqlite3
from pathlib import Path

from motus.api import facade as facade_module
from motus.core.database_connection import DatabaseManager
from motus.core.migrations_schema import _apply_audit_columns, parse_migration_file


MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"


def _apply_all_migrations(conn: sqlite3.Connection) -> None:
    for migration_path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        migration = parse_migration_file(migration_path)
        if migration.up_sql.strip():
            conn.executescript(migration.up_sql)
        if migration.name == "add_audit_columns":
            _apply_audit_columns(conn)


def test_decision_persistence_drops_missing_attempt(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "coordination.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    _apply_all_migrations(conn)
    conn.execute(
        "INSERT INTO roadmap_items (id, phase_key, title, status_key) "
        "VALUES ('WORK-1', 'phase_a', 'Work', 'pending')"
    )
    conn.commit()
    conn.close()

    db = DatabaseManager(db_path)
    monkeypatch.setattr(facade_module, "get_db_manager", lambda: db)

    ok = facade_module._persist_decision(
        decision_id="decision-1",
        lease_id="lease-1",
        decision_type="approval",
        decision_summary="summary",
        work_id="WORK-1",
        attempt_id="attempt-missing",
    )
    assert ok is True

    with db.readonly_connection() as ro_conn:
        row = ro_conn.execute(
            "SELECT work_id, attempt_id FROM decisions WHERE id = ?",
            ("decision-1",),
        ).fetchone()
    assert row is not None
    assert row["work_id"] == "WORK-1"
    assert row["attempt_id"] is None
