from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pytest


@dataclass
class _FakeEventType:
    value: str


@dataclass
class _FakeEvent:
    timestamp: datetime
    event_type: _FakeEventType
    content: str


@dataclass
class _FakeSession:
    session_id: str
    file_path: Path
    source: str = "claude"

    def to_dict(self) -> dict:
        return {"session_id": self.session_id, "source": self.source}


class _FakeBuilder:
    def get_last_action(self, file_path: Path) -> str:
        return f"last_action:{file_path.name}"


class _FakeOrchestrator:
    def __init__(self, sessions: list[_FakeSession], events: list[_FakeEvent]) -> None:
        self._sessions = sessions
        self._events = events
        self.last_tail_lines: int | None = None

    def discover_all(self, max_age_hours: int = 168):  # noqa: ARG002 - signature parity
        return list(self._sessions)

    def get_events_tail(
        self, session: _FakeSession, *, n_lines: int = 200
    ):  # noqa: ARG002 - signature parity
        self.last_tail_lines = n_lines
        return list(self._events)

    def get_builder(self, source: str):  # noqa: ARG002 - signature parity
        return _FakeBuilder()


def test_feed_session_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    from motus.commands import feed_cmd

    orch = _FakeOrchestrator([], [])
    monkeypatch.setattr(feed_cmd, "get_orchestrator", lambda: orch)

    with pytest.raises(SystemExit):
        feed_cmd.feed_session("missing")


def test_feed_session_happy_path_bounds_tail_lines(monkeypatch: pytest.MonkeyPatch) -> None:
    from motus.commands import feed_cmd

    session = _FakeSession(session_id="abc123", file_path=Path("/tmp/session.jsonl"))
    event = _FakeEvent(
        timestamp=datetime(2025, 1, 1, 0, 0, 0),
        event_type=_FakeEventType("tool"),
        content="content",
    )
    orch = _FakeOrchestrator([session], [event])
    monkeypatch.setattr(feed_cmd, "get_orchestrator", lambda: orch)
    monkeypatch.setattr(feed_cmd, "redact_secrets", lambda s: s)

    feed_cmd.feed_session("abc", tail_lines=1)
    assert orch.last_tail_lines == 10


def test_show_session_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    from motus.commands import show_cmd

    orch = _FakeOrchestrator([], [])
    monkeypatch.setattr(show_cmd, "get_orchestrator", lambda: orch)

    with pytest.raises(SystemExit):
        show_cmd.show_session("missing")


def test_show_session_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    from motus.commands import show_cmd

    session = _FakeSession(session_id="abc123", file_path=Path("/tmp/session.jsonl"))
    orch = _FakeOrchestrator([session], [])
    monkeypatch.setattr(show_cmd, "get_orchestrator", lambda: orch)

    show_cmd.show_session("abc")
