from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from motus.coordination.audit import AuditLog, _generate_uuidv7
from motus.coordination.schemas import AUDIT_EVENT_SCHEMA, AuditEvent


def test_generate_uuidv7_format():
    """Test UUIDv7 generation produces expected format."""
    uuid = _generate_uuidv7()
    assert uuid.startswith("evt-")
    # Format: evt-{12 hex}-{20 hex}
    parts = uuid[4:].split("-")
    assert len(parts) == 2
    assert len(parts[0]) == 12  # Time-based prefix
    assert len(parts[1]) == 20  # Random suffix


def test_generate_uuidv7_ordering():
    """Test UUIDv7 maintains time ordering."""
    import time

    uuid1 = _generate_uuidv7()
    time.sleep(0.002)  # Sleep 2ms to ensure different timestamp
    uuid2 = _generate_uuidv7()
    # Later UUID should have lexicographically greater time prefix
    # Compare just the time prefix (first 12 hex chars after 'evt-')
    prefix1 = uuid1[4:16]
    prefix2 = uuid2[4:16]
    assert prefix2 >= prefix1


def test_audit_log_emit_basic():
    """Test basic event emission."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log = AuditLog(tmpdir)

        event_id = log.emit(
            event_type="TASK_CLAIMED",
            payload={"claim_id": "cl-001", "resources": ["foo.py"]},
            task_id="CR-test-1",
        )

        assert event_id.startswith("evt-")

        # Verify file was created
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        ledger_path = Path(tmpdir) / f"{today}.jsonl"
        assert ledger_path.exists()

        # Verify content
        with ledger_path.open("r") as f:
            lines = f.readlines()
        assert len(lines) == 1

        event_data = json.loads(lines[0])
        assert event_data["schema"] == AUDIT_EVENT_SCHEMA
        assert event_data["event_id"] == event_id
        assert event_data["event_type"] == "TASK_CLAIMED"
        assert event_data["task_id"] == "CR-test-1"
        assert event_data["payload"]["claim_id"] == "cl-001"


def test_audit_log_emit_multiple_events():
    """Test emitting multiple events appends to same file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log = AuditLog(tmpdir)

        event_id1 = log.emit(
            event_type="TASK_CLAIMED",
            payload={"claim_id": "cl-001"},
            task_id="CR-test-1",
        )
        event_id2 = log.emit(
            event_type="TASK_COMPLETED",
            payload={"claim_id": "cl-001", "duration_s": 120},
            task_id="CR-test-1",
            parent_event_id=event_id1,
        )

        # Verify both events in same file
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        ledger_path = Path(tmpdir) / f"{today}.jsonl"

        with ledger_path.open("r") as f:
            lines = f.readlines()
        assert len(lines) == 2

        event1_data = json.loads(lines[0])
        event2_data = json.loads(lines[1])

        assert event1_data["event_id"] == event_id1
        assert event2_data["event_id"] == event_id2
        assert event2_data["parent_event_id"] == event_id1


def test_audit_log_sequence_numbers():
    """Test sequence numbers are monotonically increasing per agent."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log = AuditLog(tmpdir)

        # Emit multiple events
        for i in range(5):
            log.emit(
                event_type="TEST_EVENT",
                payload={"index": i},
            )

        # Load events
        events = log.query()
        assert len(events) == 5

        # Verify sequence numbers are monotonic
        sequences = [e.sequence_number for e in events]
        assert sequences == [1, 2, 3, 4, 5]


def test_audit_log_query_by_event_type():
    """Test querying events by event type."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log = AuditLog(tmpdir)

        log.emit(event_type="TASK_CLAIMED", payload={"id": 1}, task_id="CR-1")
        log.emit(event_type="TASK_COMPLETED", payload={"id": 2}, task_id="CR-1")
        log.emit(event_type="TASK_CLAIMED", payload={"id": 3}, task_id="CR-2")

        # Query for TASK_CLAIMED events
        claimed_events = log.query(event_type="TASK_CLAIMED")
        assert len(claimed_events) == 2
        assert all(e.event_type == "TASK_CLAIMED" for e in claimed_events)

        # Query for TASK_COMPLETED events
        completed_events = log.query(event_type="TASK_COMPLETED")
        assert len(completed_events) == 1
        assert completed_events[0].event_type == "TASK_COMPLETED"


