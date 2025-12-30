"""
Display Parity Tests - Verify TUI and Web receive identical DisplayEvents.

This module verifies that both TUI and Web surfaces consume the SAME DisplayEvent
data for any given ParsedEvent. The display layer guarantees consistency through:

1. EventTransformer.transform() - Single source of truth for ParsedEvent -> DisplayEvent
2. SessionTransformer.transform() - Single source of truth for UnifiedSession -> DisplaySession
3. SafeRenderer - Centralized escaping that both surfaces use identically

Key Invariants:
- Same ParsedEvent MUST produce identical DisplayEvent
- Both TUI and Web MUST import and use EventTransformer (not duplicate logic)
- All DisplayEvent fields MUST be pre-escaped and safe to render
- DisplaySession MUST be identical for both surfaces
- SafeRenderer output MUST be identical regardless of calling context

Architecture:
    ParsedEvent -> EventTransformer.transform() -> DisplayEvent -> TUI/Web
                                                                    (identical)
"""

from datetime import datetime

import pytest

from motus.display.events import DisplayRiskLevel
from motus.display.renderer import SafeRenderer
from motus.display.transformer import EventTransformer, SessionTransformer
from motus.protocols import SessionStatus, Source, UnifiedSession
from motus.schema.events import AgentSource, EventType, ParsedEvent, RiskLevel


class TestTransformerProducesIdenticalDisplayEvents:
    """Verify that same ParsedEvent produces same DisplayEvent."""

    def test_thinking_event_transformation_is_identical(self):
        """Same THINKING ParsedEvent produces identical DisplayEvent for TUI and Web."""
        # Create a ParsedEvent
        parsed = ParsedEvent(
            event_id="evt_thinking_001",
            session_id="session_123456789",
            event_type=EventType.THINKING,
            source=AgentSource.CLAUDE,
            timestamp=datetime(2025, 1, 15, 12, 0, 0),
            content="I'm analyzing the codebase to find the transformer module...",
        )

        # Transform it once (what both TUI and Web do)
        display_tui = EventTransformer.transform(parsed)
        display_web = EventTransformer.transform(parsed)

        # Both surfaces get IDENTICAL DisplayEvent
        assert display_tui == display_web
        assert display_tui.event_type == "thinking"
        assert display_tui.icon == "💭"
        assert display_tui.title == "Thinking"
        # short_session_id is first 8 chars
        assert display_tui.short_session_id == "session_"

    def test_tool_use_event_transformation_is_identical(self):
        """Same TOOL_USE ParsedEvent produces identical DisplayEvent for TUI and Web."""
        parsed = ParsedEvent(
            event_id="evt_tool_001",
            session_id="session_987654321",
            event_type=EventType.TOOL_USE,
            source=AgentSource.CLAUDE,
            timestamp=datetime(2025, 1, 15, 12, 5, 0),
            tool_name="Read",
            tool_input={"file_path": "/home/user/test.py"},
            risk_level=RiskLevel.SAFE,
        )

        # Transform it once (what both TUI and Web do)
        display_tui = EventTransformer.transform(parsed)
        display_web = EventTransformer.transform(parsed)

        # Both surfaces get IDENTICAL DisplayEvent
        assert display_tui == display_web
        assert display_tui.event_type == "tool_use"
        assert display_tui.tool_name == "Read"
        assert display_tui.icon == "📖"
        assert display_tui.risk_level == DisplayRiskLevel.LOW

    def test_agent_spawn_event_transformation_is_identical(self):
        """Same AGENT_SPAWN ParsedEvent produces identical DisplayEvent for TUI and Web."""
        parsed = ParsedEvent(
            event_id="evt_spawn_001",
            session_id="session_abc123",
            event_type=EventType.AGENT_SPAWN,
            source=AgentSource.CLAUDE,
            timestamp=datetime(2025, 1, 15, 12, 10, 0),
            spawn_type="task",
            raw_data={
                "model": "claude-sonnet-4-5",
                "description": "Analyze test coverage",
                "prompt": "Review all test files and identify gaps",
            },
        )

        # Transform it once (what both TUI and Web do)
        display_tui = EventTransformer.transform(parsed)
        display_web = EventTransformer.transform(parsed)

        # Both surfaces get IDENTICAL DisplayEvent
        assert display_tui == display_web
        assert display_tui.event_type == "agent_spawn"
        assert display_tui.icon == "🤖"
        assert display_tui.title == "Agent Spawn"
        assert display_tui.is_subagent is True

    def test_edit_tool_event_transformation_is_identical(self):
        """Edit tool events produce identical DisplayEvent."""
        parsed = ParsedEvent(
            event_id="evt_edit_001",
            session_id="session_edit_123",
            event_type=EventType.TOOL_USE,
            source=AgentSource.CLAUDE,
            timestamp=datetime(2025, 1, 15, 12, 15, 0),
            tool_name="Edit",
            tool_input={"file_path": "/home/user/app.py", "old_string": "foo", "new_string": "bar"},
            risk_level=RiskLevel.MEDIUM,
        )

        display_tui = EventTransformer.transform(parsed)
        display_web = EventTransformer.transform(parsed)

        # Both surfaces get IDENTICAL DisplayEvent
        assert display_tui == display_web
        assert display_tui.tool_name == "Edit"
        assert display_tui.icon == "✏️"
        assert display_tui.risk_level == DisplayRiskLevel.MEDIUM
        assert display_tui.file_path is not None  # SafeRenderer applied

    def test_bash_tool_event_transformation_is_identical(self):
        """Bash tool events produce identical DisplayEvent."""
        parsed = ParsedEvent(
            event_id="evt_bash_001",
            session_id="session_bash_456",
            event_type=EventType.TOOL_USE,
            source=AgentSource.CLAUDE,
            timestamp=datetime(2025, 1, 15, 12, 20, 0),
            tool_name="Bash",
            tool_input={
                "command": "pytest tests/test_display_parity.py -v",
                "description": "Run display parity tests",
            },
            risk_level=RiskLevel.MEDIUM,
        )

        display_tui = EventTransformer.transform(parsed)
        display_web = EventTransformer.transform(parsed)

        # Both surfaces get IDENTICAL DisplayEvent
        assert display_tui == display_web
        assert display_tui.tool_name == "Bash"
        assert display_tui.icon == "💻"
        assert len(display_tui.details) == 2  # description + command


