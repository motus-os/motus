# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Analytics for Cached Orient.

Consumes `.motus/state/orient/events.jsonl` to compute hit/conflict rates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True, slots=True)
class DecisionTypeStats:
    decision_type: str
    calls: int
    hits: int
    misses: int
    conflicts: int

    @property
    def hit_rate(self) -> float:
        denom = self.hits + self.misses
        return (self.hits / denom) if denom else 0.0

    @property
    def conflict_rate(self) -> float:
        return (self.conflicts / self.calls) if self.calls else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_type": self.decision_type,
            "calls": self.calls,
            "hits": self.hits,
            "misses": self.misses,
            "conflicts": self.conflicts,
            "hit_rate": self.hit_rate,
            "conflict_rate": self.conflict_rate,
        }


def _coerce_str(raw: Any) -> str | None:
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def compute_stats(events: Iterable[Mapping[str, Any]]) -> dict[str, DecisionTypeStats]:
    counts: dict[str, dict[str, int]] = {}
    for ev in events:
        decision_type = _coerce_str(ev.get("decision_type"))
        if decision_type is None:
            continue

        result = _coerce_str(ev.get("result")) or _coerce_str(ev.get("outcome"))
        if result not in {"HIT", "MISS", "CONFLICT"}:
            continue

        row = counts.setdefault(
            decision_type, {"calls": 0, "hits": 0, "misses": 0, "conflicts": 0}
        )
        row["calls"] += 1
        if result == "HIT":
            row["hits"] += 1
        elif result == "MISS":
            row["misses"] += 1
        elif result == "CONFLICT":
            row["conflicts"] += 1

    return {
        dt: DecisionTypeStats(
            decision_type=dt,
            calls=row["calls"],
            hits=row["hits"],
            misses=row["misses"],
            conflicts=row["conflicts"],
        )
        for dt, row in counts.items()
    }


def top_high_miss(
    stats: dict[str, DecisionTypeStats], *, limit: int = 5, min_calls: int = 1
) -> list[DecisionTypeStats]:
    candidates = [s for s in stats.values() if s.calls >= min_calls]
    candidates.sort(key=lambda s: (s.hit_rate, -s.calls, s.decision_type))
    return candidates[:limit]


def render_table(stats: Iterable[DecisionTypeStats]) -> str:
    rows = list(stats)
    headers = ("Type", "Calls", "Hit Rate", "Conflict Rate")
    data_rows = [
        (
            s.decision_type,
            str(s.calls),
            f"{s.hit_rate * 100:.1f}%",
            f"{s.conflict_rate * 100:.1f}%",
        )
        for s in rows
    ]
    widths = [
        max(len(headers[i]), *(len(r[i]) for r in data_rows)) if data_rows else len(headers[i])
        for i in range(len(headers))
    ]

    def fmt(r: tuple[str, str, str, str]) -> str:
        return (
            f"| {r[0].ljust(widths[0])} | {r[1].rjust(widths[1])} | "
            f"{r[2].rjust(widths[2])} | {r[3].rjust(widths[3])} |"
        )

    lines = [
        fmt(headers),
        "|-" + "-|-".join("-" * w for w in widths) + "-|",
        *[fmt(r) for r in data_rows],
    ]
    return "\n".join(lines)

