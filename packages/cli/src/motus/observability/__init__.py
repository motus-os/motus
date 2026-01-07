# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Observability utilities (audit + telemetry)."""

from __future__ import annotations

from typing import Any

__all__ = ["ActivityLedger", "AuditLogger", "TelemetryCollector", "Role", "get_agent_role"]


def __getattr__(name: str) -> Any:
    if name == "ActivityLedger":
        from .activity import ActivityLedger

        return ActivityLedger
    if name == "AuditLogger":
        from .audit import AuditLogger

        return AuditLogger
    if name == "TelemetryCollector":
        from .telemetry import TelemetryCollector

        return TelemetryCollector
    if name == "Role":
        from .roles import Role

        return Role
    if name == "get_agent_role":
        from .roles import get_agent_role

        return get_agent_role
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
