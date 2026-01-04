# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""
Event formatting for Motus Web UI.

Handles conversion of ParsedEvent objects to web-friendly JSON format.
"""

from motus.display.transformer import EventTransformer


def format_event_for_client(
    event, session_id: str, project_path: str, agent_depth: int = 0, source: str = ""
) -> dict:
    """Format an event for sending to the client.

    Uses EventTransformer for centralized escaping and formatting.

    Args:
        event: ParsedEvent to format
        session_id: Session ID this event belongs to
        project_path: Project path for this session
        agent_depth: Nesting depth for agent spawns (default: 0)
        source: Source identifier (default: "")

    Returns:
        Dict ready for JSON serialization to web client
    """
    # Transform ParsedEvent to DisplayEvent (handles all escaping)
    display_event = EventTransformer.transform(event)

    # Convert DisplayEvent to web-specific format
    # DisplayEvent has pre-escaped fields, so we use them directly
    web_event = {
        "session_id": session_id,
        "timestamp": display_event.timestamp_display,
        "source": source,
        "agent_depth": agent_depth,
        "event_id": display_event.event_id,
    }

    # Map event type
    if display_event.event_type == "tool_result":
        # Tool result events
        web_event.update(
            {
                "event_type": "tool_result",
                "content": display_event.content,
                "tool_output": (
                    display_event.raw_data.get("full_content", "") if display_event.raw_data else ""
                ),
                "raw_data": display_event.raw_data,
            }
        )
    elif display_event.event_type == "thinking":
        # Join details into content (already escaped)
        content = " ".join(display_event.details) if display_event.details else ""
        web_event.update(
            {
                "event_type": "thinking",
                "content": content,
            }
        )
    elif display_event.event_type == "agent_spawn":
        # Extract spawn details
        description = ""
        prompt = ""
        model = ""
        for detail in display_event.details:
            if detail.startswith("Model: "):
                model = detail[7:]  # Already escaped
            elif detail.startswith("Prompt: "):
                prompt = detail[8:]  # Already escaped
            else:
                description = detail  # Already escaped

        # Get agent type from raw_data if available
        agent_type = getattr(event, "spawn_type", None) or "general"

        web_event.update(
            {
                "event_type": "spawn",
                "content": display_event.title if not description else description,
                "tool_name": "SPAWN",
                "agent_type": agent_type,
                "description": description,
                "model": model,
                "prompt": prompt,
            }
        )
    elif display_event.event_type == "tool_use":
        # Join details into content (already escaped)
        content = " ".join(display_event.details) if display_event.details else display_event.title
        web_event.update(
            {
                "event_type": "tool",
                "content": content,
                "tool_name": display_event.tool_name or "unknown",
                "risk_level": display_event.risk_level.value,
                "file_path": display_event.file_path or "",
            }
        )
    else:
        # Generic event
        content = " ".join(display_event.details) if display_event.details else display_event.title
        web_event.update(
            {
                "event_type": "unknown",
                "content": content,
            }
        )

    return web_event
