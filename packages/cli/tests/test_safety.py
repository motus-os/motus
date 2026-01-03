"""Tests for the MC safety module."""

import json
import shlex
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch


class TestDryRunRm:
    """Test dry-run rm simulation."""

    def test_rm_single_file(self, tmp_path):
        """Test simulating rm on a single file."""
        from motus.safety import dry_run_rm

        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        result = dry_run_rm([str(test_file)])

        assert result.supported is True
        assert result.action == "DELETE"
        assert len(result.targets) == 1
        assert result.reversible is False

    def test_rm_nonexistent_file(self):
        """Test simulating rm on a nonexistent file."""
        from motus.safety import dry_run_rm

        result = dry_run_rm(["/nonexistent/file.txt"])

        assert result.supported is True
        assert len(result.targets) == 0

    def test_rm_rf_directory(self, tmp_path):
        """Test simulating rm -rf on a directory."""
        from motus.safety import dry_run_rm

        # Create a directory with files
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "file1.txt").write_text("content1")
        (subdir / "file2.txt").write_text("content2")

        result = dry_run_rm(["-rf", str(subdir)])

        assert result.supported is True
        assert result.action == "DELETE"
        assert len(result.targets) == 2

    def test_rm_with_flags_only(self):
        """Test rm with only flags (no files)."""
        from motus.safety import dry_run_rm

        result = dry_run_rm(["-rf"])

        assert result.supported is True
        assert len(result.targets) == 0


class TestDryRunGitReset:
    """Test dry-run git reset simulation."""

    def test_git_reset_soft(self):
        """Test simulating git reset (soft)."""
        from motus.safety import dry_run_git_reset

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="file1.py\nfile2.py\n")

            result = dry_run_git_reset(["--soft", "HEAD~1"])

            assert result.supported is True
            assert result.action == "RESET"
            assert result.reversible is True
            assert result.risk == "medium"

    def test_git_reset_hard(self):
        """Test simulating git reset --hard."""
        from motus.safety import dry_run_git_reset

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="file1.py\n")

            result = dry_run_git_reset(["--hard", "HEAD~1"])

            assert result.supported is True
            assert result.reversible is False
            assert result.risk == "high"


class TestDryRunGitClean:
    """Test dry-run git clean simulation."""

    def test_git_clean_simulation(self):
        """Test simulating git clean."""
        from motus.safety import dry_run_git_clean

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="Would remove untracked.txt\nWould remove temp/\n"
            )

            result = dry_run_git_clean(["-fd"])

            assert result.supported is True
            assert result.action == "DELETE"
            assert len(result.targets) == 2
            assert result.reversible is False


class TestDryRunMv:
    """Test dry-run mv simulation."""

    def test_mv_simple(self):
        """Test simulating simple mv."""
        from motus.safety import dry_run_mv

        result = dry_run_mv(["src.txt", "dst.txt"])

        assert result.supported is True
        assert result.action == "MOVE"
        assert "src.txt → dst.txt" in result.targets[0]
        assert result.reversible is True
        assert result.risk == "low"

    def test_mv_insufficient_args(self):
        """Test mv with insufficient arguments."""
        from motus.safety import dry_run_mv

        result = dry_run_mv(["only_one_arg"])

        assert result.supported is False


class TestTestHarnessDetection:
    """Test test harness detection."""

    def test_detect_pyproject_pytest(self, tmp_path):
        """Test detecting pytest from pyproject.toml."""
        from motus.safety import detect_test_harness

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
"""
        )

        with patch("motus.safety.Path.cwd", return_value=tmp_path):
            harness = detect_test_harness()

        # Updated to match new harness.py behavior (no trailing slash)
        expected_pytest = f"{shlex.quote(sys.executable)} -m pytest tests -v"
        assert harness["test_command"] == expected_pytest
        assert "ruff check src/" in harness["lint_command"]
        assert "pyproject.toml" in harness["detected_from"]

    def test_detect_package_json(self, tmp_path):
        """Test detecting npm scripts from package.json."""
        from motus.safety import detect_test_harness

        package_json = tmp_path / "package.json"
        package_json.write_text(
            json.dumps(
                {
                    "scripts": {
                        "test": "jest",
                        "lint": "eslint src/",
                        "build": "tsc",
                    }
                }
            )
        )

        with patch("motus.safety.Path.cwd", return_value=tmp_path):
            harness = detect_test_harness()

        assert harness["test_command"] == "npm test"
        assert harness["lint_command"] == "npm run lint"
        assert harness["build_command"] == "npm run build"

    def test_detect_makefile(self, tmp_path):
        """Test detecting make targets from Makefile."""
        from motus.safety import detect_test_harness

        makefile = tmp_path / "Makefile"
        makefile.write_text(
            """
test:
\tpytest tests/

