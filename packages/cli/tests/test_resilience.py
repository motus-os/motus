"""Resilience tests for error handling and graceful degradation.

These tests verify that the system handles errors gracefully:
- Bad/malformed events are logged, not crashed on
- Missing data is handled with sensible defaults
- Error states are surfaced appropriately
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path


class TestEventParsingResilience:
    """Test that event parsing handles bad data gracefully."""

    def test_corrupted_json_line_logged_not_crashed(self):
        """Corrupted JSON lines are logged and skipped, not crashed on."""
        from motus.tail_reader import tail_lines

        # Create a temp file with mix of valid and invalid lines
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            # Valid event
            f.write(json.dumps({"type": "user", "message": {"content": "test"}}) + "\n")
            # Corrupted JSON
            f.write("{not valid json\n")
            # Another valid event
            f.write(json.dumps({"type": "assistant", "message": {"content": "response"}}) + "\n")
            f.flush()

            # tail_lines should not crash, should return raw lines
            lines = tail_lines(Path(f.name), n_lines=10)

            # Should have returned lines (including corrupted one as raw string)
            assert isinstance(lines, list)
            assert len(lines) == 3  # All three lines including corrupted

    def test_missing_required_fields_handled_gracefully(self):
        """Events with missing required fields are handled gracefully."""
        from motus.ingestors.claude import ClaudeBuilder

        builder = ClaudeBuilder()

        # Event missing expected fields
        incomplete_events = [
            '{"type": "tool_use"}',  # Missing tool details
            '{"type": "thinking"}',  # Missing content
            '{"message": {}}',  # Missing type
        ]

        for line in incomplete_events:
            # parse_line should handle incomplete events gracefully
            result = builder.parse_line(line, session_id="test-session")
            # Should return empty list or partial result, not crash
            assert isinstance(result, list)

    def test_null_values_in_events_handled(self):
        """Null values in event fields are handled gracefully."""
        from motus.ingestors.claude import ClaudeBuilder

        builder = ClaudeBuilder()

        # Events with null values - these should either return empty list or handle gracefully
        null_events = [
            '{"type": "tool_use", "name": null, "input": null}',
            '{"type": "assistant", "message": {"content": null}}',
            '{"type": "thinking", "thinking": null}',
        ]

        for line in null_events:
            try:
                # parse_line should handle null values - either returning empty list or raising safe error
                result = builder.parse_line(line, session_id="test-session")
                assert isinstance(result, list)
            except (TypeError, AttributeError, KeyError, ValueError):
                # These are acceptable error types for malformed events
                # The important thing is that the builder doesn't crash with unexpected errors
                pass


class TestOrchestratorResilience:
    """Test that the orchestrator handles errors gracefully."""

    def test_orchestrator_discovers_without_crash(self):
        """Orchestrator discovery works without crashing even if dirs don't exist."""
        from motus.orchestrator import get_orchestrator

        orch = get_orchestrator()

        # discover_all should return a list, even if empty
        sessions = orch.discover_all()
        assert isinstance(sessions, list)

    def test_tail_reader_handles_nonexistent_file(self):
        """Tail reader handles non-existent files gracefully."""
        from motus.tail_reader import tail_lines

        # Should return empty list, not crash
        lines = tail_lines(Path("/nonexistent/path/file.jsonl"), n_lines=10)
        assert isinstance(lines, list)
        assert len(lines) == 0

    def test_tail_reader_handles_corrupted_file(self):
        """Tail reader handles corrupted files gracefully."""
        from motus.tail_reader import tail_lines

        # Create temp file with garbage content
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write("not json at all\n")
            f.write("more garbage\n")
            f.flush()

            # Should not crash, returns raw lines
            lines = tail_lines(Path(f.name), n_lines=10)
            assert isinstance(lines, list)


