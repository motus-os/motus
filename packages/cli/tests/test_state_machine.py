from __future__ import annotations

import json
from pathlib import Path

import pytest

from motus.coordination.state_machine import (
    CRStateMachine,
    GateFailureError,
    InvalidTransitionError,
    MissingReasonError,
)


def _read_ledger_lines(root: Path) -> list[dict]:
    ledger = root / "ledger"
    if not ledger.exists():
        return []
    items: list[dict] = []
    for path in sorted(ledger.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            items.append(json.loads(line))
    return items


def test_register_cr_creates_queued_record(tmp_path: Path) -> None:
    sm = CRStateMachine(tmp_path)
    record = sm.register_cr("CR-test-1")
    assert record.current_state == "QUEUED"
    assert len(record.state_history) == 1


def test_invalid_transition_raises(tmp_path: Path) -> None:
    sm = CRStateMachine(tmp_path)
    sm.register_cr("CR-test-1")
    with pytest.raises(InvalidTransitionError):
        sm.transition("CR-test-1", "DONE", agent_id="agent-a")


def test_gate_blocks_queued_to_in_progress(tmp_path: Path) -> None:
    sm = CRStateMachine(tmp_path)
    sm.register_cr("CR-test-1")

    with pytest.raises(GateFailureError):
        sm.transition("CR-test-1", "IN_PROGRESS", agent_id="agent-a")

    sm.mark_gate_passed("CR-test-1", "definition_of_ready")
    record = sm.transition("CR-test-1", "IN_PROGRESS", agent_id="agent-a")
    assert record.current_state == "IN_PROGRESS"

    events = _read_ledger_lines(tmp_path)
    assert any(e.get("event_type") == "CR_STATE_CHANGED" for e in events)


def test_blocked_requires_reason(tmp_path: Path) -> None:
    sm = CRStateMachine(tmp_path)
    sm.register_cr("CR-test-1")
    sm.mark_gate_passed("CR-test-1", "definition_of_ready")
    sm.transition("CR-test-1", "IN_PROGRESS", agent_id="agent-a")

    with pytest.raises(MissingReasonError):
        sm.transition("CR-test-1", "BLOCKED", agent_id="agent-a")

    record = sm.transition("CR-test-1", "BLOCKED", agent_id="agent-a", reason="waiting on input")
    assert record.current_state == "BLOCKED"
    assert record.blocked_reason == "waiting on input"


def test_cancelled_requires_reason(tmp_path: Path) -> None:
    sm = CRStateMachine(tmp_path)
    sm.register_cr("CR-test-1")
    with pytest.raises(MissingReasonError):
        sm.transition("CR-test-1", "CANCELLED", agent_id="agent-a")

    record = sm.transition("CR-test-1", "CANCELLED", agent_id="agent-a", reason="no longer needed")
    assert record.current_state == "CANCELLED"
    assert record.cancelled_reason == "no longer needed"


def test_list_by_state_uses_index(tmp_path: Path) -> None:
    sm = CRStateMachine(tmp_path)
    sm.register_cr("CR-a")
    sm.register_cr("CR-b")

    sm.mark_gate_passed("CR-a", "definition_of_ready")
    sm.transition("CR-a", "IN_PROGRESS", agent_id="agent-a")

    queued = sm.list_by_state("QUEUED")
    in_progress = sm.list_by_state("IN_PROGRESS")

    assert {r.cr_id for r in queued} == {"CR-b"}
    assert {r.cr_id for r in in_progress} == {"CR-a"}