lint:
\truff check src/
"""
        )

        with patch("motus.safety.Path.cwd", return_value=tmp_path):
            harness = detect_test_harness()

        assert harness["test_command"] is not None
        assert "Makefile" in harness["detected_from"]

    def test_detect_nothing(self, tmp_path):
        """Test when no config files exist."""
        from motus.safety import detect_test_harness

        with patch("motus.safety.Path.cwd", return_value=tmp_path):
            harness = detect_test_harness()

        assert len(harness["detected_from"]) == 0


class TestFindRelatedTests:
    """Test finding related test files."""

    def test_find_test_file(self, tmp_path):
        """Test finding test file for source file."""
        from motus.safety import find_related_tests

        # Create test file
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_cli.py").write_text("# tests")

        with patch("motus.safety.test_harness.Path.cwd", return_value=tmp_path):
            related = find_related_tests("cli.py")

            assert str(tests_dir / "test_cli.py") in related


class TestMemory:
    """Test cross-session memory functions."""

    def test_save_and_load_memory(self, tmp_path):
        """Test saving and loading memory."""
        from motus.safety import (
            MemoryEntry,
            load_memory,
            save_memory,
        )

        entries = [
            MemoryEntry(
                timestamp=datetime.now().isoformat(),
                file="test.py",
                event="test_failure",
                details="Test failed",
            )
        ]

        save_memory(entries, tmp_path)

        loaded = load_memory(tmp_path)
        assert len(loaded) == 1
        assert loaded[0].file == "test.py"
        assert loaded[0].event == "test_failure"

    def test_record_memory(self, tmp_path):
        """Test recording a memory entry."""
        from motus.safety import load_memory, record_memory

        record_memory("auth.py", "fix", "Fixed import error", project_dir=tmp_path)

        entries = load_memory(tmp_path)
        assert len(entries) == 1
        assert entries[0].file == "auth.py"
        assert entries[0].event == "fix"

    def test_get_file_memories(self, tmp_path):
        """Test getting memories for a specific file."""
        from motus.safety import get_file_memories, record_memory

        record_memory("file1.py", "event1", "details1", project_dir=tmp_path)
        record_memory("file2.py", "event2", "details2", project_dir=tmp_path)
        record_memory("file1.py", "event3", "details3", project_dir=tmp_path)

        memories = get_file_memories("file1.py", tmp_path)
        assert len(memories) == 2

    def test_memory_limit(self, tmp_path):
        """Test that memory is limited to 100 entries."""
        from motus.safety import load_memory, record_memory

        for i in range(110):
            record_memory(f"file{i}.py", "event", f"details{i}", project_dir=tmp_path)

        entries = load_memory(tmp_path)
        assert len(entries) == 100


class TestCheckpoints:
    """Test checkpoint functions."""

    def test_checkpoint_data_structure(self):
        """Test Checkpoint dataclass."""
        from motus.safety import Checkpoint

        cp = Checkpoint(
            id="mc-20251201-120000",
            message="test checkpoint",
            timestamp=datetime.now().isoformat(),
            stash_ref="stash@{0}",
            files_snapshot=["file1.py", "file2.py"],
        )

        assert cp.id == "mc-20251201-120000"
        assert len(cp.files_snapshot) == 2

    def test_save_and_load_checkpoints(self, tmp_path):
        """Test saving and loading checkpoints."""
        from motus.safety import (
            Checkpoint,
            load_checkpoints,
            save_checkpoints,
        )

        checkpoints = [
            Checkpoint(
                id="mc-test-1",
                message="test 1",
                timestamp=datetime.now().isoformat(),
            ),
            Checkpoint(
                id="mc-test-2",
                message="test 2",
                timestamp=datetime.now().isoformat(),
            ),
        ]

        save_checkpoints(checkpoints, tmp_path)

        loaded = load_checkpoints(tmp_path)
        assert len(loaded) == 2
        assert loaded[0].id == "mc-test-1"


class TestContextHints:
    """Test context hints generation."""

    def test_get_context_hints_empty(self, tmp_path):
        """Test context hints with no data."""
        from motus.safety import get_context_hints

        with patch("motus.safety.Path.cwd", return_value=tmp_path):
            hints = get_context_hints([])

        # May be empty or have basic hints
        assert isinstance(hints, str)

    def test_get_context_hints_with_test_harness(self, tmp_path):
        """Test context hints include test harness."""
        from motus.safety import get_context_hints

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.pytest.ini_options]")

        with patch("motus.safety.Path.cwd", return_value=tmp_path):
            hints = get_context_hints(["test.py"])

        assert "Test command" in hints or hints == ""


class TestDryRunCommand:
    """Test the dry_run_command function."""

    def test_unsupported_command(self, capsys):
        """Test dry-run with unsupported command."""
        from motus.safety import dry_run_command

        dry_run_command("curl https://example.com")

        captured = capsys.readouterr()
        assert "Cannot Simulate" in captured.out or "Cannot simulate" in captured.out

    def test_empty_command(self, capsys):
        """Test dry-run with empty command."""
        from motus.safety import dry_run_command

        dry_run_command("")

        captured = capsys.readouterr()
        assert "Empty command" in captured.out
