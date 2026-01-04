# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Bridge OTLP spans to Motus governance gates."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from motus.ingest.parser import SpanAction

# TODO: Wire to policy/runner.py run_gates() for full gate execution


@dataclass(frozen=True)
class GateDecision:
    """Result of processing a span through governance gates."""

    decision: str  # "permit" | "deny" | "pass"
    reason: str | None
    evidence_id: str | None
    gate_tier: int | None


def _generate_evidence_id(span: SpanAction) -> str:
    """Generate a unique evidence ID for a span action."""
    trace_prefix = span.trace_id[:8] if span.trace_id else "notrace"
    return f"ev-{trace_prefix}-{uuid.uuid4().hex[:8]}"


def process_span_action(span: SpanAction) -> GateDecision:
    """Process a span through governance gates.

    Only tool calls (spans with name starting with "tool.") are gated.
    Other spans pass through without governance overhead.
    """
    # If not a tool call, pass through without gating
    if not span.name.startswith("tool."):
        return GateDecision(
            decision="pass",
            reason="not_a_tool",
            evidence_id=None,
            gate_tier=None,
        )

    # Check safety score if present (simple gate example)
    if span.safety_score is not None and span.safety_score < 500:
        return GateDecision(
            decision="deny",
            reason=f"safety_score_below_threshold:{span.safety_score}",
            evidence_id=_generate_evidence_id(span),
            gate_tier=2,
        )

    # Permit and capture evidence
    evidence_id = _generate_evidence_id(span)
    return GateDecision(
        decision="permit",
        reason=None,
        evidence_id=evidence_id,
        gate_tier=0,
    )
