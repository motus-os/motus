"""Tests for sub-agent session discovery.

This module tests Phase 7 Track C: Sub-Agent File Discovery.
Tests that agent-*.jsonl files are:
1. Discovered (not skipped)
2. Parsed as valid sessions
3. Linked to parent via parent_event_id
4. Have correct depth computed
"""

import json

from motus.ingestors.claude import ClaudeBuilder
from motus.protocols import EventType
from tests.fixtures.constants import FIXED_TIMESTAMP


class TestSubAgentDiscovery:
    """Test that sub-agent files are discovered."""

    def test_agent_files_not_skipped(self, tmp_path, mock_uuid, mock_datetime_now):
        """agent-*.jsonl files should NOT be skipped - they should be parseable."""
        # Create mock Claude project directory
        project_dir = tmp_path / ".claude" / "projects" / "test-project"
        project_dir.mkdir(parents=True)

        # Create parent session
        parent_session = project_dir / "session.jsonl"
        parent_session.write_text(
            json.dumps(
                {
                    "type": "assistant",
                    "timestamp": FIXED_TIMESTAMP.isoformat(),
                    "sessionId": "parent-123",
                    "message": {"content": [{"type": "text", "text": "Hello"}]},
                }
            )
            + "\n"
        )

        # Create sub-agent session
        agent_session = project_dir / "agent-spawn123.jsonl"
        agent_session.write_text(
            json.dumps(
                {
                    "type": "assistant",
                    "timestamp": FIXED_TIMESTAMP.isoformat(),
                    "sessionId": "agent-spawn123",
                    "message": {"content": [{"type": "text", "text": "Sub-agent here"}]},
                }
            )
            + "\n"
        )

        # Both files should be parseable
        builder = ClaudeBuilder()

        parent_events = builder.parse_events(parent_session)
        agent_events = builder.parse_events(agent_session)

        assert len(parent_events) > 0, "Parent session should parse"
        assert len(agent_events) > 0, "Agent session should parse"

        # Agent events should have depth 1
        for event in agent_events:
            assert event.agent_depth == 1, "Agent events should have depth 1"

    def test_agent_file_parsed_as_session(self, tmp_path, mock_uuid, mock_datetime_now):
        """agent-*.jsonl should be parsed as a valid session."""
        project_dir = tmp_path / ".claude" / "projects" / "test-project"
        project_dir.mkdir(parents=True)

        agent_session = project_dir / "agent-task456.jsonl"
        agent_session.write_text(
            json.dumps(
                {
                    "type": "assistant",
                    "timestamp": FIXED_TIMESTAMP.isoformat(),
                    "sessionId": "agent-task456",
                    "message": {
                        "content": [{"type": "thinking", "thinking": "Working on task..."}]
                    },
                }
            )
            + "\n"
        )

        builder = ClaudeBuilder()
        events = builder.parse_events(agent_session)

        assert len(events) > 0, "Agent file should be parsed"
        assert any(
            e.event_type == EventType.THINKING for e in events
        ), "Should find thinking events"

    def test_parent_event_id_extracted_from_filename(self, tmp_path, mock_uuid, mock_datetime_now):
        """Parent event ID should be extracted from agent-<id>.jsonl filename."""
        project_dir = tmp_path / ".claude" / "projects" / "test-project"
        project_dir.mkdir(parents=True)

        # Filename contains the spawn event ID
        agent_session = project_dir / "agent-toolu_01abc123.jsonl"
        agent_session.write_text(
            json.dumps(
                {
                    "type": "assistant",
                    "timestamp": FIXED_TIMESTAMP.isoformat(),
                    "sessionId": "agent-toolu_01abc123",
                    "message": {"content": [{"type": "text", "text": "Sub-agent"}]},
                }
            )
            + "\n"
        )

        builder = ClaudeBuilder()
        events = builder.parse_events(agent_session)

        # All events in this sub-agent session should have parent_event_id set
        assert len(events) > 0
        for event in events:
            # Events in the sub-agent session should track back to the parent
            assert event.raw_data.get("parent_event_id") == "toolu_01abc123"

    def test_depth_computed_for_direct_subagent(self, tmp_path, mock_uuid, mock_datetime_now):
        """Direct sub-agents should have depth = 1."""
        project_dir = tmp_path / ".claude" / "projects" / "test-project"
        project_dir.mkdir(parents=True)

        # Root session (depth 0)
        root_session = project_dir / "session.jsonl"
        root_session.write_text(
            json.dumps(
                {
                    "type": "assistant",
                    "timestamp": FIXED_TIMESTAMP.isoformat(),
                    "message": {"content": [{"type": "text", "text": "Root"}]},
                }
            )
            + "\n"
        )

        # Direct sub-agent (depth 1)
        sub_agent = project_dir / "agent-spawn1.jsonl"
        sub_agent.write_text(
            json.dumps(
                {
                    "type": "assistant",
                    "timestamp": FIXED_TIMESTAMP.isoformat(),
                    "message": {"content": [{"type": "text", "text": "Sub-agent"}]},
                }
            )
            + "\n"
        )

        builder = ClaudeBuilder()

        # Parse root session - should have depth 0
        root_events = builder.parse_events(root_session)
        assert len(root_events) > 0
        for event in root_events:
            assert event.agent_depth == 0, "Root session events should have depth 0"

        # Parse sub-agent session - should have depth 1
        sub_events = builder.parse_events(sub_agent)
        assert len(sub_events) > 0
        for event in sub_events:
            assert event.agent_depth == 1, "Direct sub-agent events should have depth 1"

    def test_multiple_subagents_same_parent(self, tmp_path, mock_uuid, mock_datetime_now):
        """Multiple sub-agents from same parent should all be parseable."""
        project_dir = tmp_path / ".claude" / "projects" / "test-project"
        project_dir.mkdir(parents=True)

        # Create 3 sub-agent sessions
        for i in range(3):
            agent = project_dir / f"agent-spawn{i}.jsonl"
            agent.write_text(
                json.dumps(
                    {
                        "type": "assistant",
                        "timestamp": FIXED_TIMESTAMP.isoformat(),
                        "sessionId": f"agent-spawn{i}",
                        "message": {"content": [{"type": "text", "text": f"Agent {i}"}]},
                    }
                )
                + "\n"
            )

        # All 3 should be parseable
        builder = ClaudeBuilder()

        for i in range(3):
            agent_file = project_dir / f"agent-spawn{i}.jsonl"
            events = builder.parse_events(agent_file)
            assert len(events) > 0, f"Agent {i} should parse"
            # All should have depth 1
            for event in events:
                assert event.agent_depth == 1, f"Agent {i} should have depth 1"


