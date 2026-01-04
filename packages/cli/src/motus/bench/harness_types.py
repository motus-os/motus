# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Type definitions for benchmark harness.

All dataclass types used in benchmarking: tasks, results, scopes, outcomes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from motus.bench._git_utils import GitNameStatusEntry, GitNumStatEntry
from motus.policy.verify import VerificationResult

BENCHMARK_REPORT_VERSION = "0.1.1"


def _default_now_iso() -> str:
    return "1970-01-01T00:00:00Z"


@dataclass(frozen=True)
class DeltaScope:
    delta_paths: tuple[str, ...]
    untracked_delta_paths: tuple[str, ...]

    @property
    def in_scope(self) -> bool:
        return not self.untracked_delta_paths

    def to_dict(self) -> dict:
        return {
            "delta_paths": list(self.delta_paths),
            "untracked_delta_paths": list(self.untracked_delta_paths),
            "in_scope": self.in_scope,
        }


@dataclass(frozen=True)
class VerificationOutcome:
    ok: bool
    reason_codes: tuple[str, ...]
    message: str | None = None

    @classmethod
    def from_result(cls, result: VerificationResult) -> "VerificationOutcome":
        return cls(ok=result.ok, reason_codes=tuple(result.reason_codes), message=result.message)

    def to_dict(self) -> dict:
        payload: dict = {"ok": self.ok, "reason_codes": list(self.reason_codes)}
        if self.message:
            payload["message"] = self.message
        return payload


@dataclass(frozen=True)
class EnforcementOutcome:
    exit_code: int
    verification: VerificationOutcome
    gate_count: int
    untracked_delta_count: int

    def to_dict(self) -> dict:
        return {
            "exit_code": self.exit_code,
            "verification": self.verification.to_dict(),
            "gate_count": self.gate_count,
            "untracked_delta_count": self.untracked_delta_count,
        }


@dataclass(frozen=True)
class TrialResult:
    mode: str
    task_ok: bool
    duration_ms: int
    delta_scope: DeltaScope
    diff_name_status: tuple[GitNameStatusEntry, ...] = ()
    diff_numstat: tuple[GitNumStatEntry, ...] = ()
    churn_lines_added: int = 0
    churn_lines_deleted: int = 0
    analysis: dict | None = None
    enforcement: EnforcementOutcome | None = None

    @property
    def ok(self) -> bool:
        if not self.task_ok:
            return False
        if self.enforcement is None:
            return True
        return self.enforcement.exit_code == 0 and self.enforcement.verification.ok

    def to_dict(self) -> dict:
        payload: dict = {
            "mode": self.mode,
            "ok": self.ok,
            "task_ok": self.task_ok,
            "duration_ms": self.duration_ms,
            "delta_scope": self.delta_scope.to_dict(),
            "diff": {
                "name_status": [e.to_dict() for e in self.diff_name_status],
                "numstat": [e.to_dict() for e in self.diff_numstat],
                "churn_lines_added": self.churn_lines_added,
                "churn_lines_deleted": self.churn_lines_deleted,
            },
        }
        if self.analysis is not None:
            payload["analysis"] = self.analysis
        if self.enforcement is not None:
            payload["enforcement"] = self.enforcement.to_dict()
        return payload


@dataclass(frozen=True)
class TaskResult:
    task_id: str
    description: str
    declared_scope: tuple[str, ...]
    baseline: TrialResult
    motus: TrialResult

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "description": self.description,
            "declared_scope": list(self.declared_scope),
            "baseline": self.baseline.to_dict(),
            "motus": self.motus.to_dict(),
        }


@dataclass(frozen=True)
class BenchmarkReport:
    version: str
    tasks: tuple[TaskResult, ...]

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "tasks": [t.to_dict() for t in self.tasks],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


@dataclass(frozen=True)
class BenchmarkTask:
    task_id: str
    description: str
    declared_scope: tuple[str, ...]
    build_fixture: Callable[[Path], None]
    apply_changes: Callable[[Path], None]
    evaluate: Callable[[Path], bool]
    analyze: Callable[[Path], dict] | None = None
