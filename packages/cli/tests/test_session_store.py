from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from motus.exceptions import SessionNotFoundError
from motus.protocols import SessionStatus, Source, UnifiedSession
from motus.session_store import SessionStore


def test_create_session_persists_and_lists_active(tmp_path: Path) -> None:
    db_path = tmp_path / "sessions.db"
    store = SessionStore(db_path)

    session_id = store.create_session(tmp_path, "codex")
    assert session_id.startswith("mot_ses_")

    session = store.get_session(session_id)
    assert session is not None
    assert session.cwd == tmp_path
    assert session.agent_type == "codex"
    assert session.status == "active"

    active = store.get_active_sessions()
    assert [s.session_id for s in active] == [session_id]


def test_complete_session_updates_status(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.db")
    session_id = store.create_session(tmp_path, "haiku")

    store.complete_session(session_id, "completed")
    session = store.get_session(session_id)
    assert session is not None
    assert session.status == "completed"
    assert session.outcome == "completed"

    assert store.get_active_sessions() == []


def test_complete_session_missing_raises(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.db")

    with pytest.raises(SessionNotFoundError):
        store.complete_session("missing-session", "failed")


def test_find_abandoned_sessions_uses_updated_at(tmp_path: Path) -> None:
    db_path = tmp_path / "sessions.db"
    store = SessionStore(db_path)

    old_session = store.create_session(tmp_path, "opus")
    new_session = store.create_session(tmp_path, "sonnet")

    old_time = datetime.now(tz=timezone.utc) - timedelta(hours=48)
    old_iso = old_time.isoformat().replace("+00:00", "Z")

    store.touch_session(new_session)

    import sqlite3

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
            (old_iso, old_session),
        )

    abandoned = store.find_abandoned_sessions(threshold_hours=24)
    abandoned_ids = {session.session_id for session in abandoned}
    assert old_session in abandoned_ids
    assert new_session not in abandoned_ids


def test_persist_from_unified_and_get_all_sessions(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.db")
    now = datetime.now()
    session = UnifiedSession(
        session_id="test-session",
        source=Source.CLAUDE,
        file_path=tmp_path / "test.jsonl",
        project_path=str(tmp_path),
        created_at=now,
        last_modified=now,
        status=SessionStatus.ACTIVE,
        status_reason="active",
    )

    store.persist_from_unified(session)
    sessions = store.get_all_sessions()

    assert len(sessions) == 1
    record = sessions[0]
    assert record.session_id == "test-session"
    assert record.cwd == tmp_path
    assert record.agent_type == "claude"
    assert record.status == "active"
