# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Efficient tail-based reading for large JSONL files.

This module provides fast access to the most recent lines of JSONL session files
without parsing the entire file. For a 197MB file, this reduces load time from
~1700ms to ~180ms.
"""

import json
from collections import deque
from pathlib import Path
from typing import Union

from motus.logging import get_logger

logger = get_logger(__name__)


def tail_lines(
    file_path: Union[str, Path],
    n_lines: int = 200,
) -> list[str]:
    """Read the last N lines from a file as raw strings.

    Uses deque(maxlen=n) which scans the file but only keeps the last n lines
    in memory. No parsing is done - lines are returned as-is for downstream
    processing by ingestors (ClaudeBuilder, CodexBuilder, GeminiBuilder).

    Args:
        file_path: Path to the file
        n_lines: Number of lines to return from the end (default 200)

    Returns:
        List of raw line strings from the last n_lines of the file

    Example:
        >>> from motus.ingestors.claude import ClaudeBuilder
        >>> builder = ClaudeBuilder()
        >>> lines = tail_lines("~/.claude/projects/.../session.jsonl", n_lines=200)
        >>> for line in lines:
        ...     events = builder.parse_line(line, session_id="my-session")
    """
    path = Path(file_path).expanduser()
    if not path.exists():
        return []

    # Read raw bytes (faster) and keep last n lines
    try:
        with open(path, "rb") as f:
            raw_lines = deque(f, maxlen=n_lines)
    except OSError as e:
        logger.warning(
            "Failed to read tail lines",
            file_path=str(path),
            error_type=type(e).__name__,
            error=str(e),
        )
        return []

    # Decode to strings (tolerate bad bytes to avoid crashing on corrupted files)
    return [raw.decode("utf-8", errors="replace").strip() for raw in raw_lines if raw.strip()]


def tail_jsonl(
    file_path: Union[str, Path],
    n_lines: int = 200,
    skip_invalid: bool = True,
) -> list[dict]:
    """Read the last N lines from a JSONL file efficiently.

    Uses deque(maxlen=n) which scans the file but only keeps the last n lines
    in memory. JSON parsing is only done for the retained lines.

    Args:
        file_path: Path to the JSONL file
        n_lines: Number of lines to return from the end (default 200)
        skip_invalid: If True, skip lines that fail JSON parsing

    Returns:
        List of parsed JSON objects from the last n_lines of the file

    Example:
        >>> events = tail_jsonl("~/.claude/projects/.../session.jsonl", n_lines=200)
        >>> len(events)  # Up to 200 most recent events
        200
    """
    path = Path(file_path).expanduser()
    if not path.exists():
        return []

    # Read raw bytes (faster) and keep last n lines
    try:
        with open(path, "rb") as f:
            raw_lines = deque(f, maxlen=n_lines)
    except OSError as e:
        logger.warning(
            "Failed to read tail jsonl",
            file_path=str(path),
            error_type=type(e).__name__,
            error=str(e),
        )
        return []

    # Parse JSON only for retained lines
    results = []
    for raw in raw_lines:
        try:
            obj = json.loads(raw.decode("utf-8", errors="replace"))
            results.append(obj)
        except (json.JSONDecodeError, UnicodeDecodeError):
            if not skip_invalid:
                raise
            continue

    return results


def count_lines(file_path: Union[str, Path]) -> int:
    """Count total lines in a file efficiently.

    This scans the file but doesn't parse JSON, so it's fast (~250ms for 197MB).

    Args:
        file_path: Path to the file

    Returns:
        Total number of lines in the file
    """
    path = Path(file_path).expanduser()
    if not path.exists():
        return 0

    try:
        with open(path, "rb") as f:
            return sum(1 for _ in f)
    except OSError as e:
        logger.warning(
            "Failed to count lines",
            file_path=str(path),
            error_type=type(e).__name__,
            error=str(e),
        )
        return 0


def get_file_stats(file_path: Union[str, Path]) -> dict:
    """Get file stats for pagination support.

    Returns:
        Dict with 'size_bytes', 'size_mb', 'line_count' (estimated)
    """
    path = Path(file_path).expanduser()
    if not path.exists():
        return {"size_bytes": 0, "size_mb": 0.0, "line_count": 0}

    try:
        size = path.stat().st_size
    except OSError as e:
        logger.warning(
            "Failed to stat file",
            file_path=str(path),
            error_type=type(e).__name__,
            error=str(e),
        )
        return {"size_bytes": 0, "size_mb": 0.0, "line_count": 0}

    # Estimate line count from file size (avg ~6KB per line for Claude sessions)
    estimated_lines = size // 6000

    return {
        "size_bytes": size,
        "size_mb": round(size / (1024 * 1024), 1),
        "line_count": estimated_lines,
    }
