# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Motus Protocols - public re-exports.

Builders produce these data structures and surfaces consume them. Keep imports
stable (`from motus.protocols import UnifiedSession`, etc) by re-exporting
from the split implementation modules.
"""

from __future__ import annotations

from .protocols_builder import SessionBuilder
from .protocols_enums import EventType, FileOperation, RiskLevel, SessionStatus, Source, ToolStatus
from .protocols_models import (
    DEFAULT_THRESHOLDS,
    RawSession,
    SessionHealth,
    StatusThresholds,
    TeleportBundle,
    UnifiedEvent,
    UnifiedSession,
)
from .protocols_utils import compute_health, compute_status

__all__ = [
    "DEFAULT_THRESHOLDS",
    "EventType",
    "FileOperation",
    "RawSession",
    "RiskLevel",
    "SessionBuilder",
    "SessionHealth",
    "SessionStatus",
    "Source",
    "StatusThresholds",
    "TeleportBundle",
    "ToolStatus",
    "UnifiedEvent",
    "UnifiedSession",
    "compute_health",
    "compute_status",
]
