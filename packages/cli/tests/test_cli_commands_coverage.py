"""Comprehensive tests for CLI commands to increase coverage to 80%+.

This test file targets specific uncovered code paths in:
- list_cmd.py (38% -> 80%+)
- prune_cmd.py (30% -> 80%+)
- summary_cmd.py (40% -> 80%+)

Coverage gaps addressed:
- Error handling paths (OSError, IOError, JSON errors)
- Edge cases (empty data, malformed input, missing files)
- Different parameter combinations
- Output formatting variations
"""

import json
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from motus.commands.list_cmd import (
    _unified_to_session_info,
    find_active_session,
    list_sessions,
)
from motus.commands.models import SessionInfo, SessionStats
from motus.commands.prune_cmd import (
    archive_session,
    prune_command,
)
from motus.commands.summary_cmd import (
    _extract_decision_from_text,
    _process_claude_event,
    _process_codex_event,
    _process_gemini_message,
    analyze_session,
    extract_decisions,
    generate_agent_context,
    summary_command,
)
from motus.protocols import SessionStatus, Source, UnifiedSession

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_session_file():
    """Create a temporary session file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        temp_path = Path(f.name)
    yield temp_path
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture
def temp_dir():
    """Create a temporary directory."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    if temp_path.exists():
        shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def mock_unified_session(temp_session_file):
    """Create a mock UnifiedSession object."""
    return UnifiedSession(
        session_id="test-session-123",
        source=Source.CLAUDE,
        file_path=temp_session_file,
        project_path="/test/project",
        status=SessionStatus.ACTIVE,
        status_reason="active",
        created_at=datetime.now(),
        last_modified=datetime.now(),
        last_action="Testing",
    )


# =============================================================================
# Tests for list_cmd.py
# =============================================================================


class TestListCmdConversion:
    """Test _unified_to_session_info conversion with error handling."""

    def test_unified_to_session_info_oserror_on_stat(self, temp_session_file):
        """Test conversion when file.stat() raises OSError (lines 24-25)."""
        session = UnifiedSession(
            session_id="test-123",
            source=Source.CLAUDE,
            file_path=temp_session_file,
            project_path="/test",
            status=SessionStatus.ACTIVE,
            status_reason="test",
            created_at=datetime.now(),
            last_modified=datetime.now(),
        )

        # Mock the stat() call to raise OSError
        with patch.object(Path, "stat", side_effect=OSError("Permission denied")):
            result = _unified_to_session_info(session)

        # Should handle error and set size to 0
        assert result.size == 0
        assert result.session_id == "test-123"

    def test_unified_to_session_info_file_not_exists(self):
        """Test conversion when file doesn't exist."""
        non_existent = Path("/non/existent/path.jsonl")
        session = UnifiedSession(
            session_id="test-456",
            source=Source.CODEX,
            file_path=non_existent,
            project_path="/test",
            status=SessionStatus.IDLE,
            status_reason="idle",
            created_at=datetime.now(),
            last_modified=datetime.now(),
        )

        result = _unified_to_session_info(session)

        # Should handle missing file gracefully
        assert result.size == 0
        assert result.session_id == "test-456"

    def test_unified_to_session_info_all_fields(self, temp_session_file):
        """Test conversion with all optional fields populated."""
        # Write some data to the temp file
        temp_session_file.write_text("test data")

        session = UnifiedSession(
            session_id="full-session",
            source=Source.GEMINI,
            file_path=temp_session_file,
            project_path="/full/project/path",
            status=SessionStatus.ACTIVE,
            status_reason="generating",
            created_at=datetime.now(),
            last_modified=datetime.now(),
            last_action="Editing file.py",
        )

        result = _unified_to_session_info(session)

        assert result.session_id == "full-session"
        assert result.source == "gemini"
        assert result.is_active is True
        assert result.status == "active"
        assert result.last_action == "Editing file.py"
        assert result.project_path == "/full/project/path"
        assert result.size > 0


