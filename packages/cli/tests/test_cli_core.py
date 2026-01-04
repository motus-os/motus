"""Tests for CLI core module (argparse, session finding, utilities)."""

import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from motus.cli.core import (
    archive_session,
    delete_session,
    find_active_session,
    find_sessions,
    get_running_claude_projects,
    is_claude_process_running,
)
from motus.protocols import SessionStatus, Source, UnifiedSession


class TestIsClaudeProcessRunning:
    """Test is_claude_process_running function."""

    def test_no_processes_running(self):
        """Test when no Claude processes are running."""
        mock_orch = MagicMock()
        mock_orch.get_running_projects.return_value = set()

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            result = is_claude_process_running()

        assert result is False
        mock_orch.get_running_projects.assert_called_once()

    def test_processes_running(self):
        """Test when Claude processes are running."""
        mock_orch = MagicMock()
        mock_orch.get_running_projects.return_value = {"/project1", "/project2"}

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            result = is_claude_process_running()

        assert result is True

    def test_specific_project_active(self):
        """Test checking if specific project is active."""
        mock_orch = MagicMock()
        mock_orch.is_project_active.return_value = True

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            result = is_claude_process_running(project_path="/my/project")

        assert result is True
        mock_orch.is_project_active.assert_called_once_with("/my/project")

    def test_specific_project_inactive(self):
        """Test checking inactive project."""
        mock_orch = MagicMock()
        mock_orch.is_project_active.return_value = False

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            result = is_claude_process_running(project_path="/other/project")

        assert result is False


class TestArchiveSession:
    """Test archive_session function."""

    def test_archive_session_success(self):
        """Test successful session archiving."""
        # Create temporary file to archive
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, prefix="session-"
        ) as f:
            f.write("test data")
            temp_path = Path(f.name)

        # Create temporary archive directory
        temp_archive = tempfile.mkdtemp()

        try:
            with patch("motus.cli.core.ARCHIVE_DIR", Path(temp_archive)):
                result = archive_session(temp_path)

            assert result is True
            # Original file should be moved
            assert not temp_path.exists()
            # Archive should contain a file
            archived_files = list(Path(temp_archive).glob("*.jsonl"))
            assert len(archived_files) == 1
        finally:
            # Cleanup
            shutil.rmtree(temp_archive, ignore_errors=True)
            if temp_path.exists():
                temp_path.unlink()

    def test_archive_session_file_not_found(self):
        """Test archiving when source file doesn't exist."""
        fake_path = Path("/tmp/nonexistent-session-12345.jsonl")

        result = archive_session(fake_path)

        # Should return False when file not found
        assert result is False

    def test_archive_session_os_error(self):
        """Test archive_session handles OS errors."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            temp_path = Path(f.name)

        try:
            # Mock shutil.move to raise OSError
            with patch("motus.cli.core.shutil.move", side_effect=OSError("Move failed")):
                result = archive_session(temp_path)

            assert result is False
        finally:
            temp_path.unlink()

    def test_archive_session_unexpected_error(self):
        """Test archive_session handles unexpected errors."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            temp_path = Path(f.name)

        try:
            # Mock to raise unexpected error
            with patch(
                "motus.cli.core.shutil.move", side_effect=RuntimeError("Unexpected")
            ):
                result = archive_session(temp_path)

            assert result is False
        finally:
            temp_path.unlink()


