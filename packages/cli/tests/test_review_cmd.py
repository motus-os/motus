"""Tests for review command behavior."""

from __future__ import annotations

import sqlite3
from types import SimpleNamespace

import pytest

from motus.commands import review_cmd
from motus.commands import roadmap_cmd


class ReviewDBManager:
    """Minimal DB manager for command tests."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def transaction(self):
        from contextlib import contextmanager

        @contextmanager
        def ctx():
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                yield self._connection
                self._connection.execute("COMMIT")
            except Exception:
                self._connection.execute("ROLLBACK")
                raise

        return ctx()


@pytest.fixture
def review_db(tmp_path):
    """Create a temp database for review command tests."""
    db_path = tmp_path / "review_cmd.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE roadmap_items (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            status_key TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            deleted_at TEXT DEFAULT NULL
        );

        INSERT INTO roadmap_items (id, title, status_key) VALUES
            ('ITEM-001', 'Pending item', 'pending'),
            ('ITEM-REVIEW', 'Review item', 'review'),
            ('ITEM-DONE', 'Completed item', 'completed');

        INSERT INTO roadmap_items (id, title, status_key, deleted_at)
        VALUES ('ITEM-DELETED', 'Deleted item', 'pending', '2025-01-01 00:00:00');
        """
    )
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def patch_db_manager(monkeypatch, review_db):
    """Patch get_db_manager to use the test database."""
    test_manager = ReviewDBManager(review_db)
    monkeypatch.setattr(roadmap_cmd, "get_db_manager", lambda: test_manager)
    return test_manager


def test_review_command_dispatches(monkeypatch):
    """review_command forwards to cmd_roadmap_review."""
    called = {}

    def fake_cmd(args):
        called["args"] = args
        return 0

    monkeypatch.setattr(review_cmd, "cmd_roadmap_review", fake_cmd)
    args = SimpleNamespace(item_id="ITEM-001")
    assert review_cmd.review_command(args) == 0
    assert called["args"] is args


def test_cmd_roadmap_review_updates_status(patch_db_manager, review_db):
    """cmd_roadmap_review updates status to review."""
    args = SimpleNamespace(item_id="ITEM-001", comment=None, json=False)
    assert roadmap_cmd.cmd_roadmap_review(args) == 0

    row = review_db.execute(
        "SELECT status_key FROM roadmap_items WHERE id = ?",
        ("ITEM-001",),
    ).fetchone()
    assert row["status_key"] == "review"


def test_cmd_roadmap_review_missing_item(patch_db_manager):
    """cmd_roadmap_review fails for missing items."""
    args = SimpleNamespace(item_id="MISSING", comment=None, json=False)
    assert roadmap_cmd.cmd_roadmap_review(args) == 1


def test_cmd_roadmap_review_deleted_item(patch_db_manager, review_db):
    """cmd_roadmap_review rejects deleted items."""
    args = SimpleNamespace(item_id="ITEM-DELETED", comment=None, json=False)
    assert roadmap_cmd.cmd_roadmap_review(args) == 1

    row = review_db.execute(
        "SELECT status_key FROM roadmap_items WHERE id = ?",
        ("ITEM-DELETED",),
    ).fetchone()
    assert row["status_key"] == "pending"


def test_cmd_roadmap_review_completed_item(patch_db_manager, review_db):
    """cmd_roadmap_review is a no-op for completed items."""
    args = SimpleNamespace(item_id="ITEM-DONE", comment=None, json=False)
    assert roadmap_cmd.cmd_roadmap_review(args) == 0

    row = review_db.execute(
        "SELECT status_key FROM roadmap_items WHERE id = ?",
        ("ITEM-DONE",),
    ).fetchone()
    assert row["status_key"] == "completed"


def test_cmd_roadmap_review_already_review(patch_db_manager, review_db):
    """cmd_roadmap_review is a no-op for review items."""
    args = SimpleNamespace(item_id="ITEM-REVIEW", comment=None, json=False)
    assert roadmap_cmd.cmd_roadmap_review(args) == 0

    row = review_db.execute(
        "SELECT status_key FROM roadmap_items WHERE id = ?",
        ("ITEM-REVIEW",),
    ).fetchone()
    assert row["status_key"] == "review"