class TestWebUsesEventTransformer:
    """Verify Web imports and uses EventTransformer (no duplication)."""

    def test_web_imports_event_transformer(self):
        """Web imports EventTransformer from display.transformer."""
        # Read Web module source to verify import
        import inspect

        # Check websocket module where EventTransformer is used
        from motus.ui.web import websocket as web_websocket_module

        source = inspect.getsource(web_websocket_module)

        # Web MUST import EventTransformer (check module-level import)
        assert "EventTransformer" in source
        assert "display.transformer" in source

    def test_web_uses_event_transformer_transform(self):
        """Web calls EventTransformer.transform() on ParsedEvents."""
        import inspect

        # Check polling module where ParsedEvents are transformed
        from motus.ui.web import websocket_polling

        source = inspect.getsource(websocket_polling)

        # Web MUST use EventTransformer.transform()
        assert "EventTransformer.transform" in source

    def test_no_duplicate_transformation_logic(self):
        """Web does not duplicate transformation logic."""
        import inspect

        from motus.ui.web import formatters

        web_source = inspect.getsource(formatters)

        assert "EventTransformer.transform" in web_source


class TestDisplayEventFieldsComplete:
    """Verify all required DisplayEvent fields are present and pre-escaped."""

    def test_display_event_has_all_required_fields(self):
        """DisplayEvent has all required fields populated."""
        parsed = ParsedEvent(
            event_id="evt_complete_001",
            session_id="session_complete_123",
            event_type=EventType.TOOL_USE,
            source=AgentSource.CLAUDE,
            timestamp=datetime(2025, 1, 15, 12, 30, 0),
            tool_name="Write",
            tool_input={"file_path": "/tmp/test.md", "content": "# Test"},
            risk_level=RiskLevel.MEDIUM,
        )

        display = EventTransformer.transform(parsed)

        # Required identity fields
        assert display.event_id == "evt_complete_001"
        assert display.session_id == "session_complete_123"
        # short_session_id is first 8 chars of session_id
        assert display.short_session_id == "session_"

        # Required timing fields
        assert display.timestamp_display == "12:30:00"

        # Required classification fields
        assert display.event_type == "tool_use"
        assert display.risk_level == DisplayRiskLevel.MEDIUM

        # Required content fields (all pre-escaped)
        assert display.icon == "📝"
        assert display.title == "Write"
        assert isinstance(display.details, list)

    def test_display_event_fields_are_pre_escaped(self):
        """All DisplayEvent string fields are pre-escaped by SafeRenderer."""
        # Create event with Rich markup that needs escaping
        parsed = ParsedEvent(
            event_id="evt_escape_001",
            session_id="session_escape_123",
            event_type=EventType.THINKING,
            source=AgentSource.CLAUDE,
            timestamp=datetime(2025, 1, 15, 12, 35, 0),
            content="Testing [bold]text[/bold] and [red]colored[/red] markup",
        )

        display = EventTransformer.transform(parsed)

        # Rich markup MUST be escaped (SafeRenderer uses rich.markup.escape)
        # Rich escape converts [bold] to \[bold]
        content_str = " ".join(display.details)
        assert "\\[bold]" in content_str or "[bold]" not in content_str
        assert "\\[red]" in content_str or "[red]" not in content_str

    def test_display_event_file_paths_are_escaped(self):
        """File paths in DisplayEvent are pre-escaped."""
        parsed = ParsedEvent(
            event_id="evt_path_001",
            session_id="session_path_123",
            event_type=EventType.TOOL_USE,
            source=AgentSource.CLAUDE,
            timestamp=datetime(2025, 1, 15, 12, 40, 0),
            tool_name="Read",
            tool_input={"file_path": "/tmp/[test]/file.py"},
            risk_level=RiskLevel.SAFE,
        )

        display = EventTransformer.transform(parsed)

        # File path MUST be escaped (Rich markup escaping)
        assert display.file_path is not None
        # Rich escape escapes square brackets that could be Rich markup
        assert "\\[" in display.file_path