class TestDeleteSession:
    """Test delete_session function."""

    def test_delete_session_success(self):
        """Test successful session deletion."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write("test data")
            temp_path = Path(f.name)

        result = delete_session(temp_path)

        assert result is True
        assert not temp_path.exists()

    def test_delete_session_file_not_found(self):
        """Test deleting non-existent file."""
        fake_path = Path("/tmp/nonexistent-delete-67890.jsonl")

        result = delete_session(fake_path)

        assert result is False

    def test_delete_session_os_error(self):
        """Test delete_session handles OS errors."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            temp_path = Path(f.name)

        # Mock unlink to raise OSError
        with patch.object(Path, "unlink", side_effect=OSError("Delete failed")):
            result = delete_session(temp_path)

        assert result is False

        # Cleanup
        temp_path.unlink()

    def test_delete_session_unexpected_error(self):
        """Test delete_session handles unexpected errors."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            temp_path = Path(f.name)

        # Mock to raise unexpected error
        with patch.object(Path, "unlink", side_effect=RuntimeError("Unexpected error")):
            result = delete_session(temp_path)

        assert result is False

        # Cleanup
        temp_path.unlink()


class TestGetRunningClaudeProjects:
    """Test get_running_claude_projects function."""

    def test_no_running_projects(self):
        """Test when no projects are running."""
        mock_orch = MagicMock()
        mock_orch.get_running_projects.return_value = set()

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            result = get_running_claude_projects()

        assert result == set()
        assert isinstance(result, set)

    def test_multiple_running_projects(self):
        """Test when multiple projects are running."""
        running = {"/project/app1", "/project/app2", "/project/app3"}
        mock_orch = MagicMock()
        mock_orch.get_running_projects.return_value = running

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            result = get_running_claude_projects()

        assert result == running
        assert len(result) == 3


class TestFindSessions:
    """Test find_sessions function."""

    def test_find_sessions_empty(self):
        """Test when no sessions are found."""
        mock_orch = MagicMock()
        mock_orch.discover_all.return_value = []

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            result = find_sessions(max_age_hours=2)

        assert result == []
        mock_orch.discover_all.assert_called_once_with(max_age_hours=2)

    def test_find_sessions_with_results(self):
        """Test finding multiple sessions."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, prefix="session1-"
        ) as f:
            temp_path1 = Path(f.name)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, prefix="session2-"
        ) as f:
            temp_path2 = Path(f.name)

        try:
            mock_session1 = UnifiedSession(
                session_id="session-123",
                source=Source.CLAUDE,
                file_path=temp_path1,
                project_path="/project1",
                status=SessionStatus.ACTIVE,
                status_reason="generating",
                created_at=datetime.now(),
                last_modified=datetime.now(),
            )

            mock_session2 = UnifiedSession(
                session_id="session-456",
                source=Source.CODEX,
                file_path=temp_path2,
                project_path="/project2",
                status=SessionStatus.IDLE,
                status_reason="idle",
                created_at=datetime.now(),
                last_modified=datetime.now(),
            )

            mock_orch = MagicMock()
            mock_orch.discover_all.return_value = [mock_session1, mock_session2]
            mock_orch.get_builder.return_value = None

            with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
                result = find_sessions(max_age_hours=5)

            assert len(result) == 2
            assert result[0].session_id == "session-123"
            assert result[1].session_id == "session-456"
            assert result[0].source == "claude"
            assert result[1].source == "codex"
        finally:
            temp_path1.unlink()
            temp_path2.unlink()

    def test_find_sessions_with_last_action(self):
        """Test find_sessions retrieves last_action for crashed/open sessions."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            temp_path = Path(f.name)

        try:
            mock_session = UnifiedSession(
                session_id="crashed-session",
                source=Source.CLAUDE,
                file_path=temp_path,
                project_path="/project",
                status=SessionStatus.CRASHED,
                status_reason="error",
                created_at=datetime.now(),
                last_modified=datetime.now(),
            )

            mock_builder = MagicMock()
            mock_builder.get_last_action.return_value = "Bash: rm -rf /tmp"

            mock_orch = MagicMock()
            mock_orch.discover_all.return_value = [mock_session]
            mock_orch.get_builder.return_value = mock_builder

            with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
                result = find_sessions()

            assert len(result) == 1
            assert result[0].last_action == "Bash: rm -rf /tmp"
            mock_builder.get_last_action.assert_called_once_with(temp_path)
        finally:
            temp_path.unlink()

    def test_find_sessions_skips_last_action_for_active(self):
        """Test find_sessions doesn't get last_action for active sessions."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            temp_path = Path(f.name)

        try:
            mock_session = UnifiedSession(
                session_id="active-session",
                source=Source.CLAUDE,
                file_path=temp_path,
                project_path="/project",
                status=SessionStatus.ACTIVE,
                status_reason="generating",
                created_at=datetime.now(),
                last_modified=datetime.now(),
            )

            mock_builder = MagicMock()

            mock_orch = MagicMock()
            mock_orch.discover_all.return_value = [mock_session]
            mock_orch.get_builder.return_value = mock_builder

            with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
                result = find_sessions()

            # last_action should be empty for active sessions
            assert result[0].last_action == ""
            # get_last_action should not be called for active sessions
            mock_builder.get_last_action.assert_not_called()
        finally:
            temp_path.unlink()

    def test_find_sessions_default_max_age(self):
        """Test find_sessions uses default max_age."""
        mock_orch = MagicMock()
        mock_orch.discover_all.return_value = []

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            find_sessions()

        # Default is 2 hours
        mock_orch.discover_all.assert_called_once_with(max_age_hours=2)


