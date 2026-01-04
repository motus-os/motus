# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Shared helpers for builder base logic."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from ..commands.utils import redact_secrets
from ..protocols import EventType, RiskLevel, Source, ToolStatus, UnifiedEvent
from ..schema.events import AgentSource, ParsedEvent, unified_to_parsed

JsonDict = Dict[str, Any]

SOURCE_TO_AGENT_SOURCE = {
    Source.CLAUDE: AgentSource.CLAUDE,
    Source.CODEX: AgentSource.CODEX,
    Source.GEMINI: AgentSource.GEMINI,
}
DECISION_PATTERNS = [
    r"I(?:'ll| will) (?:use|implement|create|add|build|write|make|choose|go with)",
    r"I(?:'ve| have) decided to",
    r"I'm going to (?:use|implement|create|add|build|write|make|choose)",
    r"Let me (?:use|implement|create|add|build|write|make|choose)",
    r"I(?:'m| am) choosing",
    r"(?:Going|Opting) (?:to|with|for)",
    r"(?:Using|Implementing|Creating|Adding|Building|Writing|Making|Choosing)",
    r"The (?:best|right|better|optimal) (?:approach|solution|way|choice) (?:is|would be)",
]
DECISION_REGEX = re.compile("|".join(DECISION_PATTERNS), re.IGNORECASE)


def validate_events(
    events: list[UnifiedEvent], source_name: Source, logger_obj=None
) -> list[ParsedEvent]:
    """Convert UnifiedEvents to ParsedEvents with validation."""
    agent_source = SOURCE_TO_AGENT_SOURCE.get(source_name, AgentSource.UNKNOWN)
    validated: list[ParsedEvent] = []
    for event in events:
        parsed = unified_to_parsed(event, source=agent_source)
        if parsed is not None:
            validated.append(parsed)
        elif logger_obj is not None:
            logger_obj.warning(
                "Event validation failed",
                event_id=getattr(event, "event_id", "unknown"),
                event_type=getattr(event, "event_type", "unknown"),
            )
    return validated


def extract_decisions_from_text(
    text: str, session_id: str, timestamp: Optional[datetime] = None
) -> list[UnifiedEvent]:
    """Extract decision events from arbitrary text."""
    decisions = []
    timestamp = timestamp or datetime.now()
    if len(text) > 10240:
        text = text[:10240]
    sentences = re.split(r"[.!?]\s+", text)
    for sentence in sentences:
        if len(sentence) > 500:
            continue
        if DECISION_REGEX.search(sentence):
            decision_text = sentence.strip()
            if len(decision_text) > 20:
                decisions.append(
                    UnifiedEvent(
                        event_id=str(uuid.uuid4()),
                        session_id=session_id,
                        timestamp=timestamp,
                        event_type=EventType.DECISION,
                        content=decision_text,
                        decision_text=decision_text,
                    )
                )
    return decisions


def create_thinking_event(
    content: str,
    session_id: str,
    timestamp: Optional[datetime] = None,
    model: Optional[str] = None,
) -> UnifiedEvent:
    """Create a thinking event."""
    return UnifiedEvent(
        event_id=str(uuid.uuid4()),
        session_id=session_id,
        timestamp=timestamp or datetime.now(),
        event_type=EventType.THINKING,
        content=content,
        model=model,
    )


def redact_tool_input(input_data: dict[str, Any]) -> dict[str, Any]:
    """Redact secrets from tool input data."""
    redacted: dict[str, Any] = {}
    for key, value in input_data.items():
        if isinstance(value, str):
            redacted[key] = redact_secrets(value)
        elif isinstance(value, dict):
            redacted[key] = redact_tool_input(value)
        elif isinstance(value, list):
            redacted[key] = [
                redact_secrets(item) if isinstance(item, str) else item for item in value
            ]
        else:
            redacted[key] = value
    return redacted


def summarize_tool_input(name: str, input_data: dict) -> str:
    """Create a human-readable summary of tool input."""
    if name in ("Edit", "Write", "Read"):
        path = input_data.get("file_path") or input_data.get("path", "")
        return Path(path).name if path else "file"
    if name == "Bash":
        return input_data.get("command", "")
    if name in ("Glob", "Grep"):
        return input_data.get("pattern", "")
    if name == "WebFetch":
        return input_data.get("url", "")
    keys = list(input_data.keys())
    return ", ".join(keys) if keys else "..."


def create_tool_event(
    name: str,
    input_data: dict,
    session_id: str,
    timestamp: Optional[datetime] = None,
    output: Optional[str] = None,
    status: str = "success",
    risk_level=None,
    latency_ms: Optional[int] = None,
    logger_obj=None,
) -> UnifiedEvent:
    """Create a tool event."""
    final_risk_level = RiskLevel.SAFE
    if risk_level:
        if isinstance(risk_level, RiskLevel):
            final_risk_level = risk_level
        else:
            try:
                final_risk_level = RiskLevel(risk_level)
            except ValueError:
                if risk_level == "low":
                    final_risk_level = RiskLevel.SAFE
                elif logger_obj is not None:
                    logger_obj.warning(
                        f"Unrecognized risk level string '{risk_level}'. Defaulting to SAFE."
                    )
    redacted_input = redact_tool_input(input_data)
    return UnifiedEvent(
        event_id=str(uuid.uuid4()),
        session_id=session_id,
        timestamp=timestamp or datetime.now(),
        event_type=EventType.TOOL,
        content=f"{name}: {summarize_tool_input(name, redacted_input)}",
        tool_name=name,
        tool_input=redacted_input,
        tool_output=output,
        tool_status=ToolStatus(status) if status else None,
        risk_level=final_risk_level,
        tool_latency_ms=latency_ms,
    )


def classify_risk(tool_name: str, input_data: dict) -> RiskLevel:
    """Classify risk level for a tool call."""
    if tool_name == "Bash":
        cmd = input_data.get("command", "").lower()
        if any(
            danger in cmd
            for danger in [
                "rm -rf",
                "sudo",
                "chmod",
                "chown",
                "mkfs",
                "dd if=",
                "> /dev/",
                "curl | sh",
                "wget | sh",
            ]
        ):
            return RiskLevel.CRITICAL
        if any(
            risk in cmd for risk in ["rm ", "mv ", "cp ", "git push", "git reset", "npm publish"]
        ):
            return RiskLevel.HIGH
        return RiskLevel.MEDIUM
    if tool_name in ("Write", "Edit"):
        return RiskLevel.MEDIUM
    return RiskLevel.SAFE
