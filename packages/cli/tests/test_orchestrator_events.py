"""Tests for orchestrator/events.py module."""

import json
from pathlib import Path
from unittest.mock import MagicMock

from motus.orchestrator.events import (
    load_events,
    load_events_tail,
    load_events_tail_validated,
    load_events_validated,
)
from motus.protocols import Source, UnifiedSession
from motus.schema.events import ParsedEvent


class TestLoadEvents:
    """Test load_events function."""

    def test_load_events_from_cache(self):
        """Test loading events from cache."""
        # Create mock session
        session = MagicMock(spec=UnifiedSession)
        session.session_id = "test-session"
        session.file_path = Path("/tmp/test.jsonl")

        # Create mock builder
        builder = MagicMock()

        # Create mock cache with cached data
        cache = MagicMock()
        cached_events = [MagicMock(), MagicMock()]
        cache.get_events.return_value = cached_events

        result = load_events(session, builder, cache, refresh=False)

        assert result == cached_events
        cache.get_events.assert_called_once_with("test-session")
        # Builder should not be called when cache hit
        builder.parse_events.assert_not_called()

    def test_load_events_cache_miss(self, tmp_path):
        """Test loading events when cache misses."""
        # Create test file
        test_file = tmp_path / "test.jsonl"
        test_file.write_text('{"type": "test"}\n')

        # Create mock session
        session = MagicMock(spec=UnifiedSession)
        session.session_id = "test-session"
        session.file_path = test_file

        # Create mock builder
        builder = MagicMock()
        parsed_events = [MagicMock(), MagicMock()]
        builder.parse_events.return_value = parsed_events

        # Create mock cache (empty)
        cache = MagicMock()
        cache.get_events.return_value = None

        result = load_events(session, builder, cache, refresh=False)

        assert result == parsed_events
        builder.parse_events.assert_called_once_with(test_file)
        cache.set_events.assert_called_once_with("test-session", parsed_events)
        cache.prune_caches.assert_called_once()

    def test_load_events_refresh(self, tmp_path):
        """Test loading events with refresh=True bypasses cache."""
        # Create test file
        test_file = tmp_path / "test.jsonl"
        test_file.write_text('{"type": "test"}\n')

        # Create mock session
        session = MagicMock(spec=UnifiedSession)
        session.session_id = "test-session"
        session.file_path = test_file

        # Create mock builder
        builder = MagicMock()
        parsed_events = [MagicMock()]
        builder.parse_events.return_value = parsed_events

        # Create mock cache
        cache = MagicMock()
        cache.get_events.return_value = [MagicMock(), MagicMock()]  # Cached data

        result = load_events(session, builder, cache, refresh=True)

        # Should not call get_events when refresh=True
        cache.get_events.assert_not_called()
        assert result == parsed_events

    def test_load_events_no_builder(self):
        """Test loading events with no builder returns empty list."""
        session = MagicMock(spec=UnifiedSession)
        session.session_id = "test-session"
        cache = MagicMock()
        cache.get_events.return_value = None

        result = load_events(session, None, cache, refresh=False)

        assert result == []

    def test_load_events_error_handling(self, tmp_path):
        """Test loading events handles parsing errors."""
        # Create test file
        test_file = tmp_path / "test.jsonl"
        test_file.write_text("invalid json\n")

        # Create mock session
        session = MagicMock(spec=UnifiedSession)
        session.session_id = "test-session"
        session.file_path = test_file

        # Create mock builder that raises exception
        builder = MagicMock()
        builder.parse_events.side_effect = Exception("Parse error")

        # Create mock cache
        cache = MagicMock()
        cache.get_events.return_value = None

        result = load_events(session, builder, cache, refresh=False)

        # Should return empty list on error
        assert result == []


