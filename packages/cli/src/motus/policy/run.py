# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Gate runner for Vault OS / Motus OS evidence bundles."""

from __future__ import annotations

from motus.policy.runner import (
    EVIDENCE_MANIFEST_VERSION,
    RunResult,
    run_gate_plan,
)

__all__ = ["EVIDENCE_MANIFEST_VERSION", "RunResult", "run_gate_plan"]
