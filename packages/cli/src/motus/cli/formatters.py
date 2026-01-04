# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Rich formatting utilities for CLI output (tables, panels, colors)."""

try:
    from ..logging import get_logger

    logger = get_logger(__name__)
except ImportError:
    import logging

    logger = logging.getLogger(__name__)  # type: ignore[assignment]

try:
    from rich import box
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
except ImportError:
    # Graceful fallback if rich is not installed
    Panel = None  # type: ignore[assignment,misc]
    Table = None  # type: ignore[assignment,misc]
    Text = None  # type: ignore[assignment,misc]
    box = None  # type: ignore[assignment,misc]

from .output import ErrorEvent, SessionInfo, SessionStats, TaskEvent, ThinkingEvent, ToolEvent


def get_risk_style(risk_level) -> tuple[str, str]:
    """Get border style and icon for risk level.

    Args:
        risk_level: RiskLevel enum or string representation

    Returns:
        Tuple of (color, icon)
    """
    # Import here to avoid circular dependency
    from ..schema.events import RiskLevel

    # Convert RiskLevel enum to string value if needed
    if isinstance(risk_level, RiskLevel):
        risk_str = risk_level.value
    else:
        risk_str = risk_level

    styles = {
        "safe": ("green", "✓"),
        "medium": ("yellow", "◐"),
        "high": ("red", "●"),
        "critical": ("bold red", "⚠"),
    }
    return styles.get(risk_str, ("white", "?"))


def format_thinking(thinking: ThinkingEvent, stats: SessionStats) -> Panel:
    """Format a thinking event for display."""
    from ..commands.utils import redact_secrets

    content = redact_secrets(thinking.content)
    stats.thinking_count += 1

    max_len = 800 if len(content) < 1000 else 500
    if len(content) > max_len:
        content = content[:max_len] + "..."

    content = content.strip()
    time_str = thinking.timestamp.strftime("%H:%M:%S")

    return Panel(
        Text(content, style="italic"),
        title=f"[bold magenta]💭 THINKING[/bold magenta] [dim]#{stats.thinking_count}[/dim]",
        subtitle=f"[dim]{time_str}[/dim]",
        border_style="magenta",
        padding=(0, 1),
    )


def format_error(error: ErrorEvent, stats: SessionStats) -> Panel:
    """Format an error event for display."""
    from ..commands.utils import redact_secrets

    stats.error_count = getattr(stats, "error_count", 0) + 1

    lines = []
    lines.append(f"[bold red]{redact_secrets(error.message)}[/bold red]")

    if error.error_type:
        lines.append(f"[dim]Type:[/dim] {error.error_type}")
    if error.tool_name:
        lines.append(f"[dim]Tool:[/dim] {error.tool_name}")
    if not error.recoverable:
        lines.append("[yellow]⚠ Non-recoverable[/yellow]")

    content = "\n".join(lines)
    time_str = error.timestamp.strftime("%H:%M:%S")

    return Panel(
        Text.from_markup(content),
        title=f"[bold red]❌ ERROR[/bold red] [dim]#{stats.error_count}[/dim]",
        subtitle=f"[dim]{time_str}[/dim]",
        border_style="red",
        padding=(0, 1),
    )


def format_task(task: TaskEvent, stats: SessionStats) -> Panel:
    """Format a Task/subagent event with rich details."""
    from ..commands.utils import redact_secrets

    stats.agent_count += 1
    lines = []

    lines.append(f"[bold cyan]{task.description}[/bold cyan]")
    lines.append("")

    agent_info = f"[dim]Agent:[/dim] {task.subagent_type}"
    if task.model:
        agent_info += f"  [dim]Model:[/dim] {task.model}"
    lines.append(agent_info)

    if task.prompt:
        # Show full prompt (no truncation)
        full_prompt = redact_secrets(task.prompt)
        lines.append("")
        lines.append("[dim]Prompt:[/dim]")
        lines.append(f"[white]{full_prompt}[/white]")

    content = "\n".join(lines)
    time_str = task.timestamp.strftime("%H:%M:%S")

    return Panel(
        Text.from_markup(content),
        title=f"[bold yellow]🤖 SPAWNING AGENT[/bold yellow] [dim]#{stats.agent_count}[/dim]",
        subtitle=f"[dim]{time_str}[/dim]",
        border_style="yellow",
        padding=(0, 1),
    )


