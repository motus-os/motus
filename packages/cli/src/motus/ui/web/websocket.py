# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Compatibility shim for WebSocket handler exports."""

from motus.display.renderer import SafeRenderer
from motus.display.transformer import EventTransformer
from motus.orchestrator import get_orchestrator
from motus.schema.events import EventType
from motus.ui.web.event_parser import (
    parse_backfill_events,
    parse_incremental_events,
    parse_session_history,
    parse_session_intents,
    parse_user_intent_from_line,
)
from motus.ui.web.formatters import format_event_for_client
from motus.ui.web.websocket_handler import WebSocketHandler

__all__ = [
    "EventTransformer",
    "EventType",
    "SafeRenderer",
    "WebSocketHandler",
    "format_event_for_client",
    "get_orchestrator",
    "parse_backfill_events",
    "parse_incremental_events",
    "parse_session_history",
    "parse_session_intents",
    "parse_user_intent_from_line",
]
