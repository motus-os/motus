"""Tests for hooks module - Claude Code integration."""

import json
import tempfile
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest


class TestGetProjectSessions:
    """Tests for finding project sessions."""

    def test_returns_empty_list_when_no_directories_exist(self):
        """No sessions when directories don't exist."""
        from motus.hooks import get_project_sessions

        with patch("motus.hooks.CLAUDE_DIR", Path("/nonexistent")):
            with patch("motus.hooks.MC_STATE_DIR", Path("/nonexistent")):
                with patch("motus.hooks.GEMINI_DIR", Path("/nonexistent")):
                    sessions = get_project_sessions("/some/project")
                    assert sessions == []

    def test_finds_claude_sessions_matching_project(self):
        """Finds Claude sessions that match the project path."""
        from motus.hooks import get_project_sessions

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            projects_dir = tmpdir / "projects"

            # Create a matching session directory
            # Project /home/user/projects/myapp -> -home-user-projects-myapp
            session_dir = projects_dir / "abc123-home-user-projects-myapp"
            session_dir.mkdir(parents=True)

            # Create a transcript file
            transcript = session_dir / "transcript.jsonl"
            transcript.write_text('{"type": "test"}\n')

            with patch("motus.hooks.CLAUDE_DIR", tmpdir):
                with patch("motus.hooks.MC_STATE_DIR", Path("/nonexistent")):
                    with patch("motus.hooks.GEMINI_DIR", Path("/nonexistent")):
                        sessions = get_project_sessions("/home/user/projects/myapp")

            assert len(sessions) == 1
            assert sessions[0]["type"] == "claude"
            assert sessions[0]["path"] == transcript

    def test_ignores_old_sessions(self):
        """Sessions older than max_age_hours are ignored."""
        from motus.hooks import get_project_sessions

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            projects_dir = tmpdir / "projects"
            session_dir = projects_dir / "abc123-home-user-projects-myapp"
            session_dir.mkdir(parents=True)

            transcript = session_dir / "transcript.jsonl"
            transcript.write_text('{"type": "test"}\n')

            # Make file old (3 days ago)
            import os

            old_time = (datetime.now() - timedelta(days=3)).timestamp()
            os.utime(transcript, (old_time, old_time))

            with patch("motus.hooks.CLAUDE_DIR", tmpdir):
                with patch("motus.hooks.MC_STATE_DIR", Path("/nonexistent")):
                    with patch("motus.hooks.GEMINI_DIR", Path("/nonexistent")):
                        sessions = get_project_sessions("/home/user/projects/myapp", max_age_hours=24)

            assert len(sessions) == 0

    def test_sessions_sorted_by_mtime_newest_first(self):
        """Sessions are sorted by modification time, newest first."""
        from motus.hooks import get_project_sessions

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            projects_dir = tmpdir / "projects"
            session_dir = projects_dir / "abc123-home-user-projects-myapp"
            session_dir.mkdir(parents=True)

            # Create two transcripts with different times
            import os
            import time

            transcript1 = session_dir / "old.jsonl"
            transcript1.write_text('{"type": "old"}\n')
            old_time = (datetime.now() - timedelta(hours=2)).timestamp()
            os.utime(transcript1, (old_time, old_time))

            time.sleep(0.1)  # Ensure different mtime

            transcript2 = session_dir / "new.jsonl"
            transcript2.write_text('{"type": "new"}\n')

            with patch("motus.hooks.CLAUDE_DIR", tmpdir):
                with patch("motus.hooks.MC_STATE_DIR", Path("/nonexistent")):
                    with patch("motus.hooks.GEMINI_DIR", Path("/nonexistent")):
                        sessions = get_project_sessions("/home/user/projects/myapp")

            assert len(sessions) == 2
            assert sessions[0]["path"].name == "new.jsonl"
            assert sessions[1]["path"].name == "old.jsonl"