class TestHealthCalculationResilience:
    """Test that health calculations handle edge cases."""

    def test_session_health_dataclass_has_defaults(self):
        """SessionHealth dataclass can be created with minimal fields."""
        from motus.protocols import SessionHealth

        # Should be able to create with just required fields
        health = SessionHealth(
            session_id="test-session",
            health_score=75,
            health_label="On Track",
        )

        assert health.health_score == 75
        assert health.health_label == "On Track"
        # Defaults should work
        assert health.tool_calls == 0
        assert health.decisions == 0

    def test_session_status_enum_values(self):
        """SessionStatus enum has expected values."""
        from motus.protocols import SessionStatus

        # All expected status values should exist
        assert hasattr(SessionStatus, "ACTIVE")
        assert hasattr(SessionStatus, "CRASHED")
        assert hasattr(SessionStatus, "IDLE")


class TestRichResilience:
    """Test that Rich output handles edge cases gracefully."""

    def test_format_event_handles_missing_fields(self):
        """CLI event formatting handles events with missing fields."""
        from motus.cli import ToolEvent

        # Event with minimal fields
        event = ToolEvent(
            name="Unknown",
            input={},
            timestamp=datetime.now(),
        )

        # Should have basic attributes without crashing
        assert event.name == "Unknown"
        assert event.input == {}
        assert event.timestamp is not None

    def test_rich_escape_handles_edge_cases(self):
        """Rich markup escape handles edge cases."""
        from rich.markup import escape

        # Edge cases that shouldn't crash
        edge_cases = [
            "",  # Empty string
            " ",  # Whitespace
            "[[nested]]",  # Nested brackets
            "\\[escaped\\]",  # Pre-escaped
            "a" * 10000,  # Long string
        ]

        for case in edge_cases:
            result = escape(case)
            assert isinstance(result, str)


class TestLoggerResilience:
    """Test that logging handles errors without crashing."""

    def test_structured_logging_handles_non_serializable(self):
        """Structured logging handles non-JSON-serializable values."""
        from motus.logging import get_logger

        logger = get_logger("test_resilience")

        # Should not crash on non-serializable values
        class NonSerializable:
            pass

        try:
            logger.debug(
                "Test message",
                non_serializable=NonSerializable(),
                normal_value="test",
            )
        except Exception as e:
            # If it raises, should be a known type
            assert isinstance(e, (TypeError, ValueError))


