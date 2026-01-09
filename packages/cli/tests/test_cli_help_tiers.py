import sys
from contextlib import contextmanager

import pytest


def _run_cli_help(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    *,
    argv: list[str],
) -> str:
    monkeypatch.setattr(sys, "argv", argv)

    from motus.cli import core

    core.main()
    captured = capsys.readouterr()
    return captured.out + captured.err


def test_help_tier_uses_readonly_db(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.delenv("MC_HELP_TIER", raising=False)

    from motus.core.bootstrap import bootstrap_database_at_path
    from motus.core.database_connection import get_db_manager, reset_db_manager
    from motus.core.layered_config import reset_config

    db_path = tmp_path / "coordination.db"
    monkeypatch.setenv("MOTUS_DATABASE__PATH", str(db_path))
    reset_config()
    reset_db_manager()
    bootstrap_database_at_path(db_path)
    reset_db_manager()

    db = get_db_manager()
    called = {"value": False}
    original = db.readonly_connection

    @contextmanager
    def wrapped():
        called["value"] = True
        with original() as conn:
            yield conn

    db.readonly_connection = wrapped  # type: ignore[assignment]

    from motus.cli.help import compute_visible_help_tier

    assert compute_visible_help_tier() == 0
    assert called["value"] is True

    reset_db_manager()
    reset_config()


def test_mc_help_tier_0_shows_only_tier_0_commands(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("MC_HELP_TIER", "0")

    out = _run_cli_help(monkeypatch, capsys, argv=["motus", "--help"])

    assert "Tier 0" in out
    assert "  web" in out
    assert "  list" in out
    assert "  watch" in out

    assert "Tier 1" not in out
    assert "policy" not in out
    assert "orient" not in out
    assert "standards" not in out
    assert "claims" not in out


def test_mc_help_tier_2_includes_policy(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("MC_HELP_TIER", "2")

    out = _run_cli_help(monkeypatch, capsys, argv=["motus", "--help"])

    assert "Tier 2" in out
    assert "  policy" in out
    assert "Tier 3" not in out
    assert "  orient" not in out


def test_mc_help_all_shows_advanced_commands(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("MC_HELP_TIER", "0")

    out = _run_cli_help(monkeypatch, capsys, argv=["motus", "--help-all"])

    assert "Tier 3" in out
    assert "  orient" in out
    assert "  standards" in out
    assert "  claims" in out
    assert "  modules" in out
    assert "  gates" in out
