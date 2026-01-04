# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""
Motus CLI Commands Module.

Refactored CLI commands extracted from the monolithic cli.py.
Each command gets its own module for maintainability and testability.

PERFORMANCE: Lazy imports to avoid loading Rich/Markdown during package init.
Commands load their dependencies only when actually invoked.
"""

# PERFORMANCE: All imports deferred via __getattr__ to avoid loading
# Rich, Markdown, Pydantic models at package init time

__all__ = [
    # Models
    "ThinkingEvent",
    "ToolEvent",
    "TaskEvent",
    "FileChange",
    "SessionStats",
    "SessionInfo",
    "RISK_LEVELS",
    "DESTRUCTIVE_PATTERNS",
    # Utilities
    "assess_risk",
    "extract_project_path",
    "format_age",
    "get_risk_style",
    "parse_content_block",
    # Commands
    "list_sessions",
    "find_claude_sessions",
    "find_active_session",
    "summary_command",
    "analyze_session",
    "extract_decisions",
    "generate_agent_context",
    "context_command",
    "prune_command",
    "archive_session",
    "delete_session",
    "install_hooks_command",
    "uninstall_hooks_command",
    "get_mc_hook_config",
    "install_command",
    "init_command",
]


def __getattr__(name):
    """Lazy load command modules and their exports."""
    # Models
    if name in (
        "ThinkingEvent",
        "ToolEvent",
        "TaskEvent",
        "FileChange",
        "SessionStats",
        "SessionInfo",
        "RISK_LEVELS",
        "DESTRUCTIVE_PATTERNS",
    ):
        from .models import (
            DESTRUCTIVE_PATTERNS,
            RISK_LEVELS,
            FileChange,
            SessionInfo,
            SessionStats,
            TaskEvent,
            ThinkingEvent,
            ToolEvent,
        )

        return {
            "ThinkingEvent": ThinkingEvent,
            "ToolEvent": ToolEvent,
            "TaskEvent": TaskEvent,
            "FileChange": FileChange,
            "SessionStats": SessionStats,
            "SessionInfo": SessionInfo,
            "RISK_LEVELS": RISK_LEVELS,
            "DESTRUCTIVE_PATTERNS": DESTRUCTIVE_PATTERNS,
        }[name]

    # Utilities
    elif name in (
        "assess_risk",
        "extract_project_path",
        "format_age",
        "get_risk_style",
        "parse_content_block",
    ):
        from .utils import (
            assess_risk,
            extract_project_path,
            format_age,
            get_risk_style,
            parse_content_block,
        )

        return {
            "assess_risk": assess_risk,
            "extract_project_path": extract_project_path,
            "format_age": format_age,
            "get_risk_style": get_risk_style,
            "parse_content_block": parse_content_block,
        }[name]

    # List command
    elif name in ("list_sessions", "find_claude_sessions", "find_active_session"):
        from .list_cmd import find_active_session, find_claude_sessions, list_sessions

        return {
            "list_sessions": list_sessions,
            "find_claude_sessions": find_claude_sessions,
            "find_active_session": find_active_session,
        }[name]

    # Summary command
    elif name in (
        "summary_command",
        "analyze_session",
        "extract_decisions",
        "generate_agent_context",
    ):
        from .summary_cmd import (
            analyze_session,
            extract_decisions,
            generate_agent_context,
            summary_command,
        )

        return {
            "summary_command": summary_command,
            "analyze_session": analyze_session,
            "extract_decisions": extract_decisions,
            "generate_agent_context": generate_agent_context,
        }[name]

    # Context command
    elif name == "context_command":
        from .context_cmd import context_command

        return context_command

    # Prune command
    elif name in ("prune_command", "archive_session", "delete_session"):
        from .prune_cmd import archive_session, delete_session, prune_command

        return {
            "prune_command": prune_command,
            "archive_session": archive_session,
            "delete_session": delete_session,
        }[name]

    # Hooks command
    elif name in ("install_hooks_command", "uninstall_hooks_command", "get_mc_hook_config"):
        from .hooks_cmd import (
            get_mc_hook_config,
            install_hooks_command,
            uninstall_hooks_command,
        )

        return {
            "install_hooks_command": install_hooks_command,
            "uninstall_hooks_command": uninstall_hooks_command,
            "get_mc_hook_config": get_mc_hook_config,
        }[name]

    # Init command
    elif name == "install_command":
        from .install_cmd import install_command

        return install_command

    # Init command
    elif name == "init_command":
        from .init_cmd import init_command

        return init_command

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
