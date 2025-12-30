"""Tests for tool result parsing."""

import json

from motus.ingestors.claude import ClaudeBuilder
from motus.ingestors.codex import CodexBuilder
from motus.ingestors.gemini import GeminiBuilder
from motus.protocols import EventType

# Use deterministic constants from conftest
from tests.fixtures.constants import FIXED_TIMESTAMP


class TestClaudeToolResults:
    """Test Claude tool result parsing."""

    def test_tool_result_parsed_not_discarded(self, mock_uuid, mock_datetime_now):
        """Tool results should be parsed, not return empty list."""
        builder = ClaudeBuilder()

        # Simulate a tool result event
        line = json.dumps(
            {
                "type": "result",
                "timestamp": FIXED_TIMESTAMP.isoformat(),
                "content": "File contents here...",
                "tool_use_id": "toolu_123",
            }
        )

        events = builder.parse_line(line, "test-session")

        assert len(events) > 0, "Tool results should not be discarded"
        assert events[0].event_type == EventType.TOOL_RESULT

    def test_tool_result_content_preserved(self, mock_uuid, mock_datetime_now):
        """Full tool result content should be preserved."""
        builder = ClaudeBuilder()

        long_content = "x" * 5000  # 5KB of content
        line = json.dumps(
            {
                "type": "result",
                "timestamp": FIXED_TIMESTAMP.isoformat(),
                "content": long_content,
                "tool_use_id": "toolu_456",
            }
        )

        events = builder.parse_line(line, "test-session")

        assert len(events) > 0
        assert len(events[0].content) == 5000, "Content should not be truncated"

    def test_tool_result_linked_to_tool_use(self, mock_uuid, mock_datetime_now):
        """Tool result should include tool_use_id for correlation."""
        builder = ClaudeBuilder()

        line = json.dumps(
            {
                "type": "result",
                "timestamp": FIXED_TIMESTAMP.isoformat(),
                "content": "Some result",
                "tool_use_id": "toolu_789",
            }
        )

        events = builder.parse_line(line, "test-session")

        assert len(events) > 0
        assert events[0].tool_use_id == "toolu_789"

    def test_tool_result_array_content(self, mock_uuid, mock_datetime_now):
        """Handle array-style content blocks."""
        builder = ClaudeBuilder()

        line = json.dumps(
            {
                "type": "result",
                "timestamp": FIXED_TIMESTAMP.isoformat(),
                "content": [
                    {"type": "text", "text": "First part"},
                    {"type": "text", "text": "Second part"},
                ],
                "tool_use_id": "toolu_array",
            }
        )

        events = builder.parse_line(line, "test-session")

        assert len(events) > 0
        assert "First part" in events[0].content
        assert "Second part" in events[0].content

    def test_tool_result_tool_output_field(self, mock_uuid, mock_datetime_now):
        """Tool result should populate tool_output field."""
        builder = ClaudeBuilder()

        content = "Tool output data"
        line = json.dumps(
            {
                "type": "result",
                "timestamp": FIXED_TIMESTAMP.isoformat(),
                "content": content,
                "tool_use_id": "toolu_output",
            }
        )

        events = builder.parse_line(line, "test-session")

        assert len(events) > 0
        assert events[0].tool_output == content


class TestCodexToolResults:
    """Test Codex function output parsing."""

    def test_codex_function_output_parsed(self, mock_uuid, mock_datetime_now):
        """Codex function_call_output should create TOOL_RESULT events."""
        builder = CodexBuilder()

        line = json.dumps(
            {
                "type": "response_item",
                "timestamp": FIXED_TIMESTAMP.isoformat(),
                "payload": {
                    "type": "function_call_output",
                    "call_id": "call_123",
                    "output": "Command executed successfully",
                },
            }
        )

        events = builder.parse_line(line, "test-session")

        result_events = [e for e in events if e.event_type == EventType.TOOL_RESULT]
        assert len(result_events) > 0, "Function output should create TOOL_RESULT"
        assert result_events[0].tool_output == "Command executed successfully"

    def test_codex_json_output_parsed(self, mock_uuid, mock_datetime_now):
        """Codex JSON-encoded output should be handled."""
        builder = CodexBuilder()

        json_output = json.dumps({"status": "success", "data": "result"})
        line = json.dumps(
            {
                "type": "response_item",
                "timestamp": FIXED_TIMESTAMP.isoformat(),
                "payload": {
                    "type": "function_call_output",
                    "call_id": "call_json",
                    "output": json_output,
                },
            }
        )

        events = builder.parse_line(line, "test-session")

        result_events = [e for e in events if e.event_type == EventType.TOOL_RESULT]
        assert len(result_events) > 0
        # Should extract the value from JSON
        assert len(result_events[0].content) > 0

    def test_codex_output_includes_call_id(self, mock_uuid, mock_datetime_now):
        """Codex tool results should include call_id for correlation."""
        builder = CodexBuilder()

        line = json.dumps(
            {
                "type": "response_item",
                "timestamp": FIXED_TIMESTAMP.isoformat(),
                "payload": {
                    "type": "function_call_output",
                    "call_id": "call_correlate",
                    "output": "Result data",
                },
            }
        )

        events = builder.parse_line(line, "test-session")

        result_events = [e for e in events if e.event_type == EventType.TOOL_RESULT]
        assert len(result_events) > 0
        assert result_events[0].tool_use_id == "call_correlate"


