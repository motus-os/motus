# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Claude-specific action helpers."""

from __future__ import annotations

import json
from pathlib import Path

from ..logging import get_logger
from .common_io import _read_tail_text

logger = get_logger(__name__)


def get_claude_last_action(file_path: Path, *, logger_obj=None) -> str:
    """Return the last tool action in a Claude JSONL transcript."""
    try:
        content = _read_tail_text(file_path, max_bytes=10000)

        for line in reversed(content.strip().split("\n")):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                if not isinstance(data, dict):
                    continue
                if data.get("type") == "assistant":
                    for block in data.get("message", {}).get("content", []):
                        if block.get("type") == "tool_use":
                            name = block.get("name", "")
                            inp = block.get("input", {}) or {}
                            if name == "Edit":
                                return f"Edit {inp.get('file_path', '')}"
                            if name == "Write":
                                return f"Write {inp.get('file_path', '')}"
                            if name == "Bash":
                                cmd = inp.get("command", "")
                                return f"Bash: {cmd}"
                            if name == "Read":
                                return f"Read {inp.get('file_path', '')}"
                            return name
            except json.JSONDecodeError:
                continue
        return ""
    except OSError as e:
        if logger_obj is not None:
            logger_obj.debug(
                "Error getting last action",
                file_path=str(file_path),
                error_type=type(e).__name__,
                error=str(e),
            )
        return ""


def has_claude_completion_marker(file_path: Path, *, logger_obj=None) -> bool:
    """Check for a completion marker in a Claude JSONL transcript."""
    try:
        content = _read_tail_text(file_path, max_bytes=10000)

        found_tool_call = False
        found_response_after_tool = False

        for line in reversed(content.strip().split("\n")):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                if not isinstance(data, dict):
                    continue
                if data.get("type") == "assistant":
                    content_blocks = data.get("message", {}).get("content", [])
                    has_tool_use = any(b.get("type") == "tool_use" for b in content_blocks)
                    has_text = any(b.get("type") == "text" for b in content_blocks)

                    if has_tool_use:
                        found_tool_call = True
                        if found_response_after_tool:
                            return True
                    elif has_text and found_tool_call:
                        found_response_after_tool = True
            except json.JSONDecodeError:
                continue

        return found_response_after_tool
    except OSError as e:
        if logger_obj is not None:
            logger_obj.debug(
                "Error checking completion marker",
                file_path=str(file_path),
                error_type=type(e).__name__,
                error=str(e),
            )
        return False
