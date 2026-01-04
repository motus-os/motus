# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Standards resolver for Cached Orient.

Resolution order:
1) Specificity (descending)
2) Priority (descending)
3) Layer precedence tie-breaker (user > project > system)
4) CONFLICT (fail-closed) if still tied
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from motus.orient.index import IndexedStandard, StandardsIndex, infer_layer
from motus.orient.result import OrientResult
from motus.orient.specificity import specificity


def _predicate_matches(applies_if: dict[str, Any], context: dict[str, Any]) -> bool:
    for key, required in applies_if.items():
        if key not in context:
            return False
        actual = context[key]
        if isinstance(required, list):
            if actual not in required:
                return False
        else:
            if actual != required:
                return False
    return True


def _candidate_dict(item: IndexedStandard, *, score: int) -> dict[str, Any]:
    s = item.standard
    return {
        "standard_id": s.standard_id,
        "id": s.id,
        "type": s.type,
        "version": s.version,
        "layer": infer_layer(item.path),
        "priority": s.priority,
        "specificity": score,
        "path": item.path.as_posix(),
        "status": s.status,
    }


@dataclass(slots=True)
class StandardsResolver:
    """Resolve Cached Orient decisions from an index snapshot."""

    index: StandardsIndex

    def resolve(
        self,
        *,
        decision_type: str,
        context: dict[str, Any],
        constraints: dict[str, Any] | None = None,
        explain: bool = False,
    ) -> OrientResult:
        _ = constraints  # reserved for future phases

        standards = list(self.index.get_standards(decision_type))
        # Determinism: stable sort regardless of discovery order.
        standards.sort(key=lambda i: (i.standard.standard_id, i.path.as_posix()))

        scanned = len(standards)
        matches: list[tuple[IndexedStandard, int]] = []

        for item in standards:
            if item.standard.status != "active":
                continue
            if not _predicate_matches(item.standard.applies_if, context):
                continue
            matches.append((item, specificity(item.standard.applies_if)))

        if not matches:
            return OrientResult(
                result="MISS",
                match_trace=(
                    {"decision_type": decision_type, "context": context, "scanned": scanned}
                    if explain
                    else None
                ),
            )

        # 1) Max specificity wins.
        matches.sort(key=lambda x: (-x[1], x[0].standard.standard_id, x[0].path.as_posix()))
        max_spec = matches[0][1]
        candidates = [m for m in matches if m[1] == max_spec]

        if len(candidates) == 1:
            winner, score = candidates[0]
            return OrientResult(
                result="HIT",
                decision=winner.standard.output,
                standard_id=winner.standard.standard_id,
                layer=infer_layer(winner.path),
                match_trace=(
                    {
                        "decision_type": decision_type,
                        "context": context,
                        "scanned": scanned,
                        "matched": [
                            _candidate_dict(i, score=s)
                            for i, s in sorted(
                                matches,
                                key=lambda x: (x[0].standard.standard_id, x[0].path.as_posix()),
                            )
                        ],
                        "winner": _candidate_dict(winner, score=score),
                    }
                    if explain
                    else None
                ),
            )

        # 2) Max priority breaks specificity ties.
        candidates.sort(
            key=lambda x: (-x[0].standard.priority, x[0].standard.standard_id, x[0].path.as_posix())
        )
        max_priority = candidates[0][0].standard.priority
        candidates = [c for c in candidates if c[0].standard.priority == max_priority]

        if len(candidates) == 1:
            winner, score = candidates[0]
            return OrientResult(
                result="HIT",
                decision=winner.standard.output,
                standard_id=winner.standard.standard_id,
                layer=infer_layer(winner.path),
                match_trace=(
                    {
                        "decision_type": decision_type,
                        "context": context,
                        "scanned": scanned,
                        "matched": [
                            _candidate_dict(i, score=s)
                            for i, s in sorted(
                                matches,
                                key=lambda x: (x[0].standard.standard_id, x[0].path.as_posix()),
                            )
                        ],
                        "candidates": [_candidate_dict(i, score=s) for i, s in candidates],
                        "winner": _candidate_dict(winner, score=score),
                    }
                    if explain
                    else None
                ),
            )

        # 3) Layer precedence tie-breaker (user > project > system).
        for layer in ("user", "project", "system"):
            layer_hits = [(i, s) for i, s in candidates if infer_layer(i.path) == layer]
            if len(layer_hits) == 1:
                winner, score = layer_hits[0]
                return OrientResult(
                    result="HIT",
                    decision=winner.standard.output,
                    standard_id=winner.standard.standard_id,
                    layer=layer,
                    match_trace=(
                        {
                            "decision_type": decision_type,
                            "context": context,
                            "scanned": scanned,
                            "matched": [
                                _candidate_dict(i, score=s)
                                for i, s in sorted(
                                    matches,
                                    key=lambda x: (x[0].standard.standard_id, x[0].path.as_posix()),
                                )
                            ],
                            "candidates": [_candidate_dict(i, score=s) for i, s in candidates],
                            "winner": _candidate_dict(winner, score=score),
                        }
                        if explain
                        else None
                    ),
                )
            if len(layer_hits) > 1:
                return OrientResult(
                    result="CONFLICT",
                    candidates=[_candidate_dict(i, score=s) for i, s in layer_hits],
                    match_trace=(
                        {
                            "decision_type": decision_type,
                            "context": context,
                            "scanned": scanned,
                            "matched": [
                                _candidate_dict(i, score=s)
                                for i, s in sorted(
                                    matches,
                                    key=lambda x: (x[0].standard.standard_id, x[0].path.as_posix()),
                                )
                            ],
                            "candidates": [_candidate_dict(i, score=s) for i, s in layer_hits],
                        }
                        if explain
                        else None
                    ),
                )

        # Fallback: unresolvable ambiguity.
        return OrientResult(
            result="CONFLICT",
            candidates=[_candidate_dict(i, score=s) for i, s in candidates],
            match_trace=(
                {
                    "decision_type": decision_type,
                    "context": context,
                    "scanned": scanned,
                    "matched": [
                        _candidate_dict(i, score=s)
                        for i, s in sorted(
                            matches,
                            key=lambda x: (x[0].standard.standard_id, x[0].path.as_posix()),
                        )
                    ],
                    "candidates": [_candidate_dict(i, score=s) for i, s in candidates],
                }
                if explain
                else None
            ),
        )
