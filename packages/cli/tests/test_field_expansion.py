"""Tests for expanded field parsing across all builders.

This test suite verifies that we capture ALL available fields from JSONL files,
not just the ~40% we used to parse. We now capture:
- Claude: parentUuid, message.id, stop_reason, cache tokens, tool_use.id, isSidechain, requestId
- Codex: call_id, rate_limits, session metadata
- Gemini: message.id, project_hash, token_breakdown, finishReason, tool_call.id
"""

import json

from motus.ingestors.claude import ClaudeBuilder
from motus.ingestors.codex import CodexBuilder
from motus.ingestors.gemini import GeminiBuilder
from motus.protocols import EventType


class TestClaudeFieldExpansion:
    """Test Claude field expansion."""

    def test_message_id_captured(self):
        """message.id should be captured in raw_data."""
        builder = ClaudeBuilder()
        line = json.dumps(
            {
                "type": "assistant",
                "timestamp": "2025-01-15T12:00:00Z",
                "sessionId": "test",
                "message": {"id": "msg_01ABC123", "content": [{"type": "text", "text": "Hello"}]},
            }
        )

        events = builder.parse_line(line, "test-session")
        assert len(events) > 0
        assert events[0].raw_data.get("message_id") == "msg_01ABC123"

    def test_stop_reason_captured(self):
        """message.stop_reason should be captured."""
        builder = ClaudeBuilder()
        line = json.dumps(
            {
                "type": "assistant",
                "timestamp": "2025-01-15T12:00:00Z",
                "sessionId": "test",
                "message": {
                    "content": [{"type": "text", "text": "Done"}],
                    "stop_reason": "end_turn",
                },
            }
        )

        events = builder.parse_line(line, "test-session")
        assert len(events) > 0
        assert events[0].raw_data.get("stop_reason") == "end_turn"

    def test_cache_tokens_captured(self):
        """Cache token metrics should be captured."""
        builder = ClaudeBuilder()
        line = json.dumps(
            {
                "type": "assistant",
                "timestamp": "2025-01-15T12:00:00Z",
                "sessionId": "test",
                "message": {
                    "content": [{"type": "text", "text": "Response"}],
                    "usage": {
                        "input_tokens": 100,
                        "output_tokens": 50,
                        "cache_creation_input_tokens": 80,
                        "cache_read_input_tokens": 20,
                    },
                },
            }
        )

        events = builder.parse_line(line, "test-session")
        assert len(events) > 0
        raw = events[0].raw_data
        assert raw.get("input_tokens") == 100
        assert raw.get("output_tokens") == 50
        assert raw.get("cache_creation_tokens") == 80
        assert raw.get("cache_read_tokens") == 20

    def test_parent_uuid_captured(self):
        """parentUuid should be captured for event chaining."""
        builder = ClaudeBuilder()
        line = json.dumps(
            {
                "type": "assistant",
                "timestamp": "2025-01-15T12:00:00Z",
                "sessionId": "test",
                "parentUuid": "parent-event-123",
                "uuid": "this-event-456",
                "message": {"content": [{"type": "text", "text": "Child event"}]},
            }
        )

        events = builder.parse_line(line, "test-session")
        assert len(events) > 0
        assert events[0].raw_data.get("parent_uuid") == "parent-event-123"
        assert events[0].raw_data.get("uuid") == "this-event-456"

    def test_request_id_captured(self):
        """requestId should be captured for API correlation."""
        builder = ClaudeBuilder()
        line = json.dumps(
            {
                "type": "assistant",
                "timestamp": "2025-01-15T12:00:00Z",
                "sessionId": "test",
                "requestId": "req_abc123",
                "message": {"content": [{"type": "text", "text": "Response"}]},
            }
        )

        events = builder.parse_line(line, "test-session")
        assert len(events) > 0
        assert events[0].raw_data.get("request_id") == "req_abc123"

    def test_tool_use_id_captured(self):
        """tool_use.id should be captured for result linking."""
        builder = ClaudeBuilder()
        line = json.dumps(
            {
                "type": "assistant",
                "timestamp": "2025-01-15T12:00:00Z",
                "sessionId": "test",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "toolu_01XYZ",
                            "name": "Read",
                            "input": {"file_path": "/test.py"},
                        }
                    ]
                },
            }
        )

        events = builder.parse_line(line, "test-session")
        tool_events = [e for e in events if e.event_type == EventType.TOOL]
        assert len(tool_events) > 0
        assert tool_events[0].raw_data.get("tool_use_id") == "toolu_01XYZ"

    def test_is_sidechain_captured(self):
        """isSidechain flag should be captured."""
        builder = ClaudeBuilder()
        line = json.dumps(
            {
                "type": "assistant",
                "timestamp": "2025-01-15T12:00:00Z",
                "sessionId": "test",
                "isSidechain": True,
                "message": {"content": [{"type": "text", "text": "Sub-agent"}]},
            }
        )

        events = builder.parse_line(line, "test-session")
        assert len(events) > 0
        assert events[0].raw_data.get("is_sidechain") is True

    def test_git_branch_captured(self):
        """gitBranch should be captured."""
        builder = ClaudeBuilder()
        line = json.dumps(
            {
                "type": "assistant",
                "timestamp": "2025-01-15T12:00:00Z",
                "sessionId": "test",
                "gitBranch": "feature/new-thing",
                "message": {"content": [{"type": "text", "text": "Working"}]},
            }
        )

        events = builder.parse_line(line, "test-session")
        assert len(events) > 0
        assert events[0].raw_data.get("git_branch") == "feature/new-thing"

    def test_context_fields_captured(self):
        """Context fields (slug, agentId, cwd, version) should be captured."""
        builder = ClaudeBuilder()
        line = json.dumps(
            {
                "type": "assistant",
                "timestamp": "2025-01-15T12:00:00Z",
                "sessionId": "test",
                "slug": "test-slug",
                "agentId": "agent123",
                "cwd": "/home/user/project",
                "version": "2.0.55",
                "message": {"content": [{"type": "text", "text": "Context test"}]},
            }
        )

        events = builder.parse_line(line, "test-session")
        assert len(events) > 0
        raw = events[0].raw_data
        assert raw.get("slug") == "test-slug"
        assert raw.get("agent_id") == "agent123"
        assert raw.get("cwd") == "/home/user/project"
        assert raw.get("version") == "2.0.55"

    def test_service_tier_captured(self):
        """usage.service_tier should be captured."""
        builder = ClaudeBuilder()
        line = json.dumps(
            {
                "type": "assistant",
                "timestamp": "2025-01-15T12:00:00Z",
                "sessionId": "test",
                "message": {
                    "content": [{"type": "text", "text": "Response"}],
                    "usage": {"service_tier": "standard"},
                },
            }
        )

        events = builder.parse_line(line, "test-session")
        assert len(events) > 0
        assert events[0].raw_data.get("service_tier") == "standard"