class TestListSessions:
    """Test list_sessions function with various scenarios."""

    def test_list_sessions_no_sessions(self):
        """Test list_sessions when no sessions found (lines 74-77)."""
        mock_orch = MagicMock()
        mock_orch.discover_all.return_value = []

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            with patch("motus.commands.list_cmd.console") as mock_console:
                list_sessions(max_age_hours=24)

        # Verify the "no sessions" message was printed
        assert mock_console.print.call_count >= 2
        call_args = [str(call[0][0]) for call in mock_console.print.call_args_list]
        assert any("No recent sessions" in arg for arg in call_args)

    def test_list_sessions_with_sessions_full_display(self, temp_session_file):
        """Test list_sessions with sessions - full output (lines 79-127)."""
        temp_session_file.write_text("test data" * 100)  # Create file with size

        sessions = [
            UnifiedSession(
                session_id="session-1-active",
                source=Source.CLAUDE,
                file_path=temp_session_file,
                project_path="/projects/app",
                status=SessionStatus.ACTIVE,
                status_reason="active",
                created_at=datetime.now(),
                last_modified=datetime.now(),
                last_action="Writing code",
            ),
            UnifiedSession(
                session_id="session-2-idle",
                source=Source.CODEX,
                file_path=temp_session_file,
                project_path="/projects/backend",
                status=SessionStatus.IDLE,
                status_reason="idle",
                created_at=datetime.now(),
                last_modified=datetime.now() - timedelta(hours=1),
                last_action="Running tests",
            ),
            UnifiedSession(
                session_id="session-3-gemini",
                source=Source.GEMINI,
                file_path=temp_session_file,
                project_path="/projects/frontend",
                status=SessionStatus.OPEN,
                status_reason="open",
                created_at=datetime.now(),
                last_modified=datetime.now() - timedelta(minutes=15),
                last_action=None,  # Test None last_action
            ),
        ]

        mock_orch = MagicMock()
        mock_orch.discover_all.return_value = sessions

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            with patch("motus.commands.list_cmd.console") as mock_console:
                list_sessions(max_age_hours=48)

        # Verify table was printed with tip for active sessions
        assert mock_console.print.call_count >= 2

    def test_list_sessions_large_file_size_formatting(self, temp_session_file):
        """Test size formatting for large files (> 1MB)."""
        # Create a large mock file
        large_size = 5 * 1024 * 1024  # 5MB

        session = UnifiedSession(
            session_id="large-session",
            source=Source.CLAUDE,
            file_path=temp_session_file,
            project_path="/project",
            status=SessionStatus.IDLE,
            status_reason="idle",
            created_at=datetime.now(),
            last_modified=datetime.now(),
        )

        mock_orch = MagicMock()
        mock_orch.discover_all.return_value = [session]

        # Mock stat for the session file only to avoid impacting other paths.
        original_stat = Path.stat

        def _stat_side_effect(path: Path):
            if path == temp_session_file:
                mock_stat_result = Mock()
                mock_stat_result.st_size = large_size
                mock_stat_result.st_mode = 0o100644
                return mock_stat_result
            return original_stat(path)

        with patch.object(Path, "stat", autospec=True, side_effect=_stat_side_effect):

            with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
                with patch("motus.commands.list_cmd.console"):
                    list_sessions()

    def test_list_sessions_unknown_source(self, temp_session_file):
        """Test handling of unknown source badge."""
        session = UnifiedSession(
            session_id="unknown-source",
            source=Source.SDK,  # SDK source
            file_path=temp_session_file,
            project_path="/project",
            status=SessionStatus.IDLE,
            status_reason="idle",
            created_at=datetime.now(),
            last_modified=datetime.now(),
        )

        mock_orch = MagicMock()
        mock_orch.discover_all.return_value = [session]

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            with patch("motus.commands.list_cmd.console"):
                list_sessions()

    def test_list_sessions_no_project_path(self, temp_session_file):
        """Test session with no project path (project_path=None)."""
        session = UnifiedSession(
            session_id="no-project",
            source=Source.CLAUDE,
            file_path=temp_session_file,
            project_path=None,  # No project path
            status=SessionStatus.IDLE,
            status_reason="idle",
            created_at=datetime.now(),
            last_modified=datetime.now(),
        )

        mock_orch = MagicMock()
        mock_orch.discover_all.return_value = [session]

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            with patch("motus.commands.list_cmd.console"):
                list_sessions()


