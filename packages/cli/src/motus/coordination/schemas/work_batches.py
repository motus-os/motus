# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .common import _iso_z, _parse_iso_z

WORK_BATCH_SCHEMA = "motus.coordination.work_batch.v1"


@dataclass(frozen=True, slots=True)
class WorkItem:
    work_item_id: str
    status: str

    def to_json(self) -> dict[str, Any]:
        return {"work_item_id": self.work_item_id, "status": self.status}

    @staticmethod
    def from_json(payload: dict[str, Any]) -> "WorkItem":
        return WorkItem(work_item_id=str(payload["work_item_id"]), status=str(payload["status"]))


@dataclass(frozen=True, slots=True)
class ReconciliationReport:
    expected_count: int
    produced_count: int
    produced_artifacts: list[str]
    missing_artifacts: list[str]
    unexpected_artifacts: list[str]
    balanced: bool

    def to_json(self) -> dict[str, Any]:
        return {
            "expected_count": int(self.expected_count),
            "produced_count": int(self.produced_count),
            "produced_artifacts": list(self.produced_artifacts),
            "missing_artifacts": list(self.missing_artifacts),
            "unexpected_artifacts": list(self.unexpected_artifacts),
            "balanced": bool(self.balanced),
        }

    @staticmethod
    def from_json(payload: dict[str, Any]) -> "ReconciliationReport":
        return ReconciliationReport(
            expected_count=int(payload["expected_count"]),
            produced_count=int(payload["produced_count"]),
            produced_artifacts=[str(p) for p in payload.get("produced_artifacts", [])],
            missing_artifacts=[str(p) for p in payload.get("missing_artifacts", [])],
            unexpected_artifacts=[str(p) for p in payload.get("unexpected_artifacts", [])],
            balanced=bool(payload.get("balanced", False)),
        )


@dataclass(frozen=True, slots=True)
class WorkBatch:
    schema: str
    batch_id: str
    batch_type: str
    description: str
    status: str
    created_at: datetime
    created_by: str
    work_items: list[WorkItem]
    expected_artifacts: list[str]
    reconciliation: ReconciliationReport | None
    batch_hash: str
    prev_batch_hash: str | None
    sequence_number: int

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schema": self.schema,
            "batch_id": self.batch_id,
            "batch_type": self.batch_type,
            "description": self.description,
            "status": self.status,
            "created_at": _iso_z(self.created_at),
            "created_by": self.created_by,
            "work_items": [w.to_json() for w in self.work_items],
            "expected_artifacts": list(self.expected_artifacts),
            "batch_hash": self.batch_hash,
            "sequence_number": int(self.sequence_number),
        }
        if self.reconciliation is not None:
            out["reconciliation"] = self.reconciliation.to_json()
        if self.prev_batch_hash is not None:
            out["prev_batch_hash"] = self.prev_batch_hash
        return out

    @staticmethod
    def from_json(payload: dict[str, Any]) -> "WorkBatch":
        reconciliation_payload = payload.get("reconciliation", None)
        return WorkBatch(
            schema=str(payload["schema"]),
            batch_id=str(payload["batch_id"]),
            batch_type=str(payload["batch_type"]),
            description=str(payload["description"]),
            status=str(payload["status"]),
            created_at=_parse_iso_z(str(payload["created_at"])),
            created_by=str(payload["created_by"]),
            work_items=[WorkItem.from_json(w) for w in payload.get("work_items", [])],
            expected_artifacts=[str(p) for p in payload.get("expected_artifacts", [])],
            reconciliation=(
                ReconciliationReport.from_json(reconciliation_payload)
                if isinstance(reconciliation_payload, dict)
                else None
            ),
            batch_hash=str(payload["batch_hash"]),
            prev_batch_hash=(
                str(payload["prev_batch_hash"]) if payload.get("prev_batch_hash") else None
            ),
            sequence_number=int(payload["sequence_number"]),
        )
