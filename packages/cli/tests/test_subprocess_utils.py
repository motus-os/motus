"""Tests for subprocess_utils module."""

from unittest.mock import Mock, patch

import pytest

from motus.exceptions import SubprocessError
from motus.subprocess_utils import (
    EXIT_CODE_MEANINGS,
    MIN_MEMORY_MB,
    check_memory_before_spawn,
    decode_exit_code,
    run_with_oom_detection,
)


class TestDecodeExitCode:
    """Test exit code decoder."""

    def test_known_exit_codes(self):
        """Test decoding of known exit codes."""
        assert decode_exit_code(0) == "success"
        assert decode_exit_code(1) == "general error"
        assert decode_exit_code(2) == "misuse of command"
        assert decode_exit_code(126) == "permission denied"
        assert decode_exit_code(127) == "command not found"
        assert decode_exit_code(128) == "invalid exit argument"
        assert decode_exit_code(130) == "terminated by Ctrl+C (SIGINT)"
        assert decode_exit_code(137) == "killed (SIGKILL) - likely OOM or timeout"
        assert decode_exit_code(139) == "segmentation fault (SIGSEGV)"
        assert decode_exit_code(143) == "terminated (SIGTERM)"

    def test_signal_exit_codes(self):
        """Test decoding of exit codes from signals (>128)."""
        assert decode_exit_code(129) == "killed by signal 1"  # 128 + SIGHUP
        assert decode_exit_code(134) == "killed by signal 6"  # 128 + SIGABRT
        assert decode_exit_code(138) == "killed by signal 10"  # 128 + SIGUSR1
        assert decode_exit_code(150) == "killed by signal 22"

    def test_unknown_exit_codes(self):
        """Test decoding of unknown exit codes."""
        assert decode_exit_code(3) == "unknown (3)"
        assert decode_exit_code(42) == "unknown (42)"
        assert decode_exit_code(100) == "unknown (100)"

    def test_all_known_codes_in_dict(self):
        """Verify EXIT_CODE_MEANINGS dictionary has expected entries."""
        assert 0 in EXIT_CODE_MEANINGS
        assert 137 in EXIT_CODE_MEANINGS
        assert EXIT_CODE_MEANINGS[137] == "killed (SIGKILL) - likely OOM or timeout"


class TestCheckMemoryBeforeSpawn:
    """Test memory check function."""

    @patch("motus.subprocess_utils.psutil.virtual_memory")
    @patch("motus.subprocess_utils.logger")
    def test_sufficient_memory(self, mock_logger, mock_vmem):
        """Test when sufficient memory is available."""
        # Mock 1GB available
        mock_vmem.return_value = Mock(available=1024 * 1024 * 1024)

        result = check_memory_before_spawn()

        assert result is True
        mock_logger.warning.assert_not_called()

    @patch("motus.subprocess_utils.psutil.virtual_memory")
    @patch("motus.subprocess_utils.logger")
    def test_low_memory(self, mock_logger, mock_vmem):
        """Test when memory is low."""
        # Mock 400MB available (below MIN_MEMORY_MB of 500)
        mock_vmem.return_value = Mock(available=400 * 1024 * 1024)

        result = check_memory_before_spawn()

        assert result is False
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args[0][0]
        assert "Low memory before subprocess" in call_args
        assert "400MB" in call_args
        assert f"{MIN_MEMORY_MB}MB" in call_args

    @patch("motus.subprocess_utils.psutil.virtual_memory")
    @patch("motus.subprocess_utils.logger")
    def test_exactly_at_threshold(self, mock_logger, mock_vmem):
        """Test when memory is exactly at threshold."""
        # Mock exactly MIN_MEMORY_MB available
        mock_vmem.return_value = Mock(available=MIN_MEMORY_MB * 1024 * 1024)

        result = check_memory_before_spawn()

        # Should be True (not less than threshold)
        assert result is True
        mock_logger.warning.assert_not_called()


