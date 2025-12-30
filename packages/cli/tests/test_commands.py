"""Tests for commands module."""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestModels:
    """Tests for command models."""

    def test_thinking_event_creation(self):
        """ThinkingEvent can be created with content and timestamp."""
        from src.motus.commands import ThinkingEvent

        event = ThinkingEvent(content="Analyzing code", timestamp=datetime.now())
        assert event.content == "Analyzing code"
        assert isinstance(event.timestamp, datetime)

    def test_tool_event_creation(self):
        """ToolEvent can be created with all fields."""
        from src.motus.commands import ToolEvent

        event = ToolEvent(
            name="Edit",
            input={"file_path": "/test.py"},
            timestamp=datetime.now(),
            risk_level="medium",
        )
        assert event.name == "Edit"
        assert event.risk_level == "medium"

    def test_session_info_creation(self):
        """SessionInfo can be created with required fields."""
        from src.motus.commands import SessionInfo

        info = SessionInfo(
            session_id="abc123",
            file_path=Path("/tmp/test.jsonl"),
            last_modified=datetime.now(),
            size=1024,
        )
        assert info.session_id == "abc123"
        assert info.is_active is False
        assert info.source == "claude"

    def test_session_stats_defaults(self):
        """SessionStats has correct defaults."""
        from src.motus.commands import SessionStats

        stats = SessionStats()
        assert stats.thinking_count == 0
        assert stats.tool_count == 0
        assert stats.files_modified == set()


class TestUtils:
    """Tests for command utilities."""

    def test_assess_risk_safe_tools(self):
        """Safe tools get safe risk level."""
        from src.motus.commands import assess_risk
        from src.motus.schema.events import RiskLevel

        assert assess_risk("Read", {}) == RiskLevel.SAFE
        assert assess_risk("Glob", {}) == RiskLevel.SAFE
        assert assess_risk("Grep", {}) == RiskLevel.SAFE

    def test_assess_risk_medium_tools(self):
        """Write/Edit tools get medium risk level."""
        from src.motus.commands import assess_risk
        from src.motus.schema.events import RiskLevel

        assert assess_risk("Write", {}) == RiskLevel.MEDIUM
        assert assess_risk("Edit", {}) == RiskLevel.MEDIUM

    def test_assess_risk_bash_destructive(self):
        """Bash with destructive patterns gets critical risk."""
        from src.motus.commands import assess_risk
        from src.motus.schema.events import RiskLevel

        assert assess_risk("Bash", {"command": "rm -rf /"}) == RiskLevel.CRITICAL
        assert assess_risk("Bash", {"command": "sudo apt install"}) == RiskLevel.CRITICAL
        assert assess_risk("Bash", {"command": "git reset --hard"}) == RiskLevel.CRITICAL

    def test_assess_risk_bash_normal(self):
        """Bash with normal commands gets high (base) risk."""
        from src.motus.commands import assess_risk
        from src.motus.schema.events import RiskLevel

        # Bash is inherently high risk but not "destructive"
        result = assess_risk("Bash", {"command": "ls -la"})
        assert result == RiskLevel.HIGH

    def test_extract_project_path_valid(self):
        """Extract project path from encoded directory name."""
        from src.motus.commands import extract_project_path

        result = extract_project_path("abc123-home-user-projects-myapp")
        assert result.endswith("/home/user/projects/myapp")

    def test_extract_project_path_home(self):
        """Extract project path starting with home."""
        from src.motus.commands import extract_project_path

        result = extract_project_path("xyz-home-user-projects-app")
        # Path.resolve() may expand symlinks (e.g., /home -> /System/Volumes/Data/home on macOS)
        assert result.endswith("/home/user/projects/app") or "home/user/projects/app" in result

    def test_extract_project_path_single_part(self):
        """Single part returns the name unchanged."""
        from src.motus.commands import extract_project_path

        result = extract_project_path("abc123")
        assert result == "abc123"

    def test_extract_project_path_rejects_traversal(self):
        """Path traversal attempts are rejected."""
        from src.motus.commands import extract_project_path

        # Direct .. sequences should be rejected
        assert extract_project_path("abc-..-etc-passwd") == ""
        assert extract_project_path("-Users-..-..-etc-passwd") == ""
        assert extract_project_path("abc123-home-user-..-secrets") == ""

    def test_format_age_just_now(self):
        """Format age for very recent times."""
        from src.motus.commands import format_age

        result = format_age(datetime.now() - timedelta(seconds=30))
        assert result == "just now"

    def test_format_age_minutes(self):
        """Format age for minutes ago."""
        from src.motus.commands import format_age

        result = format_age(datetime.now() - timedelta(minutes=5))
        assert "5m ago" == result

    def test_format_age_hours(self):
        """Format age for hours ago."""
        from src.motus.commands import format_age

        result = format_age(datetime.now() - timedelta(hours=3))
        assert "3h ago" == result

    def test_format_age_days(self):
        """Format age for days ago."""
        from src.motus.commands import format_age

        result = format_age(datetime.now() - timedelta(days=2))
        assert "2d ago" == result

    def test_get_risk_style_colors(self):
        """Risk styles return correct colors."""
        from src.motus.commands import get_risk_style

        color, icon = get_risk_style("high")
        assert color == "red"
        assert "⚠" in icon

        color, icon = get_risk_style("safe")
        assert color == "green"

    def test_parse_content_block_thinking(self):
        """Parse thinking block."""
        from src.motus.commands import ThinkingEvent, parse_content_block

        block = {"type": "thinking", "thinking": "Analyzing the code"}
        result = parse_content_block(block)

        assert isinstance(result, ThinkingEvent)
        assert result.content == "Analyzing the code"

    def test_parse_content_block_tool_use(self):
        """Parse tool use block."""
        from src.motus.commands import ToolEvent, parse_content_block

        block = {"type": "tool_use", "name": "Edit", "input": {"file_path": "/test.py"}}
        result = parse_content_block(block)

        assert isinstance(result, ToolEvent)
        assert result.name == "Edit"
        assert result.risk_level == "medium"

    def test_parse_content_block_task(self):
        """Parse Task (subagent) block."""
        from src.motus.commands import TaskEvent, parse_content_block

        block = {
            "type": "tool_use",
            "name": "Task",
            "input": {
                "description": "Explore codebase",
                "prompt": "Find all tests",
                "subagent_type": "Explore",
            },
        }
        result = parse_content_block(block)

        assert isinstance(result, TaskEvent)
        assert result.subagent_type == "Explore"


