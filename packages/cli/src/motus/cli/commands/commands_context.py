# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Context command implementation - generates AI agent context summaries.

PERFORMANCE: Rich and other heavy imports deferred to function level.
"""

from rich.markup import escape

from ..exit_codes import EXIT_ERROR

try:
    from motus.logging import get_logger

    logger = get_logger(__name__)
except ImportError:
    import logging

    logger = logging.getLogger(__name__)  # type: ignore[assignment]


def context_command() -> None:
    """Generate context summary for AI agents."""
    from rich.panel import Panel

    from motus.config import MC_STATE_DIR
    from motus.orchestrator import get_orchestrator

    from ..output import unified_session_to_session_info
    from ..watch_cmd import generate_agent_context

    # Import console from shim
    from . import _get_console

    console = _get_console()

    # Discover sessions once
    orchestrator = get_orchestrator()
    unified_sessions = orchestrator.discover_all(max_age_hours=1)

    if not unified_sessions:
        console.print("[yellow]No active session found.[/yellow]")
        raise SystemExit(EXIT_ERROR)

    # Convert first (most recent) to SessionInfo
    unified = unified_sessions[0]
    session = unified_session_to_session_info(unified)

    # Pass unified_session to avoid re-discovery
    context = generate_agent_context(session, unified)

    # Also save to file for easy injection
    context_file = MC_STATE_DIR / "current_context.md"
    try:
        with open(context_file, "w") as f:
            f.write(context)
        save_status = f"[dim]Saved to {escape(str(context_file))}[/dim]"
    except (OSError, IOError) as e:
        logger.error(
            f"Failed to write context file: {e}",
        )
        save_status = f"[dim red]Failed to save: {escape(str(e))}[/dim red]"

    console.print(
        Panel(
            context,
            title="[bold cyan]📋 Agent Context[/bold cyan]",
            subtitle=save_status,
            border_style="cyan",
        )
    )

    console.print(
        "\n[dim]This context can be injected into AI agent prompts for self-awareness.[/dim]"
    )
