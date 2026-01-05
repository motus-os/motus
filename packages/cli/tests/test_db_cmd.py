# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from motus.cli.exit_codes import EXIT_ERROR, EXIT_SUCCESS
from motus.commands.db_cmd import db_stats_command
from motus.core.bootstrap import bootstrap_database_at_path
from motus.core.database_connection import reset_db_manager
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


def test_db_stats_missing_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_path = tmp_path / "missing.db"
    monkeypatch.setenv("MOTUS_DATABASE__PATH", str(db_path))
    reset_config()
    reset_db_manager()

    args = SimpleNamespace(json=True)
    assert db_stats_command(args) == EXIT_ERROR
