# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from motus.atomic_io import atomic_write_json
from motus.coordination.audit import AuditLog
from motus.coordination.gates import evaluate_required_gates, required_gates
from motus.coordination.schemas import (
    CR_STATE_RECORD_SCHEMA,
    CRStateRecord,
    GateResult,
    GateStatus,
    StateHistoryEntry,
)


class CRStateMachineError(Exception):
    pass


class InvalidTransitionError(CRStateMachineError):
    def __init__(self, cr_id: str, from_state: str, to_state: str) -> None:
        super().__init__(f"invalid transition for {cr_id}: {from_state} -> {to_state}")
        self.cr_id = cr_id
        self.from_state = from_state
        self.to_state = to_state


class GateFailureError(CRStateMachineError):
    def __init__(self, cr_id: str, failures: list[GateResult]) -> None:
        details = ", ".join(
            f"{g.gate_name}={('PASS' if g.passed else 'FAIL')}" for g in failures
        )
        super().__init__(f"gate failure for {cr_id}: {details}")
        self.cr_id = cr_id
        self.failures = failures


class MissingReasonError(CRStateMachineError):
    def __init__(self, cr_id: str, to_state: str) -> None:
        super().__init__(f"missing required reason for {cr_id} -> {to_state}")
        self.cr_id = cr_id
        self.to_state = to_state


ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "QUEUED": {"IN_PROGRESS", "CANCELLED"},
    "IN_PROGRESS": {"REVIEW", "BLOCKED", "QUEUED"},
    "BLOCKED": {"IN_PROGRESS", "CANCELLED"},
    "REVIEW": {"DONE", "IN_PROGRESS"},
    "DONE": set(),
    "CANCELLED": set(),
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _safe_filename(cr_id: str) -> str:
    if "/" in cr_id or "\\" in cr_id:
        raise ValueError(f"invalid cr_id for filename: {cr_id!r}")
    return f"{cr_id}.json"


class CRStateMachine:
    def __init__(self, root_dir: str | Path) -> None:
        self._root = Path(root_dir)
        self._states_dir = self._root / "cr_state"
        self._index_path = self._states_dir / "INDEX.json"
        self._audit = AuditLog(self._root / "ledger")

    def _state_path(self, cr_id: str) -> Path:
        return self._states_dir / _safe_filename(cr_id)

    def _load_index(self) -> dict[str, list[str]]:
        if not self._index_path.exists():
            return {}
        try:
            return json.loads(self._index_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}

    def _write_index(self, index: dict[str, list[str]]) -> None:
        self._states_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self._index_path, index)

    def _index_remove(self, index: dict[str, list[str]], state: str, cr_id: str) -> None:
        items = index.get(state, [])
        if cr_id in items:
            index[state] = [x for x in items if x != cr_id]

    def _index_add(self, index: dict[str, list[str]], state: str, cr_id: str) -> None:
        items = index.get(state, [])
        if cr_id not in items:
            items.append(cr_id)
            items.sort()
        index[state] = items

    def register_cr(self, cr_id: str, *, assigned_to: str | None = None, claim_id: str | None = None) -> CRStateRecord:
        path = self._state_path(cr_id)
        if path.exists():
            return self.get_state(cr_id)

        now = _utcnow()
        record = CRStateRecord(
            schema=CR_STATE_RECORD_SCHEMA,
            cr_id=cr_id,
            current_state="QUEUED",
            assigned_to=assigned_to,
            claim_id=claim_id,
            state_history=[StateHistoryEntry(state="QUEUED", entered_at=now, by="system")],
            gate_status={},
            blocked_reason=None,
            cancelled_reason=None,
        )

        self._states_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(path, record.to_json())

        index = self._load_index()
        self._index_add(index, "QUEUED", cr_id)
        self._write_index(index)

        return record

    def get_state(self, cr_id: str) -> CRStateRecord:
        path = self._state_path(cr_id)
        payload = json.loads(path.read_text(encoding="utf-8"))
        return CRStateRecord.from_json(payload)

    def mark_gate_passed(self, cr_id: str, gate_name: str) -> CRStateRecord:
        record = self.get_state(cr_id)
        now = _utcnow()
        updated = replace(
            record,
            gate_status={
                **record.gate_status,
                gate_name: GateStatus(passed=True, checked_at=now),
            },
        )
        atomic_write_json(self._state_path(cr_id), updated.to_json())
        return updated

    def check_gate(self, cr_id: str, gate_name: str) -> GateResult:
        record = self.get_state(cr_id)
        return evaluate_required_gates(record, [gate_name])[0]

    def transition(self, cr_id: str, to_state: str, agent_id: str, reason: str | None = None) -> CRStateRecord:
        record = self.get_state(cr_id)
        from_state = record.current_state
        to_state_norm = to_state.strip().upper()

        allowed = ALLOWED_TRANSITIONS.get(from_state, set())
        if to_state_norm not in allowed:
            raise InvalidTransitionError(cr_id, from_state, to_state_norm)

        if to_state_norm in {"BLOCKED", "CANCELLED"}:
            if reason is None or not str(reason).strip():
                raise MissingReasonError(cr_id, to_state_norm)

        gate_names = required_gates(from_state, to_state_norm)
        results = evaluate_required_gates(record, gate_names)
        failures = [r for r in results if not r.passed]
        if failures:
            raise GateFailureError(cr_id, failures)

        now = _utcnow()
        new_history = list(record.state_history) + [
            StateHistoryEntry(state=to_state_norm, entered_at=now, by=agent_id)
        ]

        updated = replace(
            record,
            current_state=to_state_norm,
            state_history=new_history,
            blocked_reason=(str(reason).strip() if to_state_norm == "BLOCKED" else record.blocked_reason),
            cancelled_reason=(
                str(reason).strip() if to_state_norm == "CANCELLED" else record.cancelled_reason
            ),
        )

        atomic_write_json(self._state_path(cr_id), updated.to_json())

        index = self._load_index()
        self._index_remove(index, from_state, cr_id)
        self._index_add(index, to_state_norm, cr_id)
        self._write_index(index)

        gate_results = {r.gate_name: ("PASS" if r.passed else "FAIL") for r in results}
        payload: dict[str, Any] = {
            "cr_id": cr_id,
            "from_state": from_state,
            "to_state": to_state_norm,
            "gate_results": gate_results,
            "reason": str(reason).strip() if reason is not None else None,
        }
        self._audit.emit(
            "CR_STATE_CHANGED",
            payload,
            task_id=cr_id,
            agent_id=agent_id,
        )

        return updated

    def list_by_state(self, state: str) -> list[CRStateRecord]:
        state_norm = state.strip().upper()
        index = self._load_index()
        cr_ids = list(index.get(state_norm, []))
        return [self.get_state(cr_id) for cr_id in cr_ids]
