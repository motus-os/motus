# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Opt-in telemetry collector (stub).

Phase 0: provide a stable interface without enabling egress by default.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class TelemetryEvent:
    name: str
    fields: Dict[str, Any]


class TelemetryCollector:
    def __init__(self, *, enabled: bool = False) -> None:
        self.enabled = enabled

    def emit(self, event: TelemetryEvent) -> None:
        # Phase 0: no-op unless explicitly enabled, and no external transport.
        if not self.enabled:
            return
        # Intentionally left as a stub: later phases can add pluggable exporters.
        return

