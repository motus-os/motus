# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Parsing logic for Gemini transcripts."""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable, List

from ..logging import get_logger
from ..protocols import EventType, UnifiedEvent
from .gemini_tools import build_tool_events

logger = get_logger(__name__)
def _parse_timestamp(value: str, fallback: datetime) -> datetime:
    if value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, TypeError) as e:
            logger.debug(
                "Timestamp parse failed",
                error_type=type(e).__name__,
                error=str(e),
            )
    return fallback
def parse_gemini_events(
    file_path: Path,
    *,
    session_id: str,
    max_file_size: int,
    create_thinking_event: Callable[..., UnifiedEvent],
    extract_decisions_from_text: Callable[..., List[UnifiedEvent]],
    create_tool_event: Callable[..., UnifiedEvent],
    assess_risk: Callable[[str, dict], object],
    logger_obj,
) -> List[UnifiedEvent]:
    events: List[UnifiedEvent] = []
    try:
        file_size = file_path.stat().st_size
        if file_size > max_file_size:
            logger_obj.warning(
                "Skipping large Gemini file",
                file_path=str(file_path),
                file_size=file_size,
            )
            return events
    except OSError:
        return events

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger_obj.error(
            "Error reading Gemini file",
            file_path=str(file_path),
            error_type=type(e).__name__,
            error=str(e),
        )
        return events

    session_id_from_data = data.get("sessionId")
    project_hash = data.get("projectHash")
    start_time_str = data.get("startTime")
    last_updated_str = data.get("lastUpdated")

    messages = data.get("messages", [])
    for msg in messages:
        msg_type = msg.get("type", "")
        content = msg.get("content", "")
        timestamp = _parse_timestamp(msg.get("timestamp", ""), datetime.now())
        msg_id = msg.get("id")

        if msg_type == "user":
            events.append(
                UnifiedEvent(
                    event_id=str(uuid.uuid4()),
                    session_id=session_id,
                    timestamp=timestamp,
                    event_type=EventType.USER_MESSAGE,
                    content=content if content else "",
                )
            )
            continue

        if msg_type != "gemini":
            continue

        model = msg.get("model", "")
        tokens = msg.get("tokens", {})
        finish_reason = msg.get("finishReason", "")
        safety_ratings = msg.get("safetyRatings", [])

        token_breakdown = {
            "input": tokens.get("input", 0) if tokens else 0,
            "output": tokens.get("output", 0) if tokens else 0,
            "cached": tokens.get("cached", 0) if tokens else 0,
            "thoughts": tokens.get("thoughts", 0) if tokens else 0,
            "tool": tokens.get("tool", 0) if tokens else 0,
            "total": tokens.get("total", 0) if tokens else 0,
        }

        base_raw_data = {
            "message_id": msg_id,
            "session_id_from_data": session_id_from_data,
            "project_hash": project_hash,
            "start_time": start_time_str,
            "last_updated": last_updated_str,
            "model": model,
            "token_breakdown": token_breakdown,
            "finish_reason": finish_reason,
            "safety_ratings": safety_ratings,
        }

        error = msg.get("error")
        if error:
            error_msg = error.get("message", str(error)) if isinstance(error, dict) else str(error)
            events.append(
                UnifiedEvent(
                    event_id=str(uuid.uuid4()),
                    session_id=session_id,
                    timestamp=timestamp,
                    event_type=EventType.ERROR,
                    content=f"API Error: {error_msg}",
                    model=model,
                    raw_data={**base_raw_data, "error": error},
                )
            )

        if finish_reason == "SAFETY":
            events.append(
                UnifiedEvent(
                    event_id=str(uuid.uuid4()),
                    session_id=session_id,
                    timestamp=timestamp,
                    event_type=EventType.ERROR,
                    content="Response blocked by safety filter",
                    model=model,
                    raw_data=base_raw_data,
                )
            )

        for thought in msg.get("thoughts", []):
            thought_time = _parse_timestamp(thought.get("timestamp", ""), timestamp)
            subject = thought.get("subject", "")
            description = thought.get("description", "")
            thinking_content = f"{subject}: {description}" if subject else description

            if thinking_content:
                thinking_event = create_thinking_event(
                    content=thinking_content,
                    session_id=session_id,
                    timestamp=thought_time,
                    model=model,
                )
                thinking_event.raw_data = {
                    **base_raw_data,
                    "thought_subject": subject,
                    "thought_description": description,
                    **(thinking_event.raw_data or {}),
                }
                events.append(thinking_event)
                events.extend(
                    extract_decisions_from_text(thinking_content, session_id, thought_time)
                )

        tool_calls = msg.get("toolCalls", [])
        if tool_calls:
            events.extend(
                build_tool_events(
                    tool_calls,
                    session_id=session_id,
                    timestamp=timestamp,
                    model=model,
                    base_raw_data=base_raw_data,
                    create_tool_event=create_tool_event,
                    assess_risk=assess_risk,
                )
            )

        if content:
            events.append(
                UnifiedEvent(
                    event_id=str(uuid.uuid4()),
                    session_id=session_id,
                    timestamp=timestamp,
                    event_type=EventType.RESPONSE,
                    content=content,
                    model=model,
                    tokens_used=(
                        tokens.get("output", 0) + tokens.get("input", 0) if tokens else None
                    ),
                    raw_data=base_raw_data,
                )
            )
            events.extend(extract_decisions_from_text(content, session_id, timestamp))

    return events
