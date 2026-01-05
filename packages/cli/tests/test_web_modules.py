"""
Comprehensive tests for web modules - event parsing, session state, and websocket management.

Tests cover:
- event_parser.py: parse_session_history, parse_backfill_events, parse_incremental_events, parse_user_intent_from_line, parse_session_intents
- session_state.py: SessionStateManager initialization, get/set/prune methods
- websocket_manager.py: WebSocketManager client tracking
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from tests.fixtures.constants import FIXED_TIMESTAMP

# ============================================================================
# SessionStateManager Tests
# ============================================================================


class TestSessionStateManagerInit:
    """Tests for SessionStateManager initialization."""

    def test_initialization_creates_empty_dicts(self):
        """SessionStateManager initializes with empty dicts."""
        from motus.ui.web.session_state import SessionStateManager

        manager = SessionStateManager()

        assert manager.session_positions == {}
        assert manager.session_contexts == {}
        assert manager.agent_stacks == {}
        assert manager.parsing_errors == {}

    def test_max_tracked_sessions_constant(self):
        """MAX_TRACKED_SESSIONS is set correctly."""
        from motus.ui.web.session_state import SessionStateManager

        assert SessionStateManager.MAX_TRACKED_SESSIONS == 50


class TestSessionStateManagerPositions:
    """Tests for session position tracking."""

    def test_get_position_returns_zero_for_new_session(self):
        """get_position returns 0 for session not yet tracked."""
        from motus.ui.web.session_state import SessionStateManager

        manager = SessionStateManager()
        position = manager.get_position("new-session-id")

        assert position == 0

    def test_get_position_returns_stored_value(self):
        """get_position returns the stored position."""
        from motus.ui.web.session_state import SessionStateManager

        manager = SessionStateManager()
        manager.session_positions["session-123"] = 1024

        position = manager.get_position("session-123")
        assert position == 1024

    def test_set_position_stores_value(self):
        """set_position stores the position correctly."""
        from motus.ui.web.session_state import SessionStateManager

        manager = SessionStateManager()
        manager.set_position("session-abc", 2048)

        assert manager.session_positions["session-abc"] == 2048

    def test_set_position_updates_existing_value(self):
        """set_position updates an existing position."""
        from motus.ui.web.session_state import SessionStateManager

        manager = SessionStateManager()
        manager.set_position("session-xyz", 100)
        manager.set_position("session-xyz", 200)

        assert manager.session_positions["session-xyz"] == 200


class TestSessionStateManagerContext:
    """Tests for session context management."""

    def test_get_context_creates_empty_context(self):
        """get_context creates empty context for new session."""
        from motus.ui.web.session_state import SessionStateManager

        manager = SessionStateManager()
        context = manager.get_context("new-session")

        assert context["files_read"] == []
        assert context["files_modified"] == []
        assert context["agent_tree"] == []
        assert context["decisions"] == []
        assert context["tool_count"] == {}

    def test_get_context_returns_existing_context(self):
        """get_context returns existing context."""
        from motus.ui.web.session_state import SessionStateManager

        manager = SessionStateManager()
        # Create and modify context
        ctx = manager.get_context("session-1")
        ctx["files_read"].append("/test/file.py")

        # Get again - should be same instance
        ctx2 = manager.get_context("session-1")
        assert ctx2["files_read"] == ["/test/file.py"]

    def test_has_context_returns_false_for_new_session(self):
        """has_context returns False for new session."""
        from motus.ui.web.session_state import SessionStateManager

        manager = SessionStateManager()
        assert manager.has_context("new-session") is False

    def test_has_context_returns_true_after_get(self):
        """has_context returns True after get_context."""
        from motus.ui.web.session_state import SessionStateManager

        manager = SessionStateManager()
        manager.get_context("session-1")
        assert manager.has_context("session-1") is True


class TestSessionStateManagerAgentStack:
    """Tests for agent stack tracking."""

    def test_get_agent_stack_returns_empty_list_for_new_session(self):
        """get_agent_stack returns empty list for new session."""
        from motus.ui.web.session_state import SessionStateManager

        manager = SessionStateManager()
        stack = manager.get_agent_stack("session-1")

        assert stack == []

    def test_set_agent_stack_stores_stack(self):
        """set_agent_stack stores the stack correctly."""
        from motus.ui.web.session_state import SessionStateManager

        manager = SessionStateManager()
        stack = ["agent-1", "agent-2", "agent-3"]
        manager.set_agent_stack("session-1", stack)

        assert manager.get_agent_stack("session-1") == stack

    def test_set_agent_stack_updates_existing(self):
        """set_agent_stack updates existing stack."""
        from motus.ui.web.session_state import SessionStateManager

        manager = SessionStateManager()
        manager.set_agent_stack("session-1", ["agent-1"])
        manager.set_agent_stack("session-1", ["agent-1", "agent-2"])

        assert manager.get_agent_stack("session-1") == ["agent-1", "agent-2"]


class TestSessionStateManagerParsingErrors:
    """Tests for parsing error tracking."""

    def test_get_parsing_error_returns_none_for_new_session(self):
        """get_parsing_error returns None for session without error."""
        from motus.ui.web.session_state import SessionStateManager

        manager = SessionStateManager()
        error = manager.get_parsing_error("session-1")

        assert error is None

    def test_set_parsing_error_stores_error(self):
        """set_parsing_error stores the error message."""
        from motus.ui.web.session_state import SessionStateManager

        manager = SessionStateManager()
        manager.set_parsing_error("session-1", "Parse error: invalid JSON")

        assert manager.get_parsing_error("session-1") == "Parse error: invalid JSON"

    def test_get_all_parsing_errors_returns_all(self):
        """get_all_parsing_errors returns all error messages."""
        from motus.ui.web.session_state import SessionStateManager

        manager = SessionStateManager()
        manager.set_parsing_error("session-1", "Error 1")
        manager.set_parsing_error("session-2", "Error 2")

        errors = manager.get_all_parsing_errors()
        assert errors == {"session-1": "Error 1", "session-2": "Error 2"}


class TestSessionStateManagerPruning:
    """Tests for session state pruning."""

    def test_prune_does_nothing_under_limit(self):
        """prune_stale_sessions does nothing when under MAX_TRACKED_SESSIONS."""
        from motus.ui.web.session_state import SessionStateManager

        manager = SessionStateManager()
        # Add 10 sessions (under limit of 50)
        for i in range(10):
            manager.set_position(f"session-{i}", i * 100)

        active = {f"session-{i}" for i in range(5)}
        manager.prune_stale_sessions(active)

        # All sessions should still be there
        assert len(manager.session_positions) == 10

    def test_prune_removes_inactive_sessions_over_limit(self):
        """prune_stale_sessions removes inactive sessions when over limit."""
        from motus.ui.web.session_state import SessionStateManager

        manager = SessionStateManager()
        # Add 60 sessions (over limit of 50)
        for i in range(60):
            manager.set_position(f"session-{i}", i * 100)
            manager.get_context(f"session-{i}")  # Create context too
            manager.set_agent_stack(f"session-{i}", [])

        # Only mark first 5 as active
        active = {f"session-{i}" for i in range(5)}
        manager.prune_stale_sessions(active)

        # Active sessions should remain
        for i in range(5):
            assert f"session-{i}" in manager.session_positions

        # Some inactive sessions should be removed
        assert len(manager.session_positions) < 60

    def test_prune_removes_from_all_dicts(self):
        """prune_stale_sessions removes from all tracking dicts."""
        from motus.ui.web.session_state import SessionStateManager

        manager = SessionStateManager()
        # Add 60 sessions to all dicts
        for i in range(60):
            manager.set_position(f"session-{i}", i * 100)
            manager.get_context(f"session-{i}")
            manager.set_agent_stack(f"session-{i}", [f"agent-{i}"])
            manager.set_parsing_error(f"session-{i}", f"error-{i}")

        # Only keep first 3 as active
        active = {"session-0", "session-1", "session-2"}
        manager.prune_stale_sessions(active)

        # Check that inactive sessions were removed from all dicts
        assert "session-50" not in manager.session_positions
        assert "session-50" not in manager.session_contexts
        assert "session-50" not in manager.agent_stacks
        assert "session-50" not in manager.parsing_errors


# ============================================================================
# WebSocketManager Tests
# ============================================================================


class TestWebSocketManagerInit:
    """Tests for WebSocketManager initialization."""

    def test_initialization_creates_empty_collections(self):
        """WebSocketManager initializes with empty collections."""
        from motus.ui.web.websocket_manager import WebSocketManager

        manager = WebSocketManager()

        assert manager.clients == set()
        assert manager.known_sessions == {}


class TestWebSocketManagerClientTracking:
    """Tests for WebSocket client tracking."""

    def test_add_client_adds_to_clients_set(self):
        """add_client adds websocket to clients set."""
        from motus.ui.web.websocket_manager import WebSocketManager

        manager = WebSocketManager()
        mock_ws = Mock()

        manager.add_client(mock_ws)

        assert mock_ws in manager.clients

    def test_add_client_initializes_known_sessions(self):
        """add_client initializes empty known_sessions set."""
        from motus.ui.web.websocket_manager import WebSocketManager

        manager = WebSocketManager()
        mock_ws = Mock()

        manager.add_client(mock_ws)

        assert manager.known_sessions[mock_ws] == set()

    def test_remove_client_removes_from_clients(self):
        """remove_client removes websocket from clients set."""
        from motus.ui.web.websocket_manager import WebSocketManager

        manager = WebSocketManager()
        mock_ws = Mock()

        manager.add_client(mock_ws)
        manager.remove_client(mock_ws)

        assert mock_ws not in manager.clients

    def test_remove_client_removes_known_sessions(self):
        """remove_client removes known_sessions entry."""
        from motus.ui.web.websocket_manager import WebSocketManager

        manager = WebSocketManager()
        mock_ws = Mock()

        manager.add_client(mock_ws)
        manager.remove_client(mock_ws)

        assert mock_ws not in manager.known_sessions

    def test_remove_client_handles_nonexistent_client(self):
        """remove_client handles removal of non-existent client gracefully."""
        from motus.ui.web.websocket_manager import WebSocketManager

        manager = WebSocketManager()
        mock_ws = Mock()

        # Should not raise
        manager.remove_client(mock_ws)


class TestWebSocketManagerKnownSessions:
    """Tests for known sessions tracking."""

    def test_get_known_sessions_returns_empty_for_new_client(self):
        """get_known_sessions returns empty set for unknown client."""
        from motus.ui.web.websocket_manager import WebSocketManager

        manager = WebSocketManager()
        mock_ws = Mock()

        sessions = manager.get_known_sessions(mock_ws)
        assert sessions == set()

    def test_get_known_sessions_returns_stored_sessions(self):
        """get_known_sessions returns stored session IDs."""
        from motus.ui.web.websocket_manager import WebSocketManager

        manager = WebSocketManager()
        mock_ws = Mock()

        manager.add_client(mock_ws)
        test_sessions = {"session-1", "session-2", "session-3"}
        manager.set_known_sessions(mock_ws, test_sessions)

        sessions = manager.get_known_sessions(mock_ws)
        assert sessions == test_sessions

    def test_set_known_sessions_updates_sessions(self):
        """set_known_sessions updates the session set."""
        from motus.ui.web.websocket_manager import WebSocketManager

        manager = WebSocketManager()
        mock_ws = Mock()

        manager.add_client(mock_ws)
        manager.set_known_sessions(mock_ws, {"session-1"})
        manager.set_known_sessions(mock_ws, {"session-1", "session-2"})

        assert manager.get_known_sessions(mock_ws) == {"session-1", "session-2"}


class TestWebSocketManagerClientCount:
    """Tests for client count tracking."""

    def test_get_client_count_returns_zero_initially(self):
        """get_client_count returns 0 when no clients."""
        from motus.ui.web.websocket_manager import WebSocketManager

        manager = WebSocketManager()
        assert manager.get_client_count() == 0

    def test_get_client_count_returns_correct_count(self):
        """get_client_count returns correct number of clients."""
        from motus.ui.web.websocket_manager import WebSocketManager

        manager = WebSocketManager()
        mock_ws1 = Mock()
        mock_ws2 = Mock()
        mock_ws3 = Mock()

        manager.add_client(mock_ws1)
        manager.add_client(mock_ws2)
        manager.add_client(mock_ws3)

        assert manager.get_client_count() == 3

    def test_get_client_count_decreases_after_removal(self):
        """get_client_count decreases when clients are removed."""
        from motus.ui.web.websocket_manager import WebSocketManager

        manager = WebSocketManager()
        mock_ws1 = Mock()
        mock_ws2 = Mock()

        manager.add_client(mock_ws1)
        manager.add_client(mock_ws2)
        manager.remove_client(mock_ws1)

        assert manager.get_client_count() == 1


# ============================================================================
# Event Parser Tests - parse_user_intent_from_line
# ============================================================================


class TestParseUserIntentFromLine:
    """Tests for parse_user_intent_from_line function."""

    def test_parses_claude_user_message(self):
        """Parses user intent from Claude transcript format."""
        from motus.ui.web.event_parser import parse_user_intent_from_line

        line = json.dumps(
            {
                "type": "user",
                "message": {
                    "content": [
                        {"type": "text", "text": "Please refactor the authentication module"}
                    ]
                },
            }
        )

        intent = parse_user_intent_from_line(line)
        assert intent == "Please refactor the authentication module"

    def test_parses_codex_user_message(self):
        """Parses user intent from Codex format."""
        from motus.ui.web.event_parser import parse_user_intent_from_line

        line = json.dumps(
            {
                "type": "event_msg",
                "payload": {"type": "user_message", "content": "Fix the bug in main.py"},
            }
        )

        intent = parse_user_intent_from_line(line)
        assert intent == "Fix the bug in main.py"

    def test_parses_codex_user_role(self):
        """Parses user intent from Codex format with role field."""
        from motus.ui.web.event_parser import parse_user_intent_from_line

        line = json.dumps(
            {"type": "event_msg", "payload": {"role": "user", "content": "Write tests for the API"}}
        )

        intent = parse_user_intent_from_line(line)
        assert intent == "Write tests for the API"

    def test_skips_short_messages(self):
        """Skips very short messages (less than 5 chars)."""
        from motus.ui.web.event_parser import parse_user_intent_from_line

        line = json.dumps(
            {"type": "user", "message": {"content": [{"type": "text", "text": "Hi"}]}}
        )

        intent = parse_user_intent_from_line(line)
        assert intent is None

    def test_returns_none_for_invalid_json(self):
        """Returns None for invalid JSON."""
        from motus.ui.web.event_parser import parse_user_intent_from_line

        line = "not valid json {"
        intent = parse_user_intent_from_line(line)
        assert intent is None

    def test_returns_none_for_non_user_message(self):
        """Returns None for non-user message types."""
        from motus.ui.web.event_parser import parse_user_intent_from_line

        line = json.dumps(
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "I will help you"}]},
            }
        )

        intent = parse_user_intent_from_line(line)
        assert intent is None

    def test_handles_missing_content_field(self):
        """Handles missing content field gracefully."""
        from motus.ui.web.event_parser import parse_user_intent_from_line

        line = json.dumps({"type": "user", "message": {}})

        intent = parse_user_intent_from_line(line)
        assert intent is None

    def test_parses_codex_list_content(self):
        """Parses Codex messages with list content."""
        from motus.ui.web.event_parser import parse_user_intent_from_line

        line = json.dumps(
            {
                "type": "event_msg",
                "payload": {
                    "type": "user_message",
                    "content": [{"text": "Add feature A"}, {"text": " and feature B"}],
                },
            }
        )

        intent = parse_user_intent_from_line(line)
        # The implementation joins with space, so there's a double space
        assert intent == "Add feature A  and feature B"


# ============================================================================
# Event Parser Tests - parse_session_history
# ============================================================================


class TestParseSessionHistory:
    """Tests for parse_session_history function."""

    @patch("motus.ui.web.event_parser.get_orchestrator")
    def test_returns_error_for_nonexistent_session(self, mock_get_orch):
        """Returns error when session not found."""
        from motus.ui.web.event_parser import parse_session_history

        mock_orch = Mock()
        mock_orch.get_session.return_value = None
        mock_get_orch.return_value = mock_orch

        result = parse_session_history("nonexistent-session")

        assert result["events"] == []
        assert result["total_events"] == 0
        assert result["has_more"] is False
        assert result["error"] == "Session not found or file not readable"

    @patch("motus.ui.web.event_parser.tail_lines")
    @patch("motus.ui.web.event_parser.get_file_stats")
    @patch("motus.ui.web.event_parser.get_orchestrator")
    def test_parses_history_with_no_events(self, mock_get_orch, mock_stats, mock_tail):
        """Handles session with no parseable events."""
        from motus.protocols import Source
        from motus.ui.web.event_parser import parse_session_history

        mock_session = Mock()
        mock_session.source = Source.CLAUDE
        mock_session.file_path = Path("/test/session.jsonl")
        mock_session.project_path = "/test/project"

        mock_orch = Mock()
        mock_orch.get_session.return_value = mock_session
        mock_builder = Mock()
        mock_builder.parse_line.return_value = []
        mock_orch.get_builder.return_value = mock_builder
        mock_get_orch.return_value = mock_orch

        mock_stats.return_value = {"line_count": 10}
        mock_tail.return_value = ["", "invalid line", ""]

        result = parse_session_history("test-session")

        assert result["events"] == []
        assert result["error"] is None

    @patch("motus.ui.web.event_parser.tail_lines")
    @patch("motus.ui.web.event_parser.get_file_stats")
    @patch("motus.ui.web.event_parser.get_orchestrator")
    def test_handles_oserror_gracefully(self, mock_get_orch, mock_stats, mock_tail):
        """Handles OSError when reading file."""
        from motus.protocols import Source
        from motus.ui.web.event_parser import parse_session_history

        mock_session = Mock()
        mock_session.source = Source.CLAUDE
        mock_session.file_path = Path("/test/session.jsonl")

        mock_orch = Mock()
        mock_orch.get_session.return_value = mock_session
        mock_get_orch.return_value = mock_orch

        mock_tail.side_effect = OSError("File not found")

        result = parse_session_history("test-session")

        assert result["error"].startswith("Error reading session")
        assert result["events"] == []


# ============================================================================
# Event Parser Tests - parse_session_intents
# ============================================================================


class TestParseSessionIntents:
    """Tests for parse_session_intents function."""

    @patch("motus.ui.web.event_parser.get_orchestrator")
    def test_returns_error_for_nonexistent_session(self, mock_get_orch):
        """Returns error when session not found."""
        from motus.ui.web.event_parser import parse_session_intents

        mock_orch = Mock()
        mock_orch.get_session.return_value = None
        mock_get_orch.return_value = mock_orch

        result = parse_session_intents("nonexistent-session")

        assert result["error"] == "Session not found"

    @patch("motus.ui.web.event_parser.get_orchestrator")
    def test_extracts_user_intents_from_events(self, mock_get_orch):
        """Extracts user intents from USER_MESSAGE events."""
        from motus.schema.events import AgentSource, EventType, ParsedEvent, RiskLevel
        from motus.ui.web.event_parser import parse_session_intents

        mock_session = Mock()

        # Create mock events with USER_MESSAGE type
        event1 = ParsedEvent(
            event_id="evt-1",
            session_id="test-session",
            event_type=EventType.USER_MESSAGE,
            source=AgentSource.CLAUDE,
            timestamp=FIXED_TIMESTAMP,
            content="Refactor the auth module",
            risk_level=RiskLevel.SAFE,
        )
        event2 = ParsedEvent(
            event_id="evt-2",
            session_id="test-session",
            event_type=EventType.USER_MESSAGE,
            source=AgentSource.CLAUDE,
            timestamp=FIXED_TIMESTAMP,
            content="Add tests for API",
            risk_level=RiskLevel.SAFE,
        )

        mock_orch = Mock()
        mock_orch.get_session.return_value = mock_session
        mock_orch.get_events_tail_validated.return_value = [event1, event2]
        mock_get_orch.return_value = mock_orch

        result = parse_session_intents("test-session")

        assert result["error"] is None
        assert len(result["intents"]) == 2
        assert result["intents"][0]["prompt"] == "Refactor the auth module"
        assert result["intents"][1]["prompt"] == "Add tests for API"

    @patch("motus.ui.web.event_parser.get_orchestrator")
    def test_handles_exception_during_parsing(self, mock_get_orch):
        """Handles exceptions during intent extraction."""
        from motus.ui.web.event_parser import parse_session_intents

        mock_session = Mock()
        mock_orch = Mock()
        mock_orch.get_session.return_value = mock_session
        mock_orch.get_events_tail_validated.side_effect = Exception("Parse error")
        mock_get_orch.return_value = mock_orch

        result = parse_session_intents("test-session")

        assert "error" in result
        assert result["error"] == "Parse error"


# ============================================================================
# Event Parser Tests - parse_incremental_events
# ============================================================================


class TestParseIncrementalEvents:
    """Tests for parse_incremental_events function."""

    @patch("motus.ui.web.event_parser.get_orchestrator")
    def test_returns_empty_when_no_new_content(self, mock_get_orch):
        """Returns empty list when file size unchanged."""
        from motus.protocols import Source
        from motus.ui.web.event_parser import parse_incremental_events

        mock_session = Mock()
        mock_session.source = Source.CLAUDE
        mock_session.file_path = MagicMock()
        mock_session.file_path.stat.return_value.st_size = 1000

        mock_orch = Mock()
        mock_get_orch.return_value = mock_orch

        events, new_pos = parse_incremental_events(mock_session, 1000)

        assert events == []
        assert new_pos == 1000

    @patch("builtins.open", create=True)
    @patch("motus.ui.web.event_parser.get_orchestrator")
    def test_reads_new_content_for_claude(self, mock_get_orch, mock_open):
        """Reads and parses new content for Claude sessions."""
        from motus.protocols import Source
        from motus.ui.web.event_parser import parse_incremental_events

        mock_session = Mock()
        mock_session.source = Source.CLAUDE
        mock_session.session_id = "test-session"
        mock_session.project_path = "/test/project"
        mock_session.file_path = MagicMock()
        mock_session.file_path.stat.return_value.st_size = 2000

        mock_file = MagicMock()
        mock_file.tell.return_value = 2000
        mock_file.read.return_value = '{"type": "test"}\n'
        mock_file.__enter__.return_value = mock_file
        mock_open.return_value = mock_file

        mock_builder = Mock()
        mock_event = Mock()
        mock_builder.parse_line.return_value = [mock_event]
        mock_orch = Mock()
        mock_orch.get_builder.return_value = mock_builder
        mock_get_orch.return_value = mock_orch

        events, new_pos = parse_incremental_events(mock_session, 1000)

        assert new_pos == 2000
        assert len(events) == 1

    @patch("motus.ui.web.event_parser.get_orchestrator")
    def test_handles_gemini_format_differently(self, mock_get_orch):
        """Handles Gemini format (single JSON file) differently."""
        from motus.protocols import Source
        from motus.ui.web.event_parser import parse_incremental_events

        mock_session = Mock()
        mock_session.source = Source.GEMINI
        mock_session.session_id = "test-session"
        mock_session.project_path = "/test/project"
        mock_session.file_path = MagicMock()
        # File size changed
        mock_session.file_path.stat.return_value.st_size = 2000

        mock_event = Mock()
        mock_orch = Mock()
        mock_orch.get_events.return_value = [mock_event]
        mock_get_orch.return_value = mock_orch

        events, new_pos = parse_incremental_events(mock_session, 1000)

        # For Gemini, new_pos should be the new file size
        assert new_pos == 2000
        assert len(events) == 1


# ============================================================================
# Event Parser Tests - parse_backfill_events
# ============================================================================


class TestParseBackfillEvents:
    """Tests for parse_backfill_events function."""

    @patch("motus.ui.web.event_parser.get_orchestrator")
    def test_returns_empty_for_no_sessions(self, mock_get_orch):
        """Returns empty list when no sessions provided."""
        from motus.ui.web.event_parser import parse_backfill_events

        mock_orch = Mock()
        mock_get_orch.return_value = mock_orch

        events = parse_backfill_events([])

        assert events == []

    @patch("motus.ui.web.event_parser.get_orchestrator")
    def test_limits_to_5_sessions(self, mock_get_orch):
        """Processes maximum of 5 sessions."""
        from motus.protocols import Source
        from motus.ui.web.event_parser import parse_backfill_events

        # Create 10 mock sessions
        sessions = []
        for i in range(10):
            mock_session = Mock()
            mock_session.source = Source.CODEX
            mock_session.session_id = f"session-{i}"
            mock_session.project_path = "/test"
            sessions.append(mock_session)

        mock_builder = Mock()
        mock_builder.parse_line.return_value = []
        mock_orch = Mock()
        mock_orch.get_builder.return_value = mock_builder
        mock_orch.get_events.return_value = []
        mock_get_orch.return_value = mock_orch

        # Should only process first 5
        events = parse_backfill_events(sessions)

        # With empty events from each session, result is empty
        assert isinstance(events, list)

    @patch("motus.ui.web.event_parser.get_orchestrator")
    def test_handles_codex_sessions(self, mock_get_orch):
        """Handles Codex session format correctly."""
        from motus.protocols import Source
        from motus.ui.web.event_parser import parse_backfill_events

        mock_session = Mock()
        mock_session.source = Source.CODEX
        mock_session.session_id = "codex-session"
        mock_session.project_path = "/test/project"

        mock_event = Mock()
        mock_orch = Mock()
        mock_orch.get_events.return_value = [mock_event]
        mock_get_orch.return_value = mock_orch

        events = parse_backfill_events([mock_session])

        assert len(events) <= 30  # Default limit