def format_tool(tool: ToolEvent, stats: SessionStats) -> Panel:
    """Format a tool event for display."""
    from ..commands.utils import redact_secrets

    stats.tool_count += 1
    input_summary = ""

    if tool.name in ("Write", "Edit"):
        file_path = tool.input.get("file_path", "")
        if file_path:
            stats.files_modified.add(file_path)

    if tool.risk_level in ("high", "critical"):
        stats.high_risk_ops += 1

    if tool.name == "Read":
        input_summary = tool.input.get("file_path", "")
    elif tool.name == "Write":
        fp = tool.input.get("file_path", "")
        input_summary = f"[bold]{fp}[/bold]\n[dim]Creating new file[/dim]"
    elif tool.name == "Edit":
        file_path = tool.input.get("file_path", "")
        old_str = redact_secrets(tool.input.get("old_string", "")[:40])
        input_summary = f"[bold]{file_path}[/bold]\n[dim]replacing:[/dim] {old_str}..."
    elif tool.name == "Bash":
        cmd = redact_secrets(tool.input.get("command", ""))
        desc = tool.input.get("description", "")
        if desc:
            input_summary = f"[dim]{desc}[/dim]\n{cmd[:100]}"
        else:
            input_summary = cmd[:120] + ("..." if len(cmd) > 120 else "")
    elif tool.name == "Glob":
        pattern = tool.input.get("pattern", "")
        path = tool.input.get("path", "")
        input_summary = f"{pattern}" + (f" in {path}" if path else "")
    elif tool.name == "Grep":
        pattern = tool.input.get("pattern", "")
        path = tool.input.get("path", "")
        input_summary = f"/{pattern}/" + (f" in {path}" if path else "")
    elif tool.name == "WebFetch":
        url = tool.input.get("url", "")
        prompt = tool.input.get("prompt", "")[:50]
        input_summary = f"{url}\n[dim]{prompt}...[/dim]"
    elif tool.name == "WebSearch":
        input_summary = f'🔍 "{tool.input.get("query", "")}"'
    elif tool.name == "TodoWrite":
        todos = tool.input.get("todos", [])
        if todos:
            items = [t.get("content", "")[:40] for t in todos[:3]]
            input_summary = "\n".join(f"• {item}" for item in items)
            if len(todos) > 3:
                input_summary += f"\n[dim]...and {len(todos) - 3} more[/dim]"
    else:
        for k, v in tool.input.items():
            if isinstance(v, str) and v:
                input_summary = f"[dim]{k}:[/dim] {v[:60]}" + ("..." if len(v) > 60 else "")
                break

    icon = {
        "Read": "📖",
        "Write": "✏️",
        "Edit": "🔧",
        "Bash": "💻",
        "Glob": "🔍",
        "Grep": "🔎",
        "Task": "🤖",
        "WebFetch": "🌐",
        "WebSearch": "🔍",
        "TodoWrite": "📝",
        "AskUserQuestion": "❓",
        "BashOutput": "📤",
        "KillShell": "🛑",
    }.get(tool.name, "⚡")

    # Import here to avoid circular dependency
    from ..schema.events import RiskLevel

    border_style, risk_icon = get_risk_style(tool.risk_level)

    # Handle both RiskLevel enum and string values
    risk_str = tool.risk_level.value if isinstance(tool.risk_level, RiskLevel) else tool.risk_level

    risk_indicator = ""
    if risk_str == "critical":
        risk_indicator = " [bold red]⚠ DESTRUCTIVE[/bold red]"
    elif risk_str == "high":
        risk_indicator = " [red]● HIGH RISK[/red]"
    elif risk_str == "medium":
        risk_indicator = " [yellow]◐[/yellow]"

    time_str = tool.timestamp.strftime("%H:%M:%S")
    title = f"[bold {border_style}]{icon} {tool.name}[/bold {border_style}]{risk_indicator}"

    return Panel(
        (
            Text.from_markup(input_summary)
            if "[" in input_summary
            else Text(input_summary, style="cyan")
        ),
        title=title,
        subtitle=f"[dim]{time_str}[/dim]",
        border_style=border_style,
        padding=(0, 1),
    )


def create_header(session: SessionInfo) -> Panel:
    """Create the header panel."""
    return Panel(
        f"[bold]Session:[/bold] {session.session_id[:12]}...\n"
        f"[bold]File:[/bold] {session.file_path.name}\n"
        f"[dim]Press Ctrl+C to exit[/dim]",
        title="[bold green]🎯 Motus[/bold green]",
        subtitle="[dim]Command Center for AI Agents[/dim]",
        border_style="green",
    )


def create_summary_table(stats: SessionStats) -> Table:
    """Create a summary table of session statistics."""
    from datetime import datetime

    duration = datetime.now() - stats.start_time
    mins = int(duration.total_seconds() // 60)
    secs = int(duration.total_seconds() % 60)

    summary = Table(show_header=False, box=box.SIMPLE)
    summary.add_column("Metric", style="dim")
    summary.add_column("Value", style="cyan")
    summary.add_row("Duration", f"{mins}m {secs}s")
    summary.add_row("Thinking blocks", str(stats.thinking_count))
    summary.add_row("Tool calls", str(stats.tool_count))
    summary.add_row("Agents spawned", str(stats.agent_count))
    summary.add_row("Files modified", str(len(stats.files_modified)))
    if stats.high_risk_ops > 0:
        summary.add_row("High-risk ops", f"[red]{stats.high_risk_ops}[/red]")

    return summary
