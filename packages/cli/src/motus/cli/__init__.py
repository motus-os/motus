# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""
CLI module for Motus.

This module provides backward compatibility by re-exporting all public symbols
from the split modules. Code importing from motus.cli will continue to work.

PERFORMANCE: All imports are lazy-loaded via __getattr__ to avoid
loading heavy dependencies at package init time.
"""

__all__ = [
    # Data structures
    "ThinkingEvent",
    "ToolEvent",
    "TaskEvent",
    "ErrorEvent",
    "FileChange",
    "SessionStats",
    "SessionInfo",
    # Event conversions
    "unified_session_to_session_info",
    "unified_event_to_legacy",
    "get_last_error",
    "get_session_errors",
    # Validators
    "parse_content_block",
    "parse_transcript_line",
    "extract_decisions",
    # Formatters
    "get_risk_style",
    "format_thinking",
    "format_error",
    "format_task",
    "format_tool",
    "create_header",
    "create_summary_table",
    # Commands
    "watch_session",
    "analyze_session",
    "generate_agent_context",
    "context_command",
    "summary_command",
    "teleport_command",
    "watch_command",
    "list_sessions",
    # Core utilities
    "is_claude_process_running",
    "archive_session",
    "delete_session",
    "get_running_claude_projects",
    "find_sessions",
    "find_claude_sessions",
    "find_active_session",
    "find_sdk_traces",
    "get_orchestrator",
    "EventType",
    "UnifiedEvent",
    "UnifiedSession",
    "main",
    # Shared utilities
    "assess_risk",
    "redact_secrets",
]


def __getattr__(name):
    """Lazy load CLI components."""
    # Commands
    if name in ("context_command", "summary_command", "teleport_command", "list_sessions"):
        from .commands import context_command, list_sessions, summary_command, teleport_command

        return {
            "context_command": context_command,
            "summary_command": summary_command,
            "teleport_command": teleport_command,
            "list_sessions": list_sessions,
        }[name]

    # Core utilities
    elif name in (
        "main",
        "archive_session",
        "delete_session",
        "find_active_session",
        "find_claude_sessions",
        "find_sdk_traces",
        "find_sessions",
        "get_orchestrator",
        "get_running_claude_projects",
        "is_claude_process_running",
        "EventType",
        "UnifiedEvent",
        "UnifiedSession",
    ):
        from .core import (
            EventType,
            UnifiedEvent,
            UnifiedSession,
            archive_session,
            delete_session,
            find_active_session,
            find_claude_sessions,
            find_sdk_traces,
            find_sessions,
            get_orchestrator,
            get_running_claude_projects,
            is_claude_process_running,
            main,
        )

        return {
            "main": main,
            "archive_session": archive_session,
            "delete_session": delete_session,
            "find_active_session": find_active_session,
            "find_claude_sessions": find_claude_sessions,
            "find_sdk_traces": find_sdk_traces,
            "find_sessions": find_sessions,
            "get_orchestrator": get_orchestrator,
            "get_running_claude_projects": get_running_claude_projects,
            "is_claude_process_running": is_claude_process_running,
            "EventType": EventType,
            "UnifiedEvent": UnifiedEvent,
            "UnifiedSession": UnifiedSession,
        }[name]

    # Formatters
    elif name in (
        "create_header",
        "create_summary_table",
        "format_error",
        "format_task",
        "format_thinking",
        "format_tool",
        "get_risk_style",
    ):
        from .formatters import (
            create_header,
            create_summary_table,
            format_error,
            format_task,
            format_thinking,
            format_tool,
            get_risk_style,
        )

        return {
            "create_header": create_header,
            "create_summary_table": create_summary_table,
            "format_error": format_error,
            "format_task": format_task,
            "format_thinking": format_thinking,
            "format_tool": format_tool,
            "get_risk_style": get_risk_style,
        }[name]

    # Output
    elif name in (
        "ErrorEvent",
        "FileChange",
        "SessionInfo",
        "SessionStats",
        "TaskEvent",
        "ThinkingEvent",
        "ToolEvent",
        "get_last_error",
        "get_session_errors",
        "unified_event_to_legacy",
        "unified_session_to_session_info",
    ):
        from .output import (
            ErrorEvent,
            FileChange,
            SessionInfo,
            SessionStats,
            TaskEvent,
            ThinkingEvent,
            ToolEvent,
            get_last_error,
            get_session_errors,
            unified_event_to_legacy,
            unified_session_to_session_info,
        )

        return {
            "ErrorEvent": ErrorEvent,
            "FileChange": FileChange,
            "SessionInfo": SessionInfo,
            "SessionStats": SessionStats,
            "TaskEvent": TaskEvent,
            "ThinkingEvent": ThinkingEvent,
            "ToolEvent": ToolEvent,
            "get_last_error": get_last_error,
            "get_session_errors": get_session_errors,
            "unified_event_to_legacy": unified_event_to_legacy,
            "unified_session_to_session_info": unified_session_to_session_info,
        }[name]

    # Validators
    elif name in ("extract_decisions", "parse_content_block", "parse_transcript_line"):
        from .validators import extract_decisions, parse_content_block, parse_transcript_line

        return {
            "extract_decisions": extract_decisions,
            "parse_content_block": parse_content_block,
            "parse_transcript_line": parse_transcript_line,
        }[name]

    # Watch command
    elif name in ("analyze_session", "generate_agent_context", "watch_command", "watch_session"):
        from .watch_cmd import analyze_session, generate_agent_context, watch_command, watch_session

        return {
            "analyze_session": analyze_session,
            "generate_agent_context": generate_agent_context,
            "watch_command": watch_command,
            "watch_session": watch_session,
        }[name]

    # Shared utilities from commands.utils
    elif name in ("assess_risk", "redact_secrets"):
        try:
            from ..commands.utils import assess_risk, redact_secrets
        except ImportError:
            from commands.utils import assess_risk, redact_secrets
        return {"assess_risk": assess_risk, "redact_secrets": redact_secrets}[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
