"""
Tests for SessionOrchestrator and source builders.

Tests the unified architecture for multi-source session management.
"""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from motus.ingestors.base import DECISION_REGEX
from motus.ingestors.claude import ClaudeBuilder
from motus.ingestors.codex import CodexBuilder, map_codex_tool
from motus.ingestors.gemini import GeminiBuilder, map_gemini_tool
from motus.orchestrator import SessionOrchestrator, get_orchestrator
from motus.protocols import (
    EventType,
    RiskLevel,
    SessionStatus,
    Source,
    UnifiedSession,
)
from motus.session_cache import CachedSession


class TestBaseBuilder:
    """Tests for BaseBuilder shared logic."""

    def test_compute_status_active(self):
        """Sessions modified within 2 minutes are ACTIVE."""
        builder = ClaudeBuilder()
        now = datetime.now()
        modified = now - timedelta(seconds=60)

        status, reason = builder.compute_status(modified, now)
        assert status == SessionStatus.ACTIVE
        assert "2 minutes" in reason

    def test_compute_status_open(self):
        """Sessions with running process are OPEN."""
        builder = ClaudeBuilder()
        now = datetime.now()
        modified = now - timedelta(minutes=15)

        # Without running process, should be IDLE
        status, reason = builder.compute_status(modified, now)
        assert status == SessionStatus.IDLE
        assert "30 minutes" in reason

        # With running process, should be OPEN
        status, reason = builder.compute_status(
            modified, now, project_path="/project", running_projects={"/project"}
        )
        assert status == SessionStatus.OPEN
        assert "Process running" in reason

    def test_compute_status_idle(self):
        """Sessions modified within 2 hours are IDLE without running process."""
        builder = ClaudeBuilder()
        now = datetime.now()
        modified = now - timedelta(hours=1)

        status, reason = builder.compute_status(modified, now)
        assert status == SessionStatus.IDLE
        assert "2 hours" in reason

        # With running process, should be OPEN
        status, reason = builder.compute_status(
            modified, now, project_path="/project", running_projects={"/project"}
        )
        assert status == SessionStatus.OPEN
        assert "Process running" in reason

    def test_compute_status_orphaned(self):
        """Sessions modified over 2 hours ago are ORPHANED."""
        builder = ClaudeBuilder()
        now = datetime.now()
        modified = now - timedelta(hours=5)

        status, reason = builder.compute_status(modified, now)
        assert status == SessionStatus.ORPHANED
        assert "No recent activity" in reason

    def test_compute_status_crashed(self):
        """Sessions with risky last action and no completion are CRASHED."""
        builder = ClaudeBuilder()
        now = datetime.now()
        modified = now - timedelta(minutes=3)  # Between crash_min and crash_max

        status, reason = builder.compute_status(
            modified, now, last_action="Edit /path/to/file.py", has_completion=False
        )
        assert status == SessionStatus.CRASHED
        assert "Edit" in reason

    def test_decision_patterns(self):
        """Test decision detection regex patterns."""
        # Should match
        assert DECISION_REGEX.search("I'll use the new API")
        assert DECISION_REGEX.search("I've decided to implement this")
        assert DECISION_REGEX.search("Let me create a new function")
        assert DECISION_REGEX.search("The best approach is to")

        # Should not match
        assert not DECISION_REGEX.search("Hello world")
        assert not DECISION_REGEX.search("The variable is set")

    def test_extract_decisions_from_text(self):
        """Test decision extraction from thinking text."""
        builder = ClaudeBuilder()
        text = "I'll use pytest for testing. The best approach is to mock the API."

        decisions = builder._extract_decisions_from_text(text, "test-session")
        assert len(decisions) >= 1
        assert any("pytest" in d.decision_text for d in decisions)

    def test_classify_risk_safe(self):
        """Read operations are SAFE."""
        builder = ClaudeBuilder()
        risk = builder._classify_risk("Read", {"file_path": "/path/to/file"})
        assert risk == RiskLevel.SAFE

    def test_classify_risk_medium(self):
        """Write operations are MEDIUM risk."""
        builder = ClaudeBuilder()
        risk = builder._classify_risk("Write", {"file_path": "/path/to/file"})
        assert risk == RiskLevel.MEDIUM

    def test_classify_risk_high(self):
        """Bash with rm is HIGH risk."""
        builder = ClaudeBuilder()
        risk = builder._classify_risk("Bash", {"command": "rm -r temp/"})
        assert risk == RiskLevel.HIGH

    def test_classify_risk_critical(self):
        """Bash with sudo is CRITICAL risk."""
        builder = ClaudeBuilder()
        risk = builder._classify_risk("Bash", {"command": "sudo rm -rf /"})
        assert risk == RiskLevel.CRITICAL