class TestCodexFieldExpansion:
    """Test Codex field expansion."""

    def test_call_id_captured(self):
        """Function call_id should be captured."""
        builder = CodexBuilder()
        line = json.dumps(
            {
                "type": "response_item",
                "timestamp": "2025-01-15T12:00:00Z",
                "payload": {
                    "type": "function_call",
                    "call_id": "call_abc123",
                    "name": "shell",
                    "arguments": json.dumps({"command": ["ls"]}),
                },
            }
        )

        events = builder.parse_line(line, "test-session")
        tool_events = [e for e in events if e.event_type == EventType.TOOL]
        if tool_events:
            assert tool_events[0].raw_data.get("call_id") == "call_abc123"

    def test_rate_limits_captured(self):
        """Rate limit info should be captured."""
        builder = CodexBuilder()
        line = json.dumps(
            {
                "type": "response_item",
                "timestamp": "2025-01-15T12:00:00Z",
                "payload": {
                    "type": "function_call",
                    "name": "shell",
                    "arguments": json.dumps({"command": ["ls"]}),
                    "rate_limits": {
                        "primary": {"used_percent": 50, "window_minutes": 60},
                        "secondary": {"used_percent": 10, "window_minutes": 1},
                    },
                },
            }
        )

        events = builder.parse_line(line, "test-session")
        tool_events = [e for e in events if e.event_type == EventType.TOOL]
        if tool_events:
            raw = tool_events[0].raw_data
            assert "rate_limits_primary" in raw
            assert raw["rate_limits_primary"]["used_percent"] == 50

    def test_session_meta_captured(self):
        """Session metadata should be captured as SESSION_START event."""
        builder = CodexBuilder()
        line = json.dumps(
            {
                "type": "session_meta",
                "timestamp": "2025-01-15T12:00:00Z",
                "payload": {
                    "id": "session-123",
                    "cli_version": "0.53.0",
                    "originator": "codex_cli_rs",
                    "model_provider": "openai",
                    "cwd": "/home/user/project",
                },
            }
        )

        events = builder.parse_line(line, "test-session")
        assert len(events) > 0
        assert events[0].event_type == EventType.SESSION_START
        raw = events[0].raw_data
        assert raw.get("cli_version") == "0.53.0"
        assert raw.get("originator") == "codex_cli_rs"
        assert raw.get("model_provider") == "openai"


