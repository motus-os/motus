# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Shared subprocess helpers (timeouts + consistent errors)."""

from __future__ import annotations

import logging
import os
import shlex
import subprocess
from pathlib import Path
from typing import IO, Mapping, Sequence

import psutil

from motus.exceptions import SubprocessError, SubprocessTimeoutError

logger = logging.getLogger(__name__)

GIT_SHORT_TIMEOUT_SECONDS = 30.0
GIT_LONG_TIMEOUT_SECONDS = 60.0
PYTEST_TIMEOUT_SECONDS = 300.0
DEFAULT_GATE_TIMEOUT_SECONDS = 120.0
MIN_MEMORY_MB = 500  # Minimum free memory before spawning subprocess

OOM_INDICATORS = ("Killed", "Cannot allocate memory", "Out of memory")

# Exit code meanings for common shell exit codes
EXIT_CODE_MEANINGS = {
    0: "success",
    1: "general error",
    2: "misuse of command",
    126: "permission denied",
    127: "command not found",
    128: "invalid exit argument",
    130: "terminated by Ctrl+C (SIGINT)",
    137: "killed (SIGKILL) - likely OOM or timeout",
    139: "segmentation fault (SIGSEGV)",
    143: "terminated (SIGTERM)",
}


def decode_exit_code(code: int) -> str:
    """Return human-readable meaning of exit code.

    Args:
        code: The exit code to decode

    Returns:
        Human-readable description of the exit code

    Examples:
        >>> decode_exit_code(0)
        'success'
        >>> decode_exit_code(137)
        'killed (SIGKILL) - likely OOM or timeout'
        >>> decode_exit_code(150)
        'killed by signal 22'
    """
    if code in EXIT_CODE_MEANINGS:
        return EXIT_CODE_MEANINGS[code]
    if code > 128:
        signal_num = code - 128
        return f"killed by signal {signal_num}"
    return f"unknown ({code})"


def check_memory_before_spawn() -> bool:
    """Warn if memory is low before spawning subprocess.

    Returns:
        True if sufficient memory available, False if low memory detected

    Side effects:
        Logs a warning if available memory is below MIN_MEMORY_MB
    """
    mem = psutil.virtual_memory()
    available_mb = mem.available / 1024 / 1024

    if available_mb < MIN_MEMORY_MB:
        logger.warning(
            f"Low memory before subprocess: {available_mb:.0f}MB available "
            f"(recommended: {MIN_MEMORY_MB}MB). Risk of OOM."
        )
        return False
    return True


def run_with_oom_detection(
    cmd: list[str],
    *,
    capture_output: bool = True,
    text: bool = True,
    timeout: float | None = None,
    **kwargs,
) -> subprocess.CompletedProcess:
    """Run subprocess with OOM detection.

    Args:
        cmd: Command to run as list of strings
        capture_output: Whether to capture stdout/stderr (default: True)
        text: Whether to decode output as text (default: True)
        timeout: Optional timeout in seconds
        **kwargs: Additional arguments to pass to subprocess.run

    Returns:
        CompletedProcess result

    Raises:
        SubprocessError: If process was killed (exit code 137) with OOM/kill detection

    Examples:
        >>> result = run_with_oom_detection(["echo", "hello"])
        >>> result.returncode
        0
    """
    result = subprocess.run(
        cmd, capture_output=capture_output, text=text, timeout=timeout, **kwargs
    )

    if result.returncode == 137:
        # Check if it was OOM
        stderr = (
            result.stderr
            if isinstance(result.stderr, str)
            else result.stderr.decode(errors="replace")
        )

        is_oom = any(indicator in stderr for indicator in OOM_INDICATORS)

        if is_oom:
            raise SubprocessError(
                f"Process killed (likely OOM): {' '.join(cmd)}\n"
                f"Suggestions:\n"
                f"  - Reduce pytest parallelism: pytest -n 2\n"
                f"  - Increase Docker memory limit\n"
                f"  - Run fewer concurrent evaluations",
                argv=cmd,
                details=f"stderr: {stderr[:200]}",
            )

        raise SubprocessError(
            f"Process killed (SIGKILL): {' '.join(cmd)}",
            argv=cmd,
            details=f"Exit code: 137 ({decode_exit_code(137)})",
        )

    return result


