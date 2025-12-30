"""Tests for MCP server implementation."""

from __future__ import annotations

import inspect
from datetime import datetime
from pathlib import Path

import pytest

from motus.mcp.server import create_server
from motus.mcp.tools import (
    export_teleport,
    get_context,
    get_events,
    get_session,
    list_sessions,
)
from motus.protocols import (
    EventType,
    SessionStatus,
    Source,
    TeleportBundle,
    UnifiedEvent,
    UnifiedSession,
)


class FakeOrchestrator:
    def __init__(self, sessions: list[UnifiedSession]):
        self._sessions = sessions

    def discover_all(self, max_age_hours: int = 24, sources=None):
        return self._sessions

    def get_session(self, session_id: str):
        for s in self._sessions:
            if s.session_id == session_id:
                return s
        return None

    def get_events(self, session: UnifiedSession):
        return self.get_events_tail(session, n_lines=999999)

    def get_events_tail(self, session: UnifiedSession, n_lines: int = 200):
        secret = "sk-aaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        return [
            UnifiedEvent(
                event_id="e1",
                session_id=session.session_id,
                timestamp=datetime.now(),
                event_type=EventType.THINKING,
                content=f"Working on {session.project_path} with key {secret}",
                raw_data={"path": session.project_path, "secret": secret},
            )
        ]

    def get_events_validated(self, session: UnifiedSession, refresh: bool = False):
        raise AssertionError("validated not used in this test")

    def get_events_tail_validated(self, session: UnifiedSession, n_lines: int = 200):
        raise AssertionError("validated not used in this test")

    def get_context(self, session: UnifiedSession):
        return {
            "files_modified": [f"{session.project_path}/secrets.txt"],
            "notes": "token=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        }

    def export_teleport(self, session: UnifiedSession, include_planning_docs: bool = True):
        return TeleportBundle(
            source_session=session.session_id,
            source_model="test-model",
            timestamp=datetime.now(),
            intent="Do the thing",
            decisions=["Use sk-aaaaaaaaaaaaaaaaaaaaaaaaaaaa"],
            files_touched=[f"{session.project_path}/file.py"],
            hot_files=[],
            pending_todos=[],
            last_action="Edit /home/user/projects/file.py",
            planning_docs={"ROADMAP.md": "path: /home/user/notes"},
        )


@pytest.fixture
def fake_session() -> UnifiedSession:
    return UnifiedSession(
        session_id="abc123",
        source=Source.CLAUDE,
        file_path=Path("/home/user/.claude/projects/x/abc123.jsonl"),
        project_path="/home/user/projects/demo",
        created_at=datetime.now(),
        last_modified=datetime.now(),
        status=SessionStatus.ACTIVE,
        status_reason="ok",
    )


@pytest.mark.asyncio
async def test_server_registers_tools():
    server = create_server()
    tools = server.list_tools()
    if inspect.isawaitable(tools):
        tools = await tools
    names = {t.name for t in tools}
    assert names == {"list_sessions", "get_session", "get_events", "get_context", "export_teleport"}


def test_redaction_defaults_are_secure():
    for fn in (get_events, get_session, get_context):
        sig = inspect.signature(fn)
        assert sig.parameters["redact"].default is True


def test_list_sessions_always_redacts(monkeypatch, fake_session: UnifiedSession):
    from motus.mcp import tools as tools_mod

    monkeypatch.setattr(tools_mod, "get_orchestrator", lambda: FakeOrchestrator([fake_session]))
    out = list_sessions(limit=10)
    assert out["sessions"][0]["project_path"].startswith("/[REDACTED_HOME]")


def test_get_session_redacts_by_default(monkeypatch, fake_session: UnifiedSession):
    from motus.mcp import tools as tools_mod

    monkeypatch.setattr(tools_mod, "get_orchestrator", lambda: FakeOrchestrator([fake_session]))
    out = get_session("abc123")
    assert out["session"]["project_path"].startswith("/[REDACTED_HOME]")


def test_get_session_redact_false_returns_full(monkeypatch, fake_session: UnifiedSession):
    from motus.mcp import tools as tools_mod

    monkeypatch.setattr(tools_mod, "get_orchestrator", lambda: FakeOrchestrator([fake_session]))
    out = get_session("abc123", redact=False)
    assert out["session"]["project_path"].startswith("/home/user/")


def test_get_events_redacts_by_default_and_drops_raw_data(
    monkeypatch, fake_session: UnifiedSession
):
    from motus.mcp import tools as tools_mod

    monkeypatch.setattr(tools_mod, "get_orchestrator", lambda: FakeOrchestrator([fake_session]))
    out = get_events("abc123")
    ev0 = out["events"][0]
    assert out["truncated"] is True
    assert "raw_data" not in ev0
    assert "[REDACTED_OPENAI_KEY]" in ev0["content"]
    assert "/[REDACTED_HOME]" in ev0["content"]


def test_get_events_redact_false_includes_secrets_when_requested(
    monkeypatch, fake_session: UnifiedSession
):
    from motus.mcp import tools as tools_mod

    monkeypatch.setattr(tools_mod, "get_orchestrator", lambda: FakeOrchestrator([fake_session]))
    out = get_events("abc123", redact=False, include_raw_data=True, full=True)
    ev0 = out["events"][0]
    assert out["truncated"] is False
    assert "raw_data" in ev0
    assert "sk-aaaaaaaaaaaaaaaaaaaaaaaaaaaa" in ev0["content"]


def test_get_context_redacts_by_default(monkeypatch, fake_session: UnifiedSession):
    from motus.mcp import tools as tools_mod

    monkeypatch.setattr(tools_mod, "get_orchestrator", lambda: FakeOrchestrator([fake_session]))
    out = get_context("abc123")
    assert "/[REDACTED_HOME]" in out["context"]["files_modified"][0]
    assert "token=[REDACTED]" in out["context"]["notes"]


def test_export_teleport_redacts_by_default(monkeypatch, fake_session: UnifiedSession):
    from motus.mcp import tools as tools_mod

    monkeypatch.setattr(tools_mod, "get_orchestrator", lambda: FakeOrchestrator([fake_session]))
    out = export_teleport("abc123")
    bundle = out["bundle"]
    assert any("[REDACTED_OPENAI_KEY]" in d for d in bundle["decisions"])
    assert "/[REDACTED_HOME]" in bundle["planning_docs"]["ROADMAP.md"]


def test_prefix_lookup_ambiguous(monkeypatch, fake_session: UnifiedSession):
    from motus.mcp import tools as tools_mod

    s1 = fake_session
    s2 = UnifiedSession(
        session_id="abc999",
        source=Source.CLAUDE,
        file_path=Path("/home/user/.claude/projects/x/abc999.jsonl"),
        project_path="/home/user/projects/demo2",
        created_at=datetime.now(),
        last_modified=datetime.now(),
        status=SessionStatus.ACTIVE,
        status_reason="ok",
    )
    monkeypatch.setattr(tools_mod, "get_orchestrator", lambda: FakeOrchestrator([s1, s2]))
    with pytest.raises(ValueError, match="Ambiguous session prefix"):
        get_session("abc")
