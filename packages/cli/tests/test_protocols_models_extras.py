from __future__ import annotations

from pathlib import Path

from motus.protocols_enums import Source
from motus.protocols_models import (
    DEFAULT_THRESHOLDS,
    RawSession,
    SessionHealth,
    StatusThresholds,
    TeleportBundle,
)
from tests.fixtures.constants import FIXED_TIMESTAMP, FIXED_TIMESTAMP_NAIVE


def test_session_health_to_dict() -> None:
    health = SessionHealth(
        session_id="s1",
        health_score=80,
        health_label="On Track",
        tool_calls=2,
        decisions=1,
        files_modified=3,
        risky_operations=1,
        thinking_blocks=4,
        duration_seconds=10,
        last_activity_seconds=5,
        current_goal="Ship",
        working_memory=["a.py"],
    )
    payload = health.to_dict()
    assert payload["health_score"] == 80
    assert payload["health_label"] == "On Track"
    assert payload["working_memory"] == ["a.py"]


def test_session_health_defaults() -> None:
    health = SessionHealth(session_id="s1", health_score=10, health_label="Stalled")
    assert health.tool_calls == 0
    assert health.working_memory == []


def test_teleport_bundle_to_markdown_includes_headers() -> None:
    bundle = TeleportBundle(
        source_session="abcd1234",
        source_model="gpt",
        timestamp=FIXED_TIMESTAMP,
        intent="Ship",
        decisions=[],
        files_touched=[],
        hot_files=[],
        pending_todos=[],
        last_action="",
    )
    text = bundle.to_markdown()
    assert "Context Teleported" in text
    assert "Original Task" in text


def test_teleport_bundle_to_markdown_includes_decisions() -> None:
    bundle = TeleportBundle(
        source_session="abcd1234",
        source_model="gpt",
        timestamp=FIXED_TIMESTAMP,
        intent="Ship",
        decisions=["Use cache"],
        files_touched=["a.py"],
        hot_files=["a.py"],
        pending_todos=["todo"],
        last_action="Edit a.py",
    )
    text = bundle.to_markdown()
    assert "Decisions Made" in text
    assert "Use cache" in text
    assert "Files Touched" in text


def test_teleport_bundle_to_markdown_includes_warnings() -> None:
    bundle = TeleportBundle(
        source_session="abcd1234",
        source_model="gpt",
        timestamp=FIXED_TIMESTAMP,
        intent="Ship",
        decisions=[],
        files_touched=[],
        hot_files=[],
        pending_todos=[],
        last_action="",
        warnings=["Be careful"],
    )
    text = bundle.to_markdown()
    assert "Be careful" in text


def test_teleport_bundle_to_markdown_truncates_planning_docs() -> None:
    long_doc = "A" * 600
    bundle = TeleportBundle(
        source_session="abcd1234",
        source_model="gpt",
        timestamp=FIXED_TIMESTAMP,
        intent="Ship",
        decisions=[],
        files_touched=[],
        hot_files=[],
        pending_todos=[],
        last_action="",
        planning_docs={"plan.md": long_doc},
    )
    text = bundle.to_markdown()
    assert "plan.md" in text
    assert "..." in text


def test_teleport_bundle_to_dict() -> None:
    bundle = TeleportBundle(
        source_session="abcd1234",
        source_model="gpt",
        timestamp=FIXED_TIMESTAMP,
        intent="Ship",
        decisions=["Decide"],
        files_touched=["a.py"],
        hot_files=["a.py"],
        pending_todos=["todo"],
        last_action="Edit a.py",
    )
    payload = bundle.to_dict()
    assert payload["source_session"] == "abcd1234"
    assert payload["intent"] == "Ship"


def test_raw_session_defaults() -> None:
    session = RawSession(
        session_id="s1",
        source=Source.CLAUDE,
        file_path=Path("/tmp/session.jsonl"),
        project_path="/tmp/project",
        last_modified=FIXED_TIMESTAMP_NAIVE,
    )
    assert session.size == 0
    assert session.created_at is None


def test_status_thresholds_defaults() -> None:
    thresholds = StatusThresholds()
    assert thresholds.active_seconds == 120
    assert thresholds.open_seconds == 1800
    assert thresholds.idle_seconds == 7200


def test_default_thresholds_instance() -> None:
    assert isinstance(DEFAULT_THRESHOLDS, StatusThresholds)