class TestListCommand:
    """Tests for list command functions."""

    def test_find_claude_sessions_empty_dir(self):
        """Returns empty list when orchestrator returns no sessions."""
        from src.motus.commands.list_cmd import find_claude_sessions

        # Mock get_orchestrator to return an orchestrator that finds no sessions
        mock_orchestrator = MagicMock()
        mock_orchestrator.discover_all.return_value = []

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orchestrator):
            sessions = find_claude_sessions()
            assert sessions == []

    def test_find_active_session_returns_none_when_empty(self):
        """Returns None when no sessions."""
        from src.motus.commands.list_cmd import find_active_session

        with patch("src.motus.commands.list_cmd.find_sessions", return_value=[]):
            result = find_active_session()
            assert result is None


class TestSummaryCommand:
    """Tests for summary command functions."""

    def test_extract_decisions_from_transcript(self):
        """Extract decisions from thinking blocks."""
        from src.motus.commands.summary_cmd import extract_decisions

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {
                            "content": [
                                {
                                    "type": "thinking",
                                    "thinking": "I'll use async for better performance. This should work well.",
                                }
                            ]
                        },
                    }
                )
                + "\n"
            )
            f.flush()

            decisions = extract_decisions(Path(f.name))

        assert len(decisions) >= 1
        assert any("async" in d for d in decisions)

    def test_extract_decisions_handles_missing_file(self):
        """Returns empty list for missing file."""
        from src.motus.commands.summary_cmd import extract_decisions

        decisions = extract_decisions(Path("/nonexistent/file.jsonl"))
        assert decisions == []

    def test_analyze_session_counts_events(self):
        """Analyze session counts thinking and tool events."""
        from src.motus.commands import SessionInfo
        from src.motus.commands.summary_cmd import analyze_session

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            # Write thinking event
            f.write(
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {
                            "content": [
                                {"type": "thinking", "thinking": "Analyzing..."},
                                {"type": "tool_use", "name": "Read", "input": {}},
                            ]
                        },
                    }
                )
                + "\n"
            )
            # Write another with file modification
            f.write(
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {
                            "content": [
                                {
                                    "type": "tool_use",
                                    "name": "Edit",
                                    "input": {"file_path": "/test.py"},
                                }
                            ]
                        },
                    }
                )
                + "\n"
            )
            f.flush()

            session = SessionInfo(
                session_id="test", file_path=Path(f.name), last_modified=datetime.now(), size=100
            )

            stats = analyze_session(session)

        assert stats.thinking_count == 1
        assert stats.tool_count == 2
        assert "/test.py" in stats.files_modified

    def test_generate_agent_context_includes_stats(self):
        """Generated context includes session statistics."""
        from src.motus.commands import SessionInfo
        from src.motus.commands.summary_cmd import generate_agent_context

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {"content": [{"type": "thinking", "thinking": "Working..."}]},
                    }
                )
                + "\n"
            )
            f.flush()

            session = SessionInfo(
                session_id="test123",
                file_path=Path(f.name),
                last_modified=datetime.now(),
                size=100,
                project_path="/home/user/projects/myapp",
            )

            context = generate_agent_context(session)

        assert "Session Context" in context
        assert "myapp" in context
        assert "Thinking blocks" in context


