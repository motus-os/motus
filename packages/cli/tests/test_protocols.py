from __future__ import annotations

from pathlib import Path

from motus import protocols
from motus.protocols_enums import EventType, SessionStatus, Source
from motus.protocols_models import StatusThresholds, UnifiedEvent, UnifiedSession
from tests.fixtures.constants import FIXED_TIMESTAMP, FIXED_TIMESTAMP_NAIVE


def test_protocols_all_contains_expected_names() -> None:
    expected = {
        "UnifiedSession",
        "UnifiedEvent",
        "SessionBuilder",
        "SessionHealth",
        "SessionStatus",
        "EventType",
        "Source",
        "compute_health",
        "compute_status",
    }
    assert expected.issubset(set(protocols.__all__))


def test_protocols_exports_builder() -> None:
    from motus.protocols_builder import SessionBuilder

    assert protocols.SessionBuilder is SessionBuilder


def test_protocols_exports_enums() -> None:
    assert protocols.EventType is EventType
    assert protocols.SessionStatus is SessionStatus
    assert protocols.Source is Source


def test_protocols_exports_models() -> None:
    assert protocols.UnifiedEvent is UnifiedEvent
    assert protocols.UnifiedSession is UnifiedSession


def test_protocols_exports_utils() -> None:
    assert callable(protocols.compute_health)
    assert callable(protocols.compute_status)


def test_protocols_default_thresholds_type() -> None:
    assert isinstance(protocols.DEFAULT_THRESHOLDS, StatusThresholds)


def test_protocols_unified_event_roundtrip() -> None:
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


def test_protocols_unified_session_roundtrip() -> None:
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
    payload = session.to_dict()
    assert payload["session_id"] == "s1"
    assert payload["status"] == "active"
    assert isinstance(payload["age_seconds"], float)
