from __future__ import annotations

import json
import subprocess
from pathlib import Path

import motus.process_detector as process_detector_module
from motus.config import config
from motus.process_detector import ProcessDetector


def _completed_process(
    args: list[str], stdout: str = "", returncode: int = 0
) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=args, returncode=returncode, stdout=stdout, stderr="")


def test_process_detector_parses_projects_from_pgrep_and_lsof(monkeypatch, tmp_path: Path) -> None:
    import pathlib

    # Patch Path.home() so the optional Gemini/Codex lsof paths are fully controlled by the test.
    monkeypatch.setattr(pathlib.Path, "home", lambda: tmp_path)

    gemini_tmp = tmp_path / ".gemini" / "tmp"
    (gemini_tmp / "hash1" / "chats").mkdir(parents=True)

    codex_sessions = tmp_path / ".codex" / "sessions"
    codex_sessions.mkdir(parents=True)
    session_file = codex_sessions / "s1.jsonl"
    session_file.write_text(
        json.dumps({"type": "session_meta", "payload": {"cwd": "/tmp/codex_project"}}) + "\n"
    )

    def fake_run(args: list[str], **_kwargs):
        # Claude: pgrep extraction via --project
        if args[:3] == ["pgrep", "-fl", "claude"]:
            return _completed_process(args, stdout="123 claude --project /tmp/claude_project\n")

        # Claude: lsof extraction via ~/.claude/projects/<project>/...
        if args[:2] == ["lsof", "+D"] and args[2] == str(config.paths.projects_dir):
            lsof_path = config.paths.projects_dir / "projB" / "abc.jsonl"
            return _completed_process(args, stdout=f"python 1 user txt 0 0 0 {lsof_path}\n")

        # Gemini: pgrep extraction via --cwd
        if args[:3] == ["pgrep", "-fl", "gemini"]:
            return _completed_process(args, stdout="456 gemini --cwd /tmp/gemini_project\n")

        # Gemini: lsof extraction via ~/.gemini/tmp/<hash>/chats/...
        if args[:2] == ["lsof", "+D"] and args[2] == str(gemini_tmp):
            chat_path = gemini_tmp / "hash1" / "chats" / "chat.json"
            return _completed_process(args, stdout=f"python 2 user txt 0 0 0 {chat_path}\n")

        # Codex: pgrep extraction via -C
        if args[:3] == ["pgrep", "-fl", "codex"]:
            return _completed_process(args, stdout="789 codex -C /tmp/codex_cwd\n")

        # Codex: lsof session file points to JSONL with session_meta cwd
        if args[:2] == ["lsof", "+D"] and args[2] == str(codex_sessions):
            return _completed_process(args, stdout=f"python 3 user txt 0 0 0 {session_file}\n")

        return _completed_process(args, stdout="", returncode=1)

    monkeypatch.setattr(subprocess, "run", fake_run)

    detector = ProcessDetector(cache_ttl=0.0, cache_path=tmp_path / "cache.json")
    projects = detector.get_running_projects()

    assert "/tmp/claude_project" in projects
    assert "projB" in projects
    assert "/tmp/gemini_project" in projects
    assert "gemini:hash1" in projects
    assert "/tmp/codex_cwd" in projects
    assert "/tmp/codex_project" in projects


def test_process_detector_disables_when_pgrep_is_missing(monkeypatch, tmp_path: Path) -> None:
    def fake_run(*_args, **_kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", fake_run)

    detector = ProcessDetector(cache_ttl=0.0, cache_path=tmp_path / "cache.json")
    assert detector.get_running_projects() == set()
    assert detector.is_degraded() is True
    # Fail-silent + cached: once disabled, it should not attempt subprocess execution again.
    assert detector.get_running_projects() == set()


def test_process_detector_uses_cache(monkeypatch, tmp_path: Path) -> None:
    import pathlib

    monkeypatch.setattr(pathlib.Path, "home", lambda: tmp_path)

    calls: list[list[str]] = []

    def fake_run(args: list[str], **_kwargs):
        calls.append(args)
        return _completed_process(args, stdout="", returncode=1)

    monkeypatch.setattr(subprocess, "run", fake_run)

    detector = ProcessDetector(cache_ttl=9999.0, cache_path=tmp_path / "cache.json")
    detector.get_running_projects()
    detector.get_running_projects()

    # First call executes; second call should return cached data (no extra subprocess calls).
    assert len(calls) == 4  # pgrep claude + lsof projects + pgrep gemini + pgrep codex


def test_process_detector_cache_ttl_expires(monkeypatch, tmp_path: Path) -> None:
    import pathlib

    now = 1000.0

    def fake_time():
        return now

    monkeypatch.setattr(process_detector_module.time, "time", fake_time)
    monkeypatch.setattr(pathlib.Path, "home", lambda: tmp_path)

    calls: list[list[str]] = []

    def fake_run(args: list[str], **_kwargs):
        calls.append(args)
        return _completed_process(args, stdout="", returncode=1)

    monkeypatch.setattr(subprocess, "run", fake_run)

    detector = ProcessDetector(cache_ttl=5.0, cache_path=tmp_path / "cache.json")
    detector.get_running_projects()

    now += 4.0
    detector.get_running_projects()
    assert len(calls) == 4

    now += 2.0
    detector.get_running_projects()
    assert len(calls) == 8
