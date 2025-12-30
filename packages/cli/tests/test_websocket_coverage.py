"""
Comprehensive tests for src/motus/ui/web/websocket.py to increase coverage.

Targets coverage from 28% to 70%+.
Tests focus on:
- WebSocket connection handling
- Message broadcasting
- Error handling paths
- Session management
- Edge cases (disconnects, reconnects)
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from motus.protocols import SessionStatus, Source
from motus.schema.events import AgentSource, EventType, ParsedEvent, RiskLevel
from motus.ui.web.state import SessionState
from motus.ui.web.websocket import WebSocketHandler
from motus.ui.web.websocket_manager import WebSocketManager
from tests.fixtures.constants import FIXED_TIMESTAMP

# Configure pytest-asyncio
pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket connection."""
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    ws.receive_json = AsyncMock()
    ws.close = AsyncMock()
    # Headers must be a regular dict (not AsyncMock) for origin validation
    ws.headers = {"origin": "http://localhost:4000"}
    return ws


@pytest.fixture
def ws_manager():
    """Create a WebSocketManager instance."""
    return WebSocketManager()


@pytest.fixture
def session_state():
    """Create a SessionState instance."""
    return SessionState()


@pytest.fixture
def ws_handler(ws_manager, session_state):
    """Create a WebSocketHandler instance."""
    return WebSocketHandler(ws_manager, session_state)


@pytest.fixture
def mock_session():
    """Create a mock session object."""
    session = Mock()
    session.session_id = "test-session-001"
    session.project_path = "/test/project"
    session.status = SessionStatus.ACTIVE
    session.source = Source.CLAUDE
    session.file_path = Path("/tmp/test.jsonl")
    return session


class TestWebSocketHandlerConnection:
    """Tests for WebSocket connection lifecycle."""

    async def test_handle_connection_accepts_websocket(self, ws_handler, mock_websocket):
        """WebSocket is accepted on connection."""
        from fastapi import WebSocketDisconnect

        with patch("motus.ui.web.websocket.get_orchestrator") as mock_get_orch:
            mock_orch = Mock()
            mock_orch.discover_all.return_value = []
            mock_get_orch.return_value = mock_orch

            # Exit loop immediately after initial send without triggering poll.
            mock_websocket.receive_json.side_effect = WebSocketDisconnect()
            await ws_handler.handle_connection(mock_websocket)

            mock_websocket.accept.assert_called_once()

    async def test_handle_connection_rejects_invalid_origin(self, ws_handler, mock_websocket):
        """WebSocket rejects connections from non-localhost origins."""
        # Set invalid origin
        mock_websocket.headers = {"origin": "http://evil.com"}

        await ws_handler.handle_connection(mock_websocket)

        # Should close without accepting
        mock_websocket.accept.assert_not_called()
        mock_websocket.close.assert_called_once_with(code=1008, reason="Invalid origin")

    async def test_handle_connection_sends_initial_sessions(
        self, ws_handler, mock_websocket, mock_session
    ):
        """Initial session list is sent on connection."""
        from fastapi import WebSocketDisconnect

        with patch("motus.ui.web.websocket.get_orchestrator") as mock_get_orch:
            mock_orch = Mock()
            mock_orch.discover_all.return_value = [mock_session]
            mock_get_orch.return_value = mock_orch

            mock_websocket.receive_json.side_effect = WebSocketDisconnect()
            await ws_handler.handle_connection(mock_websocket)

            # Check that sessions message was sent
            calls = mock_websocket.send_json.call_args_list
            assert any(
                call[0][0].get("type") == "sessions" for call in calls
            ), "No sessions message sent"

    async def test_handle_connection_adds_last_action_for_crashed_session(
        self, ws_handler, mock_websocket
    ):
        """Crashed sessions get last_action added."""
        from fastapi import WebSocketDisconnect

        crashed_session = Mock()
        crashed_session.session_id = "crashed-session"
        crashed_session.project_path = "/test/crashed"
        crashed_session.status = SessionStatus.CRASHED
        crashed_session.source = Source.CLAUDE
        crashed_session.file_path = Path("/tmp/crashed.jsonl")

        with patch("motus.ui.web.websocket.get_orchestrator") as mock_get_orch:
            mock_builder = Mock()
            mock_builder.get_last_action.return_value = "Error: Timeout"

            mock_orch = Mock()
            mock_orch.discover_all.return_value = [crashed_session]
            mock_orch.get_builder.return_value = mock_builder
            mock_get_orch.return_value = mock_orch

            mock_websocket.receive_json.side_effect = WebSocketDisconnect()
            await ws_handler.handle_connection(mock_websocket)

            # Verify get_builder and get_last_action were called
            mock_orch.get_builder.assert_called()
            mock_builder.get_last_action.assert_called_once()

    async def test_handle_connection_removes_client_on_disconnect(self, ws_handler, mock_websocket):
        """Client is removed from manager on disconnect."""
        from fastapi import WebSocketDisconnect

        with patch("motus.ui.web.websocket.get_orchestrator") as mock_get_orch:
            mock_orch = Mock()
            mock_orch.discover_all.return_value = []
            mock_get_orch.return_value = mock_orch

            # Simulate disconnect
            mock_websocket.receive_json.side_effect = WebSocketDisconnect()

            await ws_handler.handle_connection(mock_websocket)

            # Client should be removed
            assert mock_websocket not in ws_handler.ws_manager.clients

    async def test_handle_connection_polls_on_timeout(self, ws_handler, mock_websocket):
        """Poll events is called on receive timeout."""
        with patch("motus.ui.web.websocket.get_orchestrator") as mock_get_orch:
            mock_orch = Mock()
            mock_orch.discover_all.return_value = []
            mock_get_orch.return_value = mock_orch

            # First timeout triggers poll, then disconnect
            call_count = [0]

            def timeout_then_disconnect():
                call_count[0] += 1
                if call_count[0] == 1:
                    raise asyncio.TimeoutError()
                else:
                    from fastapi import WebSocketDisconnect

                    raise WebSocketDisconnect()

            mock_websocket.receive_json.side_effect = timeout_then_disconnect

            with patch.object(ws_handler, "_poll_events", new=AsyncMock()) as mock_poll:
                await ws_handler.handle_connection(mock_websocket)
                # Should have called poll at least once
                assert mock_poll.call_count >= 1