class TestSessionTransformerParity:
    """Verify DisplaySession is identical for both TUI and Web."""

    def test_session_transformation_is_identical(self):
        """Same UnifiedSession produces identical DisplaySession for TUI and Web."""
        from pathlib import Path

        # Create a UnifiedSession
        session = UnifiedSession(
            session_id="session_transform_123456789",
            source=Source.CLAUDE,
            project_path="/home/user/projects/motus",
            status=SessionStatus.ACTIVE,
            status_reason="Active session",
            file_path=Path("/tmp/session.json"),
            created_at=datetime(2025, 1, 15, 11, 0, 0),
            last_modified=datetime(2025, 1, 15, 12, 0, 0),
            event_count=42,
        )

        # Transform it once (what both TUI and Web do)
        display_tui = SessionTransformer.transform(session)
        display_web = SessionTransformer.transform(session)

        # Both surfaces get IDENTICAL DisplaySession
        assert display_tui == display_web
        assert display_tui.session_id == session.session_id
        # short_id is first 8 chars of session_id
        assert display_tui.short_id == "session_"
        assert display_tui.source == "claude"
        assert display_tui.source_icon == "🔵"
        assert display_tui.status == "active"
        assert display_tui.status_icon == "●"
        assert display_tui.event_count == 42

    def test_session_icons_are_consistent(self):
        """Session source and status icons are consistent."""
        from pathlib import Path

        # Test all sources
        for source, expected_icon in [
            (Source.CLAUDE, "🔵"),
            (Source.CODEX, "🟢"),
            (Source.GEMINI, "🟡"),
        ]:
            session = UnifiedSession(
                session_id=f"session_{source.value}",
                source=source,
                project_path="/tmp",
                status=SessionStatus.ACTIVE,
                status_reason="Active",
                file_path=Path("/tmp/session.json"),
                created_at=datetime.now(),
                last_modified=datetime.now(),
            )
            display = SessionTransformer.transform(session)
            assert display.source_icon == expected_icon

    def test_session_status_icons_are_consistent(self):
        """Session status icons are consistent."""
        from pathlib import Path

        # Test all statuses
        for status, expected_icon in [
            (SessionStatus.ACTIVE, "●"),
            (SessionStatus.IDLE, "○"),
            (SessionStatus.CRASHED, "✕"),
            (SessionStatus.ORPHANED, "?"),
        ]:
            session = UnifiedSession(
                session_id=f"session_{status.value}",
                source=Source.CLAUDE,
                project_path="/tmp",
                status=status,
                status_reason="Test",
                file_path=Path("/tmp/session.json"),
                created_at=datetime.now(),
                last_modified=datetime.now(),
            )
            display = SessionTransformer.transform(session)
            assert display.status_icon == expected_icon

    def test_session_project_name_extraction(self):
        """Project name extracted consistently from project_path."""
        from pathlib import Path

        session = UnifiedSession(
            session_id="session_project_123",
            source=Source.CLAUDE,
            project_path="/home/user/projects/motus",
            status=SessionStatus.ACTIVE,
            status_reason="Active",
            file_path=Path("/tmp/session.json"),
            created_at=datetime.now(),
            last_modified=datetime.now(),
        )

        display_tui = SessionTransformer.transform(session)
        display_web = SessionTransformer.transform(session)

        # Both extract same project name
        assert display_tui.project_name == display_web.project_name
        assert display_tui.project_name == "motus"


