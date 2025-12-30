"""Tests for CLI output module (data structures and conversions)."""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from motus.cli.output import (
    ErrorEvent,
    FileChange,
    SessionInfo,
    SessionStats,
    TaskEvent,
    ThinkingEvent,
    ToolEvent,
    get_last_error,
    get_session_errors,
    unified_event_to_legacy,
    unified_session_to_session_info,
)
from motus.protocols import (
    EventType,
    RiskLevel,
    SessionStatus,
    Source,
    ToolStatus,
    UnifiedEvent,
    UnifiedSession,
)


class TestDataclasses:
    """Test data structure instantiation."""

    def test_thinking_event_creation(self):
        """Test ThinkingEvent dataclass."""
        event = ThinkingEvent(content="Analyzing the problem...", timestamp=datetime.now())
        assert event.content == "Analyzing the problem..."
        assert isinstance(event.timestamp, datetime)

    def test_tool_event_creation(self):
        """Test ToolEvent dataclass with defaults."""
        event = ToolEvent(
            name="Read",
            input={"file_path": "/test.py"},
            timestamp=datetime.now(),
        )
        assert event.name == "Read"
        assert event.input == {"file_path": "/test.py"}
        assert event.status == "running"
        assert event.output is None
        assert event.risk_level == "safe"

    def test_tool_event_with_output(self):
        """Test ToolEvent with output and custom status."""
        event = ToolEvent(
            name="Bash",
            input={"command": "ls"},
            timestamp=datetime.now(),
            status="completed",
            output="file1.py\nfile2.py",
            risk_level="high",
        )
        assert event.status == "completed"
        assert event.output == "file1.py\nfile2.py"
        assert event.risk_level == "high"

    def test_task_event_creation(self):
        """Test TaskEvent dataclass."""
        event = TaskEvent(
            description="Search codebase",
            prompt="Find all Python files",
            subagent_type="Explore",
            model="haiku",
            timestamp=datetime.now(),
        )
        assert event.description == "Search codebase"
        assert event.subagent_type == "Explore"
        assert event.model == "haiku"

    def test_error_event_creation(self):
        """Test ErrorEvent dataclass."""
        event = ErrorEvent(
            message="File not found",
            timestamp=datetime.now(),
            error_type="tool_error",
            tool_name="Read",
            recoverable=False,
        )
        assert event.message == "File not found"
        assert event.error_type == "tool_error"
        assert event.tool_name == "Read"
        assert event.recoverable is False

    def test_error_event_defaults(self):
        """Test ErrorEvent with default values."""
        event = ErrorEvent(message="Unknown error", timestamp=datetime.now())
        assert event.error_type == "unknown"
        assert event.tool_name is None
        assert event.recoverable is True

    def test_file_change_creation(self):
        """Test FileChange dataclass."""
        change = FileChange(path="/path/to/file.py", operation="Edit", timestamp=datetime.now())
        assert change.path == "/path/to/file.py"
        assert change.operation == "Edit"
        assert isinstance(change.timestamp, datetime)

    def test_session_stats_defaults(self):
        """Test SessionStats with default values."""
        stats = SessionStats()
        assert stats.thinking_count == 0
        assert stats.tool_count == 0
        assert stats.agent_count == 0
        assert len(stats.files_modified) == 0
        assert stats.high_risk_ops == 0
        assert isinstance(stats.start_time, datetime)
        assert len(stats.errors) == 0

    def test_session_stats_with_data(self):
        """Test SessionStats with data."""
        stats = SessionStats(
            thinking_count=5,
            tool_count=10,
            agent_count=2,
            files_modified={"file1.py", "file2.py"},
            high_risk_ops=3,
            errors=["error1", "error2"],
        )
        assert stats.thinking_count == 5
        assert stats.tool_count == 10
        assert stats.agent_count == 2
        assert len(stats.files_modified) == 2
        assert stats.high_risk_ops == 3
        assert len(stats.errors) == 2

    def test_session_info_creation(self):
        """Test SessionInfo dataclass."""
        info = SessionInfo(
            session_id="test-123",
            file_path=Path("/tmp/test.jsonl"),
            last_modified=datetime.now(),
            size=1024,
            is_active=True,
            project_path="/project",
            status="active",
            last_action="Edit file.py",
            source="claude",
        )
        assert info.session_id == "test-123"
        assert info.file_path == Path("/tmp/test.jsonl")
        assert info.size == 1024
        assert info.is_active is True
        assert info.status == "active"


