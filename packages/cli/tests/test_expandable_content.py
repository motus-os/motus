"""Tests for expandable content functionality."""

from datetime import datetime

from motus.display.events import DisplayEvent
from motus.display.transformer import EventTransformer
from motus.schema.events import AgentSource, EventType, ParsedEvent


class TestTransformerContentPreservation:
    """Test that transformer preserves full content."""

    def test_short_content_unchanged(self):
        """Content under 200 chars should have no full_content."""
        event = ParsedEvent(
            event_id="test-1",
            session_id="session-1",
            timestamp=datetime.now(),
            event_type=EventType.THINKING,
            source=AgentSource.CLAUDE,
            content="Short content here",
        )

        transformed = EventTransformer.transform(event)
        assert len(transformed.details) > 0
        assert "Short content here" in transformed.details[0]
        # Short content should not have full_content field populated
        assert transformed.full_content is None

    def test_long_content_preview_created(self):
        """Content over 200 chars should have preview in details."""
        long_content = "x" * 500
        event = ParsedEvent(
            event_id="test-2",
            session_id="session-1",
            timestamp=datetime.now(),
            event_type=EventType.THINKING,
            source=AgentSource.CLAUDE,
            content=long_content,
        )

        transformed = EventTransformer.transform(event)
        # Preview should be truncated in details
        assert len(transformed.details) > 0
        preview = transformed.details[0]
        assert len(preview) <= 203  # 200 + "..."
        assert preview.endswith("...")

    def test_full_content_accessible(self):
        """Full content should be accessible via full_content field."""
        long_content = "y" * 1000
        event = ParsedEvent(
            event_id="test-3",
            session_id="session-1",
            timestamp=datetime.now(),
            event_type=EventType.THINKING,
            source=AgentSource.CLAUDE,
            content=long_content,
        )

        transformed = EventTransformer.transform(event)

        # Full content should be in full_content field
        assert transformed.full_content is not None
        assert len(transformed.full_content) == 1000

    def test_spawn_event_preserves_long_prompt(self):
        """Spawn events with long prompts should preserve full content."""
        long_prompt = "z" * 300
        event = ParsedEvent(
            event_id="test-4",
            session_id="session-1",
            timestamp=datetime.now(),
            event_type=EventType.AGENT_SPAWN,
            source=AgentSource.CLAUDE,
            raw_data={
                "model": "claude-3-5-sonnet",
                "description": "Test agent",
                "prompt": long_prompt,
            },
        )

        transformed = EventTransformer.transform(event)

        # Full prompt should be accessible
        assert transformed.full_content is not None
        assert len(transformed.full_content) == 300

    def test_spawn_event_short_prompt_no_full_content(self):
        """Spawn events with short prompts should not have full_content."""
        short_prompt = "Brief task"
        event = ParsedEvent(
            event_id="test-5",
            session_id="session-1",
            timestamp=datetime.now(),
            event_type=EventType.AGENT_SPAWN,
            source=AgentSource.CLAUDE,
            raw_data={
                "model": "claude-3-5-sonnet",
                "description": "Test agent",
                "prompt": short_prompt,
            },
        )

        transformed = EventTransformer.transform(event)

        # Short prompt should not have full_content
        assert transformed.full_content is None


class TestWebExpandFunctionality:
    """Test web expand/collapse functions exist."""

    def test_toggle_content_function_exists(self):
        """toggleContentExpand JavaScript function should be defined."""
        from pathlib import Path

        dashboard_path = Path(__file__).parent.parent / "src" / "motus" / "ui" / "static" / "dashboard.js"

        if dashboard_path.exists():
            content = dashboard_path.read_text()
            assert "toggleContentExpand" in content

    def test_expand_btn_class_in_css(self):
        """expand-btn CSS class should be defined."""
        from pathlib import Path

        css_path = Path(__file__).parent.parent / "src" / "motus" / "ui" / "static" / "dashboard.css"

        if css_path.exists():
            content = css_path.read_text()
            assert ".expand-btn" in content

    def test_expandable_content_class_in_css(self):
        """expandable-content CSS class should be defined."""
        from pathlib import Path

        css_path = Path(__file__).parent.parent / "src" / "motus" / "ui" / "static" / "dashboard.css"

        if css_path.exists():
            content = css_path.read_text()
            assert ".expandable-content" in content


class TestDisplayEventFullContent:
    """Test DisplayEvent full_content field."""

    def test_display_event_has_full_content_field(self):
        """DisplayEvent should have full_content field."""
        from motus.display.events import DisplayRiskLevel

        event = DisplayEvent(
            event_id="test-1",
            session_id="session-1",
            short_session_id="session1",
            timestamp_display="12:00:00",
            event_type="thinking",
            risk_level=DisplayRiskLevel.NONE,
            icon="💭",
            title="Thinking",
            details=["Preview"],
            full_content="Full content here",
        )

        assert hasattr(event, "full_content")
        assert event.full_content == "Full content here"

    def test_display_event_full_content_optional(self):
        """DisplayEvent full_content should be optional."""
        from motus.display.events import DisplayRiskLevel

        event = DisplayEvent(
            event_id="test-1",
            session_id="session-1",
            short_session_id="session1",
            timestamp_display="12:00:00",
            event_type="thinking",
            risk_level=DisplayRiskLevel.NONE,
            icon="💭",
            title="Thinking",
            details=["Content"],
        )

        assert hasattr(event, "full_content")
        assert event.full_content is None
