# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Benchmark harness for measuring protocol impact.

The v0.1 goal is simple: run paired trials (baseline vs Motus-enforced) and emit
deterministic, machine-readable results suitable for comparison and trend charts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from motus.bench.harness import (  # pragma: no cover
        BenchmarkHarness,
        BenchmarkReport,
        BenchmarkTask,
        EnforcementOutcome,
        TaskResult,
        TrialResult,
    )

__all__ = [
    "BenchmarkHarness",
    "BenchmarkReport",
    "BenchmarkTask",
    "EnforcementOutcome",
    "TaskResult",
    "TrialResult",
]


def __getattr__(name: str) -> Any:
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from motus.bench import harness as _harness

    return getattr(_harness, name)