class TestUnifiedSessionToSessionInfo:
    """Test conversion from UnifiedSession to SessionInfo."""

    def test_active_session_conversion(self):
        """Test converting an active UnifiedSession."""
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            f.write(b"test data")
            temp_path = Path(f.name)

        try:
            unified = UnifiedSession(
                session_id="test-session-123",
                source=Source.CLAUDE,
                file_path=temp_path,
                project_path="/project/test",
                status=SessionStatus.ACTIVE,
                status_reason="generating",
                created_at=datetime.now(),
                last_modified=datetime.now(),
            )

            session_info = unified_session_to_session_info(unified)

            assert session_info.session_id == "test-session-123"
            assert session_info.file_path == temp_path
            assert session_info.status == "active"
            assert session_info.is_active is True
            assert session_info.project_path == "/project/test"
            assert session_info.source == "claude"
            assert session_info.size == 9  # "test data"
        finally:
            temp_path.unlink()

    def test_idle_session_conversion(self):
        """Test converting an idle UnifiedSession."""
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            temp_path = Path(f.name)

        try:
            unified = UnifiedSession(
                session_id="idle-session",
                source=Source.CODEX,
                file_path=temp_path,
                project_path="/project",
                status=SessionStatus.IDLE,
                status_reason="inactive",
                created_at=datetime.now(),
                last_modified=datetime.now(),
            )

            session_info = unified_session_to_session_info(unified)

            assert session_info.status == "idle"
            assert session_info.is_active is False
            assert session_info.source == "codex"
        finally:
            temp_path.unlink()

    def test_crashed_session_conversion(self):
        """Test converting a crashed UnifiedSession."""
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            temp_path = Path(f.name)

        try:
            unified = UnifiedSession(
                session_id="crashed-session",
                source=Source.GEMINI,
                file_path=temp_path,
                project_path="/project",
                status=SessionStatus.CRASHED,
                status_reason="error",
                created_at=datetime.now(),
                last_modified=datetime.now(),
            )

            session_info = unified_session_to_session_info(unified)

            assert session_info.status == "crashed"
            assert session_info.is_active is False
            assert session_info.source == "gemini"
        finally:
            temp_path.unlink()

    def test_missing_file_size_handling(self):
        """Test handling of missing file during size calculation."""
        # Create a path that doesn't exist
        fake_path = Path("/tmp/nonexistent-file-12345.jsonl")

        unified = UnifiedSession(
            session_id="test-session",
            source=Source.CLAUDE,
            file_path=fake_path,
            project_path="/project",
            status=SessionStatus.IDLE,
            status_reason="test",
            created_at=datetime.now(),
            last_modified=datetime.now(),
        )

        session_info = unified_session_to_session_info(unified)

        # Should default to size 0 when file doesn't exist
        assert session_info.size == 0

    def test_orphaned_status_conversion(self):
        """Test converting an orphaned UnifiedSession."""
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            temp_path = Path(f.name)

        try:
            unified = UnifiedSession(
                session_id="orphaned-session",
                source=Source.CLAUDE,
                file_path=temp_path,
                project_path="/project",
                status=SessionStatus.ORPHANED,
                status_reason="no process",
                created_at=datetime.now(),
                last_modified=datetime.now(),
            )

            session_info = unified_session_to_session_info(unified)

            assert session_info.status == "orphaned"
            assert session_info.is_active is False
        finally:
            temp_path.unlink()


