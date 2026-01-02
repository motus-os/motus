from __future__ import annotations

import sqlite3

import pytest

from motus.core.database_connection import DatabaseManager


def test_readonly_connection_rejects_writes(tmp_path):
    db_path = tmp_path / "coordination.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

    db = DatabaseManager(db_path)
    ro_conn = db.get_connection(read_only=True)

    with pytest.raises(sqlite3.OperationalError):
        ro_conn.execute("CREATE TABLE should_fail (id INTEGER PRIMARY KEY)")
