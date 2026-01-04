# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Result types for the Cached Orient API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

OrientResultKind = Literal["HIT", "MISS", "CONFLICT"]
SlowPath = Literal["allowed", "required", "blocked"]


@dataclass(frozen=True, slots=True)
class OrientResult:
    """Orient API output contract."""

    result: OrientResultKind
    decision: dict[str, Any] | None = None
    standard_id: str | None = None
    layer: Literal["system", "project", "user"] | None = None
    match_trace: dict[str, Any] | None = None
    candidates: list[dict[str, Any]] | None = None
    slow_path: SlowPath | None = None

    def to_dict(self, *, include_trace: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {"result": self.result}

        if self.result == "HIT":
            data["decision"] = self.decision or {}
            data["standard_id"] = self.standard_id
            data["layer"] = self.layer
            if include_trace and self.match_trace is not None:
                data["match_trace"] = self.match_trace

        elif self.result == "MISS":
            data["slow_path"] = self.slow_path or "allowed"
            if include_trace and self.match_trace is not None:
                data["match_trace"] = self.match_trace

        elif self.result == "CONFLICT":
            data["candidates"] = self.candidates or []
            if include_trace and self.match_trace is not None:
                data["match_trace"] = self.match_trace

        return data

