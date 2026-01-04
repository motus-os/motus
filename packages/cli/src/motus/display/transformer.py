# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""EventTransformer - transforms ParsedEvent to DisplayEvent."""

from typing import Optional

from motus.display.events import DisplayEvent, DisplayRiskLevel, DisplaySession
from motus.display.renderer import SafeRenderer
from motus.protocols import UnifiedSession
from motus.schema.events import EventType, ParsedEvent, RiskLevel


class EventTransformer:
    """Transforms ParsedEvent into DisplayEvent.

    This is the ONLY place where ParsedEvent → display conversion happens.
    """

    TOOL_ICONS = {
        "Read": "📖",
        "Write": "📝",
        "Edit": "✏️",
        "Bash": "💻",
        "Glob": "🔍",
        "Grep": "🔎",
        "Task": "🤖",
        "WebFetch": "🌐",
        "WebSearch": "🔎",
        "TodoWrite": "📋",
        "AskUserQuestion": "❓",
    }

    @classmethod
    def transform(cls, event: ParsedEvent) -> DisplayEvent:
        """Transform ParsedEvent to DisplayEvent."""
        from dataclasses import replace

        r = SafeRenderer
        short_id = event.session_id[:8] if event.session_id else ""
        time_str = event.timestamp.strftime("%H:%M:%S") if event.timestamp else ""
        risk = cls._map_risk(event.risk_level)

        # Extract hierarchy fields from raw_data
        depth = 0
        parent_event_id = None
        if event.raw_data and isinstance(event.raw_data, dict):
            raw_depth = event.raw_data.get("depth", 0) or event.raw_data.get("agent_depth", 0) or 0
            # Ensure depth is an integer (handles MagicMock in tests)
            depth = int(raw_depth) if isinstance(raw_depth, (int, float)) else 0
            parent_event_id = event.raw_data.get("parent_event_id") or event.raw_data.get(
                "parent_uuid"
            )

        # Transform based on type
        if event.event_type == EventType.THINKING:
            result = cls._transform_thinking(event, short_id, time_str, risk, r)
        elif event.event_type == EventType.TOOL_USE:
            result = cls._transform_tool(event, short_id, time_str, risk, r)
        elif event.event_type == EventType.TOOL_RESULT:
            result = cls._transform_tool_result(event, short_id, time_str, risk, r)
        elif event.event_type == EventType.AGENT_SPAWN:
            result = cls._transform_spawn(event, short_id, time_str, risk, r)
        else:
            result = cls._transform_generic(event, short_id, time_str, risk, r)

        # Apply hierarchy fields to the result (DisplayEvent is frozen, so recreate)
        # Only override if we extracted non-zero depth or parent_event_id
        if depth > 0 or parent_event_id:
            result = replace(
                result, subagent_depth=depth, parent_event_id=parent_event_id, is_subagent=depth > 0
            )

        return result

    @classmethod
    def _map_risk(cls, risk: Optional[RiskLevel]) -> DisplayRiskLevel:
        if not risk:
            return DisplayRiskLevel.NONE
        mapping = {
            RiskLevel.SAFE: DisplayRiskLevel.LOW,
            RiskLevel.MEDIUM: DisplayRiskLevel.MEDIUM,
            RiskLevel.HIGH: DisplayRiskLevel.HIGH,
            RiskLevel.CRITICAL: DisplayRiskLevel.CRITICAL,
        }
        return mapping.get(risk, DisplayRiskLevel.NONE)

    @classmethod
    def _transform_thinking(cls, event, short_id, time_str, risk, r) -> DisplayEvent:
        raw_content = event.content or ""
        # Show 200 chars for preview (expandable content uses full_content)
        preview_content = r.content(raw_content, 200)
        full_content = r.escape(raw_content) if len(raw_content) > 200 else None
        return DisplayEvent(
            event_id=event.event_id or "",
            session_id=event.session_id,
            short_session_id=short_id,
            timestamp_display=time_str,
            event_type="thinking",
            risk_level=risk,
            icon="💭",
            title="Thinking",
            details=[preview_content] if preview_content else [],
            full_content=full_content,
        )

    @classmethod
    def _transform_tool(cls, event, short_id, time_str, risk, r) -> DisplayEvent:
        tool_name = event.tool_name or "Unknown"
        icon = cls.TOOL_ICONS.get(tool_name, "🔧")
        details = cls._get_tool_details(tool_name, event.tool_input or {}, r)
        file_path = None
        if event.tool_input and isinstance(event.tool_input, dict):
            fp = event.tool_input.get("file_path")
            if fp:
                file_path = r.file_path(fp)
        return DisplayEvent(
            event_id=event.event_id or "",
            session_id=event.session_id,
            short_session_id=short_id,
            timestamp_display=time_str,
            event_type="tool_use",
            risk_level=risk,
            icon=icon,
            title=tool_name,
            details=details,
            tool_name=tool_name,
            file_path=file_path,
            raw_data={"tool_use_id": event.tool_use_id} if event.tool_use_id else {},
        )

    @classmethod
    def _transform_tool_result(cls, event, short_id, time_str, risk, r) -> DisplayEvent:
        """Transform tool result event for display."""
        content = event.content or event.tool_output or ""
        tool_use_id = event.tool_use_id or (
            event.raw_data.get("tool_use_id") if event.raw_data else None
        )

        # Truncate preview but keep full content accessible
        preview = content[:500] if len(content) > 500 else content
        preview = r.content(preview, 500)  # Apply safe rendering

        details = [f"Length: {len(content)} chars"]
        if tool_use_id:
            details.append(f"Tool ID: {tool_use_id[:20]}...")

        return DisplayEvent(
            event_id=event.event_id or "",
            session_id=event.session_id,
            short_session_id=short_id,
            timestamp_display=time_str,
            event_type="tool_result",
            risk_level=risk,
            icon="📤",
            title="Result",
            details=details,
            content=preview,
            raw_data={
                "full_content": r.escape(content),  # Escape to prevent Rich markup errors
                "tool_use_id": tool_use_id,
            },
        )

    @classmethod
    def _get_tool_details(cls, tool_name: str, tool_input: dict, r) -> list:
        details = []
        fp = tool_input.get("file_path", "")
        if tool_name == "Read":
            details.append(r.file_path(fp))
        elif tool_name == "Write":
            details.append(f"Creating: {r.file_path(fp)}")
        elif tool_name == "Edit":
            details.append(f"Editing: {r.file_path(fp)}")
        elif tool_name == "Bash":
            desc = tool_input.get("description", "")
            if desc:
                details.append(r.content(desc, 60))
            details.append(r.command(tool_input.get("command", "")))
        elif tool_name in ("Glob", "Grep"):
            details.append(r.escape(tool_input.get("pattern", "")))
            path = tool_input.get("path", "")
            if path:
                details.append(f"in {r.file_path(path)}")
        elif tool_name == "Task":
            details.append(r.content(tool_input.get("description", ""), 100))
        return [d for d in details if d]

    @classmethod
    def _transform_spawn(cls, event, short_id, time_str, risk, r) -> DisplayEvent:
        raw = event.raw_data or {}
        details = []
        if model := r.escape(raw.get("model", "unknown")):
            details.append(f"Model: {model}")

        # Description
        raw_desc = raw.get("description", "")
        if raw_desc:
            desc_preview = r.content(raw_desc, 100)
            details.append(desc_preview)

        # Prompt with preview
        raw_prompt = raw.get("prompt", "")
        if raw_prompt:
            prompt_preview = r.content(raw_prompt, 150)
            details.append(f"Prompt: {prompt_preview}")

        # Store full prompt for expansion if it's long
        full_prompt = None
        if len(raw_prompt) > 150:
            full_prompt = r.escape(raw_prompt)

        return DisplayEvent(
            event_id=event.event_id or "",
            session_id=event.session_id,
            short_session_id=short_id,
            timestamp_display=time_str,
            event_type="agent_spawn",
            risk_level=risk,
            icon="🤖",
            title="Agent Spawn",
            details=details,
            is_subagent=True,
            full_content=full_prompt,
        )

    @classmethod
    def _transform_generic(cls, event, short_id, time_str, risk, r) -> DisplayEvent:
        return DisplayEvent(
            event_id=event.event_id or "",
            session_id=event.session_id,
            short_session_id=short_id,
            timestamp_display=time_str,
            event_type=event.event_type.value if event.event_type else "unknown",
            risk_level=risk,
            icon="📌",
            title=event.event_type.value if event.event_type else "Event",
            details=[],
        )


