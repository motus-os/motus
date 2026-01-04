# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""JSON and file helpers for builder parsing."""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from ..logging import get_logger

logger = get_logger(__name__)

JsonDict = Dict[str, Any]

MAX_SESSION_SIZE_BYTES = 100 * 1024 * 1024
MAX_READ_ATTEMPTS = 3
READ_RETRY_DELAY_SECONDS = 0.1


def parse_jsonl_line(line: str) -> Optional[JsonDict]:
    """Parse a JSONL line safely, returning None on failure."""
    if not line or not line.strip():
        return None
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def parse_iso_timestamp(ts: str) -> Optional[datetime]:
    """Parse an ISO 8601 timestamp, returning None on failure."""
    if not ts or not isinstance(ts, str):
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError) as e:
        logger.debug("Timestamp parse failed", error_type=type(e).__name__, error=str(e))
        return None


def parse_timestamp_field(
    data: JsonDict, field: str = "timestamp", fallback: Optional[datetime] = None
) -> datetime:
    """Parse a timestamp field from a dict, defaulting to fallback/now."""
    ts = data.get(field)
    parsed = parse_iso_timestamp(ts) if isinstance(ts, str) else None
    if parsed is not None:
        return parsed
    return fallback if fallback is not None else datetime.now()


def iter_jsonl_dicts(
    file_path: Path, *, logger_obj=None, error_label: str = "Error reading transcript"
) -> Iterator[JsonDict]:
    """Yield dict objects from a JSONL file, skipping invalid lines."""
    try:
        if not file_path.exists():
            return

        file_size = file_path.stat().st_size
        if file_size > MAX_SESSION_SIZE_BYTES:
            if logger_obj is not None:
                logger_obj.warning(
                    "Skipping large session file",
                    file_path=str(file_path),
                    file_size=file_size,
                )
            return

        for attempt in range(MAX_READ_ATTEMPTS):
            parsed: list[JsonDict] = []
            retry_last_line = False

            with open(file_path, "rb") as f:
                for raw in f:
                    if not raw.strip():
                        continue
                    line = raw.decode("utf-8", errors="replace")
                    data = parse_jsonl_line(line)
                    if data is not None:
                        parsed.append(data)
                        continue

                    if not raw.endswith(b"\n") and attempt < MAX_READ_ATTEMPTS - 1:
                        retry_last_line = True
                        break

            if retry_last_line:
                time.sleep(READ_RETRY_DELAY_SECONDS)
                continue

            yield from parsed
            return
    except OSError as e:
        if logger_obj is not None:
            logger_obj.error(
                error_label,
                file_path=str(file_path),
                error_type=type(e).__name__,
                error=str(e),
            )
        return


def _read_tail_text(file_path: Path, max_bytes: int = 10000) -> str:
    try:
        file_size = file_path.stat().st_size
        read_size = min(max_bytes, file_size)
        with open(file_path, "rb") as f:
            f.seek(max(0, file_size - read_size))
            return f.read().decode("utf-8", errors="ignore")
    except OSError as e:
        logger.warning(
            "Failed to read tail text",
            file_path=str(file_path),
            error_type=type(e).__name__,
            error=str(e),
        )
        return ""


def scan_file_tail(path: Path, num_lines: int) -> list[str]:
    """Read the last N lines from a text file efficiently."""
    if num_lines <= 0:
        return []
    content = _read_tail_text(path, max_bytes=10000)
    lines = content.strip().split("\n")
    if not lines or lines == [""]:
        return []
    return lines[-num_lines:]


def iter_jsonl_tail_dicts(file_path: Path, max_bytes: int = 10000) -> Iterator[JsonDict]:
    """Yield dict objects from the tail of a JSONL file (reverse order)."""
    content = _read_tail_text(file_path, max_bytes=max_bytes)
    for line in reversed(content.strip().split("\n")):
        data = parse_jsonl_line(line)
        if data is not None:
            yield data


def load_json_file(
    file_path: Path, *, logger_obj=None, error_label: str = "Error reading JSON file"
) -> Optional[JsonDict]:
    """Load a JSON file safely, returning None on failure."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        target_logger = logger_obj or logger
        target_logger.error(
            error_label,
            file_path=str(file_path),
            error_type=type(e).__name__,
            error=str(e),
        )
        return None
    return data if isinstance(data, dict) else None
