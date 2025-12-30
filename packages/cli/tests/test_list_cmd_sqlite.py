from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from motus.session_store import SessionRecord


def test_find_sessions_uses_sqlite_when_flag_set(monkeypatch, tmp_path: Path) -> None:
    from motus.commands import list_cmd

    now = datetime.now(tz=timezone.utc)
    record = SessionRecord(
        session_id="session-1",
        cwd=tmp_path,
        agent_type="claude",
        created_at=now,
        updated_at=now,
        status="active",
        outcome=None,
    )

    class StubStore:
        def __init__(self) -> None:
            pass

        def get_all_sessions(self):
            return [record]

    def _boom():
        raise AssertionError("orchestrator should not be called")

    monkeypatch.setenv("MC_USE_SQLITE", "1")
    monkeypatch.setattr(list_cmd, "SessionStore", StubStore)
    monkeypatch.setattr(list_cmd, "_record_list_metric", lambda *args, **kwargs: None)

    import motus.orchestrator as orchestrator

    monkeypatch.setattr(orchestrator, "get_orchestrator", _boom)

    sessions = list_cmd.find_sessions(max_age_hours=24)
    assert len(sessions) == 1
    assert sessions[0].session_id == "session-1"