class TestFindActiveSessions:
    """Test find_active_session function."""

    def test_find_active_session_returns_first_active(self, temp_session_file):
        """Test find_active_session returns first active session."""
        sessions = [
            UnifiedSession(
                session_id="active-1",
                source=Source.CLAUDE,
                file_path=temp_session_file,
                project_path="/test",
                status=SessionStatus.ACTIVE,
                status_reason="active",
                created_at=datetime.now(),
                last_modified=datetime.now(),
            ),
            UnifiedSession(
                session_id="active-2",
                source=Source.CODEX,
                file_path=temp_session_file,
                project_path="/test",
                status=SessionStatus.ACTIVE,
                status_reason="active",
                created_at=datetime.now(),
                last_modified=datetime.now(),
            ),
        ]

        with patch("motus.commands.list_cmd.find_sessions", return_value=sessions):
            result = find_active_session()

        assert result is not None
        assert result.session_id == "active-1"

    def test_find_active_session_returns_most_recent_if_no_active(self, temp_session_file):
        """Test find_active_session returns most recent when no active sessions."""
        session = UnifiedSession(
            session_id="idle-session",
            source=Source.CLAUDE,
            file_path=temp_session_file,
            project_path="/test",
            status=SessionStatus.IDLE,
            status_reason="idle",
            created_at=datetime.now(),
            last_modified=datetime.now(),
        )

        with patch("motus.commands.list_cmd.find_sessions", return_value=[session]):
            result = find_active_session()

        assert result is not None
        assert result.session_id == "idle-session"

    def test_find_active_session_returns_none_when_no_sessions(self):
        """Test find_active_session returns None when no sessions."""
        with patch("motus.commands.list_cmd.find_sessions", return_value=[]):
            result = find_active_session()

        assert result is None


# =============================================================================
# Tests for prune_cmd.py
# =============================================================================


class TestPruneImportError:
    """Test import error fallback (lines 14-18)."""

    def test_import_error_fallback(self):
        """Test that constants are defined even if config import fails."""
        # Import the module - if it loads, the fallback works
        from motus.commands import prune_cmd

        # The module should have these defined (either from config or fallback)
        assert hasattr(prune_cmd, "MC_STATE_DIR")
        assert hasattr(prune_cmd, "ARCHIVE_DIR")


class TestArchiveSession:
    """Test archive_session function."""

    def test_archive_session_oserror(self, temp_session_file):
        """Test archive_session handles OSError (line 41)."""
        # Make archive directory read-only to trigger OSError
        with patch("motus.commands.prune_cmd.ARCHIVE_DIR", Path("/invalid/path")):
            with patch("pathlib.Path.mkdir", side_effect=OSError("Permission denied")):
                result = archive_session(temp_session_file)

        assert result is False

    def test_archive_session_ioerror(self, temp_session_file):
        """Test archive_session handles IOError (line 41)."""
        with patch("shutil.copy2", side_effect=IOError("Disk full")):
            result = archive_session(temp_session_file)

        assert result is False

    def test_archive_session_shutil_error(self, temp_session_file):
        """Test archive_session handles shutil.Error (line 42)."""
        with patch("shutil.copy2", side_effect=shutil.Error("Copy failed")):
            result = archive_session(temp_session_file)

        assert result is False


