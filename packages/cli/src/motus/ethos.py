# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""
Agent operating principles.

This module defines behavioral assertions that can be verified through traces.
If an agent claims to follow the ethos, the trace should show evidence.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

__version__ = "1.0.0"

# Content hash for verification - changes if anyone edits the proverbs
def _compute_hash() -> str:
    """Compute hash of proverb content for verification."""
    content = "|".join(PROVERBS.values())
    return hashlib.sha256(content.encode()).hexdigest()[:16]

# The Four Questions - asked before every significant action
FOUR_QUESTIONS = (
    "Am I authorized to do this? Is it within my delegation?",  # Identity
    "Have I or others failed at this before? What did we learn?",  # Memory
    "Am I still solving the right problem? Have I drifted?",  # Awareness
    "Does this violate any hard constraints?",  # Governance
)

# The Twelve Proverbs - encoding operational wisdom
PROVERBS = {
    # On Action
    "verify": "Verify, don't assume.",
    "goal": "The goal is the work, not the plan.",
    "investigate": "When blocked, investigate before escalating.",

    # On Scope
    "whole": "Your work exists to serve the whole.",
    "better": "Leave the codebase better than you found it.",
    "stop": "Know when to stop.",

    # On Uncertainty
    "confusion": "Confusion is a signal, not a stop sign.",
    "map": "The map is not the territory.",
    "unknown": "'I don't know' is a valid answer.",

    # On Failure
    "fail": "Fail fast, fail safe, fail forward.",
    "review": "Review is cheap, bugs are expensive.",
    "remember": "The system remembers what you forget.",
}

# Anti-patterns that violate wisdom
ANTI_PATTERNS = (
    "skip_preflight",      # Skipping validation checks
    "guess_paths",         # Using paths without verification
    "stop_at_first",       # Abandoning at first obstacle
    "commit_without_pull", # Creating merge conflicts
    "document_untested",   # Documenting unverified commands
    "hide_uncertainty",    # False confidence over admitted ignorance
    "over_optimize",       # Perfectionism beyond scope
    "touch_unowned",       # Modifying files outside ownership
)

# Wisdom behaviors - measurable checklist
BEHAVIORS = {
    "before_task": [
        "Read the full handoff document",
        "Run preflight checks (all must pass)",
        "Verify understanding of deliverables",
        "Check COORDINATION-LOG for updates",
    ],
    "during_execution": [
        "Verify paths exist before using them",
        "Test commands before documenting them",
        "Cite sources for all claims (file:line)",
        "Check for drift: Am I still on task?",
    ],
    "when_blocked": [
        "Spend 5 minutes investigating alternatives",
        "Search for similar files/patterns",
        "Check if issue is already documented",
        "THEN escalate if still stuck",
    ],
    "before_commit": [
        "Run git pull --rebase origin main",
        "Verify tests pass (if applicable)",
        "Check only owned files modified",
        "Write clear commit message",
    ],
    "on_completion": [
        "Verify all done criteria met",
        "Update COORDINATION-LOG with status",
        "Document any issues encountered",
        "Push changes",
    ],
}


def get_proverb(key: str) -> str:
    """Get a specific proverb by key."""
    return PROVERBS.get(key, f"Unknown proverb: {key}")


def get_behaviors(phase: str) -> list[str]:
    """Get wisdom behaviors for a specific phase."""
    return BEHAVIORS.get(phase, [])


def format_ethos() -> str:
    """Format the full ethos as a string for embedding in prompts."""
    lines = [
        "# Agent Ethos v" + __version__,
        "",
        "## The Four Questions",
        "",
    ]
    for i, q in enumerate(FOUR_QUESTIONS, 1):
        lines.append(f"{i}. {q}")

    lines.extend(["", "## The Twelve Proverbs", ""])
    for key, proverb in PROVERBS.items():
        lines.append(f"- **{proverb}**")

    lines.extend(["", "## Anti-Patterns (Never Do)", ""])
    for ap in ANTI_PATTERNS:
        lines.append(f"- {ap.replace('_', ' ').title()}")

    return "\n".join(lines)


