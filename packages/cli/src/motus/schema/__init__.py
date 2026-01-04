# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Schema module - Pydantic models for event parsing and validation.

This module provides the single source of truth for event data structures
used throughout Motus. All parsers, UI components, and WebSocket
handlers must use these schemas.

Key Principles:
- Immutable after creation (frozen=True)
- Strict validation via Pydantic
- JSON serializable
- No optional fields without explicit defaults
"""

from motus.schema.events import (
    AgentSource,
    EventType,
    ParsedEvent,
    RiskLevel,
    SessionInfo,
)

__all__ = [
    "AgentSource",
    "EventType",
    "ParsedEvent",
    "RiskLevel",
    "SessionInfo",
]
