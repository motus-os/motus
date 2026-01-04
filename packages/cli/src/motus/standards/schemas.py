# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Dataclasses for standards-related artifacts beyond `Standard`.

This module intentionally keeps lightweight, serialization-friendly shapes for
on-disk state like proposals.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

ProposalStatus = Literal["pending", "approved", "rejected"]


@dataclass(frozen=True, slots=True)
class Proposal:
    schema: str
    proposal_id: str
    decision_type: str
    context_hash: str
    context_sample: dict[str, Any]
    proposed_output: dict[str, Any]
    proposed_by: str
    created_at: str
    status: ProposalStatus = "pending"
    why: str | None = None
    outcome_signals: list[str] | None = None
    promoted_to: str | None = None
    promoted_layer: Literal["user", "project"] | None = None
    promoted_at: str | None = None
    rejected_reason: str | None = None
    rejected_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "proposal_id": self.proposal_id,
            "decision_type": self.decision_type,
            "context_hash": self.context_hash,
            "context_sample": self.context_sample,
            "proposed_output": self.proposed_output,
            "proposed_by": self.proposed_by,
            "created_at": self.created_at,
            "status": self.status,
            "why": self.why,
            "outcome_signals": self.outcome_signals or [],
            "promoted_to": self.promoted_to,
            "promoted_layer": self.promoted_layer,
            "promoted_at": self.promoted_at,
            "rejected_reason": self.rejected_reason,
            "rejected_at": self.rejected_at,
        }