class TestWebSocketHandlerClientMessages:
    """Tests for handling client messages."""

    async def test_handle_select_session_sends_context(self, ws_handler, mock_websocket):
        """select_session sends context if available."""
        session_id = "test-session"
        ws_handler.session_state.session_contexts[session_id] = {
            "files_read": ["main.py"],
            "decisions": ["Starting work"],
        }

        with patch.object(ws_handler, "_send_session_history", new=AsyncMock()):
            with patch.object(ws_handler, "_send_session_intents", new=AsyncMock()):
                await ws_handler._handle_client_message(
                    mock_websocket, {"type": "select_session", "session_id": session_id}
                )

                # Check context was sent
                calls = mock_websocket.send_json.call_args_list
                assert any(
                    call[0][0].get("type") == "context" for call in calls
                ), "No context message sent"

    async def test_handle_select_session_loads_history_and_intents(
        self, ws_handler, mock_websocket
    ):
        """select_session loads history and intents."""
        session_id = "test-session"

        with patch.object(ws_handler, "_send_session_history", new=AsyncMock()) as mock_history:
            with patch.object(ws_handler, "_send_session_intents", new=AsyncMock()) as mock_intents:
                await ws_handler._handle_client_message(
                    mock_websocket, {"type": "select_session", "session_id": session_id}
                )

                mock_history.assert_called_once_with(mock_websocket, session_id)
                mock_intents.assert_called_once_with(mock_websocket, session_id)

    async def test_handle_request_backfill(self, ws_handler, mock_websocket):
        """request_backfill triggers backfill send."""
        with patch.object(ws_handler, "_send_backfill", new=AsyncMock()) as mock_backfill:
            await ws_handler._handle_client_message(
                mock_websocket, {"type": "request_backfill", "limit": 50}
            )

            mock_backfill.assert_called_once_with(mock_websocket, 50)

    async def test_handle_request_intents(self, ws_handler, mock_websocket):
        """request_intents triggers intents send."""
        session_id = "test-session"

        with patch.object(ws_handler, "_send_session_intents", new=AsyncMock()) as mock_intents:
            await ws_handler._handle_client_message(
                mock_websocket, {"type": "request_intents", "session_id": session_id}
            )

            mock_intents.assert_called_once_with(mock_websocket, session_id)

    async def test_handle_load_more(self, ws_handler, mock_websocket):
        """load_more triggers history load with offset."""
        session_id = "test-session"
        offset = 100

        with patch.object(ws_handler, "_send_session_history", new=AsyncMock()) as mock_history:
            await ws_handler._handle_client_message(
                mock_websocket, {"type": "load_more", "session_id": session_id, "offset": offset}
            )

            mock_history.assert_called_once_with(mock_websocket, session_id, offset=offset)

    async def test_handle_heartbeat(self, ws_handler, mock_websocket):
        """heartbeat message is handled without error."""
        await ws_handler._handle_client_message(mock_websocket, {"type": "heartbeat"})
        # Should not raise