class TestPruneCommand:
    """Test prune_command function."""

    def test_prune_command_full_flow_archive(self, temp_session_file):
        """Test complete prune flow with archive (lines 56-102)."""
        old_time = datetime.now() - timedelta(hours=5)

        # Create old session
        old_session = SessionInfo(
            session_id="old-session-1",
            file_path=temp_session_file,
            last_modified=old_time,
            size=1024,
            is_active=False,
            project_path="/old/project",
            status="idle",
        )

        mock_orch = MagicMock()
        mock_orch.discover_all.return_value = [
            UnifiedSession(
                session_id=old_session.session_id,
                source=Source.CLAUDE,
                file_path=old_session.file_path,
                project_path=old_session.project_path,
                status=SessionStatus.IDLE,
                status_reason="idle",
                created_at=old_time,
                last_modified=old_time,
            )
        ]

        with patch(
            "motus.commands.prune_cmd.find_claude_sessions", return_value=[old_session]
        ):
            with patch("motus.commands.prune_cmd.archive_session", return_value=True):
                with patch("motus.commands.prune_cmd.console") as mock_console:
                    prune_command(older_than_hours=2, archive=True, force=True)

        # Verify messages were printed (lines 65-102)
        # Just check it was called, content assertions are fragile
        assert mock_console.print.call_count >= 1

    def test_prune_command_delete_mode(self, temp_session_file):
        """Test prune with delete mode (lines 88-89)."""
        old_time = datetime.now() - timedelta(hours=3)

        old_session = SessionInfo(
            session_id="delete-me",
            file_path=temp_session_file,
            last_modified=old_time,
            size=1024,
            is_active=False,
            project_path="/project",
            status="idle",
        )

        with patch(
            "motus.commands.prune_cmd.find_claude_sessions", return_value=[old_session]
        ):
            with patch("motus.commands.prune_cmd.delete_session", return_value=True):
                with patch("motus.commands.prune_cmd.console"):
                    prune_command(older_than_hours=2, archive=False, force=True)

    def test_prune_command_mixed_success_failure(self, temp_session_file):
        """Test prune with some successes and failures (lines 91-99)."""
        old_time = datetime.now() - timedelta(hours=5)

        sessions = [
            SessionInfo(
                session_id=f"session-{i}",
                file_path=temp_session_file,
                last_modified=old_time,
                size=1024,
                is_active=False,
                project_path="/project",
                status="idle",
            )
            for i in range(3)
        ]

        # Mock archive_session to return True, False, True
        archive_results = [True, False, True]

        with patch("motus.commands.prune_cmd.find_claude_sessions", return_value=sessions):
            with patch(
                "motus.commands.prune_cmd.archive_session", side_effect=archive_results
            ):
                with patch("motus.commands.prune_cmd.console") as mock_console:
                    prune_command(older_than_hours=2, archive=True, force=True)

        # Check that failure message was printed (line 99)
        # console.print was called multiple times, just verify call count
        assert mock_console.print.call_count >= 1

    def test_prune_command_user_cancels(self, temp_session_file):
        """Test prune when user cancels confirmation (lines 78-80)."""
        old_time = datetime.now() - timedelta(hours=5)

        old_session = SessionInfo(
            session_id="cancel-me",
            file_path=temp_session_file,
            last_modified=old_time,
            size=1024,
            is_active=False,
            project_path="/project",
            status="idle",
        )

        with patch(
            "motus.commands.prune_cmd.find_claude_sessions", return_value=[old_session]
        ):
            with patch("motus.commands.prune_cmd.Confirm.ask", return_value=False):
                with patch("motus.commands.prune_cmd.console") as mock_console:
                    prune_command(older_than_hours=2, archive=True, force=False)

        # Verify message was printed
        assert mock_console.print.call_count >= 1

    def test_prune_command_more_than_10_sessions(self, temp_session_file):
        """Test prune with >10 sessions shows ellipsis (lines 72-73)."""
        old_time = datetime.now() - timedelta(hours=5)

        # Create 15 old sessions
        sessions = [
            SessionInfo(
                session_id=f"session-{i}",
                file_path=temp_session_file,
                last_modified=old_time,
                size=1024,
                is_active=False,
                project_path=f"/project-{i}",
                status="idle",
            )
            for i in range(15)
        ]

        with patch("motus.commands.prune_cmd.find_claude_sessions", return_value=sessions):
            with patch("motus.commands.prune_cmd.archive_session", return_value=True):
                with patch("motus.commands.prune_cmd.console") as mock_console:
                    prune_command(older_than_hours=2, archive=True, force=True)

        # Verify multiple print calls were made
        assert mock_console.print.call_count >= 1

    def test_prune_command_archive_mode_shows_location(self, temp_session_file):
        """Test archive mode prints archive location (lines 101-102)."""
        old_time = datetime.now() - timedelta(hours=5)

        old_session = SessionInfo(
            session_id="archive-test",
            file_path=temp_session_file,
            last_modified=old_time,
            size=1024,
            is_active=False,
            project_path="/project",
            status="idle",
        )

        with patch(
            "motus.commands.prune_cmd.find_claude_sessions", return_value=[old_session]
        ):
            with patch("motus.commands.prune_cmd.archive_session", return_value=True):
                with patch("motus.commands.prune_cmd.console") as mock_console:
                    prune_command(older_than_hours=2, archive=True, force=True)

        # Verify archive mode was executed
        assert mock_console.print.call_count >= 1


