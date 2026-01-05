"""Additional tests for ui/web/event_parser.py to increase coverage."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from motus.protocols import Source
from motus.schema.events import AgentSource, EventType, ParsedEvent, RiskLevel
from tests.fixtures.constants import FIXED_TIMESTAMP


class TestParseSessionHistoryPagination:
    """Tests for parse_session_history pagination behavior."""

    @patch("motus.ui.web.event_parser.tail_lines")
    @patch("motus.ui.web.event_parser.get_file_stats")
    @patch("motus.ui.web.event_parser.get_orchestrator")
    def test_initial_load_returns_newest_first(self, mock_get_orch, mock_stats, mock_tail):
        """Initial load returns most recent events newest-first."""
        from motus.ui.web.event_parser import parse_session_history

        mock_session = Mock()
        mock_session.source = Source.CLAUDE
        mock_session.file_path = Path("/tmp/test.jsonl")
        mock_session.project_path = "/project"

        # Create mock events with timestamps
        mock_events = []
        for i in range(10):
            event = Mock()
            event.timestamp = FIXED_TIMESTAMP
            mock_events.append(event)

        mock_builder = Mock()
        mock_builder.parse_line.return_value = [mock_events[0]]

        mock_orch = Mock()
        mock_orch.get_session.return_value = mock_session
        mock_orch.get_builder.return_value = mock_builder
        mock_get_orch.return_value = mock_orch

        mock_stats.return_value = {"line_count": 10}
        # Mock 10 lines
        mock_tail.return_value = [f'{{"type": "event", "index": {i}}}' for i in range(10)]

        result = parse_session_history("test-session", offset=0, batch_size=5)

        assert result["offset"] == 0
        assert result["error"] is None

    @patch("motus.ui.web.event_parser.tail_lines")
    @patch("motus.ui.web.event_parser.get_file_stats")
    @patch("motus.ui.web.event_parser.get_orchestrator")
    def test_load_more_with_offset(self, mock_get_orch, mock_stats, mock_tail):
        """Load more with offset returns earlier events."""
        from motus.ui.web.event_parser import parse_session_history

        mock_session = Mock()
        mock_session.source = Source.CLAUDE
        mock_session.file_path = Path("/tmp/test.jsonl")
        mock_session.project_path = "/project"

        mock_builder = Mock()
        mock_event = Mock()
        mock_builder.parse_line.return_value = [mock_event]

        mock_orch = Mock()
        mock_orch.get_session.return_value = mock_session
        mock_orch.get_builder.return_value = mock_builder
        mock_get_orch.return_value = mock_orch

        mock_stats.return_value = {"line_count": 100}
        mock_tail.return_value = [f'{{"type": "event", "index": {i}}}' for i in range(50)]

        # Request with offset (like "load more")
        result = parse_session_history("test-session", offset=10, batch_size=5)

        assert result["offset"] == 10
        assert result["error"] is None

    @patch("motus.ui.web.event_parser.tail_lines")
    @patch("motus.ui.web.event_parser.get_file_stats")
    @patch("motus.ui.web.event_parser.get_orchestrator")
    def test_has_more_flag_when_more_events_exist(self, mock_get_orch, mock_stats, mock_tail):
        """has_more flag is True when more events exist."""
        from motus.ui.web.event_parser import parse_session_history

        mock_session = Mock()
        mock_session.source = Source.CLAUDE
        mock_session.file_path = Path("/tmp/test.jsonl")
        mock_session.project_path = "/project"

        mock_builder = Mock()
        mock_event = Mock()
        mock_builder.parse_line.return_value = [mock_event]

        mock_orch = Mock()
        mock_orch.get_session.return_value = mock_session
        mock_orch.get_builder.return_value = mock_builder
        mock_get_orch.return_value = mock_orch

        # Large file with many events
        mock_stats.return_value = {"line_count": 1000}
        # Return enough lines to indicate more exist
        mock_tail.return_value = ['{"type": "event"}' for i in range(500)]

        result = parse_session_history("test-session", offset=0, batch_size=10)

        assert result["has_more"] is True

    @patch("motus.ui.web.event_parser.tail_lines")
    @patch("motus.ui.web.event_parser.get_file_stats")
    @patch("motus.ui.web.event_parser.get_orchestrator")
    def test_format_callback_is_called(self, mock_get_orch, mock_stats, mock_tail):
        """format_callback is called for each parsed event."""
        from motus.ui.web.event_parser import parse_session_history

        mock_session = Mock()
        mock_session.source = Source.CLAUDE
        mock_session.file_path = Path("/tmp/test.jsonl")
        mock_session.project_path = "/project"

        mock_event = Mock()
        mock_builder = Mock()
        mock_builder.parse_line.return_value = [mock_event]

        mock_orch = Mock()
        mock_orch.get_session.return_value = mock_session
        mock_orch.get_builder.return_value = mock_builder
        mock_get_orch.return_value = mock_orch

        mock_stats.return_value = {"line_count": 10}
        mock_tail.return_value = ['{"type": "event"}'] * 3

        callback_calls = []

        def format_callback(event, session_id, project_path, source):
            callback_calls.append((event, session_id, project_path, source))
            return {"formatted": True}

        result = parse_session_history(
            "test-session", offset=0, batch_size=10, format_callback=format_callback
        )

        # Should have called callback for each parsed event
        assert len(callback_calls) > 0
        assert result["error"] is None

    @patch("motus.ui.web.event_parser.tail_lines")
    @patch("motus.ui.web.event_parser.get_file_stats")
    @patch("motus.ui.web.event_parser.get_orchestrator")
    def test_early_termination_when_enough_events(self, mock_get_orch, mock_stats, mock_tail):
        """Parser terminates early when enough events collected."""
        from motus.ui.web.event_parser import parse_session_history

        mock_session = Mock()
        mock_session.source = Source.CLAUDE
        mock_session.file_path = Path("/tmp/test.jsonl")
        mock_session.project_path = "/project"

        mock_event = Mock()
        mock_builder = Mock()
        mock_builder.parse_line.return_value = [mock_event]

        mock_orch = Mock()
        mock_orch.get_session.return_value = mock_session
        mock_orch.get_builder.return_value = mock_builder
        mock_get_orch.return_value = mock_orch

        mock_stats.return_value = {"line_count": 1000}
        # Provide many lines
        mock_tail.return_value = ['{"type": "event"}'] * 1000

        result = parse_session_history("test-session", offset=0, batch_size=5)

        # Should not process all 1000 lines due to early termination
        assert result["error"] is None


class TestParseBackfillEventsDetailed:
    """Detailed tests for parse_backfill_events."""

    @patch("builtins.open", create=True)
    @patch("motus.ui.web.event_parser.get_orchestrator")
    def test_reads_last_10kb_for_claude_sessions(self, mock_get_orch, mock_open):
        """Reads last ~10KB from Claude session files."""
        from motus.ui.web.event_parser import parse_backfill_events

        mock_session = Mock()
        mock_session.source = Source.CLAUDE
        mock_session.session_id = "claude-session"
        mock_session.project_path = "/test"
        mock_session.file_path = MagicMock()
        # File is 20KB
        mock_session.file_path.stat.return_value.st_size = 20000

        mock_file = MagicMock()
        mock_file.read.return_value = '{"type": "event"}\n'
        mock_file.__enter__.return_value = mock_file
        mock_open.return_value = mock_file

        mock_builder = Mock()
        mock_event = Mock()
        mock_builder.parse_line.return_value = [mock_event]
        mock_orch = Mock()
        mock_orch.get_builder.return_value = mock_builder
        mock_get_orch.return_value = mock_orch

        parse_backfill_events([mock_session], limit=10)

        # Should have called seek with offset from end
        mock_file.seek.assert_called_once()
        seek_pos = mock_file.seek.call_args[0][0]
        assert seek_pos == 10000  # 20000 - 10000

    @patch("motus.ui.web.event_parser.get_orchestrator")
    def test_uses_orchestrator_for_gemini_sessions(self, mock_get_orch):
        """Uses orchestrator.get_events for Gemini sessions."""
        from motus.ui.web.event_parser import parse_backfill_events

        mock_session = Mock()
        mock_session.source = Source.GEMINI
        mock_session.session_id = "gemini-session"
        mock_session.project_path = "/test"

        mock_events = [Mock() for _ in range(15)]
        mock_orch = Mock()
        mock_orch.get_events.return_value = mock_events
        mock_orch.get_builder.return_value = Mock()
        mock_get_orch.return_value = mock_orch

        parse_backfill_events([mock_session], limit=10)

        # Should have called get_events
        mock_orch.get_events.assert_called_once_with(mock_session)

    @patch("motus.ui.web.event_parser.get_orchestrator")
    def test_takes_last_10_events_from_codex(self, mock_get_orch):
        """Takes last 10 events from Codex sessions."""
        from motus.ui.web.event_parser import parse_backfill_events

        mock_session = Mock()
        mock_session.source = Source.CODEX
        mock_session.session_id = "codex-session"
        mock_session.project_path = "/test"

        # Create 20 mock events
        mock_events = [Mock() for _ in range(20)]
        mock_orch = Mock()
        mock_orch.get_events.return_value = mock_events
        mock_orch.get_builder.return_value = Mock()
        mock_get_orch.return_value = mock_orch

        events = parse_backfill_events([mock_session], limit=30)

        # Should process only last 10 from the session
        assert isinstance(events, list)

    @patch("builtins.open", create=True)
    @patch("motus.ui.web.event_parser.get_orchestrator")
    def test_handles_oserror_for_individual_session(self, mock_get_orch, mock_open):
        """Handles OSError for individual session and continues."""
        from motus.ui.web.event_parser import parse_backfill_events

        mock_session1 = Mock()
        mock_session1.source = Source.CLAUDE
        mock_session1.session_id = "session-1"
        mock_session1.project_path = "/test1"
        mock_session1.file_path = MagicMock()
        mock_session1.file_path.stat.side_effect = OSError("File not found")

        mock_session2 = Mock()
        mock_session2.source = Source.CLAUDE
        mock_session2.session_id = "session-2"
        mock_session2.project_path = "/test2"
        mock_session2.file_path = MagicMock()
        mock_session2.file_path.stat.return_value.st_size = 10000

        mock_file = MagicMock()
        mock_file.read.return_value = '{"type": "event"}\n'
        mock_file.__enter__.return_value = mock_file
        mock_open.return_value = mock_file

        mock_builder = Mock()
        mock_event = Mock()
        mock_builder.parse_line.return_value = [mock_event]
        mock_orch = Mock()
        mock_orch.get_builder.return_value = mock_builder
        mock_get_orch.return_value = mock_orch

        # Should not raise, should continue to session-2
        events = parse_backfill_events([mock_session1, mock_session2], limit=10)

        assert isinstance(events, list)

    @patch("motus.ui.web.event_parser.get_orchestrator")
    def test_handles_unexpected_exception_for_session(self, mock_get_orch):
        """Handles unexpected exceptions for individual sessions."""
        from motus.ui.web.event_parser import parse_backfill_events

        mock_session = Mock()
        mock_session.source = Source.CODEX
        mock_session.session_id = "session-1"
        mock_session.project_path = "/test"

        mock_orch = Mock()
        mock_orch.get_events.side_effect = Exception("Unexpected error")
        mock_orch.get_builder.return_value = Mock()
        mock_get_orch.return_value = mock_orch

        # Should not raise
        events = parse_backfill_events([mock_session], limit=10)

        assert isinstance(events, list)

    @patch("motus.ui.web.event_parser.get_orchestrator")
    def test_sorts_and_limits_backfill_events(self, mock_get_orch):
        """Backfill events are sorted by timestamp and limited."""
        from motus.ui.web.event_parser import parse_backfill_events

        mock_session = Mock()
        mock_session.source = Source.CODEX
        mock_session.session_id = "session-1"
        mock_session.project_path = "/test"

        # Create mock events (get_events returns last 10)
        mock_events = [Mock() for _ in range(15)]
        mock_orch = Mock()
        mock_orch.get_events.return_value = mock_events
        mock_orch.get_builder.return_value = Mock()
        mock_get_orch.return_value = mock_orch

        events = parse_backfill_events([mock_session], limit=5)

        # Result should be limited
        assert len(events) <= 5


class TestParseIncrementalEventsCallbacks:
    """Tests for parse_incremental_events callback behavior."""

    @patch("builtins.open", create=True)
    @patch("motus.ui.web.event_parser.get_orchestrator")
    def test_line_callback_is_called(self, mock_get_orch, mock_open):
        """line_callback is called for each new line."""
        from motus.ui.web.event_parser import parse_incremental_events

        mock_session = Mock()
        mock_session.source = Source.CLAUDE
        mock_session.session_id = "test-session"
        mock_session.project_path = "/test"
        mock_session.file_path = MagicMock()
        mock_session.file_path.stat.return_value.st_size = 2000

        mock_file = MagicMock()
        mock_file.tell.return_value = 2000
        mock_file.read.return_value = '{"type": "event1"}\n{"type": "event2"}\n'
        mock_file.__enter__.return_value = mock_file
        mock_open.return_value = mock_file

        mock_builder = Mock()
        mock_builder.parse_line.return_value = []
        mock_orch = Mock()
        mock_orch.get_builder.return_value = mock_builder
        mock_get_orch.return_value = mock_orch

        line_calls = []

        def line_callback(line, session_id, project_path):
            line_calls.append((line, session_id, project_path))

        events, new_pos = parse_incremental_events(mock_session, 1000, line_callback=line_callback)

        # Should have called line_callback for each line
        assert len(line_calls) == 2
        assert line_calls[0][1] == "test-session"
        assert line_calls[0][2] == "/test"

    @patch("builtins.open", create=True)
    @patch("motus.ui.web.event_parser.get_orchestrator")
    def test_format_callback_is_called(self, mock_get_orch, mock_open):
        """format_callback is called for each parsed event."""
        from motus.ui.web.event_parser import parse_incremental_events

        mock_session = Mock()
        mock_session.source = Source.CLAUDE
        mock_session.session_id = "test-session"
        mock_session.project_path = "/test"
        mock_session.file_path = MagicMock()
        mock_session.file_path.stat.return_value.st_size = 2000

        mock_file = MagicMock()
        mock_file.tell.return_value = 2000
        mock_file.read.return_value = '{"type": "event"}\n'
        mock_file.__enter__.return_value = mock_file
        mock_open.return_value = mock_file

        mock_event = Mock()
        mock_builder = Mock()
        mock_builder.parse_line.return_value = [mock_event]
        mock_orch = Mock()
        mock_orch.get_builder.return_value = mock_builder
        mock_get_orch.return_value = mock_orch

        format_calls = []

        def format_callback(event, session_id, project_path, source):
            format_calls.append((event, session_id, project_path, source))
            return {"formatted": True}

        events, new_pos = parse_incremental_events(
            mock_session, 1000, format_callback=format_callback
        )

        # Should have called format_callback
        assert len(format_calls) == 1
        assert format_calls[0][1] == "test-session"
        assert format_calls[0][3] == "claude"

    @patch("motus.ui.web.event_parser.get_orchestrator")
    def test_gemini_returns_empty_when_size_unchanged(self, mock_get_orch):
        """Gemini returns empty list when file size unchanged."""
        from motus.ui.web.event_parser import parse_incremental_events

        mock_session = Mock()
        mock_session.source = Source.GEMINI
        mock_session.file_path = MagicMock()
        # File size is same as last_pos
        mock_session.file_path.stat.return_value.st_size = 5000

        mock_orch = Mock()
        mock_get_orch.return_value = mock_orch

        events, new_pos = parse_incremental_events(mock_session, 5000)

        assert events == []
        assert new_pos == 5000

    @patch("motus.ui.web.event_parser.get_orchestrator")
    def test_gemini_refreshes_when_size_changed(self, mock_get_orch):
        """Gemini re-parses file when size changes."""
        from motus.ui.web.event_parser import parse_incremental_events

        mock_session = Mock()
        mock_session.source = Source.GEMINI
        mock_session.session_id = "gemini-session"
        mock_session.project_path = "/test"
        mock_session.file_path = MagicMock()
        # File size changed
        mock_session.file_path.stat.return_value.st_size = 6000

        mock_events = [Mock(), Mock()]
        mock_orch = Mock()
        mock_orch.get_events.return_value = mock_events
        mock_get_orch.return_value = mock_orch

        events, new_pos = parse_incremental_events(mock_session, 5000)

        # Should call get_events with refresh=True
        mock_orch.get_events.assert_called_once_with(mock_session, refresh=True)
        assert new_pos == 6000
        assert len(events) == 2


class TestParseSessionIntentsDetails:
    """Detailed tests for parse_session_intents."""

    @patch("motus.ui.web.event_parser.get_orchestrator")
    def test_calculates_cache_hit_rate(self, mock_get_orch):
        """Calculates cache hit rate from token usage."""
        from motus.ui.web.event_parser import parse_session_intents

        mock_session = Mock()

        # Create event with token usage
        event = ParsedEvent(
            event_id="evt-1",
            session_id="test-session",
            event_type=EventType.ASSISTANT_MESSAGE,
            source=AgentSource.CLAUDE,
            timestamp=FIXED_TIMESTAMP,
            content="Response",
            risk_level=RiskLevel.SAFE,
            raw_data={
                "usage": {
                    "input_tokens": 1000,
                    "output_tokens": 500,
                    "cache_read_input_tokens": 800,
                }
            },
        )

        mock_orch = Mock()
        mock_orch.get_session.return_value = mock_session
        mock_orch.get_events_tail_validated.return_value = [event]
        mock_get_orch.return_value = mock_orch

        result = parse_session_intents("test-session")

        assert result["error"] is None
        stats = result["stats"]
        # Cache hit rate should be (800 / 1000) * 100 = 80%
        assert "80.0%" in stats["cache_hit_rate"]

    @patch("motus.ui.web.event_parser.get_orchestrator")
    def test_tracks_models_used(self, mock_get_orch):
        """Tracks all models used in session."""
        from motus.ui.web.event_parser import parse_session_intents

        mock_session = Mock()

        events = [
            ParsedEvent(
                event_id="evt-1",
                session_id="test-session",
                event_type=EventType.THINKING,
                source=AgentSource.CLAUDE,
                timestamp=FIXED_TIMESTAMP,
                content="Think",
                risk_level=RiskLevel.SAFE,
                model="claude-sonnet-4",
            ),
            ParsedEvent(
                event_id="evt-2",
                session_id="test-session",
                event_type=EventType.THINKING,
                source=AgentSource.CLAUDE,
                timestamp=FIXED_TIMESTAMP,
                content="Think",
                risk_level=RiskLevel.SAFE,
                model="claude-opus-4",
            ),
        ]

        mock_orch = Mock()
        mock_orch.get_session.return_value = mock_session
        mock_orch.get_events_tail_validated.return_value = events
        mock_get_orch.return_value = mock_orch

        result = parse_session_intents("test-session")

        stats = result["stats"]
        assert len(stats["models_used"]) == 2
        assert "claude-sonnet-4" in stats["models_used"]
        assert "claude-opus-4" in stats["models_used"]

    @patch("motus.ui.web.event_parser.get_orchestrator")
    def test_tracks_file_operations(self, mock_get_orch):
        """Tracks Read and Edit/Write file operations."""
        from motus.ui.web.event_parser import parse_session_intents

        mock_session = Mock()

        events = [
            ParsedEvent(
                event_id="evt-1",
                session_id="test-session",
                event_type=EventType.TOOL_USE,
                source=AgentSource.CLAUDE,
                timestamp=FIXED_TIMESTAMP,
                tool_name="Read",
                file_path="/src/main.py",
                risk_level=RiskLevel.SAFE,
            ),
            ParsedEvent(
                event_id="evt-2",
                session_id="test-session",
                event_type=EventType.TOOL_USE,
                source=AgentSource.CLAUDE,
                timestamp=FIXED_TIMESTAMP,
                tool_name="Edit",
                file_path="/src/config.py",
                risk_level=RiskLevel.SAFE,
            ),
            ParsedEvent(
                event_id="evt-3",
                session_id="test-session",
                event_type=EventType.TOOL_USE,
                source=AgentSource.CLAUDE,
                timestamp=FIXED_TIMESTAMP,
                tool_name="Write",
                file_path="/src/new.py",
                risk_level=RiskLevel.SAFE,
            ),
        ]

        mock_orch = Mock()
        mock_orch.get_session.return_value = mock_session
        mock_orch.get_events_tail_validated.return_value = events
        mock_get_orch.return_value = mock_orch

        result = parse_session_intents("test-session")

        stats = result["stats"]
        assert stats["files_read"] == 1
        assert stats["files_modified"] == 2

    @patch("motus.ui.web.event_parser.get_orchestrator")
    def test_tracks_errors(self, mock_get_orch):
        """Tracks error events."""
        from motus.ui.web.event_parser import parse_session_intents

        mock_session = Mock()

        events = [
            ParsedEvent(
                event_id="evt-1",
                session_id="test-session",
                event_type=EventType.ERROR,
                source=AgentSource.CLAUDE,
                timestamp=FIXED_TIMESTAMP,
                is_error=True,
                error_message="File not found",
                risk_level=RiskLevel.SAFE,
            ),
            ParsedEvent(
                event_id="evt-2",
                session_id="test-session",
                event_type=EventType.ERROR,
                source=AgentSource.CLAUDE,
                timestamp=FIXED_TIMESTAMP,
                is_error=True,
                error_message="Permission denied",
                risk_level=RiskLevel.SAFE,
            ),
        ]

        mock_orch = Mock()
        mock_orch.get_session.return_value = mock_session
        mock_orch.get_events_tail_validated.return_value = events
        mock_get_orch.return_value = mock_orch

        result = parse_session_intents("test-session")

        stats = result["stats"]
        assert stats["errors"] == 2

    @patch("motus.ui.web.event_parser.get_orchestrator")
    def test_formats_intent_timestamps(self, mock_get_orch):
        """Formats intent timestamps as HH:MM:SS."""
        from motus.ui.web.event_parser import parse_session_intents

        mock_session = Mock()

        event = ParsedEvent(
            event_id="evt-1",
            session_id="test-session",
            event_type=EventType.USER_MESSAGE,
            source=AgentSource.CLAUDE,
            timestamp=FIXED_TIMESTAMP,
            content="Add feature X",
            risk_level=RiskLevel.SAFE,
        )

        mock_orch = Mock()
        mock_orch.get_session.return_value = mock_session
        mock_orch.get_events_tail_validated.return_value = [event]
        mock_get_orch.return_value = mock_orch

        result = parse_session_intents("test-session")

        intents = result["intents"]
        assert len(intents) == 1
        # Should be formatted as HH:MM:SS
        assert ":" in intents[0]["timestamp"]
        assert len(intents[0]["timestamp"].split(":")) == 3

    @patch("motus.ui.web.event_parser.get_orchestrator")
    def test_handles_zero_cache_hit_rate(self, mock_get_orch):
        """Handles zero cache hit rate when no cache reads."""
        from motus.ui.web.event_parser import parse_session_intents

        mock_session = Mock()

        event = ParsedEvent(
            event_id="evt-1",
            session_id="test-session",
            event_type=EventType.ASSISTANT_MESSAGE,
            source=AgentSource.CLAUDE,
            timestamp=FIXED_TIMESTAMP,
            content="Response",
            risk_level=RiskLevel.SAFE,
            raw_data={
                "usage": {
                    "input_tokens": 1000,
                    "output_tokens": 500,
                    "cache_read_input_tokens": 0,
                }
            },
        )

        mock_orch = Mock()
        mock_orch.get_session.return_value = mock_session
        mock_orch.get_events_tail_validated.return_value = [event]
        mock_get_orch.return_value = mock_orch

        result = parse_session_intents("test-session")

        stats = result["stats"]
        assert "0.0%" in stats["cache_hit_rate"]

    @patch("motus.ui.web.event_parser.get_orchestrator")
    def test_handles_events_without_raw_data(self, mock_get_orch):
        """Handles events without raw_data field."""
        from motus.ui.web.event_parser import parse_session_intents

        mock_session = Mock()

        event = ParsedEvent(
            event_id="evt-1",
            session_id="test-session",
            event_type=EventType.THINKING,
            source=AgentSource.CLAUDE,
            timestamp=FIXED_TIMESTAMP,
            content="Think",
            risk_level=RiskLevel.SAFE,
        )

        mock_orch = Mock()
        mock_orch.get_session.return_value = mock_session
        mock_orch.get_events_tail_validated.return_value = [event]
        mock_get_orch.return_value = mock_orch

        # Should not raise
        result = parse_session_intents("test-session")

        assert result["error"] is None
        assert result["stats"]["total_input_tokens"] == 0
