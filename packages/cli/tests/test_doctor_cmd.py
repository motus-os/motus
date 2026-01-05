# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

from __future__ import annotations

import json
from pathlib import Path

import pytest

from motus.commands.doctor_cmd import doctor_command
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


def test_doctor_json_output(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _bootstrap_db(tmp_path, monkeypatch)

    exit_code = doctor_command(json_output=True, fix=False)
    assert exit_code in (0, 1)

    payload = json.loads(capsys.readouterr().out)
    assert "summary" in payload
    assert "checks" in payload