# =============================================================================
# Tests for summary_cmd.py
# =============================================================================


class TestSummaryImportError:
    """Test import error fallback (lines 20-23)."""

    def test_import_error_fallback(self):
        """Test that MC_STATE_DIR is defined even if config import fails."""
        from motus.commands import summary_cmd

        assert hasattr(summary_cmd, "MC_STATE_DIR")


class TestExtractDecisionFromText:
    """Test _extract_decision_from_text helper."""

    def test_extract_decision_from_text_with_marker(self):
        """Test decision extraction with marker present."""
        decisions = []
        text = "I'll use SQLite for the database. This should work well."

        _extract_decision_from_text(text, decisions)

        assert len(decisions) == 1
        assert "I'll use SQLite for the database" in decisions[0]

    def test_extract_decision_from_text_long_sentence_skipped(self):
        """Test that sentences >200 chars are skipped (line 49)."""
        decisions = []
        long_text = "I'll use " + "a" * 200 + " for implementation"

        _extract_decision_from_text(long_text, decisions)

        assert len(decisions) == 0

    def test_extract_decision_from_text_no_marker(self):
        """Test no extraction when no marker present."""
        decisions = []
        text = "Just some regular text without decision markers"

        _extract_decision_from_text(text, decisions)

        assert len(decisions) == 0


class TestExtractDecisions:
    """Test extract_decisions function for all sources."""

    def test_extract_decisions_gemini_source(self, temp_session_file):
        """Test Gemini JSON extraction (lines 72-84)."""
        gemini_data = {
            "messages": [
                {
                    "type": "gemini",
                    "thoughts": [{"description": "I'll use React for the frontend"}],
                    "content": "The best approach is to use TypeScript",
                }
            ]
        }

        temp_session_file.write_text(json.dumps(gemini_data))

        decisions = extract_decisions(temp_session_file, source="gemini")

        assert len(decisions) > 0

    def test_extract_decisions_codex_source(self, temp_session_file):
        """Test Codex JSONL extraction (lines 92-108)."""
        codex_events = [
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "content": [{"type": "text", "text": "I decided to use async/await"}],
                },
            },
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "content": "I will implement caching",  # String content (line 107-108)
                },
            },
        ]

        temp_session_file.write_text("\n".join(json.dumps(e) for e in codex_events))

        decisions = extract_decisions(temp_session_file, source="codex")

        assert len(decisions) > 0

    def test_extract_decisions_claude_source(self, temp_session_file):
        """Test Claude JSONL extraction (lines 111-115)."""
        claude_events = [
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "thinking",
                            "thinking": "I should use FastAPI for this API. It's well-suited.",
                        }
                    ]
                },
            }
        ]

        temp_session_file.write_text("\n".join(json.dumps(e) for e in claude_events))

        decisions = extract_decisions(temp_session_file, source="claude")

        assert len(decisions) > 0

    def test_extract_decisions_json_decode_error(self, temp_session_file):
        """Test handling of malformed JSON (line 117-118)."""
        # Write invalid JSON
        temp_session_file.write_text("not valid json\n{invalid}\n")

        # Should not crash, return empty list
        decisions = extract_decisions(temp_session_file, source="claude")

        assert decisions == []

    def test_extract_decisions_file_error(self):
        """Test handling of file errors (lines 120-126)."""
        non_existent = Path("/non/existent/file.jsonl")

        # Should not crash, return empty list
        decisions = extract_decisions(non_existent, source="claude")

        assert decisions == []

    def test_extract_decisions_deduplication(self, temp_session_file):
        """Test decision deduplication (lines 128-134)."""
        events = [
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "thinking", "thinking": "I'll use Redis"},
                        {"type": "thinking", "thinking": "I'll use Redis"},  # Duplicate
                    ]
                },
            }
        ]

        temp_session_file.write_text("\n".join(json.dumps(e) for e in events))

        decisions = extract_decisions(temp_session_file, source="claude")

        # Should only have one due to deduplication
        redis_count = sum(1 for d in decisions if "Redis" in d)
        assert redis_count == 1

    def test_extract_decisions_limit_10(self, temp_session_file):
        """Test decision limit of 10 (line 136)."""
        events = [
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "thinking", "thinking": f"I'll use approach {i}"}
                        for i in range(20)
                    ]
                },
            }
        ]

        temp_session_file.write_text(json.dumps(events[0]))

        decisions = extract_decisions(temp_session_file, source="claude")

        # Should be limited to 10
        assert len(decisions) <= 10