class TestWebSocketHandlerSessionHistory:
    """Tests for session history sending."""

    async def test_send_session_history_success(self, ws_handler, mock_websocket):
        """Session history is sent successfully."""
        session_id = "test-session"

        with patch("motus.ui.web.websocket.parse_session_history") as mock_parse:
            mock_parse.return_value = {
                "events": [{"event_id": "1"}],
                "total_events": 100,
                "has_more": True,
                "offset": 0,
                "error": None,
            }

            await ws_handler._send_session_history(mock_websocket, session_id)

            # Verify message sent
            mock_websocket.send_json.assert_called_once()
            call_args = mock_websocket.send_json.call_args[0][0]
            assert call_args["type"] == "session_history"
            assert call_args["session_id"] == session_id
            assert call_args["has_more"] is True

    async def test_send_session_history_error(self, ws_handler, mock_websocket):
        """Session history error is sent to client."""
        session_id = "test-session"

        with patch("motus.ui.web.websocket.parse_session_history") as mock_parse:
            mock_parse.return_value = {
                "events": [],
                "total_events": 0,
                "has_more": False,
                "offset": 0,
                "error": "File not found",
            }

            await ws_handler._send_session_history(mock_websocket, session_id)

            # Verify error message sent
            mock_websocket.send_json.assert_called_once()
            call_args = mock_websocket.send_json.call_args[0][0]
            assert call_args["type"] == "error"
            assert call_args["session_id"] == session_id
            assert "File not found" in call_args["message"]


class TestWebSocketHandlerBackfill:
    """Tests for backfill functionality."""

    async def test_send_backfill(self, ws_handler, mock_websocket, mock_session):
        """Backfill events are sent."""
        with patch("motus.ui.web.websocket.get_orchestrator") as mock_get_orch:
            with patch("motus.ui.web.websocket.parse_backfill_events") as mock_parse:
                mock_orch = Mock()
                mock_orch.discover_all.return_value = [mock_session]
                mock_get_orch.return_value = mock_orch

                mock_parse.return_value = [{"event_id": "1"}, {"event_id": "2"}]

                await ws_handler._send_backfill(mock_websocket, limit=30)

                # Verify backfill message sent
                mock_websocket.send_json.assert_called_once()
                call_args = mock_websocket.send_json.call_args[0][0]
                assert call_args["type"] == "backfill"
                assert len(call_args["events"]) == 2


class TestWebSocketHandlerIntents:
    """Tests for intent extraction and sending."""

    async def test_send_session_intents_success(self, ws_handler, mock_websocket):
        """Session intents are sent successfully."""
        session_id = "test-session"

        with patch("motus.ui.web.websocket.parse_session_intents") as mock_parse:
            mock_parse.return_value = {
                "intents": [{"prompt": "Fix bug", "timestamp": "12:00:00"}],
                "stats": {"total_input_tokens": 1000},
                "error": None,
            }

            await ws_handler._send_session_intents(mock_websocket, session_id)

            # Verify message sent
            mock_websocket.send_json.assert_called_once()
            call_args = mock_websocket.send_json.call_args[0][0]
            assert call_args["type"] == "session_intents"
            assert call_args["session_id"] == session_id
            assert len(call_args["intents"]) == 1

    async def test_send_session_intents_error(self, ws_handler, mock_websocket):
        """Session intents error is logged but not sent."""
        session_id = "test-session"

        with patch("motus.ui.web.websocket.parse_session_intents") as mock_parse:
            mock_parse.return_value = {"error": "Session not found"}

            await ws_handler._send_session_intents(mock_websocket, session_id)

            # Should not send message on error
            mock_websocket.send_json.assert_not_called()


