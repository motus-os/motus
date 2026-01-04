# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Intent parsing helpers."""

from __future__ import annotations

from pathlib import Path

from .intent_models import Intent
from .logging import get_logger
from .orchestrator import get_orchestrator
from .protocols import Source
from .schema.events import EventType, ParsedEvent

logger = get_logger(__name__)


def _determine_source(session_path: Path) -> Source:
    path_str = str(session_path)

    if "/.claude/" in path_str:
        return Source.CLAUDE
    if "/.codex/" in path_str:
        return Source.CODEX
    if "/.gemini/" in path_str:
        return Source.GEMINI

    logger.debug("Could not determine source from path, defaulting to Claude", path=path_str)
    return Source.CLAUDE


def parse_intent(session_path: Path) -> Intent:
    source = _determine_source(session_path)

    orchestrator = get_orchestrator()
    builder = orchestrator.get_builder(source)

    if not builder:
        logger.warning("Could not get builder for source", source=source.value)
        return Intent(task="No task specified")

    events = builder.parse_events_validated(session_path)
    user_messages = [e for e in events if e.event_type == EventType.USER_MESSAGE]

    task = "No task specified"
    if user_messages:
        first_message = user_messages[0]
        task = _extract_task_from_prompt(first_message.content)

    constraints = _extract_constraints(user_messages[0].content if user_messages else "")
    out_of_scope = _infer_out_of_scope(constraints)
    priority_files = _identify_priority_files(events)

    return Intent(
        task=task,
        constraints=constraints,
        out_of_scope=out_of_scope,
        priority_files=priority_files,
    )


def _extract_task_from_prompt(prompt: str) -> str:
    prompt = prompt.strip()

    replacements = [
        ("I want to ", ""),
        ("I need to ", ""),
        ("Can you ", ""),
        ("Could you ", ""),
        ("Please ", ""),
        ("Help me ", ""),
        ("I'd like to ", ""),
        ("Let's ", ""),
    ]

    task = prompt
    for old, new in replacements:
        if task.startswith(old):
            task = new + task[len(old) :]
            break

    if task:
        task = task[0].upper() + task[1:]

    if len(task) > 150:
        task = task[:147] + "..."

    return task


def _extract_constraints(prompt: str) -> list[str]:
    constraints: list[str] = []

    sentences = prompt.replace("\n", ". ").split(". ")

    constraint_patterns = [
        "don't ",
        "do not ",
        "make sure ",
        "ensure ",
        "keep ",
        "avoid ",
        "without ",
        "must not ",
        "shouldn't ",
        "maintain ",
    ]

    for sentence in sentences:
        sentence_lower = sentence.lower().strip()
        for pattern in constraint_patterns:
            if pattern in sentence_lower:
                constraint = sentence.strip()
                if constraint and len(constraint) > 10:
                    constraints.append(constraint[:100])
                break

    return constraints


def _infer_out_of_scope(constraints: list[str]) -> list[str]:
    out_of_scope: list[str] = []

    patterns = [
        ("don't modify", "Modifying"),
        ("don't add", "Adding"),
        ("don't change", "Changing"),
        ("don't refactor", "Refactoring"),
        ("avoid", ""),
        ("without", ""),
        ("keep.*minimal", "Large-scale changes"),
    ]

    for constraint in constraints:
        constraint_lower = constraint.lower()
        for pattern, replacement in patterns:
            if pattern in constraint_lower:
                if replacement:
                    parts = constraint_lower.split(pattern)
                    if len(parts) > 1:
                        what = parts[1].strip().split()[0:3]
                        scope_item = replacement + " " + " ".join(what)
                        out_of_scope.append(scope_item.strip())
                        break

    return out_of_scope


def _identify_priority_files(events: list[ParsedEvent]) -> list[str]:
    files_modified: set[str] = set()

    for event in events:
        if event.event_type == EventType.TOOL_USE:
            if event.tool_name in ("Edit", "Write") and event.file_path:
                files_modified.add(event.file_path)
            elif event.file_path and event.content.startswith("Modified:"):
                files_modified.add(event.file_path)

    priority = list(files_modified)
    return priority[:10]