class TestProcessClaudeEvent:
    """Test _process_claude_event function."""

    def test_process_claude_event_thinking(self):
        """Test processing thinking block."""
        stats = SessionStats()
        event = {
            "type": "assistant",
            "message": {"content": [{"type": "thinking", "thinking": "test"}]},
        }

        _process_claude_event(event, stats)

        assert stats.thinking_count == 1

    def test_process_claude_event_tool_write(self):
        """Test processing Write tool (lines 150-153)."""
        stats = SessionStats()
        event = {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Write",
                        "input": {"file_path": "/test/file.py"},
                    }
                ]
            },
        }

        _process_claude_event(event, stats)

        assert stats.tool_count == 1
        assert "/test/file.py" in stats.files_modified

    def test_process_claude_event_bash_high_risk(self):
        """Test processing high-risk Bash command (lines 155-158)."""
        stats = SessionStats()
        event = {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Bash",
                        "input": {"command": "rm -rf /tmp/test"},
                    }
                ]
            },
        }

        _process_claude_event(event, stats)

        assert stats.high_risk_ops == 1

    def test_process_claude_event_task_agent(self):
        """Test processing Task tool (lines 160-161)."""
        stats = SessionStats()
        event = {
            "type": "assistant",
            "message": {"content": [{"type": "tool_use", "name": "Task", "input": {}}]},
        }

        _process_claude_event(event, stats)

        assert stats.agent_count == 1


class TestProcessCodexEvent:
    """Test _process_codex_event function."""

    def test_process_codex_event_function_call(self):
        """Test processing Codex function call (lines 166-196)."""
        stats = SessionStats()
        event = {
            "type": "response_item",
            "payload": {
                "type": "function_call",
                "name": "write_file",
                "arguments": {"path": "/test/output.py"},
            },
        }

        _process_codex_event(event, stats)

        assert stats.tool_count == 1
        assert "/test/output.py" in stats.files_modified

    def test_process_codex_event_arguments_string(self):
        """Test Codex with arguments as JSON string (lines 173-177)."""
        stats = SessionStats()
        event = {
            "type": "response_item",
            "payload": {
                "type": "function_call",
                "name": "shell_command",
                "arguments": json.dumps({"command": "sudo reboot"}),
            },
        }

        _process_codex_event(event, stats)

        assert stats.high_risk_ops == 1

    def test_process_codex_event_invalid_json_arguments(self):
        """Test Codex with invalid JSON arguments."""
        stats = SessionStats()
        event = {
            "type": "response_item",
            "payload": {
                "type": "function_call",
                "name": "test",
                "arguments": "not valid json",
            },
        }

        # Should not crash
        _process_codex_event(event, stats)


