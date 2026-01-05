"""Tests for Scope Creep Monitor module."""

from unittest.mock import MagicMock, patch

from motus.intent import Intent
from motus.scope import (
    ScopeStatus,
    calculate_scope_status,
    check_scope,
    format_scope_report,
    get_touched_files_from_git,
)


class TestScopeStatus:
    """Tests for ScopeStatus dataclass."""

    def test_default_values(self):
        """Test ScopeStatus default values."""
        status = ScopeStatus()
        assert status.expected_files == []
        assert status.touched_files == []
        assert status.unexpected_files == []
        assert status.drift_percentage == 0.0
        assert status.threshold == 150.0
        assert status.alert is False

    def test_to_dict(self):
        """Test serialization to dict."""
        status = ScopeStatus(
            expected_files=["a.py"],
            touched_files=["a.py", "b.py"],
            unexpected_files=["b.py"],
            drift_percentage=200.0,
            threshold=150.0,
            alert=True,
            timestamp="2025-01-01T00:00:00",
        )
        data = status.to_dict()
        assert data["expected_files"] == ["a.py"]
        assert data["touched_files"] == ["a.py", "b.py"]
        assert data["unexpected_files"] == ["b.py"]
        assert data["drift_percentage"] == 200.0
        assert data["alert"] is True


class TestCalculateScopeStatus:
    """Tests for calculate_scope_status function."""

    def test_no_expected_no_touched(self):
        """Test with no expected files and no touched files."""
        intent = Intent(task="test", priority_files=[])
        status = calculate_scope_status(intent, set())
        assert status.drift_percentage == 0.0
        assert status.alert is False

    def test_no_expected_some_touched(self):
        """Test with no expected files but some touched."""
        intent = Intent(task="test", priority_files=[])
        status = calculate_scope_status(intent, {"a.py", "b.py"})
        assert status.drift_percentage == 100.0  # All unexpected
        assert len(status.unexpected_files) == 2

    def test_all_expected(self):
        """Test when touched files match expected exactly."""
        intent = Intent(task="test", priority_files=["a.py", "b.py"])
        status = calculate_scope_status(intent, {"a.py", "b.py"})
        assert status.drift_percentage == 100.0  # 100% = on target
        assert status.alert is False
        assert len(status.unexpected_files) == 0

    def test_some_unexpected(self):
        """Test when some touched files are unexpected."""
        intent = Intent(task="test", priority_files=["a.py"])
        status = calculate_scope_status(intent, {"a.py", "b.py", "c.py"})
        assert status.drift_percentage == 300.0  # 3 touched / 1 expected = 300%
        assert status.alert is True  # Exceeds 150% threshold
        assert len(status.unexpected_files) == 2
        assert "b.py" in status.unexpected_files
        assert "c.py" in status.unexpected_files

    def test_under_threshold(self):
        """Test when drift is under threshold."""
        intent = Intent(task="test", priority_files=["a.py", "b.py"])
        status = calculate_scope_status(intent, {"a.py", "b.py", "c.py"}, threshold=200.0)
        assert status.drift_percentage == 150.0  # 3 / 2 = 150%
        assert status.alert is False  # Under 200% threshold

    def test_custom_threshold(self):
        """Test with custom threshold."""
        intent = Intent(task="test", priority_files=["a.py"])
        status = calculate_scope_status(intent, {"a.py", "b.py"}, threshold=100.0)
        assert status.drift_percentage == 200.0
        assert status.alert is True  # Exceeds 100% threshold


class TestGetTouchedFilesFromGit:
    """Tests for get_touched_files_from_git function."""

    def test_no_changes(self, tmp_path):
        """Test when git status shows no changes."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            result = get_touched_files_from_git(tmp_path)
            assert result == set()

    def test_modified_files(self, tmp_path):
        """Test parsing modified files."""
        with patch("subprocess.run") as mock_run:
            # Git porcelain format: "XY filename" - XY is 2 chars + 1 space
            mock_run.return_value = MagicMock(
                returncode=0, stdout="M  src/main.py\nM  tests/test.py\n"
            )
            result = get_touched_files_from_git(tmp_path)
            assert "src/main.py" in result
            assert "tests/test.py" in result

    def test_excludes_mc_directory(self, tmp_path):
        """Test that .mc/ files are excluded."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="M  src/main.py\nM  .mc/checkpoints.json\n"
            )
            result = get_touched_files_from_git(tmp_path)
            assert "src/main.py" in result
            assert ".mc/checkpoints.json" not in result

    def test_handles_renamed_files(self, tmp_path):
        """Test parsing renamed files."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="R  old.py -> new.py\n")
            result = get_touched_files_from_git(tmp_path)
            assert "new.py" in result
            assert "old.py" not in result

    def test_git_failure(self, tmp_path):
        """Test handling git failure."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
            result = get_touched_files_from_git(tmp_path)
            assert result == set()


