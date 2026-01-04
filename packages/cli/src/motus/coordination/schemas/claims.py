# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .common import _iso_z, _parse_iso_z

CLAIM_RECORD_SCHEMA = "motus.coordination.claim.v1"


@dataclass(frozen=True, slots=True)
class ClaimedResource:
    type: str
    path: str

    def to_json(self) -> dict[str, Any]:
        return {"type": self.type, "path": self.path}

    @staticmethod
    def from_json(payload: dict[str, Any]) -> "ClaimedResource":
        return ClaimedResource(type=str(payload["type"]), path=str(payload["path"]))


@dataclass(frozen=True, slots=True)
class ClaimRecord:
    schema: str
    claim_id: str
    agent_id: str
    session_id: str
    task_id: str
    task_type: str
    namespace: str | None
    claimed_resources: list[ClaimedResource]
    claimed_at: datetime
    expires_at: datetime
    lease_duration_s: int
    status: str
    idempotency_key: str | None = None

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schema": self.schema,
            "claim_id": self.claim_id,
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "task_id": self.task_id,
            "task_type": self.task_type,
            "claimed_resources": [r.to_json() for r in self.claimed_resources],
            "claimed_at": _iso_z(self.claimed_at),
            "expires_at": _iso_z(self.expires_at),
            "lease_duration_s": self.lease_duration_s,
            "status": self.status,
        }
        if self.namespace is not None:
            out["namespace"] = self.namespace
        if self.idempotency_key is not None:
            out["idempotency_key"] = self.idempotency_key
        return out

    @staticmethod
    def from_json(payload: dict[str, Any]) -> "ClaimRecord":
        resources_payload = payload.get("claimed_resources", [])
        return ClaimRecord(
            schema=str(payload["schema"]),
            claim_id=str(payload["claim_id"]),
            agent_id=str(payload["agent_id"]),
            session_id=str(payload["session_id"]),
            task_id=str(payload["task_id"]),
            task_type=str(payload["task_type"]),
            namespace=str(payload["namespace"]) if "namespace" in payload else None,
            claimed_resources=[ClaimedResource.from_json(r) for r in resources_payload],
            claimed_at=_parse_iso_z(str(payload["claimed_at"])),
            expires_at=_parse_iso_z(str(payload["expires_at"])),
            lease_duration_s=int(payload["lease_duration_s"]),
            status=str(payload["status"]),
            idempotency_key=(
                str(payload["idempotency_key"]) if "idempotency_key" in payload else None
            ),
        )
