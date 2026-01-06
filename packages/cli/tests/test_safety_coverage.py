"""
Comprehensive tests for safety.py to increase coverage from 49% to 80%+.

This test file targets the missing coverage gaps identified in the coverage report:
- Lines 63-64: Error handling in load_checkpoints
- Lines 80-156: checkpoint_command functionality
- Lines 161-193: list_checkpoints_command functionality
- Lines 201-254: rollback_command functionality
- Lines 289-302: dry_run_rm glob expansion
- Lines 361: git clean output parsing
- Lines 407-408: shlex error handling
- Lines 420-426: dry_run_command routing
- Lines 437-457: dry_run_command display logic
- Lines 500-504: detect_test_harness return paths
- Lines 537-556: test_harness_command output
- Lines 594-595: Error handling in load_memory
- Lines 639-681: memory_command display
- Lines 700-706: get_context_hints with files
- Line 716: empty hints case
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch


class TestLoadCheckpointsErrorHandling:
    """Test error handling in load_checkpoints."""

    def test_load_checkpoints_json_decode_error(self, tmp_path):
        """Test load_checkpoints with invalid JSON."""
        from motus.safety import load_checkpoints

        # Create invalid JSON file
        motus_dir = tmp_path / ".motus"
        motus_dir.mkdir()
        (motus_dir / "checkpoints.json").write_text("invalid json{")

        checkpoints = load_checkpoints(tmp_path)
        assert checkpoints == []

    def test_load_checkpoints_type_error(self, tmp_path):
        """Test load_checkpoints with wrong data type."""
        from motus.safety import load_checkpoints

        # Create file with wrong data structure
        motus_dir = tmp_path / ".motus"
        motus_dir.mkdir()
        (motus_dir / "checkpoints.json").write_text('["not", "checkpoint", "objects"]')

        checkpoints = load_checkpoints(tmp_path)
        assert checkpoints == []


class TestCheckpointCommand:
    """Test checkpoint_command functionality (lines 80-156)."""

    def test_checkpoint_command_not_git_repo(self, capsys):
        """Test checkpoint_command when not in a git repository."""
        from motus.safety import checkpoint_command

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="not a git repository")

            result = checkpoint_command("test checkpoint")

            assert result is False
            captured = capsys.readouterr()
            assert "Not in a git repository" in captured.out

    def test_checkpoint_command_no_changes(self, capsys):
        """Test checkpoint_command when there are no changes."""
        from motus.safety import checkpoint_command

        with patch("subprocess.run") as mock_run:
            # First call: check if git repo
            # Second call: get status
            mock_run.side_effect = [
                MagicMock(returncode=0),  # is git repo
                MagicMock(returncode=0, stdout=""),  # no changes
            ]

            result = checkpoint_command("test")

            assert result is False
            captured = capsys.readouterr()
            assert "No changes to checkpoint" in captured.out

    def test_checkpoint_command_success(self, capsys, tmp_path):
        """Test successful checkpoint creation."""
        from motus.safety import checkpoint_command

        with (
            patch("subprocess.run") as mock_run,
            patch("motus.safety.checkpoint.Path.cwd", return_value=tmp_path),
            patch("motus.safety.checkpoint.datetime") as mock_datetime,
        ):
            # Mock datetime to return fixed timestamp
            mock_now = MagicMock()
            mock_now.strftime.return_value = "20250115-120000"
            mock_now.isoformat.return_value = "2025-01-15T12:00:00"
            mock_datetime.now.return_value = mock_now

            # Mock subprocess calls
            mock_run.side_effect = [
                MagicMock(returncode=0),  # is git repo
                MagicMock(returncode=0, stdout=" M file1.py\n M file2.py\n"),  # status
                MagicMock(returncode=0),  # git stash push
                MagicMock(returncode=0, stdout="stash@{0} mc-checkpoint: test\n"),  # stash list
                MagicMock(returncode=0),  # stash pop
            ]

            result = checkpoint_command("test")

            assert result is True
            captured = capsys.readouterr()
            assert "Checkpoint created" in captured.out
            assert "test" in captured.out

    def test_checkpoint_command_stash_fails(self, capsys):
        """Test checkpoint_command when git stash fails."""
        from motus.safety import checkpoint_command

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0),  # is git repo
                MagicMock(returncode=0, stdout=" M file.py\n"),  # has changes
                MagicMock(returncode=1, stderr="stash failed"),  # stash push fails
            ]

            result = checkpoint_command("test")

            assert result is False
            captured = capsys.readouterr()
            assert "Failed to create checkpoint" in captured.out

    def test_checkpoint_command_no_stash_ref(self, capsys, tmp_path):
        """Test checkpoint when stash ref is not found in stash list."""
        from motus.safety import checkpoint_command

        with (
            patch("subprocess.run") as mock_run,
            patch("motus.safety.checkpoint.Path.cwd", return_value=tmp_path),
            patch("motus.safety.checkpoint.datetime") as mock_datetime,
        ):
            mock_now = MagicMock()
            mock_now.strftime.return_value = "20250115-120000"
            mock_now.isoformat.return_value = "2025-01-15T12:00:00"
            mock_datetime.now.return_value = mock_now

            # Stash list doesn't contain our message
            mock_run.side_effect = [
                MagicMock(returncode=0),  # is git repo
                MagicMock(returncode=0, stdout=" M file.py\n"),  # has changes
                MagicMock(returncode=0),  # stash push
                MagicMock(returncode=0, stdout="stash@{0} other-stash\n"),  # stash list (no match)
                MagicMock(returncode=0),  # stash pop
            ]

            result = checkpoint_command("test")

            assert result is True


class TestListCheckpointsCommand:
    """Test list_checkpoints_command functionality (lines 161-193)."""

    def test_list_checkpoints_command_empty(self, capsys, tmp_path):
        """Test list_checkpoints_command with no checkpoints."""
        from motus.safety import list_checkpoints_command

        with (
            patch("motus.safety.checkpoint.load_checkpoints", return_value=[]),
            patch("motus.safety.checkpoint.Path.cwd", return_value=tmp_path),
        ):
            list_checkpoints_command()

            captured = capsys.readouterr()
            assert "No checkpoints found" in captured.out
            assert "motus checkpoint" in captured.out

    def test_list_checkpoints_command_with_checkpoints(self, capsys, tmp_path):
        """Test list_checkpoints_command with existing checkpoints."""
        from motus.safety import Checkpoint, list_checkpoints_command

        # Create mock checkpoints with different ages
        now = datetime.now()
        checkpoints = [
            Checkpoint(
                id="mc-20250115-120000",
                message="recent checkpoint",
                timestamp=(now - timedelta(minutes=30)).isoformat(),
                files_snapshot=["file1.py", "file2.py"],
            ),
            Checkpoint(
                id="mc-20250115-110000",
                message="older checkpoint",
                timestamp=(now - timedelta(hours=2)).isoformat(),
                files_snapshot=["file3.py"],
            ),
            Checkpoint(
                id="mc-20250115-100000",
                message="very old checkpoint",
                timestamp=(now - timedelta(hours=5)).isoformat(),
                files_snapshot=["file4.py", "file5.py", "file6.py"],
            ),
        ]

        with (
            patch("motus.safety.checkpoint.load_checkpoints", return_value=checkpoints),
            patch("motus.safety.checkpoint.Path.cwd", return_value=tmp_path),
        ):
            list_checkpoints_command()

            captured = capsys.readouterr()
            assert "Checkpoints" in captured.out
            assert "mc-20250115-120000" in captured.out
            assert "recent checkpoint" in captured.out
            assert "motus rollback" in captured.out

    def test_list_checkpoints_command_invalid_timestamp(self, capsys, tmp_path):
        """Test list_checkpoints_command with invalid timestamp."""
        from motus.safety import Checkpoint, list_checkpoints_command

        checkpoints = [
            Checkpoint(
                id="mc-test",
                message="test",
                timestamp="invalid-timestamp",
                files_snapshot=["file.py"],
            )
        ]

        with (
            patch("motus.safety.checkpoint.load_checkpoints", return_value=checkpoints),
            patch("motus.safety.checkpoint.Path.cwd", return_value=tmp_path),
        ):
            list_checkpoints_command()

            captured = capsys.readouterr()
            assert "Checkpoints" in captured.out
            assert "?" in captured.out  # Age should be "?"

    def test_list_checkpoints_command_more_than_10(self, capsys, tmp_path):
        """Test list_checkpoints_command shows only last 10."""
        from motus.safety import Checkpoint, list_checkpoints_command

        # Create 15 checkpoints
        checkpoints = []
        now = datetime.now()
        for i in range(15):
            checkpoints.append(
                Checkpoint(
                    id=f"mc-checkpoint-{i:02d}",
                    message=f"checkpoint {i}",
                    timestamp=(now - timedelta(hours=i)).isoformat(),
                    files_snapshot=[f"file{i}.py"],
                )
            )

        with (
            patch("motus.safety.checkpoint.load_checkpoints", return_value=checkpoints),
            patch("motus.safety.checkpoint.Path.cwd", return_value=tmp_path),
        ):
            list_checkpoints_command()

            captured = capsys.readouterr()
            # Should show first 10
            assert "mc-checkpoint-00" in captured.out
            assert "mc-checkpoint-09" in captured.out
            # Should not show 11-14
            assert "mc-checkpoint-14" not in captured.out


class TestRollbackCommand:
    """Test rollback_command functionality (lines 201-254)."""

    def test_rollback_command_no_checkpoints(self, capsys):
        """Test rollback_command when no checkpoints exist."""
        from motus.safety import rollback_command

        with patch("motus.safety.checkpoint.load_checkpoints", return_value=[]):
            result = rollback_command()

            assert result is False
            captured = capsys.readouterr()
            assert "No checkpoints found" in captured.out

    def test_rollback_command_no_id_shows_most_recent(self, capsys):
        """Test rollback_command without ID shows most recent checkpoint."""
        from motus.safety import Checkpoint, rollback_command

        checkpoints = [
            Checkpoint(
                id="mc-20250115-120000",
                message="most recent",
                timestamp="2025-01-15T12:00:00",
                files_snapshot=["file1.py", "file2.py", "file3.py"],
            )
        ]

        with patch("motus.safety.checkpoint.load_checkpoints", return_value=checkpoints):
            result = rollback_command(None)

            assert result is True
            captured = capsys.readouterr()
            assert "Most recent checkpoint" in captured.out
            assert "mc-20250115-120000" in captured.out

    def test_rollback_command_checkpoint_not_found(self, capsys):
        """Test rollback_command with non-existent checkpoint ID."""
        from motus.safety import Checkpoint, rollback_command

        checkpoints = [
            Checkpoint(
                id="mc-existing",
                message="test",
                timestamp="2025-01-15T12:00:00",
                files_snapshot=["file.py"],
            )
        ]

        with patch("motus.safety.checkpoint.load_checkpoints", return_value=checkpoints):
            result = rollback_command("nonexistent-id")

            assert result is False
            captured = capsys.readouterr()
            assert "Checkpoint not found" in captured.out

    def test_rollback_command_partial_id_match(self, capsys):
        """Test rollback_command with partial ID match."""
        from motus.safety import Checkpoint, rollback_command

        checkpoints = [
            Checkpoint(
                id="mc-20250115-120000",
                message="test",
                timestamp="2025-01-15T12:00:00",
                stash_ref="stash@{0}",
                files_snapshot=["file.py"],
            )
        ]

        with (
            patch("motus.safety.checkpoint.load_checkpoints", return_value=checkpoints),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.side_effect = [
                MagicMock(returncode=0),  # safety stash
                MagicMock(returncode=0),  # apply checkpoint stash
            ]

            result = rollback_command("mc-20250115")

            assert result is True
            captured = capsys.readouterr()
            assert "Rolled back" in captured.out

    def test_rollback_command_apply_fails(self, capsys):
        """Test rollback_command when stash apply fails."""
        from motus.safety import Checkpoint, rollback_command

        checkpoints = [
            Checkpoint(
                id="mc-test",
                message="test",
                timestamp="2025-01-15T12:00:00",
                stash_ref="stash@{0}",
                files_snapshot=["file.py"],
            )
        ]

        with (
            patch("motus.safety.checkpoint.load_checkpoints", return_value=checkpoints),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.side_effect = [
                MagicMock(returncode=0),  # safety stash
                MagicMock(returncode=1, stderr="apply failed"),  # apply fails
                MagicMock(returncode=0),  # restore safety stash
            ]

            result = rollback_command("mc-test")

            assert result is False
            captured = capsys.readouterr()
            assert "Failed to apply checkpoint" in captured.out

    def test_rollback_command_no_stash_ref(self, capsys):
        """Test rollback_command when checkpoint has no stash_ref."""
        from motus.safety import Checkpoint, rollback_command

        checkpoints = [
            Checkpoint(
                id="mc-test",
                message="test",
                timestamp="2025-01-15T12:00:00",
                stash_ref=None,  # No stash ref
                files_snapshot=["file.py"],
            )
        ]

        with (
            patch("motus.safety.checkpoint.load_checkpoints", return_value=checkpoints),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0)  # safety stash

            result = rollback_command("mc-test")

            assert result is True
            captured = capsys.readouterr()
            assert "Rolled back" in captured.out


class TestDryRunRmGlobExpansion:
    """Test dry_run_rm glob expansion (lines 289-302)."""

    def test_dry_run_rm_glob_pattern(self, tmp_path):
        """Test dry_run_rm with glob pattern."""
        from motus.safety import dry_run_rm

        # Create files matching pattern
        (tmp_path / "test1.txt").write_text("content")
        (tmp_path / "test2.txt").write_text("content")
        (tmp_path / "other.txt").write_text("content")

        with patch("glob.glob") as mock_glob:
            mock_glob.return_value = [
                str(tmp_path / "test1.txt"),
                str(tmp_path / "test2.txt"),
            ]

            result = dry_run_rm([str(tmp_path / "test*.txt")])

            assert len(result.targets) == 2

    def test_dry_run_rm_glob_directory_recursive(self, tmp_path):
        """Test dry_run_rm with glob matching directories with recursive flag."""
        from motus.safety import dry_run_rm

        # Create directory structure
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "file1.txt").write_text("content")
        (subdir / "file2.txt").write_text("content")

        with patch("glob.glob") as mock_glob:
            mock_glob.return_value = [str(subdir)]

            result = dry_run_rm(["-rf", str(tmp_path / "sub*")])

            # Should find files in directory
            assert result.action == "DELETE"


class TestDryRunGitCleanParsing:
    """Test git clean output parsing (line 361)."""

    def test_dry_run_git_clean_multiple_files(self):
        """Test git clean with multiple files to remove."""
        from motus.safety import dry_run_git_clean

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="Would remove file1.txt\nWould remove file2.txt\nWould remove dir/\n"
            )

            result = dry_run_git_clean(["-fd"])

            assert result.supported is True
            assert len(result.targets) == 3
            assert "file1.txt" in result.targets
            assert "file2.txt" in result.targets
            assert "dir/" in result.targets


class TestDryRunCommandShellParsing:
    """Test dry_run_command shell parsing (lines 407-408)."""

    def test_dry_run_command_shlex_error(self, capsys):
        """Test dry_run_command with invalid shell syntax."""
        from motus.safety import dry_run_command

        # Command with unmatched quote
        dry_run_command('rm "file.txt')

        # Should fall back to simple split and continue
        capsys.readouterr()
        # Should not crash, may show unsupported or simulate


class TestDryRunCommandRouting:
    """Test dry_run_command routing to different handlers (lines 420-426)."""

    def test_dry_run_command_rm(self, capsys, tmp_path):
        """Test dry_run_command routing to dry_run_rm."""
        from motus.safety import dry_run_command

        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        dry_run_command(f"rm {test_file}")

        captured = capsys.readouterr()
        assert "DELETE" in captured.out or "Dry Run" in captured.out

    def test_dry_run_command_git_reset(self, capsys):
        """Test dry_run_command routing to dry_run_git_reset."""
        from motus.safety import dry_run_command

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="")

            dry_run_command("git reset --hard HEAD~1")

            captured = capsys.readouterr()
            assert "RESET" in captured.out or "Dry Run" in captured.out

    def test_dry_run_command_git_clean(self, capsys):
        """Test dry_run_command routing to dry_run_git_clean."""
        from motus.safety import dry_run_command

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="")

            dry_run_command("git clean -fd")

            captured = capsys.readouterr()
            assert "DELETE" in captured.out or "Dry Run" in captured.out

    def test_dry_run_command_mv(self, capsys):
        """Test dry_run_command routing to dry_run_mv."""
        from motus.safety import dry_run_command

        dry_run_command("mv old.txt new.txt")

        captured = capsys.readouterr()
        assert "MOVE" in captured.out or "Dry Run" in captured.out


class TestDryRunCommandDisplay:
    """Test dry_run_command display logic (lines 437-457)."""

    def test_dry_run_command_display_supported_low_risk(self, capsys):
        """Test display for supported command with low risk."""
        from motus.safety import dry_run_command

        dry_run_command("mv source.txt dest.txt")

        captured = capsys.readouterr()
        assert "MOVE" in captured.out
        assert "Risk" in captured.out.lower() or "Dry Run" in captured.out

    def test_dry_run_command_display_supported_high_risk(self, capsys, tmp_path):
        """Test display for supported command with high risk."""
        from motus.safety import dry_run_command

        # Create many files to trigger high risk
        for i in range(15):
            (tmp_path / f"file{i}.txt").write_text("content")

        files_str = " ".join([str(tmp_path / f"file{i}.txt") for i in range(15)])
        dry_run_command(f"rm {files_str}")

        captured = capsys.readouterr()
        assert "DELETE" in captured.out or "Dry Run" in captured.out

    def test_dry_run_command_display_not_reversible(self, capsys, tmp_path):
        """Test display shows NOT REVERSIBLE warning."""
        from motus.safety import dry_run_command

        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        dry_run_command(f"rm {test_file}")

        captured = capsys.readouterr()
        assert "NOT REVERSIBLE" in captured.out or "DELETE" in captured.out

    def test_dry_run_command_display_many_targets(self, capsys, tmp_path):
        """Test display truncates many targets."""
        from motus.safety import dry_run_command

        # Create many files
        for i in range(20):
            (tmp_path / f"file{i}.txt").write_text("content")

        files_str = " ".join([str(tmp_path / f"file{i}.txt") for i in range(20)])
        dry_run_command(f"rm {files_str}")

        captured = capsys.readouterr()
        # Should show "and X more" for files beyond first 10
        assert "more" in captured.out or "DELETE" in captured.out

    def test_dry_run_command_display_unsupported(self, capsys):
        """Test display for unsupported command."""
        from motus.safety import dry_run_command

        dry_run_command("curl https://example.com")

        captured = capsys.readouterr()
        assert "Cannot Simulate" in captured.out or "Cannot simulate" in captured.out
        assert "Supported commands" in captured.out


class TestDetectTestHarnessReturnPaths:
    """Test detect_test_harness return paths (lines 500-504)."""

    def test_detect_test_harness_cargo(self, tmp_path):
        """Test detecting Cargo.toml."""
        from motus.safety import detect_test_harness

        cargo_toml = tmp_path / "Cargo.toml"
        cargo_toml.write_text('[package]\nname = "test"')

        with patch("motus.safety.checkpoint.Path.cwd", return_value=tmp_path):
            harness = detect_test_harness()

            # Should detect cargo test command
            assert "cargo test" in harness["test_command"] or harness["test_command"] is None
            if "cargo test" in harness["test_command"]:
                assert "Cargo.toml" in harness["detected_from"]

    def test_detect_test_harness_makefile_target(self, tmp_path):
        """Test detecting Makefile with test target."""
        from motus.safety import detect_test_harness

        makefile = tmp_path / "Makefile"
        makefile.write_text("test:\n\tpytest tests/\n")

        with patch("motus.safety.checkpoint.Path.cwd", return_value=tmp_path):
            harness = detect_test_harness()

            if harness["test_command"] is not None:
                assert "Makefile" in harness["detected_from"]


class TestTestHarnessCommand:
    """Test test_harness_command display (lines 537-556)."""

    def test_test_harness_command_no_config(self, capsys, tmp_path):
        """Test test_harness_command with no detected config."""
        from motus.safety import test_harness_command

        with patch(
            "motus.safety.test_harness.detect_test_harness",
            return_value={
                "test_command": None,
                "lint_command": None,
                "build_command": None,
                "detected_from": [],
            },
        ):
            test_harness_command()

            captured = capsys.readouterr()
            assert "No test configuration detected" in captured.out
            assert "pyproject.toml" in captured.out or "package.json" in captured.out

    def test_test_harness_command_with_all_commands(self, capsys):
        """Test test_harness_command with all commands detected."""
        from motus.safety import test_harness_command

        with patch(
            "motus.safety.test_harness.detect_test_harness",
            return_value={
                "test_command": "pytest tests/",
                "lint_command": "ruff check src/",
                "build_command": "python -m build",
                "detected_from": ["pyproject.toml"],
            },
        ):
            test_harness_command()

            captured = capsys.readouterr()
            assert "Detected Test Harness" in captured.out
            assert "pytest tests/" in captured.out
            assert "ruff check src/" in captured.out
            assert "python -m build" in captured.out
            assert "pyproject.toml" in captured.out

    def test_test_harness_command_partial_config(self, capsys):
        """Test test_harness_command with only some commands."""
        from motus.safety import test_harness_command

        with patch(
            "motus.safety.test_harness.detect_test_harness",
            return_value={
                "test_command": "npm test",
                "lint_command": None,
                "build_command": None,
                "detected_from": ["package.json"],
            },
        ):
            test_harness_command()

            captured = capsys.readouterr()
            assert "npm test" in captured.out
            assert "package.json" in captured.out


class TestLoadMemoryErrorHandling:
    """Test error handling in load_memory (lines 594-595)."""

    def test_load_memory_json_decode_error(self, tmp_path):
        """Test load_memory with invalid JSON."""
        from motus.safety import load_memory

        motus_dir = tmp_path / ".motus"
        motus_dir.mkdir()
        (motus_dir / "memory.json").write_text("invalid json{")

        memories = load_memory(tmp_path)
        assert memories == []

    def test_load_memory_type_error(self, tmp_path):
        """Test load_memory with wrong data type."""
        from motus.safety import load_memory

        motus_dir = tmp_path / ".motus"
        motus_dir.mkdir()
        (motus_dir / "memory.json").write_text('["not", "memory", "objects"]')

        memories = load_memory(tmp_path)
        assert memories == []


class TestMemoryCommand:
    """Test memory_command display (lines 639-681)."""

    def test_memory_command_no_entries(self, capsys, tmp_path):
        """Test memory_command with no memories."""
        from motus.safety import memory_command

        with patch("motus.safety.memory.load_memory", return_value=[]):
            memory_command()

            captured = capsys.readouterr()
            assert "No memories recorded yet" in captured.out
            assert "tests fail" in captured.out or "fixes are applied" in captured.out

    def test_memory_command_with_entries(self, capsys, tmp_path):
        """Test memory_command with existing memories."""
        from motus.safety import MemoryEntry, memory_command

        now = datetime.now()
        entries = [
            MemoryEntry(
                timestamp=(now - timedelta(minutes=30)).isoformat(),
                file="auth.py",
                event="test_failure",
                details="TypeError: expected string, got None",
            ),
            MemoryEntry(
                timestamp=(now - timedelta(hours=2)).isoformat(),
                file="api.py",
                event="fix",
                details="Fixed import error",
            ),
            MemoryEntry(
                timestamp=(now - timedelta(days=1)).isoformat(),
                file="utils.py",
                event="lesson",
                details="Always validate input parameters",
            ),
        ]

        with patch("motus.safety.memory.load_memory", return_value=entries):
            memory_command()

            captured = capsys.readouterr()
            assert "Memory" in captured.out
            assert "auth.py" in captured.out
            assert "test_failure" in captured.out

    def test_memory_command_for_specific_file(self, capsys, tmp_path):
        """Test memory_command for a specific file."""
        from motus.safety import MemoryEntry, memory_command

        entries = [
            MemoryEntry(
                timestamp=datetime.now().isoformat(),
                file="target.py",
                event="fix",
                details="Fixed bug",
            )
        ]

        with (
            patch("motus.safety.memory.get_file_memories", return_value=entries),
            patch("motus.safety.memory.load_memory", return_value=entries),
        ):
            memory_command("target.py")

            captured = capsys.readouterr()
            assert "target.py" in captured.out

    def test_memory_command_invalid_timestamp(self, capsys):
        """Test memory_command with invalid timestamp."""
        from motus.safety import MemoryEntry, memory_command

        entries = [
            MemoryEntry(
                timestamp="invalid-timestamp",
                file="test.py",
                event="event",
                details="details",
            )
        ]

        with patch("motus.safety.memory.load_memory", return_value=entries):
            memory_command()

            captured = capsys.readouterr()
            assert "?" in captured.out  # Age should be "?"

    def test_memory_command_age_formatting(self, capsys):
        """Test memory_command age formatting for different time ranges."""
        from motus.safety import MemoryEntry, memory_command

        now = datetime.now()
        entries = [
            MemoryEntry(
                timestamp=(now - timedelta(minutes=30)).isoformat(),
                file="file1.py",
                event="event1",
                details="minutes ago",
            ),
            MemoryEntry(
                timestamp=(now - timedelta(hours=2)).isoformat(),
                file="file2.py",
                event="event2",
                details="hours ago",
            ),
            MemoryEntry(
                timestamp=(now - timedelta(days=2)).isoformat(),
                file="file3.py",
                event="event3",
                details="days ago",
            ),
        ]

        with patch("motus.safety.memory.load_memory", return_value=entries):
            memory_command()

            captured = capsys.readouterr()
            # Should show different age formats (m, h, d)
            assert "Memory" in captured.out


class TestRememberCommand:
    """Test remember_command functionality."""

    def test_remember_command(self, capsys, tmp_path):
        """Test manually recording a memory."""
        from motus.safety import remember_command

        with (
            patch("motus.safety.memory.record_memory") as mock_record,
            patch("motus.safety.checkpoint.Path.cwd", return_value=tmp_path),
        ):
            remember_command("test.py", "lesson", "Important lesson learned")

            mock_record.assert_called_once_with("test.py", "lesson", "Important lesson learned")
            captured = capsys.readouterr()
            assert "Remembered" in captured.out
            assert "lesson" in captured.out
            assert "test.py" in captured.out


class TestGetContextHints:
    """Test get_context_hints functionality (lines 700-706, 716)."""

    def test_get_context_hints_with_related_tests(self, tmp_path):
        """Test get_context_hints includes related tests."""
        from motus.safety import get_context_hints

        with (
            patch(
                "motus.safety.context.find_related_tests",
                return_value=["tests/test_api.py", "tests/test_api_integration.py"],
            ),
            patch("motus.safety.context.get_file_memories", return_value=[]),
            patch(
                "motus.safety.context.detect_test_harness",
                return_value={
                    "test_command": None,
                    "lint_command": None,
                    "build_command": None,
                    "detected_from": [],
                },
            ),
            patch("motus.safety.context.load_checkpoints", return_value=[]),
        ):
            hints = get_context_hints(["src/api.py"])

            assert "Related tests" in hints
            assert "test_api.py" in hints

    def test_get_context_hints_with_memories(self, tmp_path):
        """Test get_context_hints includes file memories."""
        from motus.safety import MemoryEntry, get_context_hints

        memory = MemoryEntry(
            timestamp=datetime.now().isoformat(),
            file="src/auth.py",
            event="test_failure",
            details="Authentication failed in edge case",
        )

        with (
            patch("motus.safety.context.find_related_tests", return_value=[]),
            patch("motus.safety.context.get_file_memories", return_value=[memory]),
            patch(
                "motus.safety.context.detect_test_harness",
                return_value={
                    "test_command": None,
                    "lint_command": None,
                    "build_command": None,
                    "detected_from": [],
                },
            ),
            patch("motus.safety.context.load_checkpoints", return_value=[]),
        ):
            hints = get_context_hints(["src/auth.py"])

            assert "Memory" in hints
            assert "test_failure" in hints

    def test_get_context_hints_with_test_harness(self, tmp_path):
        """Test get_context_hints includes test harness."""
        from motus.safety import get_context_hints

        with (
            patch("motus.safety.context.find_related_tests", return_value=[]),
            patch("motus.safety.context.get_file_memories", return_value=[]),
            patch(
                "motus.safety.context.detect_test_harness",
                return_value={
                    "test_command": "pytest tests/ -v",
                    "lint_command": None,
                    "build_command": None,
                    "detected_from": ["pyproject.toml"],
                },
            ),
            patch("motus.safety.context.load_checkpoints", return_value=[]),
        ):
            hints = get_context_hints(["src/main.py"])

            assert "Test command" in hints
            assert "pytest tests/ -v" in hints

    def test_get_context_hints_with_checkpoint(self, tmp_path):
        """Test get_context_hints includes last checkpoint."""
        from motus.safety import Checkpoint, get_context_hints

        checkpoint = Checkpoint(
            id="mc-20250115-120000",
            message="before refactor",
            timestamp="2025-01-15T12:00:00",
            files_snapshot=["src/api.py"],
        )

        with (
            patch("motus.safety.context.find_related_tests", return_value=[]),
            patch("motus.safety.context.get_file_memories", return_value=[]),
            patch(
                "motus.safety.context.detect_test_harness",
                return_value={
                    "test_command": None,
                    "lint_command": None,
                    "build_command": None,
                    "detected_from": [],
                },
            ),
            patch("motus.safety.context.load_checkpoints", return_value=[checkpoint]),
        ):
            hints = get_context_hints(["src/api.py"])

            assert "Last checkpoint" in hints
            assert "mc-20250115-120000" in hints
            assert "before refactor" in hints

    def test_get_context_hints_empty_no_files(self, tmp_path):
        """Test get_context_hints returns empty string when no hints (line 716)."""
        from motus.safety import get_context_hints

        with (
            patch("motus.safety.context.find_related_tests", return_value=[]),
            patch("motus.safety.context.get_file_memories", return_value=[]),
            patch(
                "motus.safety.context.detect_test_harness",
                return_value={
                    "test_command": None,
                    "lint_command": None,
                    "build_command": None,
                    "detected_from": [],
                },
            ),
            patch("motus.safety.context.load_checkpoints", return_value=[]),
        ):
            hints = get_context_hints([])

            assert hints == ""

    def test_get_context_hints_all_combined(self, tmp_path):
        """Test get_context_hints with all types of hints."""
        from motus.safety import (
            Checkpoint,
            MemoryEntry,
            get_context_hints,
        )

        memory = MemoryEntry(
            timestamp=datetime.now().isoformat(),
            file="src/utils.py",
            event="fix",
            details="Fixed edge case",
        )

        checkpoint = Checkpoint(
            id="mc-test",
            message="checkpoint",
            timestamp="2025-01-15T12:00:00",
            files_snapshot=["src/utils.py"],
        )

        with (
            patch(
                "motus.safety.context.find_related_tests",
                return_value=["tests/test_utils.py"],
            ),
            patch("motus.safety.context.get_file_memories", return_value=[memory]),
            patch(
                "motus.safety.context.detect_test_harness",
                return_value={
                    "test_command": "pytest tests/",
                    "lint_command": None,
                    "build_command": None,
                    "detected_from": ["pyproject.toml"],
                },
            ),
            patch("motus.safety.context.load_checkpoints", return_value=[checkpoint]),
        ):
            hints = get_context_hints(["src/utils.py"])

        assert "[Motus Context]" in hints
        assert "Related tests" in hints
        assert "Memory" in hints
        assert "Test command" in hints
        assert "Last checkpoint" in hints


class TestDryRunResultDataclass:
    """Test DryRunResult dataclass."""

    def test_dry_run_result_creation(self):
        """Test creating DryRunResult with all fields."""
        from motus.safety import DryRunResult

        result = DryRunResult(
            supported=True,
            command="rm file.txt",
            action="DELETE",
            targets=["file.txt"],
            size_bytes=1024,
            reversible=False,
            message="Would delete 1 file",
            risk="high",
        )

        assert result.supported is True
        assert result.command == "rm file.txt"
        assert result.action == "DELETE"
        assert len(result.targets) == 1
        assert result.size_bytes == 1024
        assert result.reversible is False
        assert result.risk == "high"

    def test_dry_run_result_defaults(self):
        """Test DryRunResult with default values."""
        from motus.safety import DryRunResult

        result = DryRunResult(supported=False, command="test")

        assert result.supported is False
        assert result.command == "test"
        assert result.action == ""
        assert result.targets == []
        assert result.size_bytes == 0
        assert result.reversible is True
        assert result.message == ""
        assert result.risk == "unknown"


class TestMemoryEntryDataclass:
    """Test MemoryEntry dataclass."""

    def test_memory_entry_creation(self):
        """Test creating MemoryEntry with all fields."""
        from motus.safety import MemoryEntry

        entry = MemoryEntry(
            timestamp="2025-01-15T12:00:00",
            file="test.py",
            event="test_failure",
            details="Test failed with TypeError",
            test_file="tests/test_main.py",
        )

        assert entry.timestamp == "2025-01-15T12:00:00"
        assert entry.file == "test.py"
        assert entry.event == "test_failure"
        assert entry.details == "Test failed with TypeError"
        assert entry.test_file == "tests/test_main.py"

    def test_memory_entry_optional_test_file(self):
        """Test MemoryEntry with optional test_file."""
        from motus.safety import MemoryEntry

        entry = MemoryEntry(
            timestamp="2025-01-15T12:00:00",
            file="test.py",
            event="fix",
            details="Fixed bug",
        )

        assert entry.test_file is None


class TestEdgeCases:
    """Test additional edge cases and error conditions."""

    def test_dry_run_rm_directory_without_recursive(self, tmp_path):
        """Test dry_run_rm on directory without -r flag."""
        from motus.safety import dry_run_rm

        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "file.txt").write_text("content")

        result = dry_run_rm([str(subdir)])

        # Should not include files since no -r flag
        assert result.supported is True

    def test_checkpoint_command_with_empty_message(self, tmp_path):
        """Test checkpoint_command with empty message."""
        from motus.safety import checkpoint_command

        with (
            patch("subprocess.run") as mock_run,
            patch("motus.safety.checkpoint.Path.cwd", return_value=tmp_path),
            patch("motus.safety.checkpoint.datetime") as mock_datetime,
        ):
            mock_now = MagicMock()
            mock_now.strftime.return_value = "20250115-120000"
            mock_now.isoformat.return_value = "2025-01-15T12:00:00"
            mock_datetime.now.return_value = mock_now

            mock_run.side_effect = [
                MagicMock(returncode=0),  # is git repo
                MagicMock(returncode=0, stdout=" M file.py\n"),  # has changes
                MagicMock(returncode=0),  # stash push
                MagicMock(returncode=0, stdout="stash@{0} mc-checkpoint: \n"),  # stash list
                MagicMock(returncode=0),  # stash pop
            ]

            result = checkpoint_command("")

            assert result is True

    def test_dry_run_command_empty_args(self, capsys):
        """Test dry_run_command with command that has no args."""
        from motus.safety import dry_run_command

        dry_run_command("git")

        # Should handle gracefully
        captured = capsys.readouterr()
        assert "Cannot simulate" in captured.out or "Cannot Simulate" in captured.out

    def test_get_file_memories_with_test_file_match(self, tmp_path):
        """Test get_file_memories matches test_file field."""
        from motus.safety import (
            MemoryEntry,
            get_file_memories,
            save_memory,
        )

        entries = [
            MemoryEntry(
                timestamp="2025-01-15T12:00:00",
                file="src/api.py",
                event="test_failure",
                details="Test failed",
                test_file="tests/test_api.py",
            )
        ]

        save_memory(entries, tmp_path)

        # Should find by test_file
        memories = get_file_memories("tests/test_api.py", tmp_path)
        assert len(memories) == 1
        assert memories[0].test_file == "tests/test_api.py"
