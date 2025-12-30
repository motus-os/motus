"""Tests for context extraction."""

import pytest

pytest.importorskip("motus.ui.tui", reason="TUI removed in v0.5.0")

from motus.ui.tui.context_extractor import (
    _extract_decision,
    extract_context,
)


class MockEvent:
    """Mock event for testing."""

    def __init__(self, event_type: str, **kwargs):
        self.event_type = event_type
        self.tool_name = kwargs.get("tool_name")
        self.file_path = kwargs.get("file_path")
        self.content = kwargs.get("content", "")
        self.details = kwargs.get("details", [])
        self.raw_data = kwargs.get("raw_data", {})
        self.title = kwargs.get("title")


class TestContextExtraction:
    """Test context extraction from events."""

    def test_empty_events_returns_default(self):
        """Empty event list should return default context."""
        context = extract_context([])

        assert context.total_events == 0
        assert context.health_score == 1.0
        assert len(context.files_read) == 0

    def test_files_read_tracked(self):
        """Read events should track files."""
        events = [
            MockEvent("tool_use", tool_name="Read", file_path="/test.py"),
            MockEvent("tool_use", tool_name="Read", file_path="/other.py"),
        ]

        context = extract_context(events)

        assert len(context.files_read) == 2
        assert "/test.py" in context.files_read

    def test_files_modified_tracked(self):
        """Write/Edit events should track modified files."""
        events = [
            MockEvent("tool_use", tool_name="Write", file_path="/new.py"),
            MockEvent("tool_use", tool_name="Edit", file_path="/existing.py"),
        ]

        context = extract_context(events)

        assert len(context.files_modified) == 2

    def test_duplicate_files_not_tracked_twice(self):
        """Same file read multiple times should only appear once."""
        events = [
            MockEvent("tool_use", tool_name="Read", file_path="/test.py"),
            MockEvent("tool_use", tool_name="Read", file_path="/test.py"),
            MockEvent("tool_use", tool_name="Read", file_path="/test.py"),
        ]

        context = extract_context(events)

        assert len(context.files_read) == 1
        assert context.files_read[0] == "/test.py"

    def test_tool_counts(self):
        """Tool usage should be counted."""
        events = [
            MockEvent("tool_use", tool_name="Read"),
            MockEvent("tool_use", tool_name="Read"),
            MockEvent("tool_use", tool_name="Bash"),
        ]

        context = extract_context(events)

        assert context.tool_counts.get("Read") == 2
        assert context.tool_counts.get("Bash") == 1

    def test_agent_spawns_tracked(self):
        """Spawn events should be tracked."""
        events = [
            MockEvent("spawn", raw_data={"agent_type": "research", "agent_model": "sonnet"}),
            MockEvent("spawn", raw_data={"agent_type": "coder"}),
        ]

        context = extract_context(events)

        assert len(context.agent_spawns) == 2
        assert context.agent_spawns[0]["type"] == "research"
        assert context.agent_spawns[0]["model"] == "sonnet"
        assert context.agent_spawns[1]["type"] == "coder"

    def test_agent_spawn_with_agent_spawn_type(self):
        """Support both 'spawn' and 'agent_spawn' event types."""
        events = [
            MockEvent("agent_spawn", raw_data={"agent_type": "analyzer"}),
        ]

        context = extract_context(events)

        assert len(context.agent_spawns) == 1
        assert context.agent_spawns[0]["type"] == "analyzer"

    def test_friction_count(self):
        """Error events should increase friction count."""
        events = [
            MockEvent("thinking"),
            MockEvent("error"),
            MockEvent("error"),
            MockEvent("tool_use", tool_name="Read"),
        ]

        context = extract_context(events)

        assert context.friction_count == 2

    def test_health_score_calculation(self):
        """Health score should decrease with errors."""
        # No errors = perfect health
        events_good = [MockEvent("thinking") for _ in range(10)]
        context_good = extract_context(events_good)
        assert context_good.health_score == 1.0

        # Many errors = low health
        events_bad = [MockEvent("error") for _ in range(10)]
        context_bad = extract_context(events_bad)
        assert context_bad.health_score < 0.5

    def test_health_score_partial_errors(self):
        """Health score should reflect partial error rate."""
        # 2 errors out of 10 events = 20% error rate
        events = [MockEvent("thinking") for _ in range(8)]
        events.extend([MockEvent("error") for _ in range(2)])

        context = extract_context(events)

        # error_rate = 2/10 = 0.2
        # health = 1.0 - (0.2 * 3) = 0.4
        assert context.health_score == pytest.approx(0.4, abs=0.01)

    def test_files_limited_to_last_10(self):
        """Should only keep last 10 files read."""
        events = [
            MockEvent("tool_use", tool_name="Read", file_path=f"/file{i}.py") for i in range(20)
        ]

        context = extract_context(events)

        assert len(context.files_read) == 10
        assert "/file19.py" in context.files_read
        assert "/file0.py" not in context.files_read

    def test_tool_counts_limited_to_top_8(self):
        """Should only keep top 8 most used tools."""
        events = []
        for i in range(15):
            # Create tools with different usage counts
            for _ in range(i + 1):
                events.append(MockEvent("tool_use", tool_name=f"Tool{i}"))

        context = extract_context(events)

        assert len(context.tool_counts) == 8

    def test_decisions_limited_to_last_5(self):
        """Should only keep last 5 decisions."""
        events = [
            MockEvent("thinking", content=f"I'll do task {i}. It's important.") for i in range(10)
        ]

        context = extract_context(events)

        assert len(context.decisions) <= 5


