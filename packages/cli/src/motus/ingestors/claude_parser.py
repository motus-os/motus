# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Claude JSONL parsing helpers."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from ..protocols import EventType, UnifiedEvent
from .claude_tools import build_base_raw_data, parse_result, parse_tool_block
from .common import parse_jsonl_line, parse_timestamp_field

MAX_FILE_SIZE = 50 * 1024 * 1024


def parse_events(builder, file_path: Path) -> List[UnifiedEvent]:
    events: List[UnifiedEvent] = []
    session_id = file_path.stem

    try:
        file_size = file_path.stat().st_size
        if file_size > MAX_FILE_SIZE:
            builder._logger.warning(
                "Skipping large Claude file",
                file_path=str(file_path),
                file_size=file_size,
            )
            return events
    except OSError:
        return events

    is_subagent = file_path.name.startswith("agent-")
    parent_event_id = file_path.stem.replace("agent-", "") if is_subagent else None
    agent_depth = 1 if is_subagent else 0

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            for line_num, line in enumerate(f, 1):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    events.extend(
                        parse_line_data(builder, data, session_id, parent_event_id, agent_depth)
                    )
                except json.JSONDecodeError as e:
                    builder._logger.debug(
                        "Invalid JSON in Claude file",
                        line_num=line_num,
                        file_path=str(file_path),
                        error_type=type(e).__name__,
                        error=str(e),
                    )
                    continue
    except OSError as e:
        builder._logger.error(
            "Error reading transcript",
            file_path=str(file_path),
            error_type=type(e).__name__,
            error=str(e),
        )

    return events


def parse_line(builder, raw_line: str, session_id: str) -> List[UnifiedEvent]:
    data = parse_jsonl_line(raw_line)
    if data is None:
        return []
    return parse_line_data(builder, data, session_id)


def parse_line_data(
    builder,
    data: Dict,
    session_id: str,
    parent_event_id: Optional[str] = None,
    agent_depth: int = 0,
) -> List[UnifiedEvent]:
    event_type = data.get("type", "")
    timestamp = parse_timestamp_field(data)

    if event_type == "assistant":
        return parse_assistant_message(
            builder, data, session_id, timestamp, parent_event_id, agent_depth
        )
    if event_type == "user":
        return parse_user_message(data, session_id, timestamp)
    if event_type == "result":
        return parse_result(data, session_id, timestamp)
    return []


def parse_assistant_message(
    builder,
    data: Dict,
    session_id: str,
    timestamp: datetime,
    parent_event_id: Optional[str] = None,
    agent_depth: int = 0,
) -> List[UnifiedEvent]:
    events: List[UnifiedEvent] = []
    message = data.get("message", {})
    content_blocks = message.get("content", [])
    model = message.get("model", data.get("model"))
    base_raw_data = build_base_raw_data(
        message, data, model, parent_event_id, agent_depth
    )

    for block in content_blocks:
        block_type = block.get("type")
        if block_type == "thinking":
            thinking_text = block.get("thinking", "")
            if thinking_text:
                thinking_event = builder._create_thinking_event(
                    content=thinking_text,
                    session_id=session_id,
                    timestamp=timestamp,
                    model=model,
                )
                thinking_event_dict = {
                    **thinking_event.__dict__,
                    "parent_event_id": parent_event_id,
                    "agent_depth": agent_depth,
                    "raw_data": {
                        **base_raw_data,
                        "block_type": "thinking",
                        **(thinking_event.raw_data or {}),
                    },
                }
                events.append(UnifiedEvent(**thinking_event_dict))
                events.extend(
                    builder._extract_decisions_from_text(
                        thinking_text, session_id, timestamp
                    )
                )
        elif block_type == "text":
            text = block.get("text", "")
            if text:
                events.append(
                    UnifiedEvent(
                        event_id=str(uuid.uuid4()),
                        session_id=session_id,
                        timestamp=timestamp,
                        event_type=EventType.RESPONSE,
                        content=text,
                        model=model,
                        parent_event_id=parent_event_id,
                        agent_depth=agent_depth,
                        raw_data={
                            **base_raw_data,
                            "block_type": "text",
                        },
                    )
                )
                events.extend(builder._extract_decisions_from_text(text, session_id, timestamp))
        elif block_type == "tool_use":
            events.extend(
                parse_tool_block(
                    builder,
                    block,
                    session_id,
                    timestamp,
                    base_raw_data,
                    parent_event_id,
                    agent_depth,
                    model,
                )
            )

    return events


def parse_user_message(data: Dict, session_id: str, timestamp: datetime) -> List[UnifiedEvent]:
    message = data.get("message", {})
    content = message.get("content", "")

    if isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif isinstance(block, str):
                text_parts.append(block)
        content = " ".join(text_parts)

    if content:
        return [
            UnifiedEvent(
                event_id=str(uuid.uuid4()),
                session_id=session_id,
                timestamp=timestamp,
                event_type=EventType.USER_MESSAGE,
                content=content,
            )
        ]
    return []
