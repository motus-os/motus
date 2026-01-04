from __future__ import annotations

import sys
from unittest.mock import patch

import pytest


def _run_help(argv: list[str], capsys: pytest.CaptureFixture[str]) -> int:
    with patch("sys.argv", argv):
        from motus.cli.core import main

        with pytest.raises(SystemExit) as exc:
            main()
    _ = capsys.readouterr()
    return exc.value.code


def test_health_help_exists(capsys: pytest.CaptureFixture[str]) -> None:
    code = _run_help(["motus", "health", "--help"], capsys)
    assert code == 0


def test_verify_clean_help_exists(capsys: pytest.CaptureFixture[str]) -> None:
    code = _run_help(["motus", "verify", "clean", "--help"], capsys)
    assert code == 0


def test_handoffs_list_help_exists(capsys: pytest.CaptureFixture[str]) -> None:
    code = _run_help(["motus", "handoffs", "list", "--help"], capsys)
    assert code == 0


def test_handoffs_check_requires_root(capsys: pytest.CaptureFixture[str]) -> None:
    with patch("sys.argv", ["motus", "handoffs", "check"]):
        from motus.cli.core import main

        with pytest.raises(SystemExit) as exc:
            main()

    assert exc.value.code == 2
