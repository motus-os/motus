# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .common import _iso_z, _parse_iso_z

REVERSAL_BATCH_SCHEMA = "motus.coordination.reversal_batch.v1"
SNAPSHOT_SCHEMA = "motus.coordination.snapshot.v1"


@dataclass(frozen=True, slots=True)
class FileState:
    path: str
    hash: str
    exists: bool

    def to_json(self) -> dict[str, Any]:
        return {"path": self.path, "hash": self.hash, "exists": self.exists}

    @staticmethod
    def from_json(payload: dict[str, Any]) -> "FileState":
        return FileState(
            path=str(payload["path"]), hash=str(payload["hash"]), exists=bool(payload["exists"])
        )


@dataclass(frozen=True, slots=True)
class Snapshot:
    schema: str
    snapshot_id: str
    reversal_id: str
    captured_at: datetime
    file_states: list[FileState]

    def to_json(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "snapshot_id": self.snapshot_id,
            "reversal_id": self.reversal_id,
            "captured_at": _iso_z(self.captured_at),
            "file_states": [fs.to_json() for fs in self.file_states],
        }

    @staticmethod
    def from_json(payload: dict[str, Any]) -> "Snapshot":
        file_states_payload = payload.get("file_states", [])
        return Snapshot(
            schema=str(payload["schema"]),
            snapshot_id=str(payload["snapshot_id"]),
            reversal_id=str(payload["reversal_id"]),
            captured_at=_parse_iso_z(str(payload["captured_at"])),
            file_states=[FileState.from_json(fs) for fs in file_states_payload],
        )


@dataclass(frozen=True, slots=True)
class CompensatingAction:
    action_id: str
    action_type: str
    target: str
    executed_at: datetime | None
    result: str | None
    before_hash: str | None
    after_hash: str | None

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "action_id": self.action_id,
            "action_type": self.action_type,
            "target": self.target,
        }
        if self.executed_at is not None:
            out["executed_at"] = _iso_z(self.executed_at)
        if self.result is not None:
            out["result"] = self.result
        if self.before_hash is not None:
            out["before_hash"] = self.before_hash
        if self.after_hash is not None:
            out["after_hash"] = self.after_hash
        return out

    @staticmethod
    def from_json(payload: dict[str, Any]) -> "CompensatingAction":
        return CompensatingAction(
            action_id=str(payload["action_id"]),
            action_type=str(payload["action_type"]),
            target=str(payload["target"]),
            executed_at=(
                _parse_iso_z(str(payload["executed_at"])) if "executed_at" in payload else None
            ),
            result=str(payload["result"]) if "result" in payload else None,
            before_hash=str(payload["before_hash"]) if "before_hash" in payload else None,
            after_hash=str(payload["after_hash"]) if "after_hash" in payload else None,
        )


@dataclass(frozen=True, slots=True)
class ReversalItem:
    work_item_id: str
    original_status: str
    compensating_action: str
    artifacts_to_remove: list[str]
    status: str

    def to_json(self) -> dict[str, Any]:
        return {
            "work_item_id": self.work_item_id,
            "original_status": self.original_status,
            "compensating_action": self.compensating_action,
            "artifacts_to_remove": self.artifacts_to_remove,
            "status": self.status,
        }

    @staticmethod
    def from_json(payload: dict[str, Any]) -> "ReversalItem":
        return ReversalItem(
            work_item_id=str(payload["work_item_id"]),
            original_status=str(payload["original_status"]),
            compensating_action=str(payload["compensating_action"]),
            artifacts_to_remove=[str(a) for a in payload.get("artifacts_to_remove", [])],
            status=str(payload["status"]),
        )


@dataclass(frozen=True, slots=True)
class ReversalBatch:
    schema: str
    reversal_id: str
    reverses_batch_id: str
    reversal_type: str
    status: str
    reason: str
    created_at: datetime
    created_by: str
    items_to_reverse: list[ReversalItem]
    compensating_actions_log: list[CompensatingAction]
    reversal_hash: str
    original_batch_hash: str

    def to_json(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "reversal_id": self.reversal_id,
            "reverses_batch_id": self.reverses_batch_id,
            "reversal_type": self.reversal_type,
            "status": self.status,
            "reason": self.reason,
            "created_at": _iso_z(self.created_at),
            "created_by": self.created_by,
            "items_to_reverse": [item.to_json() for item in self.items_to_reverse],
            "compensating_actions_log": [
                action.to_json() for action in self.compensating_actions_log
            ],
            "reversal_hash": self.reversal_hash,
            "original_batch_hash": self.original_batch_hash,
        }

    @staticmethod
    def from_json(payload: dict[str, Any]) -> "ReversalBatch":
        items_payload = payload.get("items_to_reverse", [])
        actions_payload = payload.get("compensating_actions_log", [])
        return ReversalBatch(
            schema=str(payload["schema"]),
            reversal_id=str(payload["reversal_id"]),
            reverses_batch_id=str(payload["reverses_batch_id"]),
            reversal_type=str(payload["reversal_type"]),
            status=str(payload["status"]),
            reason=str(payload["reason"]),
            created_at=_parse_iso_z(str(payload["created_at"])),
            created_by=str(payload["created_by"]),
            items_to_reverse=[ReversalItem.from_json(item) for item in items_payload],
            compensating_actions_log=[
                CompensatingAction.from_json(action) for action in actions_payload
            ],
            reversal_hash=str(payload["reversal_hash"]),
            original_batch_hash=str(payload["original_batch_hash"]),
        )