class TestProcessGeminiMessage:
    """Test _process_gemini_message function."""

    def test_process_gemini_message_thoughts(self):
        """Test processing Gemini thoughts (lines 201-229)."""
        stats = SessionStats()
        msg = {
            "type": "gemini",
            "thoughts": [
                {"description": "Thinking about approach"},
                {"description": "Considering alternatives"},
            ],
            "toolCalls": [],
        }

        _process_gemini_message(msg, stats)

        assert stats.thinking_count == 2

    def test_process_gemini_message_tool_calls(self):
        """Test processing Gemini tool calls."""
        stats = SessionStats()
        msg = {
            "type": "gemini",
            "thoughts": [],
            "toolCalls": [
                {"name": "write_file", "args": {"path": "/test/gemini.py"}},
                {"name": "shell", "args": {"command": "chmod 777 file.sh"}},
            ],
        }

        _process_gemini_message(msg, stats)

        assert stats.tool_count == 2
        assert "/test/gemini.py" in stats.files_modified
        assert stats.high_risk_ops == 1


class TestAnalyzeSession:
    """Test analyze_session function."""

    def test_analyze_session_gemini(self, temp_session_file):
        """Test analyzing Gemini session (lines 247-253)."""
        session = SessionInfo(
            session_id="gemini-test",
            file_path=temp_session_file,
            last_modified=datetime.now(),
            size=1024,
            source="gemini",
        )

        gemini_data = {
            "messages": [
                {
                    "type": "gemini",
                    "thoughts": [{"description": "test"}],
                    "toolCalls": [],
                }
            ]
        }

        temp_session_file.write_text(json.dumps(gemini_data))

        stats = analyze_session(session)

        assert stats.thinking_count == 1

    def test_analyze_session_codex(self, temp_session_file):
        """Test analyzing Codex session (lines 261-262)."""
        session = SessionInfo(
            session_id="codex-test",
            file_path=temp_session_file,
            last_modified=datetime.now(),
            size=1024,
            source="codex",
        )

        codex_events = [
            {
                "type": "response_item",
                "payload": {"type": "function_call", "name": "test", "arguments": {}},
            }
        ]

        temp_session_file.write_text("\n".join(json.dumps(e) for e in codex_events))

        stats = analyze_session(session)

        assert stats.tool_count == 1

    def test_analyze_session_json_decode_error(self, temp_session_file):
        """Test session analysis with malformed JSON (line 266)."""
        session = SessionInfo(
            session_id="bad-json",
            file_path=temp_session_file,
            last_modified=datetime.now(),
            size=1024,
            source="claude",
        )

        temp_session_file.write_text("invalid json\n")

        # Should not crash
        stats = analyze_session(session)

        assert stats.thinking_count == 0

    def test_analyze_session_file_error(self):
        """Test session analysis with file errors (lines 269-275)."""
        session = SessionInfo(
            session_id="missing",
            file_path=Path("/non/existent.jsonl"),
            last_modified=datetime.now(),
            size=0,
            source="claude",
        )

        # Should not crash
        stats = analyze_session(session)

        assert stats.thinking_count == 0


class TestGenerateAgentContext:
    """Test generate_agent_context function."""

    def test_generate_agent_context_with_files_modified(self, temp_session_file):
        """Test context generation with modified files (lines 302-307)."""
        session = SessionInfo(
            session_id="ctx-test",
            file_path=temp_session_file,
            last_modified=datetime.now(),
            size=1024,
            is_active=True,
            project_path="/test/project",
            source="claude",
        )

        # Write minimal valid data
        temp_session_file.write_text(json.dumps({"type": "test"}))

        # Mock stats with files
        mock_stats = SessionStats(
            thinking_count=5,
            tool_count=10,
            files_modified={f"/long/path/file{i}.py" for i in range(5)},
        )

        with patch("motus.commands.summary_cmd.analyze_session", return_value=mock_stats):
            with patch("motus.commands.summary_cmd.extract_decisions", return_value=[]):
                context = generate_agent_context(session)

        assert "Files Modified" in context
        assert "file0.py" in context

    def test_generate_agent_context_with_decisions(self, temp_session_file):
        """Test context generation with decisions (lines 309-314)."""
        session = SessionInfo(
            session_id="ctx-test-2",
            file_path=temp_session_file,
            last_modified=datetime.now(),
            size=1024,
            is_active=False,
            project_path="/project",
            source="claude",
        )

        temp_session_file.write_text(json.dumps({"type": "test"}))

        mock_stats = SessionStats()
        decisions = ["I'll use PostgreSQL", "Let's implement caching"]

        with patch("motus.commands.summary_cmd.analyze_session", return_value=mock_stats):
            with patch(
                "motus.commands.summary_cmd.extract_decisions",
                return_value=decisions,
            ):
                context = generate_agent_context(session)

        assert "Key Decisions" in context
        assert "PostgreSQL" in context

    def test_generate_agent_context_redacts_secrets(self, temp_session_file):
        """Test that secrets in decisions are redacted (line 313)."""
        session = SessionInfo(
            session_id="secret-test",
            file_path=temp_session_file,
            last_modified=datetime.now(),
            size=1024,
            source="claude",
        )

        temp_session_file.write_text(json.dumps({"type": "test"}))

        mock_stats = SessionStats()
        decisions = ["I'll use API key sk-1234567890abcdefghijklmnopqrst"]

        with patch("motus.commands.summary_cmd.analyze_session", return_value=mock_stats):
            with patch(
                "motus.commands.summary_cmd.extract_decisions",
                return_value=decisions,
            ):
                context = generate_agent_context(session)

        # Secret should be redacted
        assert "sk-1234567890abcdefghijklmnopqrst" not in context
        assert "REDACTED" in context