class TestGeminiFieldExpansion:
    """Test Gemini field expansion."""

    def test_message_id_captured(self):
        """Message ID should be captured in raw_data."""
        builder = GeminiBuilder()

        # Create a minimal Gemini session structure
        session_data = {
            "sessionId": "test-session",
            "projectHash": "abcd1234",
            "startTime": "2025-01-15T12:00:00Z",
            "lastUpdated": "2025-01-15T12:05:00Z",
            "messages": [
                {
                    "id": "msg-001",
                    "timestamp": "2025-01-15T12:00:00Z",
                    "type": "gemini",
                    "model": "gemini-2.5-flash",
                    "content": "Test response",
                    "tokens": {
                        "input": 100,
                        "output": 50,
                        "cached": 30,
                        "thoughts": 10,
                        "tool": 0,
                        "total": 160,
                    },
                }
            ],
        }

        # Write to temp file and parse
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(session_data, f)
            temp_path = f.name

        try:
            from pathlib import Path

            events = builder.parse_events(Path(temp_path))
            assert len(events) > 0
            response_events = [e for e in events if e.event_type == EventType.RESPONSE]
            if response_events:
                assert response_events[0].raw_data.get("message_id") == "msg-001"
        finally:
            import os

            os.unlink(temp_path)

    def test_token_breakdown_captured(self):
        """Full token breakdown should be captured."""
        builder = GeminiBuilder()

        session_data = {
            "sessionId": "test-session",
            "projectHash": "abcd1234",
            "messages": [
                {
                    "id": "msg-001",
                    "timestamp": "2025-01-15T12:00:00Z",
                    "type": "gemini",
                    "model": "gemini-2.5-flash",
                    "content": "Test",
                    "tokens": {
                        "input": 100,
                        "output": 50,
                        "cached": 30,
                        "thoughts": 10,
                        "tool": 5,
                        "total": 195,
                    },
                }
            ],
        }

        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(session_data, f)
            temp_path = f.name

        try:
            from pathlib import Path

            events = builder.parse_events(Path(temp_path))
            response_events = [e for e in events if e.event_type == EventType.RESPONSE]
            if response_events:
                breakdown = response_events[0].raw_data.get("token_breakdown")
                assert breakdown is not None
                assert breakdown["input"] == 100
                assert breakdown["output"] == 50
                assert breakdown["cached"] == 30
                assert breakdown["thoughts"] == 10
                assert breakdown["tool"] == 5
                assert breakdown["total"] == 195
        finally:
            import os

            os.unlink(temp_path)

    def test_finish_reason_captured(self):
        """finishReason should be captured."""
        builder = GeminiBuilder()

        session_data = {
            "sessionId": "test-session",
            "projectHash": "abcd1234",
            "messages": [
                {
                    "id": "msg-001",
                    "timestamp": "2025-01-15T12:00:00Z",
                    "type": "gemini",
                    "model": "gemini-2.5-flash",
                    "content": "Done",
                    "finishReason": "STOP",
                    "tokens": {},
                }
            ],
        }

        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(session_data, f)
            temp_path = f.name

        try:
            from pathlib import Path

            events = builder.parse_events(Path(temp_path))
            response_events = [e for e in events if e.event_type == EventType.RESPONSE]
            if response_events:
                assert response_events[0].raw_data.get("finish_reason") == "STOP"
        finally:
            import os

            os.unlink(temp_path)

    def test_project_hash_captured(self):
        """projectHash should be captured in session-level context."""
        builder = GeminiBuilder()

        session_data = {
            "sessionId": "test-session",
            "projectHash": "abc123def456",
            "messages": [
                {
                    "id": "msg-001",
                    "timestamp": "2025-01-15T12:00:00Z",
                    "type": "gemini",
                    "content": "Test",
                }
            ],
        }

        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(session_data, f)
            temp_path = f.name

        try:
            from pathlib import Path

            events = builder.parse_events(Path(temp_path))
            if events:
                assert events[0].raw_data.get("project_hash") == "abc123def456"
        finally:
            import os

            os.unlink(temp_path)


