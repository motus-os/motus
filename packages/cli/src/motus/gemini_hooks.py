#!/usr/bin/env python3
# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""
Motus Gemini Hooks

These hooks integrate Motus with Gemini agents to inject observed context
back into the session - completing the feedback loop.

Usage:
    echo '{"cwd": "/path/to/project"}' | python3 -m motus.gemini_hooks
"""

import json
import sys
from pathlib import Path

from .config import config
from .hooks_context import (
    extract_decisions_from_session,
    extract_file_patterns,
    get_project_sessions,
)
from .logging import get_logger

logger = get_logger(__name__)

MC_STATE_DIR = config.paths.state_dir
GEMINI_DIR = Path.home() / ".gemini"  # Default Gemini dir


def generate_context_injection(cwd: str) -> str:
    """Generate context to inject into Gemini session."""
    # Pass gemini_dir explicitly
    sessions = get_project_sessions(cwd, max_age_hours=48, gemini_dir=GEMINI_DIR)

    if not sessions:
        return ""  # No recent sessions, no context to inject

    context_parts = []
    context_parts.append("## Motus Context (Recent Activity)")
    context_parts.append("Context observed from recent development sessions (Claude, Gemini, etc.):")
    context_parts.append("")

    # Collect decisions from recent sessions
    all_decisions: list[dict] = []
    all_files: dict[str, int] = {}

    for session in sessions[:5]:  # Last 5 sessions (more than Claude as Gemini has larger context window)
        decisions = extract_decisions_from_session(session["path"])
        all_decisions.extend(decisions)

        files = extract_file_patterns(session["path"])
        for f, count in files.items():
            all_files[f] = all_files.get(f, 0) + count

    # Add decisions section
    if all_decisions:
        context_parts.append("### Recent Decisions")
        # Deduplicate by text
        seen_decisions = set()
        for d in all_decisions[:8]:
            text = d["decision"]
            if text in seen_decisions:
                continue
            seen_decisions.add(text)

            entry = f"- {text}"
            if d.get("reasoning"):
                entry += f" (Reasoning: {d['reasoning']})"
            context_parts.append(entry)
        context_parts.append("")

    # Add frequently modified files
    if all_files:
        sorted_files = sorted(all_files.items(), key=lambda x: x[1], reverse=True)
        context_parts.append("### Frequently Modified Files")
        for f, count in sorted_files[:8]:
            # Shorten path for display
            short_path = f.replace(cwd, ".") if cwd in f else f
            context_parts.append(f"- {short_path} ({count} edits)")
        context_parts.append("")

    # Check for latest summary
    summary_file = MC_STATE_DIR / "latest_summary.md"
    if summary_file.exists():
        try:
            content = summary_file.read_text(encoding="utf-8")
            context_parts.append("### Latest Session Summary")
            context_parts.append(content[:1000] + ("..." if len(content) > 1000 else ""))
            context_parts.append("")
        except Exception:
            pass

    return "\n".join(context_parts)


def main():
    """Main entry point for Gemini hooks."""
    try:
        # Read hook input from stdin
        if not sys.stdin.isatty():
            hook_input = json.load(sys.stdin)
        else:
            # Fallback for testing with arguments
            hook_input = {"cwd": sys.argv[1] if len(sys.argv) > 1 else "."}

        cwd = hook_input.get("cwd", ".")

        # Generate and output context
        context = generate_context_injection(cwd)
        if context:
            print(context)

    except Exception as e:
        logger.error(
            "Error in Gemini hook",
            error_type=type(e).__name__,
            error=str(e),
            exc_info=True,
        )
        sys.exit(1)

if __name__ == "__main__":
    main()