class TestFindActiveSession:
    """Test find_active_session function."""

    def test_find_active_session_none_found(self):
        """Test when no active session exists."""
        mock_orch = MagicMock()
        mock_orch.discover_all.return_value = []

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            result = find_active_session()

        assert result is None
        mock_orch.discover_all.assert_called_once_with(max_age_hours=1)

    def test_find_active_session_returns_most_recent(self):
        """Test find_active_session returns most recent session."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            temp_path1 = Path(f.name)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            temp_path2 = Path(f.name)

        try:
            # Most recent session
            mock_session1 = UnifiedSession(
                session_id="recent-session",
                source=Source.CLAUDE,
                file_path=temp_path1,
                project_path="/project",
                status=SessionStatus.ACTIVE,
                status_reason="active",
                created_at=datetime.now(),
                last_modified=datetime.now(),
            )

            # Older session
            mock_session2 = UnifiedSession(
                session_id="older-session",
                source=Source.CODEX,
                file_path=temp_path2,
                project_path="/project",
                status=SessionStatus.IDLE,
                status_reason="idle",
                created_at=datetime.now(),
                last_modified=datetime.now(),
            )

            mock_builder = MagicMock()
            mock_builder.get_last_action.return_value = "Edit file.py"

            mock_orch = MagicMock()
            # First session is most recent
            mock_orch.discover_all.return_value = [mock_session1, mock_session2]
            mock_orch.get_builder.return_value = mock_builder

            with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
                result = find_active_session()

            assert result is not None
            assert result.session_id == "recent-session"
            assert result.source == "claude"
        finally:
            temp_path1.unlink()
            temp_path2.unlink()

    def test_find_active_session_with_last_action(self):
        """Test find_active_session retrieves last_action."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            temp_path = Path(f.name)

        try:
            mock_session = UnifiedSession(
                session_id="test-session",
                source=Source.GEMINI,
                file_path=temp_path,
                project_path="/project",
                status=SessionStatus.OPEN,
                status_reason="open",
                created_at=datetime.now(),
                last_modified=datetime.now(),
            )

            mock_builder = MagicMock()
            mock_builder.get_last_action.return_value = "Write config.json"

            mock_orch = MagicMock()
            mock_orch.discover_all.return_value = [mock_session]
            mock_orch.get_builder.return_value = mock_builder

            with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
                result = find_active_session()

            assert result.last_action == "Write config.json"
            mock_builder.get_last_action.assert_called_once_with(temp_path)
        finally:
            temp_path.unlink()

    def test_find_active_session_no_builder(self):
        """Test find_active_session when builder not available."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            temp_path = Path(f.name)

        try:
            mock_session = UnifiedSession(
                session_id="test-session",
                source=Source.CLAUDE,
                file_path=temp_path,
                project_path="/project",
                status=SessionStatus.ACTIVE,
                status_reason="active",
                created_at=datetime.now(),
                last_modified=datetime.now(),
            )

            mock_orch = MagicMock()
            mock_orch.discover_all.return_value = [mock_session]
            mock_orch.get_builder.return_value = None  # No builder available

            with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
                result = find_active_session()

            # Should still return session, just without last_action
            assert result is not None
            assert result.session_id == "test-session"
            assert result.last_action == ""
        finally:
            temp_path.unlink()


class TestBackwardCompatibility:
    """Test backward compatibility aliases."""

    def test_find_claude_sessions_alias(self):
        """Test find_claude_sessions is an alias for find_sessions."""
        from motus.cli.core import find_claude_sessions

        assert find_claude_sessions is find_sessions


class TestMainFunction:
    """Test main() argument parsing and command dispatch."""

    def test_main_no_args_shows_help(self, capsys):
        """Test main with no args shows help and suggests web."""
        with patch("sys.argv", ["motus"]):
            from motus.cli.core import main

            main()

        out = capsys.readouterr().out
        assert "motus web" in out
        assert "usage:" in out.lower()

    def test_main_watch_command(self):
        """Test main dispatches watch command."""
        with patch("sys.argv", ["motus", "watch"]):
            with patch("motus.cli.core.watch_command") as mock_watch:
                from motus.cli.core import main

                main()

            mock_watch.assert_called_once()

    def test_main_watch_command_with_session_id(self):
        """Test main dispatches watch command with session ID."""
        with patch("sys.argv", ["motus", "watch", "test-session-123"]):
            with patch("motus.cli.core.watch_command") as mock_watch:
                from motus.cli.core import main

                main()

            mock_watch.assert_called_once()
            args = mock_watch.call_args[0][0]
            assert args.session_id == "test-session-123"

    def test_main_list_command(self):
        """Test main dispatches list command."""
        with patch("sys.argv", ["motus", "list"]):
            with patch("motus.cli.core.list_sessions") as mock_list:
                from motus.cli.core import main

                main()

            mock_list.assert_called_once()
            args = mock_list.call_args[0][0]
            assert args.fast is False

    def test_main_list_command_fast_flag(self):
        """Test main dispatches list command with fast flag."""
        with patch("sys.argv", ["motus", "list", "--fast"]):
            with patch("motus.cli.core.list_sessions") as mock_list:
                from motus.cli.core import main

                main()

            mock_list.assert_called_once()
            args = mock_list.call_args[0][0]
            assert args.fast is True

    def test_main_web_command(self):
        """Test main dispatches web command."""
        with patch("sys.argv", ["motus", "web"]):
            with patch("motus.ui.web.run_web") as mock_web:
                from motus.cli.core import main

                main()

            mock_web.assert_called_once()

    def test_main_summary_command_no_session_id(self):
        """Test main dispatches summary command without session ID."""
        with patch("sys.argv", ["motus", "summary"]):
            with patch("motus.cli.core.summary_command") as mock_summary:
                from motus.cli.core import main

                main()

            mock_summary.assert_called_once_with(None)

    def test_main_summary_command_with_session_id(self):
        """Test main dispatches summary command with session ID."""
        with patch("sys.argv", ["motus", "summary", "session-456"]):
            with patch("motus.cli.core.summary_command") as mock_summary:
                from motus.cli.core import main

                main()

            mock_summary.assert_called_once_with("session-456")

    def test_main_teleport_command(self):
        """Test main dispatches teleport command."""
        with patch("sys.argv", ["motus", "teleport", "session-789"]):
            with patch("motus.cli.core.teleport_command") as mock_teleport:
                from motus.cli.core import main

                main()

            mock_teleport.assert_called_once()
            args = mock_teleport.call_args[0][0]
            assert args.session_id == "session-789"

    def test_main_teleport_command_with_no_docs(self):
        """Test main dispatches teleport command with --no-docs flag."""
        with patch("sys.argv", ["motus", "teleport", "session-123", "--no-docs"]):
            with patch("motus.cli.core.teleport_command") as mock_teleport:
                from motus.cli.core import main

                main()

            args = mock_teleport.call_args[0][0]
            assert args.session_id == "session-123"
            assert args.no_docs is True

    def test_main_teleport_command_with_output(self):
        """Test main dispatches teleport command with output file."""
        with patch("sys.argv", ["motus", "teleport", "session-123", "-o", "bundle.json"]):
            with patch("motus.cli.core.teleport_command") as mock_teleport:
                from motus.cli.core import main

                main()

            args = mock_teleport.call_args[0][0]
            assert args.output == "bundle.json"

    def test_main_init_command(self):
        """Test main dispatches init command."""
        with patch("sys.argv", ["motus", "init", "--full", "--path", "/tmp"]):
            with patch("motus.commands.init_cmd.init_command") as mock_init:
                from motus.cli.core import main

                main()

            mock_init.assert_called_once()

    def test_main_checkpoint_command(self, capsys):
        """Test main dispatches checkpoint command."""
        from pathlib import Path

        with patch("sys.argv", ["motus", "checkpoint", "before-refactor"]):
            with patch("motus.checkpoint.create_checkpoint") as mock_create:
                mock_create.return_value = MagicMock(
                    id="mc-20250101-120000-000",
                    label="before-refactor",
                    timestamp="2025-01-01T12:00:00",
                )

                from motus.cli.core import main

                main()

            mock_create.assert_called_once_with("before-refactor", Path.cwd())

        out = capsys.readouterr().out
        assert "Checkpoint created: mc-20250101-120000-000" in out

    def test_main_checkpoints_command(self, capsys):
        """Test main dispatches checkpoints command."""
        from pathlib import Path

        with patch("sys.argv", ["motus", "checkpoints"]):
            with patch("motus.checkpoint.list_checkpoints") as mock_list:
                mock_list.return_value = [
                    MagicMock(
                        id="mc-20250101-120000-000",
                        label="before-refactor",
                        timestamp="2025-01-01T12:00:00",
                    )
                ]

                from motus.cli.core import main

                main()

            mock_list.assert_called_once_with(Path.cwd())

        out = capsys.readouterr().out
        assert "mc-20250101-120000-000" in out
        assert "before-refactor" in out

    def test_main_rollback_command(self, capsys):
        """Test main dispatches rollback command."""
        from pathlib import Path

        with patch("sys.argv", ["motus", "rollback", "mc-20250101-120000-000"]):
            with patch("motus.checkpoint.rollback_checkpoint") as mock_rollback:
                mock_rollback.return_value = MagicMock(
                    id="mc-20250101-120000-000",
                    label="before-refactor",
                    timestamp="2025-01-01T12:00:00",
                )

                from motus.cli.core import main

                main()

            mock_rollback.assert_called_once_with("mc-20250101-120000-000", Path.cwd())

        out = capsys.readouterr().out
        assert "Rolled back to checkpoint: mc-20250101-120000-000" in out

    def test_main_diff_command(self, capsys):
        """Test main dispatches diff command."""
        from pathlib import Path

        with patch("sys.argv", ["motus", "diff", "mc-20250101-120000-000"]):
            with patch("motus.checkpoint.diff_checkpoint") as mock_diff:
                mock_diff.return_value = "diff --git a/foo b/foo\n"

                from motus.cli.core import main

                main()

            mock_diff.assert_called_once_with("mc-20250101-120000-000", Path.cwd())

        out = capsys.readouterr().out
        assert "diff --git a/foo b/foo" in out


class TestLazyImports:
    """Test lazy import functions."""

    def test_get_orchestrator_lazy_import(self):
        """Test _get_orchestrator lazy imports orchestrator."""
        from motus.cli.core import _get_orchestrator

        orch = _get_orchestrator()
        assert orch is not None

    def test_get_protocol_types_lazy_import(self):
        """Test _get_protocol_types lazy imports protocol types."""
        from motus.cli.core import _get_protocol_types

        proto = _get_protocol_types()
        assert proto is not None
        assert hasattr(proto, "EventType")


class TestFindSdkTraces:
    """Test find_sdk_traces function."""

    def test_find_sdk_traces_no_directory(self):
        """Test find_sdk_traces when traces directory doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mc_dir = Path(tmpdir) / ".mc"
            mc_dir.mkdir()

            with patch("motus.cli.core.MC_STATE_DIR", mc_dir):
                from motus.cli.core import find_sdk_traces

                result = find_sdk_traces()

            assert result == []

    def test_find_sdk_traces_empty_directory(self):
        """Test find_sdk_traces with empty traces directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mc_dir = Path(tmpdir) / ".mc"
            mc_dir.mkdir()
            traces_dir = mc_dir / "traces"
            traces_dir.mkdir()

            with patch("motus.cli.core.MC_STATE_DIR", mc_dir):
                from motus.cli.core import find_sdk_traces

                result = find_sdk_traces()

            assert result == []

    def test_find_sdk_traces_with_trace_files(self):
        """Test find_sdk_traces finds and parses trace files."""
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            mc_dir = Path(tmpdir) / ".mc"
            mc_dir.mkdir()
            traces_dir = mc_dir / "traces"
            traces_dir.mkdir()

            # Create a trace file
            trace_file = traces_dir / "test-trace.jsonl"
            trace_data = {"tracer_name": "TestTracer", "session_id": "test-123"}
            with open(trace_file, "w") as f:
                f.write(json.dumps(trace_data) + "\n")

            with patch("motus.cli.core.MC_STATE_DIR", mc_dir):
                from motus.cli.core import find_sdk_traces

                result = find_sdk_traces()

            assert len(result) == 1
            assert result[0]["name"] == "TestTracer"
            assert result[0]["file"] == trace_file

    def test_find_sdk_traces_invalid_json(self):
        """Test find_sdk_traces handles invalid JSON gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mc_dir = Path(tmpdir) / ".mc"
            mc_dir.mkdir()
            traces_dir = mc_dir / "traces"
            traces_dir.mkdir()

            # Create trace file with invalid JSON
            trace_file = traces_dir / "invalid-trace.jsonl"
            with open(trace_file, "w") as f:
                f.write("{ invalid json }\n")

            with patch("motus.cli.core.MC_STATE_DIR", mc_dir):
                from motus.cli.core import find_sdk_traces

                result = find_sdk_traces()

            # Should still include the file, using filename as name
            assert len(result) == 1
            assert result[0]["name"] == "invalid-trace"

    def test_find_sdk_traces_sorts_by_modified(self):
        """Test find_sdk_traces sorts traces by modification time."""
        import json
        import time

        with tempfile.TemporaryDirectory() as tmpdir:
            mc_dir = Path(tmpdir) / ".mc"
            mc_dir.mkdir()
            traces_dir = mc_dir / "traces"
            traces_dir.mkdir()

            # Create multiple trace files with different timestamps
            trace1 = traces_dir / "trace1.jsonl"
            trace2 = traces_dir / "trace2.jsonl"

            with open(trace1, "w") as f:
                f.write(json.dumps({"tracer_name": "Trace1"}) + "\n")

            time.sleep(0.1)

            with open(trace2, "w") as f:
                f.write(json.dumps({"tracer_name": "Trace2"}) + "\n")

            with patch("motus.cli.core.MC_STATE_DIR", mc_dir):
                from motus.cli.core import find_sdk_traces

                result = find_sdk_traces()

            # Should be sorted newest first
            assert len(result) == 2
            assert result[0]["name"] == "Trace2"  # Most recent
            assert result[1]["name"] == "Trace1"

    def test_find_sdk_traces_limits_to_five(self):
        """Test find_sdk_traces returns max 5 traces."""
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            mc_dir = Path(tmpdir) / ".mc"
            mc_dir.mkdir()
            traces_dir = mc_dir / "traces"
            traces_dir.mkdir()

            # Create 10 trace files
            for i in range(10):
                trace_file = traces_dir / f"trace{i}.jsonl"
                with open(trace_file, "w") as f:
                    f.write(json.dumps({"tracer_name": f"Trace{i}"}) + "\n")

            with patch("motus.cli.core.MC_STATE_DIR", mc_dir):
                from motus.cli.core import find_sdk_traces

                result = find_sdk_traces()

            # Should limit to 5 most recent
            assert len(result) == 5

    def test_find_sdk_traces_is_active_flag(self):
        """Test find_sdk_traces sets is_active flag correctly."""
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            mc_dir = Path(tmpdir) / ".mc"
            mc_dir.mkdir()
            traces_dir = mc_dir / "traces"
            traces_dir.mkdir()

            # Create a recent trace file
            trace_file = traces_dir / "active-trace.jsonl"
            with open(trace_file, "w") as f:
                f.write(json.dumps({"tracer_name": "ActiveTrace"}) + "\n")

            with patch("motus.cli.core.MC_STATE_DIR", mc_dir):
                from motus.cli.core import find_sdk_traces

                result = find_sdk_traces()

            # File was just created, should be active (< 60 seconds)
            assert len(result) == 1
            assert result[0]["is_active"] is True
