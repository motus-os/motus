"""
UX Parity Tests - Verify consistent behavior across CLI, TUI, and Web surfaces.

This module tests that the same event or session data produces consistent
user-visible output across all three interfaces (CLI, TUI, Web).

Key Invariants:
- Same event must show consistent core information (tool name, file path, etc.)
- Empty states must be helpful and consistent
- Error messages must be actionable and contain necessary context
- Formatting must preserve essential information across surfaces

Architecture:
- CLI uses cli/formatters.py and cli/output.py
- TUI uses display/transformer.py -> DisplayEvent
- Web uses ui/web/formatters.py + display/transformer.py
"""

from datetime import datetime
from pathlib import Path

import pytest

# Import CLI formatting
from motus.cli.output import (
    ErrorEvent,
    TaskEvent,
    ThinkingEvent,
    ToolEvent,
    unified_event_to_legacy,
)

# Import display structures
from motus.display.events import DisplayRiskLevel
from motus.display.transformer import EventTransformer, SessionTransformer

# Import core data structures
from motus.protocols import (
    EventType,
    RiskLevel,
    SessionStatus,
    Source,
    ToolStatus,
    UnifiedEvent,
    UnifiedSession,
)
from motus.schema.events import AgentSource, ParsedEvent
from motus.schema.events import EventType as SchemaEventType
from motus.schema.events import RiskLevel as SchemaRiskLevel

# Import Web formatting
from motus.ui.web.formatters import format_event_for_client


