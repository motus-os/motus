"""Tests for watch_cmd module (real-time session monitoring)."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from motus.cli.output import SessionInfo, SessionStats
from motus.cli.watch_cmd import (
    analyze_session,
    generate_agent_context,
    watch_command,
    watch_session,
)
from motus.protocols import (
    EventType,
    RiskLevel,
    SessionStatus,
    Source,
    UnifiedEvent,
    UnifiedSession,
)


class TestAnalyzeSession:
    """Test analyze_session function."""

    def test_analyze_session_basic(self):
        """Test basic session analysis."""
        session_info = SessionInfo(
            session_id="test-123",
            file_path=Path("/tmp/test.jsonl"),
            last_modified=datetime.now(),
            size=1024,
            project_path="/project",
        )

        # Mock orchestrator
        mock_orch = MagicMock()
        mock_orch.get_events.return_value = []

        unified_session = UnifiedSession(
            session_id="test-123",
            source=Source.CLAUDE,
            file_path=Path("/tmp/test.jsonl"),
            project_path="/project",
            created_at=datetime.now(),
            last_modified=datetime.now(),
            status=SessionStatus.IDLE,
            status_reason="test",
        )

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            stats = analyze_session(session_info, unified_session)

        assert isinstance(stats, SessionStats)
        assert stats.thinking_count == 0
        assert stats.tool_count == 0
        assert stats.agent_count == 0

    def test_analyze_session_with_events(self):
        """Test session analysis with various events."""
        session_info = SessionInfo(
            session_id="test-123",
            file_path=Path("/tmp/test.jsonl"),
            last_modified=datetime.now(),
            size=1024,
            project_path="/project",
        )

        # Create mock events
        events = [
            UnifiedEvent(
                event_id="evt-1",
                session_id="test-123",
                event_type=EventType.THINKING,
                timestamp=datetime.now(),
                content="Analyzing...",
            ),
            UnifiedEvent(
                event_id="evt-2",
                session_id="test-123",
                event_type=EventType.TOOL,
                timestamp=datetime.now(),
                content="Tool call",
                tool_name="Read",
                tool_input={"file_path": "/test.py"},
                risk_level=RiskLevel.SAFE,
            ),
            UnifiedEvent(
                event_id="evt-3",
                session_id="test-123",
                event_type=EventType.AGENT_SPAWN,
                timestamp=datetime.now(),
                content="Spawning agent",
                agent_type="Explore",
            ),
            UnifiedEvent(
                event_id="evt-4",
                session_id="test-123",
                event_type=EventType.TOOL,
                timestamp=datetime.now(),
                content="Write file",
                tool_name="Write",
                tool_input={"file_path": "/output.py"},
                risk_level=RiskLevel.MEDIUM,
            ),
        ]

        mock_orch = MagicMock()
        mock_orch.get_events.return_value = events

        unified_session = UnifiedSession(
            session_id="test-123",
            source=Source.CLAUDE,
            file_path=Path("/tmp/test.jsonl"),
            project_path="/project",
            created_at=datetime.now(),
            last_modified=datetime.now(),
            status=SessionStatus.IDLE,
            status_reason="test",
        )

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            stats = analyze_session(session_info, unified_session)

        assert stats.thinking_count == 1
        assert stats.tool_count == 2
        assert stats.agent_count == 1
        assert len(stats.files_modified) == 1
        assert "/output.py" in stats.files_modified

    def test_analyze_session_high_risk_operations(self):
        """Test counting high-risk operations."""
        session_info = SessionInfo(
            session_id="test-123",
            file_path=Path("/tmp/test.jsonl"),
            last_modified=datetime.now(),
            size=1024,
            project_path="/project",
        )

        events = [
            UnifiedEvent(
                event_id="evt-1",
                session_id="test-123",
                event_type=EventType.TOOL,
                timestamp=datetime.now(),
                content="High risk op",
                tool_name="Bash",
                tool_input={"command": "rm -rf /"},
                risk_level=RiskLevel.HIGH,
            ),
            UnifiedEvent(
                event_id="evt-2",
                session_id="test-123",
                event_type=EventType.TOOL,
                timestamp=datetime.now(),
                content="Critical op",
                tool_name="Edit",
                tool_input={"file_path": "/important.py"},
                risk_level=RiskLevel.CRITICAL,
            ),
        ]

        mock_orch = MagicMock()
        mock_orch.get_events.return_value = events

        unified_session = UnifiedSession(
            session_id="test-123",
            source=Source.CLAUDE,
            file_path=Path("/tmp/test.jsonl"),
            project_path="/project",
            created_at=datetime.now(),
            last_modified=datetime.now(),
            status=SessionStatus.IDLE,
            status_reason="test",
        )

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            stats = analyze_session(session_info, unified_session)

        assert stats.high_risk_ops == 2

    def test_analyze_session_without_unified_session(self):
        """Test analyze_session when it needs to discover unified session."""
        session_info = SessionInfo(
            session_id="test-123",
            file_path=Path("/tmp/test.jsonl"),
            last_modified=datetime.now(),
            size=1024,
            project_path="/project",
        )

        unified_session = UnifiedSession(
            session_id="test-123",
            source=Source.CLAUDE,
            file_path=Path("/tmp/test.jsonl"),
            project_path="/project",
            created_at=datetime.now(),
            last_modified=datetime.now(),
            status=SessionStatus.IDLE,
            status_reason="test",
        )

        mock_orch = MagicMock()
        mock_orch.discover_all.return_value = [unified_session]
        mock_orch.get_events.return_value = []

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            stats = analyze_session(session_info)

        assert isinstance(stats, SessionStats)
        mock_orch.discover_all.assert_called_once()

    def test_analyze_session_edit_file_tracking(self):
        """Test that Edit operations track modified files."""
        session_info = SessionInfo(
            session_id="test-123",
            file_path=Path("/tmp/test.jsonl"),
            last_modified=datetime.now(),
            size=1024,
            project_path="/project",
        )

        events = [
            UnifiedEvent(
                event_id="evt-1",
                session_id="test-123",
                event_type=EventType.TOOL,
                timestamp=datetime.now(),
                content="Edit file",
                tool_name="Edit",
                tool_input={"file_path": "/file1.py"},
                risk_level=RiskLevel.MEDIUM,
            ),
            UnifiedEvent(
                event_id="evt-2",
                session_id="test-123",
                event_type=EventType.TOOL,
                timestamp=datetime.now(),
                content="Edit file",
                tool_name="Edit",
                tool_input={"file_path": "/file2.py"},
                risk_level=RiskLevel.MEDIUM,
            ),
        ]

        mock_orch = MagicMock()
        mock_orch.get_events.return_value = events

        unified_session = UnifiedSession(
            session_id="test-123",
            source=Source.CLAUDE,
            file_path=Path("/tmp/test.jsonl"),
            project_path="/project",
            created_at=datetime.now(),
            last_modified=datetime.now(),
            status=SessionStatus.IDLE,
            status_reason="test",
        )

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            stats = analyze_session(session_info, unified_session)

        assert len(stats.files_modified) == 2
        assert "/file1.py" in stats.files_modified
        assert "/file2.py" in stats.files_modified

    def test_analyze_session_handles_errors(self):
        """Test that analyze_session handles errors gracefully."""
        session_info = SessionInfo(
            session_id="test-123",
            file_path=Path("/tmp/test.jsonl"),
            last_modified=datetime.now(),
            size=1024,
            project_path="/project",
        )

        mock_orch = MagicMock()
        mock_orch.discover_all.side_effect = Exception("Test error")

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            stats = analyze_session(session_info)

        # Should return stats with error recorded
        assert isinstance(stats, SessionStats)
        assert len(stats.errors) == 1


class TestGenerateAgentContext:
    """Test generate_agent_context function."""

    def test_generate_agent_context_basic(self):
        """Test basic context generation."""
        session_info = SessionInfo(
            session_id="test-session-123",
            file_path=Path("/tmp/test.jsonl"),
            last_modified=datetime.now(),
            size=5120,
            project_path="/project",
        )

        mock_orch = MagicMock()
        mock_orch.get_events.return_value = []

        unified_session = UnifiedSession(
            session_id="test-session-123",
            source=Source.CLAUDE,
            file_path=Path("/tmp/test.jsonl"),
            project_path="/project",
            created_at=datetime.now(),
            last_modified=datetime.now(),
            status=SessionStatus.IDLE,
            status_reason="test",
        )

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            context = generate_agent_context(session_info, unified_session)

        assert isinstance(context, str)
        assert "Motus Session Context" in context
        assert "test-session" in context
        assert "5KB" in context

    def test_generate_agent_context_with_high_risk_warning(self):
        """Test context includes warning for high-risk operations."""
        session_info = SessionInfo(
            session_id="test-123",
            file_path=Path("/tmp/test.jsonl"),
            last_modified=datetime.now(),
            size=1024,
            project_path="/project",
        )

        # Create 4 high-risk events to trigger warning
        events = [
            UnifiedEvent(
                event_id=f"evt-{i}",
                session_id="test-123",
                event_type=EventType.TOOL,
                timestamp=datetime.now(),
                content="High risk",
                tool_name="Bash",
                risk_level=RiskLevel.HIGH,
            )
            for i in range(4)
        ]

        mock_orch = MagicMock()
        mock_orch.get_events.return_value = events

        unified_session = UnifiedSession(
            session_id="test-123",
            source=Source.CLAUDE,
            file_path=Path("/tmp/test.jsonl"),
            project_path="/project",
            created_at=datetime.now(),
            last_modified=datetime.now(),
            status=SessionStatus.IDLE,
            status_reason="test",
        )

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            context = generate_agent_context(session_info, unified_session)

        assert "high-risk operations detected" in context.lower()

    def test_generate_agent_context_with_thinking_warning(self):
        """Test context includes warning for low thinking vs high tool usage."""
        session_info = SessionInfo(
            session_id="test-123",
            file_path=Path("/tmp/test.jsonl"),
            last_modified=datetime.now(),
            size=1024,
            project_path="/project",
        )

        # 51 tool calls but only 4 thinking blocks
        events = [
            UnifiedEvent(
                event_id=f"tool-{i}",
                session_id="test-123",
                event_type=EventType.TOOL,
                timestamp=datetime.now(),
                content="Tool call",
                tool_name="Read",
                risk_level=RiskLevel.SAFE,
            )
            for i in range(51)
        ] + [
            UnifiedEvent(
                event_id=f"think-{i}",
                session_id="test-123",
                event_type=EventType.THINKING,
                timestamp=datetime.now(),
                content="Thinking...",
            )
            for i in range(4)
        ]

        mock_orch = MagicMock()
        mock_orch.get_events.return_value = events

        unified_session = UnifiedSession(
            session_id="test-123",
            source=Source.CLAUDE,
            file_path=Path("/tmp/test.jsonl"),
            project_path="/project",
            created_at=datetime.now(),
            last_modified=datetime.now(),
            status=SessionStatus.IDLE,
            status_reason="test",
        )

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            context = generate_agent_context(session_info, unified_session)

        assert "deliberation" in context.lower() or "thinking" in context.lower()

    def test_generate_agent_context_with_many_files_warning(self):
        """Test context includes warning for many modified files."""
        session_info = SessionInfo(
            session_id="test-123",
            file_path=Path("/tmp/test.jsonl"),
            last_modified=datetime.now(),
            size=1024,
            project_path="/project",
        )

        # Create 11 Write operations for different files
        events = [
            UnifiedEvent(
                event_id=f"evt-{i}",
                session_id="test-123",
                event_type=EventType.TOOL,
                timestamp=datetime.now(),
                content="Write file",
                tool_name="Write",
                tool_input={"file_path": f"/file{i}.py"},
                risk_level=RiskLevel.MEDIUM,
            )
            for i in range(11)
        ]

        mock_orch = MagicMock()
        mock_orch.get_events.return_value = events

        unified_session = UnifiedSession(
            session_id="test-123",
            source=Source.CLAUDE,
            file_path=Path("/tmp/test.jsonl"),
            project_path="/project",
            created_at=datetime.now(),
            last_modified=datetime.now(),
            status=SessionStatus.IDLE,
            status_reason="test",
        )

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            context = generate_agent_context(session_info, unified_session)

        assert "Many files modified" in context or "checkpoint" in context.lower()

    def test_generate_agent_context_with_many_agents_warning(self):
        """Test context includes warning for multiple subagents."""
        session_info = SessionInfo(
            session_id="test-123",
            file_path=Path("/tmp/test.jsonl"),
            last_modified=datetime.now(),
            size=1024,
            project_path="/project",
        )

        # Create 6 agent spawn events
        events = [
            UnifiedEvent(
                event_id=f"evt-{i}",
                session_id="test-123",
                event_type=EventType.AGENT_SPAWN,
                timestamp=datetime.now(),
                content="Spawning agent",
                agent_type="Explore",
            )
            for i in range(6)
        ]

        mock_orch = MagicMock()
        mock_orch.get_events.return_value = events

        unified_session = UnifiedSession(
            session_id="test-123",
            source=Source.CLAUDE,
            file_path=Path("/tmp/test.jsonl"),
            project_path="/project",
            created_at=datetime.now(),
            last_modified=datetime.now(),
            status=SessionStatus.IDLE,
            status_reason="test",
        )

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            context = generate_agent_context(session_info, unified_session)

        assert "subagents" in context.lower() or "coordination" in context.lower()


class TestWatchCommand:
    """Test watch_command function."""

    def test_watch_command_no_sessions(self):
        """Test watch_command with no active sessions."""
        args = MagicMock()
        args.session_id = None

        mock_orch = MagicMock()
        mock_orch.discover_all.return_value = []

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            with pytest.raises(SystemExit):
                watch_command(args)

    def test_watch_command_with_session_id(self):
        """Test watch_command with specific session ID."""
        args = MagicMock()
        args.session_id = "test-123"

        unified_session = UnifiedSession(
            session_id="test-12345-full",
            source=Source.CLAUDE,
            file_path=Path("/tmp/test.jsonl"),
            project_path="/project",
            created_at=datetime.now(),
            last_modified=datetime.now(),
            status=SessionStatus.ACTIVE,
            status_reason="test",
        )

        mock_orch = MagicMock()
        mock_orch.discover_all.return_value = [unified_session]
        mock_orch.get_events.return_value = []

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            with patch("motus.cli.watch_cmd.watch_session") as mock_watch:
                watch_command(args)
                mock_watch.assert_called_once()

    def test_watch_command_session_not_found(self):
        """Test watch_command with non-existent session ID."""
        args = MagicMock()
        args.session_id = "nonexistent"

        unified_session = UnifiedSession(
            session_id="other-session",
            source=Source.CLAUDE,
            file_path=Path("/tmp/test.jsonl"),
            project_path="/project",
            created_at=datetime.now(),
            last_modified=datetime.now(),
            status=SessionStatus.ACTIVE,
            status_reason="test",
        )

        mock_orch = MagicMock()
        mock_orch.discover_all.return_value = [unified_session]

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            with pytest.raises(SystemExit):
                watch_command(args)

    def test_watch_command_most_recent(self):
        """Test watch_command selects most recent session when no ID provided."""
        args = MagicMock()
        args.session_id = None

        unified_sessions = [
            UnifiedSession(
                session_id="session-1",
                source=Source.CLAUDE,
                file_path=Path("/tmp/test1.jsonl"),
                project_path="/project",
                created_at=datetime.now(),
                last_modified=datetime.now(),
                status=SessionStatus.ACTIVE,
                status_reason="test",
            ),
            UnifiedSession(
                session_id="session-2",
                source=Source.CLAUDE,
                file_path=Path("/tmp/test2.jsonl"),
                project_path="/project",
                created_at=datetime.now(),
                last_modified=datetime.now(),
                status=SessionStatus.ACTIVE,
                status_reason="test",
            ),
        ]

        mock_orch = MagicMock()
        mock_orch.discover_all.return_value = unified_sessions
        mock_orch.get_events.return_value = []

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            with patch("motus.cli.watch_cmd.watch_session") as mock_watch:
                watch_command(args)
                # Should watch the first (most recent) session
                mock_watch.assert_called_once()


class TestWatchSession:
    """Test watch_session function (limited testing due to interactive nature)."""

    def test_watch_session_no_unified_session_found(self):
        """Test watch_session when unified session cannot be found."""
        session_info = SessionInfo(
            session_id="test-123",
            file_path=Path("/tmp/test.jsonl"),
            last_modified=datetime.now(),
            size=1024,
            project_path="/project",
        )

        mock_orch = MagicMock()
        mock_orch.discover_all.return_value = []

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            with patch("motus.cli.watch_cmd.console") as mock_console:
                # Call without unified_session, so it tries to discover
                watch_session(session_info, unified_session=None)
                # Should print error message
                assert mock_console.print.called

    def test_watch_session_with_unified_session(self):
        """Test watch_session with pre-provided unified session."""
        session_info = SessionInfo(
            session_id="test-123",
            file_path=Path("/tmp/test.jsonl"),
            last_modified=datetime.now(),
            size=1024,
            project_path="/project",
        )

        unified_session = UnifiedSession(
            session_id="test-123",
            source=Source.CLAUDE,
            file_path=Path("/tmp/test.jsonl"),
            project_path="/project",
            created_at=datetime.now(),
            last_modified=datetime.now(),
            status=SessionStatus.ACTIVE,
            status_reason="test",
        )

        mock_orch = MagicMock()
        mock_orch.get_events.return_value = []

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            with patch("motus.cli.watch_cmd.console") as mock_console:
                # Use keyboard interrupt to exit the watch loop quickly
                mock_console.print.side_effect = [None, None, None, KeyboardInterrupt()]

                try:
                    watch_session(session_info, unified_session)
                except KeyboardInterrupt:
                    pass

                # Should have called orchestrator.get_events
                assert mock_orch.get_events.called