class TestClaudeBuilder:
    """Tests for ClaudeBuilder."""

    def test_source_name(self):
        """Builder identifies as CLAUDE source."""
        builder = ClaudeBuilder()
        assert builder.source_name == Source.CLAUDE

    def test_parse_events_thinking_block(self):
        """Parse thinking blocks from Claude transcript."""
        builder = ClaudeBuilder()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            line = json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {"type": "thinking", "thinking": "I need to analyze this code"}
                        ],
                        "model": "claude-sonnet-4-20250514",
                    },
                }
            )
            f.write(line + "\n")
            f.flush()

            events = builder.parse_events(Path(f.name))

        thinking_events = [e for e in events if e.event_type == EventType.THINKING]
        assert len(thinking_events) >= 1
        assert "analyze" in thinking_events[0].content

    def test_parse_events_tool_use(self):
        """Parse tool_use blocks from Claude transcript."""
        builder = ClaudeBuilder()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            line = json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "name": "Read",
                                "input": {"file_path": "/path/to/file.py"},
                            }
                        ]
                    },
                }
            )
            f.write(line + "\n")
            f.flush()

            events = builder.parse_events(Path(f.name))

        tool_events = [e for e in events if e.event_type == EventType.TOOL]
        assert len(tool_events) == 1
        assert tool_events[0].tool_name == "Read"

    def test_parse_events_user_message(self):
        """Parse user messages from Claude transcript."""
        builder = ClaudeBuilder()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            line = json.dumps({"type": "user", "message": {"content": "Please fix the bug"}})
            f.write(line + "\n")
            f.flush()

            events = builder.parse_events(Path(f.name))

        user_events = [e for e in events if e.event_type == EventType.USER_MESSAGE]
        assert len(user_events) == 1
        assert "fix" in user_events[0].content


class TestCodexBuilder:
    """Tests for CodexBuilder."""

    def test_source_name(self):
        """Builder identifies as CODEX source."""
        builder = CodexBuilder()
        assert builder.source_name == Source.CODEX

    def test_tool_name_mapping(self):
        """Codex tool names map to unified names."""
        assert map_codex_tool("shell_command") == "Bash"
        assert map_codex_tool("read_file") == "Read"
        assert map_codex_tool("write_file") == "Write"
        assert map_codex_tool("update_plan") == "TodoWrite"
        assert map_codex_tool("mcp__some_tool") == "MCP"
        assert map_codex_tool("unknown_tool") == "unknown_tool"

    def test_parse_events_function_call(self):
        """Parse function_call from Codex transcript."""
        builder = CodexBuilder()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            # Session meta line
            meta = json.dumps(
                {"type": "session_meta", "payload": {"id": "test-session", "cwd": "/tmp"}}
            )
            f.write(meta + "\n")

            # Function call
            line = json.dumps(
                {
                    "type": "response_item",
                    "timestamp": "2025-01-01T12:00:00Z",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": {"command": "ls -la"},
                    },
                }
            )
            f.write(line + "\n")
            f.flush()

            events = builder.parse_events(Path(f.name))

        tool_events = [e for e in events if e.event_type == EventType.TOOL]
        assert len(tool_events) >= 1
        assert tool_events[0].tool_name == "Bash"

    def test_synthetic_thinking_surrogates(self):
        """Codex generates synthetic thinking for tool calls."""
        builder = CodexBuilder()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            meta = json.dumps(
                {"type": "session_meta", "payload": {"id": "test-session", "cwd": "/tmp"}}
            )
            f.write(meta + "\n")

            line = json.dumps(
                {
                    "type": "response_item",
                    "timestamp": "2025-01-01T12:00:00Z",
                    "payload": {
                        "type": "function_call",
                        "name": "read_file",
                        "arguments": {"path": "/path/to/file.py"},
                    },
                }
            )
            f.write(line + "\n")
            f.flush()

            events = builder.parse_events(Path(f.name))

        thinking_events = [e for e in events if e.event_type == EventType.THINKING]
        assert len(thinking_events) >= 1
        assert thinking_events[0].raw_data.get("synthetic") is True