def _read_tail_bytes(path: Path, max_bytes: int) -> bytes:
    if max_bytes <= 0:
        return b""
    try:
        with path.open("rb") as f:
            try:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                f.seek(max(0, size - max_bytes))
            except OSError:
                pass
            return f.read()
    except OSError:
        return b""


def _stderr_hint_for_sigkill(tail: str, *, argv: Sequence[str], what: str) -> str:
    joined = " ".join(argv)
    is_oom = any(indicator in tail for indicator in OOM_INDICATORS)
    if is_oom:
        header = f"Process killed (likely OOM): {joined}"
        details = "Detected OOM indicators in stderr."
    else:
        header = f"Process killed (SIGKILL): {joined}"
        details = "SIGKILL can be caused by OOM, container limits, or external timeouts."

    return (
        "\n"
        f"[motus] {what} exited with 137 ({decode_exit_code(137)}).\n"
        f"[motus] {header}\n"
        f"[motus] {details}\n"
        "[motus] Suggestions:\n"
        "[motus]   - Reduce pytest parallelism: pytest -n 2\n"
        "[motus]   - Increase Docker memory limit\n"
        "[motus]   - Reduce concurrent evaluations\n"
    )


def _format_argv(argv: Sequence[str]) -> str:
    try:
        return shlex.join(list(argv))
    except Exception:
        return " ".join(argv)


def run_subprocess(
    argv: Sequence[str],
    *,
    cwd: Path | None = None,
    timeout_seconds: float,
    what: str,
    capture_output: bool = False,
    text: bool = False,
    check: bool = False,
    env: Mapping[str, str] | None = None,
    stdout: IO[str] | None = None,
    stderr: IO[str] | None = None,
) -> subprocess.CompletedProcess:
    """Run subprocess with timeout and consistent errors.

    Notes:
    - `timeout_seconds` is required (Motus is fail-closed on hangs).
    - Raises `SubprocessTimeoutError` for timeouts and `SubprocessError` for execution failures.
    """

    argv_list = list(argv)
    if not argv_list:
        raise ValueError("argv must be non-empty")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be > 0")

    try:
        check_memory_before_spawn()
    except Exception:
        pass

    try:
        proc = subprocess.run(
            argv_list,
            cwd=cwd,
            capture_output=capture_output,
            text=text,
            check=check,
            env=env,
            stdout=stdout,
            stderr=stderr,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as e:
        raise SubprocessTimeoutError(
            f"{what} timed out after {timeout_seconds}s",
            argv=argv_list,
            timeout_seconds=timeout_seconds,
            details=_format_argv(argv_list),
        ) from e
    except FileNotFoundError as e:
        raise SubprocessError(
            f"{what} command not found",
            argv=argv_list,
            details=str(e),
        ) from e
    except PermissionError as e:
        raise SubprocessError(
            f"{what} command not executable",
            argv=argv_list,
            details=str(e),
        ) from e
    except OSError as e:
        raise SubprocessError(
            f"{what} failed to execute",
            argv=argv_list,
            details=str(e),
        ) from e

    if proc.returncode == 137:
        tail_text = ""
        if proc.stderr is not None:
            if isinstance(proc.stderr, str):
                tail_text = proc.stderr[-4096:]
            else:
                tail_text = proc.stderr.decode(errors="replace")[-4096:]
        else:
            stderr_name = getattr(stderr, "name", None)
            if isinstance(stderr_name, str) and stderr_name:
                tail_text = _read_tail_bytes(Path(stderr_name), 4096).decode(
                    errors="replace"
                )

        hint = _stderr_hint_for_sigkill(tail_text, argv=argv_list, what=what)
        try:
            if stderr is not None:
                stderr.write(hint)
                stderr.flush()
            elif proc.stderr is not None:
                if isinstance(proc.stderr, str):
                    proc.stderr += hint
                else:
                    proc.stderr += hint.encode("utf-8", errors="replace")
        except Exception:
            pass

    return proc
