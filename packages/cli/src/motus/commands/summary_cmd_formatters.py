# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Formatting and decision extraction helpers for summary command."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from rich.markdown import Markdown
from rich.panel import Panel

logger = logging.getLogger(__name__)
MAX_DECISION_FILE_BYTES = int(os.environ.get("MC_DECISIONS_MAX_BYTES", "5242880"))

# Decision markers - used across all sources
DECISION_MARKERS = [
    "I'll ",
    "I will ",
    "I decided ",
    "I'm going to ",
    "The best approach ",
    "I should ",
    "Let's ",
    "I chose ",
    "Decision:",
    "Approach:",
    "Strategy:",
]


def _extract_decision_from_text(text: str, decisions: list[str]) -> None:
    """Helper to extract decisions from a text block."""
    for marker in DECISION_MARKERS:
        if marker in text:
            sentences = text.replace("\n", " ").split(". ")
            for sentence in sentences:
                if marker in sentence and len(sentence) < 200:
                    decisions.append(sentence.strip())
                    break
            break


def extract_decisions(file_path: Path, source: str = "claude") -> list[str]:
    """Extract decision points from a session transcript."""
    decisions = []

    try:
        try:
            if file_path.stat().st_size > MAX_DECISION_FILE_BYTES:
                logger.warning("Decision extraction skipped (file too large): %s", file_path)
                return []
        except OSError as e:
            logger.warning("Decision extraction failed to stat file %s: %s", file_path, e)
            return []

        if source == "gemini":
            with open(file_path, "r") as f:
                data = json.load(f)

            for msg in data.get("messages", []):
                if msg.get("type") == "gemini":
                    for thought in msg.get("thoughts", []):
                        desc = thought.get("description", "")
                        _extract_decision_from_text(desc, decisions)
                    content = msg.get("content", "")
                    if content:
                        _extract_decision_from_text(content, decisions)
        else:
            with open(file_path, "r") as f:
                for line in f:
                    try:
                        event = json.loads(line)

                        if source == "codex":
                            if event.get("type") == "response_item":
                                payload = event.get("payload", {})
                                if payload.get("type") == "message":
                                    content = payload.get("content", [])
                                    if isinstance(content, list):
                                        for item in content:
                                            if (
                                                isinstance(item, dict)
                                                and item.get("type") == "text"
                                            ):
                                                _extract_decision_from_text(
                                                    item.get("text", ""), decisions
                                                )
                                    elif isinstance(content, str):
                                        _extract_decision_from_text(content, decisions)
                        else:
                            if event.get("type") == "assistant":
                                for block in event.get("message", {}).get("content", []):
                                    if block.get("type") == "thinking":
                                        text = block.get("thinking", "")
                                        _extract_decision_from_text(text, decisions)

                    except json.JSONDecodeError:
                        continue

    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.warning("Decision extraction failed for %s: %s", file_path, e)
        return []

    seen = set()
    unique = []
    for decision in decisions:
        if decision not in seen:
            seen.add(decision)
            unique.append(decision)

    return unique[:10]


def format_summary_panel(context: str, session_id: str) -> Panel:
    """Build the Rich panel for a session summary."""
    return Panel(
        Markdown(context),
        title=f"Session Summary: {session_id[:12]}",
        border_style="blue",
    )


def save_summary(context: str, state_dir: Path) -> Path:
    """Persist the latest summary to the state directory."""
    state_dir.mkdir(exist_ok=True)
    summary_file = state_dir / "latest_summary.md"
    summary_file.write_text(context)
    return summary_file