class TestGeminiBuilder:
    """Tests for GeminiBuilder."""

    def test_source_name(self):
        """Builder identifies as GEMINI source."""
        builder = GeminiBuilder()
        assert builder.source_name == Source.GEMINI

    def test_tool_name_mapping(self):
        """Gemini tool names map to unified names."""
        assert map_gemini_tool("shell") == "Bash"
        assert map_gemini_tool("read_file") == "Read"
        assert map_gemini_tool("write_file") == "Write"
        assert map_gemini_tool("search_files") == "Grep"
        assert map_gemini_tool("unknown") == "unknown"

    def test_parse_events_gemini_response(self):
        """Parse Gemini JSON transcript."""
        builder = GeminiBuilder()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            data = {
                "sessionId": "test-session",
                "projectHash": "abc123",
                "messages": [
                    {"type": "user", "content": "Hello"},
                    {
                        "type": "gemini",
                        "model": "gemini-pro",
                        "content": "Hello! How can I help?",
                        "thoughts": [{"subject": "Greeting", "description": "User is greeting me"}],
                    },
                ],
            }
            json.dump(data, f)
            f.flush()

            events = builder.parse_events(Path(f.name))

        # Should have user message, thinking, and response
        user_events = [e for e in events if e.event_type == EventType.USER_MESSAGE]
        thinking_events = [e for e in events if e.event_type == EventType.THINKING]
        response_events = [e for e in events if e.event_type == EventType.RESPONSE]

        assert len(user_events) == 1
        assert len(thinking_events) >= 1
        assert len(response_events) == 1

    def test_parse_events_tool_calls(self):
        """Parse Gemini tool calls."""
        builder = GeminiBuilder()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            data = {
                "sessionId": "test-session",
                "projectHash": "abc123",
                "messages": [
                    {
                        "type": "gemini",
                        "model": "gemini-pro",
                        "toolCalls": [{"name": "shell", "args": {"command": "ls"}}],
                    }
                ],
            }
            json.dump(data, f)
            f.flush()

            events = builder.parse_events(Path(f.name))

        tool_events = [e for e in events if e.event_type == EventType.TOOL]
        assert len(tool_events) == 1
        assert tool_events[0].tool_name == "Bash"