class TestExtractDecisions:
    """Tests for extracting decisions from session transcripts."""

    def test_extracts_sdk_decision_events(self):
        """Extracts decisions from SDK Decision events."""
        from motus.hooks import extract_decisions_from_session

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(
                json.dumps(
                    {
                        "type": "Decision",
                        "decision": "Use SQLite for state",
                        "reasoning": "Need queryable history",
                    }
                )
                + "\n"
            )
            f.flush()

            decisions = extract_decisions_from_session(Path(f.name))

        assert len(decisions) == 1
        assert decisions[0]["decision"] == "Use SQLite for state"
        assert decisions[0]["reasoning"] == "Need queryable history"

    def test_extracts_decisions_from_claude_thinking(self):
        """Extracts decisions from Claude thinking blocks."""
        from motus.hooks import extract_decisions_from_session

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {
                            "content": [
                                {
                                    "type": "thinking",
                                    "thinking": "Looking at the code. I'll use async because the batch is large. This should improve performance.",
                                }
                            ]
                        },
                    }
                )
                + "\n"
            )
            f.flush()

            decisions = extract_decisions_from_session(Path(f.name))

        assert len(decisions) == 1
        assert "I'll use async" in decisions[0]["decision"]

    def test_handles_malformed_json(self):
        """Gracefully handles malformed JSON lines."""
        from motus.hooks import extract_decisions_from_session

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write("not valid json\n")
            f.write(json.dumps({"type": "Decision", "decision": "Valid"}) + "\n")
            f.flush()

            decisions = extract_decisions_from_session(Path(f.name))

        assert len(decisions) == 1
        assert decisions[0]["decision"] == "Valid"

    def test_limits_max_decisions(self):
        """Respects max_decisions limit."""
        from motus.hooks import extract_decisions_from_session

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for i in range(10):
                f.write(json.dumps({"type": "Decision", "decision": f"Decision {i}"}) + "\n")
            f.flush()

            decisions = extract_decisions_from_session(Path(f.name), max_decisions=3)

        assert len(decisions) == 3

    def test_handles_missing_file(self):
        """Returns empty list for missing files."""
        from motus.hooks import extract_decisions_from_session

        decisions = extract_decisions_from_session(Path("/nonexistent/file.jsonl"))
        assert decisions == []


class TestExtractFilePatterns:
    """Tests for extracting file modification patterns."""

    def test_counts_write_tool_calls(self):
        """Counts Write tool calls."""
        from motus.hooks import extract_file_patterns

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(
                json.dumps(
                    {"type": "tool_use", "name": "Write", "input": {"file_path": "/src/app.py"}}
                )
                + "\n"
            )
            f.write(
                json.dumps(
                    {"type": "tool_use", "name": "Write", "input": {"file_path": "/src/app.py"}}
                )
                + "\n"
            )
            f.flush()

            patterns = extract_file_patterns(Path(f.name))

        assert patterns["/src/app.py"] == 2

    def test_counts_edit_tool_calls(self):
        """Counts Edit tool calls."""
        from motus.hooks import extract_file_patterns

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(
                json.dumps(
                    {"type": "tool_use", "name": "Edit", "input": {"file_path": "/src/utils.py"}}
                )
                + "\n"
            )
            f.flush()

            patterns = extract_file_patterns(Path(f.name))

        assert patterns["/src/utils.py"] == 1

    def test_ignores_read_tool_calls(self):
        """Ignores Read tool calls (not modifications)."""
        from motus.hooks import extract_file_patterns

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(
                json.dumps(
                    {"type": "tool_use", "name": "Read", "input": {"file_path": "/src/app.py"}}
                )
                + "\n"
            )
            f.flush()

            patterns = extract_file_patterns(Path(f.name))

        assert "/src/app.py" not in patterns


class TestGenerateContextInjection:
    """Tests for context injection generation."""

    def test_returns_empty_string_when_no_sessions(self):
        """Returns empty string when no sessions exist."""
        from motus.hooks import generate_context_injection

        with patch("motus.hooks.get_project_sessions", return_value=[]):
            context = generate_context_injection("/some/project")

        assert context == ""

    def test_includes_mc_context_tags(self):
        """Context is wrapped in mc-context tags."""
        from motus.hooks import generate_context_injection

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(json.dumps({"type": "Decision", "decision": "Test"}) + "\n")
            f.flush()

            mock_sessions = [{"path": Path(f.name), "mtime": datetime.now(), "type": "claude"}]

            with patch("motus.hooks.get_project_sessions", return_value=mock_sessions):
                context = generate_context_injection("/some/project")

        assert context.startswith("<mc-context>")
        assert context.endswith("</mc-context>")

    def test_includes_decisions_section(self):
        """Context includes decisions section."""
        from motus.hooks import generate_context_injection

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(
                json.dumps(
                    {"type": "Decision", "decision": "Use Redis for caching", "reasoning": "Fast"}
                )
                + "\n"
            )
            f.flush()

            mock_sessions = [{"path": Path(f.name), "mtime": datetime.now(), "type": "claude"}]

            with patch("motus.hooks.get_project_sessions", return_value=mock_sessions):
                context = generate_context_injection("/some/project")

        assert "### Recent Decisions" in context
        assert "Use Redis for caching" in context

    def test_includes_hot_files_section(self):
        """Context includes hot files section."""
        from motus.hooks import generate_context_injection

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(
                json.dumps(
                    {
                        "type": "tool_use",
                        "name": "Edit",
                        "input": {"file_path": "/project/src/app.py"},
                    }
                )
                + "\n"
            )
            f.flush()

            mock_sessions = [{"path": Path(f.name), "mtime": datetime.now(), "type": "claude"}]

            with patch("motus.hooks.get_project_sessions", return_value=mock_sessions):
                context = generate_context_injection("/project")

        assert "### Hot Files" in context
        assert "app.py" in context