class TestWebSocketHandlerEventPolling:
    """Tests for event polling logic."""

    async def test_poll_events_detects_new_sessions(self, ws_handler, mock_websocket, mock_session):
        """New sessions are detected and sent."""
        # Set initial known sessions
        ws_handler.ws_manager.set_known_sessions(mock_websocket, set())

        # Mock cached sessions with a new session
        ws_handler.session_state._cached_sessions = [mock_session]
        ws_handler.session_state._sessions_cache_time = 9999999999

        with patch("motus.ui.web.websocket.get_orchestrator") as mock_get_orch:
            mock_orch = Mock()
            mock_orch.is_process_degraded.return_value = False
            mock_get_orch.return_value = mock_orch

            await ws_handler._poll_events(mock_websocket)

            # Should send sessions update
            calls = mock_websocket.send_json.call_args_list
            assert any(
                call[0][0].get("type") == "sessions" for call in calls
            ), "No sessions message sent"

    async def test_poll_events_only_polls_active_sessions(self, ws_handler, mock_websocket):
        """Only active/open sessions are polled."""
        active_session = Mock()
        active_session.session_id = "active-session"
        active_session.status = SessionStatus.ACTIVE
        active_session.project_path = "/test"
        active_session.source = Source.CLAUDE
        active_session.file_path = Path("/tmp/active.jsonl")

        idle_session = Mock()
        idle_session.session_id = "idle-session"
        idle_session.status = SessionStatus.IDLE
        idle_session.project_path = "/test"
        idle_session.source = Source.CLAUDE

        ws_handler.session_state._cached_sessions = [active_session, idle_session]
        ws_handler.session_state._sessions_cache_time = 9999999999
        ws_handler.ws_manager.set_known_sessions(
            mock_websocket, {s.session_id for s in [active_session, idle_session]}
        )

        with patch("motus.ui.web.websocket.parse_incremental_events") as mock_parse:
            mock_parse.return_value = ([], 0)

            await ws_handler._poll_events(mock_websocket)

            # Should only parse active session
            assert mock_parse.call_count == 1
            call_session = mock_parse.call_args.kwargs["session"]
            assert call_session.session_id == "active-session"

    async def test_poll_events_handles_oserror(self, ws_handler, mock_websocket, mock_session):
        """OSError during polling is logged and session marked."""
        mock_session.status = SessionStatus.ACTIVE
        ws_handler.session_state._cached_sessions = [mock_session]
        ws_handler.session_state._sessions_cache_time = 9999999999
        ws_handler.ws_manager.set_known_sessions(mock_websocket, {mock_session.session_id})

        with patch("motus.ui.web.websocket.parse_incremental_events") as mock_parse:
            mock_parse.side_effect = OSError("File read error")

            await ws_handler._poll_events(mock_websocket)

            # Should have set error for the session
            error = ws_handler.session_state.get_parsing_error(mock_session.session_id)
            assert error is not None
            assert "File read error" in error

    async def test_poll_events_handles_unexpected_exception(
        self, ws_handler, mock_websocket, mock_session
    ):
        """Unexpected exception during polling is logged."""
        mock_session.status = SessionStatus.ACTIVE
        ws_handler.session_state._cached_sessions = [mock_session]
        ws_handler.session_state._sessions_cache_time = 9999999999
        ws_handler.ws_manager.set_known_sessions(mock_websocket, {mock_session.session_id})

        with patch("motus.ui.web.websocket.parse_incremental_events") as mock_parse:
            mock_parse.side_effect = ValueError("Unexpected error")

            await ws_handler._poll_events(mock_websocket)

            # Should have set error for the session
            error = ws_handler.session_state.get_parsing_error(mock_session.session_id)
            assert error is not None
            assert "Parsing error" in error

    async def test_poll_events_sends_batch_events(self, ws_handler, mock_websocket, mock_session):
        """Batched events are sent in single message."""
        mock_session.status = SessionStatus.ACTIVE
        ws_handler.session_state._cached_sessions = [mock_session]
        ws_handler.session_state._sessions_cache_time = 9999999999
        ws_handler.ws_manager.set_known_sessions(mock_websocket, {mock_session.session_id})

        # Create mock events
        events = [
            ParsedEvent(
                event_id="evt-1",
                session_id=mock_session.session_id,
                event_type=EventType.THINKING,
                source=AgentSource.CLAUDE,
                timestamp=FIXED_TIMESTAMP,
                content="Thinking",
                risk_level=RiskLevel.SAFE,
            ),
            ParsedEvent(
                event_id="evt-2",
                session_id=mock_session.session_id,
                event_type=EventType.TOOL_USE,
                source=AgentSource.CLAUDE,
                timestamp=FIXED_TIMESTAMP,
                tool_name="Read",
                risk_level=RiskLevel.SAFE,
            ),
        ]

        with patch("motus.ui.web.websocket.parse_incremental_events") as mock_parse:
            mock_parse.return_value = (events, 1000)

            with patch.object(ws_handler, "_update_context", new=AsyncMock()):
                await ws_handler._poll_events(mock_websocket)

                # Should send batch_events message
                calls = mock_websocket.send_json.call_args_list
                batch_call = next((c for c in calls if c[0][0].get("type") == "batch_events"), None)
                assert batch_call is not None
                assert batch_call[0][0]["count"] == 2

    async def test_poll_events_prunes_session_dicts(self, ws_handler, mock_websocket, mock_session):
        """Session dicts are pruned periodically."""
        ws_handler.session_state._cached_sessions = [mock_session]
        ws_handler.session_state._sessions_cache_time = 9999999999
        ws_handler.ws_manager.set_known_sessions(mock_websocket, {mock_session.session_id})

        # Ensure we exceed MAX_TRACKED_SESSIONS so pruning actually runs.
        # (prune_session_dicts is a no-op under the limit.)
        for i in range(ws_handler.session_state.MAX_TRACKED_SESSIONS + 1):
            session_id = f"stale-session-{i}"
            ws_handler.session_state.session_positions[session_id] = 100
            ws_handler.session_state.session_contexts[session_id] = {}

        await ws_handler._poll_events(mock_websocket)

        # Stale sessions should be pruned (active session remains).
        assert (
            len(ws_handler.session_state.session_positions)
            <= ws_handler.session_state.MAX_TRACKED_SESSIONS
        )
        assert mock_session.session_id not in ws_handler.session_state.session_positions

    async def test_poll_events_early_exit_no_active_sessions(self, ws_handler, mock_websocket):
        """Polling exits early if no active sessions."""
        # Only idle session
        idle_session = Mock()
        idle_session.status = SessionStatus.IDLE

        ws_handler.session_state._cached_sessions = [idle_session]
        ws_handler.session_state._sessions_cache_time = 9999999999

        with patch("motus.ui.web.websocket.parse_incremental_events") as mock_parse:
            await ws_handler._poll_events(mock_websocket)

            # Should not parse any events
            mock_parse.assert_not_called()