class TestSessionOrchestrator:
    """Tests for SessionOrchestrator."""

    def test_orchestrator_singleton(self):
        """get_orchestrator returns singleton instance."""
        orch1 = get_orchestrator()
        orch2 = get_orchestrator()
        assert orch1 is orch2

    def test_orchestrator_has_all_builders(self):
        """Orchestrator has builders for all sources."""
        orch = SessionOrchestrator()
        assert Source.CLAUDE in orch._builders
        assert Source.CODEX in orch._builders
        assert Source.GEMINI in orch._builders

    def test_discover_all_empty(self):
        """discover_all returns empty list when no sessions exist."""
        orch = SessionOrchestrator()

        # Mock all builders to return empty
        for builder in orch._builders.values():
            builder.discover = MagicMock(return_value=[])

        # If SQLite session cache is enabled, ensure it doesn't leak real user data into tests.
        if getattr(orch, "_sqlite_cache", None) is not None:
            orch._sqlite_cache.sync = MagicMock(return_value=None)
        if getattr(orch, "_discovery", None) is not None:
            orch._discovery._sqlite_cache = None

        sessions = orch.discover_all(max_age_hours=1)
        assert sessions == []

    @patch("motus.orchestrator.discovery.SessionDiscovery._maybe_auto_sync")
    def test_discover_all_falls_back_when_sqlite_cache_fails(self, mock_auto_sync):
        """If SQLite cache query fails, discovery falls back to builder.discover()."""
        mock_auto_sync.return_value = False  # Auto-sync returns false (nothing synced)

        orch = SessionOrchestrator()

        orch._process_detector.get_running_projects = MagicMock(return_value=set())
        orch._sqlite_cache.query = MagicMock(side_effect=Exception("boom"))
        # Propagate mock to discovery layer
        orch._discovery._sqlite_cache = orch._sqlite_cache

        # Only Claude should be consulted for this test.
        for builder in orch._builders.values():
            builder.discover = MagicMock(return_value=[])

        sessions = orch.discover_all(max_age_hours=1, sources=[Source.CLAUDE])
        assert sessions == []
        # When query fails, auto_sync is attempted
        mock_auto_sync.assert_called_once()
        # Then falls back to builder.discover()
        orch._builders[Source.CLAUDE].discover.assert_called_once()

    def test_discover_all_does_not_sync_sqlite_cache_when_cached(self):
        """discover_all should not trigger SQLite sync when cache has data."""
        orch = SessionOrchestrator()

        orch._process_detector.get_running_projects = MagicMock(return_value=set())
        orch._sqlite_cache.sync = MagicMock(return_value=None)
        # Propagate mock to discovery layer
        orch._discovery._sqlite_cache = orch._sqlite_cache
        cached = CachedSession(
            session_id="cached-1",
            file_path=Path("/tmp/cached.jsonl"),
            project_path="/project",
            file_mtime_ns=int(datetime.now().timestamp() * 1e9),
            file_size_bytes=123,
            last_action="",
            has_completion=False,
            status="active",
        )
        orch._sqlite_cache.query = MagicMock(return_value=[cached])

        for builder in orch._builders.values():
            builder.discover = MagicMock(return_value=[])

        sessions = orch.discover_all(max_age_hours=1, sources=[Source.CLAUDE])
        assert sessions
        orch._sqlite_cache.sync.assert_not_called()
        orch._builders[Source.CLAUDE].discover.assert_not_called()

    @patch("motus.core.bootstrap.ensure_database")
    def test_discover_all_auto_syncs_when_cache_empty(self, mock_ensure_db):
        """discover_all auto-syncs once when cache is empty."""
        mock_ensure_db.return_value = None  # ensure_database succeeds

        orch = SessionOrchestrator()

        orch._process_detector.get_running_projects = MagicMock(return_value=set())
        orch._sqlite_cache.sync = MagicMock(return_value=None)
        # Propagate mock to discovery layer
        orch._discovery._sqlite_cache = orch._sqlite_cache
        cached = CachedSession(
            session_id="cached-2",
            file_path=Path("/tmp/cached-2.jsonl"),
            project_path="/project",
            file_mtime_ns=int(datetime.now().timestamp() * 1e9),
            file_size_bytes=456,
            last_action="",
            has_completion=False,
            status="active",
        )
        orch._sqlite_cache.query = MagicMock(side_effect=[[], [cached]])

        for builder in orch._builders.values():
            builder.discover = MagicMock(return_value=[])

        sessions = orch.discover_all(max_age_hours=1, sources=[Source.CLAUDE])
        assert sessions
        orch._sqlite_cache.sync.assert_called_once()
        orch._builders[Source.CLAUDE].discover.assert_not_called()

    def test_discover_all_skips_process_detection(self):
        """discover_all can skip process detection for fast listing."""
        orch = SessionOrchestrator()

        orch._process_detector.get_running_projects = MagicMock(return_value={"/project"})
        orch._discovery._sqlite_cache = None

        for builder in orch._builders.values():
            builder.discover = MagicMock(return_value=[])

        sessions = orch.discover_all(
            max_age_hours=1,
            sources=[Source.CLAUDE],
            skip_process_detection=True,
        )
        assert sessions == []
        orch._process_detector.get_running_projects.assert_not_called()

    def test_discover_all_sorting(self):
        """discover_all sorts by status then recency."""
        orch = SessionOrchestrator()
        now = datetime.now()

        # Create mock sessions
        mock_sessions = [
            UnifiedSession(
                session_id="orphaned-1",
                source=Source.CLAUDE,
                file_path=Path("/tmp/orphaned.jsonl"),
                project_path="/project",
                status=SessionStatus.ORPHANED,
                status_reason="old",
                created_at=now - timedelta(hours=5),
                last_modified=now - timedelta(hours=5),
            ),
            UnifiedSession(
                session_id="active-1",
                source=Source.CLAUDE,
                file_path=Path("/tmp/active.jsonl"),
                project_path="/project",
                status=SessionStatus.ACTIVE,
                status_reason="recent",
                created_at=now,
                last_modified=now,
            ),
            UnifiedSession(
                session_id="open-1",
                source=Source.CODEX,
                file_path=Path("/tmp/open.jsonl"),
                project_path="/project",
                status=SessionStatus.OPEN,
                status_reason="open",
                created_at=now - timedelta(minutes=10),
                last_modified=now - timedelta(minutes=10),
            ),
        ]

        # Manually add to cache
        for s in mock_sessions:
            orch._session_cache[s.session_id] = s

        # Get from cache
        sessions = list(orch._session_cache.values())

        # Sort like orchestrator does
        def sort_key(s):
            status_order = {
                SessionStatus.ACTIVE: 0,
                SessionStatus.OPEN: 1,
                SessionStatus.CRASHED: 2,
                SessionStatus.IDLE: 3,
                SessionStatus.ORPHANED: 4,
            }
            return (status_order.get(s.status, 5), -s.last_modified.timestamp())

        sessions.sort(key=sort_key)

        assert sessions[0].status == SessionStatus.ACTIVE
        assert sessions[1].status == SessionStatus.OPEN
        assert sessions[2].status == SessionStatus.ORPHANED

    def test_get_events_caching(self):
        """get_events caches parsed events."""
        orch = SessionOrchestrator()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            line = json.dumps({"type": "user", "message": {"content": "test"}})
            f.write(line + "\n")
            f.flush()

            session = UnifiedSession(
                session_id="test-cache",
                source=Source.CLAUDE,
                file_path=Path(f.name),
                project_path="/tmp",
                status=SessionStatus.ACTIVE,
                status_reason="test",
                created_at=datetime.now(),
                last_modified=datetime.now(),
            )

            # First call parses
            events1 = orch.get_events(session)
            # Second call uses cache
            events2 = orch.get_events(session)

            assert events1 == events2
            assert session.session_id in orch._event_cache

    def test_refresh_cache(self):
        """refresh_cache clears cached data."""
        orch = SessionOrchestrator()
        orch._session_cache["test"] = MagicMock()
        orch._event_cache["test"] = []

        orch.refresh_cache()

        assert "test" not in orch._session_cache
        assert "test" not in orch._event_cache

    def test_get_context(self):
        """get_context aggregates session context."""
        orch = SessionOrchestrator()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            # User message
            f.write(json.dumps({"type": "user", "message": {"content": "Read file.py"}}) + "\n")
            # Tool use
            f.write(
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {
                            "content": [
                                {
                                    "type": "tool_use",
                                    "name": "Read",
                                    "input": {"file_path": "/path/file.py"},
                                }
                            ]
                        },
                    }
                )
                + "\n"
            )
            f.flush()

            session = UnifiedSession(
                session_id="test-context",
                source=Source.CLAUDE,
                file_path=Path(f.name),
                project_path="/tmp",
                status=SessionStatus.ACTIVE,
                status_reason="test",
                created_at=datetime.now(),
                last_modified=datetime.now(),
            )

            context = orch.get_context(session)

            assert "files_read" in context
            assert "tool_counts" in context
            assert "Read" in context["tool_counts"]


