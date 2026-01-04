# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Event-specific handlers for Motus Web UI parsing."""

import json
from typing import Optional

from motus.logging import get_logger
from motus.schema.events import EventType

logger = get_logger(__name__)


def parse_user_intent_from_line(line: str) -> Optional[str]:
    """Extract user intent from a JSONL line if it contains a user message."""
    try:
        data = json.loads(line)

        if data.get("type") == "user":
            message = data.get("message", {})
            content = message.get("content", [])
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    prompt = block.get("text", "").strip()
                    if prompt and len(prompt) > 5:
                        return prompt

        if data.get("type") == "event_msg":
            payload = data.get("payload", {})
            if payload.get("type") == "user_message" or payload.get("role") == "user":
                content = payload.get("content", "")
                if isinstance(content, list):
                    content = " ".join(
                        str(c.get("text", c)) for c in content if isinstance(c, dict)
                    )
                if content and len(content) > 5:
                    return content

    except (json.JSONDecodeError, TypeError, AttributeError):
        pass

    return None


def build_session_intents(events: list) -> dict:
    """Build intents and stats from session events."""
    intents = []
    user_messages = [e for e in events if e.event_type == EventType.USER_MESSAGE]
    for msg in user_messages:
        intents.append(
            {
                "prompt": msg.content or "",
                "timestamp": msg.timestamp.strftime("%H:%M:%S"),
                "completed": False,
            }
        )

    total_input_tokens = 0
    total_output_tokens = 0
    total_cache_read = 0
    models_used = set()
    files_read = set()
    files_modified = set()
    errors = 0

    for event in events:
        if event.model:
            models_used.add(event.model)

        if hasattr(event, "raw_data") and event.raw_data:
            raw = event.raw_data if isinstance(event.raw_data, dict) else {}
            usage = raw.get("usage", {})
            if usage:
                total_input_tokens += usage.get("input_tokens", 0)
                total_output_tokens += usage.get("output_tokens", 0)
                total_cache_read += usage.get("cache_read_input_tokens", 0)

        if event.event_type == EventType.TOOL_USE:
            if event.tool_name == "Read" and event.file_path:
                files_read.add(event.file_path)
            elif event.tool_name in ("Edit", "Write") and event.file_path:
                files_modified.add(event.file_path)

        if event.is_error or event.error_message:
            errors += 1

    cache_hit_rate = 0.0
    if total_input_tokens > 0:
        cache_hit_rate = (total_cache_read / total_input_tokens) * 100

    return {
        "intents": intents,
        "stats": {
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "cache_hit_rate": f"{cache_hit_rate:.1f}%",
            "models_used": list(models_used),
            "files_read": len(files_read),
            "files_modified": len(files_modified),
            "errors": errors,
        },
    }