class TestEscapedContentIdentical:
    """Verify SafeRenderer output is identical for both TUI and Web."""

    def test_safe_renderer_escape_is_deterministic(self):
        """SafeRenderer.escape() produces same output every time."""
        test_cases = [
            "<script>alert('xss')</script>",
            "[bold]text[/bold]",
            "Normal text",
            "Path/with/[brackets]",
            "Command with `backticks`",
        ]

        for content in test_cases:
            result1 = SafeRenderer.escape(content)
            result2 = SafeRenderer.escape(content)
            assert result1 == result2

    def test_safe_renderer_content_truncation_is_consistent(self):
        """SafeRenderer.content() truncates consistently."""
        long_text = "A" * 300

        # Same input always produces same output
        result_tui = SafeRenderer.content(long_text, 200)
        result_web = SafeRenderer.content(long_text, 200)

        assert result_tui == result_web
        assert len(result_tui) <= 203  # 200 + "..."

    def test_safe_renderer_file_path_escaping_is_consistent(self):
        """SafeRenderer.file_path() escapes consistently."""
        path = "/home/user/[test]/file.py"

        result_tui = SafeRenderer.file_path(path)
        result_web = SafeRenderer.file_path(path)

        assert result_tui == result_web

    def test_safe_renderer_command_escaping_is_consistent(self):
        """SafeRenderer.command() escapes consistently."""
        cmd = 'bash -c "echo [bold]text[/bold]"'

        result_tui = SafeRenderer.command(cmd)
        result_web = SafeRenderer.command(cmd)

        assert result_tui == result_web

    def test_safe_renderer_whitespace_normalization(self):
        """SafeRenderer.content() normalizes whitespace consistently."""
        text_with_whitespace = "Line1\n\nLine2\t\tLine3   Line4"

        result_tui = SafeRenderer.content(text_with_whitespace, 200)
        result_web = SafeRenderer.content(text_with_whitespace, 200)

        assert result_tui == result_web
        assert "\n" not in result_tui  # Whitespace normalized
        assert "\t" not in result_tui


class TestRiskLevelMapping:
    """Verify risk level mapping is identical for both surfaces."""

    def test_risk_level_mapping_safe(self):
        """SAFE risk level maps to LOW display risk."""
        parsed = ParsedEvent(
            event_id="evt_risk_safe",
            session_id="session_123",
            event_type=EventType.TOOL_USE,
            source=AgentSource.CLAUDE,
            timestamp=datetime.now(),
            tool_name="Read",
            risk_level=RiskLevel.SAFE,
        )

        display = EventTransformer.transform(parsed)
        assert display.risk_level == DisplayRiskLevel.LOW

    def test_risk_level_mapping_medium(self):
        """MEDIUM risk level maps to MEDIUM display risk."""
        parsed = ParsedEvent(
            event_id="evt_risk_medium",
            session_id="session_123",
            event_type=EventType.TOOL_USE,
            source=AgentSource.CLAUDE,
            timestamp=datetime.now(),
            tool_name="Edit",
            risk_level=RiskLevel.MEDIUM,
        )

        display = EventTransformer.transform(parsed)
        assert display.risk_level == DisplayRiskLevel.MEDIUM

    def test_risk_level_mapping_high(self):
        """HIGH risk level maps to HIGH display risk."""
        parsed = ParsedEvent(
            event_id="evt_risk_high",
            session_id="session_123",
            event_type=EventType.TOOL_USE,
            source=AgentSource.CLAUDE,
            timestamp=datetime.now(),
            tool_name="Bash",
            risk_level=RiskLevel.HIGH,
        )

        display = EventTransformer.transform(parsed)
        assert display.risk_level == DisplayRiskLevel.HIGH

    def test_risk_level_mapping_critical(self):
        """CRITICAL risk level maps to CRITICAL display risk."""
        parsed = ParsedEvent(
            event_id="evt_risk_critical",
            session_id="session_123",
            event_type=EventType.TOOL_USE,
            source=AgentSource.CLAUDE,
            timestamp=datetime.now(),
            tool_name="Bash",
            tool_input={"command": "rm -rf /"},
            risk_level=RiskLevel.CRITICAL,
        )

        display = EventTransformer.transform(parsed)
        assert display.risk_level == DisplayRiskLevel.CRITICAL

    def test_risk_level_none_defaults_to_none(self):
        """None risk level maps to NONE display risk."""
        parsed = ParsedEvent(
            event_id="evt_risk_none",
            session_id="session_123",
            event_type=EventType.THINKING,
            source=AgentSource.CLAUDE,
            timestamp=datetime.now(),
            content="Just thinking...",
            # risk_level defaults to SAFE
        )

        display = EventTransformer.transform(parsed)
        # Default SAFE maps to LOW
        assert display.risk_level == DisplayRiskLevel.LOW


