import os
import time
from pathlib import Path


def _set_mtime(path: Path, *, mtime_seconds: float) -> None:
    os.utime(path, (mtime_seconds, mtime_seconds))


def test_symlink_attack_is_skipped(tmp_path, monkeypatch):
    from motus.config import PathConfig, config
    from motus.core.bootstrap import bootstrap_database_at_path
    from motus.session_cache import SessionSQLiteCache

    claude_root = tmp_path / ".claude"
    projects_dir = claude_root / "projects" / "-Users-test-project"
    projects_dir.mkdir(parents=True, exist_ok=True)

    target = tmp_path / "secret.txt"
    target.write_text("SECRET", encoding="utf-8")

    link = projects_dir / "link.jsonl"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        # If symlinks are unavailable on this platform, skip the test.
        return

    _set_mtime(link, mtime_seconds=time.time())
    monkeypatch.setattr(config, "paths", PathConfig(claude_dir=claude_root))

    db_path = tmp_path / "coordination.db"
    bootstrap_database_at_path(db_path)

    cache = SessionSQLiteCache(db_path=db_path)
    result = cache.sync(full=True)
    assert result.files_seen == 1
    assert result.skipped == 1


def test_partial_write_is_not_ingested(tmp_path, monkeypatch):
    from motus.config import PathConfig, config
    from motus.core.bootstrap import bootstrap_database_at_path
    from motus.session_cache import SessionSQLiteCache

    claude_root = tmp_path / ".claude"
    projects_dir = claude_root / "projects" / "-Users-test-project"
    projects_dir.mkdir(parents=True, exist_ok=True)

    session_file = projects_dir / "partial.jsonl"
    # Missing trailing newline on purpose
    session_file.write_text('{"type":"assistant"}', encoding="utf-8")
    _set_mtime(session_file, mtime_seconds=time.time())
    monkeypatch.setattr(config, "paths", PathConfig(claude_dir=claude_root))

    db_path = tmp_path / "coordination.db"
    bootstrap_database_at_path(db_path)

    cache = SessionSQLiteCache(db_path=db_path)
    result = cache.sync(full=True)
    assert result.files_seen == 1
    assert result.partial == 1


def test_giant_file_is_skipped(tmp_path, monkeypatch):
    import motus.session_cache as sc
    from motus.config import PathConfig, config
    from motus.core.bootstrap import bootstrap_database_at_path

    claude_root = tmp_path / ".claude"
    projects_dir = claude_root / "projects" / "-Users-test-project"
    projects_dir.mkdir(parents=True, exist_ok=True)

    session_file = projects_dir / "big.jsonl"
    session_file.write_bytes(b'{"type":"assistant"}\n' + b"x" * 64)
    _set_mtime(session_file, mtime_seconds=time.time())

    monkeypatch.setattr(config, "paths", PathConfig(claude_dir=claude_root))
    monkeypatch.setattr(sc, "MAX_INGEST_FILE_BYTES", 16)

    db_path = tmp_path / "coordination.db"
    bootstrap_database_at_path(db_path)

    cache = sc.SessionSQLiteCache(db_path=db_path)
    result = cache.sync(full=True)
    assert result.files_seen == 1
    assert result.skipped == 1
