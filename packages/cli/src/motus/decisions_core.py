# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Core decision extraction and formatting helpers."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

# Patterns that indicate a decision was made
_DECISION_SUBJECTS = [
    r"I(?:'ve|'ll| will| have)?",
    r"we(?:'ve|'ll| will| have)?",
]
_DECISION_ACTIONS = (
    r"(?:decided to|chose to|chosen to|opted to|going to|will)"
)

DECISION_PATTERNS = [
    # Explicit decision language
    *[rf"{subject} {_DECISION_ACTIONS}" for subject in _DECISION_SUBJECTS],
    r"(?:decided|chose|chosen|opted) to (?:use|implement|add|create|remove|change|update|fix|keep|skip|avoid)",
    r"(?:using|implementing|adding|creating|removing|changing|updating|fixing|keeping|skipping|avoiding) .+? instead of",
    r"(?:rather than|instead of|over) .+?, (?:I|we)(?:'ll|'ve| will| have)?",
    # Reasoning indicators
    r"because .+? (?:is|are|was|were|will be|would be) (?:better|simpler|cleaner|faster|safer|more)",
    r"(?:this|that) (?:is|would be) (?:better|simpler|cleaner|faster|safer|more)",
    r"(?:the reason|reasoning) (?:is|being) that",
    # Comparison decisions
    r"(?:prefer|preferable|better) (?:to use|to have|than)",
    r"(?:should|shouldn't|will|won't) (?:use|add|include|create|have)",
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in DECISION_PATTERNS]
MAX_DECISION_TEXT_CHARS = int(os.environ.get("MC_DECISION_TEXT_MAX", "4000"))


@dataclass
class Decision:
    """A decision made during a session."""

    timestamp: str
    decision: str
    reasoning: str = ""
    files_affected: list[str] = field(default_factory=list)
    reversible: bool = True
    context: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp,
            "decision": self.decision,
            "reasoning": self.reasoning,
            "files_affected": self.files_affected,
            "reversible": self.reversible,
            "context": self.context,
        }


@dataclass
class DecisionLedger:
    """Collection of decisions from a session."""

    session_id: str
    decisions: list[Decision] = field(default_factory=list)
    timestamp: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "session_id": self.session_id,
            "decisions": [d.to_dict() for d in self.decisions],
            "timestamp": self.timestamp,
        }


def extract_decision_from_text(text: str, context: str = "") -> Optional[Decision]:
    """Extract a decision from a text block if one exists."""
    if len(text) > MAX_DECISION_TEXT_CHARS:
        text = text[:MAX_DECISION_TEXT_CHARS]
    for pattern in COMPILED_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue

        start = text.rfind(".", 0, match.start()) + 1
        end = text.find(".", match.end())
        if end == -1:
            end = len(text)

        decision_text = text[start:end].strip()
        if len(decision_text) < 10:
            continue

        reasoning = ""
        because_match = re.search(
            r"because (.+?)(?:\.|$)", text[match.start() :], re.IGNORECASE
        )
        if because_match:
            reasoning = because_match.group(1).strip()

        files = extract_file_references(text)

        return Decision(
            timestamp=datetime.now().isoformat(),
            decision=decision_text[:200],
            reasoning=reasoning[:200] if reasoning else "",
            files_affected=files[:5],
            reversible=True,
            context=context[:100] if context else "",
        )

    return None


def extract_file_references(text: str) -> list[str]:
    """Extract file path references from text."""
    files: list[str] = []

    patterns = [
        r"[\w/.-]+\.(?:py|js|ts|tsx|jsx|json|yaml|yml|md|txt|sh|css|scss|html)",
        r"(?:src|lib|tests?|components?|utils?|config)/[\w/.-]+",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            if match not in files and len(match) < 100:
                files.append(match)

    return files


def format_decision_ledger(ledger: DecisionLedger) -> str:
    """Format decision ledger as a readable string."""
    lines = []

    if not ledger.decisions:
        lines.append("No decisions found in session.")
        lines.append("")
        lines.append(f"Session: {ledger.session_id[:8]}...")
        return "\n".join(lines)

    lines.append(f"Decisions from session {ledger.session_id[:8]}...")
    lines.append("")

    for i, decision in enumerate(ledger.decisions, 1):
        lines.append(f"{i}. {decision.decision}")
        if decision.reasoning:
            lines.append(f"   Reasoning: {decision.reasoning}")
        if decision.files_affected:
            lines.append(f"   Files: {', '.join(decision.files_affected)}")
        lines.append("")

    lines.append(f"Total: {len(ledger.decisions)} decision(s)")
    return "\n".join(lines)


def format_decisions_for_export(ledger: DecisionLedger) -> str:
    """Format decisions for CLAUDE.md or PR description."""
    lines = ["## Decisions Made", ""]

    if not ledger.decisions:
        lines.append("_No significant decisions recorded._")
        return "\n".join(lines)

    for decision in ledger.decisions:
        lines.append(f"- **{decision.decision}**")
        if decision.reasoning:
            lines.append(f"  - Reasoning: {decision.reasoning}")
        if decision.files_affected:
            files_str = ", ".join(f"`{f}`" for f in decision.files_affected)
            lines.append(f"  - Files affected: {files_str}")

    return "\n".join(lines)