class TestIntegration:
    """Integration tests for the unified architecture."""

    def test_end_to_end_claude_parsing(self):
        """End-to-end test: Claude transcript -> events -> context."""
        orch = SessionOrchestrator()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            # Simulate a realistic Claude session
            f.write(
                json.dumps({"type": "user", "message": {"content": "Fix the bug in auth.py"}})
                + "\n"
            )
            f.write(
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {
                            "content": [
                                {
                                    "type": "thinking",
                                    "thinking": "I'll read auth.py to understand the bug",
                                },
                                {
                                    "type": "tool_use",
                                    "name": "Read",
                                    "input": {"file_path": "auth.py"},
                                },
                            ],
                            "model": "claude-sonnet-4-20250514",
                        },
                    }
                )
                + "\n"
            )
            f.write(
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {
                            "content": [
                                {
                                    "type": "thinking",
                                    "thinking": "I see the issue. I'll fix the validation",
                                },
                                {
                                    "type": "tool_use",
                                    "name": "Edit",
                                    "input": {
                                        "file_path": "auth.py",
                                        "old_string": "bug",
                                        "new_string": "fix",
                                    },
                                },
                            ]
                        },
                    }
                )
                + "\n"
            )
            f.flush()

            session = UnifiedSession(
                session_id="integration-test",
                source=Source.CLAUDE,
                file_path=Path(f.name),
                project_path="/project",
                status=SessionStatus.ACTIVE,
                status_reason="test",
                created_at=datetime.now(),
                last_modified=datetime.now(),
            )

            # Get events
            events = orch.get_events(session)
            assert len(events) > 0

            # Check event types
            event_types = [e.event_type for e in events]
            assert EventType.USER_MESSAGE in event_types
            assert EventType.THINKING in event_types
            assert EventType.TOOL in event_types

            # Get context
            context = orch.get_context(session)
            assert "auth.py" in str(context["files_read"]) or "auth.py" in str(
                context["files_modified"]
            )

            # Get health
            health = orch.get_health(session)
            assert health.tool_calls > 0

    def test_teleport_bundle_export(self):
        """Test TeleportBundle export for context transfer."""
        orch = SessionOrchestrator()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {
                            "content": [
                                {
                                    "type": "thinking",
                                    "thinking": "I'll implement the new feature. Goal: add user auth.",
                                },
                                {
                                    "type": "tool_use",
                                    "name": "Write",
                                    "input": {"file_path": "auth.py"},
                                },
                            ]
                        },
                    }
                )
                + "\n"
            )
            f.flush()

            session = UnifiedSession(
                session_id="teleport-test",
                source=Source.CLAUDE,
                file_path=Path(f.name),
                project_path="/project",
                status=SessionStatus.ACTIVE,
                status_reason="test",
                created_at=datetime.now(),
                last_modified=datetime.now(),
            )

            bundle = orch.export_teleport(session)

            assert bundle.source_session == "teleport-test"
            assert bundle.source_model == "claude"
            assert len(bundle.files_touched) > 0

    def test_teleport_planning_docs(self):
        """Test planning docs inclusion in TeleportBundle."""
        orch = SessionOrchestrator()

        # Create a temp directory with planning docs
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)

            # Create planning docs
            (project_path / "ROADMAP.md").write_text(
                "# Project Roadmap\n\n## Phase 1\nImplement auth system.\n\n## Phase 2\nAdd features."
            )
            (project_path / "ARCHITECTURE.md").write_text(
                "# Architecture\n\nThis is the architecture doc."
            )
            (project_path / "CONTRIBUTING.md").write_text("# Contributing\n\nHow to contribute.")

            # Create .claude/commands directory with slash commands
            commands_dir = project_path / ".claude" / "commands"
            commands_dir.mkdir(parents=True)
            (commands_dir / "test-cmd.md").write_text("Run tests and validate code")

            # Create .motus/intent.yaml
            motus_dir = project_path / ".motus"
            motus_dir.mkdir(parents=True)
            (motus_dir / "intent.yaml").write_text("task: implement auth\nconstraints:\n  - secure")

            # Create a session transcript
            transcript_file = project_path / "session.jsonl"
            with open(transcript_file, "w") as f:
                f.write(
                    json.dumps(
                        {
                            "type": "assistant",
                            "message": {
                                "content": [
                                    {
                                        "type": "thinking",
                                        "thinking": "I'll add auth. Goal: secure login.",
                                    },
                                    {
                                        "type": "tool_use",
                                        "name": "Write",
                                        "input": {"file_path": "auth.py"},
                                    },
                                ]
                            },
                        }
                    )
                    + "\n"
                )

            session = UnifiedSession(
                session_id="test-planning-docs",
                source=Source.CLAUDE,
                file_path=transcript_file,
                project_path=str(project_path),
                status=SessionStatus.ACTIVE,
                status_reason="test",
                created_at=datetime.now(),
                last_modified=datetime.now(),
            )

            # Test with planning docs enabled (default)
            bundle = orch.export_teleport(session, include_planning_docs=True)
            assert bundle.planning_docs is not None
            assert "ROADMAP.md" in bundle.planning_docs
            assert "ARCHITECTURE.md" in bundle.planning_docs
            assert "CONTRIBUTING.md" in bundle.planning_docs
            assert ".claude/commands" in bundle.planning_docs
            assert "intent.yaml" in bundle.planning_docs

            # Verify content summaries are reasonable length
            assert len(bundle.planning_docs["ROADMAP.md"]) < 600
            assert "Project Roadmap" in bundle.planning_docs["ROADMAP.md"]

            # Verify slash commands are summarized
            assert "test-cmd" in bundle.planning_docs[".claude/commands"]

            # Test with planning docs disabled
            bundle_no_docs = orch.export_teleport(session, include_planning_docs=False)
            assert len(bundle_no_docs.planning_docs) == 0

    def test_teleport_planning_docs_markdown(self):
        """Test planning docs appear in markdown output."""
        orch = SessionOrchestrator()

        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)

            # Create a simple planning doc
            (project_path / "ROADMAP.md").write_text("# Roadmap\n\nBuild awesome features.")

            # Create session
            transcript_file = project_path / "session.jsonl"
            with open(transcript_file, "w") as f:
                f.write(
                    json.dumps(
                        {
                            "type": "assistant",
                            "message": {
                                "content": [{"type": "thinking", "thinking": "Starting work"}]
                            },
                        }
                    )
                    + "\n"
                )

            session = UnifiedSession(
                session_id="test-markdown",
                source=Source.CLAUDE,
                file_path=transcript_file,
                project_path=str(project_path),
                status=SessionStatus.ACTIVE,
                status_reason="test",
                created_at=datetime.now(),
                last_modified=datetime.now(),
            )

            bundle = orch.export_teleport(session, include_planning_docs=True)
            markdown = bundle.to_markdown()

            # Verify planning context section exists
            assert "### Planning Context" in markdown
            assert "#### ROADMAP.md" in markdown
            assert "Build awesome features" in markdown

    def test_detect_planning_docs_missing_project(self):
        """Test planning docs detection with non-existent project path."""
        orch = SessionOrchestrator()
        docs = orch._detect_planning_docs("/nonexistent/path/xyz123")
        assert docs == {}
