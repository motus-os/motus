# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Summary generation command."""

from __future__ import annotations

import importlib
import json
import logging
from typing import Optional

from .models import SessionInfo, SessionStats
from .summary_cmd_formatters import format_summary_panel, save_summary
from .utils import redact_secrets

logger = logging.getLogger(__name__)


def _get_summary_module():
    return importlib.import_module("motus.commands.summary_cmd")


def _process_claude_event(event: dict, stats: SessionStats) -> None:
    """Process a Claude transcript event for statistics."""
    if event.get("type") == "assistant":
        for block in event.get("message", {}).get("content", []):
            if block.get("type") == "thinking":
                stats.thinking_count += 1
            elif block.get("type") == "tool_use":
                stats.tool_count += 1
                tool_name = block.get("name", "")
                tool_input = block.get("input", {})
                if tool_name in ("Write", "Edit"):
                    file_path = tool_input.get("file_path", "")
                    if file_path:
                        stats.files_modified.add(file_path)
                if tool_name == "Bash":
                    cmd = str(tool_input.get("command", ""))
                    if any(p in cmd.lower() for p in ["rm ", "sudo", "chmod"]):
                        stats.high_risk_ops += 1
                if tool_name == "Task":
                    stats.agent_count += 1


def _process_codex_event(event: dict, stats: SessionStats) -> None:
    """Process a Codex transcript event for statistics."""
    if event.get("type") == "response_item":
        payload = event.get("payload", {})
        if payload.get("type") == "function_call":
            stats.tool_count += 1
            tool_name = payload.get("name", "")
            arguments = payload.get("arguments", {})
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except (json.JSONDecodeError, TypeError):
                    arguments = {}
            tool_map = {
                "shell_command": "Bash",
                "write_file": "Write",
                "edit_file": "Edit",
                "create_file": "Write",
            }
            unified_name = tool_map.get(tool_name, tool_name)
            if unified_name in ("Write", "Edit"):
                file_path = arguments.get("path", arguments.get("workdir", ""))
                if file_path:
                    stats.files_modified.add(file_path)
            if unified_name == "Bash":
                cmd = str(arguments.get("command", ""))
                if any(p in cmd.lower() for p in ["rm ", "sudo", "chmod"]):
                    stats.high_risk_ops += 1


def _process_gemini_message(msg: dict, stats: SessionStats) -> None:
    """Process a Gemini message for statistics."""
    if msg.get("type") == "gemini":
        thoughts = msg.get("thoughts", [])
        stats.thinking_count += len(thoughts)
        for tool_call in msg.get("toolCalls", []):
            stats.tool_count += 1
            func_name = tool_call.get("name", "")
            func_args = tool_call.get("args", {})
            tool_map = {
                "shell": "Bash",
                "run_shell_command": "Bash",
                "write_file": "Write",
                "edit_file": "Edit",
            }
            unified_name = tool_map.get(func_name, func_name)
            if unified_name in ("Write", "Edit"):
                file_path = func_args.get("path", "")
                if file_path:
                    stats.files_modified.add(file_path)
            if unified_name == "Bash":
                cmd = str(func_args.get("command", ""))
                if any(p in cmd.lower() for p in ["rm ", "sudo", "chmod"]):
                    stats.high_risk_ops += 1


def analyze_session(session: SessionInfo) -> SessionStats:
    """Analyze a session and return statistics."""
    stats = SessionStats()
    source = getattr(session, "source", "claude") or "claude"

    try:
        if source == "gemini":
            with open(session.file_path, "r") as f:
                data = json.load(f)
            for msg in data.get("messages", []):
                _process_gemini_message(msg, stats)
        else:
            with open(session.file_path, "r") as f:
                for line in f:
                    try:
                        event = json.loads(line)

                        if source == "codex":
                            _process_codex_event(event, stats)
                        else:
                            _process_claude_event(event, stats)
                    except json.JSONDecodeError:
                        continue

    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.warning("Session analysis failed for %s: %s", session.file_path, e)
        return stats

    return stats


def generate_agent_context(session: SessionInfo) -> str:
    """Generate context summary for AI agents."""
    summary_module = _get_summary_module()
    source = getattr(session, "source", "claude") or "claude"
    stats = summary_module.analyze_session(session)
    decisions = summary_module.extract_decisions(session.file_path, source=source)
    context_parts = [
        "## Session Context",
        "",
        f"**Project**: {session.project_path}",
        f"**Session ID**: {session.session_id[:12]}",
        f"**Status**: {'🟢 Active' if session.is_active else '⚪ Idle'}",
        "",
        "### Activity Summary",
        f"- Thinking blocks: {stats.thinking_count}",
        f"- Tool calls: {stats.tool_count}",
        f"- Files modified: {len(stats.files_modified)}",
        f"- Agent spawns: {stats.agent_count}",
        f"- High-risk ops: {stats.high_risk_ops}",
        "",
    ]

    if stats.files_modified:
        context_parts.append("### Files Modified")
        for file_path in list(stats.files_modified)[:10]:
            short = file_path.split("/")[-1]
            context_parts.append(f"- {short}")
        context_parts.append("")

    if decisions:
        context_parts.append("### Key Decisions")
        for decision in decisions[:5]:
            context_parts.append(f"- {redact_secrets(decision)}")
        context_parts.append("")

    return "\n".join(context_parts)


def summary_command(session_id: Optional[str] = None):
    """Generate and display session summary for any source."""
    summary_module = _get_summary_module()
    if session_id:
        sessions = summary_module.find_sessions(max_age_hours=168)
        session = next((s for s in sessions if s.session_id.startswith(session_id)), None)
        if not session:
            summary_module.console.print(
                f"[red]Session not found: {summary_module.escape(session_id)}[/red]"
            )
            return
    else:
        session = summary_module.find_active_session()
        if not session:
            summary_module.console.print("[yellow]No recent sessions found.[/yellow]")
            return
    context = summary_module.generate_agent_context(session)
    summary_module.console.print(format_summary_panel(context, session.session_id))
    summary_file = save_summary(context, summary_module.MC_STATE_DIR)
    summary_module.console.print(
        f"\n[dim]Summary saved to: {summary_module.escape(str(summary_file))}[/dim]"
    )