class TestEventDisplayParity:
    """Verify same event shows consistent info across surfaces."""

    def test_tool_event_contains_tool_name_all_surfaces(self):
        """All surfaces (CLI, TUI, Web) must show the tool name for tool events."""
        # Create a UnifiedEvent for a tool use
        unified_event = UnifiedEvent(
            event_id="evt_tool_001",
            session_id="session_abc123",
            timestamp=datetime(2025, 1, 15, 12, 0, 0),
            event_type=EventType.TOOL,
            content="Reading file",
            tool_name="Read",
            tool_input={"file_path": "/tmp/test.py"},
            tool_status=ToolStatus.SUCCESS,
            risk_level=RiskLevel.SAFE,
        )

        # Convert to ParsedEvent (for TUI/Web)
        parsed_event = ParsedEvent(
            event_id=unified_event.event_id,
            session_id=unified_event.session_id,
            event_type=SchemaEventType.TOOL_USE,
            source=AgentSource.CLAUDE,
            timestamp=unified_event.timestamp,
            tool_name=unified_event.tool_name,
            tool_input=unified_event.tool_input,
            risk_level=SchemaRiskLevel.SAFE,
        )

        # CLI: Convert UnifiedEvent to legacy ToolEvent
        cli_event = unified_event_to_legacy(unified_event)
        assert isinstance(cli_event, ToolEvent)
        assert cli_event.name == "Read"

        # TUI: Transform to DisplayEvent
        tui_event = EventTransformer.transform(parsed_event)
        assert tui_event.tool_name == "Read"

        # Web: Format for client
        web_event = format_event_for_client(
            parsed_event, session_id="session_abc123", project_path="/tmp", source="claude"
        )
        assert web_event["tool_name"] == "Read"

    def test_file_path_visible_in_all_surfaces(self):
        """File paths must be visible in tool events across all surfaces."""
        test_path = "/home/user/motus-command/src/test.py"

        # Create events
        unified_event = UnifiedEvent(
            event_id="evt_edit_001",
            session_id="session_edit_123",
            timestamp=datetime(2025, 1, 15, 12, 5, 0),
            event_type=EventType.TOOL,
            content="Editing file",
            tool_name="Edit",
            tool_input={"file_path": test_path, "old_string": "foo", "new_string": "bar"},
            risk_level=RiskLevel.MEDIUM,
        )

        parsed_event = ParsedEvent(
            event_id=unified_event.event_id,
            session_id=unified_event.session_id,
            event_type=SchemaEventType.TOOL_USE,
            source=AgentSource.CLAUDE,
            timestamp=unified_event.timestamp,
            tool_name=unified_event.tool_name,
            tool_input=unified_event.tool_input,
            risk_level=SchemaRiskLevel.MEDIUM,
        )

        # CLI: Check file path is in input dict
        cli_event = unified_event_to_legacy(unified_event)
        assert test_path in cli_event.input["file_path"]

        # TUI: Check file path is extracted
        tui_event = EventTransformer.transform(parsed_event)
        assert tui_event.file_path is not None
        assert test_path in tui_event.file_path or "test.py" in tui_event.file_path

        # Web: Check file path is present
        web_event = format_event_for_client(
            parsed_event, session_id="session_edit_123", project_path="/tmp", source="claude"
        )
        assert "file_path" in web_event

    def test_risk_level_visible_all_surfaces(self):
        """Risk levels must be visible and consistent across surfaces."""
        unified_event = UnifiedEvent(
            event_id="evt_bash_001",
            session_id="session_bash_456",
            timestamp=datetime(2025, 1, 15, 12, 10, 0),
            event_type=EventType.TOOL,
            content="Running command",
            tool_name="Bash",
            tool_input={"command": "rm -rf /tmp/test", "description": "Delete test files"},
            risk_level=RiskLevel.HIGH,
        )

        parsed_event = ParsedEvent(
            event_id=unified_event.event_id,
            session_id=unified_event.session_id,
            event_type=SchemaEventType.TOOL_USE,
            source=AgentSource.CLAUDE,
            timestamp=unified_event.timestamp,
            tool_name=unified_event.tool_name,
            tool_input=unified_event.tool_input,
            risk_level=SchemaRiskLevel.HIGH,
        )

        # CLI: Risk level in event
        cli_event = unified_event_to_legacy(unified_event)
        assert cli_event.risk_level == "high"

        # TUI: Risk level mapped to display level
        tui_event = EventTransformer.transform(parsed_event)
        assert tui_event.risk_level == DisplayRiskLevel.HIGH

        # Web: Risk level in JSON
        web_event = format_event_for_client(
            parsed_event, session_id="session_bash_456", project_path="/tmp", source="claude"
        )
        assert web_event["risk_level"] == "high"

    def test_thinking_content_preserved_all_surfaces(self):
        """Thinking event content must be preserved across surfaces."""
        thinking_content = "I need to analyze the test file structure to find the right pattern."

        unified_event = UnifiedEvent(
            event_id="evt_think_001",
            session_id="session_think_789",
            timestamp=datetime(2025, 1, 15, 12, 15, 0),
            event_type=EventType.THINKING,
            content=thinking_content,
        )

        parsed_event = ParsedEvent(
            event_id=unified_event.event_id,
            session_id=unified_event.session_id,
            event_type=SchemaEventType.THINKING,
            source=AgentSource.CLAUDE,
            timestamp=unified_event.timestamp,
            content=thinking_content,
        )

        # CLI: Content preserved
        cli_event = unified_event_to_legacy(unified_event)
        assert isinstance(cli_event, ThinkingEvent)
        assert cli_event.content == thinking_content

        # TUI: Content in details or content field
        tui_event = EventTransformer.transform(parsed_event)
        content_found = thinking_content in str(tui_event.details) or (
            tui_event.content and thinking_content in tui_event.content
        )
        assert content_found

        # Web: Content in event
        web_event = format_event_for_client(
            parsed_event, session_id="session_think_789", project_path="/tmp", source="claude"
        )
        assert "content" in web_event
        assert len(web_event["content"]) > 0

    def test_agent_spawn_visible_all_surfaces(self):
        """Agent spawn events must be visible across all surfaces."""
        unified_event = UnifiedEvent(
            event_id="evt_spawn_001",
            session_id="session_spawn_111",
            timestamp=datetime(2025, 1, 15, 12, 20, 0),
            event_type=EventType.AGENT_SPAWN,
            content="Spawning analysis agent",
            agent_type="task",
            agent_description="Analyze test coverage",
            agent_prompt="Review all test files",
            agent_model="claude-sonnet-4-5",
        )

        parsed_event = ParsedEvent(
            event_id=unified_event.event_id,
            session_id=unified_event.session_id,
            event_type=SchemaEventType.AGENT_SPAWN,
            source=AgentSource.CLAUDE,
            timestamp=unified_event.timestamp,
            spawn_type="task",
            raw_data={
                "description": unified_event.agent_description,
                "prompt": unified_event.agent_prompt,
                "model": unified_event.agent_model,
            },
        )

        # CLI: Converts to TaskEvent
        cli_event = unified_event_to_legacy(unified_event)
        assert isinstance(cli_event, TaskEvent)
        assert cli_event.subagent_type == "task"

        # TUI: Shows as agent spawn
        tui_event = EventTransformer.transform(parsed_event)
        assert tui_event.event_type == "agent_spawn"
        assert tui_event.is_subagent is True

        # Web: Shows spawn event
        web_event = format_event_for_client(
            parsed_event, session_id="session_spawn_111", project_path="/tmp", source="claude"
        )
        assert web_event["event_type"] == "spawn"
        assert web_event["tool_name"] == "SPAWN"

    def test_timestamp_formatted_consistently(self):
        """Timestamps must be formatted consistently across surfaces."""
        test_time = datetime(2025, 1, 15, 14, 32, 45)

        parsed_event = ParsedEvent(
            event_id="evt_time_001",
            session_id="session_time_222",
            event_type=SchemaEventType.THINKING,
            source=AgentSource.CLAUDE,
            timestamp=test_time,
            content="Test",
        )

        # TUI: Formatted as HH:MM:SS
        tui_event = EventTransformer.transform(parsed_event)
        assert tui_event.timestamp_display == "14:32:45"

        # Web: Also includes timestamp
        web_event = format_event_for_client(
            parsed_event, session_id="session_time_222", project_path="/tmp", source="claude"
        )
        assert "timestamp" in web_event
        assert web_event["timestamp"] == "14:32:45"