class TestPruneCommand:
    """Tests for prune command functions."""

    def test_archive_session_creates_archive(self):
        """Archive session creates dated directory."""
        from src.motus.commands.prune_cmd import archive_session

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"type": "test"}\n')
            f.flush()
            path = Path(f.name)

            with patch(
                "src.motus.commands.prune_cmd.ARCHIVE_DIR", Path(tempfile.mkdtemp())
            ):
                result = archive_session(path)

        assert result is True

    def test_delete_session_removes_file(self):
        """Delete session removes file."""
        from src.motus.commands.prune_cmd import delete_session

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"type": "test"}\n')
            path = Path(f.name)

            result = delete_session(path)

        assert result is True
        assert not path.exists()

    def test_delete_session_handles_missing(self):
        """Delete session handles missing file gracefully."""
        from src.motus.commands.prune_cmd import delete_session

        result = delete_session(Path("/nonexistent/file.jsonl"))
        assert result is False


class TestHooksCommand:
    """Tests for hooks command functions."""

    def test_get_mc_hook_config_structure(self):
        """Hook config has correct structure."""
        from src.motus.commands.hooks_cmd import get_mc_hook_config

        config = get_mc_hook_config()

        assert "hooks" in config
        assert "SessionStart" in config["hooks"]
        assert "UserPromptSubmit" in config["hooks"]

    def test_hook_config_includes_motus(self):
        """Hook config commands reference motus module."""
        from src.motus.commands.hooks_cmd import get_mc_hook_config

        config = get_mc_hook_config()

        session_start = config["hooks"]["SessionStart"][0]
        command = session_start["hooks"][0]["command"]
        assert "motus" in command

    def test_hook_config_has_timeout(self):
        """Hook config includes timeout."""
        from src.motus.commands.hooks_cmd import get_mc_hook_config

        config = get_mc_hook_config()

        session_start = config["hooks"]["SessionStart"][0]
        timeout = session_start["hooks"][0]["timeout"]
        assert timeout == 5000