class TestUnifiedEventToLegacy:
    """Test conversion from UnifiedEvent to legacy event types."""

    def test_thinking_event_conversion(self):
        """Test converting thinking event."""
        unified = UnifiedEvent(
            event_id="evt-1",
            event_type=EventType.THINKING,
            timestamp=datetime.now(),
            content="Let me analyze this problem...",
            session_id="test-123",
        )

        legacy = unified_event_to_legacy(unified)

        assert isinstance(legacy, ThinkingEvent)
        assert legacy.content == "Let me analyze this problem..."
        assert isinstance(legacy.timestamp, datetime)

    def test_tool_event_conversion(self):
        """Test converting tool event."""
        unified = UnifiedEvent(
            event_id="evt-2",
            event_type=EventType.TOOL,
            timestamp=datetime.now(),
            content="",
            session_id="test-123",
            tool_name="Read",
            tool_input={"file_path": "/test.py"},
            tool_status=ToolStatus.SUCCESS,
            tool_output="File contents...",
            risk_level=RiskLevel.SAFE,
        )

        legacy = unified_event_to_legacy(unified)

        assert isinstance(legacy, ToolEvent)
        assert legacy.name == "Read"
        assert legacy.input == {"file_path": "/test.py"}
        assert legacy.status == "success"
        assert legacy.output == "File contents..."
        assert legacy.risk_level == "safe"

    def test_tool_event_without_name(self):
        """Test converting tool event with missing name."""
        unified = UnifiedEvent(
            event_id="evt-3",
            event_type=EventType.TOOL,
            timestamp=datetime.now(),
            content="",
            session_id="test-123",
            tool_name=None,
            tool_input={"command": "ls"},
            tool_status=ToolStatus.PENDING,
        )

        legacy = unified_event_to_legacy(unified)

        assert isinstance(legacy, ToolEvent)
        assert legacy.name == "unknown"
        assert legacy.input == {"command": "ls"}

    def test_agent_spawn_event_conversion(self):
        """Test converting agent spawn event."""
        unified = UnifiedEvent(
            event_id="evt-4",
            event_type=EventType.AGENT_SPAWN,
            timestamp=datetime.now(),
            content="Searching codebase",
            session_id="test-123",
            agent_description="Search for Python files",
            agent_prompt="Find all *.py files",
            agent_type="Explore",
            agent_model="haiku",
            model="claude-3-opus",
        )

        legacy = unified_event_to_legacy(unified)

        assert isinstance(legacy, TaskEvent)
        assert legacy.description == "Search for Python files"
        assert legacy.prompt == "Find all *.py files"
        assert legacy.subagent_type == "Explore"
        assert legacy.model == "haiku"

    def test_agent_spawn_fallback_to_content(self):
        """Test agent spawn falls back to content when description missing."""
        unified = UnifiedEvent(
            event_id="evt-5",
            event_type=EventType.AGENT_SPAWN,
            timestamp=datetime.now(),
            content="Fallback description",
            session_id="test-123",
            agent_description=None,
            agent_prompt="",
            agent_type="unknown",
        )

        legacy = unified_event_to_legacy(unified)

        assert isinstance(legacy, TaskEvent)
        assert legacy.description == "Fallback description"

    def test_error_event_conversion(self):
        """Test converting error event."""
        unified = UnifiedEvent(
            event_id="evt-6",
            event_type=EventType.ERROR,
            timestamp=datetime.now(),
            content="File not found",
            session_id="test-123",
            tool_name="Read",
            raw_data={"error_type": "tool_error"},
        )

        legacy = unified_event_to_legacy(unified)

        assert isinstance(legacy, ErrorEvent)
        assert legacy.message == "File not found"
        assert legacy.error_type == "tool_error"
        assert legacy.tool_name == "Read"

    def test_error_event_without_raw_data(self):
        """Test error event with no raw_data."""
        unified = UnifiedEvent(
            event_id="evt-7",
            event_type=EventType.ERROR,
            timestamp=datetime.now(),
            content="Unknown error",
            session_id="test-123",
        )

        legacy = unified_event_to_legacy(unified)

        assert isinstance(legacy, ErrorEvent)
        assert legacy.error_type == "unknown"

    def test_unmappable_event_returns_none(self):
        """Test that unmappable event types return None."""
        unified = UnifiedEvent(
            event_id="evt-8",
            event_type=EventType.DECISION,
            timestamp=datetime.now(),
            content="I decided to use approach X",
            session_id="test-123",
        )

        legacy = unified_event_to_legacy(unified)

        # DECISION events don't have a legacy format yet
        assert legacy is None