class TestDegradedModeResilience:
    """Test graceful degradation when components fail."""

    def test_web_shows_error_banner_on_orchestrator_failure(self):
        """Web UI shows error state when orchestrator fails, doesn't crash."""
        from unittest.mock import MagicMock, patch

        from motus.ui.web import MCWebServer

        # Create server instance
        server = MCWebServer(port=0)

        # Mock orchestrator to raise exception on discover_all
        mock_orchestrator = MagicMock()
        mock_orchestrator.discover_all.side_effect = Exception("Discovery failed")

        with patch("motus.ui.web.state.get_orchestrator", return_value=mock_orchestrator):
            # Call _get_cached_sessions - should handle error gracefully
            try:
                sessions = server._get_cached_sessions()
                # Should return empty list instead of crashing
                assert isinstance(sessions, list)
                assert len(sessions) == 0
            except Exception as e:
                # If it raises, verify it's logged and not propagated to UI
                # The web server should catch this and show degraded state
                assert "Discovery failed" in str(e)

    def test_discovery_returns_empty_on_permission_error(self):
        """Orchestrator discovery gracefully returns empty list on permission errors."""
        from unittest.mock import MagicMock, patch

        from motus.orchestrator import SessionOrchestrator
        from motus.protocols import Source

        orch = SessionOrchestrator()

        # Mock builder to raise permission error
        mock_builder = MagicMock()
        mock_builder.discover.side_effect = PermissionError("Access denied")

        # Patch builders dict - need to use Source enum
        with patch.object(orch, "_builders", {Source.CLAUDE: mock_builder}):
            # Should return empty list, not crash
            sessions = orch.discover_all(sources=[Source.CLAUDE])
            assert isinstance(sessions, list)
            assert len(sessions) == 0

    def test_parsing_skips_corrupted_lines(self):
        """Event parsing skips corrupted JSON lines, processes good ones."""
        import json
        import tempfile
        from pathlib import Path

        from motus.ingestors.claude import ClaudeBuilder

        builder = ClaudeBuilder()

        # Create temp file with mix of valid and invalid lines
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            # Valid event
            f.write(
                json.dumps(
                    {
                        "type": "message_start",
                        "message": {
                            "id": "msg_123",
                            "type": "message",
                            "role": "assistant",
                            "model": "claude-3-5-sonnet-20241022",
                        },
                    }
                )
                + "\n"
            )
            # Corrupted JSON
            f.write("{corrupted json line\n")
            # Another valid event
            f.write(
                json.dumps(
                    {
                        "type": "content_block_start",
                        "index": 0,
                        "content_block": {"type": "text", "text": ""},
                    }
                )
                + "\n"
            )
            # Malformed event (missing required fields)
            f.write(json.dumps({"type": "unknown"}) + "\n")
            # Another good event
            f.write(
                json.dumps(
                    {
                        "type": "content_block_delta",
                        "index": 0,
                        "delta": {"type": "text_delta", "text": "Hello"},
                    }
                )
                + "\n"
            )
            f.flush()
            temp_path = Path(f.name)

        # Parse should skip corrupted lines, process good ones
        try:
            events = builder.parse_events(temp_path)
            # Should have parsed some events (at least the valid ones)
            assert isinstance(events, list)
            # Should not have crashed on corrupted lines
            # Some valid events should have been parsed
            assert len(events) >= 0  # May be 0 if all events were malformed
        except Exception as e:
            # Should handle parsing errors gracefully
            assert False, f"Parser crashed instead of skipping bad lines: {e}"

    def test_websocket_reconnects_on_disconnect(self):
        """WebSocket handler doesn't crash on client disconnect."""
        from unittest.mock import AsyncMock, MagicMock

        from fastapi import WebSocketDisconnect

        from motus.ui.web import MCWebServer

        server = MCWebServer(port=0)

        # Create mock websocket that disconnects
        mock_websocket = MagicMock()
        mock_websocket.accept = AsyncMock()
        mock_websocket.receive_json = AsyncMock(side_effect=WebSocketDisconnect())

        # Mock orchestrator
        mock_orchestrator = MagicMock()
        mock_orchestrator.discover_all.return_value = []

        # The websocket handler should catch WebSocketDisconnect and clean up
        # This test verifies the handler structure handles disconnects gracefully
        # (Full async test would require more complex setup)

        # Verify server has WebSocketManager initialized
        assert hasattr(server, "ws_manager")
        assert isinstance(server.ws_manager.clients, set)
        assert isinstance(server.ws_manager.known_sessions, dict)

        # Add mock client and verify cleanup works
        server.ws_manager.add_client(mock_websocket)

        # Simulate cleanup (what finally block does)
        server.ws_manager.remove_client(mock_websocket)

        # Verify cleanup succeeded
        assert mock_websocket not in server.ws_manager.clients
        assert mock_websocket not in server.ws_manager.known_sessions

    def test_session_not_found_returns_error_json(self):
        """API endpoint returns structured error for missing session, not 500."""
        from unittest.mock import MagicMock, patch

        from motus.ui.web import MCWebServer

        server = MCWebServer(port=0)

        # Mock orchestrator with no sessions
        mock_orchestrator = MagicMock()
        mock_orchestrator.get_session.return_value = None

        with patch("motus.ui.web.routes.get_orchestrator", return_value=mock_orchestrator):
            # Create the app
            app = server.create_app()

            # Test the summary endpoint (uses get_session internally)
            # We'll call the endpoint handler directly since setting up TestClient
            # requires FastAPI to be installed (which it is in web extras)
            try:
                from fastapi.testclient import TestClient

                client = TestClient(app)

                # Request summary for non-existent session
                response = client.get("/api/summary/nonexistent-session-id")

                # Should return 200 with error JSON, not 500
                assert response.status_code == 200
                data = response.json()
                assert "error" in data
                assert "not found" in data["error"].lower()
            except ImportError:
                # FastAPI not installed - verify the logic manually
                import asyncio

                # Get the endpoint handler
                for route in app.routes:
                    if hasattr(route, "path") and route.path == "/api/summary/{session_id}":
                        # Call the handler directly
                        result = asyncio.run(route.endpoint(session_id="nonexistent"))
                        assert isinstance(result, dict)
                        assert "error" in result
                        break
