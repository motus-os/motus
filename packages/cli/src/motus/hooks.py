#!/usr/bin/env python3
# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""
Motus Claude Code Hooks

These hooks integrate Motus with Claude Code to inject observed context
back into Claude sessions - completing the feedback loop.

Install with: motus install-hooks
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

from .config import config
from .hooks_context import (
    MAX_SESSION_SIZE_BYTES,
)
from .hooks_context import (
    extract_decisions_from_session as _extract_decisions_from_session,
)
from .hooks_context import (
    extract_file_patterns as _extract_file_patterns,
)
from .hooks_context import (
    get_project_sessions as _get_project_sessions,
)
from .logging import get_logger

logger = get_logger(__name__)


MC_STATE_DIR = config.paths.state_dir
CLAUDE_DIR = config.paths.claude_dir
GEMINI_DIR = Path.home() / ".gemini"


def get_project_sessions(cwd: str, max_age_hours: int = 24) -> list:
    """Find recent Motus sessions for a project directory."""
    return _get_project_sessions(
        cwd,
        max_age_hours=max_age_hours,
        claude_dir=CLAUDE_DIR,
        mc_state_dir=MC_STATE_DIR,
        gemini_dir=GEMINI_DIR,
    )


def extract_decisions_from_session(session_path: Path, max_decisions: int = 5) -> list:
    """Extract key decisions from a session transcript."""
    return _extract_decisions_from_session(
        session_path,
        max_decisions=max_decisions,
        max_session_size_bytes=MAX_SESSION_SIZE_BYTES,
    )


def extract_file_patterns(session_path: Path) -> dict:
    """Extract frequently modified files from a session."""
    return _extract_file_patterns(
        session_path,
        max_session_size_bytes=MAX_SESSION_SIZE_BYTES,
    )


def generate_context_injection(cwd: str) -> str:
    """Generate context to inject into Claude session."""
    sessions = get_project_sessions(cwd, max_age_hours=48)

    if not sessions:
        return ""  # No recent sessions, no context to inject

    context_parts = []
    context_parts.append("<mc-context>")
    context_parts.append("## Motus-Observed Context (from recent sessions)")
    context_parts.append("")

    # Collect decisions from recent sessions
    all_decisions: list[str] = []
    all_files: dict[str, int] = {}

    for session in sessions[:3]:  # Last 3 sessions
        decisions = extract_decisions_from_session(session["path"])
        all_decisions.extend(decisions)

        files = extract_file_patterns(session["path"])
        for f, count in files.items():
            all_files[f] = all_files.get(f, 0) + count

    # Add decisions section
    if all_decisions:
        context_parts.append("### Recent Decisions")
        for d in all_decisions[:5]:
            decision_text = d["decision"]
            if d.get("reasoning"):
                decision_text += f" ({d['reasoning'][:100]})"
            context_parts.append(f"- {decision_text}")
        context_parts.append("")

    # Add frequently modified files
    if all_files:
        sorted_files = sorted(all_files.items(), key=lambda x: x[1], reverse=True)
        context_parts.append("### Hot Files (frequently modified)")
        for f, count in sorted_files[:5]:
            # Shorten path for display
            short_path = f.replace(cwd, ".") if cwd in f else f
            context_parts.append(f"- {short_path} ({count} edits)")
        context_parts.append("")

    # Check for latest summary
    summary_file = MC_STATE_DIR / "latest_summary.md"
    if summary_file.exists():
        try:
            age = datetime.now() - datetime.fromtimestamp(summary_file.stat().st_mtime)
        except OSError as e:
            logger.warning(
                "Failed to stat summary file",
                summary_file=str(summary_file),
                error_type=type(e).__name__,
                error=str(e),
            )
        else:
            if age < timedelta(hours=24):
                context_parts.append("### Session Summary Available")
                context_parts.append("Run `motus summary` to see detailed session analysis")
                context_parts.append("")

    context_parts.append("</mc-context>")

    return "\n".join(context_parts)


def session_start_hook():
    """
    Claude Code SessionStart hook.

    Reads session metadata from stdin and outputs context to stdout.
    """
    try:
        # Read hook input
        hook_input = json.load(sys.stdin)
        cwd = hook_input.get("cwd", "")

        # Generate and output context
        context = generate_context_injection(cwd)
        if context:
            print(context)

        sys.exit(0)
    except json.JSONDecodeError as e:
        logger.warning(
            "Invalid JSON from hook input",
            error_type=type(e).__name__,
            error=str(e),
        )
        sys.exit(0)  # Don't block Claude
    except Exception as e:
        logger.error(
            "Hook error in session_start",
            error_type=type(e).__name__,
            error=str(e),
            exc_info=True,
        )
        sys.exit(0)  # Don't block Claude


def user_prompt_hook():
    """
    Claude Code UserPromptSubmit hook.

    Can inject context based on what the user is asking.
    """
    try:
        hook_input = json.load(sys.stdin)
        prompt = hook_input.get("prompt", "")
        cwd = hook_input.get("cwd", "")

        # Check for keywords that might benefit from Motus context
        context_keywords = [
            "continue",
            "resume",
            "last session",
            "where was I",
            "what did",
            "why did",
            "decision",
            "remember",
        ]

        should_inject = any(kw in prompt.lower() for kw in context_keywords)

        if should_inject:
            context = generate_context_injection(cwd)
            if context:
                print(context)

        sys.exit(0)
    except json.JSONDecodeError as e:
        logger.warning(
            "Invalid JSON from hook input",
            error_type=type(e).__name__,
            error=str(e),
        )
        sys.exit(0)  # Don't block Claude
    except Exception as e:
        logger.error(
            "Hook error in user_prompt",
            error_type=type(e).__name__,
            error=str(e),
            exc_info=True,
        )
        sys.exit(0)  # Don't block Claude


def get_hook_config() -> dict:
    """Generate Claude Code hooks configuration for Motus."""
    return {
        "hooks": {
            "SessionStart": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": 'python3 -c "from motus.hooks import session_start_hook; session_start_hook()"',
                            "timeout": 5000,
                        }
                    ],
                }
            ],
            "UserPromptSubmit": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": 'python3 -c "from motus.hooks import user_prompt_hook; user_prompt_hook()"',
                            "timeout": 3000,
                        }
                    ],
                }
            ],
        }
    }


if __name__ == "__main__":
    # For testing
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "session_start":
            session_start_hook()
        elif sys.argv[1] == "user_prompt":
            user_prompt_hook()
        elif sys.argv[1] == "config":
            print(json.dumps(get_hook_config(), indent=2))
    else:
        # Test context generation
        print(generate_context_injection("."))