class SessionTransformer:
    """Transforms UnifiedSession into DisplaySession."""

    SOURCE_ICONS = {"claude": "🔵", "codex": "🟢", "gemini": "🟡"}
    STATUS_ICONS = {"active": "●", "idle": "○", "crashed": "✕", "orphaned": "?"}

    @classmethod
    def _format_time_ago(cls, seconds: float) -> str:
        """Format seconds into human-readable time ago string."""
        if seconds < 60:
            return "now"
        elif seconds < 3600:
            mins = int(seconds / 60)
            return f"{mins}m"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours}h"
        else:
            days = int(seconds / 86400)
            return f"{days}d"

    @classmethod
    def transform(cls, session: UnifiedSession) -> DisplaySession:
        r = SafeRenderer
        source = session.source.value if session.source else "unknown"
        status = session.status.value if session.status else "unknown"
        time_ago = cls._format_time_ago(session.age_seconds)
        return DisplaySession(
            session_id=session.session_id,
            short_id=session.session_id[:8],
            source=source,
            source_icon=cls.SOURCE_ICONS.get(source, "⚪"),
            status=status,
            status_icon=cls.STATUS_ICONS.get(status, "?"),
            project_path=r.file_path(session.project_path or "", 50),
            project_name=r.escape((session.project_path or "").split("/")[-1]),
            event_count=session.event_count or 0,
            health_score=session.health_score if hasattr(session, "health_score") else 100,
            time_ago=time_ago,
        )
