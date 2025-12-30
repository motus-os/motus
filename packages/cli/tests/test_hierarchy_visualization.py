"""Tests for hierarchy visualization in Track G."""

from datetime import datetime

from motus.display.events import DisplayEvent, DisplayRiskLevel
from motus.display.transformer import EventTransformer
from motus.schema.events import AgentSource, EventType, ParsedEvent


class TestDepthPropagation:
    """Test that depth is properly propagated through the display pipeline."""

    def test_depth_zero_for_root_events(self):
        """Root session events should have depth 0."""
        event = ParsedEvent(
            event_id="root-1",
            session_id="session-1",
            timestamp=datetime.now(),
            event_type=EventType.THINKING,
            source=AgentSource.CLAUDE,
            content="Root thinking",
            raw_data={},
        )

        transformed = EventTransformer.transform(event)

        # Default depth should be 0
        assert transformed.subagent_depth == 0
        assert transformed.is_subagent is False

    def test_depth_preserved_from_raw_data(self):
        """Depth from raw_data should be preserved."""
        event = ParsedEvent(
            event_id="sub-1",
            session_id="session-1",
            timestamp=datetime.now(),
            event_type=EventType.THINKING,
            source=AgentSource.CLAUDE,
            content="Sub-agent thinking",
            raw_data={"depth": 2, "parent_event_id": "spawn-123"},
        )

        transformed = EventTransformer.transform(event)

        # Depth should be propagated
        assert transformed.subagent_depth == 2
        assert transformed.is_subagent is True

    def test_agent_depth_field_alternative(self):
        """Should also accept agent_depth field."""
        event = ParsedEvent(
            event_id="sub-2",
            session_id="session-1",
            timestamp=datetime.now(),
            event_type=EventType.TOOL_USE,
            source=AgentSource.CLAUDE,
            tool_name="Read",
            raw_data={"agent_depth": 1, "parent_event_id": "spawn-456"},
        )

        transformed = EventTransformer.transform(event)

        assert transformed.subagent_depth == 1
        assert transformed.is_subagent is True

    def test_parent_event_id_preserved(self):
        """parent_event_id should be preserved from raw_data."""
        event = ParsedEvent(
            event_id="sub-2",
            session_id="session-1",
            timestamp=datetime.now(),
            event_type=EventType.AGENT_SPAWN,
            source=AgentSource.CLAUDE,
            content="Spawn prompt",
            raw_data={"parent_event_id": "toolu_abc123", "depth": 1},
        )

        transformed = EventTransformer.transform(event)

        assert transformed.parent_event_id == "toolu_abc123"
        assert transformed.subagent_depth == 1

    def test_parent_uuid_alternative_field(self):
        """Should also accept parent_uuid field."""
        event = ParsedEvent(
            event_id="sub-3",
            session_id="session-1",
            timestamp=datetime.now(),
            event_type=EventType.THINKING,
            source=AgentSource.CLAUDE,
            content="Sub-agent thinking",
            raw_data={"parent_uuid": "uuid-789", "depth": 1},
        )

        transformed = EventTransformer.transform(event)

        assert transformed.parent_event_id == "uuid-789"

    def test_spawn_event_depth(self):
        """Spawn events should preserve depth."""
        event = ParsedEvent(
            event_id="spawn-1",
            session_id="session-1",
            timestamp=datetime.now(),
            event_type=EventType.AGENT_SPAWN,
            source=AgentSource.CLAUDE,
            content="Spawn a task agent",
            raw_data={
                "depth": 1,
                "parent_event_id": "toolu_parent",
                "model": "claude-sonnet-4.5",
                "prompt": "Complete this task",
            },
        )

        transformed = EventTransformer.transform(event)

        assert transformed.subagent_depth == 1
        assert transformed.parent_event_id == "toolu_parent"
        assert transformed.is_subagent is True
        assert transformed.event_type == "agent_spawn"


class TestHierarchyFields:
    """Test hierarchy fields in DisplayEvent."""

    def test_display_event_has_hierarchy_fields(self):
        """DisplayEvent should have all hierarchy fields."""
        event = DisplayEvent(
            event_id="test-1",
            session_id="session-1",
            short_session_id="session-",
            timestamp_display="12:00:00",
            event_type="thinking",
            risk_level=DisplayRiskLevel.NONE,
            icon="💭",
            title="Thinking",
            details=["Test detail"],
            subagent_depth=2,
            parent_event_id="spawn-123",
            is_subagent=True,
        )

        assert event.subagent_depth == 2
        assert event.parent_event_id == "spawn-123"
        assert event.is_subagent is True

    def test_display_event_defaults(self):
        """DisplayEvent should have sensible defaults for hierarchy fields."""
        event = DisplayEvent(
            event_id="test-2",
            session_id="session-2",
            short_session_id="session-",
            timestamp_display="12:00:00",
            event_type="tool_use",
            risk_level=DisplayRiskLevel.LOW,
            icon="🔧",
            title="Tool",
            details=[],
        )

        # Default values
        assert event.subagent_depth == 0
        assert event.parent_event_id is None
        assert event.is_subagent is False


