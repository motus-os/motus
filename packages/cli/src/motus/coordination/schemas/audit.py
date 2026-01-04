# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .common import _iso_z, _parse_iso_z

AUDIT_EVENT_SCHEMA = "motus.coordination.audit_event.v1"


@dataclass(frozen=True, slots=True)
class AuditEvent:
    schema: str
    event_id: str
    event_type: str
    timestamp: datetime
    agent_id: str
    session_id: str
    task_id: str | None
    correlation_id: str | None
    parent_event_id: str | None
    sequence_number: int
    payload: dict[str, Any]

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schema": self.schema,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": _iso_z(self.timestamp),
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "sequence_number": self.sequence_number,
            "payload": self.payload,
        }
        if self.task_id is not None:
            out["task_id"] = self.task_id
        if self.correlation_id is not None:
            out["correlation_id"] = self.correlation_id
        if self.parent_event_id is not None:
            out["parent_event_id"] = self.parent_event_id
        return out

    @staticmethod
    def from_json(payload: dict[str, Any]) -> "AuditEvent":
        return AuditEvent(
            schema=str(payload["schema"]),
            event_id=str(payload["event_id"]),
            event_type=str(payload["event_type"]),
            timestamp=_parse_iso_z(str(payload["timestamp"])),
            agent_id=str(payload["agent_id"]),
            session_id=str(payload["session_id"]),
            task_id=str(payload["task_id"]) if "task_id" in payload else None,
            correlation_id=(
                str(payload["correlation_id"]) if "correlation_id" in payload else None
            ),
            parent_event_id=(
                str(payload["parent_event_id"]) if "parent_event_id" in payload else None
            ),
            sequence_number=int(payload["sequence_number"]),
            payload=dict(payload.get("payload", {})),
        )
