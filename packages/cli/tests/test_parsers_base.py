"""Tests for the parser base interface.

This module tests the BaseParser abstract base class to ensure:
- It cannot be instantiated directly
- Subclasses must implement abstract methods
- safe_parse() error handling works correctly
- can_parse() delegation works as expected
"""

from datetime import datetime
from unittest.mock import patch

import pytest

from motus.parsers import BaseParser
from motus.schema import AgentSource, EventType, ParsedEvent

# Fixed test values for deterministic tests
FIXED_TIMESTAMP = datetime(2025, 1, 15, 12, 0, 0)
FIXED_EVENT_ID = "test-event-001"


class TestBaseParserAbstract:
    """Test that BaseParser enforces abstract interface."""

    def test_cannot_instantiate_directly(self):
        """BaseParser cannot be instantiated without implementing abstract methods."""
        with pytest.raises(TypeError) as exc_info:
            BaseParser()

        # Should mention abstract methods
        error_msg = str(exc_info.value)
        assert "abstract" in error_msg.lower()

    def test_subclass_must_implement_can_parse(self):
        """Subclass must implement can_parse() method."""

        class IncompleteParser(BaseParser):
            source = AgentSource.CLAUDE

            def parse(self, raw_data: dict) -> ParsedEvent | None:
                return None

        with pytest.raises(TypeError) as exc_info:
            IncompleteParser()

        error_msg = str(exc_info.value)
        assert "can_parse" in error_msg

    def test_subclass_must_implement_parse(self):
        """Subclass must implement parse() method."""

        class IncompleteParser(BaseParser):
            source = AgentSource.CLAUDE

            def can_parse(self, raw_data: dict) -> bool:
                return True

        with pytest.raises(TypeError) as exc_info:
            IncompleteParser()

        error_msg = str(exc_info.value)
        assert "parse" in error_msg

    def test_complete_subclass_can_be_instantiated(self):
        """Subclass with all methods implemented can be instantiated."""

        class CompleteParser(BaseParser):
            source = AgentSource.CLAUDE

            def can_parse(self, raw_data: dict) -> bool:
                return True

            def parse(self, raw_data: dict) -> ParsedEvent | None:
                return None

        parser = CompleteParser()
        assert parser.source == AgentSource.CLAUDE


class TestCanParse:
    """Test can_parse() method delegation."""

    def test_can_parse_returns_true(self):
        """can_parse() can return True."""

        class TestParser(BaseParser):
            source = AgentSource.CLAUDE

            def can_parse(self, raw_data: dict) -> bool:
                return raw_data.get("type") == "test"

            def parse(self, raw_data: dict) -> ParsedEvent | None:
                return None

        parser = TestParser()
        assert parser.can_parse({"type": "test"}) is True
        assert parser.can_parse({"type": "other"}) is False

    def test_can_parse_with_complex_logic(self):
        """can_parse() can implement complex validation logic."""

        class TestParser(BaseParser):
            source = AgentSource.CODEX

            def can_parse(self, raw_data: dict) -> bool:
                return (
                    "event_type" in raw_data
                    and "session_id" in raw_data
                    and raw_data.get("source") == "codex"
                )

            def parse(self, raw_data: dict) -> ParsedEvent | None:
                return None

        parser = TestParser()

        # All conditions met
        assert (
            parser.can_parse({"event_type": "tool", "session_id": "123", "source": "codex"}) is True
        )

        # Missing field
        assert parser.can_parse({"event_type": "tool", "source": "codex"}) is False

        # Wrong source
        assert (
            parser.can_parse({"event_type": "tool", "session_id": "123", "source": "claude"})
            is False
        )