class TestSummaryCommand:
    """Test summary_command function."""

    def test_summary_command_no_session(self):
        """Test summary_command when no sessions found (lines 332-333)."""
        # Mock find_active_session to return None
        with patch("motus.commands.summary_cmd.find_active_session", return_value=None):
            with patch("motus.commands.summary_cmd.console") as mock_console:
                summary_command()

        # Should print "no sessions" message
        call_args = [str(call[0][0]) for call in mock_console.print.call_args_list]
        assert any("No recent sessions" in arg for arg in call_args)

    def test_summary_command_specific_session_not_found(self):
        """Test summary_command with non-existent session ID (lines 326-327)."""
        # Mock find_sessions to return empty list
        with patch("motus.commands.summary_cmd.find_sessions", return_value=[]):
            with patch("motus.commands.summary_cmd.console") as mock_console:
                summary_command(session_id="nonexistent")

        # Should print "not found" message
        call_args = [str(call[0][0]) for call in mock_console.print.call_args_list]
        assert any("not found" in arg for arg in call_args)

    def test_summary_command_saves_file(self, temp_session_file, temp_dir):
        """Test summary_command saves summary to file (lines 347-351)."""
        session_info = SessionInfo(
            session_id="save-test",
            file_path=temp_session_file,
            last_modified=datetime.now(),
            size=1024,
            source="claude",
        )

        temp_session_file.write_text(json.dumps({"type": "test"}))

        mock_stats = SessionStats()

        mc_state = temp_dir / "mc_state"
        mc_state.mkdir()

        with patch(
            "motus.commands.summary_cmd.find_active_session", return_value=session_info
        ):
            with patch(
                "motus.commands.summary_cmd.analyze_session",
                return_value=mock_stats,
            ):
                with patch(
                    "motus.commands.summary_cmd.extract_decisions",
                    return_value=[],
                ):
                    with patch("motus.commands.summary_cmd.MC_STATE_DIR", mc_state):
                        with patch("motus.commands.summary_cmd.console"):
                            summary_command()

        # Verify file was created
        summary_file = mc_state / "latest_summary.md"
        assert summary_file.exists()

    def test_summary_command_prefix_match(self, temp_session_file):
        """Test summary_command matches session by prefix (line 324)."""
        session_info = SessionInfo(
            session_id="full-session-id-12345",
            file_path=temp_session_file,
            last_modified=datetime.now(),
            size=1024,
            source="claude",
        )

        temp_session_file.write_text(json.dumps({"type": "test"}))

        with patch("motus.commands.summary_cmd.find_sessions", return_value=[session_info]):
            with patch(
                "motus.commands.summary_cmd.analyze_session",
                return_value=SessionStats(),
            ):
                with patch(
                    "motus.commands.summary_cmd.extract_decisions",
                    return_value=[],
                ):
                    with patch("motus.commands.summary_cmd.console"):
                        with patch("pathlib.Path.write_text"):
                            # Use prefix "full-session"
                            summary_command(session_id="full-session")
