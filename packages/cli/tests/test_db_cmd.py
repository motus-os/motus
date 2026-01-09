# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from motus.cli.exit_codes import EXIT_ERROR, EXIT_SUCCESS
from motus.commands.db_cmd import (
    db_lock_info_command,
    db_recover_command,
    db_stats_command,
    db_wait_command,
)
from motus.core.bootstrap import bootstrap_database_at_path
from motus.core.database_connection import (
    configure_connection,
    get_db_manager,
    reset_db_manager,
)
from motus.core.layered_config import reset_config


def _bootstrap_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_path = tmp_path / "coordination.db"
    monkeypatch.setenv("MOTUS_DATABASE__PATH", str(db_path))
    reset_config()
    reset_db_manager()
    bootstrap_database_at_path(db_path)
    reset_db_manager()
    return db_path


def test_db_stats_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _bootstrap_db(tmp_path, monkeypatch)

    args = SimpleNamespace(json=True)
    assert db_stats_command(args) == EXIT_SUCCESS

    payload = json.loads(capsys.readouterr().out)
    assert payload["db_size_bytes"] >= 0
    assert "table_counts" in payload


def test_db_stats_uses_readonly_connection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _bootstrap_db(tmp_path, monkeypatch)
    db = get_db_manager()
    called = {"value": False}
    original = db.readonly_connection

    @contextmanager
    def wrapped():
        called["value"] = True
        with original() as conn:
            yield conn

    db.readonly_connection = wrapped  # type: ignore[assignment]

    args = SimpleNamespace(json=True)
    assert db_stats_command(args) == EXIT_SUCCESS
    _ = json.loads(capsys.readouterr().out)
    assert called["value"] is True


def test_db_stats_missing_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_path = tmp_path / "missing.db"
    monkeypatch.setenv("MOTUS_DATABASE__PATH", str(db_path))
    reset_config()
    reset_db_manager()

    args = SimpleNamespace(json=True)
    assert db_stats_command(args) == EXIT_ERROR


def test_db_lock_info_json(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _bootstrap_db(tmp_path, monkeypatch)
    db = get_db_manager()
    with db.connection():
        args = SimpleNamespace(json=True)
        assert db_lock_info_command(args) == EXIT_SUCCESS

    payload = json.loads(capsys.readouterr().out)
    assert payload["pid"] == os.getpid()
    assert payload["pid_alive"] is True
    assert payload.get("status") in {"pending", "active"}
    assert payload.get("lock_registry_path")


def test_db_wait_times_out_when_locked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path = _bootstrap_db(tmp_path, monkeypatch)
    conn = sqlite3.connect(
        str(db_path), isolation_level=None, check_same_thread=False
    )
    configure_connection(conn, set_row_factory=False)
    conn.execute("BEGIN IMMEDIATE")
    try:
        args = SimpleNamespace(max_seconds=0.2, interval=0.05)
        assert db_wait_command(args) == EXIT_ERROR
        out = capsys.readouterr().out
        assert "Timed out waiting for write lock" in out
    finally:
        if conn.in_transaction:
            conn.rollback()
        conn.close()


def test_db_wait_succeeds_when_unlocked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _bootstrap_db(tmp_path, monkeypatch)

    args = SimpleNamespace(max_seconds=0.2, interval=0.05)
    assert db_wait_command(args) == EXIT_SUCCESS
    out = capsys.readouterr().out
    assert "Write lock available" in out


def test_db_recover_aborts_when_active_lock(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _bootstrap_db(tmp_path, monkeypatch)
    db = get_db_manager()
    try:
        with db.transaction():
            args = SimpleNamespace()
            assert db_recover_command(args) == EXIT_ERROR
            out = capsys.readouterr().out
            assert "Active lock holder detected" in out
    finally:
        reset_db_manager()
