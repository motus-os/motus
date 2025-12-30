"""Tests for harness_cmd module (test harness detection command)."""

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

from motus.commands.harness_cmd import harness_command


@dataclass
class MockHarness:
    """Mock harness object for testing."""

    test_command: str = ""
    lint_command: str = ""
    build_command: str = ""
    smoke_test: str = ""


class TestHarnessCommand:
    """Test harness_command function."""

    def test_harness_command_no_detection(self):
        """Test harness command when no harness is detected."""
        mock_harness = MockHarness()

        with patch("motus.harness.detect_harness", return_value=mock_harness):
            with patch("motus.commands.harness_cmd.Path.cwd", return_value=Path("/tmp")):
                with patch("motus.commands.harness_cmd.console") as mock_console:
                    harness_command()
                    # Should print "No test harness detected"
                    assert mock_console.print.called

    def test_harness_command_with_test_command(self):
        """Test harness command with test command detected."""
        mock_harness = MockHarness(test_command="pytest")

        with patch("motus.harness.detect_harness", return_value=mock_harness):
            with patch("motus.commands.harness_cmd.Path.cwd", return_value=Path("/tmp")):
                with patch("motus.commands.harness_cmd.console") as mock_console:
                    harness_command()
                    # Should display table with test command
                    assert mock_console.print.called

    def test_harness_command_with_all_commands(self):
        """Test harness command with all commands detected."""
        mock_harness = MockHarness(
            test_command="pytest",
            lint_command="ruff check",
            build_command="python -m build",
            smoke_test="python -c 'import mymodule'",
        )

        with patch("motus.harness.detect_harness", return_value=mock_harness):
            with patch("motus.commands.harness_cmd.Path.cwd", return_value=Path("/tmp")):
                with patch("motus.commands.harness_cmd.console") as mock_console:
                    harness_command()
                    # Should display table with all commands
                    assert mock_console.print.called

    def test_harness_command_save_to_file(self):
        """Test harness command saves to file when requested."""
        mock_harness = MockHarness(
            test_command="pytest",
            lint_command="ruff check",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("motus.harness.detect_harness", return_value=mock_harness):
                with patch(
                    "motus.commands.harness_cmd.Path.cwd", return_value=Path(tmpdir)
                ):
                    with patch("motus.commands.harness_cmd.console") as mock_console:
                        harness_command(save=True)

                        # Check that file was created
                        harness_file = Path(tmpdir) / ".mc" / "harness.json"
                        assert harness_file.exists()

                        # Check content
                        with open(harness_file) as f:
                            data = json.load(f)
                            assert data["test_command"] == "pytest"
                            assert data["lint_command"] == "ruff check"

                        # Should print success message
                        assert mock_console.print.called

    def test_harness_command_save_creates_directory(self):
        """Test harness command creates .mc directory if it doesn't exist."""
        mock_harness = MockHarness(test_command="pytest")

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("motus.harness.detect_harness", return_value=mock_harness):
                with patch(
                    "motus.commands.harness_cmd.Path.cwd", return_value=Path(tmpdir)
                ):
                    with patch("motus.commands.harness_cmd.console"):
                        harness_command(save=True)

                        # .mc directory should have been created
                        mc_dir = Path(tmpdir) / ".mc"
                        assert mc_dir.exists()
                        assert mc_dir.is_dir()

    def test_harness_command_save_error_handling(self):
        """Test harness command handles file save errors gracefully."""
        mock_harness = MockHarness(test_command="pytest")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Use a real directory but make file writing fail
            with patch("motus.harness.detect_harness", return_value=mock_harness):
                with patch(
                    "motus.commands.harness_cmd.Path.cwd", return_value=Path(tmpdir)
                ):
                    with patch("builtins.open", side_effect=OSError("Permission denied")):
                        with patch("motus.commands.harness_cmd.console") as mock_console:
                            # Should not raise exception
                            harness_command(save=True)
                            # Should print error message
                            assert mock_console.print.called

    def test_harness_command_only_lint_command(self):
        """Test harness command with only lint command."""
        mock_harness = MockHarness(lint_command="ruff check")

        with patch("motus.harness.detect_harness", return_value=mock_harness):
            with patch("motus.commands.harness_cmd.Path.cwd", return_value=Path("/tmp")):
                with patch("motus.commands.harness_cmd.console") as mock_console:
                    harness_command()
                    assert mock_console.print.called

    def test_harness_command_only_build_command(self):
        """Test harness command with only build command."""
        mock_harness = MockHarness(build_command="make")

        with patch("motus.harness.detect_harness", return_value=mock_harness):
            with patch("motus.commands.harness_cmd.Path.cwd", return_value=Path("/tmp")):
                with patch("motus.commands.harness_cmd.console") as mock_console:
                    harness_command()
                    assert mock_console.print.called

    def test_harness_command_only_smoke_test(self):
        """Test harness command with only smoke test."""
        mock_harness = MockHarness(smoke_test="python -m mymodule --version")

        with patch("motus.harness.detect_harness", return_value=mock_harness):
            with patch("motus.commands.harness_cmd.Path.cwd", return_value=Path("/tmp")):
                with patch("motus.commands.harness_cmd.console") as mock_console:
                    harness_command()
                    assert mock_console.print.called

    def test_harness_command_save_without_commands(self):
        """Test that save doesn't happen when no commands detected."""
        mock_harness = MockHarness()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("motus.harness.detect_harness", return_value=mock_harness):
                with patch(
                    "motus.commands.harness_cmd.Path.cwd", return_value=Path(tmpdir)
                ):
                    with patch("motus.commands.harness_cmd.console"):
                        harness_command(save=True)

                        # .mc directory should NOT be created when no commands detected
                        mc_dir = Path(tmpdir) / ".mc"
                        # Command returns early, so directory is not created
                        assert not mc_dir.exists()

    def test_harness_command_mixed_commands(self):
        """Test harness command with some commands but not all."""
        mock_harness = MockHarness(
            test_command="npm test",
            build_command="npm run build",
        )

        with patch("motus.harness.detect_harness", return_value=mock_harness):
            with patch("motus.commands.harness_cmd.Path.cwd", return_value=Path("/tmp")):
                with patch("motus.commands.harness_cmd.console") as mock_console:
                    harness_command()
                    # Should display table with available commands
                    assert mock_console.print.called

    def test_harness_command_save_overwrites_existing(self):
        """Test that save overwrites existing harness.json file."""
        mock_harness = MockHarness(test_command="pytest -v")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create existing .mc/harness.json
            mc_dir = Path(tmpdir) / ".mc"
            mc_dir.mkdir()
            harness_file = mc_dir / "harness.json"
            with open(harness_file, "w") as f:
                json.dump({"test_command": "old command"}, f)

            with patch("motus.harness.detect_harness", return_value=mock_harness):
                with patch(
                    "motus.commands.harness_cmd.Path.cwd", return_value=Path(tmpdir)
                ):
                    with patch("motus.commands.harness_cmd.console"):
                        harness_command(save=True)

                        # Check that file was overwritten
                        with open(harness_file) as f:
                            data = json.load(f)
                            assert data["test_command"] == "pytest -v"