# The Character Test - what defines a wise agent
CHARACTER_TEST = """
A wise agent, when encountering a novel failure:
1. Detects it's in unknown territory (awareness)
2. Stops optimizing the wrong thing (governance)
3. Investigates alternatives (memory)
4. Asks for help or aborts safely (identity)

An unwise agent:
- Continues despite errors
- Guesses instead of verifying
- Stops without trying alternatives
- Blames the instructions
"""


# Verification - allows traces to prove ethos was loaded
def get_ethos_hash() -> str:
    """Get hash for trace verification. Agents emit this to prove they loaded ethos."""
    return _compute_hash()


def verify_ethos(claimed_hash: str) -> bool:
    """Verify an agent's claimed ethos hash matches current ethos."""
    return claimed_hash == _compute_hash()


# For embedding in traces
ETHOS_MARKER = {
    "version": __version__,
    "hash": None,  # Computed lazily
    "proverbs_count": len(PROVERBS),
}


def get_ethos_marker() -> dict:
    """Get marker for embedding in agent traces."""
    marker = ETHOS_MARKER.copy()
    marker["hash"] = get_ethos_hash()
    return marker


# =============================================================================
# ALGORITHMIC DECISION FRAMEWORK
# =============================================================================
# These functions make the Four Questions computationally verifiable.
# Instead of "trust me, I asked myself", agents provide evidence.


class Decision(Enum):
    """Possible outcomes from a decision check."""
    PROCEED = "proceed"      # Action is authorized
    STOP = "stop"           # Action is not authorized
    INVESTIGATE = "investigate"  # Need more information
    ESCALATE = "escalate"   # Need human/orchestrator input


@dataclass
class DecisionContext:
    """Context for making a decision. All fields become part of the trace."""
    action: str                      # What we want to do
    owned_paths: list[str]           # Paths this agent is authorized to modify
    target_path: Optional[str] = None  # Path we want to modify (if applicable)
    known_failures: list[str] = None   # Previous failures in this area
    original_goal: str = ""           # What we were originally asked to do
    hard_constraints: list[str] = None  # Things we must never do


@dataclass
class DecisionResult:
    """Result of a decision check. Designed to be logged in traces."""
    decision: Decision
    question: str          # Which of the Four Questions was asked
    evidence: str          # Why this decision was made
    proverb_applied: str   # Which proverb informed the decision


def check_identity(ctx: DecisionContext) -> DecisionResult:
    """Question 1: Am I authorized to do this?

    Algorithmic check: Is target_path within owned_paths?
    """
    if ctx.target_path is None:
        return DecisionResult(
            decision=Decision.PROCEED,
            question="Am I authorized to do this?",
            evidence="No file modification required",
            proverb_applied="verify"
        )

    target = Path(ctx.target_path)
    for owned in ctx.owned_paths:
        owned_path = Path(owned)
        # Check if target is under an owned directory (supports globs like "specs/*")
        if owned.endswith("*"):
            parent = Path(owned.rstrip("/*"))
            try:
                target.relative_to(parent)
                return DecisionResult(
                    decision=Decision.PROCEED,
                    question="Am I authorized to do this?",
                    evidence=f"{ctx.target_path} is under owned path {owned}",
                    proverb_applied="whole"
                )
            except ValueError:
                continue
        elif str(target) == str(owned_path) or target == owned_path:
            return DecisionResult(
                decision=Decision.PROCEED,
                question="Am I authorized to do this?",
                evidence=f"{ctx.target_path} is explicitly owned",
                proverb_applied="whole"
            )

    return DecisionResult(
        decision=Decision.STOP,
        question="Am I authorized to do this?",
        evidence=f"{ctx.target_path} is NOT in owned paths: {ctx.owned_paths}",
        proverb_applied="whole"
    )


def check_memory(ctx: DecisionContext) -> DecisionResult:
    """Question 2: Have I or others failed at this before?

    Algorithmic check: Is this action in the known_failures list?
    """
    if not ctx.known_failures:
        return DecisionResult(
            decision=Decision.PROCEED,
            question="Have I or others failed at this before?",
            evidence="No known failures for this action",
            proverb_applied="remember"
        )

    action_lower = ctx.action.lower()
    for failure in ctx.known_failures:
        if failure.lower() in action_lower or action_lower in failure.lower():
            return DecisionResult(
                decision=Decision.INVESTIGATE,
                question="Have I or others failed at this before?",
                evidence=f"Similar action failed before: {failure}",
                proverb_applied="remember"
            )

    return DecisionResult(
        decision=Decision.PROCEED,
        question="Have I or others failed at this before?",
        evidence=f"Action '{ctx.action}' not in known failures",
        proverb_applied="remember"
    )