class TestDepthComputation:
    """Test depth computation for agent hierarchy."""

    def test_root_session_depth_zero(self, tmp_path, mock_uuid, mock_datetime_now):
        """Root session (not agent-*) should have depth 0."""
        session_file = tmp_path / "session.jsonl"
        session_file.write_text(
            json.dumps(
                {
                    "type": "assistant",
                    "timestamp": FIXED_TIMESTAMP.isoformat(),
                    "message": {"content": [{"type": "text", "text": "Root"}]},
                }
            )
            + "\n"
        )

        builder = ClaudeBuilder()
        events = builder.parse_events(session_file)

        assert len(events) > 0
        for event in events:
            assert event.agent_depth == 0, "Root session should have depth 0"

    def test_direct_subagent_depth_one(self, tmp_path, mock_uuid, mock_datetime_now):
        """agent-*.jsonl should have depth 1."""
        session_file = tmp_path / "agent-task1.jsonl"
        session_file.write_text(
            json.dumps(
                {
                    "type": "assistant",
                    "timestamp": FIXED_TIMESTAMP.isoformat(),
                    "message": {"content": [{"type": "text", "text": "Direct sub-agent"}]},
                }
            )
            + "\n"
        )

        builder = ClaudeBuilder()
        events = builder.parse_events(session_file)

        assert len(events) > 0
        for event in events:
            assert event.agent_depth == 1, "Direct sub-agent should have depth 1"


class TestSubAgentContent:
    """Test that sub-agent content is captured."""

    def test_subagent_thinking_captured(self, tmp_path, mock_uuid, mock_datetime_now):
        """Sub-agent thinking blocks should be parsed."""
        agent_session = tmp_path / "agent-research.jsonl"
        agent_session.write_text(
            json.dumps(
                {
                    "type": "assistant",
                    "timestamp": FIXED_TIMESTAMP.isoformat(),
                    "sessionId": "agent-research",
                    "message": {
                        "content": [
                            {"type": "thinking", "thinking": "Researching the topic..."},
                            {"type": "text", "text": "Found relevant info"},
                        ]
                    },
                }
            )
            + "\n"
        )

        builder = ClaudeBuilder()
        events = builder.parse_events(agent_session)

        thinking_events = [e for e in events if e.event_type == EventType.THINKING]
        assert len(thinking_events) > 0, "Should capture thinking events"
        assert "Researching" in thinking_events[0].content

    def test_subagent_tool_calls_captured(self, tmp_path, mock_uuid, mock_datetime_now):
        """Sub-agent tool calls should be parsed."""
        agent_session = tmp_path / "agent-coder.jsonl"
        agent_session.write_text(
            json.dumps(
                {
                    "type": "assistant",
                    "timestamp": FIXED_TIMESTAMP.isoformat(),
                    "sessionId": "agent-coder",
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "name": "Read",
                                "input": {"file_path": "/test.py"},
                                "id": "toolu_sub",
                            }
                        ]
                    },
                }
            )
            + "\n"
        )

        builder = ClaudeBuilder()
        events = builder.parse_events(agent_session)

        tool_events = [e for e in events if e.event_type == EventType.TOOL]
        assert len(tool_events) > 0, "Should capture tool events"
        assert tool_events[0].tool_name == "Read"


