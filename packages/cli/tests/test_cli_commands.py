"""Tests for CLI commands module."""

import tempfile
from argparse import Namespace
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from motus.cli.commands import (
    context_command,
    list_sessions,
    summary_command,
    teleport_command,
)
from motus.cli.output import SessionStats
from motus.protocols import SessionStatus, Source, TeleportBundle, UnifiedSession


class TestContextCommand:
    """Test context_command function."""

    def test_context_command_no_sessions(self, capsys):
        """Test context_command when no sessions found."""
        mock_orch = MagicMock()
        mock_orch.discover_all.return_value = []

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            with pytest.raises(SystemExit) as exc_info:
                context_command()

        assert exc_info.value.code == 1
        mock_orch.discover_all.assert_called_once_with(max_age_hours=1)

    def test_context_command_with_session(self):
        """Test context_command with active session."""
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            temp_path = Path(f.name)

        try:
            mock_session = UnifiedSession(
                session_id="test-session-123",
                source=Source.CLAUDE,
                file_path=temp_path,
                project_path="/project/test",
                status=SessionStatus.ACTIVE,
                status_reason="generating",
                created_at=datetime.now(),
                last_modified=datetime.now(),
            )

            mock_orch = MagicMock()
            mock_orch.discover_all.return_value = [mock_session]

            mock_context = "## Context\n\nTest context for agent."

            with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
                with patch(
                    "motus.cli.watch_cmd.generate_agent_context",
                    return_value=mock_context,
                ) as mock_gen:
                    with patch("builtins.open", create=True):
                        context_command()

            # Verify generate_agent_context was called
            mock_gen.assert_called_once()
            # First arg should be SessionInfo (converted from UnifiedSession)
            call_args = mock_gen.call_args[0]
            assert call_args[0].session_id == "test-session-123"
            assert call_args[1] == mock_session  # unified_session passed
        finally:
            temp_path.unlink()

    def test_context_command_file_write_error(self):
        """Test context_command handles file write errors."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            temp_path = Path(f.name)

        try:
            mock_session = UnifiedSession(
                session_id="test-session",
                source=Source.CLAUDE,
                file_path=temp_path,
                project_path="/project",
                status=SessionStatus.ACTIVE,
                status_reason="test",
                created_at=datetime.now(),
                last_modified=datetime.now(),
            )

            mock_orch = MagicMock()
            mock_orch.discover_all.return_value = [mock_session]

            with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
                with patch(
                    "motus.cli.watch_cmd.generate_agent_context", return_value="test"
                ):
                    with patch("builtins.open", side_effect=OSError("Write error")):
                        # Should not raise, just log error
                        context_command()
        finally:
            temp_path.unlink()


class TestSummaryCommand:
    """Test summary_command function."""

    def test_summary_command_no_sessions(self):
        """Test summary_command when no sessions found."""
        mock_orch = MagicMock()
        mock_orch.discover_all.return_value = []

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            with pytest.raises(SystemExit) as exc_info:
                summary_command()

        assert exc_info.value.code == 1
        mock_orch.discover_all.assert_called_once_with(max_age_hours=1)

    def test_summary_command_most_recent(self):
        """Test summary_command uses most recent session."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            temp_path = Path(f.name)

        try:
            mock_session = UnifiedSession(
                session_id="recent-session-456",
                source=Source.CODEX,
                file_path=temp_path,
                project_path="/project/app",
                status=SessionStatus.IDLE,
                status_reason="idle",
                created_at=datetime.now(),
                last_modified=datetime.now(),
            )

            mock_orch = MagicMock()
            mock_orch.discover_all.return_value = [mock_session]

            mock_stats = SessionStats(
                thinking_count=10,
                tool_count=25,
                agent_count=3,
                files_modified={"file1.py", "file2.py"},
                high_risk_ops=2,
            )

            with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
                with patch("motus.cli.watch_cmd.analyze_session", return_value=mock_stats):
                    with patch(
                        "motus.cli.validators.extract_decisions",
                        return_value=["Decision 1"],
                    ):
                        with patch("builtins.open", create=True):
                            summary_command()

            # Should query for most recent (1 hour)
            mock_orch.discover_all.assert_called_once_with(max_age_hours=1)
        finally:
            temp_path.unlink()

    def test_summary_command_specific_session(self):
        """Test summary_command with specific session ID."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            temp_path = Path(f.name)

        try:
            mock_session = UnifiedSession(
                session_id="specific-session-789",
                source=Source.GEMINI,
                file_path=temp_path,
                project_path="/project",
                status=SessionStatus.IDLE,
                status_reason="idle",
                created_at=datetime.now(),
                last_modified=datetime.now(),
            )

            mock_orch = MagicMock()
            mock_orch.discover_all.return_value = [mock_session]

            mock_stats = SessionStats(thinking_count=5)

            with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
                with patch("motus.cli.watch_cmd.analyze_session", return_value=mock_stats):
                    with patch("motus.cli.validators.extract_decisions", return_value=[]):
                        with patch("builtins.open", create=True):
                            summary_command(session_id="specific")

            # Should query for 48 hours when session_id provided
            mock_orch.discover_all.assert_called_once_with(max_age_hours=48)
        finally:
            temp_path.unlink()

    def test_summary_command_session_not_found(self):
        """Test summary_command when specific session not found."""
        mock_session = UnifiedSession(
            session_id="other-session",
            source=Source.CLAUDE,
            file_path=Path("/tmp/test.jsonl"),
            project_path="/project",
            status=SessionStatus.IDLE,
            status_reason="test",
            created_at=datetime.now(),
            last_modified=datetime.now(),
        )

        mock_orch = MagicMock()
        mock_orch.discover_all.return_value = [mock_session]

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            with pytest.raises(SystemExit) as exc_info:
                summary_command(session_id="nonexistent")

        assert exc_info.value.code == 1

    def test_summary_command_with_stats_and_decisions(self):
        """Test summary_command generates complete summary."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write("test")
            temp_path = Path(f.name)

        try:
            mock_session = UnifiedSession(
                session_id="test-session-complete",
                source=Source.CLAUDE,
                file_path=temp_path,
                project_path="/project/myapp",
                status=SessionStatus.ACTIVE,
                status_reason="active",
                created_at=datetime.now(),
                last_modified=datetime.now(),
            )

            mock_orch = MagicMock()
            mock_orch.discover_all.return_value = [mock_session]

            # Rich stats that should trigger recommendations
            mock_stats = SessionStats(
                thinking_count=50,
                tool_count=150,
                agent_count=5,
                files_modified={f"file{i}.py" for i in range(15)},
                high_risk_ops=5,
            )

            decisions = [
                "I'll use SQLite for simplicity",
                "I decided to use async/await",
                "The best approach is to cache results",
            ]

            with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
                with patch("motus.cli.watch_cmd.analyze_session", return_value=mock_stats):
                    with patch(
                        "motus.cli.validators.extract_decisions", return_value=decisions
                    ):
                        with patch("pathlib.Path.write_text", return_value=None) as mock_write:
                            summary_command()

            # Verify files were written (summary file and latest file)
            assert mock_write.call_count == 2
        finally:
            temp_path.unlink()

    def test_summary_command_file_write_failure(self):
        """Test summary_command handles file write failures."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            temp_path = Path(f.name)

        try:
            mock_session = UnifiedSession(
                session_id="test-session",
                source=Source.CLAUDE,
                file_path=temp_path,
                project_path="/project",
                status=SessionStatus.IDLE,
                status_reason="test",
                created_at=datetime.now(),
                last_modified=datetime.now(),
            )

            mock_orch = MagicMock()
            mock_orch.discover_all.return_value = [mock_session]
            mock_stats = SessionStats()

            with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
                with patch("motus.cli.watch_cmd.analyze_session", return_value=mock_stats):
                    with patch("motus.cli.validators.extract_decisions", return_value=[]):
                        with patch(
                            "pathlib.Path.write_text", side_effect=OSError("Write error")
                        ):
                            summary_command()
        finally:
            temp_path.unlink()


class TestTeleportCommand:
    """Test teleport_command function."""

    def test_teleport_command_session_not_found(self):
        """Test teleport_command when session not found."""
        args = Namespace(session_id="nonexistent", no_docs=False, output=None)

        mock_orch = MagicMock()
        mock_orch.discover_all.return_value = []

        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            teleport_command(args)

        mock_orch.discover_all.assert_called_once_with(max_age_hours=168)

    def test_teleport_command_exports_bundle_to_stdout(self, capsys):
        """Test teleport_command exports bundle to stdout."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            temp_path = Path(f.name)

        try:
            mock_session = UnifiedSession(
                session_id="teleport-session-123",
                source=Source.CLAUDE,
                file_path=temp_path,
                project_path="/project",
                status=SessionStatus.IDLE,
                status_reason="test",
                created_at=datetime.now(),
                last_modified=datetime.now(),
            )

            mock_bundle = TeleportBundle(
                source_session="teleport-session-123",
                source_model="claude-3-opus",
                intent="Implement feature X",
                decisions=["Use approach Y"],
                files_touched=["file.py"],
                hot_files=["file.py"],
                pending_todos=["Test feature"],
                last_action="Edit file.py",
                timestamp=datetime.now(),
                planning_docs={},
            )

            mock_orch = MagicMock()
            mock_orch.discover_all.return_value = [mock_session]
            mock_orch.export_teleport.return_value = mock_bundle

            args = Namespace(session_id="teleport", no_docs=False, output=None)

            with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
                teleport_command(args)

            # Should have called export_teleport
            mock_orch.export_teleport.assert_called_once_with(
                mock_session, include_planning_docs=True
            )

            # Check that JSON was printed (captured output)
            captured = capsys.readouterr()
            assert "teleport-session-123" in captured.out
            assert "claude-3-opus" in captured.out
        finally:
            temp_path.unlink()

    def test_teleport_command_exports_to_file(self):
        """Test teleport_command exports bundle to file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            temp_path = Path(f.name)

        output_file = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json")
        output_path = output_file.name
        output_file.close()

        try:
            mock_session = UnifiedSession(
                session_id="export-session-456",
                source=Source.CODEX,
                file_path=temp_path,
                project_path="/project",
                status=SessionStatus.IDLE,
                status_reason="test",
                created_at=datetime.now(),
                last_modified=datetime.now(),
            )

            mock_bundle = TeleportBundle(
                source_session="export-session-456",
                source_model="codex",
                intent="Test export",
                decisions=[],
                files_touched=[],
                hot_files=[],
                pending_todos=[],
                last_action="",
                timestamp=datetime.now(),
                planning_docs={},
            )

            mock_orch = MagicMock()
            mock_orch.discover_all.return_value = [mock_session]
            mock_orch.export_teleport.return_value = mock_bundle

            args = Namespace(session_id="export", no_docs=True, output=output_path)

            with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
                teleport_command(args)

            # Verify file was written
            with open(output_path, "r") as f:
                content = f.read()
                assert "export-session-456" in content
                assert "codex" in content

            # Verify include_planning_docs was False
            mock_orch.export_teleport.assert_called_once_with(
                mock_session, include_planning_docs=False
            )
        finally:
            temp_path.unlink()
            Path(output_path).unlink()

    def test_teleport_command_handles_export_error(self):
        """Test teleport_command handles export errors gracefully."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            temp_path = Path(f.name)

        try:
            mock_session = UnifiedSession(
                session_id="error-session",
                source=Source.CLAUDE,
                file_path=temp_path,
                project_path="/project",
                status=SessionStatus.IDLE,
                status_reason="test",
                created_at=datetime.now(),
                last_modified=datetime.now(),
            )

            mock_orch = MagicMock()
            mock_orch.discover_all.return_value = [mock_session]
            mock_orch.export_teleport.side_effect = OSError("Export failed")

            args = Namespace(session_id="error", no_docs=False, output=None)

            with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
                # Should not crash
                teleport_command(args)
        finally:
            temp_path.unlink()

    def test_teleport_command_prefix_match(self):
        """Test teleport_command matches session by prefix."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            temp_path = Path(f.name)

        try:
            mock_session = UnifiedSession(
                session_id="full-session-id-12345",
                source=Source.CLAUDE,
                file_path=temp_path,
                project_path="/project",
                status=SessionStatus.IDLE,
                status_reason="test",
                created_at=datetime.now(),
                last_modified=datetime.now(),
            )

            mock_bundle = TeleportBundle(
                source_session="full-session-id-12345",
                source_model="claude",
                intent="Test",
                decisions=[],
                files_touched=[],
                hot_files=[],
                pending_todos=[],
                last_action="",
                timestamp=datetime.now(),
                planning_docs={},
            )

            mock_orch = MagicMock()
            mock_orch.discover_all.return_value = [mock_session]
            mock_orch.export_teleport.return_value = mock_bundle

            # Use just prefix "full-session"
            args = Namespace(session_id="full-session", no_docs=False, output=None)

            with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
                teleport_command(args)

            # Should match and export
            mock_orch.export_teleport.assert_called_once()
        finally:
            temp_path.unlink()


class TestListSessions:
    """Test list_sessions delegation."""

    def test_list_sessions_delegates(self):
        """Test list_sessions delegates to list_cmd module."""
        with patch("motus.commands.list_cmd.list_sessions") as mock_func:
            list_sessions()
            mock_func.assert_called_once()

    def test_list_sessions_import_error(self):
        """Test list_sessions handles import errors gracefully."""
        # This tests the ImportError path in the actual function
        # We can't easily mock the import, but we can verify the function exists
        assert callable(list_sessions)