def check_awareness(ctx: DecisionContext) -> DecisionResult:
    """Question 3: Am I still solving the right problem?

    Algorithmic check: Does action relate to original_goal?
    """
    if not ctx.original_goal:
        return DecisionResult(
            decision=Decision.INVESTIGATE,
            question="Am I still solving the right problem?",
            evidence="No original goal defined - cannot verify alignment",
            proverb_applied="goal"
        )

    # Simple keyword overlap check - agents can implement more sophisticated
    action_words = set(ctx.action.lower().split())
    goal_words = set(ctx.original_goal.lower().split())

    # Remove common words
    stop_words = {"the", "a", "an", "to", "for", "in", "on", "with", "and", "or"}
    action_words -= stop_words
    goal_words -= stop_words

    overlap = action_words & goal_words
    if overlap:
        return DecisionResult(
            decision=Decision.PROCEED,
            question="Am I still solving the right problem?",
            evidence=f"Action relates to goal via: {overlap}",
            proverb_applied="goal"
        )

    return DecisionResult(
        decision=Decision.INVESTIGATE,
        question="Am I still solving the right problem?",
        evidence=f"Action '{ctx.action}' may have drifted from goal '{ctx.original_goal}'",
        proverb_applied="goal"
    )


def check_governance(ctx: DecisionContext) -> DecisionResult:
    """Question 4: Does this violate any hard constraints?

    Algorithmic check: Is action in hard_constraints list?
    """
    if not ctx.hard_constraints:
        return DecisionResult(
            decision=Decision.PROCEED,
            question="Does this violate any hard constraints?",
            evidence="No hard constraints defined",
            proverb_applied="fail"
        )

    action_lower = ctx.action.lower()
    for constraint in ctx.hard_constraints:
        if constraint.lower() in action_lower:
            return DecisionResult(
                decision=Decision.STOP,
                question="Does this violate any hard constraints?",
                evidence=f"Action violates constraint: {constraint}",
                proverb_applied="fail"
            )

    return DecisionResult(
        decision=Decision.PROCEED,
        question="Does this violate any hard constraints?",
        evidence=f"Action does not violate {len(ctx.hard_constraints)} constraints",
        proverb_applied="fail"
    )


def evaluate_action(ctx: DecisionContext) -> tuple[Decision, list[DecisionResult]]:
    """Run all four questions and return aggregate decision.

    Returns:
        tuple of (final_decision, list of individual results)

    Decision logic:
        - Any STOP → STOP (hard no)
        - Any ESCALATE → ESCALATE (need human)
        - Any INVESTIGATE and no STOP → INVESTIGATE (need more info)
        - All PROCEED → PROCEED (go ahead)
    """
    results = [
        check_identity(ctx),
        check_memory(ctx),
        check_awareness(ctx),
        check_governance(ctx),
    ]

    decisions = [r.decision for r in results]

    if Decision.STOP in decisions:
        return Decision.STOP, results
    if Decision.ESCALATE in decisions:
        return Decision.ESCALATE, results
    if Decision.INVESTIGATE in decisions:
        return Decision.INVESTIGATE, results
    return Decision.PROCEED, results


def format_decision_trace(ctx: DecisionContext, results: list[DecisionResult]) -> str:
    """Format decision results for embedding in agent trace.

    This is the algorithmic proof that the agent asked the Four Questions.
    """
    lines = [
        "## Decision Trace",
        f"Action: {ctx.action}",
        f"Target: {ctx.target_path or 'N/A'}",
        "",
        "### Four Questions Check",
    ]

    for i, result in enumerate(results, 1):
        status = "✅" if result.decision == Decision.PROCEED else "⚠️" if result.decision == Decision.INVESTIGATE else "❌"
        lines.append(f"{i}. {status} {result.question}")
        lines.append(f"   Evidence: {result.evidence}")
        lines.append(f"   Proverb: \"{get_proverb(result.proverb_applied)}\"")
        lines.append("")

    return "\n".join(lines)
