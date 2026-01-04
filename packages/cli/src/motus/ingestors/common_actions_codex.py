# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Codex-specific action helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from ..logging import get_logger
from .common_io import _read_tail_text

logger = get_logger(__name__)


def get_codex_last_action(
    file_path: Path, *, map_tool: Callable[[str], str], logger_obj=None
) -> str:
    """Return the last tool action in a Codex JSONL transcript."""
    try:
        content = _read_tail_text(file_path, max_bytes=10000)

        for line in reversed(content.strip().split("\n")):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                if not isinstance(data, dict):
                    continue
                if data.get("type") == "response_item":
                    payload = data.get("payload", {})
                    if not isinstance(payload, dict):
                        continue
                    if payload.get("type") == "function_call":
                        tool_name = payload.get("name", "")
                        arguments: Any = payload.get("arguments", {})

                        if isinstance(arguments, str):
                            try:
                                arguments = json.loads(arguments)
                            except json.JSONDecodeError:
                                arguments = {}

                        unified_name = map_tool(tool_name)
                        args = arguments if isinstance(arguments, dict) else {}

                        if unified_name == "Bash":
                            cmd = args.get("command", "")
                            return f"Bash: {cmd}"
                        if unified_name in ("Write", "Edit"):
                            path = args.get("path", args.get("workdir", ""))
                            return f"{unified_name} {path}"
                        if unified_name == "Read":
                            path = args.get("path", "")
                            return f"Read {path}"
                        return unified_name
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


def has_codex_completion_marker(file_path: Path, *, logger_obj=None) -> bool:
    """Check for a completion marker in a Codex JSONL transcript."""
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
                if data.get("type") == "response_item":
                    payload = data.get("payload", {})
                    if not isinstance(payload, dict):
                        continue
                    if payload.get("type") == "function_call":
                        found_tool_call = True
                        if found_response_after_tool:
                            return True
                    elif found_tool_call:
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
