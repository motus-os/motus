from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

import motus.protocols_models as protocols_models
from motus.protocols_enums import (
    EventType,
    FileOperation,
    RiskLevel,
    SessionStatus,
    Source,
    ToolStatus,
)
from motus.protocols_models import UnifiedEvent, UnifiedSession
from tests.fixtures.constants import FIXED_TIMESTAMP, FIXED_TIMESTAMP_NAIVE


def test_unified_event_to_dict_minimal_fields() -> None:
    event = UnifiedEvent(
        event_id="e1",
        session_id="s1",
        timestamp=FIXED_TIMESTAMP,
        event_type=EventType.THINKING,
        content="Thinking",
    )
    payload = event.to_dict()
    assert payload["event_id"] == "e1"
    assert payload["event_type"] == "thinking"
    assert payload["tool_name"] is None


def test_unified_event_to_dict_includes_tool_fields() -> None:
    event = UnifiedEvent(
        event_id="e2",
        session_id="s1",
        timestamp=FIXED_TIMESTAMP,
        event_type=EventType.TOOL,
        content="Run tool",
        tool_name="Bash",
        tool_input={"command": "ls"},
        tool_output="ok",
        tool_use_id="tu1",
        tool_status=ToolStatus.SUCCESS,
        risk_level=RiskLevel.MEDIUM,
        tool_latency_ms=12,
    )
    payload = event.to_dict()
    assert payload["tool_name"] == "Bash"
    assert payload["tool_status"] == "success"
    assert payload["risk_level"] == "medium"


def test_unified_event_to_dict_includes_file_fields() -> None:
    event = UnifiedEvent(
        event_id="e3",
        session_id="s1",
        timestamp=FIXED_TIMESTAMP,
        event_type=EventType.FILE_CHANGE,
        content="Edit",
        file_path="/tmp/file.txt",
        file_operation=FileOperation.EDIT,
        lines_added=3,
        lines_removed=1,
    )
    payload = event.to_dict()
    assert payload["file_path"] == "/tmp/file.txt"
    assert payload["file_operation"] == "edit"
    assert payload["lines_added"] == 3


def test_unified_event_to_dict_includes_agent_fields() -> None:
    event = UnifiedEvent(
        event_id="e4",
        session_id="s1",
        timestamp=FIXED_TIMESTAMP,
        event_type=EventType.AGENT_SPAWN,
        content="Spawn",
        agent_type="assistant",
        agent_description="Analyze",
        agent_prompt="do work",
        agent_model="gpt",
        parent_event_id="p1",
        agent_depth=1,
    )
    payload = event.to_dict()
    assert payload["agent_type"] == "assistant"
    assert payload["agent_model"] == "gpt"
    assert payload["agent_depth"] == 1


def test_unified_event_to_dict_includes_model_fields() -> None:
    event = UnifiedEvent(
        event_id="e5",
        session_id="s1",
        timestamp=FIXED_TIMESTAMP,
        event_type=EventType.RESPONSE,
        content="Response",
        model="gpt-4",
        tokens_used=100,
        cache_hit=True,
    )
    payload = event.to_dict()
    assert payload["model"] == "gpt-4"
    assert payload["tokens_used"] == 100
    assert payload["cache_hit"] is True


def test_unified_event_default_lists_are_unique() -> None:
    event_a = UnifiedEvent(
        event_id="e6",
        session_id="s1",
        timestamp=FIXED_TIMESTAMP,
        event_type=EventType.DECISION,
        content="Decision",
    )
    event_b = UnifiedEvent(
        event_id="e7",
        session_id="s2",
        timestamp=FIXED_TIMESTAMP,
        event_type=EventType.DECISION,
        content="Decision",
    )
    event_a.files_affected.append("a.py")
    assert event_b.files_affected == []


def test_unified_session_is_active_true() -> None:
    session = UnifiedSession(
        session_id="s1",
        source=Source.CLAUDE,
        file_path=Path("/tmp/session.jsonl"),
        project_path="/tmp/project",
        created_at=FIXED_TIMESTAMP_NAIVE,
        last_modified=FIXED_TIMESTAMP_NAIVE,
        status=SessionStatus.ACTIVE,
        status_reason="fresh",
    )
    assert session.is_active is True


def test_unified_session_is_active_false() -> None:
    session = UnifiedSession(
        session_id="s1",
        source=Source.CLAUDE,
        file_path=Path("/tmp/session.jsonl"),
        project_path="/tmp/project",
        created_at=FIXED_TIMESTAMP_NAIVE,
        last_modified=FIXED_TIMESTAMP_NAIVE,
        status=SessionStatus.IDLE,
        status_reason="idle",
    )
    assert session.is_active is False


def test_unified_session_age_seconds_uses_now(monkeypatch: pytest.MonkeyPatch) -> None:
    class FixedDateTime:
        @staticmethod
        def now() -> object:
            return FIXED_TIMESTAMP_NAIVE + timedelta(seconds=30)

    monkeypatch.setattr(protocols_models, "datetime", FixedDateTime)

    session = UnifiedSession(
        session_id="s1",
        source=Source.CLAUDE,
        file_path=Path("/tmp/session.jsonl"),
        project_path="/tmp/project",
        created_at=FIXED_TIMESTAMP_NAIVE,
        last_modified=FIXED_TIMESTAMP_NAIVE,
        status=SessionStatus.OPEN,
        status_reason="open",
    )
    assert session.age_seconds == 30.0


def test_unified_session_to_dict_includes_computed_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FixedDateTime:
        @staticmethod
        def now() -> object:
            return FIXED_TIMESTAMP_NAIVE + timedelta(seconds=5)

    monkeypatch.setattr(protocols_models, "datetime", FixedDateTime)

    session = UnifiedSession(
        session_id="s1",
        source=Source.CLAUDE,
        file_path=Path("/tmp/session.jsonl"),
        project_path="/tmp/project",
        created_at=FIXED_TIMESTAMP_NAIVE,
        last_modified=FIXED_TIMESTAMP_NAIVE,
        status=SessionStatus.ACTIVE,
        status_reason="ok",
    )
    payload = session.to_dict()
    assert payload["is_active"] is True
    assert payload["age_seconds"] == 5.0


def test_unified_session_default_lists_are_unique() -> None:
    session_a = UnifiedSession(
        session_id="s1",
        source=Source.CLAUDE,
        file_path=Path("/tmp/a.jsonl"),
        project_path="/tmp/project",
        created_at=FIXED_TIMESTAMP_NAIVE,
        last_modified=FIXED_TIMESTAMP_NAIVE,
        status=SessionStatus.ACTIVE,
        status_reason="ok",
    )
    session_b = UnifiedSession(
        session_id="s2",
        source=Source.CLAUDE,
        file_path=Path("/tmp/b.jsonl"),
        project_path="/tmp/project",
        created_at=FIXED_TIMESTAMP_NAIVE,
        last_modified=FIXED_TIMESTAMP_NAIVE,
        status=SessionStatus.ACTIVE,
        status_reason="ok",
    )
    session_a.files_read.append("a.py")
    assert session_b.files_read == []