class TestGetTouchedFilesFromSession:
    """Tests for get_touched_files_from_session function."""

    def test_with_tool_use_events(self, tmp_path):
        """Test extracting touched files from TOOL_USE events with ParsedEvent."""
        from datetime import datetime

        from motus.schema.events import AgentSource, EventType, ParsedEvent

        session_file = tmp_path / "test_session.jsonl"
        session_file.write_text('{"type": "test"}\n')

        # Mock the orchestrator to return ParsedEvent objects
        with patch("motus.scope.get_orchestrator") as mock_get_orch:
            mock_orch = MagicMock()
            mock_session = MagicMock()
            mock_session.file_path = session_file

            # Create TOOL_USE events with Edit/Write tools
            events = [
                ParsedEvent(
                    event_id="1",
                    session_id="test",
                    event_type=EventType.TOOL_USE,
                    source=AgentSource.CLAUDE,
                    timestamp=datetime.now(),
                    tool_name="Edit",
                    file_path="src/main.py",
                ),
                ParsedEvent(
                    event_id="2",
                    session_id="test",
                    event_type=EventType.TOOL_USE,
                    source=AgentSource.CLAUDE,
                    timestamp=datetime.now(),
                    tool_name="Write",
                    file_path="src/utils.py",
                ),
                ParsedEvent(
                    event_id="3",
                    session_id="test",
                    event_type=EventType.TOOL_USE,
                    source=AgentSource.CLAUDE,
                    timestamp=datetime.now(),
                    tool_name="Read",  # Should be ignored
                    file_path="README.md",
                ),
            ]

            mock_orch.discover_all.return_value = [mock_session]
            mock_orch.get_events.return_value = events
            mock_get_orch.return_value = mock_orch

            from motus.scope import get_touched_files_from_session

            result = get_touched_files_from_session(session_file)

            # Should only include Edit and Write events
            assert "src/main.py" in result
            assert "src/utils.py" in result
            assert "README.md" not in result

    def test_with_codex_source(self, tmp_path):
        """Test that TOOL_USE events from Codex are properly handled."""
        from datetime import datetime

        from motus.schema.events import AgentSource, EventType, ParsedEvent

        session_file = tmp_path / "codex_session.jsonl"
        session_file.write_text('{"type": "test"}\n')

        with patch("motus.scope.get_orchestrator") as mock_get_orch:
            mock_orch = MagicMock()
            mock_session = MagicMock()
            mock_session.file_path = session_file

            # Create TOOL_USE event from Codex
            events = [
                ParsedEvent(
                    event_id="1",
                    session_id="test",
                    event_type=EventType.TOOL_USE,
                    source=AgentSource.CODEX,
                    timestamp=datetime.now(),
                    tool_name="Edit",
                    file_path="src/codex_file.py",
                ),
            ]

            mock_orch.discover_all.return_value = [mock_session]
            mock_orch.get_events.return_value = events
            mock_get_orch.return_value = mock_orch

            from motus.scope import get_touched_files_from_session

            result = get_touched_files_from_session(session_file)
            assert "src/codex_file.py" in result

    def test_with_gemini_source(self, tmp_path):
        """Test that TOOL_USE events from Gemini are properly handled."""
        from datetime import datetime

        from motus.schema.events import AgentSource, EventType, ParsedEvent

        session_file = tmp_path / "gemini_session.jsonl"
        session_file.write_text('{"type": "test"}\n')

        with patch("motus.scope.get_orchestrator") as mock_get_orch:
            mock_orch = MagicMock()
            mock_session = MagicMock()
            mock_session.file_path = session_file

            # Create TOOL_USE event from Gemini
            events = [
                ParsedEvent(
                    event_id="1",
                    session_id="test",
                    event_type=EventType.TOOL_USE,
                    source=AgentSource.GEMINI,
                    timestamp=datetime.now(),
                    tool_name="Write",
                    file_path="src/gemini_file.py",
                ),
            ]

            mock_orch.discover_all.return_value = [mock_session]
            mock_orch.get_events.return_value = events
            mock_get_orch.return_value = mock_orch

            from motus.scope import get_touched_files_from_session

            result = get_touched_files_from_session(session_file)
            assert "src/gemini_file.py" in result


class TestCheckScope:
    """Tests for check_scope function."""

    def test_no_intent_file(self, tmp_path):
        """Test when no intent file exists."""
        status = check_scope(repo_path=tmp_path, mc_dir=tmp_path / ".mc")
        assert status.expected_files == []
        assert status.drift_percentage == 0.0

    def test_with_intent_and_git(self, tmp_path):
        """Test with intent and mock git status."""
        mc_dir = tmp_path / ".mc"
        mc_dir.mkdir()
        intent_file = mc_dir / "intent.yaml"
        intent_file.write_text("task: Test\npriority_files:\n  - main.py\n")

        with patch("motus.scope.get_touched_files_from_git") as mock_git:
            mock_git.return_value = {"main.py", "extra.py"}
            status = check_scope(repo_path=tmp_path, mc_dir=mc_dir)
            assert "main.py" in status.expected_files
            assert "extra.py" in status.unexpected_files
            assert status.drift_percentage == 200.0


class TestFormatScopeReport:
    """Tests for format_scope_report function."""

    def test_no_alert(self):
        """Test formatting when no alert."""
        status = ScopeStatus(
            expected_files=["a.py"],
            touched_files=["a.py"],
            unexpected_files=[],
            drift_percentage=100.0,
            threshold=150.0,
            alert=False,
        )
        report = format_scope_report(status)
        assert "SCOPE ALERT" not in report
        assert "Files touched: 1" in report
        assert "Expected files: 1" in report

    def test_with_alert(self):
        """Test formatting with alert."""
        status = ScopeStatus(
            expected_files=["a.py"],
            touched_files=["a.py", "b.py", "c.py"],
            unexpected_files=["b.py", "c.py"],
            drift_percentage=300.0,
            threshold=150.0,
            alert=True,
        )
        report = format_scope_report(status)
        assert "SCOPE ALERT" in report
        assert "Files outside priority_files" in report
        assert "- b.py" in report
        assert "- c.py" in report

    def test_truncates_long_list(self):
        """Test that long file lists are truncated."""
        unexpected = [f"file{i}.py" for i in range(15)]
        status = ScopeStatus(
            expected_files=["a.py"],
            touched_files=["a.py"] + unexpected,
            unexpected_files=unexpected,
            drift_percentage=1600.0,
            threshold=150.0,
            alert=True,
        )
        report = format_scope_report(status)
        assert "and 5 more" in report
