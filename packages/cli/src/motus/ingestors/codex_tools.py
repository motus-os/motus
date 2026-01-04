# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Codex tool mapping and tool-related helpers."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from ..commands.utils import assess_risk
from ..protocols import EventType, UnifiedEvent

# Map Codex tool names to unified names
CODEX_TOOL_MAP = {
    "shell_command": "Bash",
    "update_plan": "TodoWrite",
    "list_mcp_resources": "MCP",
    "read_file": "Read",
    "write_file": "Write",
    "edit_file": "Edit",
    "create_file": "Write",
}


def map_codex_tool(tool_name: str) -> str:
    """Map Codex tool name to unified tool name."""
    if tool_name in CODEX_TOOL_MAP:
        return CODEX_TOOL_MAP[tool_name]
    if tool_name.startswith("mcp__"):
        return "MCP"
    return tool_name


def build_thinking_surrogate(tool_name: str, arguments: Dict[str, Any]) -> str:
    """Build a synthetic thinking description for a tool call."""
    if tool_name == "Bash":
        cmd = arguments.get("command", "")
        return f"Executing shell command: {cmd}"
    if tool_name in ("Write", "Edit"):
        path = arguments.get("path", arguments.get("workdir", "file"))
        return f"Modifying file: {path}"
    if tool_name == "Read":
        path = arguments.get("path", "file")
        return f"Reading file: {path}"
    if tool_name == "TodoWrite":
        return "Updating plan/todo list"
    return f"Using tool: {tool_name}"


def _build_planning_thinking(
    unified_tool: str, arguments: Dict[str, Any], file_path: str | None
) -> str:
    thinking_content = f"Planning: {unified_tool}"
    if unified_tool == "Bash":
        cmd = arguments.get("command", "")
        thinking_content = f"Planning to run: {cmd}"
    elif unified_tool in ("Write", "Edit"):
        thinking_content = f"Planning to modify: {file_path or 'file'}"
    elif unified_tool == "Read":
        thinking_content = f"Planning to read: {file_path or 'file'}"
    return thinking_content


def parse_function_call(
    payload: Dict[str, Any],
    session_id: str,
    timestamp: datetime,
    *,
    create_tool_event,
    rate_limit_data: Dict[str, Any],
) -> List[UnifiedEvent]:
    """Parse a Codex function_call payload into UnifiedEvent records."""
    events: List[UnifiedEvent] = []
    tool_name = payload.get("name", "unknown")
    arguments = payload.get("arguments", {})
    call_id = payload.get("call_id")

    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except (json.JSONDecodeError, TypeError):
            arguments = {"raw": arguments}

    unified_tool = map_codex_tool(tool_name)
    file_path = (
        arguments.get("file_path") or arguments.get("path") or arguments.get("workdir")
    )

    if unified_tool == "Task":
        agent_type = arguments.get("subagent_type", "general")
        description = arguments.get("description", "")
        prompt = arguments.get("prompt", "")
        context_text = arguments.get("context", "")
        agent_model = arguments.get("model")

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
                raw_data={
                    "context": context_text,
                    "depth": 1,
                },
            )
        )
    else:
        tool_event = create_tool_event(
            name=unified_tool,
            input_data=arguments,
            session_id=session_id,
            timestamp=timestamp,
            risk_level=assess_risk(unified_tool, arguments),
        )
        tool_event.raw_data = {
            **rate_limit_data,
            "call_id": call_id,
            **(tool_event.raw_data or {}),
        }
        events.append(tool_event)

    thinking_content = _build_planning_thinking(unified_tool, arguments, file_path)
    events.append(
        UnifiedEvent(
            event_id=str(uuid.uuid4()),
            session_id=session_id,
            timestamp=timestamp,
            event_type=EventType.THINKING,
            content=thinking_content,
            raw_data={
                **rate_limit_data,
                "synthetic": True,
                "source": "codex_surrogate",
                "call_id": call_id,
            },
        )
    )

    if unified_tool in ("Read", "Glob", "Grep") and file_path:
        events.append(
            UnifiedEvent(
                event_id=str(uuid.uuid4()),
                session_id=session_id,
                timestamp=timestamp,
                event_type=EventType.FILE_READ,
                content=f"Read: {Path(file_path).name}",
                file_path=file_path,
            )
        )
    elif unified_tool in ("Write", "Edit") and file_path:
        events.append(
            UnifiedEvent(
                event_id=str(uuid.uuid4()),
                session_id=session_id,
                timestamp=timestamp,
                event_type=EventType.FILE_MODIFIED,
                content=f"Modified: {Path(file_path).name}",
                file_path=file_path,
            )
        )

    return events
