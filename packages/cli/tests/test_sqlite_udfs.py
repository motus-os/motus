"""Tests for SQLite UDF registration."""

from __future__ import annotations

import sqlite3

from motus.core.database_connection import configure_connection


def test_sqlite_udfs_registered() -> None:
    conn = sqlite3.connect(":memory:")
    configure_connection(conn)

    assert conn.execute(
        "SELECT mc_strip_prefix('foo/bar', 'foo/')"
    ).fetchone()[0] == "bar"

    assert conn.execute(
        "SELECT mc_sha256('test')"
    ).fetchone()[0] == "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"

    assert conn.execute(
        "SELECT mc_id('ev', 'seed')"
    ).fetchone()[0] == "ev-19b25856e1c1"

    assert conn.execute(
        "SELECT mc_date_add('2025-01-01T00:00:00Z', 3600)"
    ).fetchone()[0] == "2025-01-01T01:00:00Z"

    assert conn.execute(
        "SELECT mc_date_diff('2025-01-01T00:00:00Z', '2025-01-01T00:00:10Z')"
    ).fetchone()[0] == 10

    conn.close()