class TestGetHookConfig:
    """Tests for hook configuration generation."""

    def test_returns_valid_config_structure(self):
        """Returns valid hook config structure."""
        from motus.hooks import get_hook_config

        config = get_hook_config()

        assert "hooks" in config
        assert "SessionStart" in config["hooks"]
        assert "UserPromptSubmit" in config["hooks"]

    def test_session_start_hook_config(self):
        """SessionStart hook has correct structure."""
        from motus.hooks import get_hook_config

        config = get_hook_config()
        session_start = config["hooks"]["SessionStart"][0]

        assert session_start["matcher"] == "*"
        assert len(session_start["hooks"]) == 1
        assert session_start["hooks"][0]["type"] == "command"
        assert "session_start_hook" in session_start["hooks"][0]["command"]
        assert session_start["hooks"][0]["timeout"] == 5000

    def test_user_prompt_hook_config(self):
        """UserPromptSubmit hook has correct structure."""
        from motus.hooks import get_hook_config

        config = get_hook_config()
        user_prompt = config["hooks"]["UserPromptSubmit"][0]

        assert user_prompt["matcher"] == "*"
        assert "user_prompt_hook" in user_prompt["hooks"][0]["command"]
        assert user_prompt["hooks"][0]["timeout"] == 3000


class TestSessionStartHook:
    """Tests for the session start hook."""

    def test_outputs_context_for_valid_input(self):
        """Outputs context when valid cwd is provided."""
        from motus.hooks import session_start_hook

        hook_input = json.dumps({"cwd": "/home/user/projects/myapp"})

        with patch("sys.stdin", StringIO(hook_input)):
            with patch(
                "motus.hooks.generate_context_injection",
                return_value="<mc-context>test</mc-context>",
            ):
                with patch("builtins.print") as mock_print:
                    with pytest.raises(SystemExit) as exc_info:
                        session_start_hook()

        assert exc_info.value.code == 0
        mock_print.assert_called_once_with("<mc-context>test</mc-context>")

    def test_exits_cleanly_on_invalid_json(self):
        """Exits with 0 on invalid JSON (don't block Claude)."""
        from motus.hooks import session_start_hook

        with patch("sys.stdin", StringIO("not valid json")):
            with pytest.raises(SystemExit) as exc_info:
                session_start_hook()

        assert exc_info.value.code == 0

    def test_no_output_when_no_context(self):
        """No output when context is empty."""
        from motus.hooks import session_start_hook

        hook_input = json.dumps({"cwd": "/some/project"})

        with patch("sys.stdin", StringIO(hook_input)):
            with patch("motus.hooks.generate_context_injection", return_value=""):
                with patch("builtins.print") as mock_print:
                    with pytest.raises(SystemExit) as exc_info:
                        session_start_hook()

        assert exc_info.value.code == 0
        mock_print.assert_not_called()


class TestUserPromptHook:
    """Tests for the user prompt hook."""

    def test_injects_context_for_resume_keywords(self):
        """Injects context when prompt contains resume keywords."""
        from motus.hooks import user_prompt_hook

        hook_input = json.dumps(
            {"cwd": "/project", "prompt": "Where was I? Continue from last session."}
        )

        with patch("sys.stdin", StringIO(hook_input)):
            with patch(
                "motus.hooks.generate_context_injection", return_value="<context>"
            ) as mock_gen:
                with patch("builtins.print") as mock_print:
                    with pytest.raises(SystemExit):
                        user_prompt_hook()

        mock_gen.assert_called_once()
        mock_print.assert_called_once_with("<context>")

    def test_no_injection_for_normal_prompts(self):
        """No context injection for normal prompts."""
        from motus.hooks import user_prompt_hook

        hook_input = json.dumps({"cwd": "/project", "prompt": "Write a function to sort a list"})

        with patch("sys.stdin", StringIO(hook_input)):
            with patch("motus.hooks.generate_context_injection") as mock_gen:
                with patch("builtins.print") as mock_print:
                    with pytest.raises(SystemExit):
                        user_prompt_hook()

        mock_gen.assert_not_called()
        mock_print.assert_not_called()

    def test_triggers_on_what_did_keyword(self):
        """Triggers on 'what did' keyword."""
        from motus.hooks import user_prompt_hook

        hook_input = json.dumps({"cwd": "/project", "prompt": "What did I do in the last session?"})

        with patch("sys.stdin", StringIO(hook_input)):
            with patch(
                "motus.hooks.generate_context_injection", return_value="<ctx>"
            ) as mock_gen:
                with pytest.raises(SystemExit):
                    user_prompt_hook()

        mock_gen.assert_called_once()

    def test_triggers_on_remember_keyword(self):
        """Triggers on 'remember' keyword."""
        from motus.hooks import user_prompt_hook

        hook_input = json.dumps(
            {"cwd": "/project", "prompt": "Do you remember the decision we made?"}
        )

        with patch("sys.stdin", StringIO(hook_input)):
            with patch(
                "motus.hooks.generate_context_injection", return_value="<ctx>"
            ) as mock_gen:
                with pytest.raises(SystemExit):
                    user_prompt_hook()

        mock_gen.assert_called_once()