class TestAgentSpawnEvent:
    """Test that AGENT_SPAWN events properly link to sub-agent sessions."""

    def test_agent_spawn_has_parent_event_id(self, tmp_path, mock_uuid, mock_datetime_now):
        """AGENT_SPAWN event should have tool_use.id as parent_event_id."""
        session_file = tmp_path / "session.jsonl"
        session_file.write_text(
            json.dumps(
                {
                    "type": "assistant",
                    "timestamp": FIXED_TIMESTAMP.isoformat(),
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "id": "toolu_spawn123",
                                "name": "Task",
                                "input": {
                                    "subagent_type": "research",
                                    "description": "Research Python testing",
                                    "prompt": "Find pytest info",
                                },
                            }
                        ]
                    },
                }
            )
            + "\n"
        )

        builder = ClaudeBuilder()
        events = builder.parse_events(session_file)

        spawn_events = [e for e in events if e.event_type == EventType.AGENT_SPAWN]
        assert len(spawn_events) == 1, "Should find AGENT_SPAWN event"
        assert spawn_events[0].parent_event_id == "toolu_spawn123", "Should link to tool_use.id"

    def test_agent_spawn_increments_depth(self, tmp_path, mock_uuid, mock_datetime_now):
        """AGENT_SPAWN from depth=0 session should create depth=1 sub-agent."""
        session_file = tmp_path / "session.jsonl"
        session_file.write_text(
            json.dumps(
                {
                    "type": "assistant",
                    "timestamp": FIXED_TIMESTAMP.isoformat(),
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "id": "toolu_spawn",
                                "name": "Task",
                                "input": {
                                    "subagent_type": "general",
                                    "description": "Sub-task",
                                    "prompt": "Do work",
                                },
                            }
                        ]
                    },
                }
            )
            + "\n"
        )

        builder = ClaudeBuilder()
        events = builder.parse_events(session_file)

        spawn_events = [e for e in events if e.event_type == EventType.AGENT_SPAWN]
        assert len(spawn_events) == 1
        # AGENT_SPAWN is created in parent session (depth 0), but indicates depth 1 for the sub-agent
        assert spawn_events[0].agent_depth == 1, "Spawned sub-agent should be depth 1"


class TestEdgeCases:
    """Test edge cases for sub-agent discovery."""

    def test_empty_subagent_file(self, tmp_path, mock_uuid):
        """Empty sub-agent file should not crash."""
        agent_session = tmp_path / "agent-empty.jsonl"
        agent_session.write_text("")

        builder = ClaudeBuilder()
        events = builder.parse_events(agent_session)

        assert isinstance(events, list)
        assert len(events) == 0

    def test_malformed_subagent_file(self, tmp_path, mock_uuid):
        """Malformed sub-agent file should not crash."""
        agent_session = tmp_path / "agent-bad.jsonl"
        agent_session.write_text("{ not valid json }\n")

        builder = ClaudeBuilder()
        events = builder.parse_events(agent_session)

        assert isinstance(events, list)
        # Should skip malformed lines gracefully

    def test_subagent_with_mixed_content(self, tmp_path, mock_uuid, mock_datetime_now):
        """Sub-agent with thinking, tools, and responses."""
        agent_session = tmp_path / "agent-mixed.jsonl"
        agent_session.write_text(
            json.dumps(
                {
                    "type": "assistant",
                    "timestamp": FIXED_TIMESTAMP.isoformat(),
                    "message": {
                        "content": [
                            {"type": "thinking", "thinking": "Planning..."},
                            {
                                "type": "tool_use",
                                "name": "Read",
                                "input": {"file_path": "/test.py"},
                                "id": "t1",
                            },
                            {"type": "text", "text": "Analysis complete"},
                        ]
                    },
                }
            )
            + "\n"
        )

        builder = ClaudeBuilder()
        events = builder.parse_events(agent_session)

        # Should have all event types
        event_types = {e.event_type for e in events}
        assert EventType.THINKING in event_types
        assert EventType.TOOL in event_types
        assert EventType.RESPONSE in event_types

        # All should have depth=1
        for event in events:
            assert event.agent_depth == 1, "All events in sub-agent should have depth 1"
