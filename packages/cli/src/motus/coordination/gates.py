# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from motus.coordination.schemas import CRStateRecord, GateResult


@dataclass(frozen=True, slots=True)
class GateFailure:
    gate_name: str
    details: str


TRANSITION_GATES: dict[tuple[str, str], tuple[str, ...]] = {
    ("QUEUED", "IN_PROGRESS"): ("definition_of_ready",),
    ("IN_PROGRESS", "REVIEW"): ("implementation_complete",),
    ("REVIEW", "DONE"): ("definition_of_done", "completion_receipt"),
}


def required_gates(from_state: str, to_state: str) -> tuple[str, ...]:
    return TRANSITION_GATES.get((from_state, to_state), ())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def evaluate_gate(record: CRStateRecord, gate_name: str) -> GateResult:
    status = record.gate_status.get(gate_name)
    if status is None:
        return GateResult(
            gate_name=gate_name,
            passed=False,
            details="gate has not been checked",
            checked_at=_utcnow(),
        )

    if status.passed:
        return GateResult(
            gate_name=gate_name,
            passed=True,
            details=None,
            checked_at=status.checked_at or _utcnow(),
        )

    return GateResult(
        gate_name=gate_name,
        passed=False,
        details="gate marked failed",
        checked_at=status.checked_at or _utcnow(),
    )


def evaluate_required_gates(record: CRStateRecord, gate_names: Iterable[str]) -> list[GateResult]:
    return [evaluate_gate(record, name) for name in gate_names]
