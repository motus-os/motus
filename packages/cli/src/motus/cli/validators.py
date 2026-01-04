# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Input validation and session ID parsing for CLI."""

import json
from pathlib import Path

try:
    from ..logging import get_logger

    logger = get_logger(__name__)
except ImportError:
    import logging

    logger = logging.getLogger(__name__)  # type: ignore[assignment]


def parse_content_block(block: dict):
    """Parse a content block from a transcript line.

    DEPRECATED: Will be removed in v0.5.0. Use orchestrator.get_events() instead.

    This function is kept for backward compatibility with existing tests.
    New code should use orchestrator.get_events() with unified_event_to_legacy().
    """
    from datetime import datetime

    from ..commands.utils import assess_risk
    from .output import TaskEvent, ThinkingEvent, ToolEvent

    block_type = block.get("type")

    if block_type == "thinking":
        thinking = block.get("thinking", "")
        if thinking:
            return ThinkingEvent(content=thinking, timestamp=datetime.now())

    elif block_type == "tool_use":
        name = block.get("name", "Unknown")
        input_data = block.get("input", {})

        if name == "Task":
            return TaskEvent(
                description=input_data.get("description", ""),
                prompt=input_data.get("prompt", ""),
                subagent_type=input_data.get("subagent_type", "unknown"),
                model=input_data.get("model"),
                timestamp=datetime.now(),
            )

        risk = assess_risk(name, input_data)
        return ToolEvent(name=name, input=input_data, timestamp=datetime.now(), risk_level=risk)

    return None


def parse_transcript_line(line: str) -> list:
    """Parse a JSONL line from Claude transcript.

    DEPRECATED: Will be removed in v0.5.0. Use orchestrator.get_events() instead.

    This function is kept for backward compatibility with existing tests.
    New code should use orchestrator.get_events() with unified_event_to_legacy().
    """
    events: list[object] = []

    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        return events

    if data.get("type") != "assistant":
        return events

    message = data.get("message", {})
    content = message.get("content", [])

    if isinstance(content, str):
        return events

    for block in content:
        event = parse_content_block(block)
        if event:
            events.append(event)

    return events


def extract_decisions(file_path: Path, source: str = "claude") -> list[str]:
    """Extract decision patterns from thinking blocks.

    Works with Claude, Codex, and Gemini transcript formats.
    """
    decisions = []
    decision_patterns = [
        "I'll use",
        "I decided",
        "I'm going to",
        "Let me",
        "I should",
        "The best approach",
        "I chose",
        "Instead of",
        "Rather than",
    ]

    def extract_from_thinking(thinking: str) -> None:
        """Extract decisions from a thinking text block."""
        for pattern in decision_patterns:
            if pattern.lower() in thinking.lower():
                sentences = thinking.replace("\n", " ").split(". ")
                for sentence in sentences:
                    if pattern.lower() in sentence.lower() and len(sentence) > 20:
                        clean = sentence.strip()[:150]
                        if clean and clean not in decisions:
                            decisions.append(clean)
                        break

    try:
        # Gemini uses JSON (not JSONL), so handle separately
        if source == "gemini":
            with open(file_path, "r") as f:
                data = json.load(f)
                for msg in data.get("messages", []):
                    if msg.get("type") == "gemini":
                        # Gemini stores thoughts in a separate array
                        for thought in msg.get("thoughts", []):
                            description = thought.get("description", "")
                            if description:
                                extract_from_thinking(description)
            return decisions[:10]

        # JSONL format for Claude/Codex
        with open(file_path, "r") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)

                    # Claude format: type="assistant" with thinking blocks
                    if data.get("type") == "assistant":
                        message = data.get("message", {})
                        content = message.get("content", [])
                        if isinstance(content, list):
                            for block in content:
                                if block.get("type") == "thinking":
                                    thinking = block.get("thinking", "")
                                    extract_from_thinking(thinking)

                    # Codex format: type="response_item" with text content
                    elif data.get("type") == "response_item":
                        payload = data.get("payload", {})
                        item_type = payload.get("type")
                        # Codex thinking is in "message" type items
                        if item_type == "message":
                            content = payload.get("content", [])
                            for c in content if isinstance(content, list) else []:
                                if c.get("type") == "output_text":
                                    text = c.get("text", "")
                                    extract_from_thinking(text)

                except json.JSONDecodeError:
                    continue
    except OSError as e:
        logger.debug(
            f"Error reading session file: {e}",
        )
    except Exception as e:
        logger.warning(
            f"Unexpected error extracting decisions: {e}",
        )

    return decisions[:10]  # Limit to 10 most relevant
