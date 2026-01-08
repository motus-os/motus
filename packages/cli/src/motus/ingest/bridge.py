# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Bridge OTLP spans to Motus governance gates."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from motus.config import config
from motus.exceptions import ConfigError
from motus.ingest.parser import SpanAction

_GATE_TIER_RE = re.compile(r"^T(\d+)$")


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


def _gate_tier_value(tier: str | None) -> int | None:
    if not tier:
        return None
    match = _GATE_TIER_RE.fullmatch(tier.strip())
    if not match:
        return None
    return int(match.group(1))


def _resolve_repo_dir(span: SpanAction) -> Path:
    """Resolve repo directory from span metadata (fallback to cwd)."""
    candidates = (
        "repo.root",
        "repo.path",
        "project.root",
        "project.path",
        "tool.cwd",
        "cwd",
    )
    for key in candidates:
        raw = span.raw_attributes.get(key)
        if raw:
            try:
                return Path(str(raw)).expanduser().resolve()
            except (OSError, RuntimeError, ValueError):
                continue
    return Path.cwd()


def _extract_declared_files(span: SpanAction, repo_dir: Path) -> list[str]:
    """Extract candidate file paths for policy scope matching."""
    target = span.target or ""
    if not target or "://" in target:
        return []
    target_path = Path(target)
    if target_path.is_absolute():
        try:
            rel = target_path.resolve().relative_to(repo_dir.resolve())
            return [rel.as_posix()]
        except (OSError, RuntimeError, ValueError):
            return [target_path.as_posix()]
    return [target_path.as_posix()]


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

    vault_dir = config.paths.vault_dir
    if vault_dir is None:
        # Permit with legacy fallback when no vault policy is configured.
        evidence_id = _generate_evidence_id(span)
        return GateDecision(
            decision="permit",
            reason=None,
            evidence_id=evidence_id,
            gate_tier=0,
        )

    if not vault_dir.exists():
        return GateDecision(
            decision="deny",
            reason="vault_missing",
            evidence_id=_generate_evidence_id(span),
            gate_tier=None,
        )

    repo_dir = _resolve_repo_dir(span)
    declared_files = _extract_declared_files(span, repo_dir)

    try:
        from motus.policy.load import load_vault_policy
        from motus.policy.loader import compute_gate_plan
        from motus.policy.runner import run_gate_plan

        policy = load_vault_policy(vault_dir)
        plan = compute_gate_plan(changed_files=declared_files, policy=policy)
        result = run_gate_plan(
            plan=plan,
            declared_files=declared_files,
            declared_files_source="otlp",
            repo_dir=repo_dir,
            policy=policy,
        )
        decision = "permit" if result.exit_code == 0 else "deny"
        reason = None if result.exit_code == 0 else f"gate_exit_code:{result.exit_code}"
        return GateDecision(
            decision=decision,
            reason=reason,
            evidence_id=f"ev-{result.evidence_dir.name}",
            gate_tier=_gate_tier_value(plan.gate_tier),
        )
    except ConfigError:
        return GateDecision(
            decision="deny",
            reason="policy_error",
            evidence_id=_generate_evidence_id(span),
            gate_tier=None,
        )
    except Exception:
        return GateDecision(
            decision="deny",
            reason="gate_run_error",
            evidence_id=_generate_evidence_id(span),
            gate_tier=None,
        )
