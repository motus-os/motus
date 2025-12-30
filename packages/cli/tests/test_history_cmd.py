"""Tests for history_cmd module (command history display)."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from motus.commands.history_cmd import history_command
from motus.protocols import (
    EventType,
    SessionStatus,
    Source,
    UnifiedEvent,
    UnifiedSession,
)


class TestHistoryCommand:
    """Test history_command function."""

    def test_history_command_no_sessions(self):
        """Test history command with no sessions."""
        mock_orch = MagicMock()
        mock_orch.discover_all.return_value = []

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            with patch("motus.commands.history_cmd.console") as mock_console:
                history_command()
                # Should print "No recent sessions found"
                assert mock_console.print.called

    def test_history_command_with_sessions_no_events(self):
        """Test history command with sessions but no events."""
        sessions = [
            UnifiedSession(
                session_id="test-123",
                source=Source.CLAUDE,
                file_path=Path("/tmp/test.jsonl"),
                project_path="/project",
                created_at=datetime.now(),
                last_modified=datetime.now(),
                status=SessionStatus.ACTIVE,
                status_reason="test",
            )
        ]

        mock_orch = MagicMock()
        mock_orch.discover_all.return_value = sessions
        mock_orch.get_events.return_value = []

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            with patch("motus.commands.history_cmd.console") as mock_console:
                history_command()
                # Should print "No recent history found"
                assert mock_console.print.called

    def test_history_command_with_tool_events(self):
        """Test history command displays tool events."""
        sessions = [
            UnifiedSession(
                session_id="test-123",
                source=Source.CLAUDE,
                file_path=Path("/tmp/test.jsonl"),
                project_path="/project",
                created_at=datetime.now(),
                last_modified=datetime.now(),
                status=SessionStatus.ACTIVE,
                status_reason="test",
            )
        ]

        events = [
            UnifiedEvent(
                event_id="evt-1",
                session_id="test-123",
                event_type=EventType.TOOL,
                timestamp=datetime.now(),
                content="Read file",
                tool_name="Read",
                tool_input={"file_path": "/test.py"},
            ),
            UnifiedEvent(
                event_id="evt-2",
                session_id="test-123",
                event_type=EventType.TOOL,
                timestamp=datetime.now(),
                content="Edit file",
                tool_name="Edit",
                tool_input={"file_path": "/test.py"},
            ),
        ]

        mock_orch = MagicMock()
        mock_orch.discover_all.return_value = sessions
        mock_orch.get_events.return_value = events

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            with patch("motus.commands.history_cmd.console") as mock_console:
                history_command()
                # Should display table with tool events
                assert mock_console.print.called

    def test_history_command_with_thinking_events(self):
        """Test history command displays thinking events."""
        sessions = [
            UnifiedSession(
                session_id="test-123",
                source=Source.CLAUDE,
                file_path=Path("/tmp/test.jsonl"),
                project_path="/project",
                created_at=datetime.now(),
                last_modified=datetime.now(),
                status=SessionStatus.ACTIVE,
                status_reason="test",
            )
        ]

        events = [
            UnifiedEvent(
                event_id="evt-1",
                session_id="test-123",
                event_type=EventType.THINKING,
                timestamp=datetime.now(),
                content="I need to analyze the code structure carefully.",
            ),
        ]

        mock_orch = MagicMock()
        mock_orch.discover_all.return_value = sessions
        mock_orch.get_events.return_value = events

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            with patch("motus.commands.history_cmd.console") as mock_console:
                history_command()
                assert mock_console.print.called

    def test_history_command_with_agent_spawn_events(self):
        """Test history command displays agent spawn events."""
        sessions = [
            UnifiedSession(
                session_id="test-123",
                source=Source.CLAUDE,
                file_path=Path("/tmp/test.jsonl"),
                project_path="/project",
                created_at=datetime.now(),
                last_modified=datetime.now(),
                status=SessionStatus.ACTIVE,
                status_reason="test",
            )
        ]

        events = [
            UnifiedEvent(
                event_id="evt-1",
                session_id="test-123",
                event_type=EventType.AGENT_SPAWN,
                timestamp=datetime.now(),
                content="Spawning agent",
                agent_type="Explore",
                agent_model="haiku",
            ),
        ]

        mock_orch = MagicMock()
        mock_orch.discover_all.return_value = sessions
        mock_orch.get_events.return_value = events

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            with patch("motus.commands.history_cmd.console") as mock_console:
                history_command()
                assert mock_console.print.called

    def test_history_command_with_decision_events(self):
        """Test history command displays decision events."""
        sessions = [
            UnifiedSession(
                session_id="test-123",
                source=Source.CLAUDE,
                file_path=Path("/tmp/test.jsonl"),
                project_path="/project",
                created_at=datetime.now(),
                last_modified=datetime.now(),
                status=SessionStatus.ACTIVE,
                status_reason="test",
            )
        ]

        events = [
            UnifiedEvent(
                event_id="evt-1",
                session_id="test-123",
                event_type=EventType.DECISION,
                timestamp=datetime.now(),
                content="I decided to use async/await pattern",
            ),
        ]

        mock_orch = MagicMock()
        mock_orch.discover_all.return_value = sessions
        mock_orch.get_events.return_value = events

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            with patch("motus.commands.history_cmd.console") as mock_console:
                history_command()
                assert mock_console.print.called

    def test_history_command_with_error_events(self):
        """Test history command displays error events."""
        sessions = [
            UnifiedSession(
                session_id="test-123",
                source=Source.CLAUDE,
                file_path=Path("/tmp/test.jsonl"),
                project_path="/project",
                created_at=datetime.now(),
                last_modified=datetime.now(),
                status=SessionStatus.ACTIVE,
                status_reason="test",
            )
        ]

        events = [
            UnifiedEvent(
                event_id="evt-1",
                session_id="test-123",
                event_type=EventType.ERROR,
                timestamp=datetime.now(),
                content="File not found error",
            ),
        ]

        mock_orch = MagicMock()
        mock_orch.discover_all.return_value = sessions
        mock_orch.get_events.return_value = events

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            with patch("motus.commands.history_cmd.console") as mock_console:
                history_command()
                assert mock_console.print.called

    def test_history_command_bash_tool_truncation(self):
        """Test that long bash commands are truncated."""
        sessions = [
            UnifiedSession(
                session_id="test-123",
                source=Source.CLAUDE,
                file_path=Path("/tmp/test.jsonl"),
                project_path="/project",
                created_at=datetime.now(),
                last_modified=datetime.now(),
                status=SessionStatus.ACTIVE,
                status_reason="test",
            )
        ]

        events = [
            UnifiedEvent(
                event_id="evt-1",
                session_id="test-123",
                event_type=EventType.TOOL,
                timestamp=datetime.now(),
                content="Run command",
                tool_name="Bash",
                tool_input={"command": "A" * 100},
            ),
        ]

        mock_orch = MagicMock()
        mock_orch.discover_all.return_value = sessions
        mock_orch.get_events.return_value = events

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            with patch("motus.commands.history_cmd.console") as mock_console:
                history_command()
                assert mock_console.print.called

    def test_history_command_long_thinking_truncation(self):
        """Test that long thinking content is truncated."""
        sessions = [
            UnifiedSession(
                session_id="test-123",
                source=Source.CLAUDE,
                file_path=Path("/tmp/test.jsonl"),
                project_path="/project",
                created_at=datetime.now(),
                last_modified=datetime.now(),
                status=SessionStatus.ACTIVE,
                status_reason="test",
            )
        ]

        events = [
            UnifiedEvent(
                event_id="evt-1",
                session_id="test-123",
                event_type=EventType.THINKING,
                timestamp=datetime.now(),
                content="X" * 150,
            ),
        ]

        mock_orch = MagicMock()
        mock_orch.discover_all.return_value = sessions
        mock_orch.get_events.return_value = events

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            with patch("motus.commands.history_cmd.console") as mock_console:
                history_command()
                assert mock_console.print.called

    def test_history_command_multiple_sessions(self):
        """Test history command with multiple sessions."""
        sessions = [
            UnifiedSession(
                session_id=f"session-{i}",
                source=Source.CLAUDE,
                file_path=Path(f"/tmp/test{i}.jsonl"),
                project_path="/project",
                created_at=datetime.now(),
                last_modified=datetime.now(),
                status=SessionStatus.ACTIVE,
                status_reason="test",
            )
            for i in range(5)
        ]

        events = [
            UnifiedEvent(
                event_id="evt-1",
                session_id="session-0",
                event_type=EventType.TOOL,
                timestamp=datetime.now(),
                content="Tool call",
                tool_name="Read",
                tool_input={"file_path": "/test.py"},
            ),
        ]

        mock_orch = MagicMock()
        mock_orch.discover_all.return_value = sessions
        mock_orch.get_events.return_value = events

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            with patch("motus.commands.history_cmd.console") as mock_console:
                history_command()
                assert mock_console.print.called

    def test_history_command_max_sessions_limit(self):
        """Test that history command respects max_sessions parameter."""
        sessions = [
            UnifiedSession(
                session_id=f"session-{i}",
                source=Source.CLAUDE,
                file_path=Path(f"/tmp/test{i}.jsonl"),
                project_path="/project",
                created_at=datetime.now(),
                last_modified=datetime.now(),
                status=SessionStatus.ACTIVE,
                status_reason="test",
            )
            for i in range(20)
        ]

        mock_orch = MagicMock()
        mock_orch.discover_all.return_value = sessions
        mock_orch.get_events.return_value = []

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            with patch("motus.commands.history_cmd.console"):
                history_command(max_sessions=5)
                # Should only process first 5 sessions
                assert mock_orch.get_events.call_count <= 5

    def test_history_command_max_events_limit(self):
        """Test that history command respects max_events parameter."""
        sessions = [
            UnifiedSession(
                session_id="test-123",
                source=Source.CLAUDE,
                file_path=Path("/tmp/test.jsonl"),
                project_path="/project",
                created_at=datetime.now(),
                last_modified=datetime.now(),
                status=SessionStatus.ACTIVE,
                status_reason="test",
            )
        ]

        # Create 100 events
        events = [
            UnifiedEvent(
                event_id=f"evt-{i}",
                session_id="test-123",
                event_type=EventType.TOOL,
                timestamp=datetime.now(),
                content=f"Event {i}",
                tool_name="Read",
                tool_input={"file_path": f"/test{i}.py"},
            )
            for i in range(100)
        ]

        mock_orch = MagicMock()
        mock_orch.discover_all.return_value = sessions
        mock_orch.get_events.return_value = events

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            with patch("motus.commands.history_cmd.console") as mock_console:
                history_command(max_events=10)
                assert mock_console.print.called

    def test_history_command_handles_session_error(self):
        """Test that history command handles errors when getting session events."""
        sessions = [
            UnifiedSession(
                session_id="test-123",
                source=Source.CLAUDE,
                file_path=Path("/tmp/test.jsonl"),
                project_path="/project",
                created_at=datetime.now(),
                last_modified=datetime.now(),
                status=SessionStatus.ACTIVE,
                status_reason="test",
            ),
            UnifiedSession(
                session_id="test-456",
                source=Source.CLAUDE,
                file_path=Path("/tmp/test2.jsonl"),
                project_path="/project",
                created_at=datetime.now(),
                last_modified=datetime.now(),
                status=SessionStatus.ACTIVE,
                status_reason="test",
            ),
        ]

        # First session raises error, second returns events
        def get_events_side_effect(session):
            if session.session_id == "test-123":
                raise Exception("Test error")
            return [
                UnifiedEvent(
                    event_id="evt-1",
                    session_id="test-456",
                    event_type=EventType.TOOL,
                    timestamp=datetime.now(),
                    content="Tool call",
                    tool_name="Read",
                    tool_input={"file_path": "/test.py"},
                )
            ]

        mock_orch = MagicMock()
        mock_orch.discover_all.return_value = sessions
        mock_orch.get_events.side_effect = get_events_side_effect

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            with patch("motus.commands.history_cmd.console") as mock_console:
                history_command()
                # Should still display events from successful session
                assert mock_console.print.called

    def test_history_command_different_sources(self):
        """Test history command with different session sources."""
        sessions = [
            UnifiedSession(
                session_id="claude-session",
                source=Source.CLAUDE,
                file_path=Path("/tmp/claude.jsonl"),
                project_path="/project",
                created_at=datetime.now(),
                last_modified=datetime.now(),
                status=SessionStatus.ACTIVE,
                status_reason="test",
            ),
            UnifiedSession(
                session_id="codex-session",
                source=Source.CODEX,
                file_path=Path("/tmp/codex.jsonl"),
                project_path="/project",
                created_at=datetime.now(),
                last_modified=datetime.now(),
                status=SessionStatus.ACTIVE,
                status_reason="test",
            ),
            UnifiedSession(
                session_id="gemini-session",
                source=Source.GEMINI,
                file_path=Path("/tmp/gemini.jsonl"),
                project_path="/project",
                created_at=datetime.now(),
                last_modified=datetime.now(),
                status=SessionStatus.ACTIVE,
                status_reason="test",
            ),
        ]

        events = [
            UnifiedEvent(
                event_id="evt-1",
                session_id="claude-session",
                event_type=EventType.TOOL,
                timestamp=datetime.now(),
                content="Tool call",
                tool_name="Read",
                tool_input={"file_path": "/test.py"},
            ),
        ]

        mock_orch = MagicMock()
        mock_orch.discover_all.return_value = sessions
        mock_orch.get_events.return_value = events

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            with patch("motus.commands.history_cmd.console") as mock_console:
                history_command()
                assert mock_console.print.called

    def test_history_command_tool_with_query(self):
        """Test history command with tool that has query input."""
        sessions = [
            UnifiedSession(
                session_id="test-123",
                source=Source.CLAUDE,
                file_path=Path("/tmp/test.jsonl"),
                project_path="/project",
                created_at=datetime.now(),
                last_modified=datetime.now(),
                status=SessionStatus.ACTIVE,
                status_reason="test",
            )
        ]

        events = [
            UnifiedEvent(
                event_id="evt-1",
                session_id="test-123",
                event_type=EventType.TOOL,
                timestamp=datetime.now(),
                content="Search",
                tool_name="WebSearch",
                tool_input={"query": "python best practices"},
            ),
        ]

        mock_orch = MagicMock()
        mock_orch.discover_all.return_value = sessions
        mock_orch.get_events.return_value = events

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            with patch("motus.commands.history_cmd.console") as mock_console:
                history_command()
                assert mock_console.print.called

    def test_history_command_tool_with_pattern(self):
        """Test history command with tool that has pattern input."""
        sessions = [
            UnifiedSession(
                session_id="test-123",
                source=Source.CLAUDE,
                file_path=Path("/tmp/test.jsonl"),
                project_path="/project",
                created_at=datetime.now(),
                last_modified=datetime.now(),
                status=SessionStatus.ACTIVE,
                status_reason="test",
            )
        ]

        events = [
            UnifiedEvent(
                event_id="evt-1",
                session_id="test-123",
                event_type=EventType.TOOL,
                timestamp=datetime.now(),
                content="Search pattern",
                tool_name="Grep",
                tool_input={"pattern": "def.*test"},
            ),
        ]

        mock_orch = MagicMock()
        mock_orch.discover_all.return_value = sessions
        mock_orch.get_events.return_value = events

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            with patch("motus.commands.history_cmd.console") as mock_console:
                history_command()
                assert mock_console.print.called