class TestParse:
    """Test parse() method."""

    def test_parse_returns_event(self):
        """parse() can return a ParsedEvent."""

        class TestParser(BaseParser):
            source = AgentSource.CLAUDE

            def can_parse(self, raw_data: dict) -> bool:
                return True

            def parse(self, raw_data: dict) -> ParsedEvent | None:
                return ParsedEvent(
                    event_id=FIXED_EVENT_ID,
                    session_id=raw_data["session_id"],
                    event_type=EventType.TOOL_USE,
                    source=self.source,
                    timestamp=FIXED_TIMESTAMP,
                    tool_name=raw_data.get("tool"),
                )

        parser = TestParser()
        raw_data = {
            "session_id": "test-session",
            "tool": "Read",
        }

        event = parser.parse(raw_data)
        assert event is not None
        assert event.session_id == "test-session"
        assert event.event_type == EventType.TOOL_USE
        assert event.source == AgentSource.CLAUDE
        assert event.tool_name == "Read"

    def test_parse_returns_none_to_skip(self):
        """parse() can return None to skip an event."""

        class TestParser(BaseParser):
            source = AgentSource.GEMINI

            def can_parse(self, raw_data: dict) -> bool:
                return True

            def parse(self, raw_data: dict) -> ParsedEvent | None:
                # Skip events marked as internal
                if raw_data.get("internal"):
                    return None
                return ParsedEvent(
                    event_id=FIXED_EVENT_ID,
                    session_id="test",
                    event_type=EventType.TOOL_USE,
                    source=self.source,
                    timestamp=FIXED_TIMESTAMP,
                )

        parser = TestParser()

        # Normal event
        event = parser.parse({"internal": False})
        assert event is not None

        # Skipped event
        event = parser.parse({"internal": True})
        assert event is None

    def test_parse_can_raise_exceptions(self):
        """parse() can raise exceptions for invalid data."""

        class TestParser(BaseParser):
            source = AgentSource.CLAUDE

            def can_parse(self, raw_data: dict) -> bool:
                return True

            def parse(self, raw_data: dict) -> ParsedEvent | None:
                # Require session_id field
                if "session_id" not in raw_data:
                    raise ValueError("session_id is required")
                return ParsedEvent(
                    event_id=FIXED_EVENT_ID,
                    session_id=raw_data["session_id"],
                    event_type=EventType.TOOL_USE,
                    source=self.source,
                    timestamp=FIXED_TIMESTAMP,
                )

        parser = TestParser()

        # Valid data
        event = parser.parse({"session_id": "123"})
        assert event is not None

        # Invalid data
        with pytest.raises(ValueError) as exc_info:
            parser.parse({})
        assert "session_id is required" in str(exc_info.value)