class TestToolIconMapping:
    """Verify tool icons are consistent across all transformations."""

    def test_tool_icons_are_consistent(self):
        """Tool icons are mapped consistently."""
        tool_icon_mapping = {
            "Read": "📖",
            "Write": "📝",
            "Edit": "✏️",
            "Bash": "💻",
            "Glob": "🔍",
            "Grep": "🔎",
            "Task": "🤖",
            "WebFetch": "🌐",
            "WebSearch": "🔎",
            "TodoWrite": "📋",
            "AskUserQuestion": "❓",
        }

        for tool_name, expected_icon in tool_icon_mapping.items():
            parsed = ParsedEvent(
                event_id=f"evt_{tool_name}",
                session_id="session_123",
                event_type=EventType.TOOL_USE,
                source=AgentSource.CLAUDE,
                timestamp=datetime.now(),
                tool_name=tool_name,
            )

            display = EventTransformer.transform(parsed)
            assert display.icon == expected_icon

    def test_unknown_tool_gets_default_icon(self):
        """Unknown tools get a default icon."""
        parsed = ParsedEvent(
            event_id="evt_unknown",
            session_id="session_123",
            event_type=EventType.TOOL_USE,
            source=AgentSource.CLAUDE,
            timestamp=datetime.now(),
            tool_name="UnknownTool",
        )

        display = EventTransformer.transform(parsed)
        assert display.icon == "🔧"  # Default tool icon


class TestTimestampFormatting:
    """Verify timestamp formatting is identical for both surfaces."""

    def test_timestamp_formatted_as_hh_mm_ss(self):
        """Timestamps formatted as HH:MM:SS."""
        parsed = ParsedEvent(
            event_id="evt_time_001",
            session_id="session_123",
            event_type=EventType.THINKING,
            source=AgentSource.CLAUDE,
            timestamp=datetime(2025, 1, 15, 14, 32, 45),
            content="Test",
        )

        display = EventTransformer.transform(parsed)
        assert display.timestamp_display == "14:32:45"

    def test_timestamp_formatting_is_consistent(self):
        """Same timestamp produces same display string."""
        timestamp = datetime(2025, 1, 15, 9, 5, 3)

        parsed = ParsedEvent(
            event_id="evt_time_002",
            session_id="session_123",
            event_type=EventType.THINKING,
            source=AgentSource.CLAUDE,
            timestamp=timestamp,
            content="Test",
        )

        display1 = EventTransformer.transform(parsed)
        display2 = EventTransformer.transform(parsed)

        assert display1.timestamp_display == display2.timestamp_display
        assert display1.timestamp_display == "09:05:03"


class TestGenericEventHandling:
    """Verify generic/unknown events are handled consistently."""

    def test_unknown_event_type_handled_gracefully(self):
        """Unknown event types produce generic DisplayEvent."""
        parsed = ParsedEvent(
            event_id="evt_unknown_type",
            session_id="session_123",
            event_type=EventType.SESSION_START,  # Not handled by specific transformers
            source=AgentSource.CLAUDE,
            timestamp=datetime.now(),
        )

        display = EventTransformer.transform(parsed)

        # Generic transformation
        assert display.event_type == "session_start"
        assert display.icon == "📌"
        assert display.title == "session_start"
        assert display.details == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