class TestWebSocketHandlerContextTracking:
    """Tests for context update and tracking."""

    async def test_update_context_thinking_tracks_decisions(self, ws_handler, mock_websocket):
        """THINKING events track decisions."""
        session_id = "test-session"

        event = ParsedEvent(
            event_id="evt-1",
            session_id=session_id,
            event_type=EventType.THINKING,
            source=AgentSource.CLAUDE,
            timestamp=FIXED_TIMESTAMP,
            content="I'll start by reading the configuration file to understand the setup",
            risk_level=RiskLevel.SAFE,
        )

        await ws_handler._update_context(mock_websocket, event, session_id, "/test/project")

        ctx = ws_handler.session_state.get_context(session_id)
        assert len(ctx["decisions"]) > 0

    async def test_update_context_thinking_tracks_errors(self, ws_handler, mock_websocket):
        """THINKING events track errors."""
        session_id = "test-session"

        event = ParsedEvent(
            event_id="evt-1",
            session_id=session_id,
            event_type=EventType.THINKING,
            source=AgentSource.CLAUDE,
            timestamp=FIXED_TIMESTAMP,
            content="Traceback (most recent call last): FileNotFoundError: No such file or directory",
            risk_level=RiskLevel.SAFE,
        )

        await ws_handler._update_context(mock_websocket, event, session_id, "/test/project")

        ctx = ws_handler.session_state.get_context(session_id)
        assert ctx.get("friction_count", 0) > 0

    async def test_update_context_agent_spawn_tracks_agent_tree(self, ws_handler, mock_websocket):
        """AGENT_SPAWN events track agent tree."""
        session_id = "test-session"

        event = ParsedEvent(
            event_id="evt-1",
            session_id=session_id,
            event_type=EventType.AGENT_SPAWN,
            source=AgentSource.CLAUDE,
            timestamp=FIXED_TIMESTAMP,
            content="Spawning sub-agent",
            risk_level=RiskLevel.SAFE,
            spawn_type="task",
            raw_data={"context": "Run tests"},
        )

        with patch("motus.ui.web.websocket.EventTransformer") as mock_transformer:
            mock_display = Mock()
            mock_display.details = ["Task agent", "Model: claude-sonnet-4", "Prompt: Run tests"]
            mock_transformer.transform.return_value = mock_display

            await ws_handler._update_context(mock_websocket, event, session_id, "/test/project")

            ctx = ws_handler.session_state.get_context(session_id)
            assert len(ctx["agent_tree"]) > 0
            assert ctx["agent_tree"][0]["type"] == "task"

    async def test_update_context_tool_use_tracks_tool_count(self, ws_handler, mock_websocket):
        """TOOL_USE events track tool usage counts."""
        session_id = "test-session"

        event = ParsedEvent(
            event_id="evt-1",
            session_id=session_id,
            event_type=EventType.TOOL_USE,
            source=AgentSource.CLAUDE,
            timestamp=FIXED_TIMESTAMP,
            tool_name="Read",
            tool_input={"file_path": "/src/main.py"},
            risk_level=RiskLevel.SAFE,
        )

        with patch("motus.ui.web.websocket.EventTransformer") as mock_transformer:
            mock_display = Mock()
            mock_display.file_path = "/src/main.py"
            mock_display.details = []
            mock_transformer.transform.return_value = mock_display

            await ws_handler._update_context(mock_websocket, event, session_id, "/test/project")

            ctx = ws_handler.session_state.get_context(session_id)
            assert ctx["tool_count"]["Read"] == 1

    async def test_update_context_tool_use_tracks_files_read(self, ws_handler, mock_websocket):
        """Read tool usage tracks files read."""
        session_id = "test-session"

        event = ParsedEvent(
            event_id="evt-1",
            session_id=session_id,
            event_type=EventType.TOOL_USE,
            source=AgentSource.CLAUDE,
            timestamp=FIXED_TIMESTAMP,
            tool_name="Read",
            tool_input={"file_path": "/src/config.py"},
            risk_level=RiskLevel.SAFE,
        )

        with patch("motus.ui.web.websocket.EventTransformer") as mock_transformer:
            mock_display = Mock()
            mock_display.file_path = "/src/config.py"
            mock_display.details = []
            mock_transformer.transform.return_value = mock_display

            await ws_handler._update_context(mock_websocket, event, session_id, "/test/project")

            ctx = ws_handler.session_state.get_context(session_id)
            assert "config.py" in ctx["files_read"]

    async def test_update_context_tool_use_tracks_files_modified(self, ws_handler, mock_websocket):
        """Edit/Write tool usage tracks files modified."""
        session_id = "test-session"

        event = ParsedEvent(
            event_id="evt-1",
            session_id=session_id,
            event_type=EventType.TOOL_USE,
            source=AgentSource.CLAUDE,
            timestamp=FIXED_TIMESTAMP,
            tool_name="Edit",
            tool_input={"file_path": "/src/main.py"},
            risk_level=RiskLevel.SAFE,
        )

        with patch("motus.ui.web.websocket.EventTransformer") as mock_transformer:
            mock_display = Mock()
            mock_display.file_path = "/src/main.py"
            mock_display.details = []
            mock_transformer.transform.return_value = mock_display

            await ws_handler._update_context(mock_websocket, event, session_id, "/test/project")

            ctx = ws_handler.session_state.get_context(session_id)
            assert "main.py" in ctx["files_modified"]

    async def test_track_thinking_limits_decisions_to_5(self, ws_handler, mock_websocket):
        """Decision tracking keeps only last 5."""
        event = ParsedEvent(
            event_id="evt-1",
            session_id="test-session",
            event_type=EventType.THINKING,
            source=AgentSource.CLAUDE,
            timestamp=FIXED_TIMESTAMP,
            content="I'll do this",
            risk_level=RiskLevel.SAFE,
        )

        ctx = ws_handler.session_state.get_context("test-session")

        # Add 6 decisions
        for i in range(6):
            updated_event = event.model_copy(update={"content": f"I'll do task {i}"})
            await ws_handler._track_thinking(updated_event, ctx)

        # Should only keep 5
        assert len(ctx["decisions"]) <= 5

    async def test_track_agent_spawn_limits_to_5(self, ws_handler, mock_websocket):
        """Agent tree keeps only last 5 spawns."""
        session_id = "test-session"
        ctx = ws_handler.session_state.get_context(session_id)

        event = ParsedEvent(
            event_id="evt-1",
            session_id=session_id,
            event_type=EventType.AGENT_SPAWN,
            source=AgentSource.CLAUDE,
            timestamp=FIXED_TIMESTAMP,
            spawn_type="task",
            risk_level=RiskLevel.SAFE,
        )

        with patch("motus.ui.web.websocket.EventTransformer") as mock_transformer:
            mock_display = Mock()
            mock_display.details = ["Agent"]
            mock_transformer.transform.return_value = mock_display

            # Add 6 spawns
            for i in range(6):
                await ws_handler._track_agent_spawn(
                    mock_websocket, event, session_id, ctx, mock_display
                )

            # Should only keep 5
            assert len(ctx["agent_tree"]) <= 5

    async def test_track_tool_use_handles_json_string_input(self, ws_handler, mock_websocket):
        """Tool input as JSON string is parsed."""
        session_id = "test-session"

        event = ParsedEvent(
            event_id="evt-1",
            session_id=session_id,
            event_type=EventType.TOOL_USE,
            source=AgentSource.CLAUDE,
            timestamp=FIXED_TIMESTAMP,
            tool_name="Read",
            tool_input='{"file_path": "/src/test.py"}',  # String instead of dict
            risk_level=RiskLevel.SAFE,
        )

        with patch("motus.ui.web.websocket.EventTransformer") as mock_transformer:
            mock_display = Mock()
            mock_display.file_path = ""
            mock_display.details = []
            mock_transformer.transform.return_value = mock_display

            # Should not raise
            await ws_handler._update_context(mock_websocket, event, session_id, "/test/project")

    async def test_track_tool_use_handles_invalid_json_input(self, ws_handler, mock_websocket):
        """Invalid JSON in tool input is handled gracefully."""
        session_id = "test-session"

        event = ParsedEvent(
            event_id="evt-1",
            session_id=session_id,
            event_type=EventType.TOOL_USE,
            source=AgentSource.CLAUDE,
            timestamp=FIXED_TIMESTAMP,
            tool_name="Read",
            tool_input="{invalid json}",  # Invalid JSON
            risk_level=RiskLevel.SAFE,
        )

        with patch("motus.ui.web.websocket.EventTransformer") as mock_transformer:
            mock_display = Mock()
            mock_display.file_path = ""
            mock_display.details = []
            mock_transformer.transform.return_value = mock_display

            # Should not raise
            await ws_handler._update_context(mock_websocket, event, session_id, "/test/project")

    async def test_track_tool_use_limits_files_read_to_10(self, ws_handler, mock_websocket):
        """Files read list is limited to 10."""
        session_id = "test-session"
        ctx = ws_handler.session_state.get_context(session_id)

        with patch("motus.ui.web.websocket.EventTransformer") as mock_transformer:
            mock_display = Mock()
            mock_display.details = []
            mock_transformer.transform.return_value = mock_display

            # Add 12 files
            for i in range(12):
                event = ParsedEvent(
                    event_id=f"evt-{i}",
                    session_id=session_id,
                    event_type=EventType.TOOL_USE,
                    source=AgentSource.CLAUDE,
                    timestamp=FIXED_TIMESTAMP,
                    tool_name="Read",
                    tool_input={"file_path": f"/src/file{i}.py"},
                    risk_level=RiskLevel.SAFE,
                )
                mock_display.file_path = f"/src/file{i}.py"

                await ws_handler._track_tool_use(
                    mock_websocket, event, session_id, ctx, mock_display
                )

            # Should only keep 10
            assert len(ctx["files_read"]) <= 10

    async def test_update_context_handles_event_without_event_type(
        self, ws_handler, mock_websocket
    ):
        """Events without event_type are handled gracefully."""
        session_id = "test-session"

        event = Mock()
        event.event_type = None

        with patch("motus.ui.web.websocket.EventTransformer") as mock_transformer:
            mock_display = Mock()
            mock_transformer.transform.return_value = mock_display

            # Should not raise
            await ws_handler._update_context(mock_websocket, event, session_id, "/test/project")
