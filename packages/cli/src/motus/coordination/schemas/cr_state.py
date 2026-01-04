# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .common import _iso_z, _parse_iso_z

CR_STATE_RECORD_SCHEMA = "motus.coordination.cr_state.v1"


@dataclass(frozen=True, slots=True)
class StateHistoryEntry:
    state: str
    entered_at: datetime
    by: str

    def to_json(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "entered_at": _iso_z(self.entered_at),
            "by": self.by,
        }

    @staticmethod
    def from_json(payload: dict[str, Any]) -> "StateHistoryEntry":
        return StateHistoryEntry(
            state=str(payload["state"]),
            entered_at=_parse_iso_z(str(payload["entered_at"])),
            by=str(payload["by"]),
        )


@dataclass(frozen=True, slots=True)
class GateStatus:
    passed: bool
    checked_at: datetime | None

    def to_json(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "checked_at": _iso_z(self.checked_at) if self.checked_at else None,
        }

    @staticmethod
    def from_json(payload: dict[str, Any]) -> "GateStatus":
        checked_at_str = payload.get("checked_at")
        return GateStatus(
            passed=bool(payload["passed"]),
            checked_at=_parse_iso_z(str(checked_at_str)) if checked_at_str else None,
        )


@dataclass(frozen=True, slots=True)
class CRStateRecord:
    schema: str
    cr_id: str
    current_state: str
    assigned_to: str | None
    claim_id: str | None
    state_history: list[StateHistoryEntry]
    gate_status: dict[str, GateStatus]
    blocked_reason: str | None
    cancelled_reason: str | None

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schema": self.schema,
            "cr_id": self.cr_id,
            "current_state": self.current_state,
            "assigned_to": self.assigned_to,
            "claim_id": self.claim_id,
            "state_history": [entry.to_json() for entry in self.state_history],
            "gate_status": {k: v.to_json() for k, v in self.gate_status.items()},
            "blocked_reason": self.blocked_reason,
            "cancelled_reason": self.cancelled_reason,
        }
        return out

    @staticmethod
    def from_json(payload: dict[str, Any]) -> "CRStateRecord":
        state_history_payload = payload.get("state_history", [])
        gate_status_payload = payload.get("gate_status", {})
        return CRStateRecord(
            schema=str(payload["schema"]),
            cr_id=str(payload["cr_id"]),
            current_state=str(payload["current_state"]),
            assigned_to=str(payload["assigned_to"]) if payload.get("assigned_to") else None,
            claim_id=str(payload["claim_id"]) if payload.get("claim_id") else None,
            state_history=[StateHistoryEntry.from_json(e) for e in state_history_payload],
            gate_status={k: GateStatus.from_json(v) for k, v in gate_status_payload.items()},
            blocked_reason=(
                str(payload["blocked_reason"]) if payload.get("blocked_reason") else None
            ),
            cancelled_reason=(
                str(payload["cancelled_reason"]) if payload.get("cancelled_reason") else None
            ),
        )


@dataclass(frozen=True, slots=True)
class GateResult:
    gate_name: str
    passed: bool
    details: str | None
    checked_at: datetime

    def to_json(self) -> dict[str, Any]:
        return {
            "gate_name": self.gate_name,
            "passed": self.passed,
            "details": self.details,
            "checked_at": _iso_z(self.checked_at),
        }

    @staticmethod
    def from_json(payload: dict[str, Any]) -> "GateResult":
        return GateResult(
            gate_name=str(payload["gate_name"]),
            passed=bool(payload["passed"]),
            details=str(payload["details"]) if payload.get("details") else None,
            checked_at=_parse_iso_z(str(payload["checked_at"])),
        )