class TestRunWithOOMDetection:
    """Test OOM detection in subprocess runner."""

    @patch("motus.subprocess_utils.subprocess.run")
    def test_successful_command(self, mock_run):
        """Test successful command execution."""
        mock_run.return_value = Mock(returncode=0, stdout="success", stderr="")

        result = run_with_oom_detection(["echo", "hello"])

        assert result.returncode == 0
        mock_run.assert_called_once()

    @patch("motus.subprocess_utils.subprocess.run")
    def test_oom_kill_detected(self, mock_run):
        """Test OOM kill detection from stderr."""
        mock_run.return_value = Mock(returncode=137, stdout="", stderr="Killed")

        with pytest.raises(SubprocessError) as exc_info:
            run_with_oom_detection(["pytest", "tests/"])

        error = exc_info.value
        assert "Process killed (likely OOM)" in str(error)
        assert "Reduce pytest parallelism" in str(error)
        assert "pytest tests/" in str(error)

    @patch("motus.subprocess_utils.subprocess.run")
    def test_oom_cannot_allocate_memory(self, mock_run):
        """Test OOM detection with 'Cannot allocate memory' message."""
        mock_run.return_value = Mock(
            returncode=137, stdout="", stderr="Cannot allocate memory"
        )

        with pytest.raises(SubprocessError) as exc_info:
            run_with_oom_detection(["python3", "-c", "x = [0] * (10**9)"])

        error = exc_info.value
        assert "Process killed (likely OOM)" in str(error)

    @patch("motus.subprocess_utils.subprocess.run")
    def test_oom_out_of_memory(self, mock_run):
        """Test OOM detection with 'Out of memory' message."""
        mock_run.return_value = Mock(
            returncode=137, stdout="", stderr="Out of memory error occurred"
        )

        with pytest.raises(SubprocessError) as exc_info:
            run_with_oom_detection(["some-command"])

        error = exc_info.value
        assert "Process killed (likely OOM)" in str(error)

    @patch("motus.subprocess_utils.subprocess.run")
    def test_sigkill_without_oom_indicators(self, mock_run):
        """Test SIGKILL detection without OOM indicators."""
        mock_run.return_value = Mock(returncode=137, stdout="", stderr="Some other error")

        with pytest.raises(SubprocessError) as exc_info:
            run_with_oom_detection(["timeout-command"])

        error = exc_info.value
        assert "Process killed (SIGKILL)" in str(error)
        assert "timeout-command" in str(error)
        # Should mention the exit code meaning
        assert "137" in str(error.details) or "137" in str(error)

    @patch("motus.subprocess_utils.subprocess.run")
    def test_non_oom_failure(self, mock_run):
        """Test non-OOM failure (regular error code)."""
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="test failed")

        # Should not raise, just return the result
        result = run_with_oom_detection(["pytest", "tests/"])

        assert result.returncode == 1

    @patch("motus.subprocess_utils.subprocess.run")
    def test_binary_stderr_handling(self, mock_run):
        """Test handling of binary stderr output."""
        # Simulate bytes stderr
        mock_stderr = b"Killed"
        mock_run.return_value = Mock(returncode=137, stdout="", stderr=mock_stderr)

        with pytest.raises(SubprocessError) as exc_info:
            run_with_oom_detection(["some-command"])

        error = exc_info.value
        assert "Process killed (likely OOM)" in str(error)

    @patch("motus.subprocess_utils.subprocess.run")
    def test_custom_kwargs_passed_through(self, mock_run):
        """Test that custom kwargs are passed to subprocess.run."""
        mock_run.return_value = Mock(returncode=0, stdout="output", stderr="")

        run_with_oom_detection(
            ["echo", "test"], cwd="/tmp", env={"FOO": "bar"}, timeout=30.0
        )

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["cwd"] == "/tmp"
        assert call_kwargs["env"] == {"FOO": "bar"}
        assert call_kwargs["timeout"] == 30.0

    @patch("motus.subprocess_utils.subprocess.run")
    def test_error_includes_stderr_snippet(self, mock_run):
        """Test that error includes stderr snippet in details."""
        long_stderr = "A" * 300 + "Killed" + "B" * 100
        mock_run.return_value = Mock(returncode=137, stdout="", stderr=long_stderr)

        with pytest.raises(SubprocessError) as exc_info:
            run_with_oom_detection(["cmd"])

        error = exc_info.value
        # Should truncate stderr to 200 chars
        assert len(error.details) <= 250  # "stderr: " prefix + 200 chars + margin
        assert "stderr:" in error.details

