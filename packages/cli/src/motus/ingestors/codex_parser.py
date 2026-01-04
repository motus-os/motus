# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Codex JSONL parsing helpers."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List

from ..protocols import EventType, UnifiedEvent
from .codex_tools import parse_function_call
from .common import parse_timestamp_field


class CodexEventParser:
    """Parse Codex JSONL payloads into UnifiedEvent records."""

    def __init__(
        self,
        *,
        logger,
        create_tool_event,
        extract_decisions_from_text,
    ) -> None:
        self._logger = logger
        self._create_tool_event = create_tool_event
        self._extract_decisions_from_text = extract_decisions_from_text

    def parse_line_data(self, data: Dict[str, Any], session_id: str) -> List[UnifiedEvent]:
        """Parse a single JSONL line into events."""
        events: List[UnifiedEvent] = []
        event_type = data.get("type", "")
        timestamp = parse_timestamp_field(data)
        payload = data.get("payload", {})

        if event_type == "session_meta":
            cli_version = payload.get("cli_version")
            originator = payload.get("originator")
            model_provider = payload.get("model_provider")
            instructions = payload.get("instructions")
            source = payload.get("source")
            session_cwd = payload.get("cwd")
            session_id_from_meta = payload.get("id")

            events.append(
                UnifiedEvent(
                    event_id=str(uuid.uuid4()),
                    session_id=session_id,
                    timestamp=timestamp,
                    event_type=EventType.SESSION_START,
                    content=f"Codex session started: {originator} v{cli_version}",
                    raw_data={
                        "cli_version": cli_version,
                        "originator": originator,
                        "model_provider": model_provider,
                        "instructions": instructions,
                        "source": source,
                        "cwd": session_cwd,
                        "session_id_from_meta": session_id_from_meta,
                    },
                )
            )
            return events

        if event_type == "response_item":
            events.extend(self._parse_response_item(payload, session_id, timestamp))
        elif event_type == "event_msg":
            events.extend(self._parse_event_msg(payload, session_id, timestamp))

        return events

    def _parse_response_item(
        self, payload: Dict[str, Any], session_id: str, timestamp: datetime
    ) -> List[UnifiedEvent]:
        """Parse a response_item event (tool calls, text output)."""
        events: List[UnifiedEvent] = []
        item_type = payload.get("type")

        rate_limits = payload.get("rate_limits")
        rate_limit_data = {}
        if rate_limits:
            rate_limit_data = {
                "rate_limits_primary": rate_limits.get("primary", {}),
                "rate_limits_secondary": rate_limits.get("secondary", {}),
            }

        if item_type == "function_call":
            events.extend(
                parse_function_call(
                    payload,
                    session_id,
                    timestamp,
                    create_tool_event=self._create_tool_event,
                    rate_limit_data=rate_limit_data,
                )
            )

        elif item_type == "function_call_output":
            output = payload.get("output", "")
            call_id = payload.get("call_id", "")

            if isinstance(output, str):
                try:
                    parsed = json.loads(output)
                    if isinstance(parsed, dict):
                        output = parsed.get("output", parsed.get("result", str(parsed)))
                    elif isinstance(parsed, str):
                        output = parsed
                except json.JSONDecodeError:
                    pass

            if output:
                events.append(
                    UnifiedEvent(
                        event_id=str(uuid.uuid4()),
                        session_id=session_id,
                        timestamp=timestamp,
                        event_type=EventType.TOOL_RESULT,
                        content=str(output),
                        tool_output=str(output),
                        tool_use_id=call_id,
                        raw_data={
                            "call_id": call_id,
                            "content_length": len(str(output)),
                        },
                    )
                )

        elif item_type == "message":
            content = payload.get("content", [])
            text = ""
            if isinstance(content, list):
                text = "".join(
                    item.get("text", "")
                    for item in content
                    if isinstance(item, dict) and item.get("type") == "text"
                )
            elif isinstance(content, str):
                text = content

            if text:
                events.append(
                    UnifiedEvent(
                        event_id=str(uuid.uuid4()),
                        session_id=session_id,
                        timestamp=timestamp,
                        event_type=EventType.RESPONSE,
                        content=text,
                        raw_data=rate_limit_data,
                    )
                )

                events.extend(
                    self._extract_decisions_from_text(text, session_id, timestamp)
                )

        return events

    def _parse_event_msg(
        self, payload: Dict[str, Any], session_id: str, timestamp: datetime
    ) -> List[UnifiedEvent]:
        """Parse an event_msg (user input, system events)."""
        msg_type = payload.get("type")

        if msg_type == "user_message" or payload.get("role") == "user":
            content = payload.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    str(c.get("text", c)) for c in content if isinstance(c, dict)
                )

            if content:
                return [
                    UnifiedEvent(
                        event_id=str(uuid.uuid4()),
                        session_id=session_id,
                        timestamp=timestamp,
                        event_type=EventType.USER_MESSAGE,
                        content=str(content),
                    )
                ]

        return []