class TestGeminiToolResults:
    """Test Gemini tool result parsing."""

    def test_gemini_tool_result_parsed(self, mock_uuid, mock_datetime_now):
        """Gemini tool results should be extracted from toolCalls."""
        builder = GeminiBuilder()

        # Create a Gemini session JSON file
        gemini_data = {
            "sessionId": "test-session",
            "messages": [
                {
                    "type": "gemini",
                    "timestamp": FIXED_TIMESTAMP.isoformat(),
                    "model": "gemini-pro",
                    "toolCalls": [
                        {
                            "id": "tool_1",
                            "name": "read_file",
                            "args": {},
                            "result": "File content here",
                        }
                    ],
                    "content": "",
                }
            ],
        }

        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(gemini_data, f)
            temp_path = f.name

        try:
            from pathlib import Path

            events = builder.parse_events(Path(temp_path))

            result_events = [e for e in events if e.event_type == EventType.TOOL_RESULT]
            assert len(result_events) > 0, "Gemini tool results should be parsed"
            assert result_events[0].tool_output == "File content here"
        finally:
            import os

            os.unlink(temp_path)

    def test_gemini_tool_error_not_result(self, mock_uuid, mock_datetime_now):
        """Gemini tool errors should create ERROR events, not TOOL_RESULT."""
        builder = GeminiBuilder()

        gemini_data = {
            "sessionId": "test-session",
            "messages": [
                {
                    "type": "gemini",
                    "timestamp": FIXED_TIMESTAMP.isoformat(),
                    "model": "gemini-pro",
                    "toolCalls": [
                        {
                            "id": "tool_err",
                            "name": "read_file",
                            "args": {},
                            "error": "File not found",
                        }
                    ],
                    "content": "",
                }
            ],
        }

        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(gemini_data, f)
            temp_path = f.name

        try:
            from pathlib import Path

            events = builder.parse_events(Path(temp_path))

            result_events = [e for e in events if e.event_type == EventType.TOOL_RESULT]
            error_events = [e for e in events if e.event_type == EventType.ERROR]

            # Should have error, not result
            assert len(error_events) > 0
            assert len(result_events) == 0  # No result when there's an error
        finally:
            import os

            os.unlink(temp_path)


class TestToolResultIntegration:
    """Integration tests for tool results."""

    def test_tool_use_followed_by_result(self, mock_uuid, mock_datetime_now):
        """A tool_use event followed by a result should both be captured."""
        builder = ClaudeBuilder()

        # Tool use line
        tool_use_line = json.dumps(
            {
                "type": "assistant",
                "timestamp": FIXED_TIMESTAMP.isoformat(),
                "message": {
                    "model": "claude-sonnet-4-5",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "toolu_integration",
                            "name": "Read",
                            "input": {"file_path": "/test.py"},
                        }
                    ],
                },
            }
        )

        # Result line
        result_line = json.dumps(
            {
                "type": "result",
                "timestamp": FIXED_TIMESTAMP.isoformat(),
                "content": "def hello():\n    print('world')",
                "tool_use_id": "toolu_integration",
            }
        )

        tool_events = builder.parse_line(tool_use_line, "test-session")
        result_events = builder.parse_line(result_line, "test-session")

        # Should have both tool use and result
        assert any(e.event_type == EventType.TOOL for e in tool_events)
        assert any(e.event_type == EventType.TOOL_RESULT for e in result_events)

    def test_no_result_for_empty_content(self, mock_uuid, mock_datetime_now):
        """Empty tool results should not create events."""
        builder = ClaudeBuilder()

        line = json.dumps(
            {
                "type": "result",
                "timestamp": FIXED_TIMESTAMP.isoformat(),
                "content": "",
                "tool_use_id": "toolu_empty",
            }
        )

        events = builder.parse_line(line, "test-session")

        # Should not create an event for empty content
        result_events = [e for e in events if e.event_type == EventType.TOOL_RESULT]
        assert len(result_events) == 0