class TestSafeParse:
    """Test safe_parse() error handling."""

    def test_safe_parse_success(self):
        """safe_parse() returns event when parse() succeeds."""

        class TestParser(BaseParser):
            source = AgentSource.CLAUDE

            def can_parse(self, raw_data: dict) -> bool:
                return True

            def parse(self, raw_data: dict) -> ParsedEvent | None:
                return ParsedEvent(
                    event_id=FIXED_EVENT_ID,
                    session_id="test-session",
                    event_type=EventType.TOOL_USE,
                    source=self.source,
                    timestamp=FIXED_TIMESTAMP,
                )

        parser = TestParser()
        event = parser.safe_parse({"type": "tool"})

        assert event is not None
        assert event.session_id == "test-session"

    def test_safe_parse_returns_none_when_parse_returns_none(self):
        """safe_parse() returns None when parse() returns None."""

        class TestParser(BaseParser):
            source = AgentSource.CLAUDE

            def can_parse(self, raw_data: dict) -> bool:
                return True

            def parse(self, raw_data: dict) -> ParsedEvent | None:
                return None

        parser = TestParser()
        event = parser.safe_parse({"type": "skip"})

        assert event is None

    @patch("motus.parsers.base.logger")
    def test_safe_parse_catches_value_error(self, mock_logger):
        """safe_parse() catches ValueError and returns None."""

        class TestParser(BaseParser):
            source = AgentSource.CLAUDE

            def can_parse(self, raw_data: dict) -> bool:
                return True

            def parse(self, raw_data: dict) -> ParsedEvent | None:
                raise ValueError("Invalid data")

        parser = TestParser()
        event = parser.safe_parse({"bad": "data"})

        # Should return None
        assert event is None

        # Should log error with structured logging
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert call_args[0][0] == "Failed to parse event"
        assert call_args[1]["source"] == "claude"
        assert call_args[1]["exc_info"] is True
        assert call_args[1]["error_type"] == "ValueError"
        assert call_args[1]["error"] == "Invalid data"

    @patch("motus.parsers.base.logger")
    def test_safe_parse_catches_key_error(self, mock_logger):
        """safe_parse() catches KeyError and returns None."""

        class TestParser(BaseParser):
            source = AgentSource.CODEX

            def can_parse(self, raw_data: dict) -> bool:
                return True

            def parse(self, raw_data: dict) -> ParsedEvent | None:
                # Access missing key
                return ParsedEvent(
                    session_id=raw_data["missing_key"],
                    event_type=EventType.TOOL_USE,
                    source=self.source,
                )

        parser = TestParser()
        event = parser.safe_parse({})

        # Should return None
        assert event is None

        # Should log error with structured logging
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert call_args[0][0] == "Failed to parse event"
        assert call_args[1]["source"] == "codex"
        assert call_args[1]["error_type"] == "KeyError"

    @patch("motus.parsers.base.logger")
    def test_safe_parse_catches_type_error(self, mock_logger):
        """safe_parse() catches TypeError and returns None."""

        class TestParser(BaseParser):
            source = AgentSource.GEMINI

            def can_parse(self, raw_data: dict) -> bool:
                return True

            def parse(self, raw_data: dict) -> ParsedEvent | None:
                # Cause a TypeError
                return None + "string"  # type: ignore

        parser = TestParser()
        event = parser.safe_parse({"data": "test"})

        # Should return None
        assert event is None

        # Should log error with structured logging
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert call_args[0][0] == "Failed to parse event"
        assert call_args[1]["source"] == "gemini"
        assert call_args[1]["error_type"] == "TypeError"

    def test_safe_parse_propagates_unexpected_exceptions(self):
        """safe_parse() lets unexpected exceptions propagate."""

        class TestParser(BaseParser):
            source = AgentSource.GEMINI

            def can_parse(self, raw_data: dict) -> bool:
                return True

            def parse(self, raw_data: dict) -> ParsedEvent | None:
                raise RuntimeError("Unexpected system error")

        parser = TestParser()

        # RuntimeError is not in the caught exceptions, so it should propagate
        with pytest.raises(RuntimeError, match="Unexpected system error"):
            parser.safe_parse({"data": "test"})

    @patch("motus.parsers.base.logger")
    def test_safe_parse_logs_raw_data_type(self, mock_logger):
        """safe_parse() logs the type of raw_data in error."""

        class TestParser(BaseParser):
            source = AgentSource.CLAUDE

            def can_parse(self, raw_data: dict) -> bool:
                return True

            def parse(self, raw_data: dict) -> ParsedEvent | None:
                raise ValueError("Test error")

        parser = TestParser()
        parser.safe_parse({"test": "data"})

        call_args = mock_logger.error.call_args
        assert call_args[1]["raw_data_type"] == "dict"


class TestParserSource:
    """Test parser source attribute."""

    def test_source_attribute_required(self):
        """Parser must define source attribute."""

        class TestParser(BaseParser):
            source = AgentSource.CLAUDE

            def can_parse(self, raw_data: dict) -> bool:
                return True

            def parse(self, raw_data: dict) -> ParsedEvent | None:
                return None

        parser = TestParser()
        assert hasattr(parser, "source")
        assert parser.source == AgentSource.CLAUDE

    def test_different_sources(self):
        """Different parsers can have different sources."""

        class ClaudeParser(BaseParser):
            source = AgentSource.CLAUDE

            def can_parse(self, raw_data: dict) -> bool:
                return True

            def parse(self, raw_data: dict) -> ParsedEvent | None:
                return None

        class CodexParser(BaseParser):
            source = AgentSource.CODEX

            def can_parse(self, raw_data: dict) -> bool:
                return True

            def parse(self, raw_data: dict) -> ParsedEvent | None:
                return None

        claude_parser = ClaudeParser()
        codex_parser = CodexParser()

        assert claude_parser.source == AgentSource.CLAUDE
        assert codex_parser.source == AgentSource.CODEX
        assert claude_parser.source != codex_parser.source