class TestWebHierarchyDisplay:
    """Test hierarchy display elements in web UI."""

    def test_depth_classes_defined(self):
        """CSS should define depth classes."""
        import os

        css_path = "src/motus/ui/static/dashboard.css"
        if os.path.exists(css_path):
            with open(css_path) as f:
                content = f.read()

            # Should have depth classes
            assert ".depth-1" in content
            assert ".depth-2" in content
            assert ".depth-3" in content

    def test_tree_connector_styles(self):
        """CSS should have tree connector styling."""
        import os

        css_path = "src/motus/ui/static/dashboard.css"
        if os.path.exists(css_path):
            with open(css_path) as f:
                content = f.read()

            # Should have tree connector class
            assert ".tree-connector" in content or ".event-thread" in content

    def test_subagent_group_styles(self):
        """CSS should have subagent group styles."""
        import os

        css_path = "src/motus/ui/static/dashboard.css"
        if os.path.exists(css_path):
            with open(css_path) as f:
                content = f.read()

            # Should have subagent group elements
            assert ".subagent-group" in content
            assert ".subagent-header" in content
            assert ".collapse-icon" in content


class TestIntegration:
    """Integration tests for full hierarchy visualization pipeline."""

    def test_full_pipeline_root_to_subagent(self):
        """Test full pipeline from ParsedEvent to DisplayEvent with hierarchy."""
        # Root event
        root_event = ParsedEvent(
            event_id="root-1",
            session_id="session-1",
            timestamp=datetime.now(),
            event_type=EventType.THINKING,
            source=AgentSource.CLAUDE,
            content="Planning...",
            raw_data={},
        )

        # Spawn event (depth 1)
        spawn_event = ParsedEvent(
            event_id="spawn-1",
            session_id="session-1",
            timestamp=datetime.now(),
            event_type=EventType.AGENT_SPAWN,
            source=AgentSource.CLAUDE,
            content="Research agent spawn",
            raw_data={
                "depth": 1,
                "parent_event_id": "toolu_abc",
                "model": "claude-sonnet-4.5",
                "prompt": "Research this topic",
            },
        )

        # Sub-agent event (depth 1)
        sub_event = ParsedEvent(
            event_id="sub-1",
            session_id="session-1",
            timestamp=datetime.now(),
            event_type=EventType.TOOL_USE,
            source=AgentSource.CLAUDE,
            tool_name="Read",
            raw_data={"depth": 1, "parent_event_id": "toolu_abc"},
        )

        # Transform all events
        root_display = EventTransformer.transform(root_event)
        spawn_display = EventTransformer.transform(spawn_event)
        sub_display = EventTransformer.transform(sub_event)

        # Verify hierarchy
        assert root_display.subagent_depth == 0
        assert root_display.is_subagent is False

        assert spawn_display.subagent_depth == 1
        assert spawn_display.is_subagent is True
        assert spawn_display.parent_event_id == "toolu_abc"

        assert sub_display.subagent_depth == 1
        assert sub_display.is_subagent is True
        assert sub_display.parent_event_id == "toolu_abc"

    def test_nested_hierarchy_depth_3(self):
        """Test deeply nested hierarchy (3 levels)."""
        events = []

        # Create a 3-level hierarchy
        for depth in range(4):  # 0, 1, 2, 3
            event = ParsedEvent(
                event_id=f"event-{depth}",
                session_id="session-1",
                timestamp=datetime.now(),
                event_type=EventType.THINKING,
                source=AgentSource.CLAUDE,
                content=f"Depth {depth} thinking",
                raw_data={
                    "depth": depth,
                    "parent_event_id": f"spawn-{depth - 1}" if depth > 0 else None,
                },
            )
            events.append(EventTransformer.transform(event))

        # Verify all depths
        assert events[0].subagent_depth == 0
        assert events[1].subagent_depth == 1
        assert events[2].subagent_depth == 2
        assert events[3].subagent_depth == 3

        # Verify parent linking
        assert events[0].parent_event_id is None
        assert events[1].parent_event_id == "spawn-0"
        assert events[2].parent_event_id == "spawn-1"
        assert events[3].parent_event_id == "spawn-2"
