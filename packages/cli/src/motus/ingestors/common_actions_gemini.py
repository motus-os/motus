# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Gemini-specific action helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from ..logging import get_logger
from .common_io import load_json_file

logger = get_logger(__name__)


def get_gemini_last_action(
    file_path: Path, *, map_tool: Callable[[str], str], logger_obj=None
) -> str:
    """Return the last tool action in a Gemini JSON transcript."""
    try:
        data = load_json_file(
            file_path, logger_obj=logger_obj, error_label="Error reading Gemini file"
        )
        if not data:
            return ""

        messages = data.get("messages", [])

        for msg in reversed(messages):
            if msg.get("type") == "gemini":
                tool_calls = msg.get("toolCalls", [])
                if tool_calls:
                    tool_call = tool_calls[-1]
                    func_name = tool_call.get("name", "")
                    func_args = tool_call.get("args", {}) or {}

                    unified_name = map_tool(func_name)

                    if unified_name == "Bash":
                        cmd = func_args.get("command", "")
                        return f"Bash: {cmd}"
                    if unified_name in ("Write", "Edit"):
                        path = func_args.get("path", "")
                        return f"{unified_name} {path}"
                    if unified_name == "Read":
                        path = func_args.get("path", "")
                        return f"Read {path}"
                    return unified_name
        return ""
    except (AttributeError, TypeError) as e:
        if logger_obj is not None:
            logger_obj.debug(
                "Error getting last action",
                file_path=str(file_path),
                error_type=type(e).__name__,
                error=str(e),
            )
        return ""


def has_gemini_completion_marker(file_path: Path, *, logger_obj=None) -> bool:
    """Check for a completion marker in a Gemini JSON transcript."""
    try:
        data = load_json_file(
            file_path, logger_obj=logger_obj, error_label="Error reading Gemini file"
        )
        if not data:
            return False

        messages = data.get("messages", [])
        if not messages:
            return False

        found_tool_call = False
        found_response_after_tool = False

        for msg in reversed(messages):
            if msg.get("type") == "gemini":
                tool_calls = msg.get("toolCalls", [])
                text_content = msg.get("content", "")

                if tool_calls:
                    found_tool_call = True
                    if found_response_after_tool:
                        return True
                elif text_content and found_tool_call:
                    found_response_after_tool = True

        return found_response_after_tool
    except (AttributeError, TypeError) as e:
        if logger_obj is not None:
            logger_obj.debug(
                "Error checking completion marker",
                file_path=str(file_path),
                error_type=type(e).__name__,
                error=str(e),
            )
        return False
