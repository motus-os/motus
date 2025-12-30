import os
import sqlite3
import time
from pathlib import Path


def _write_jsonl(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")


def _set_mtime(path: Path, *, mtime_seconds: float) -> None:
    os.utime(path, (mtime_seconds, mtime_seconds))


def test_sync_full_ingests_and_query_returns_cached_sessions(tmp_path, monkeypatch):
    from motus.config import PathConfig, config
    from motus.core.bootstrap import bootstrap_database_at_path
    from motus.session_cache import SessionSQLiteCache

    claude_root = tmp_path / ".claude"
    projects_dir = claude_root / "projects" / "-Users-test-project"
    session_file = projects_dir / "abc123.jsonl"

    _write_jsonl(
        session_file,
        [
            '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Read","input":{"file_path":"b.txt"}}]}}',
            '{"type":"assistant","message":{"content":[{"type":"text","text":"ok"}]}}',
            '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Write","input":{"file_path":"a.txt"}}]}}',
        ],
    )

    # Ensure the file is "recent"
    _set_mtime(session_file, mtime_seconds=time.time())

    # Point config to our temp claude dir
    monkeypatch.setattr(config, "paths", PathConfig(claude_dir=claude_root))

    # Create test DB and apply migrations
    db_path = tmp_path / "coordination.db"
    bootstrap_database_at_path(db_path)

    cache = SessionSQLiteCache(db_path=db_path)
    result = cache.sync(full=True)
    assert result.files_seen == 1
    assert result.ingested == 1

    sessions = cache.query(max_age_hours=24)
    assert len(sessions) == 1
    assert sessions[0].session_id == "abc123"
    assert sessions[0].file_path == session_file
    assert sessions[0].last_action.startswith("Write")
    assert sessions[0].has_completion is True


def test_sync_missing_projects_dir_returns_empty(tmp_path, monkeypatch):
    from motus.config import PathConfig, config
    from motus.core.bootstrap import bootstrap_database_at_path
    from motus.session_cache import SessionSQLiteCache

    claude_root = tmp_path / ".claude"
    monkeypatch.setattr(config, "paths", PathConfig(claude_dir=claude_root))

    db_path = tmp_path / "coordination.db"
    bootstrap_database_at_path(db_path)

    cache = SessionSQLiteCache(db_path=db_path)
    result = cache.sync(full=True)

    assert result.files_seen == 0
    assert result.ingested == 0
    assert result.partial == 0
    assert result.corrupted == 0
    assert result.skipped == 0


def test_sync_idempotent_skips_unchanged(tmp_path, monkeypatch):
    from motus.config import PathConfig, config
    from motus.core.bootstrap import bootstrap_database_at_path
    from motus.session_cache import SessionSQLiteCache

    claude_root = tmp_path / ".claude"
    projects_dir = claude_root / "projects" / "-Users-test-project"
    session_file = projects_dir / "abc123.jsonl"
    _write_jsonl(
        session_file,
        ['{"type":"assistant","message":{"content":[{"type":"text","text":"hi"}]}}'],
    )
    _set_mtime(session_file, mtime_seconds=time.time())
    monkeypatch.setattr(config, "paths", PathConfig(claude_dir=claude_root))

    db_path = tmp_path / "coordination.db"
    bootstrap_database_at_path(db_path)

    cache = SessionSQLiteCache(db_path=db_path)
    first = cache.sync(full=True)
    assert first.ingested == 1

    second = cache.sync(full=True)
    assert second.ingested == 0
    assert second.unchanged == 1


def test_sync_missing_projects_dir_returns_empty(tmp_path, monkeypatch):
    from motus.config import PathConfig, config
    from motus.core.bootstrap import bootstrap_database_at_path
    from motus.session_cache import SessionSQLiteCache

    claude_root = tmp_path / ".claude"
    monkeypatch.setattr(config, "paths", PathConfig(claude_dir=claude_root))

    db_path = tmp_path / "coordination.db"
    bootstrap_database_at_path(db_path)

    cache = SessionSQLiteCache(db_path=db_path)
    result = cache.sync(full=True)
    assert result.files_seen == 0
    assert result.ingested == 0
    assert result.unchanged == 0
    assert result.partial == 0
    assert result.corrupted == 0
    assert result.skipped == 0


def test_corrupted_jsonl_is_marked_and_skipped_in_query(tmp_path, monkeypatch):
    from motus.config import PathConfig, config
    from motus.core.bootstrap import bootstrap_database_at_path
    from motus.session_cache import SessionSQLiteCache

    claude_root = tmp_path / ".claude"
    projects_dir = claude_root / "projects" / "-Users-test-project"
    good = projects_dir / "good.jsonl"
    bad = projects_dir / "bad.jsonl"

    _write_jsonl(good, ['{"type":"assistant","message":{"content":[{"type":"text","text":"ok"}]}}'])
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text('{"type":\n', encoding="utf-8")  # invalid JSON (with newline)
    _set_mtime(good, mtime_seconds=time.time())
    _set_mtime(bad, mtime_seconds=time.time())

    monkeypatch.setattr(config, "paths", PathConfig(claude_dir=claude_root))
    db_path = tmp_path / "coordination.db"
    bootstrap_database_at_path(db_path)

    cache = SessionSQLiteCache(db_path=db_path)
    result = cache.sync(full=True)
    assert result.files_seen == 2
    assert result.corrupted == 1

    sessions = cache.query(max_age_hours=24)
    assert [s.session_id for s in sessions] == ["good"]

    # Corrupted session stored as status=corrupted
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT status, parse_error FROM session_file_cache WHERE id = ?", ("bad",)
        ).fetchone()
        assert row is not None
        assert row[0] == "corrupted"
        assert row[1]
