# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Context hints for agent injection."""

from .checkpoint import load_checkpoints
from .memory import get_file_memories
from .test_harness import detect_test_harness, find_related_tests


def get_context_hints(files: list[str]) -> str:
    """Get context hints for files being edited.

    This is what gets injected into the agent's context via hooks.
    """
    hints = []

    for file in files:
        # Get related tests
        related_tests = find_related_tests(file)
        if related_tests:
            hints.append(f"• Related tests for {file}: {', '.join(related_tests)}")

        # Get memories for this file
        memories = get_file_memories(file)
        if memories:
            recent = memories[0]
            hints.append(f"• Memory ({file}): {recent.event} - {recent.details}")

    # Get test harness
    harness = detect_test_harness()
    if harness["test_command"]:
        hints.append(f"• Test command: {harness['test_command']}")

    # Get checkpoints
    checkpoints = load_checkpoints()
    if checkpoints:
        hints.append(f"• Last checkpoint: {checkpoints[0].id} ({checkpoints[0].message})")

    if hints:
        return "[Motus Context]\n" + "\n".join(hints)
    return ""