def test_audit_log_query_by_task_id():
    """Test querying events by task ID."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log = AuditLog(tmpdir)

        log.emit(event_type="TASK_CLAIMED", payload={}, task_id="CR-1")
        log.emit(event_type="TASK_COMPLETED", payload={}, task_id="CR-1")
        log.emit(event_type="TASK_CLAIMED", payload={}, task_id="CR-2")

        # Query for CR-1 events
        cr1_events = log.query(task_id="CR-1")
        assert len(cr1_events) == 2
        assert all(e.task_id == "CR-1" for e in cr1_events)

        # Query for CR-2 events
        cr2_events = log.query(task_id="CR-2")
        assert len(cr2_events) == 1
        assert cr2_events[0].task_id == "CR-2"


def test_audit_log_query_by_time_range():
    """Test querying events by time range."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log = AuditLog(tmpdir)

        now = datetime.now(timezone.utc)
        past = now - timedelta(hours=1)
        future = now + timedelta(hours=1)

        # Emit events
        log.emit(event_type="EVENT_1", payload={})
        log.emit(event_type="EVENT_2", payload={})

        # Query with time range
        events_since = log.query(since=past)
        assert len(events_since) == 2

        events_until = log.query(until=future)
        assert len(events_until) == 2

        # Query with narrow range (should exclude events)
        events_narrow = log.query(since=future)
        assert len(events_narrow) == 0


def test_audit_log_get_task_history():
    """Test getting task history in causal order."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log = AuditLog(tmpdir)

        # Create causal chain: claimed → started → completed
        e1 = log.emit(
            event_type="TASK_CLAIMED",
            payload={"claim_id": "cl-001"},
            task_id="CR-test-1",
        )
        e2 = log.emit(
            event_type="TASK_STARTED",
            payload={},
            task_id="CR-test-1",
            parent_event_id=e1,
        )
        e3 = log.emit(
            event_type="TASK_COMPLETED",
            payload={"duration_s": 120},
            task_id="CR-test-1",
            parent_event_id=e2,
        )

        # Get task history
        history = log.get_task_history("CR-test-1")
        assert len(history) == 3

        # Verify causal order
        assert history[0].event_id == e1
        assert history[1].event_id == e2
        assert history[2].event_id == e3


def test_audit_log_correlation_id():
    """Test correlation ID for cross-agent tracing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log = AuditLog(tmpdir)

        correlation_id = "corr-batch-001"

        log.emit(
            event_type="TASK_CLAIMED",
            payload={},
            task_id="CR-1",
            correlation_id=correlation_id,
        )
        log.emit(
            event_type="TASK_CLAIMED",
            payload={},
            task_id="CR-2",
            correlation_id=correlation_id,
        )

        # Verify correlation_id is stored
        events = log.query()
        assert len(events) == 2
        assert all(e.correlation_id == correlation_id for e in events)


def test_audit_log_empty_directory():
    """Test querying empty audit log."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log = AuditLog(tmpdir)

        events = log.query()
        assert events == []

        history = log.get_task_history("nonexistent")
        assert history == []


def test_audit_event_schema_serialization():
    """Test AuditEvent serialization/deserialization."""
    now = datetime.now(timezone.utc)

    event = AuditEvent(
        schema=AUDIT_EVENT_SCHEMA,
        event_id="evt-test-123",
        event_type="TASK_CLAIMED",
        timestamp=now,
        agent_id="agent-1",
        session_id="session-1",
        task_id="CR-test",
        correlation_id="corr-1",
        parent_event_id="evt-parent-456",
        sequence_number=42,
        payload={"key": "value"},
    )

    # Serialize
    json_data = event.to_json()
    assert json_data["schema"] == AUDIT_EVENT_SCHEMA
    assert json_data["event_id"] == "evt-test-123"
    assert json_data["event_type"] == "TASK_CLAIMED"
    assert json_data["agent_id"] == "agent-1"
    assert json_data["session_id"] == "session-1"
    assert json_data["task_id"] == "CR-test"
    assert json_data["correlation_id"] == "corr-1"
    assert json_data["parent_event_id"] == "evt-parent-456"
    assert json_data["sequence_number"] == 42
    assert json_data["payload"] == {"key": "value"}

    # Deserialize
    event2 = AuditEvent.from_json(json_data)
    assert event2.schema == event.schema
    assert event2.event_id == event.event_id
    assert event2.event_type == event.event_type
    assert event2.agent_id == event.agent_id
    assert event2.session_id == event.session_id
    assert event2.task_id == event.task_id
    assert event2.correlation_id == event.correlation_id
    assert event2.parent_event_id == event.parent_event_id
    assert event2.sequence_number == event.sequence_number
    assert event2.payload == event.payload


def test_audit_event_optional_fields():
    """Test AuditEvent with optional fields as None."""
    now = datetime.now(timezone.utc)

    event = AuditEvent(
        schema=AUDIT_EVENT_SCHEMA,
        event_id="evt-test-123",
        event_type="SYSTEM_EVENT",
        timestamp=now,
        agent_id="agent-1",
        session_id="session-1",
        task_id=None,
        correlation_id=None,
        parent_event_id=None,
        sequence_number=1,
        payload={},
    )

    # Serialize
    json_data = event.to_json()
    assert "task_id" not in json_data
    assert "correlation_id" not in json_data
    assert "parent_event_id" not in json_data

    # Deserialize
    event2 = AuditEvent.from_json(json_data)
    assert event2.task_id is None
    assert event2.correlation_id is None
    assert event2.parent_event_id is None