class TestLoadEventsTail:
    """Test load_events_tail function."""

    def test_load_events_tail_claude(self, tmp_path):
        """Test loading tail events for Claude (JSONL) session."""
        # Create test file
        test_file = tmp_path / "test.jsonl"
        test_file.write_text('{"type": "line1"}\n{"type": "line2"}\n{"type": "line3"}\n')

        # Create mock session
        session = MagicMock(spec=UnifiedSession)
        session.session_id = "test-session"
        session.file_path = test_file
        session.source = Source.CLAUDE

        # Create mock builder
        builder = MagicMock()
        builder.parse_line.return_value = [MagicMock()]

        result = load_events_tail(session, builder, n_lines=2)

        # Should call parse_line for each line
        assert isinstance(result, list)

    def test_load_events_tail_gemini(self, tmp_path):
        """Test loading tail events for Gemini (JSON) session."""
        # Create test file
        test_file = tmp_path / "test.json"
        test_file.write_text(json.dumps({"messages": [{"type": "test"}]}))

        # Create mock session
        session = MagicMock(spec=UnifiedSession)
        session.session_id = "test-session"
        session.file_path = test_file
        session.source = Source.GEMINI

        # Create mock builder
        builder = MagicMock()
        all_events = [MagicMock(), MagicMock(), MagicMock()]
        builder.parse_events.return_value = all_events

        result = load_events_tail(session, builder, n_lines=2)

        # For Gemini, should parse all and slice
        assert len(result) == 2
        assert result == all_events[-2:]

    def test_load_events_tail_no_builder(self):
        """Test loading tail events with no builder returns empty list."""
        session = MagicMock(spec=UnifiedSession)
        session.session_id = "test-session"
        session.source = Source.CLAUDE

        result = load_events_tail(session, None, n_lines=100)

        assert result == []

    def test_load_events_tail_error_handling(self, tmp_path):
        """Test loading tail events handles errors."""
        # Create test file
        test_file = tmp_path / "test.jsonl"
        test_file.write_text("invalid json\n")

        # Create mock session
        session = MagicMock(spec=UnifiedSession)
        session.session_id = "test-session"
        session.file_path = test_file
        session.source = Source.CLAUDE

        # Create mock builder that raises exception
        builder = MagicMock()
        builder.parse_line.side_effect = Exception("Parse error")

        result = load_events_tail(session, builder, n_lines=10)

        # Should return empty list on error
        assert result == []


class TestLoadEventsValidated:
    """Test load_events_validated function."""

    def test_load_events_validated_success(self, tmp_path):
        """Test loading and validating events successfully."""
        # Create test file
        test_file = tmp_path / "test.jsonl"
        test_file.write_text('{"type": "test"}\n')

        # Create mock session
        session = MagicMock(spec=UnifiedSession)
        session.session_id = "test-session"
        session.file_path = test_file

        # Create mock builder
        builder = MagicMock()
        # Mock the return value as a list of ParsedEvent-like objects
        mock_event = MagicMock(spec=ParsedEvent)
        builder.parse_events_validated.return_value = [mock_event]

        # Create mock cache
        cache = MagicMock()
        cache.get_parsed_events.return_value = None

        result = load_events_validated(session, builder, cache, refresh=False)

        # Should call parse_events_validated and return results
        assert len(result) == 1
        builder.parse_events_validated.assert_called_once_with(test_file)

    def test_load_events_validated_empty(self):
        """Test loading validated events returns empty on no events."""
        session = MagicMock(spec=UnifiedSession)
        session.session_id = "test-session"
        cache = MagicMock()
        cache.get_parsed_events.return_value = None

        result = load_events_validated(session, None, cache, refresh=False)

        assert result == []


class TestLoadEventsTailValidated:
    """Test load_events_tail_validated function."""

    def test_load_events_tail_validated_success(self, tmp_path):
        """Test loading and validating tail events successfully."""
        # Create test file
        test_file = tmp_path / "test.jsonl"
        test_file.write_text('{"type": "line1"}\n{"type": "line2"}\n')

        # Create mock session
        session = MagicMock(spec=UnifiedSession)
        session.session_id = "test-session"
        session.file_path = test_file
        session.source = Source.CLAUDE

        # Create mock builder
        builder = MagicMock()
        builder.parse_line.return_value = [MagicMock()]

        result = load_events_tail_validated(session, builder, n_lines=10)

        assert isinstance(result, list)
        assert all(isinstance(e, ParsedEvent) for e in result)

    def test_load_events_tail_validated_empty(self):
        """Test loading validated tail events returns empty on no events."""
        session = MagicMock(spec=UnifiedSession)
        session.session_id = "test-session"
        session.source = Source.CLAUDE

        result = load_events_tail_validated(session, None, n_lines=10)

        assert result == []
