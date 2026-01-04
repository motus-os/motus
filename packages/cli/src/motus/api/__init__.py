# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Motus API module.

This module provides:
1. The 6-Call Work Compiler API (facade.py)
2. External API resilience helpers (resilience.py)

The Work Compiler is the primary interface for task execution:

    from motus.api import WorkCompiler

    wc = WorkCompiler()
    result = wc.claim_work(task_id="PA-047", ...)
    if result.decision.decision == "GRANTED":
        wc.get_context(result.lease.lease_id)
        wc.put_outcome(...)
        wc.record_evidence(...)
        wc.record_decision(...)
        wc.release_work(result.lease.lease_id, outcome="success")
"""

from __future__ import annotations

from motus.api.facade import (
    DecisionResponse,
    DraftDecisionResponse,
    EvidenceResponse,
    OutcomeResponse,
    WorkCompiler,
)
from motus.api.resilience import (
    RateLimitState,
    call_with_backoff,
    handle_rate_limit_headers,
    should_preemptive_throttle,
)

__all__ = [
    # 6-Call Work Compiler API
    "WorkCompiler",
    "OutcomeResponse",
    "EvidenceResponse",
    "DecisionResponse",
    "DraftDecisionResponse",
    # Resilience helpers
    "RateLimitState",
    "call_with_backoff",
    "handle_rate_limit_headers",
    "should_preemptive_throttle",
]
