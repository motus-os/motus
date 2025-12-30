"""Tests for subprocess_utils run paths."""

import subprocess
from unittest.mock import Mock, patch

import pytest

from motus.exceptions import SubprocessError, SubprocessTimeoutError
from motus.subprocess_utils import (
    _format_argv,
    _read_tail_bytes,
    check_memory_before_spawn,
    decode_exit_code,
    run_subprocess,
    run_with_oom_detection,
)


class TestIntegration:
    """Integration tests with actual subprocess calls."""

    def test_decode_exit_code_with_real_exit_137(self):
        """Test decoding exit code 137."""
        result = decode_exit_code(137)
        assert result == "killed (SIGKILL) - likely OOM or timeout"
        assert "OOM" in result or "timeout" in result

    def test_successful_echo_command(self):
        """Test running actual echo command."""
        result = run_with_oom_detection(["echo", "hello"])
        assert result.returncode == 0
        assert "hello" in result.stdout

    def test_failing_command_non_137(self):
        """Test running command that fails with non-137 exit code."""
        # This command should fail with exit code 1
        result = run_with_oom_detection(["false"])
        assert result.returncode == 1
        # Should not raise exception for non-137 exit codes

    @patch("motus.subprocess_utils.psutil.virtual_memory")
    def test_memory_check_with_real_psutil(self, mock_vmem):
        """Test memory check with mocked psutil but real logic."""
        # Mock sufficient memory
        mock_vmem.return_value = Mock(available=1024 * 1024 * 1024)
        assert check_memory_before_spawn() is True

        # Mock low memory
        mock_vmem.return_value = Mock(available=100 * 1024 * 1024)
        assert check_memory_before_spawn() is False


class TestRunSubprocessSigkillHints:
    """Test SIGKILL (exit 137) hints in run_subprocess."""

    @patch("motus.subprocess_utils.check_memory_before_spawn", return_value=True)
    @patch("motus.subprocess_utils.subprocess.run")
    def test_sigkill_appends_hint_to_stderr_file_when_available(
        self, mock_run, _mock_mem, tmp_path
    ):
        stderr_path = tmp_path / "stderr.txt"
        stdout_path = tmp_path / "stdout.txt"

        with (
            stdout_path.open("w", encoding="utf-8") as stdout_file,
            stderr_path.open("w+", encoding="utf-8") as stderr_file,
        ):
            stderr_file.write("Killed\n")
            stderr_file.flush()
            mock_run.return_value = Mock(returncode=137, stdout=None, stderr=None)

            proc = run_subprocess(
                ["pytest", "tests/"],
                cwd=tmp_path,
                stdout=stdout_file,
                stderr=stderr_file,
                text=True,
                timeout_seconds=1.0,
                what="gate subprocess",
            )

        assert proc.returncode == 137
        stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace")
        assert "Killed" in stderr_text
        assert "[motus] gate subprocess exited with 137" in stderr_text
        assert "likely OOM" in stderr_text

    @patch("motus.subprocess_utils.check_memory_before_spawn", return_value=True)
    @patch("motus.subprocess_utils.subprocess.run")
    def test_sigkill_without_oom_indicators_appends_generic_hint(
        self, mock_run, _mock_mem, tmp_path
    ):
        stderr_path = tmp_path / "stderr.txt"
        stdout_path = tmp_path / "stdout.txt"

        with (
            stdout_path.open("w", encoding="utf-8") as stdout_file,
            stderr_path.open("w+", encoding="utf-8") as stderr_file,
        ):
            stderr_file.write("Some other error\n")
            stderr_file.flush()
            mock_run.return_value = Mock(returncode=137, stdout=None, stderr=None)

            proc = run_subprocess(
                ["git", "status", "--short"],
                cwd=tmp_path,
                stdout=stdout_file,
                stderr=stderr_file,
                text=True,
                timeout_seconds=1.0,
                what="git status",
            )

        assert proc.returncode == 137
        stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace")
        assert "[motus] git status exited with 137" in stderr_text
        assert "SIGKILL can be caused" in stderr_text

    @patch("motus.subprocess_utils.check_memory_before_spawn", return_value=True)
    @patch("motus.subprocess_utils.subprocess.run")
    def test_sigkill_appends_hint_to_captured_stderr(self, mock_run, _mock_mem):
        mock_run.return_value = Mock(returncode=137, stdout="", stderr="Killed")

        proc = run_subprocess(
            ["pytest", "tests/"],
            capture_output=True,
            text=True,
            timeout_seconds=1.0,
            what="pytest",
        )

        assert proc.returncode == 137
        assert isinstance(proc.stderr, str)
        assert "[motus] pytest exited with 137" in proc.stderr


class TestSubprocessUtilityPaths:
    """Cover remaining branches for subprocess utilities."""

    def test_read_tail_bytes_returns_empty_for_nonpositive(self, tmp_path):
        path = tmp_path / "file.txt"
        assert _read_tail_bytes(path, 0) == b""

    def test_read_tail_bytes_missing_file(self, tmp_path):
        path = tmp_path / "missing.txt"
        assert _read_tail_bytes(path, 10) == b""

    def test_format_argv_fallback_on_exception(self, monkeypatch):
        def _boom(_argv):
            raise RuntimeError("nope")

        monkeypatch.setattr("motus.subprocess_utils.shlex.join", _boom)
        assert _format_argv(["echo", "hi"]) == "echo hi"

    def test_run_subprocess_rejects_empty_argv(self):
        with pytest.raises(ValueError):
            run_subprocess([], timeout_seconds=1.0, what="empty argv")

    def test_run_subprocess_rejects_nonpositive_timeout(self):
        with pytest.raises(ValueError):
            run_subprocess(["echo"], timeout_seconds=0, what="bad timeout")

    @patch("motus.subprocess_utils.subprocess.run")
    def test_run_subprocess_timeout_error(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["sleep"], timeout=1)

        with pytest.raises(SubprocessTimeoutError):
            run_subprocess(["sleep", "1"], timeout_seconds=1.0, what="sleep")

    @patch("motus.subprocess_utils.subprocess.run")
    def test_run_subprocess_command_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError("missing")

        with pytest.raises(SubprocessError) as exc_info:
            run_subprocess(["missing"], timeout_seconds=1.0, what="missing")
        assert "command not found" in str(exc_info.value)

    @patch("motus.subprocess_utils.subprocess.run")
    def test_run_subprocess_permission_error(self, mock_run):
        mock_run.side_effect = PermissionError("denied")

        with pytest.raises(SubprocessError) as exc_info:
            run_subprocess(["nope"], timeout_seconds=1.0, what="nope")
        assert "command not executable" in str(exc_info.value)

    @patch("motus.subprocess_utils.subprocess.run")
    def test_run_subprocess_oserror(self, mock_run):
        mock_run.side_effect = OSError("bad")

        with pytest.raises(SubprocessError) as exc_info:
            run_subprocess(["bad"], timeout_seconds=1.0, what="bad")
        assert "failed to execute" in str(exc_info.value)

    @patch("motus.subprocess_utils.check_memory_before_spawn", return_value=True)
    @patch("motus.subprocess_utils.subprocess.run")
    def test_run_subprocess_sigkill_with_binary_stderr(self, mock_run, _mock_mem):
        mock_run.return_value = Mock(returncode=137, stdout=None, stderr=b"Killed")

        proc = run_subprocess(
            ["pytest", "tests/"],
            capture_output=True,
            text=False,
            timeout_seconds=1.0,
            what="pytest",
        )

        assert proc.returncode == 137
        assert b"[motus] pytest exited with 137" in proc.stderr
