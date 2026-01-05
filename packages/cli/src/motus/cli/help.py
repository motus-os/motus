# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""CLI help-tier utilities and formatting."""

from __future__ import annotations

import argparse
import os

from rich.console import Console

from motus.cli.exit_codes import EXIT_ERROR, EXIT_SUCCESS, EXIT_USAGE

_HELP_TIER_ENV = "MC_HELP_TIER"

_COMMAND_HELP_TIERS: dict[str, int] = {
    # Tier 0: instant value
    "web": 0,
    "list": 0,
    "watch": 0,
    # Tier 1: basic operations
    "show": 1,
    "feed": 1,
    "sync": 1,
    "context": 1,
    "doctor": 1,
    "install": 1,
    # Tier 2: standard operations
    "errors": 2,
    "checkpoint": 2,
    "checkpoints": 2,
    "rollback": 2,
    "diff": 2,
    "history": 2,
    "teleport": 2,
    "policy": 2,
    "intent": 2,
    "explain": 2,
    "claude": 2,
    # Tier 3: advanced / power users
    "orient": 3,
    "standards": 3,
    "claims": 3,
    "mcp": 3,
    "init": 3,
    "summary": 3,
    "harness": 3,
    "health": 3,
    "verify": 3,
    "handoffs": 3,
    "activity": 3,
    "audit": 3,
    "db": 3,
    "release": 3,
}

_COMMAND_HELP_TEXTS: dict[str, str] = {
    "watch": "Watch a session in real-time",
    "list": "List recent sessions",
    "show": "Show session details",
    "feed": "Show recent events for a session",
    "sync": "Sync session cache into SQLite",
    "web": "Launch web dashboard at http://127.0.0.1:4000",
    "context": "Generate context summary for AI agent prompts",
    "orient": "Lookup a cached decision",
    "standards": "Standards lookup utilities",
    "summary": "Generate a summary for CLAUDE.md context",
    "doctor": "Run health checks",
    "install": "Install agent onboarding defaults",
    "errors": "Summarize errors from a session",
    "intent": "Extract/show intent from a session",
    "harness": "Detect test harness for a repository",
    "policy": "Plan and run policy gates (proof of compliance)",
    "claims": "Coordination claim registry",
    "checkpoint": "Create a state checkpoint",
    "checkpoints": "List all available checkpoints",
    "rollback": "Restore state to a previous checkpoint",
    "diff": "Show changes between current state and a checkpoint",
    "history": "Show command history",
    "teleport": "Export a session bundle for cross-session context transfer",
    "mcp": "Start MCP server (stdio transport)",
    "init": "Initialize a Motus workspace (.motus/)",
    "explain": "Explain a policy run decision trace",
    "health": "Health baseline utilities",
    "verify": "Verification utilities",
    "handoffs": "Handoff hygiene utilities",
    "activity": "Activity proof ledger utilities",
    "audit": "Audit finding pipeline utilities",
    "db": "Database maintenance utilities",
    "release": "Release evidence gates",
    "claude": "Manage CLAUDE.md instructions safely",
}


def _visible_help_tier_from_env() -> int | None:
    raw = os.environ.get(_HELP_TIER_ENV, "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return max(0, min(3, value))


def _get_cli_run_count() -> int | None:
    """Best-effort total run count for tier gating (Phase 0 DB audit_log)."""
    try:
        import sqlite3

        from ..core.database import configure_connection, get_database_path

        max_sample = 20
        db_path = get_database_path()
        if not db_path.exists():
            return 0

        conn = sqlite3.connect(str(db_path))
        configure_connection(conn, set_row_factory=False)
        try:
            row = conn.execute(
                "SELECT 1 FROM audit_log WHERE event_type = ? AND action = ? LIMIT ?",
                ("cli", "invoke", max_sample),
            ).fetchall()
            return len(row)
        finally:
            conn.close()
    except Exception:
        return None


def compute_visible_help_tier() -> int:
    """Compute visible help tier.

    Precedence:
    1) `MC_HELP_TIER` env override (deterministic tests)
    2) Persistent run count (Phase 0 DB audit_log)
    3) Fail-open (tier 3) if unavailable
    """
    override = _visible_help_tier_from_env()
    if override is not None:
        return override

    runs = _get_cli_run_count()
    if runs is None:
        return 3
    if runs < 1:
        return 0
    if runs < 5:
        return 1
    if runs < 20:
        return 2
    return 3


def first_command_token(argv: list[str]) -> str | None:
    """Return the first non-flag token from argv.

    Args:
        argv: CLI argv tokens.

    Returns:
        First command token or None when not found.
    """
    for token in argv:
        if not token.startswith("-"):
            return token
    return None


def print_top_level_help(console: Console, visible_tier: int) -> None:
    """Render the top-level CLI help output.

    Args:
        console: Rich console for output.
        visible_tier: Highest help tier to display.
    """
    console.print("[bold]Motus[/bold]\n")
    console.print("Usage: motus <command> [args]\n")
    console.print("Try [cyan]motus web[/cyan] to launch the dashboard.\n")

    tiers = [
        (0, "Tier 0 (Instant Value)"),
        (1, "Tier 1 (Basic)"),
        (2, "Tier 2 (Standard)"),
        (3, "Tier 3 (Advanced)"),
    ]
    for tier, label in tiers:
        if tier > visible_tier:
            continue
        console.print(f"{label}:")
        for name in sorted(k for k, v in _COMMAND_HELP_TIERS.items() if v == tier):
            desc = _COMMAND_HELP_TEXTS.get(name, "")
            console.print(f"  {name:<12} {desc}".rstrip(), markup=False)
        console.print("")

    if visible_tier < 3:
        console.print("Run [cyan]motus --help-all[/cyan] to show all commands.")

    console.print("\n[bold]Environment:[/bold]")
    console.print(f"  {_HELP_TIER_ENV}  Visible help tier override (0-3)", markup=False)
    console.print("  MC_VAULT_DIR  Vault root directory", markup=False)
    console.print("  MC_PROFILE  Policy profile id", markup=False)
    console.print("  MC_EVIDENCE_DIR  Evidence output directory", markup=False)
    console.print("\n[bold]Exit Codes:[/bold]")
    console.print(f"  {EXIT_SUCCESS}  Success", markup=False)
    console.print(f"  {EXIT_ERROR}  Operational error", markup=False)
    console.print(f"  {EXIT_USAGE}  Invalid arguments", markup=False)


def print_parser_help(console: Console, parser: argparse.ArgumentParser) -> None:
    """Render argparse help text.

    Args:
        console: Rich console for output.
        parser: Argument parser to format.
    """
    console.print(parser.format_help(), markup=False)


def format_cli_resource_id(command: str | None, args: argparse.Namespace) -> str:
    """Format a CLI resource identifier for telemetry.

    Args:
        command: Top-level command token.
        args: Parsed argparse namespace.

    Returns:
        Resource identifier string or empty string when unknown.
    """
    if not command:
        return ""

    if command == "policy":
        sub = getattr(args, "policy_command", None)
        return f"policy:{sub}" if sub else "policy"
    if command == "standards":
        sub = getattr(args, "standards_command", None)
        return f"standards:{sub}" if sub else "standards"
    if command == "claims":
        sub = getattr(args, "claims_command", None)
        return f"claims:{sub}" if sub else "claims"

    return command
