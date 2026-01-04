# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Argparse registration for session-oriented commands."""

from __future__ import annotations

import argparse


def register_session_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Register session-related CLI commands."""
    watch_parser = subparsers.add_parser("watch", help="Watch a session in real-time")
    watch_parser.add_argument("session_id", nargs="?", help="Session ID to watch (optional)")

    list_parser = subparsers.add_parser("list", help="List recent sessions")
    list_parser.add_argument(
        "--fast",
        "--no-process-detect",
        action="store_true",
        dest="fast",
        help="Skip process detection for faster listing",
    )

    sync_parser = subparsers.add_parser("sync", help="Sync session cache into SQLite")
    sync_parser.add_argument(
        "--full",
        action="store_true",
        help="Full sync: scan and ingest all session files",
    )
    sync_parser.add_argument(
        "--max-age-hours",
        type=int,
        default=None,
        help="Incremental sync limited to files modified within this window",
    )

    show_parser = subparsers.add_parser("show", help="Show session details")
    show_parser.add_argument("session_id", help="Session ID (prefix match supported)")

    feed_parser = subparsers.add_parser("feed", help="Show recent events for a session")
    feed_parser.add_argument("session_id", help="Session ID (prefix match supported)")
    feed_parser.add_argument(
        "--tail-lines",
        type=int,
        default=200,
        help="Number of transcript lines to read from the end (default: 200)",
    )

    subparsers.add_parser("context", help="Generate context summary for AI agent prompts")

    summary_parser = subparsers.add_parser(
        "summary", help="Generate a summary for CLAUDE.md context"
    )
    summary_parser.add_argument("session_id", nargs="?", help="Session ID to summarize (optional)")

    subparsers.add_parser("history", help="Show command history")

    teleport_parser = subparsers.add_parser(
        "teleport", help="Export a session bundle for cross-session context transfer"
    )
    teleport_parser.add_argument("session_id", help="Session ID to export")
    teleport_parser.add_argument(
        "--no-docs",
        action="store_true",
        help="Exclude planning docs (ROADMAP, ARCHITECTURE, etc.) from bundle",
    )
    teleport_parser.add_argument(
        "-o", "--output", help="Output file path (default: stdout as JSON)"
    )
