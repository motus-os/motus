# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Argparse registration for system commands."""

from __future__ import annotations

import argparse


def register_system_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Register argparse parsers for system-level CLI commands.

    Args:
        subparsers: Argparse subparser collection for CLI commands.
    """
    subparsers.add_parser("web", help="Launch web dashboard at http://127.0.0.1:4000")

    doctor_parser = subparsers.add_parser("doctor", help="Run health checks")
    doctor_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    doctor_parser.add_argument(
        "--fix",
        action="store_true",
        help="Attempt safe auto-remediation for warnings",
    )

    errors_parser = subparsers.add_parser("errors", help="Summarize errors from a session")
    errors_parser.add_argument("session_id", nargs="?", help="Session ID (prefix match supported)")
    errors_parser.add_argument("--last", type=int, help="Summarize last N sessions")
    errors_parser.add_argument("--session", help="Explicit session file path (.jsonl)")
    errors_parser.add_argument(
        "--category",
        choices=["api", "exit", "file_io"],
        help="Filter to one category",
    )
    errors_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    intent_parser = subparsers.add_parser("intent", help="Extract/show intent from a session")
    intent_parser.add_argument("session_id", help="Session ID to analyze")
    intent_parser.add_argument("--save", action="store_true", help="Save intent to .mc/intent.yaml")

    harness_parser = subparsers.add_parser("harness", help="Detect test harness for a repository")
    harness_parser.add_argument(
        "--save", action="store_true", help="Save detected harness to .mc/harness.yaml"
    )

    checkpoint_parser = subparsers.add_parser("checkpoint", help="Create a state checkpoint")
    checkpoint_parser.add_argument("label", help="A descriptive label for the checkpoint")

    subparsers.add_parser("checkpoints", help="List all available checkpoints")

    rollback_parser = subparsers.add_parser(
        "rollback", help="Restore state to a previous checkpoint"
    )
    rollback_parser.add_argument("checkpoint_id", help="Checkpoint ID to roll back to")

    diff_parser = subparsers.add_parser(
        "diff", help="Show changes between current state and a checkpoint"
    )
    diff_parser.add_argument("checkpoint_id", help="Checkpoint ID to diff against")

    explain_parser = subparsers.add_parser(
        "explain", help="Explain a policy run decision trace"
    )
    explain_parser.add_argument("run_id", help="Policy run ID (evidence directory name)")
    explain_parser.add_argument(
        "--repo",
        help="Repository root (default: current working directory)",
    )

    subparsers.add_parser("mcp", help="Start MCP server (stdio transport)")

    subparsers.add_parser("install", help="Install agent onboarding defaults")

    init_parser = subparsers.add_parser("init", help="Initialize a Motus workspace (.motus/)")
    init_mode = init_parser.add_mutually_exclusive_group(required=True)
    init_mode.add_argument("--full", action="store_true", help="Create fresh Motus workspace")
    init_mode.add_argument(
        "--integrate",
        metavar="PATH",
        help="Overlay on existing workspace (creates <PATH>/.motus only)",
    )
    init_mode.add_argument("--lite", action="store_true", help="Minimal footprint mode")
    init_parser.add_argument(
        "--path",
        default=".",
        help="Target directory (used for --full/--lite; default: .)",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Repair missing directories and update current pointer (never deletes data)",
    )

    config_parser = subparsers.add_parser("config", help="Manage Motus configuration")
    config_parser.add_argument(
        "config_args",
        nargs="*",
        help="Subcommand and args (show/get/set/reset/path)",
    )

    claude_parser = subparsers.add_parser(
        "claude",
        help="Manage CLAUDE.md instructions safely",
    )
    claude_parser.add_argument(
        "--path",
        default=".",
        help="Target repository root (default: .)",
    )
    claude_parser.add_argument(
        "--claude-path",
        help="Override CLAUDE.md path (default: <root>/CLAUDE.md)",
    )
    claude_parser.add_argument(
        "--docs-path",
        default="docs/AGENT-INSTRUCTIONS.md",
        help="Path for agent instructions (default: docs/AGENT-INSTRUCTIONS.md)",
    )
    claude_parser.add_argument(
        "--no-docs",
        action="store_true",
        help="Skip writing docs/AGENT-INSTRUCTIONS.md",
    )
    claude_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show actions without writing files",
    )
    claude_parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print updated CLAUDE.md to stdout without writing files",
    )
    claude_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite managed blocks if modified",
    )