class TestDecisionExtraction:
    """Test decision extraction from thinking content."""

    def test_extract_decision_with_ill(self):
        """Should extract decisions with I'll marker."""
        content = "Looking at the code. I'll start by reading the main file."
        decision = _extract_decision(content)

        assert decision is not None
        assert "i'll start by reading" in decision.lower()

    def test_extract_decision_with_let_me(self):
        """Should extract decisions with 'let me' marker."""
        content = "Let me analyze the structure first."
        decision = _extract_decision(content)

        assert decision is not None
        assert "let me analyze" in decision.lower()

    def test_extract_decision_with_i_need_to(self):
        """Should extract decisions with 'I need to' marker."""
        content = "I need to check the configuration file."
        decision = _extract_decision(content)

        assert decision is not None
        assert "i need to check" in decision.lower()

    def test_extract_decision_no_marker(self):
        """Should return None without decision markers."""
        content = "The file contains a class definition."
        decision = _extract_decision(content)

        assert decision is None

    def test_decision_truncated(self):
        """Long decisions should be truncated."""
        content = "I'll " + "x" * 200
        decision = _extract_decision(content)

        assert decision is not None
        assert len(decision) <= 100

    def test_decision_extracts_until_period(self):
        """Should extract until first period."""
        content = "I'll read the file carefully and parse it. Then I'll analyze it."
        decision = _extract_decision(content)

        assert decision is not None
        assert "then" not in decision.lower()

    def test_decision_minimum_length(self):
        """Should not extract very short decisions."""
        content = "I'll go."
        decision = _extract_decision(content)

        # Too short (< 20 chars), should be None
        assert decision is None

    def test_multiple_markers_extracts_first(self):
        """With multiple markers, should extract first one."""
        content = "I'll start here by analyzing the code. Then let me do that."
        decision = _extract_decision(content)

        assert decision is not None
        assert "i'll start" in decision.lower()


