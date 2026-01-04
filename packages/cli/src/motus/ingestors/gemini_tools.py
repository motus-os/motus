# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Tool handling helpers for Gemini transcripts."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Callable

from ..protocols import EventType, UnifiedEvent

GEMINI_TOOL_MAP = {
    "shell": "Bash",
    "run_shell_command": "Bash",
    "read_file": "Read",
    "write_file": "Write",
    "edit_file": "Edit",
    "search_files": "Grep",
    "list_files": "Glob",
    "web_search": "WebSearch",
    "web_fetch": "WebFetch",
}


def map_gemini_tool(tool_name: str) -> str:
    """Map Gemini function name to unified tool name."""
    return GEMINI_TOOL_MAP.get(tool_name, tool_name)


def build_tool_events(
    tool_calls: list[dict],
    *,
    session_id: str,
    timestamp,
    model: str,
    base_raw_data: dict,
    create_tool_event: Callable[..., UnifiedEvent],
    assess_risk: Callable[[str, dict], Any],
) -> list[UnifiedEvent]:
    events: list[UnifiedEvent] = []

    for tool_call in tool_calls:
        func_name = tool_call.get("name", "")
        func_args = tool_call.get("args", {})
        mapped_name = map_gemini_tool(func_name)
        tool_call_id = tool_call.get("id")

        tool_error = tool_call.get("error")
        if tool_error:
            events.append(
                UnifiedEvent(
                    event_id=str(uuid.uuid4()),
                    session_id=session_id,
                    timestamp=timestamp,
                    event_type=EventType.ERROR,
                    content=f"Tool error ({mapped_name}): {tool_error}",
                    tool_name=mapped_name,
                    model=model,
                    raw_data={
                        **base_raw_data,
                        "tool_call_id": tool_call_id,
                        "tool_error": tool_error,
                    },
                )
            )

        tool_result = tool_call.get("result", tool_call.get("output", ""))
        if tool_result and not tool_error:
            events.append(
                UnifiedEvent(
                    event_id=str(uuid.uuid4()),
                    session_id=session_id,
                    timestamp=timestamp,
                    event_type=EventType.TOOL_RESULT,
                    content=str(tool_result),
                    tool_output=str(tool_result),
                    tool_use_id=tool_call_id,
                    tool_name=mapped_name,
                    raw_data={
                        **base_raw_data,
                        "tool_call_id": tool_call_id,
                        "tool_name": mapped_name,
                        "has_error": False,
                    },
                )
            )

        if mapped_name == "Task":
            agent_type = func_args.get("subagent_type", "general") if func_args else "general"
            description = func_args.get("description", "") if func_args else ""
            prompt = func_args.get("prompt", "") if func_args else ""
            context_text = func_args.get("context", "") if func_args else ""
            agent_model = func_args.get("model") if func_args else None

            events.append(
                UnifiedEvent(
                    event_id=str(uuid.uuid4()),
                    session_id=session_id,
                    timestamp=timestamp,
                    event_type=EventType.AGENT_SPAWN,
                    content=f"{agent_type}: {description}",
                    agent_type=agent_type,
                    agent_description=description,
                    agent_prompt=prompt,
                    agent_model=agent_model,
                    model=model,
                    raw_data={
                        **base_raw_data,
                        "tool_call_id": tool_call_id,
                        "full_description": description,
                        "full_prompt": prompt,
                        "context": context_text,
                        "depth": 1,
                    },
                )
            )
        else:
            risk_level_enum = assess_risk(mapped_name, func_args or {})
            tool_event = create_tool_event(
                name=mapped_name,
                input_data=func_args or {},
                session_id=session_id,
                timestamp=timestamp,
                risk_level=risk_level_enum,
            )
            tool_event.raw_data = {
                **base_raw_data,
                "tool_call_id": tool_call_id,
                **(tool_event.raw_data or {}),
            }
            events.append(tool_event)

            file_path_arg = (
                (func_args.get("file_path") or func_args.get("path")) if func_args else None
            )
            if mapped_name in ("Read", "Glob", "Grep") and file_path_arg:
                events.append(
                    UnifiedEvent(
                        event_id=str(uuid.uuid4()),
                        session_id=session_id,
                        timestamp=timestamp,
                        event_type=EventType.FILE_READ,
                        content=f"Read: {Path(file_path_arg).name}",
                        file_path=file_path_arg,
                    )
                )
            elif mapped_name in ("Write", "Edit") and file_path_arg:
                events.append(
                    UnifiedEvent(
                        event_id=str(uuid.uuid4()),
                        session_id=session_id,
                        timestamp=timestamp,
                        event_type=EventType.FILE_MODIFIED,
                        content=f"Modified: {Path(file_path_arg).name}",
                        file_path=file_path_arg,
                    )
                )

    return events
