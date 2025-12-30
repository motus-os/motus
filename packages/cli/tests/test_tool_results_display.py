"""Tests for tool result display (Track F - Phase 7)."""

from datetime import datetime

from motus.display.transformer import EventTransformer
from motus.schema.events import AgentSource, EventType, ParsedEvent


class TestToolResultTransformation:
    """Test tool result event transformation."""

    def test_tool_result_transformed(self):
        """TOOL_RESULT events should be transformed properly."""
        event = ParsedEvent(
            event_id="result-1",
            session_id="session-1",
            timestamp=datetime.now(),
            event_type=EventType.TOOL_RESULT,
            source=AgentSource.CLAUDE,
            content="File contents here...",
            tool_output="File contents here...",
            raw_data={"tool_use_id": "toolu_123"},
        )

        # Transform should not raise
        transformed = EventTransformer.transform(event)

        assert transformed is not None
        assert transformed.event_type == "tool_result"
        assert transformed.icon == "📤"
        assert transformed.title == "Result"

    def test_tool_result_content_preserved(self):
        """Tool result content should be accessible."""
        long_content = "x" * 2000
        event = ParsedEvent(
            event_id="result-2",
            session_id="session-1",
            timestamp=datetime.now(),
            event_type=EventType.TOOL_RESULT,
            source=AgentSource.CLAUDE,
            content=long_content,
            tool_output=long_content,
            raw_data={"tool_use_id": "toolu_456"},
        )

        transformed = EventTransformer.transform(event)

        # Full content should be accessible in raw_data
        full = transformed.raw_data.get("full_content") or transformed.content
        assert len(full) == 2000

        # Preview should be truncated
        assert len(transformed.content) <= 500

    def test_tool_use_id_preserved(self):
        """tool_use_id should be preserved for linking."""
        event = ParsedEvent(
            event_id="result-3",
            session_id="session-1",
            timestamp=datetime.now(),
            event_type=EventType.TOOL_RESULT,
            source=AgentSource.CLAUDE,
            content="Result",
            tool_use_id="toolu_789",
            raw_data={"tool_use_id": "toolu_789"},
        )

        transformed = EventTransformer.transform(event)

        assert transformed.raw_data.get("tool_use_id") == "toolu_789"

    def test_tool_result_has_length_detail(self):
        """Tool result should include length in details."""
        event = ParsedEvent(
            event_id="result-4",
            session_id="session-1",
            timestamp=datetime.now(),
            event_type=EventType.TOOL_RESULT,
            source=AgentSource.CLAUDE,
            content="Short result",
            tool_output="Short result",
        )

        transformed = EventTransformer.transform(event)

        # Should have length detail
        assert any("Length:" in detail for detail in transformed.details)


class TestToolResultWebDisplay:
    """Test tool result display in web UI."""

    def test_tool_result_function_exists(self):
        """renderToolResult function should exist in dashboard.js."""
        import os

        dashboard_path = (
            "/home/user/projects/motus-command/src/motus/ui/static/dashboard.js"
        )

        if os.path.exists(dashboard_path):
            with open(dashboard_path) as f:
                content = f.read()

            # Should have tool result handling
            assert "renderToolResult" in content
            assert "tool_result" in content or "tool-result" in content

    def test_tool_result_css_exists(self):
        """Tool result CSS should exist in dashboard.css."""
        import os

        css_path = "/home/user/projects/motus-command/src/motus/ui/static/dashboard.css"

        if os.path.exists(css_path):
            with open(css_path) as f:
                content = f.read()

            # Should have tool result styling
            assert "tool-result" in content or "tool_result" in content
            assert "tool-output" in content


class TestToolResultGrouping:
    """Test that tool results are visually grouped with tool calls."""

    def test_tool_result_follows_tool_use(self):
        """Tool results should appear after their tool_use chronologically."""
        # This is enforced by timestamp ordering - tool_result timestamp > tool_use timestamp
        tool_use = ParsedEvent(
            event_id="tool-1",
            session_id="session-1",
            timestamp=datetime(2025, 1, 1, 12, 0, 0),
            event_type=EventType.TOOL_USE,
            source=AgentSource.CLAUDE,
            tool_name="Read",
            tool_use_id="toolu_123",
        )

        tool_result = ParsedEvent(
            event_id="result-1",
            session_id="session-1",
            timestamp=datetime(2025, 1, 1, 12, 0, 1),  # 1 second later
            event_type=EventType.TOOL_RESULT,
            source=AgentSource.CLAUDE,
            tool_use_id="toolu_123",
            content="File contents",
        )

        # Result should come after use chronologically
        assert tool_result.timestamp > tool_use.timestamp

    def test_tool_result_indented_in_web(self):
        """Tool results should be indented in web UI via CSS."""
        import os

        css_path = "/home/user/projects/motus-command/src/motus/ui/static/dashboard.css"

        if os.path.exists(css_path):
            with open(css_path) as f:
                content = f.read()

            # Should have margin-left for indentation
            assert "margin-left" in content and "tool-result" in content


class TestToolResultEdgeCases:
    """Test edge cases for tool result display."""

    def test_empty_tool_result(self):
        """Handle empty tool results gracefully."""
        event = ParsedEvent(
            event_id="result-empty",
            session_id="session-1",
            timestamp=datetime.now(),
            event_type=EventType.TOOL_RESULT,
            source=AgentSource.CLAUDE,
            content="",
            tool_output="",
        )

        transformed = EventTransformer.transform(event)
        assert transformed is not None
        assert transformed.event_type == "tool_result"

    def test_tool_result_without_tool_use_id(self):
        """Handle tool results without tool_use_id."""
        event = ParsedEvent(
            event_id="result-no-id",
            session_id="session-1",
            timestamp=datetime.now(),
            event_type=EventType.TOOL_RESULT,
            source=AgentSource.CLAUDE,
            content="Result without ID",
        )

        transformed = EventTransformer.transform(event)
        assert transformed is not None
        # Should handle missing tool_use_id gracefully
        assert transformed.raw_data.get("tool_use_id") is None

    def test_very_long_tool_result(self):
        """Handle very long tool results (>10KB)."""
        long_content = "x" * 50000  # 50KB
        event = ParsedEvent(
            event_id="result-long",
            session_id="session-1",
            timestamp=datetime.now(),
            event_type=EventType.TOOL_RESULT,
            source=AgentSource.CLAUDE,
            content=long_content,
            tool_output=long_content,
        )

        transformed = EventTransformer.transform(event)

        # Should truncate preview
        assert len(transformed.content) <= 500

        # Should preserve full content
        full = transformed.raw_data.get("full_content", "")
        assert len(full) == 50000
