# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from motus.observability.activity import ActivityLedger


def _run_cli(argv: list[str], capsys: pytest.CaptureFixture[str]) -> int:
    with patch("sys.argv", argv):
        from motus.cli.core import main

        with pytest.raises(SystemExit) as exc:
            main()
    _ = capsys.readouterr()
    return exc.value.code


def test_activity_help_exists(capsys: pytest.CaptureFixture[str]) -> None:
    code = _run_cli(["motus", "activity", "--help"], capsys)
    assert code == 0


def test_activity_list_reads_ledger(tmp_path, monkeypatch, capsys: pytest.CaptureFixture[str]) -> None:
    ledger_dir = tmp_path / "ledger"
    monkeypatch.setenv("MOTUS_ACTIVITY_DIR", str(ledger_dir))

    ActivityLedger().emit(
        actor="test",
        category="cli",
        action="invoke",
        subject={"command": "activity"},
    )

    with patch("sys.argv", ["motus", "activity", "list", "--limit", "1"]):
        from motus.cli.core import main

        with pytest.raises(SystemExit) as exc:
            main()

    assert exc.value.code == 0
    out = capsys.readouterr().out.strip()
    payload = json.loads(out.splitlines()[-1])
    assert payload["category"] == "cli"
