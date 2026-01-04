# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Cached Orient API implementation wrapper.

v0 intentionally supports a "null" resolver; later CRs provide full resolution logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from motus.orient.result import OrientResult, SlowPath
from motus.standards.schema import DecisionTypeRegistry


class StandardsResolver(Protocol):
    def resolve(
        self,
        *,
        decision_type: str,
        context: dict[str, Any],
        constraints: dict[str, Any] | None = None,
        explain: bool = False,
    ) -> OrientResult: ...


@dataclass(frozen=True, slots=True)
class _NullResolver:
    def resolve(
        self,
        *,
        decision_type: str,
        context: dict[str, Any],
        constraints: dict[str, Any] | None = None,
        explain: bool = False,
    ) -> OrientResult:
        _ = (decision_type, context, constraints, explain)
        return OrientResult(result="MISS")


class OrientAPI:
    """Public API for Cached Orient lookups."""

    def __init__(
        self,
        *,
        resolver: StandardsResolver | None = None,
        decision_types: DecisionTypeRegistry | None = None,
    ) -> None:
        self._resolver: StandardsResolver = resolver or _NullResolver()
        self._decision_types = decision_types

    def orient(
        self,
        decision_type: str,
        context: dict[str, Any],
        *,
        constraints: dict[str, Any] | None = None,
        explain: bool = False,
    ) -> OrientResult:
        result = self._resolver.resolve(
            decision_type=decision_type,
            context=context,
            constraints=constraints,
            explain=explain,
        )

        if result.result != "MISS":
            return result

        slow_path = result.slow_path or self._slow_path_for_miss(decision_type)
        return OrientResult(
            result="MISS",
            slow_path=slow_path,
            match_trace=result.match_trace,
        )

    def explain(
        self,
        decision_type: str,
        context: dict[str, Any],
        *,
        constraints: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = self.orient(decision_type, context, constraints=constraints, explain=True)
        return result.match_trace or {"result": result.result}

    def _slow_path_for_miss(self, decision_type: str) -> SlowPath:
        if self._decision_types is None:
            return "allowed"

        dt = self._decision_types.get(decision_type)
        if dt is None:
            return "allowed"

        if dt.required:
            return "required"
        if dt.default_slow_path == "block":
            return "blocked"
        return "allowed"

