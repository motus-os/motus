# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Extractors shared across builder implementations.

These helpers are used by multiple transcript ingestors (Claude/Codex/Gemini) to
avoid duplicated parsing logic.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, TypeVar

from .common import iter_jsonl_dicts, load_json_file, parse_timestamp_field

T = TypeVar("T")


def extract_claude_thinking(
    file_path: Path,
    *,
    session_id: str,
    create_thinking_event: Callable[..., T],
    logger_obj=None,
) -> List[T]:
    """Extract thinking blocks from Claude JSONL transcripts."""
    events: List[T] = []
    for data in iter_jsonl_dicts(file_path, logger_obj=logger_obj):
        if data.get("type") != "assistant":
            continue
        message = data.get("message", {})
        timestamp = parse_timestamp_field(data)
        model = message.get("model", data.get("model"))
        for block in message.get("content", []):
            if block.get("type") == "thinking":
                thinking_text = block.get("thinking", "")
                if thinking_text:
                    events.append(
                        create_thinking_event(
                            content=thinking_text,
                            session_id=session_id,
                            timestamp=timestamp,
                            model=model,
                        )
                    )
    return events


def extract_claude_decisions(
    file_path: Path,
    *,
    session_id: str,
    extract_decisions_from_text: Callable[[str, str, datetime], List[T]],
    logger_obj=None,
) -> List[T]:
    """Extract decisions from Claude thinking/text blocks."""
    events: List[T] = []
    for data in iter_jsonl_dicts(file_path, logger_obj=logger_obj):
        if data.get("type") != "assistant":
            continue
        message = data.get("message", {})
        timestamp = parse_timestamp_field(data)
        for block in message.get("content", []):
            text = ""
            if block.get("type") == "thinking":
                text = block.get("thinking", "")
            elif block.get("type") == "text":
                text = block.get("text", "")
            if text:
                events.extend(extract_decisions_from_text(text, session_id, timestamp))
    return events


def extract_codex_thinking(
    file_path: Path,
    *,
    session_id: str,
    create_thinking_event: Callable[..., T],
    map_tool: Callable[[str], str],
    build_surrogate: Callable[[str, Dict[str, Any]], str],
    logger_obj=None,
) -> List[T]:
    """Extract synthetic thinking surrogates from Codex JSONL tool calls."""
    events: List[T] = []
    for data in iter_jsonl_dicts(file_path, logger_obj=logger_obj):
        if data.get("type") != "response_item":
            continue
        payload = data.get("payload", {})
        if payload.get("type") != "function_call":
            continue

        timestamp = parse_timestamp_field(data)
        tool_name = payload.get("name", "")
        arguments: Any = payload.get("arguments", {})

        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {}

        unified_tool = map_tool(tool_name)
        thinking_content = build_surrogate(
            unified_tool, arguments if isinstance(arguments, dict) else {}
        )
        events.append(
            create_thinking_event(
                content=thinking_content,
                session_id=session_id,
                timestamp=timestamp,
            )
        )

    return events


def extract_codex_decisions(
    file_path: Path,
    *,
    session_id: str,
    extract_decisions_from_text: Callable[[str, str, datetime], List[T]],
    logger_obj=None,
) -> List[T]:
    """Extract decisions from Codex JSONL response messages."""
    events: List[T] = []
    for data in iter_jsonl_dicts(file_path, logger_obj=logger_obj):
        if data.get("type") != "response_item":
            continue
        payload = data.get("payload", {})
        if payload.get("type") != "message":
            continue

        timestamp = parse_timestamp_field(data)
        content: Any = payload.get("content", [])

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
            events.extend(extract_decisions_from_text(text, session_id, timestamp))

    return events


def extract_gemini_thinking(
    file_path: Path,
    *,
    session_id: str,
    create_thinking_event: Callable[..., T],
    logger_obj=None,
) -> List[T]:
    """Extract thinking/thoughts from Gemini JSON transcripts."""
    events: List[T] = []
    data = load_json_file(file_path, logger_obj=logger_obj, error_label="Error reading Gemini file")
    if not data:
        return events

    for msg in data.get("messages", []):
        if msg.get("type") != "gemini":
            continue

        model = msg.get("model", "")
        timestamp = parse_timestamp_field(msg)

        for thought in msg.get("thoughts", []):
            thought_time = parse_timestamp_field(thought, fallback=timestamp)
            subject = thought.get("subject", "")
            description = thought.get("description", "")
            thinking_content = f"{subject}: {description}" if subject else description
            if thinking_content:
                events.append(
                    create_thinking_event(
                        content=thinking_content,
                        session_id=session_id,
                        timestamp=thought_time,
                        model=model,
                    )
                )

    return events


def extract_gemini_decisions(
    file_path: Path,
    *,
    session_id: str,
    extract_decisions_from_text: Callable[[str, str, datetime], List[T]],
    logger_obj=None,
) -> List[T]:
    """Extract decisions from Gemini thoughts and response content."""
    events: List[T] = []
    data = load_json_file(file_path, logger_obj=logger_obj, error_label="Error reading Gemini file")
    if not data:
        return events

    for msg in data.get("messages", []):
        if msg.get("type") != "gemini":
            continue

        timestamp = parse_timestamp_field(msg)

        for thought in msg.get("thoughts", []):
            thought_time = parse_timestamp_field(thought, fallback=timestamp)
            subject = thought.get("subject", "")
            description = thought.get("description", "")
            text = f"{subject}: {description}" if subject else description
            if text:
                events.extend(extract_decisions_from_text(text, session_id, thought_time))

        content = msg.get("content", "")
        if content:
            events.extend(extract_decisions_from_text(content, session_id, timestamp))

    return events