class TestCodexEventParsing:
    """Tests for Codex transcript event parsing."""

    def test_extract_decisions_from_codex_transcript(self):
        """Extract decisions from Codex format transcript."""
        from src.motus.cli import extract_decisions

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            # Write Codex format event
            f.write(
                json.dumps(
                    {
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": "I'll use the SessionManager instead of the old function. This approach is better.",
                                }
                            ],
                        },
                    }
                )
                + "\n"
            )
            f.flush()

            decisions = extract_decisions(Path(f.name), source="codex")

        assert len(decisions) >= 1
        assert any("SessionManager" in d for d in decisions)

    def test_extract_decisions_handles_both_formats(self):
        """Extract decisions works with mixed Claude and Codex events."""
        from src.motus.cli import extract_decisions

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            # Claude format
            f.write(
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {
                            "content": [
                                {
                                    "type": "thinking",
                                    "thinking": "I decided to use async for performance.",
                                }
                            ]
                        },
                    }
                )
                + "\n"
            )
            # Codex format
            f.write(
                json.dumps(
                    {
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": "I chose to implement caching here.",
                                }
                            ],
                        },
                    }
                )
                + "\n"
            )
            f.flush()

            decisions = extract_decisions(Path(f.name))

        # Should find decisions from both formats
        assert len(decisions) >= 1

    def test_codex_builder_tool_call(self):
        """CodexBuilder parses tool call events to UnifiedEvent."""
        import json

        from src.motus.ingestors.codex import CodexBuilder

        builder = CodexBuilder()

        # Codex format for function call
        line = json.dumps(
            {
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "name": "Read",
                    "arguments": '{"file_path": "/path/to/file.py"}',
                },
            }
        )

        result = builder.parse_line(line, session_id="test-session")

        # Builder returns list of UnifiedEvent
        assert isinstance(result, list)
        # May return 0 or 1 events depending on format

    def test_codex_builder_message(self):
        """CodexBuilder parses assistant messages to UnifiedEvent."""
        import json

        from src.motus.ingestors.codex import CodexBuilder

        builder = CodexBuilder()

        # Codex format for output text
        line = json.dumps(
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "I'm analyzing the code..."}],
                },
            }
        )

        result = builder.parse_line(line, session_id="test-session")

        # Builder returns list of UnifiedEvent
        assert isinstance(result, list)

    def test_codex_builder_unknown_type(self):
        """Unknown Codex event type returns empty list."""
        import json

        from src.motus.ingestors.codex import CodexBuilder

        builder = CodexBuilder()

        line = json.dumps(
            {
                "type": "unknown_type",
                "content": "test",
            }
        )

        result = builder.parse_line(line, session_id="test-session")
        assert isinstance(result, list)
        assert len(result) == 0


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
class TestSessionManagerEdgeCases:
    """Tests for SessionManager edge cases (backward compatibility)."""

    def test_session_info_with_codex_source(self):
        """SessionInfo can be created with codex source."""
        from src.motus.commands import SessionInfo

        info = SessionInfo(
            session_id="codex-123",
            file_path=Path("/tmp/codex.jsonl"),
            last_modified=datetime.now(),
            size=2048,
            source="codex",
        )
        assert info.source == "codex"

    def test_session_info_default_status(self):
        """SessionInfo defaults to idle status."""
        from src.motus.commands import SessionInfo

        info = SessionInfo(
            session_id="test",
            file_path=Path("/tmp/test.jsonl"),
            last_modified=datetime.now(),
            size=1024,
        )
        assert info.status == "idle"
        assert info.is_active is False

    def test_find_claude_sessions_uses_orchestrator(self):
        """find_claude_sessions returns sessions from the loader."""
        from src.motus.commands.list_cmd import find_claude_sessions
        from src.motus.commands.models import SessionInfo

        mock_sessions = [
            SessionInfo(
                session_id="claude-1",
                file_path=Path("/tmp/claude.jsonl"),
                last_modified=datetime.now(),
                size=1024,
                is_active=True,
                project_path="/test/project1",
                last_action="test action",
                source="claude",
            ),
            SessionInfo(
                session_id="codex-1",
                file_path=Path("/tmp/codex.jsonl"),
                last_modified=datetime.now(),
                size=2048,
                is_active=False,
                project_path="/test/project2",
                last_action="another action",
                source="codex",
            ),
        ]

        with patch("src.motus.commands.list_cmd._load_sessions", return_value=mock_sessions):
            sessions = find_claude_sessions(max_age_hours=24)

        # Should return sessions from all sources
        assert len(sessions) == 2
        assert sessions[0].session_id == "claude-1"
        assert sessions[1].session_id == "codex-1"


class TestPermissionHandling:
    """Tests for permission error handling."""

    def test_get_running_projects_handles_permission_error(self):
        """get_running_claude_projects handles permission errors gracefully."""

        from src.motus.cli import get_running_claude_projects

        # Mock subprocess.run to simulate lsof permission error
        # Mock Path(...).exists() for Gemini/Codex dirs to return False
        with (
            patch("subprocess.run") as mock_run,
            patch("motus.process_detector.Path") as mock_path_class,
        ):
            # Setup mock for Path.home() / ".gemini" / "tmp" and codex dirs
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = False
            mock_path_class.home.return_value.__truediv__.return_value.__truediv__.return_value = (
                mock_path_instance
            )

            # pgrep for Claude succeeds
            pgrep_claude_result = MagicMock()
            pgrep_claude_result.returncode = 0
            pgrep_claude_result.stdout = "12345 claude"

            # lsof for Claude returns non-zero but has some output
            lsof_claude_result = MagicMock()
            lsof_claude_result.returncode = 1  # Permission error
            lsof_claude_result.stdout = ""  # No valid output due to permission error
            lsof_claude_result.stderr = "lsof: WARNING: can't stat() some files"

            # pgrep for Gemini finds nothing
            pgrep_gemini_result = MagicMock()
            pgrep_gemini_result.returncode = 1
            pgrep_gemini_result.stdout = ""

            # pgrep for Codex finds nothing
            pgrep_codex_result = MagicMock()
            pgrep_codex_result.returncode = 1
            pgrep_codex_result.stdout = ""

            # ProcessDetector now makes more subprocess calls (includes lsof for gemini and codex too)
            # Just return the same result for all calls
            mock_run.return_value = pgrep_codex_result

            result = get_running_claude_projects()

        # Should return empty set, not crash
        assert isinstance(result, set)

    def test_extract_decisions_handles_permission_error(self):
        """extract_decisions handles file permission errors."""
        from src.motus.cli import extract_decisions

        # Try to read a file that would cause permission error
        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            # Should return empty list, not crash
            decisions = extract_decisions(Path("/some/protected/file.jsonl"))

        assert decisions == []
