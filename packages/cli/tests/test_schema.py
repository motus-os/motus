"""Comprehensive tests for schema module.

This module tests all Pydantic models and enums in the schema package,
including immutability, strict validation, serialization, and enum values.
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from motus.schema import (
    AgentSource,
    EventType,
    ParsedEvent,
    RiskLevel,
    SessionInfo,
)
from motus.schema.events import unified_to_parsed

# Fixed test values for deterministic tests
FIXED_TIMESTAMP = datetime(2025, 1, 15, 12, 0, 0)
FIXED_EVENT_ID = "test-event-001"


class TestEnums:
    """Test all enum values are defined correctly."""

    def test_event_type_values(self):
        """EventType enum has all expected values."""
        assert EventType.TOOL_USE.value == "tool_use"
        assert EventType.TOOL_RESULT.value == "tool_result"
        assert EventType.THINKING.value == "thinking"
        assert EventType.DECISION.value == "decision"
        assert EventType.AGENT_SPAWN.value == "agent_spawn"
        assert EventType.AGENT_RESULT.value == "agent_result"
        assert EventType.SESSION_START.value == "session_start"
        assert EventType.SESSION_END.value == "session_end"
        assert EventType.USER_MESSAGE.value == "user_message"
        assert EventType.ASSISTANT_MESSAGE.value == "assistant_message"
        assert EventType.ERROR.value == "error"

    def test_event_type_count(self):
        """EventType has exactly 11 values."""
        assert len(EventType) == 11

    def test_agent_source_values(self):
        """AgentSource enum has all expected values."""
        assert AgentSource.CLAUDE.value == "claude"
        assert AgentSource.CODEX.value == "codex"
        assert AgentSource.GEMINI.value == "gemini"
        assert AgentSource.UNKNOWN.value == "unknown"

    def test_agent_source_count(self):
        """AgentSource has exactly 4 values."""
        assert len(AgentSource) == 4

    def test_risk_level_values(self):
        """RiskLevel enum has all expected values."""
        assert RiskLevel.SAFE.value == "safe"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.CRITICAL.value == "critical"

    def test_risk_level_count(self):
        """RiskLevel has exactly 4 values (SAFE, MEDIUM, HIGH, CRITICAL)."""
        assert len(RiskLevel) == 4

    def test_enums_are_string_enums(self):
        """All enums inherit from str."""
        assert isinstance(EventType.TOOL_USE, str)
        assert isinstance(AgentSource.CLAUDE, str)
        assert isinstance(RiskLevel.SAFE, str)


class TestParsedEventCreation:
    """Test ParsedEvent creation with various field combinations."""

    def test_creation_with_required_fields_only(self):
        """ParsedEvent can be created with only required fields."""
        event = ParsedEvent(
            event_id=FIXED_EVENT_ID,
            session_id="test-session-123",
            event_type=EventType.TOOL_USE,
            source=AgentSource.CLAUDE,
            timestamp=FIXED_TIMESTAMP,
        )
        assert event.event_id == FIXED_EVENT_ID
        assert event.session_id == "test-session-123"
        assert event.event_type == EventType.TOOL_USE
        assert event.source == AgentSource.CLAUDE
        assert event.timestamp == FIXED_TIMESTAMP
        # Check defaults
        assert event.risk_level == RiskLevel.SAFE
        assert event.content == ""
        assert event.is_error is False
        assert event.model is None
        assert event.tool_use_id is None

    def test_creation_with_all_fields(self):
        """ParsedEvent can be created with all fields populated."""
        timestamp = datetime(2025, 1, 15, 12, 0, 0)
        raw_data = {"original": "data"}

        event = ParsedEvent(
            event_id="custom-event-id",
            session_id="session-456",
            event_type=EventType.TOOL_USE,
            source=AgentSource.CLAUDE,
            timestamp=timestamp,
            model="claude-sonnet-4-5",
            risk_level=RiskLevel.HIGH,
            content="Reading file /test.py",
            tool_name="Read",
            tool_input='{"file_path": "/test.py"}',
            tool_output="File contents here",
            tool_use_id="toolu_01ABC123",
            file_path="/test.py",
            spawn_type="task",
            spawn_prompt="Analyze this code",
            spawn_model="claude-sonnet-4",
            is_error=False,
            error_message=None,
            raw_data=raw_data,
        )

        assert event.event_id == "custom-event-id"
        assert event.session_id == "session-456"
        assert event.event_type == EventType.TOOL_USE
        assert event.source == AgentSource.CLAUDE
        assert event.timestamp == timestamp
        assert event.model == "claude-sonnet-4-5"
        assert event.risk_level == RiskLevel.HIGH
        assert event.content == "Reading file /test.py"
        assert event.tool_name == "Read"
        assert event.tool_input == '{"file_path": "/test.py"}'
        assert event.tool_output == "File contents here"
        assert event.tool_use_id == "toolu_01ABC123"
        assert event.file_path == "/test.py"
        assert event.spawn_type == "task"
        assert event.spawn_prompt == "Analyze this code"
        assert event.spawn_model == "claude-sonnet-4"
        assert event.is_error is False
        assert event.error_message is None
        assert event.raw_data == raw_data

    def test_event_id_is_required(self):
        """ParsedEvent requires event_id to be provided."""
        with pytest.raises(ValidationError) as exc_info:
            ParsedEvent(
                # event_id is missing (required field)
                session_id="session-1",
                event_type=EventType.THINKING,
                source=AgentSource.CLAUDE,
                timestamp=FIXED_TIMESTAMP,
            )
        # Verify the error mentions event_id is required
        assert "event_id" in str(exc_info.value).lower()

    def test_timestamp_is_required(self):
        """ParsedEvent requires timestamp to be provided."""
        with pytest.raises(ValidationError) as exc_info:
            ParsedEvent(
                event_id=FIXED_EVENT_ID,
                session_id="session-1",
                event_type=EventType.THINKING,
                source=AgentSource.CLAUDE,
                # timestamp is missing (required field)
            )
        # Verify the error mentions timestamp is required
        assert "timestamp" in str(exc_info.value).lower()

    def test_default_values(self):
        """ParsedEvent sets correct default values."""
        event = ParsedEvent(
            event_id=FIXED_EVENT_ID,
            session_id="session-1",
            event_type=EventType.THINKING,
            source=AgentSource.CLAUDE,
            timestamp=FIXED_TIMESTAMP,
        )

        # Test all default values
        assert event.risk_level == RiskLevel.SAFE
        assert event.content == ""
        assert event.model is None
        assert event.tool_name is None
        assert event.tool_input is None
        assert event.tool_output is None
        assert event.tool_use_id is None
        assert event.file_path is None
        assert event.spawn_type is None
        assert event.spawn_prompt is None
        assert event.spawn_model is None
        assert event.is_error is False
        assert event.error_message is None
        assert event.raw_data is None


class TestParsedEventImmutability:
    """Test ParsedEvent immutability (frozen=True)."""

    def test_cannot_modify_event_id(self):
        """Cannot modify event_id after creation."""
        event = ParsedEvent(
            event_id="original-id",
            session_id="session-1",
            event_type=EventType.THINKING,
            source=AgentSource.CLAUDE,
            timestamp=FIXED_TIMESTAMP,
        )

        with pytest.raises(ValidationError):
            event.event_id = "new-id"

    def test_cannot_modify_session_id(self):
        """Cannot modify session_id after creation."""
        event = ParsedEvent(
            event_id=FIXED_EVENT_ID,
            session_id="original-session",
            event_type=EventType.THINKING,
            source=AgentSource.CLAUDE,
            timestamp=FIXED_TIMESTAMP,
        )

        with pytest.raises(ValidationError):
            event.session_id = "new-session"

    def test_cannot_modify_content(self):
        """Cannot modify content after creation."""
        event = ParsedEvent(
            event_id=FIXED_EVENT_ID,
            session_id="session-1",
            event_type=EventType.THINKING,
            source=AgentSource.CLAUDE,
            timestamp=FIXED_TIMESTAMP,
            content="Original content",
        )

        with pytest.raises(ValidationError):
            event.content = "Modified content"

    def test_cannot_modify_tool_name(self):
        """Cannot modify tool_name after creation."""
        event = ParsedEvent(
            event_id=FIXED_EVENT_ID,
            session_id="session-1",
            event_type=EventType.TOOL_USE,
            source=AgentSource.CLAUDE,
            timestamp=FIXED_TIMESTAMP,
            tool_name="Read",
        )

        with pytest.raises(ValidationError):
            event.tool_name = "Write"

    def test_cannot_modify_risk_level(self):
        """Cannot modify risk_level after creation."""
        event = ParsedEvent(
            event_id=FIXED_EVENT_ID,
            session_id="session-1",
            event_type=EventType.TOOL_USE,
            source=AgentSource.CLAUDE,
            timestamp=FIXED_TIMESTAMP,
            risk_level=RiskLevel.SAFE,
        )

        with pytest.raises(ValidationError):
            event.risk_level = RiskLevel.HIGH


class TestParsedEventStrictMode:
    """Test ParsedEvent strict validation (strict=True)."""

    def test_session_id_must_be_string(self):
        """session_id must be a string, not coerced."""
        with pytest.raises(ValidationError):
            ParsedEvent(
                event_id=FIXED_EVENT_ID,
                session_id=123,  # Integer instead of string
                event_type=EventType.THINKING,
                source=AgentSource.CLAUDE,
                timestamp=FIXED_TIMESTAMP,
            )

    def test_event_type_must_be_enum(self):
        """event_type must be EventType enum, not string."""
        with pytest.raises(ValidationError):
            ParsedEvent(
                event_id=FIXED_EVENT_ID,
                session_id="session-1",
                event_type="tool_use",  # String instead of enum
                source=AgentSource.CLAUDE,
                timestamp=FIXED_TIMESTAMP,
            )

    def test_source_must_be_enum(self):
        """source must be AgentSource enum, not string."""
        with pytest.raises(ValidationError):
            ParsedEvent(
                event_id=FIXED_EVENT_ID,
                session_id="session-1",
                event_type=EventType.THINKING,
                source="claude",  # String instead of enum
                timestamp=FIXED_TIMESTAMP,
            )

    def test_risk_level_must_be_enum(self):
        """risk_level must be RiskLevel enum, not string."""
        with pytest.raises(ValidationError):
            ParsedEvent(
                event_id=FIXED_EVENT_ID,
                session_id="session-1",
                event_type=EventType.THINKING,
                source=AgentSource.CLAUDE,
                timestamp=FIXED_TIMESTAMP,
                risk_level="safe",  # String instead of enum
            )

    def test_timestamp_must_be_datetime(self):
        """timestamp must be datetime, not string."""
        with pytest.raises(ValidationError):
            ParsedEvent(
                event_id=FIXED_EVENT_ID,
                session_id="session-1",
                event_type=EventType.THINKING,
                source=AgentSource.CLAUDE,
                timestamp="2025-01-15T12:00:00",  # String instead of datetime
            )

    def test_is_error_must_be_bool(self):
        """is_error must be boolean, not string or int."""
        with pytest.raises(ValidationError):
            ParsedEvent(
                event_id=FIXED_EVENT_ID,
                session_id="session-1",
                event_type=EventType.ERROR,
                source=AgentSource.CLAUDE,
                timestamp=FIXED_TIMESTAMP,
                is_error="true",  # String instead of bool
            )

        with pytest.raises(ValidationError):
            ParsedEvent(
                event_id=FIXED_EVENT_ID,
                session_id="session-1",
                event_type=EventType.ERROR,
                source=AgentSource.CLAUDE,
                timestamp=FIXED_TIMESTAMP,
                is_error=1,  # Int instead of bool
            )


class TestParsedEventExtraFields:
    """Test ParsedEvent forbids extra fields (extra='forbid')."""

    def test_extra_fields_forbidden(self):
        """Cannot add extra fields not in schema."""
        with pytest.raises(ValidationError) as exc_info:
            ParsedEvent(
                event_id=FIXED_EVENT_ID,
                session_id="session-1",
                event_type=EventType.THINKING,
                source=AgentSource.CLAUDE,
                timestamp=FIXED_TIMESTAMP,
                unexpected_field="should fail",
            )

        # Verify the error mentions the extra field
        assert "unexpected_field" in str(exc_info.value).lower()

    def test_multiple_extra_fields_forbidden(self):
        """Cannot add multiple extra fields."""
        with pytest.raises(ValidationError) as exc_info:
            ParsedEvent(
                event_id=FIXED_EVENT_ID,
                session_id="session-1",
                event_type=EventType.THINKING,
                source=AgentSource.CLAUDE,
                timestamp=FIXED_TIMESTAMP,
                extra1="field1",
                extra2="field2",
            )

        error_str = str(exc_info.value).lower()
        assert "extra" in error_str or "unexpected" in error_str


class TestParsedEventSerialization:
    """Test ParsedEvent.to_dict() serialization."""

    def test_to_dict_basic(self):
        """to_dict() returns dictionary with all fields."""
        timestamp = datetime(2025, 1, 15, 12, 0, 0)
        event = ParsedEvent(
            event_id="test-event-123",
            session_id="session-456",
            event_type=EventType.TOOL_USE,
            source=AgentSource.CLAUDE,
            timestamp=timestamp,
            risk_level=RiskLevel.HIGH,
            content="Test content",
        )

        result = event.to_dict()

        assert isinstance(result, dict)
        assert result["event_id"] == "test-event-123"
        assert result["session_id"] == "session-456"
        assert result["event_type"] == "tool_use"  # Enum value
        assert result["source"] == "claude"  # Enum value
        assert result["timestamp"] == "2025-01-15T12:00:00"  # ISO format
        assert result["risk_level"] == "high"  # Enum value
        assert result["content"] == "Test content"

    def test_to_dict_converts_timestamp_to_iso(self):
        """to_dict() converts datetime to ISO format string."""
        timestamp = datetime(2025, 1, 15, 12, 30, 45)
        event = ParsedEvent(
            event_id=FIXED_EVENT_ID,
            session_id="session-1",
            event_type=EventType.THINKING,
            source=AgentSource.CLAUDE,
            timestamp=timestamp,
        )

        result = event.to_dict()

        assert result["timestamp"] == "2025-01-15T12:30:45"
        assert isinstance(result["timestamp"], str)

    def test_to_dict_converts_enums_to_values(self):
        """to_dict() converts all enums to their string values."""
        event = ParsedEvent(
            event_id=FIXED_EVENT_ID,
            session_id="session-1",
            event_type=EventType.AGENT_SPAWN,
            source=AgentSource.GEMINI,
            timestamp=FIXED_TIMESTAMP,
            risk_level=RiskLevel.MEDIUM,
        )

        result = event.to_dict()

        # All should be strings, not enum objects
        assert result["event_type"] == "agent_spawn"
        assert result["source"] == "gemini"
        assert result["risk_level"] == "medium"
        assert isinstance(result["event_type"], str)
        assert isinstance(result["source"], str)
        assert isinstance(result["risk_level"], str)

    def test_to_dict_includes_none_values(self):
        """to_dict() includes None values for optional fields."""
        event = ParsedEvent(
            event_id=FIXED_EVENT_ID,
            session_id="session-1",
            event_type=EventType.THINKING,
            source=AgentSource.CLAUDE,
            timestamp=FIXED_TIMESTAMP,
        )

        result = event.to_dict()

        # Optional fields should be present with None values
        assert "model" in result
        assert result["model"] is None
        assert "tool_name" in result
        assert result["tool_name"] is None
        assert "tool_input" in result
        assert result["tool_input"] is None
        assert "tool_use_id" in result
        assert result["tool_use_id"] is None
        assert "error_message" in result
        assert result["error_message"] is None

    def test_to_dict_with_all_fields(self):
        """to_dict() handles all fields being populated."""
        timestamp = datetime(2025, 1, 15, 12, 0, 0)
        raw_data = {"key": "value", "nested": {"a": 1}}

        event = ParsedEvent(
            event_id="full-event",
            session_id="session-full",
            event_type=EventType.TOOL_USE,
            source=AgentSource.CODEX,
            timestamp=timestamp,
            model="codex-2.0",
            risk_level=RiskLevel.HIGH,
            content="Full event",
            tool_name="Bash",
            tool_input='{"command": "ls"}',
            tool_output="file1.py\nfile2.py",
            tool_use_id="toolu_01XYZ789",
            file_path="/test/script.sh",
            spawn_type="agent",
            spawn_prompt="Run tests",
            spawn_model="codex-latest",
            is_error=True,
            error_message="Command failed",
            raw_data=raw_data,
        )

        result = event.to_dict()

        # Verify all fields are present
        assert result["event_id"] == "full-event"
        assert result["session_id"] == "session-full"
        assert result["event_type"] == "tool_use"
        assert result["source"] == "codex"
        assert result["timestamp"] == "2025-01-15T12:00:00"
        assert result["model"] == "codex-2.0"
        assert result["risk_level"] == "high"
        assert result["content"] == "Full event"
        assert result["tool_name"] == "Bash"
        assert result["tool_input"] == '{"command": "ls"}'
        assert result["tool_output"] == "file1.py\nfile2.py"
        assert result["tool_use_id"] == "toolu_01XYZ789"
        assert result["file_path"] == "/test/script.sh"
        assert result["spawn_type"] == "agent"
        assert result["spawn_prompt"] == "Run tests"
        assert result["spawn_model"] == "codex-latest"
        assert result["is_error"] is True
        assert result["error_message"] == "Command failed"
        assert result["raw_data"] == raw_data


class TestParsedEventShortId:
    """Test ParsedEvent.short_id() method."""

    def test_short_id_truncates_long_id(self):
        """short_id() returns first 8 characters of long event_id."""
        event = ParsedEvent(
            event_id="abcdefgh-1234-5678-9012-345678901234",
            session_id="session-1",
            event_type=EventType.THINKING,
            source=AgentSource.CLAUDE,
            timestamp=FIXED_TIMESTAMP,
        )

        assert event.short_id() == "abcdefgh"

    def test_short_id_returns_full_short_id(self):
        """short_id() returns full id if already 8 chars or less."""
        event = ParsedEvent(
            event_id="abc123",
            session_id="session-1",
            event_type=EventType.THINKING,
            source=AgentSource.CLAUDE,
            timestamp=FIXED_TIMESTAMP,
        )

        assert event.short_id() == "abc123"

    def test_short_id_with_exactly_8_chars(self):
        """short_id() returns full id when exactly 8 characters."""
        event = ParsedEvent(
            event_id="12345678",
            session_id="session-1",
            event_type=EventType.THINKING,
            source=AgentSource.CLAUDE,
            timestamp=FIXED_TIMESTAMP,
        )

        assert event.short_id() == "12345678"


class TestSessionInfoCreation:
    """Test SessionInfo creation with various field combinations."""

    def test_creation_with_required_fields_only(self):
        """SessionInfo can be created with only required fields."""
        info = SessionInfo(
            session_id="session-123",
            source=AgentSource.CLAUDE,
        )

        assert info.session_id == "session-123"
        assert info.source == AgentSource.CLAUDE
        # Check defaults
        assert info.project_path == ""
        assert info.event_count == 0
        assert info.is_active is False
        assert info.size_bytes == 0

    def test_creation_with_all_fields(self):
        """SessionInfo can be created with all fields populated."""
        start_time = datetime(2025, 1, 15, 10, 0, 0)
        end_time = datetime(2025, 1, 15, 12, 0, 0)
        last_event = datetime(2025, 1, 15, 11, 59, 0)

        info = SessionInfo(
            session_id="session-456",
            source=AgentSource.GEMINI,
            project_path="/Users/test/project",
            start_time=start_time,
            end_time=end_time,
            last_event_time=last_event,
            event_count=42,
            is_active=True,
            model="gemini-2.5-pro",
            size_bytes=1024000,
        )

        assert info.session_id == "session-456"
        assert info.source == AgentSource.GEMINI
        assert info.project_path == "/Users/test/project"
        assert info.start_time == start_time
        assert info.end_time == end_time
        assert info.last_event_time == last_event
        assert info.event_count == 42
        assert info.is_active is True
        assert info.model == "gemini-2.5-pro"
        assert info.size_bytes == 1024000

    def test_default_values(self):
        """SessionInfo sets correct default values."""
        info = SessionInfo(
            session_id="session-1",
            source=AgentSource.CLAUDE,
        )

        assert info.project_path == ""
        assert info.start_time is None
        assert info.end_time is None
        assert info.last_event_time is None
        assert info.event_count == 0
        assert info.is_active is False
        assert info.model is None
        assert info.size_bytes == 0


class TestSessionInfoImmutability:
    """Test SessionInfo immutability (frozen=True)."""

    def test_cannot_modify_session_id(self):
        """Cannot modify session_id after creation."""
        info = SessionInfo(
            session_id="original-session",
            source=AgentSource.CLAUDE,
        )

        with pytest.raises(ValidationError):
            info.session_id = "new-session"

    def test_cannot_modify_source(self):
        """Cannot modify source after creation."""
        info = SessionInfo(
            session_id="session-1",
            source=AgentSource.CLAUDE,
        )

        with pytest.raises(ValidationError):
            info.source = AgentSource.GEMINI

    def test_cannot_modify_event_count(self):
        """Cannot modify event_count after creation."""
        info = SessionInfo(
            session_id="session-1",
            source=AgentSource.CLAUDE,
            event_count=10,
        )

        with pytest.raises(ValidationError):
            info.event_count = 20

    def test_cannot_modify_is_active(self):
        """Cannot modify is_active after creation."""
        info = SessionInfo(
            session_id="session-1",
            source=AgentSource.CLAUDE,
            is_active=True,
        )

        with pytest.raises(ValidationError):
            info.is_active = False


class TestSessionInfoStrictMode:
    """Test SessionInfo strict validation (strict=True)."""

    def test_session_id_must_be_string(self):
        """session_id must be a string, not coerced."""
        with pytest.raises(ValidationError):
            SessionInfo(
                session_id=12345,  # Integer instead of string
                source=AgentSource.CLAUDE,
            )

    def test_source_must_be_enum(self):
        """source must be AgentSource enum, not string."""
        with pytest.raises(ValidationError):
            SessionInfo(
                session_id="session-1",
                source="claude",  # String instead of enum
            )

    def test_event_count_must_be_int(self):
        """event_count must be int, not string."""
        with pytest.raises(ValidationError):
            SessionInfo(
                session_id="session-1",
                source=AgentSource.CLAUDE,
                event_count="10",  # String instead of int
            )

    def test_is_active_must_be_bool(self):
        """is_active must be boolean, not string or int."""
        with pytest.raises(ValidationError):
            SessionInfo(
                session_id="session-1",
                source=AgentSource.CLAUDE,
                is_active="true",  # String instead of bool
            )

    def test_size_bytes_must_be_int(self):
        """size_bytes must be int, not string."""
        with pytest.raises(ValidationError):
            SessionInfo(
                session_id="session-1",
                source=AgentSource.CLAUDE,
                size_bytes="1024",  # String instead of int
            )


class TestSessionInfoValidation:
    """Test SessionInfo field validation."""

    def test_event_count_must_be_non_negative(self):
        """event_count must be >= 0."""
        with pytest.raises(ValidationError):
            SessionInfo(
                session_id="session-1",
                source=AgentSource.CLAUDE,
                event_count=-1,
            )

    def test_event_count_zero_is_valid(self):
        """event_count can be 0."""
        info = SessionInfo(
            session_id="session-1",
            source=AgentSource.CLAUDE,
            event_count=0,
        )
        assert info.event_count == 0

    def test_size_bytes_must_be_non_negative(self):
        """size_bytes must be >= 0."""
        with pytest.raises(ValidationError):
            SessionInfo(
                session_id="session-1",
                source=AgentSource.CLAUDE,
                size_bytes=-100,
            )

    def test_size_bytes_zero_is_valid(self):
        """size_bytes can be 0."""
        info = SessionInfo(
            session_id="session-1",
            source=AgentSource.CLAUDE,
            size_bytes=0,
        )
        assert info.size_bytes == 0


class TestSessionInfoExtraFields:
    """Test SessionInfo forbids extra fields (extra='forbid')."""

    def test_extra_fields_forbidden(self):
        """Cannot add extra fields not in schema."""
        with pytest.raises(ValidationError) as exc_info:
            SessionInfo(
                session_id="session-1",
                source=AgentSource.CLAUDE,
                unexpected_field="should fail",
            )

        assert "unexpected_field" in str(exc_info.value).lower()


class TestSessionInfoSerialization:
    """Test SessionInfo.to_dict() serialization."""

    def test_to_dict_basic(self):
        """to_dict() returns dictionary with all fields."""
        info = SessionInfo(
            session_id="session-123",
            source=AgentSource.CLAUDE,
            project_path="/Users/test/project",
            event_count=25,
            is_active=True,
        )

        result = info.to_dict()

        assert isinstance(result, dict)
        assert result["session_id"] == "session-123"
        assert result["source"] == "claude"  # Enum value
        assert result["project_path"] == "/Users/test/project"
        assert result["event_count"] == 25
        assert result["is_active"] is True

    def test_to_dict_converts_datetimes_to_iso(self):
        """to_dict() converts datetime fields to ISO format strings."""
        start_time = datetime(2025, 1, 15, 10, 0, 0)
        end_time = datetime(2025, 1, 15, 12, 0, 0)
        last_event = datetime(2025, 1, 15, 11, 59, 0)

        info = SessionInfo(
            session_id="session-1",
            source=AgentSource.CLAUDE,
            start_time=start_time,
            end_time=end_time,
            last_event_time=last_event,
        )

        result = info.to_dict()

        assert result["start_time"] == "2025-01-15T10:00:00"
        assert result["end_time"] == "2025-01-15T12:00:00"
        assert result["last_event_time"] == "2025-01-15T11:59:00"
        assert isinstance(result["start_time"], str)
        assert isinstance(result["end_time"], str)
        assert isinstance(result["last_event_time"], str)

    def test_to_dict_handles_none_datetimes(self):
        """to_dict() handles None values for optional datetime fields."""
        info = SessionInfo(
            session_id="session-1",
            source=AgentSource.CLAUDE,
        )

        result = info.to_dict()

        # None datetimes should remain None in output
        assert result["start_time"] is None
        assert result["end_time"] is None
        assert result["last_event_time"] is None

    def test_to_dict_converts_source_enum(self):
        """to_dict() converts source enum to string value."""
        info = SessionInfo(
            session_id="session-1",
            source=AgentSource.GEMINI,
        )

        result = info.to_dict()

        assert result["source"] == "gemini"
        assert isinstance(result["source"], str)


class TestSessionInfoShortId:
    """Test SessionInfo.short_id() method."""

    def test_short_id_truncates_long_id(self):
        """short_id() returns first 8 characters of long session_id."""
        info = SessionInfo(
            session_id="abcdefgh-1234-5678-9012-345678901234",
            source=AgentSource.CLAUDE,
        )

        assert info.short_id() == "abcdefgh"

    def test_short_id_returns_full_short_id(self):
        """short_id() returns full id if already 8 chars or less."""
        info = SessionInfo(
            session_id="abc123",
            source=AgentSource.CLAUDE,
        )

        assert info.short_id() == "abc123"

    def test_short_id_with_exactly_8_chars(self):
        """short_id() returns full id when exactly 8 characters."""
        info = SessionInfo(
            session_id="12345678",
            source=AgentSource.CLAUDE,
        )

        assert info.short_id() == "12345678"


class TestSchemaIntegration:
    """Integration tests for schema module."""

    def test_import_all_exports(self):
        """All exported classes can be imported from schema package."""
        from enum import Enum

        from motus.schema import (
            AgentSource,
            EventType,
            ParsedEvent,
            RiskLevel,
            SessionInfo,
        )

        # Verify enums are Enum subclasses
        assert issubclass(EventType, Enum)
        assert issubclass(AgentSource, Enum)
        assert issubclass(RiskLevel, Enum)
        # Verify they're Pydantic models
        assert hasattr(ParsedEvent, "model_validate")
        assert hasattr(SessionInfo, "model_validate")

    def test_parsed_event_roundtrip_serialization(self):
        """ParsedEvent can be serialized and deserialized."""
        original = ParsedEvent(
            event_id="test-123",
            session_id="session-456",
            event_type=EventType.TOOL_USE,
            source=AgentSource.CLAUDE,
            timestamp=datetime(2025, 1, 15, 12, 0, 0),
            content="Test event",
        )

        # Serialize to dict - verify it works (enums become strings)
        _ = original.to_dict()

        # Can't directly deserialize from to_dict() because it converts enums to strings
        # But we can use model_dump() for roundtrip
        data_for_roundtrip = original.model_dump()
        restored = ParsedEvent(**data_for_roundtrip)

        assert restored.event_id == original.event_id
        assert restored.session_id == original.session_id
        assert restored.event_type == original.event_type
        assert restored.source == original.source
        assert restored.content == original.content

    def test_session_info_roundtrip_serialization(self):
        """SessionInfo can be serialized and deserialized."""
        original = SessionInfo(
            session_id="session-789",
            source=AgentSource.GEMINI,
            project_path="/test/path",
            event_count=15,
        )

        # Serialize and restore
        data = original.model_dump()
        restored = SessionInfo(**data)

        assert restored.session_id == original.session_id
        assert restored.source == original.source
        assert restored.project_path == original.project_path
        assert restored.event_count == original.event_count


class TestUnifiedToParsedConversion:
    """Test unified_to_parsed conversion function.

    This is the validation layer that converts UnifiedEvent (dataclass)
    to ParsedEvent (Pydantic) with schema validation.
    """

    def test_conversion_basic_event(self):
        """unified_to_parsed converts a basic UnifiedEvent correctly."""
        from motus.protocols import EventType as PEventType
        from motus.protocols import UnifiedEvent

        event = UnifiedEvent(
            event_id="test-123",
            session_id="session-456",
            timestamp=FIXED_TIMESTAMP,
            event_type=PEventType.TOOL,
            content="Test tool call",
            tool_name="Read",
        )

        parsed = unified_to_parsed(event, source=AgentSource.CLAUDE)

        assert parsed is not None
        assert parsed.event_id == "test-123"
        assert parsed.session_id == "session-456"
        assert parsed.source == AgentSource.CLAUDE
        assert parsed.event_type == EventType.TOOL_USE
        assert parsed.tool_name == "Read"

    def test_conversion_with_tool_input(self):
        """unified_to_parsed preserves tool_input as dict."""
        from motus.protocols import EventType as PEventType
        from motus.protocols import UnifiedEvent

        event = UnifiedEvent(
            event_id="test-456",
            session_id="session-789",
            timestamp=FIXED_TIMESTAMP,
            event_type=PEventType.TOOL,
            content="Read file",
            tool_name="Read",
            tool_input={"file_path": "/tmp/test.py"},
        )

        parsed = unified_to_parsed(event, source=AgentSource.CODEX)

        assert parsed is not None
        assert parsed.tool_input == {"file_path": "/tmp/test.py"}
        assert parsed.source == AgentSource.CODEX

    def test_conversion_maps_risk_levels(self):
        """unified_to_parsed correctly maps RiskLevel enum values."""
        from motus.protocols import EventType as PEventType
        from motus.protocols import RiskLevel as PRiskLevel
        from motus.protocols import UnifiedEvent

        # Test all risk levels
        for proto_risk, schema_risk in [
            (PRiskLevel.SAFE, RiskLevel.SAFE),
            (PRiskLevel.MEDIUM, RiskLevel.MEDIUM),
            (PRiskLevel.HIGH, RiskLevel.HIGH),
            (PRiskLevel.CRITICAL, RiskLevel.CRITICAL),
        ]:
            event = UnifiedEvent(
                event_id="risk-test",
                session_id="session-risk",
                timestamp=FIXED_TIMESTAMP,
                event_type=PEventType.TOOL,
                content="Risk test",
                risk_level=proto_risk,
            )

            parsed = unified_to_parsed(event)
            assert parsed is not None
            assert parsed.risk_level == schema_risk

    def test_conversion_maps_event_types(self):
        """unified_to_parsed correctly maps EventType enum values."""
        from motus.protocols import EventType as PEventType
        from motus.protocols import UnifiedEvent

        # Test key event type mappings
        mappings = [
            (PEventType.THINKING, EventType.THINKING),
            (PEventType.TOOL, EventType.TOOL_USE),
            (PEventType.DECISION, EventType.DECISION),
            (PEventType.AGENT_SPAWN, EventType.AGENT_SPAWN),
            (PEventType.ERROR, EventType.ERROR),
            (PEventType.USER_MESSAGE, EventType.USER_MESSAGE),
            (PEventType.RESPONSE, EventType.ASSISTANT_MESSAGE),
        ]

        for proto_type, schema_type in mappings:
            event = UnifiedEvent(
                event_id="type-test",
                session_id="session-type",
                timestamp=FIXED_TIMESTAMP,
                event_type=proto_type,
                content="Type test",
            )

            parsed = unified_to_parsed(event)
            assert parsed is not None
            assert parsed.event_type == schema_type, f"Expected {schema_type} for {proto_type}"

    def test_conversion_preserves_agent_spawn_fields(self):
        """unified_to_parsed preserves agent spawn related fields."""
        from motus.protocols import EventType as PEventType
        from motus.protocols import UnifiedEvent

        event = UnifiedEvent(
            event_id="spawn-test",
            session_id="session-spawn",
            timestamp=FIXED_TIMESTAMP,
            event_type=PEventType.AGENT_SPAWN,
            content="Spawning agent",
            agent_type="Explore",
            agent_description="Quick exploration agent",
            agent_prompt="Find the config file",
            agent_model="haiku",
        )

        parsed = unified_to_parsed(event)

        assert parsed is not None
        assert parsed.spawn_type == "Explore"
        assert parsed.agent_description == "Quick exploration agent"
        assert parsed.spawn_prompt == "Find the config file"
        assert parsed.spawn_model == "haiku"

    def test_conversion_preserves_file_fields(self):
        """unified_to_parsed preserves file operation fields."""
        from motus.protocols import EventType as PEventType
        from motus.protocols import FileOperation, UnifiedEvent

        event = UnifiedEvent(
            event_id="file-test",
            session_id="session-file",
            timestamp=FIXED_TIMESTAMP,
            event_type=PEventType.FILE_MODIFIED,
            content="Modified file",
            file_path="/tmp/test.py",
            file_operation=FileOperation.WRITE,
            lines_added=10,
            lines_removed=5,
            files_affected=["/tmp/test.py", "/tmp/other.py"],
        )

        parsed = unified_to_parsed(event)

        assert parsed is not None
        assert parsed.file_path == "/tmp/test.py"
        assert parsed.file_operation == "write"
        assert parsed.lines_added == 10
        assert parsed.lines_removed == 5
        assert parsed.files_affected == ["/tmp/test.py", "/tmp/other.py"]

    def test_conversion_handles_missing_fields_gracefully(self):
        """unified_to_parsed fills defaults for missing optional fields."""

        # Create a minimal mock object
        class MinimalEvent:
            event_id = "min-test"
            session_id = "session-min"
            timestamp = FIXED_TIMESTAMP
            event_type = None  # Will be handled

        result = unified_to_parsed(MinimalEvent())
        # The function uses defaults when fields are missing
        assert result is not None
        assert result.event_id == "min-test"
        assert result.session_id == "session-min"
        # event_type defaults to THINKING when unmapped
        assert result.event_type == EventType.THINKING

    def test_conversion_default_source_is_unknown(self):
        """unified_to_parsed uses UNKNOWN source when not specified."""
        from motus.protocols import EventType as PEventType
        from motus.protocols import UnifiedEvent

        event = UnifiedEvent(
            event_id="no-source-test",
            session_id="session-no-source",
            timestamp=FIXED_TIMESTAMP,
            event_type=PEventType.THINKING,
            content="Thinking content",
        )

        parsed = unified_to_parsed(event)  # No source arg

        assert parsed is not None
        assert parsed.source == AgentSource.UNKNOWN