class TestGetLastError:
    """Test get_last_error function."""

    def test_get_last_error_no_errors(self):
        """Test get_last_error returns None when no errors exist."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            import json

            # Write some non-error events
            f.write(
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {"content": [{"type": "thinking", "thinking": "Analyzing..."}]},
                    }
                )
                + "\n"
            )
            temp_path = Path(f.name)

        try:
            # Mock orchestrator
            mock_orch = MagicMock()
            mock_builder = MagicMock()
            mock_orch._get_builder_for_file.return_value = mock_builder

            # Mock get_events to return no errors
            mock_orch.get_events.return_value = []

            with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
                result = get_last_error(temp_path)

            assert result is None
        finally:
            temp_path.unlink()

    def test_get_last_error_with_errors(self):
        """Test get_last_error returns most recent error."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            temp_path = Path(f.name)

        try:
            # Mock orchestrator
            mock_orch = MagicMock()
            mock_builder = MagicMock()
            mock_orch._get_builder_for_file.return_value = mock_builder

            # Create mock error events
            error1 = UnifiedEvent(
                event_id="err-1",
                event_type=EventType.ERROR,
                timestamp=datetime(2025, 1, 1, 10, 0),
                content="First error",
                session_id="test",
            )
            error2 = UnifiedEvent(
                event_id="err-2",
                event_type=EventType.ERROR,
                timestamp=datetime(2025, 1, 1, 11, 0),
                content="Second error",
                session_id="test",
            )

            mock_orch.get_events.return_value = [error1, error2]

            with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
                result = get_last_error(temp_path)

            assert result is not None
            assert isinstance(result, ErrorEvent)
            assert result.message == "Second error"
        finally:
            temp_path.unlink()

    def test_get_last_error_missing_file(self):
        """Test get_last_error handles missing file gracefully."""
        fake_path = Path("/tmp/nonexistent-file-98765.jsonl")

        result = get_last_error(fake_path)

        assert result is None


class TestGetSessionErrors:
    """Test get_session_errors function."""

    def test_get_session_errors_empty(self):
        """Test get_session_errors with no errors."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            temp_path = Path(f.name)

        try:
            mock_orch = MagicMock()
            mock_builder = MagicMock()
            mock_orch._get_builder_for_file.return_value = mock_builder
            mock_orch.get_events.return_value = []

            with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
                result = get_session_errors(temp_path)

            assert result == []
        finally:
            temp_path.unlink()

    def test_get_session_errors_with_multiple_errors(self):
        """Test get_session_errors returns all errors in order."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            temp_path = Path(f.name)

        try:
            mock_orch = MagicMock()
            mock_builder = MagicMock()
            mock_orch._get_builder_for_file.return_value = mock_builder

            # Create multiple errors
            errors = [
                UnifiedEvent(
                    event_id=f"err-{i}",
                    event_type=EventType.ERROR,
                    timestamp=datetime(2025, 1, 1, 10, i),
                    content=f"Error {i}",
                    session_id="test",
                )
                for i in range(3)
            ]

            mock_orch.get_events.return_value = errors

            with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
                result = get_session_errors(temp_path)

            assert len(result) == 3
            assert all(isinstance(e, ErrorEvent) for e in result)
            assert result[0].message == "Error 0"
            assert result[2].message == "Error 2"
        finally:
            temp_path.unlink()

    def test_get_session_errors_missing_builder(self):
        """Test get_session_errors when builder not found."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            temp_path = Path(f.name)

        try:
            mock_orch = MagicMock()
            mock_orch._get_builder_for_file.return_value = None

            with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
                result = get_session_errors(temp_path)

            assert result == []
        finally:
            temp_path.unlink()

    def test_get_session_errors_handles_exception(self):
        """Test get_session_errors handles exceptions gracefully."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            temp_path = Path(f.name)

        try:
            mock_orch = MagicMock()
            mock_orch._get_builder_for_file.side_effect = Exception("Test error")

            with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
                result = get_session_errors(temp_path)

            # Should return empty list on error
            assert result == []
        finally:
            temp_path.unlink()