class TestContextPanel:
    """Test context panel rendering."""

    def test_panel_renders_without_context(self):
        """Panel should render empty state."""
        from motus.ui.tui.panels.context import ContextPanel

        panel = ContextPanel()
        rendered = panel.render()

        assert rendered is not None
        assert "no session" in rendered.lower()

    def test_panel_renders_with_context(self):
        """Panel should render with context."""
        from motus.ui.tui.panels.context import ContextPanel

        # Create mock events
        events = [
            MockEvent("tool_use", tool_name="Read", file_path="/test.py"),
            MockEvent("tool_use", tool_name="Read", file_path="/other.py"),
            MockEvent("tool_use", tool_name="Bash"),
        ]

        panel = ContextPanel()
        panel.update_from_events(events)

        rendered = panel.render()
        assert rendered is not None
        assert "Health" in rendered
        assert "Read" in rendered

    def test_panel_shows_health_good(self):
        """Panel should show good health with no errors."""
        from motus.ui.tui.panels.context import ContextPanel

        events = [MockEvent("thinking") for _ in range(10)]

        panel = ContextPanel()
        panel.update_from_events(events)

        rendered = panel.render()
        assert "Good" in rendered

    def test_panel_shows_health_poor(self):
        """Panel should show poor health with many errors."""
        from motus.ui.tui.panels.context import ContextPanel

        events = [MockEvent("error") for _ in range(10)]

        panel = ContextPanel()
        panel.update_from_events(events)

        rendered = panel.render()
        assert "Needs Attention" in rendered or "Fair" in rendered

    def test_panel_shows_files(self):
        """Panel should display files."""
        from motus.ui.tui.panels.context import ContextPanel

        events = [
            MockEvent("tool_use", tool_name="Read", file_path="/path/to/test.py"),
            MockEvent("tool_use", tool_name="Write", file_path="/path/to/output.txt"),
        ]

        panel = ContextPanel()
        panel.update_from_events(events)

        rendered = panel.render()
        assert "Files" in rendered or "Read" in rendered
        assert "test.py" in rendered
        assert "output.txt" in rendered

    def test_panel_shows_tools(self):
        """Panel should display tool counts."""
        from motus.ui.tui.panels.context import ContextPanel

        events = [
            MockEvent("tool_use", tool_name="Read"),
            MockEvent("tool_use", tool_name="Read"),
            MockEvent("tool_use", tool_name="Bash"),
        ]

        panel = ContextPanel()
        panel.update_from_events(events)

        rendered = panel.render()
        assert "Tools" in rendered or "Read" in rendered

    def test_panel_shows_friction(self):
        """Panel should display friction when errors exist."""
        from motus.ui.tui.panels.context import ContextPanel

        events = [
            MockEvent("thinking"),
            MockEvent("error"),
            MockEvent("error"),
        ]

        panel = ContextPanel()
        panel.update_from_events(events)

        rendered = panel.render()
        assert "Friction" in rendered or "error" in rendered.lower()

    def test_panel_shows_agents(self):
        """Panel should display agent spawns."""
        from motus.ui.tui.panels.context import ContextPanel

        events = [
            MockEvent("spawn", raw_data={"agent_type": "research", "agent_model": "sonnet"}),
            MockEvent("spawn", raw_data={"agent_type": "coder"}),
        ]

        panel = ContextPanel()
        panel.update_from_events(events)

        rendered = panel.render()
        assert "Agents" in rendered or "research" in rendered

    def test_panel_toggle_visibility(self):
        """Panel should toggle visibility."""
        from motus.ui.tui.panels.context import ContextPanel

        panel = ContextPanel()

        # Should toggle without error
        panel.toggle_visibility()
        panel.toggle_visibility()


class TestEventTypeExtraction:
    """Test event type extraction from various formats."""

    def test_get_event_type_string(self):
        """Should handle string event types."""
        from motus.ui.tui.context_extractor import _get_event_type

        event = MockEvent("tool_use")
        assert _get_event_type(event) == "tool_use"

    def test_get_event_type_uppercase(self):
        """Should lowercase event types."""
        from motus.ui.tui.context_extractor import _get_event_type

        event = MockEvent("TOOL_USE")
        assert _get_event_type(event) == "tool_use"

    def test_get_file_path_from_details(self):
        """Should extract file path from details."""
        from motus.ui.tui.context_extractor import _get_file_path

        event = MockEvent("tool_use", details=["/path/to/file.py"])
        path = _get_file_path(event)

        assert path == "/path/to/file.py"

    def test_get_file_path_from_raw_data(self):
        """Should extract file path from raw_data."""
        from motus.ui.tui.context_extractor import _get_file_path

        event = MockEvent("tool_use", raw_data={"file_path": "/test.py"})
        path = _get_file_path(event)

        assert path == "/test.py"

    def test_get_tool_name_from_title(self):
        """Should extract tool name from title."""
        from motus.ui.tui.context_extractor import _get_tool_name

        event = MockEvent("tool_use", title="Read")
        tool = _get_tool_name(event)

        assert tool == "Read"

    def test_total_events_count(self):
        """Should count total events correctly."""
        events = [MockEvent("thinking") for _ in range(15)]
        context = extract_context(events)

        assert context.total_events == 15