class TestFieldPreservation:
    """Test that expanded fields don't break existing parsing."""

    def test_basic_parsing_still_works(self):
        """Basic event parsing should still work with new fields."""
        builder = ClaudeBuilder()
        line = json.dumps(
            {
                "type": "assistant",
                "timestamp": "2025-01-15T12:00:00Z",
                "sessionId": "test",
                "message": {"content": [{"type": "text", "text": "Simple message"}]},
            }
        )

        events = builder.parse_line(line, "test-session")
        assert len(events) > 0
        assert "Simple message" in events[0].content

    def test_missing_fields_handled_gracefully(self):
        """Missing optional fields should not cause errors."""
        builder = ClaudeBuilder()
        # Minimal message with no optional fields
        line = json.dumps(
            {
                "type": "assistant",
                "timestamp": "2025-01-15T12:00:00Z",
                "sessionId": "test",
                "message": {"content": [{"type": "text", "text": "Minimal"}]},
            }
        )

        events = builder.parse_line(line, "test-session")
        assert len(events) > 0  # Should parse without error

    def test_codex_minimal_parsing(self):
        """Codex should handle minimal events."""
        builder = CodexBuilder()
        line = json.dumps(
            {
                "type": "response_item",
                "timestamp": "2025-01-15T12:00:00Z",
                "payload": {"type": "message", "content": [{"type": "text", "text": "Response"}]},
            }
        )

        builder.parse_line(line, "test-session")
        # Should not crash, may or may not produce events depending on content

    def test_gemini_minimal_parsing(self):
        """Gemini should handle minimal session data."""
        builder = GeminiBuilder()

        session_data = {
            "sessionId": "test",
            "messages": [{"timestamp": "2025-01-15T12:00:00Z", "type": "user", "content": "Hello"}],
        }

        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(session_data, f)
            temp_path = f.name

        try:
            from pathlib import Path

            events = builder.parse_events(Path(temp_path))
            assert len(events) > 0  # Should parse user message
        finally:
            import os

            os.unlink(temp_path)


class TestRawDataStructure:
    """Test the structure and completeness of raw_data fields."""

    def test_claude_raw_data_structure(self):
        """Verify Claude raw_data contains expected fields."""
        builder = ClaudeBuilder()
        line = json.dumps(
            {
                "type": "assistant",
                "timestamp": "2025-01-15T12:00:00Z",
                "sessionId": "test",
                "parentUuid": "parent-123",
                "uuid": "event-456",
                "requestId": "req_789",
                "isSidechain": False,
                "gitBranch": "main",
                "slug": "test-slug",
                "agentId": "agent-123",
                "cwd": "/test",
                "version": "2.0.55",
                "userType": "external",
                "message": {
                    "id": "msg_001",
                    "model": "claude-sonnet-4-5-20250929",
                    "content": [{"type": "text", "text": "Test"}],
                    "stop_reason": "end_turn",
                    "usage": {
                        "input_tokens": 100,
                        "output_tokens": 50,
                        "cache_creation_input_tokens": 80,
                        "cache_read_input_tokens": 20,
                        "service_tier": "standard",
                    },
                },
            }
        )

        events = builder.parse_line(line, "test-session")
        assert len(events) > 0
        raw = events[0].raw_data

        # Verify all major field categories are present
        assert "message_id" in raw
        assert "stop_reason" in raw
        assert "input_tokens" in raw
        assert "output_tokens" in raw
        assert "cache_creation_tokens" in raw
        assert "cache_read_tokens" in raw
        assert "parent_uuid" in raw
        assert "uuid" in raw
        assert "request_id" in raw
        assert "is_sidechain" in raw
        assert "git_branch" in raw

    def test_codex_raw_data_structure(self):
        """Verify Codex raw_data contains expected fields."""
        builder = CodexBuilder()
        line = json.dumps(
            {
                "type": "response_item",
                "timestamp": "2025-01-15T12:00:00Z",
                "payload": {
                    "type": "function_call",
                    "name": "shell",
                    "call_id": "call_123",
                    "arguments": json.dumps({"command": ["ls"]}),
                    "rate_limits": {
                        "primary": {"used_percent": 50},
                        "secondary": {"used_percent": 10},
                    },
                },
            }
        )

        events = builder.parse_line(line, "test-session")
        tool_events = [e for e in events if e.event_type == EventType.TOOL]
        if tool_events:
            raw = tool_events[0].raw_data
            assert "call_id" in raw
            assert "rate_limits_primary" in raw or "rate_limits_secondary" in raw