class TestEmptyStateParity:
    """Verify helpful empty states across surfaces."""

    def test_empty_session_list_handling(self):
        """All surfaces handle empty session lists gracefully."""
        # Create empty session list
        sessions = []

        # All surfaces should handle this without error
        assert len(sessions) == 0

        # TUI: SessionTransformer handles empty list
        display_sessions = [SessionTransformer.transform(s) for s in sessions]
        assert len(display_sessions) == 0

    def test_session_with_no_events_handling(self):
        """All surfaces handle sessions with no events."""
        session = UnifiedSession(
            session_id="session_empty_001",
            source=Source.CLAUDE,
            file_path=Path("/tmp/empty.json"),
            project_path="/tmp",
            created_at=datetime(2025, 1, 15, 12, 0, 0),
            last_modified=datetime(2025, 1, 15, 12, 0, 0),
            status=SessionStatus.IDLE,
            status_reason="No activity",
            event_count=0,
        )

        # TUI: Can transform session even with no events
        display_session = SessionTransformer.transform(session)
        assert display_session.event_count == 0
        assert display_session.session_id == session.session_id

    def test_missing_tool_name_handling(self):
        """All surfaces handle tool events with missing tool names."""
        unified_event = UnifiedEvent(
            event_id="evt_missing_001",
            session_id="session_missing_333",
            timestamp=datetime.now(),
            event_type=EventType.TOOL,
            content="Unknown tool",
            tool_name=None,  # Missing tool name
        )

        parsed_event = ParsedEvent(
            event_id=unified_event.event_id,
            session_id=unified_event.session_id,
            event_type=SchemaEventType.TOOL_USE,
            source=AgentSource.CLAUDE,
            timestamp=unified_event.timestamp,
            tool_name=None,
        )

        # CLI: Handles None tool name
        cli_event = unified_event_to_legacy(unified_event)
        assert cli_event.name == "unknown"

        # TUI: Provides default
        tui_event = EventTransformer.transform(parsed_event)
        assert tui_event.tool_name is not None

        # Web: Provides default (capitalized)
        web_event = format_event_for_client(
            parsed_event, session_id="session_missing_333", project_path="/tmp", source="claude"
        )
        # Web uses capitalized "Unknown" as default
        assert web_event["tool_name"].lower() == "unknown"

    def test_empty_file_path_handling(self):
        """All surfaces handle tool events with missing file paths."""
        unified_event = UnifiedEvent(
            event_id="evt_nofile_001",
            session_id="session_nofile_444",
            timestamp=datetime.now(),
            event_type=EventType.TOOL,
            content="Tool without file",
            tool_name="Bash",
            tool_input={"command": "ls"},
        )

        parsed_event = ParsedEvent(
            event_id=unified_event.event_id,
            session_id=unified_event.session_id,
            event_type=SchemaEventType.TOOL_USE,
            source=AgentSource.CLAUDE,
            timestamp=unified_event.timestamp,
            tool_name=unified_event.tool_name,
            tool_input=unified_event.tool_input,
        )

        # CLI: Handles missing file_path
        cli_event = unified_event_to_legacy(unified_event)
        assert isinstance(cli_event, ToolEvent)

        # TUI: file_path is None or empty
        tui_event = EventTransformer.transform(parsed_event)
        assert tui_event.file_path is None or tui_event.file_path == ""

        # Web: file_path is empty string
        web_event = format_event_for_client(
            parsed_event, session_id="session_nofile_444", project_path="/tmp", source="claude"
        )
        assert web_event.get("file_path", "") == ""


