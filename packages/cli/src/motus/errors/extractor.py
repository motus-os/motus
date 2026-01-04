# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterator, Optional


class ErrorCategory(str, Enum):
    API = "api"
    EXIT = "exit"
    FILE_IO = "file_io"
    OTHER = "other"


@dataclass(frozen=True)
class ErrorItem:
    category: ErrorCategory
    message: str
    timestamp: Optional[str] = None
    exit_code: Optional[int] = None
    http_status: Optional[int] = None
    tool_command: Optional[str] = None


@dataclass(frozen=True)
class ErrorSummary:
    total_errors: int
    by_category: dict[str, int]
    by_exit_code: dict[int, int] = field(default_factory=dict)
    by_http_status: dict[int, int] = field(default_factory=dict)
    by_file_error: dict[str, int] = field(default_factory=dict)
    first_errors: list[ErrorItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_errors": self.total_errors,
            "by_category": self.by_category,
            "by_exit_code": dict(sorted(self.by_exit_code.items())),
            "by_http_status": dict(sorted(self.by_http_status.items())),
            "by_file_error": dict(sorted(self.by_file_error.items())),
            "first_errors": [e.__dict__ for e in self.first_errors],
        }


_HTTP_STATUS_RE = re.compile(r"\b(4\d\d|5\d\d)\b")


def _iter_lines(path: Path) -> Iterator[str]:
    with open(path, "rb") as f:
        for raw in f:
            if not raw.strip():
                continue
            yield raw.decode("utf-8", errors="replace")


def _parse_timestamp(data: dict[str, Any]) -> Optional[str]:
    ts = data.get("timestamp") or data.get("created_at") or data.get("time")
    if isinstance(ts, str) and ts:
        return ts
    return None


def _walk_for_key(data: Any, key: str, *, max_depth: int = 6) -> Optional[Any]:
    if max_depth <= 0:
        return None
    if isinstance(data, dict):
        if key in data:
            return data.get(key)
        for value in data.values():
            found = _walk_for_key(value, key, max_depth=max_depth - 1)
            if found is not None:
                return found
    elif isinstance(data, list):
        for item in data:
            found = _walk_for_key(item, key, max_depth=max_depth - 1)
            if found is not None:
                return found
    return None


def _extract_exit_error(data: dict[str, Any]) -> Optional[ErrorItem]:
    exit_code = _walk_for_key(data, "exit_code")
    if not isinstance(exit_code, int) or exit_code == 0:
        return None

    command = _walk_for_key(data, "command")
    if not isinstance(command, str) or not command:
        command = None

    return ErrorItem(
        category=ErrorCategory.EXIT,
        message=f"exit_code={exit_code}" + (f" command={command}" if command else ""),
        timestamp=_parse_timestamp(data),
        exit_code=exit_code,
        tool_command=command,
    )


def _extract_api_error(raw_line: str, data: dict[str, Any]) -> Optional[ErrorItem]:
    lowered = raw_line.lower()
    if "error" not in lowered and "429" not in lowered and "5" not in lowered:
        return None

    http_status = _walk_for_key(data, "status_code")
    if not isinstance(http_status, int):
        match = _HTTP_STATUS_RE.search(raw_line)
        http_status = int(match.group(1)) if match else None

    if http_status not in (429, 500, 502, 503, 504):
        return None

    return ErrorItem(
        category=ErrorCategory.API,
        message=f"http_status={http_status}",
        timestamp=_parse_timestamp(data),
        http_status=http_status,
    )


def _extract_file_error(raw_line: str, data: dict[str, Any]) -> Optional[ErrorItem]:
    lowered = raw_line.lower()
    if not any(
        token in lowered
        for token in ("enoent", "eacces", "filenotfounderror", "permissionerror")
    ):
        return None

    kind = "file_io_error"
    if "enoent" in lowered or "filenotfounderror" in lowered:
        kind = "ENOENT"
    elif "eacces" in lowered or "permissionerror" in lowered:
        kind = "EACCES"

    return ErrorItem(
        category=ErrorCategory.FILE_IO,
        message=kind,
        timestamp=_parse_timestamp(data),
    )


def extract_errors_from_jsonl(
    session_path: Path,
    *,
    max_first_errors: int = 10,
    category: Optional[ErrorCategory] = None,
) -> ErrorSummary:
    """Extract and categorize errors from a session JSONL file.

    Streaming implementation: does not load the file into memory.
    """
    by_category: dict[str, int] = {c.value: 0 for c in ErrorCategory}
    by_exit_code: dict[int, int] = {}
    by_http_status: dict[int, int] = {}
    by_file_error: dict[str, int] = {}
    first: list[ErrorItem] = []
    total = 0

    for line in _iter_lines(session_path):
        # Fast-path: skip lines unlikely to contain errors.
        lowered = line.lower()
        if (
            "error" not in lowered
            and "exit_code" not in lowered
            and "429" not in lowered
            and "enoent" not in lowered
            and "eacces" not in lowered
        ):
            continue

        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue

        item = (
            _extract_exit_error(payload)
            or _extract_api_error(line, payload)
            or _extract_file_error(line, payload)
        )
        if item is None:
            continue

        if category is not None and item.category != category:
            continue

        total += 1
        by_category[item.category.value] = by_category.get(item.category.value, 0) + 1
        if item.category == ErrorCategory.EXIT and item.exit_code is not None:
            by_exit_code[item.exit_code] = by_exit_code.get(item.exit_code, 0) + 1
        if item.category == ErrorCategory.API and item.http_status is not None:
            by_http_status[item.http_status] = by_http_status.get(item.http_status, 0) + 1
        if item.category == ErrorCategory.FILE_IO:
            by_file_error[item.message] = by_file_error.get(item.message, 0) + 1
        if len(first) < max_first_errors:
            first.append(item)

    by_category = {k: v for k, v in by_category.items() if v > 0}
    return ErrorSummary(
        total_errors=total,
        by_category=by_category,
        by_exit_code=by_exit_code,
        by_http_status=by_http_status,
        by_file_error=by_file_error,
        first_errors=first,
    )
