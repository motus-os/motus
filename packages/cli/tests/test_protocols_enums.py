from __future__ import annotations

from motus.protocols_enums import (
    EventType,
    FileOperation,
    RiskLevel,
    SessionStatus,
    Source,
    ToolStatus,
)


def test_session_status_values() -> None:
    assert {status.value for status in SessionStatus} == {
        "active",
        "open",
        "idle",
        "orphaned",
        "crashed",
    }


def test_event_type_values() -> None:
    assert {event.value for event in EventType} == {
        "thinking",
        "tool",
        "tool_result",
        "decision",
        "file_change",
        "file_read",
        "file_modified",
        "agent_spawn",
        "error",
        "session_start",
        "session_end",
        "user_message",
        "response",
    }


def test_risk_level_values() -> None:
    assert {level.value for level in RiskLevel} == {
        "safe",
        "medium",
        "high",
        "critical",
    }


def test_tool_status_values() -> None:
    assert {status.value for status in ToolStatus} == {
        "success",
        "error",
        "pending",
        "cancelled",
    }


def test_file_operation_values() -> None:
    assert {op.value for op in FileOperation} == {"read", "write", "edit", "delete"}


def test_source_values() -> None:
    assert {source.value for source in Source} == {"claude", "codex", "gemini", "sdk"}


def test_enum_members_are_strings() -> None:
    assert all(isinstance(member, str) for member in EventType)


def test_enum_compares_to_value() -> None:
    assert EventType.TOOL == "tool"
    assert Source.CLAUDE == "claude"