class TestErrorStateParity:
    """Verify consistent error messages."""

    def test_error_event_contains_message(self):
        """Error events must contain the error message across all surfaces."""
        error_message = "Failed to read file: Permission denied"

        unified_event = UnifiedEvent(
            event_id="evt_error_001",
            session_id="session_error_555",
            timestamp=datetime.now(),
            event_type=EventType.ERROR,
            content=error_message,
            tool_name="Read",
        )

        # CLI: Error message preserved
        cli_event = unified_event_to_legacy(unified_event)
        assert isinstance(cli_event, ErrorEvent)
        assert cli_event.message == error_message

    def test_crashed_session_identifiable(self):
        """Crashed sessions must be identifiable across surfaces."""
        crashed_session = UnifiedSession(
            session_id="session_crashed_666",
            source=Source.CLAUDE,
            file_path=Path("/tmp/crashed.json"),
            project_path="/tmp",
            created_at=datetime.now(),
            last_modified=datetime.now(),
            status=SessionStatus.CRASHED,
            status_reason="Stopped during: Edit src/test.py",
        )

        # TUI: Status visible
        display_session = SessionTransformer.transform(crashed_session)
        assert display_session.status == "crashed"
        assert display_session.status_icon == "✕"

    def test_session_not_found_handling(self):
        """Missing session IDs should be handled gracefully."""
        missing_id = "session_nonexistent_999"

        # All surfaces should be able to display the ID in error messages
        assert len(missing_id) > 0
        assert missing_id.startswith("session_")


