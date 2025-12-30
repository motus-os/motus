"""
Comprehensive tests for the new builder architecture.

This module provides parity tests to replace the 56 deleted legacy parser tests:
- test_codex_parser.py (22 tests)
- test_gemini_parser.py (17 tests)
- test_transcript_parser.py (17 tests)

Tests cover:
- ClaudeBuilder: JSONL parsing, thinking blocks, tool_use, agent spawns
- CodexBuilder: JSONL parsing, function_call events, file size guards
- GeminiBuilder: JSON parsing, function_call events, model responses, file size guards

All tests verify builders return List[UnifiedEvent] and handle malformed input gracefully.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from motus.ingestors.claude import ClaudeBuilder
from motus.ingestors.codex import MAX_FILE_SIZE as CODEX_MAX_FILE_SIZE
from motus.ingestors.codex import CodexBuilder
from motus.ingestors.gemini import MAX_FILE_SIZE as GEMINI_MAX_FILE_SIZE
from motus.ingestors.gemini import GeminiBuilder
from motus.protocols import EventType

# Use deterministic constants from conftest
from tests.fixtures.constants import FIXED_TIMESTAMP


class TestClaudeBuilder:
    """Tests for ClaudeBuilder - Claude Code JSONL transcript parsing."""

    def test_parse_line_with_thinking_block(self, mock_uuid, mock_datetime_now):
        """Test parse_line() extracts thinking blocks from assistant messages."""
        builder = ClaudeBuilder()

        line = json.dumps(
            {
                "type": "assistant",
                "timestamp": FIXED_TIMESTAMP.isoformat(),
                "message": {
                    "model": "claude-sonnet-4-5",
                    "content": [
                        {
                            "type": "thinking",
                            "thinking": "I need to read the file first to understand the structure.",
                        }
                    ],
                },
            }
        )

        events = builder.parse_line(line, session_id="test-session")

        assert isinstance(events, list)
        assert len(events) >= 1

        # Find thinking event
        thinking_events = [e for e in events if e.event_type == EventType.THINKING]
        assert len(thinking_events) >= 1

        thinking = thinking_events[0]
        assert thinking.content == "I need to read the file first to understand the structure."
        assert thinking.session_id == "test-session"
        assert thinking.model == "claude-sonnet-4-5"

    def test_parse_line_with_tool_use_block(self, mock_uuid, mock_datetime_now):
        """Test parse_line() extracts tool_use blocks and creates tool events."""
        builder = ClaudeBuilder()

        line = json.dumps(
            {
                "type": "assistant",
                "timestamp": FIXED_TIMESTAMP.isoformat(),
                "message": {
                    "model": "claude-sonnet-4-5",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "tool_1",
                            "name": "Read",
                            "input": {"file_path": "/Users/test/example.py"},
                        }
                    ],
                },
            }
        )

        events = builder.parse_line(line, session_id="test-session")

        assert isinstance(events, list)
        assert len(events) >= 1

        # Find tool event
        tool_events = [e for e in events if e.event_type == EventType.TOOL]
        assert len(tool_events) >= 1

        tool = tool_events[0]
        assert tool.tool_name == "Read"
        assert tool.tool_input == {"file_path": "/Users/test/example.py"}
        assert tool.session_id == "test-session"

    def test_parse_line_with_task_tool_agent_spawn(self, mock_uuid, mock_datetime_now):
        """Test parse_line() creates AGENT_SPAWN events for Task tool calls."""
        builder = ClaudeBuilder()

        line = json.dumps(
            {
                "type": "assistant",
                "timestamp": FIXED_TIMESTAMP.isoformat(),
                "message": {
                    "model": "claude-sonnet-4-5",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "tool_task",
                            "name": "Task",
                            "input": {
                                "subagent_type": "research",
                                "description": "Research Python testing frameworks",
                                "prompt": "Find information about pytest fixtures",
                                "model": "claude-sonnet-4",
                            },
                        }
                    ],
                },
            }
        )

        events = builder.parse_line(line, session_id="test-session")

        assert isinstance(events, list)

        # Find agent spawn event
        agent_events = [e for e in events if e.event_type == EventType.AGENT_SPAWN]
        assert len(agent_events) == 1

        agent = agent_events[0]
        assert agent.agent_type == "research"
        assert agent.agent_description == "Research Python testing frameworks"
        assert agent.agent_prompt == "Find information about pytest fixtures"
        assert agent.agent_model == "claude-sonnet-4"
        assert "research" in agent.content

    def test_parse_line_with_text_response(self, mock_uuid, mock_datetime_now):
        """Test parse_line() extracts text content from assistant messages."""
        builder = ClaudeBuilder()

        line = json.dumps(
            {
                "type": "assistant",
                "timestamp": FIXED_TIMESTAMP.isoformat(),
                "message": {
                    "model": "claude-sonnet-4-5",
                    "content": [
                        {"type": "text", "text": "I've analyzed the code and found several issues."}
                    ],
                },
            }
        )

        events = builder.parse_line(line, session_id="test-session")

        assert isinstance(events, list)

        # Find response event
        response_events = [e for e in events if e.event_type == EventType.RESPONSE]
        assert len(response_events) >= 1

        response = response_events[0]
        assert "analyzed the code" in response.content
        assert response.model == "claude-sonnet-4-5"

    def test_parse_line_with_user_message(self, mock_uuid, mock_datetime_now):
        """Test parse_line() parses user messages."""
        builder = ClaudeBuilder()

        line = json.dumps(
            {
                "type": "user",
                "timestamp": FIXED_TIMESTAMP.isoformat(),
                "message": {
                    "content": [{"type": "text", "text": "Can you help me refactor this function?"}]
                },
            }
        )

        events = builder.parse_line(line, session_id="test-session")

        assert isinstance(events, list)
        assert len(events) == 1

        user_msg = events[0]
        assert user_msg.event_type == EventType.USER_MESSAGE
        assert "refactor this function" in user_msg.content

    def test_parse_line_handles_malformed_json(self):
        """Test parse_line() gracefully handles malformed JSON."""
        builder = ClaudeBuilder()

        malformed_line = "{ not valid json }"
        events = builder.parse_line(malformed_line, session_id="test-session")

        assert isinstance(events, list)
        assert len(events) == 0

    def test_parse_line_handles_empty_line(self):
        """Test parse_line() handles empty lines."""
        builder = ClaudeBuilder()

        events = builder.parse_line("", session_id="test-session")
        assert isinstance(events, list)
        assert len(events) == 0

        events = builder.parse_line("   \n  ", session_id="test-session")
        assert isinstance(events, list)
        assert len(events) == 0

    def test_parse_line_handles_missing_fields(self, mock_uuid, mock_datetime_now):
        """Test parse_line() handles missing required fields gracefully."""
        builder = ClaudeBuilder()

        # Missing message field
        line = json.dumps({"type": "assistant", "timestamp": FIXED_TIMESTAMP.isoformat()})

        events = builder.parse_line(line, session_id="test-session")
        assert isinstance(events, list)
        # Should not crash, may return empty list

        # Missing content field in message
        line = json.dumps(
            {"type": "assistant", "timestamp": FIXED_TIMESTAMP.isoformat(), "message": {}}
        )

        events = builder.parse_line(line, session_id="test-session")
        assert isinstance(events, list)

    def test_parse_events_full_file(self, mock_uuid, mock_datetime_now):
        """Test parse_events() parses complete JSONL file."""
        builder = ClaudeBuilder()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            # Write multi-line JSONL
            f.write(
                json.dumps(
                    {
                        "type": "user",
                        "timestamp": FIXED_TIMESTAMP.isoformat(),
                        "message": {"content": "Hello"},
                    }
                )
                + "\n"
            )
            f.write(
                json.dumps(
                    {
                        "type": "assistant",
                        "timestamp": FIXED_TIMESTAMP.isoformat(),
                        "message": {
                            "model": "claude-sonnet-4-5",
                            "content": [
                                {"type": "thinking", "thinking": "Processing request"},
                                {"type": "text", "text": "Hi there!"},
                            ],
                        },
                    }
                )
                + "\n"
            )
            temp_path = Path(f.name)

        try:
            events = builder.parse_events(temp_path)

            assert isinstance(events, list)
            assert len(events) >= 2  # At minimum user + response

            # Verify we have different event types
            event_types = {e.event_type for e in events}
            assert EventType.USER_MESSAGE in event_types
        finally:
            temp_path.unlink()

    def test_parse_events_handles_invalid_lines(self, mock_uuid, mock_datetime_now):
        """Test parse_events() skips invalid lines and continues parsing."""
        builder = ClaudeBuilder()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(json.dumps({"type": "user", "message": {"content": "Valid"}}) + "\n")
            f.write("{ invalid json }\n")
            f.write(json.dumps({"type": "user", "message": {"content": "Also valid"}}) + "\n")
            temp_path = Path(f.name)

        try:
            events = builder.parse_events(temp_path)

            assert isinstance(events, list)
            # Should parse valid lines, skip invalid
            user_events = [e for e in events if e.event_type == EventType.USER_MESSAGE]
            assert len(user_events) >= 1
        finally:
            temp_path.unlink()


class TestCodexBuilder:
    """Tests for CodexBuilder - OpenAI Codex CLI JSONL transcript parsing."""

    def test_parse_line_with_function_call(self, mock_uuid, mock_datetime_now):
        """Test parse_line() extracts function_call events."""
        builder = CodexBuilder()

        line = json.dumps(
            {
                "type": "response_item",
                "timestamp": FIXED_TIMESTAMP.isoformat(),
                "payload": {
                    "type": "function_call",
                    "name": "read_file",
                    "arguments": {"file_path": "/test/example.py"},
                },
            }
        )

        events = builder.parse_line(line, session_id="test-session")

        assert isinstance(events, list)
        assert len(events) >= 1

        # Find tool event (Codex calls them function_call)
        tool_events = [e for e in events if e.event_type == EventType.TOOL]
        assert len(tool_events) >= 1

        tool = tool_events[0]
        assert tool.tool_name == "Read"  # Mapped from read_file
        assert "/test/example.py" in str(tool.tool_input)

    def test_parse_line_with_shell_command(self, mock_uuid, mock_datetime_now):
        """Test parse_line() handles shell_command (Bash) tool."""
        builder = CodexBuilder()

        line = json.dumps(
            {
                "type": "response_item",
                "timestamp": FIXED_TIMESTAMP.isoformat(),
                "payload": {
                    "type": "function_call",
                    "name": "shell_command",
                    "arguments": {"command": "pytest tests/"},
                },
            }
        )

        events = builder.parse_line(line, session_id="test-session")

        assert isinstance(events, list)

        tool_events = [e for e in events if e.event_type == EventType.TOOL]
        assert len(tool_events) >= 1

        tool = tool_events[0]
        assert tool.tool_name == "Bash"  # Mapped from shell_command
        assert "pytest" in str(tool.tool_input)

    def test_parse_line_with_message_output(self, mock_uuid, mock_datetime_now):
        """Test parse_line() parses message/output_text events."""
        builder = CodexBuilder()

        line = json.dumps(
            {
                "type": "response_item",
                "timestamp": FIXED_TIMESTAMP.isoformat(),
                "payload": {
                    "type": "message",
                    "content": [{"type": "text", "text": "Analysis complete. Found 3 issues."}],
                },
            }
        )

        events = builder.parse_line(line, session_id="test-session")

        assert isinstance(events, list)

        response_events = [e for e in events if e.event_type == EventType.RESPONSE]
        assert len(response_events) >= 1

        response = response_events[0]
        assert "Analysis complete" in response.content

    def test_parse_line_creates_synthetic_thinking(self, mock_uuid, mock_datetime_now):
        """Test parse_line() creates synthetic thinking events for Codex."""
        builder = CodexBuilder()

        line = json.dumps(
            {
                "type": "response_item",
                "timestamp": FIXED_TIMESTAMP.isoformat(),
                "payload": {
                    "type": "function_call",
                    "name": "read_file",
                    "arguments": {"path": "/test.py"},
                },
            }
        )

        events = builder.parse_line(line, session_id="test-session")

        assert isinstance(events, list)

        # Should have synthetic thinking
        thinking_events = [e for e in events if e.event_type == EventType.THINKING]
        assert len(thinking_events) >= 1

        thinking = thinking_events[0]
        assert "Planning" in thinking.content or "read" in thinking.content.lower()

    def test_parse_line_handles_user_message(self, mock_uuid, mock_datetime_now):
        """Test parse_line() parses user messages from event_msg."""
        builder = CodexBuilder()

        line = json.dumps(
            {
                "type": "event_msg",
                "timestamp": FIXED_TIMESTAMP.isoformat(),
                "payload": {
                    "type": "user_message",
                    "role": "user",
                    "content": "Please analyze this code",
                },
            }
        )

        events = builder.parse_line(line, session_id="test-session")

        assert isinstance(events, list)

        user_events = [e for e in events if e.event_type == EventType.USER_MESSAGE]
        assert len(user_events) >= 1

        user_msg = user_events[0]
        assert "analyze this code" in user_msg.content

    def test_parse_line_handles_malformed_json(self):
        """Test parse_line() gracefully handles malformed JSON."""
        builder = CodexBuilder()

        malformed_line = "not valid json"
        events = builder.parse_line(malformed_line, session_id="test-session")

        assert isinstance(events, list)
        assert len(events) == 0

    def test_parse_line_handles_string_arguments(self, mock_uuid, mock_datetime_now):
        """Test parse_line() parses stringified JSON arguments."""
        builder = CodexBuilder()

        line = json.dumps(
            {
                "type": "response_item",
                "timestamp": FIXED_TIMESTAMP.isoformat(),
                "payload": {
                    "type": "function_call",
                    "name": "write_file",
                    "arguments": json.dumps({"path": "/test.py", "content": "print('hello')"}),
                },
            }
        )

        events = builder.parse_line(line, session_id="test-session")

        assert isinstance(events, list)

        tool_events = [e for e in events if e.event_type == EventType.TOOL]
        assert len(tool_events) >= 1

        tool = tool_events[0]
        assert tool.tool_name == "Write"
        assert isinstance(tool.tool_input, dict)

    def test_parse_events_with_file_size_guard(self, mock_uuid):
        """Test parse_events() skips files over MAX_FILE_SIZE."""
        builder = CodexBuilder()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(json.dumps({"type": "session_meta", "payload": {}}) + "\n")
            temp_path = Path(f.name)

        try:
            # Mock stat to return size over limit
            with patch.object(Path, "stat") as mock_stat:
                mock_stat.return_value.st_size = CODEX_MAX_FILE_SIZE + 1
                events = builder.parse_events(temp_path)

            # Should return empty list due to size guard
            assert isinstance(events, list)
            assert len(events) == 0
        finally:
            temp_path.unlink()

    def test_parse_events_full_file(self, mock_uuid, mock_datetime_now):
        """Test parse_events() parses complete JSONL file."""
        builder = CodexBuilder()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(
                json.dumps({"type": "session_meta", "payload": {"id": "test-123", "cwd": "/test"}})
                + "\n"
            )
            f.write(
                json.dumps(
                    {
                        "type": "event_msg",
                        "timestamp": FIXED_TIMESTAMP.isoformat(),
                        "payload": {"type": "user_message", "content": "Hello"},
                    }
                )
                + "\n"
            )
            f.write(
                json.dumps(
                    {
                        "type": "response_item",
                        "timestamp": FIXED_TIMESTAMP.isoformat(),
                        "payload": {
                            "type": "function_call",
                            "name": "read_file",
                            "arguments": {"path": "/test.py"},
                        },
                    }
                )
                + "\n"
            )
            temp_path = Path(f.name)

        try:
            events = builder.parse_events(temp_path)

            assert isinstance(events, list)
            assert len(events) >= 1

            # Should have various event types
            event_types = {e.event_type for e in events}
            # At minimum should have tool events
            assert any(t in event_types for t in [EventType.TOOL, EventType.USER_MESSAGE])
        finally:
            temp_path.unlink()

    def test_parse_events_handles_missing_file(self):
        """Test parse_events() handles missing file gracefully."""
        builder = CodexBuilder()

        nonexistent = Path("/tmp/does-not-exist-12345.jsonl")
        events = builder.parse_events(nonexistent)

        assert isinstance(events, list)
        assert len(events) == 0


class TestGeminiBuilder:
    """Tests for GeminiBuilder - Google Gemini CLI JSON transcript parsing."""

    def test_parse_events_with_function_call(self, mock_uuid, mock_datetime_now):
        """Test parse_events() extracts function_call events from JSON."""
        builder = GeminiBuilder()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                {
                    "sessionId": "test-session",
                    "messages": [
                        {
                            "type": "gemini",
                            "timestamp": FIXED_TIMESTAMP.isoformat(),
                            "model": "gemini-2.0",
                            "toolCalls": [
                                {"name": "read_file", "args": {"file_path": "/test/example.py"}}
                            ],
                        }
                    ],
                },
                f,
            )
            temp_path = Path(f.name)

        try:
            events = builder.parse_events(temp_path)

            assert isinstance(events, list)

            tool_events = [e for e in events if e.event_type == EventType.TOOL]
            assert len(tool_events) >= 1

            tool = tool_events[0]
            assert tool.tool_name == "Read"  # Mapped from read_file
            assert tool.tool_input == {"file_path": "/test/example.py"}
        finally:
            temp_path.unlink()

    def test_parse_events_with_model_response(self, mock_uuid, mock_datetime_now):
        """Test parse_events() extracts model response text."""
        builder = GeminiBuilder()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                {
                    "sessionId": "test-session",
                    "messages": [
                        {
                            "type": "gemini",
                            "timestamp": FIXED_TIMESTAMP.isoformat(),
                            "model": "gemini-2.0",
                            "content": "I've completed the analysis. Here are my findings.",
                        }
                    ],
                },
                f,
            )
            temp_path = Path(f.name)

        try:
            events = builder.parse_events(temp_path)

            assert isinstance(events, list)

            response_events = [e for e in events if e.event_type == EventType.RESPONSE]
            assert len(response_events) >= 1

            response = response_events[0]
            assert "analysis" in response.content
            assert response.model == "gemini-2.0"
        finally:
            temp_path.unlink()

    def test_parse_events_with_thinking_thoughts(self, mock_uuid, mock_datetime_now):
        """Test parse_events() extracts thinking/thoughts from Gemini."""
        builder = GeminiBuilder()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                {
                    "sessionId": "test-session",
                    "messages": [
                        {
                            "type": "gemini",
                            "timestamp": FIXED_TIMESTAMP.isoformat(),
                            "model": "gemini-2.0",
                            "thoughts": [
                                {
                                    "subject": "Analysis",
                                    "description": "Need to examine the data structure first",
                                    "timestamp": FIXED_TIMESTAMP.isoformat(),
                                }
                            ],
                        }
                    ],
                },
                f,
            )
            temp_path = Path(f.name)

        try:
            events = builder.parse_events(temp_path)

            assert isinstance(events, list)

            thinking_events = [e for e in events if e.event_type == EventType.THINKING]
            assert len(thinking_events) >= 1

            thinking = thinking_events[0]
            assert "Analysis" in thinking.content
            assert "data structure" in thinking.content
        finally:
            temp_path.unlink()

    def test_parse_events_with_user_message(self, mock_uuid, mock_datetime_now):
        """Test parse_events() parses user messages."""
        builder = GeminiBuilder()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                {
                    "sessionId": "test-session",
                    "messages": [
                        {
                            "type": "user",
                            "timestamp": FIXED_TIMESTAMP.isoformat(),
                            "content": "Can you help me debug this?",
                        }
                    ],
                },
                f,
            )
            temp_path = Path(f.name)

        try:
            events = builder.parse_events(temp_path)

            assert isinstance(events, list)
            assert len(events) >= 1

            user_msg = events[0]
            assert user_msg.event_type == EventType.USER_MESSAGE
            assert "debug" in user_msg.content
        finally:
            temp_path.unlink()

    def test_parse_events_with_api_error(self, mock_uuid, mock_datetime_now):
        """Test parse_events() handles API errors in messages."""
        builder = GeminiBuilder()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                {
                    "sessionId": "test-session",
                    "messages": [
                        {
                            "type": "gemini",
                            "timestamp": FIXED_TIMESTAMP.isoformat(),
                            "model": "gemini-2.0",
                            "error": {"message": "Rate limit exceeded"},
                        }
                    ],
                },
                f,
            )
            temp_path = Path(f.name)

        try:
            events = builder.parse_events(temp_path)

            assert isinstance(events, list)

            error_events = [e for e in events if e.event_type == EventType.ERROR]
            assert len(error_events) >= 1

            error = error_events[0]
            assert "Rate limit" in error.content
        finally:
            temp_path.unlink()

    def test_parse_events_with_safety_block(self, mock_uuid, mock_datetime_now):
        """Test parse_events() handles safety filter blocks."""
        builder = GeminiBuilder()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                {
                    "sessionId": "test-session",
                    "messages": [
                        {
                            "type": "gemini",
                            "timestamp": FIXED_TIMESTAMP.isoformat(),
                            "model": "gemini-2.0",
                            "finishReason": "SAFETY",
                            "safetyRatings": [{"category": "HARM_CATEGORY_DANGEROUS_CONTENT"}],
                        }
                    ],
                },
                f,
            )
            temp_path = Path(f.name)

        try:
            events = builder.parse_events(temp_path)

            assert isinstance(events, list)

            error_events = [e for e in events if e.event_type == EventType.ERROR]
            assert len(error_events) >= 1

            error = error_events[0]
            assert "safety" in error.content.lower()
        finally:
            temp_path.unlink()

    def test_parse_events_with_file_size_guard(self, mock_uuid):
        """Test parse_events() skips files over MAX_FILE_SIZE."""
        builder = GeminiBuilder()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"sessionId": "test"}, f)
            temp_path = Path(f.name)

        try:
            # Mock stat to return size over limit
            with patch.object(Path, "stat") as mock_stat:
                mock_stat.return_value.st_size = GEMINI_MAX_FILE_SIZE + 1
                events = builder.parse_events(temp_path)

            # Should return empty list due to size guard
            assert isinstance(events, list)
            assert len(events) == 0
        finally:
            temp_path.unlink()

    def test_parse_events_handles_malformed_json(self):
        """Test parse_events() handles malformed JSON gracefully."""
        builder = GeminiBuilder()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{ not valid json }")
            temp_path = Path(f.name)

        try:
            events = builder.parse_events(temp_path)

            # Should handle error gracefully
            assert isinstance(events, list)
            assert len(events) == 0
        finally:
            temp_path.unlink()

    def test_parse_events_handles_missing_messages(self, mock_uuid):
        """Test parse_events() handles missing messages field."""
        builder = GeminiBuilder()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"sessionId": "test-session"}, f)
            temp_path = Path(f.name)

        try:
            events = builder.parse_events(temp_path)

            assert isinstance(events, list)
            # May be empty but should not crash
        finally:
            temp_path.unlink()

    def test_parse_events_handles_missing_file(self):
        """Test parse_events() handles missing file gracefully."""
        builder = GeminiBuilder()

        nonexistent = Path("/tmp/does-not-exist-67890.json")
        events = builder.parse_events(nonexistent)

        assert isinstance(events, list)
        assert len(events) == 0

    def test_parse_line_returns_empty_for_gemini(self):
        """Test parse_line() returns empty for Gemini (uses JSON, not JSONL)."""
        builder = GeminiBuilder()

        # Gemini doesn't support line-level parsing (JSON not JSONL)
        line = json.dumps({"type": "gemini", "content": "Test"})
        events = builder.parse_line(line, session_id="test-session")

        assert isinstance(events, list)
        # Should return empty since Gemini uses full JSON parsing
        assert len(events) == 0


class TestBuilderEdgeCases:
    """Test edge cases and error handling across all builders."""

    def test_empty_file_handling(self, mock_uuid):
        """Test all builders handle empty files gracefully."""
        builders = [ClaudeBuilder(), CodexBuilder(), GeminiBuilder()]

        for builder in builders:
            with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
                # Empty file
                temp_path = Path(f.name)

            try:
                events = builder.parse_events(temp_path)
                assert isinstance(events, list)
                # Empty file should return empty list
                assert len(events) == 0
            finally:
                temp_path.unlink()

    def test_null_session_id_handling(self, mock_uuid, mock_datetime_now):
        """Test builders handle None/empty session IDs."""
        claude = ClaudeBuilder()
        codex = CodexBuilder()

        valid_line = json.dumps({"type": "user", "message": {"content": "test"}})

        # Should not crash with empty session_id
        events = claude.parse_line(valid_line, session_id="")
        assert isinstance(events, list)

        events = codex.parse_line(valid_line, session_id="")
        assert isinstance(events, list)

    def test_very_long_content_truncation(self, mock_uuid, mock_datetime_now):
        """Test builders preserve full content without truncation."""
        builder = ClaudeBuilder()

        # Create very long text (>500 chars)
        long_text = "A" * 1000

        line = json.dumps(
            {
                "type": "assistant",
                "timestamp": FIXED_TIMESTAMP.isoformat(),
                "message": {"content": [{"type": "text", "text": long_text}]},
            }
        )

        events = builder.parse_line(line, session_id="test-session")

        response_events = [e for e in events if e.event_type == EventType.RESPONSE]
        if response_events:
            response = response_events[0]
            # Content should NOT be truncated - full preservation
            assert len(response.content) == 1000

    def test_timestamp_parsing_fallback(self, mock_uuid):
        """Test builders fallback to current time if timestamp parsing fails."""
        builder = ClaudeBuilder()

        line = json.dumps(
            {
                "type": "user",
                "timestamp": "invalid-timestamp-format",
                "message": {"content": "test"},
            }
        )

        events = builder.parse_line(line, session_id="test-session")

        # Should not crash, should use fallback timestamp
        assert isinstance(events, list)
        if events:
            assert events[0].timestamp is not None


class TestBuilderExtractMethods:
    """Test builder extract_thinking and extract_decisions methods."""

    def test_claude_extract_thinking(self, tmp_path, mock_uuid):
        """Test ClaudeBuilder extract_thinking method."""
        from motus.ingestors.claude import ClaudeBuilder

        builder = ClaudeBuilder()

        # Create test file with thinking blocks
        test_file = tmp_path / "test.jsonl"
        test_file.write_text(
            json.dumps(
                {
                    "type": "assistant",
                    "timestamp": "2025-01-15T12:00:00Z",
                    "message": {
                        "model": "claude-3",
                        "content": [
                            {"type": "thinking", "thinking": "I need to analyze this carefully"},
                            {"type": "text", "text": "Here's my response"},
                        ],
                    },
                }
            )
            + "\n"
        )

        events = builder.extract_thinking(test_file)

        assert len(events) == 1
        assert events[0].event_type == EventType.THINKING
        assert "analyze this carefully" in events[0].content

    def test_claude_extract_thinking_oserror(self, tmp_path, mock_uuid):
        """Test ClaudeBuilder extract_thinking with missing file."""
        from motus.ingestors.claude import ClaudeBuilder

        builder = ClaudeBuilder()

        missing_file = tmp_path / "missing.jsonl"

        events = builder.extract_thinking(missing_file)

        assert events == []

    def test_claude_extract_decisions(self, tmp_path, mock_uuid):
        """Test ClaudeBuilder extract_decisions method."""
        from motus.ingestors.claude import ClaudeBuilder

        builder = ClaudeBuilder()

        # Create test file with decision markers that match DECISION_PATTERNS
        test_file = tmp_path / "test.jsonl"
        test_file.write_text(
            json.dumps(
                {
                    "type": "assistant",
                    "timestamp": "2025-01-15T12:00:00Z",
                    "message": {
                        "model": "claude-3",
                        "content": [
                            {
                                "type": "thinking",
                                "thinking": "I have decided to use the async pattern for performance",
                            },
                            {"type": "text", "text": "I'll use the reactive approach"},
                        ],
                    },
                }
            )
            + "\n"
        )

        events = builder.extract_decisions(test_file)

        # Should find decisions in thinking and text blocks
        assert len(events) >= 1
        decision_events = [e for e in events if e.event_type == EventType.DECISION]
        assert len(decision_events) >= 1

    def test_claude_extract_decisions_oserror(self, tmp_path, mock_uuid):
        """Test ClaudeBuilder extract_decisions with missing file."""
        from motus.ingestors.claude import ClaudeBuilder

        builder = ClaudeBuilder()

        missing_file = tmp_path / "missing.jsonl"

        events = builder.extract_decisions(missing_file)

        assert events == []

    def test_codex_extract_thinking(self, tmp_path, mock_uuid):
        """Test CodexBuilder extract_thinking method."""
        from motus.ingestors.codex import CodexBuilder

        builder = CodexBuilder()

        # Create test file with Codex thinking (synthesized from tool calls)
        test_file = tmp_path / "test.jsonl"
        test_file.write_text(
            json.dumps(
                {
                    "type": "response_item",
                    "timestamp": "2025-01-15T12:00:00Z",
                    "payload": {
                        "type": "function_call",
                        "name": "read_file",
                        "arguments": {"path": "/test.py"},
                    },
                }
            )
            + "\n"
        )

        events = builder.extract_thinking(test_file)

        # Codex creates synthetic thinking from tool calls
        assert isinstance(events, list)

    def test_codex_extract_thinking_oserror(self, tmp_path, mock_uuid):
        """Test CodexBuilder extract_thinking with missing file."""
        from motus.ingestors.codex import CodexBuilder

        builder = CodexBuilder()

        missing_file = tmp_path / "missing.jsonl"

        events = builder.extract_thinking(missing_file)

        assert events == []

    def test_codex_extract_decisions(self, tmp_path, mock_uuid):
        """Test CodexBuilder extract_decisions method."""
        from motus.ingestors.codex import CodexBuilder

        builder = CodexBuilder()

        # Create test file with message containing decision
        test_file = tmp_path / "test.jsonl"
        test_file.write_text(
            json.dumps(
                {
                    "type": "response_item",
                    "timestamp": "2025-01-15T12:00:00Z",
                    "payload": {
                        "type": "message",
                        "content": "Decision: I will use the async pattern",
                    },
                }
            )
            + "\n"
        )

        events = builder.extract_decisions(test_file)

        assert isinstance(events, list)

    def test_codex_extract_decisions_oserror(self, tmp_path, mock_uuid):
        """Test CodexBuilder extract_decisions with missing file."""
        from motus.ingestors.codex import CodexBuilder

        builder = CodexBuilder()

        missing_file = tmp_path / "missing.jsonl"

        events = builder.extract_decisions(missing_file)

        assert events == []

    def test_gemini_extract_thinking(self, tmp_path, mock_uuid):
        """Test GeminiBuilder extract_thinking method."""
        from motus.ingestors.gemini import GeminiBuilder

        builder = GeminiBuilder()

        # Create test file with Gemini thinking
        test_file = tmp_path / "test.json"
        test_file.write_text(
            json.dumps(
                {
                    "messages": [
                        {
                            "type": "gemini",
                            "timestamp": "2025-01-15T12:00:00Z",
                            "model": "gemini-1.5",
                            "thoughts": [
                                {
                                    "subject": "Analysis",
                                    "description": "Analyzing the codebase structure",
                                }
                            ],
                        }
                    ]
                }
            )
        )

        events = builder.extract_thinking(test_file)

        assert isinstance(events, list)
        assert len(events) == 1
        assert events[0].event_type == EventType.THINKING

    def test_gemini_extract_thinking_oserror(self, tmp_path, mock_uuid):
        """Test GeminiBuilder extract_thinking with missing file."""
        from motus.ingestors.gemini import GeminiBuilder

        builder = GeminiBuilder()

        missing_file = tmp_path / "missing.json"

        events = builder.extract_thinking(missing_file)

        assert events == []

    def test_gemini_extract_decisions(self, tmp_path, mock_uuid):
        """Test GeminiBuilder extract_decisions method."""
        from motus.ingestors.gemini import GeminiBuilder

        builder = GeminiBuilder()

        # Create test file with decision
        test_file = tmp_path / "test.json"
        test_file.write_text(
            json.dumps(
                {
                    "messages": [
                        {
                            "type": "gemini",
                            "timestamp": "2025-01-15T12:00:00Z",
                            "text": "Decision: Using reactive pattern",
                        }
                    ]
                }
            )
        )

        events = builder.extract_decisions(test_file)

        assert isinstance(events, list)

    def test_gemini_extract_decisions_oserror(self, tmp_path, mock_uuid):
        """Test GeminiBuilder extract_decisions with missing file."""
        from motus.ingestors.gemini import GeminiBuilder

        builder = GeminiBuilder()

        missing_file = tmp_path / "missing.json"

        events = builder.extract_decisions(missing_file)

        assert events == []
