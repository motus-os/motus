from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from motus.protocols import (
    EventType,
    RiskLevel,
    SessionStatus,
    Source,
    UnifiedEvent,
    UnifiedSession,
)
from motus.protocols_utils import compute_health, compute_status


def test_compute_status_detects_crash_window_for_risky_action_without_completion() -> None:
    now = datetime.now()
    last_modified = now - timedelta(seconds=120)  # between crash_min=60 and crash_max=300
    status, reason = compute_status(
        last_modified=last_modified,
        now=now,
        last_action="Edit src/foo.py",
        has_completion=False,
    )
    assert status == SessionStatus.CRASHED
    assert "Stopped during" in reason


@pytest.mark.parametrize(
    "age_seconds,expected",
    [
        (60, SessionStatus.ACTIVE),
        (301, SessionStatus.OPEN),
        (4000, SessionStatus.IDLE),
        (10_000, SessionStatus.ORPHANED),
    ],
)
def test_compute_status_standard_age_buckets(age_seconds: int, expected: SessionStatus) -> None:
    now = datetime.now()
    last_modified = now - timedelta(seconds=age_seconds)
    status, _reason = compute_status(last_modified=last_modified, now=now)
    assert status == expected


def test_compute_health_score_label_and_working_memory() -> None:
    now = datetime.now()
    session = UnifiedSession(
        session_id="s1",
        source=Source.CLAUDE,
        file_path=Path("/tmp/s1.jsonl"),
        project_path="/tmp/project",
        created_at=now - timedelta(hours=1),
        last_modified=now - timedelta(seconds=1000),
        status=SessionStatus.ORPHANED,
        status_reason="stale",
        files_modified=["a.py", "b.py", "c.py", "d.py", "e.py", "f.py"],
        working_on="Ship tests",
    )

    events = [
        UnifiedEvent(
            event_id="e1",
            session_id="s1",
            timestamp=now,
            event_type=EventType.TOOL,
            content="Bash: rm -rf /",
            risk_level=RiskLevel.CRITICAL,
        ),
        UnifiedEvent(
            event_id="e2",
            session_id="s1",
            timestamp=now,
            event_type=EventType.DECISION,
            content="Decision",
            decision_text="Keep it minimal",
        ),
        UnifiedEvent(
            event_id="e3",
            session_id="s1",
            timestamp=now,
            event_type=EventType.THINKING,
            content="Thinking",
        ),
    ]

    health = compute_health(session, events)

    assert health.session_id == session.session_id
    assert health.tool_calls == 1
    assert health.decisions == 1
    assert health.risky_operations == 1
    assert health.health_label in {"On Track", "Needs Attention", "At Risk", "Stalled"}

    # Working memory should include the last 5 modified files and recent decisions.
    assert "b.py" in health.working_memory
    assert "f.py" in health.working_memory
    assert "Keep it minimal" in health.working_memory


def test_ui_lazy_exports_and_unknown_attribute() -> None:
    import motus.ui as ui

    assert callable(ui.run_web)
    assert ui.MCWebServer is not None

    with pytest.raises(AttributeError):
        getattr(ui, "nope")
