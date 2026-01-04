# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..protocols import EventType, UnifiedEvent


def build_base_raw_data(message: Dict, data: Dict, model: Optional[str], parent_event_id: Optional[str], agent_depth: int) -> Dict:
    usage = message.get("usage", {})
    return {
        "message_id": message.get("id"),
        "model": model,
        "stop_reason": message.get("stop_reason"),
        "stop_sequence": message.get("stop_sequence"),
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "cache_creation_tokens": usage.get("cache_creation_input_tokens", 0),
        "cache_read_tokens": usage.get("cache_read_input_tokens", 0),
        "service_tier": usage.get("service_tier"),
        "cache_creation": usage.get("cache_creation", {}),
        "parent_uuid": data.get("parentUuid"),
        "uuid": data.get("uuid"),
        "request_id": data.get("requestId"),
        "parent_event_id": parent_event_id,
        "agent_depth": agent_depth,
        "is_sidechain": data.get("isSidechain", False),
        "git_branch": data.get("gitBranch"),
        "slug": data.get("slug"),
        "agent_id": data.get("agentId"),
        "cwd": data.get("cwd"),
        "version": data.get("version"),
        "user_type": data.get("userType"),
    }


def parse_tool_block(
    builder: Any,
    block: Dict,
    session_id: str,
    timestamp: datetime,
    base_raw_data: Dict,
    parent_event_id: Optional[str],
    agent_depth: int,
    model: Optional[str],
) -> List[UnifiedEvent]:
    events: List[UnifiedEvent] = []
    tool_name = block.get("name", "")
    tool_input = block.get("input", {})
    tool_use_id = block.get("id")

    if tool_name == "Task":
        agent_type = tool_input.get("subagent_type", "general")
        description = tool_input.get("description", "")
        prompt = tool_input.get("prompt", "")
        context_text = tool_input.get("context", "")
        agent_model = tool_input.get("model")

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
                parent_event_id=tool_use_id,
                agent_depth=agent_depth + 1,
                model=model,
                raw_data={
                    **base_raw_data,
                    "block_type": "tool_use",
                    "tool_use_id": tool_use_id,
                    "context": context_text,
                    "depth": agent_depth + 1,
                },
            )
        )
        return events

    tool_event = builder._create_tool_event(
        name=tool_name,
        input_data=tool_input,
        session_id=session_id,
        timestamp=timestamp,
        risk_level=builder._classify_risk(tool_name, tool_input).value,
    )
    tool_event_dict = {
        **tool_event.__dict__,
        "parent_event_id": parent_event_id,
        "agent_depth": agent_depth,
        "raw_data": {
            **base_raw_data,
            "block_type": "tool_use",
            "tool_use_id": tool_use_id,
            **(tool_event.raw_data or {}),
        },
    }
    events.append(UnifiedEvent(**tool_event_dict))
    events.extend(
        _track_tool_files(
            tool_name,
            tool_input,
            session_id,
            timestamp,
            parent_event_id,
            agent_depth,
        )
    )
    return events


def _track_tool_files(
    tool_name: str,
    tool_input: Dict,
    session_id: str,
    timestamp: datetime,
    parent_event_id: Optional[str],
    agent_depth: int,
) -> List[UnifiedEvent]:
    file_path = tool_input.get("file_path") or tool_input.get("path")
    if not file_path:
        return []

    if tool_name in ("Read", "Glob", "Grep"):
        return [
            UnifiedEvent(
                event_id=str(uuid.uuid4()),
                session_id=session_id,
                timestamp=timestamp,
                event_type=EventType.FILE_READ,
                content=f"Read: {Path(file_path).name}",
                file_path=file_path,
                parent_event_id=parent_event_id,
                agent_depth=agent_depth,
            )
        ]
    if tool_name in ("Write", "Edit"):
        return [
            UnifiedEvent(
                event_id=str(uuid.uuid4()),
                session_id=session_id,
                timestamp=timestamp,
                event_type=EventType.FILE_MODIFIED,
                content=f"Modified: {Path(file_path).name}",
                file_path=file_path,
                parent_event_id=parent_event_id,
                agent_depth=agent_depth,
            )
        ]
    return []


def parse_result(data: Dict, session_id: str, timestamp: datetime) -> List[UnifiedEvent]:
    events: List[UnifiedEvent] = []
    content = data.get("content", [])

    if isinstance(content, str):
        result_text = content
    elif isinstance(content, list):
        result_parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    result_parts.append(block.get("text", ""))
                else:
                    result_parts.append(str(block.get("content", block.get("text", ""))))
            elif isinstance(block, str):
                result_parts.append(block)
        result_text = "\n".join(filter(None, result_parts))
    else:
        result_text = str(content) if content else ""

    if result_text:
        tool_use_id = data.get("tool_use_id")
        events.append(
            UnifiedEvent(
                event_id=str(uuid.uuid4()),
                session_id=session_id,
                timestamp=timestamp,
                event_type=EventType.TOOL_RESULT,
                content=result_text,
                tool_output=result_text,
                tool_use_id=tool_use_id,
                raw_data={
                    "tool_use_id": tool_use_id,
                    "content_type": type(content).__name__,
                    "content_length": len(result_text),
                },
            )
        )

    return events