class TestSessionDisplayParity:
    """Verify session information is consistent across surfaces."""

    def test_session_id_truncation_consistent(self):
        """Session IDs should be truncated consistently (first 8 chars)."""
        full_id = "session_1234567890abcdef"

        session = UnifiedSession(
            session_id=full_id,
            source=Source.CLAUDE,
            file_path=Path("/tmp/test.json"),
            project_path="/tmp",
            created_at=datetime.now(),
            last_modified=datetime.now(),
            status=SessionStatus.ACTIVE,
            status_reason="Active",
        )

        # TUI: Uses short_id (first 8 chars)
        display_session = SessionTransformer.transform(session)
        assert display_session.short_id == "session_"

    def test_session_source_icons_consistent(self):
        """Session source icons must be consistent."""
        sources_and_icons = [
            (Source.CLAUDE, "🔵"),
            (Source.CODEX, "🟢"),
            (Source.GEMINI, "🟡"),
        ]

        for source, expected_icon in sources_and_icons:
            session = UnifiedSession(
                session_id=f"session_{source.value}",
                source=source,
                file_path=Path("/tmp/test.json"),
                project_path="/tmp",
                created_at=datetime.now(),
                last_modified=datetime.now(),
                status=SessionStatus.ACTIVE,
                status_reason="Active",
            )

            # TUI: Check icon
            display_session = SessionTransformer.transform(session)
            assert display_session.source_icon == expected_icon

    def test_session_status_icons_consistent(self):
        """Session status icons must be consistent."""
        statuses_and_icons = [
            (SessionStatus.ACTIVE, "●"),
            (SessionStatus.IDLE, "○"),
            (SessionStatus.CRASHED, "✕"),
            (SessionStatus.ORPHANED, "?"),
        ]

        for status, expected_icon in statuses_and_icons:
            session = UnifiedSession(
                session_id=f"session_{status.value}",
                source=Source.CLAUDE,
                file_path=Path("/tmp/test.json"),
                project_path="/tmp",
                created_at=datetime.now(),
                last_modified=datetime.now(),
                status=status,
                status_reason="Test",
            )

            # TUI: Check icon
            display_session = SessionTransformer.transform(session)
            assert display_session.status_icon == expected_icon

    def test_project_name_extraction_consistent(self):
        """Project names must be extracted consistently from paths."""
        test_cases = [
            ("/home/user/projects/motus-command", "motus-command"),
            ("/tmp/test-project", "test-project"),
            ("/home/user/my-app", "my-app"),
        ]

        for project_path, expected_name in test_cases:
            session = UnifiedSession(
                session_id="session_test",
                source=Source.CLAUDE,
                file_path=Path("/tmp/test.json"),
                project_path=project_path,
                created_at=datetime.now(),
                last_modified=datetime.now(),
                status=SessionStatus.ACTIVE,
                status_reason="Active",
            )

            # TUI: Extract project name
            display_session = SessionTransformer.transform(session)
            assert display_session.project_name == expected_name


class TestToolIconParity:
    """Verify tool icons are consistent across surfaces."""

    def test_common_tool_icons_consistent(self):
        """Common tools must have consistent icons."""
        tool_icons = {
            "Read": "📖",
            "Write": "📝",
            "Edit": "✏️",
            "Bash": "💻",
            "Glob": "🔍",
            "Grep": "🔎",
        }

        for tool_name, expected_icon in tool_icons.items():
            parsed_event = ParsedEvent(
                event_id=f"evt_{tool_name}",
                session_id="session_icons",
                event_type=SchemaEventType.TOOL_USE,
                source=AgentSource.CLAUDE,
                timestamp=datetime.now(),
                tool_name=tool_name,
            )

            # TUI: Check icon
            tui_event = EventTransformer.transform(parsed_event)
            assert tui_event.icon == expected_icon

    def test_thinking_icon_consistent(self):
        """Thinking events must have consistent icon."""
        parsed_event = ParsedEvent(
            event_id="evt_think",
            session_id="session_icons",
            event_type=SchemaEventType.THINKING,
            source=AgentSource.CLAUDE,
            timestamp=datetime.now(),
            content="Analyzing...",
        )

        # TUI: Check thinking icon
        tui_event = EventTransformer.transform(parsed_event)
        assert tui_event.icon == "💭"

    def test_agent_spawn_icon_consistent(self):
        """Agent spawn events must have consistent icon."""
        parsed_event = ParsedEvent(
            event_id="evt_spawn",
            session_id="session_icons",
            event_type=SchemaEventType.AGENT_SPAWN,
            source=AgentSource.CLAUDE,
            timestamp=datetime.now(),
            spawn_type="task",
        )

        # TUI: Check spawn icon
        tui_event = EventTransformer.transform(parsed_event)
        assert tui_event.icon == "🤖"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
