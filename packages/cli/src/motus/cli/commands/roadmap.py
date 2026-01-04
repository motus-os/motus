# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Argparse registration for roadmap commands."""

from __future__ import annotations

import argparse


def register_roadmap_parsers(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    """Register argparse parsers for roadmap subcommands.

    Args:
        subparsers: Argparse subparser collection for CLI commands.

    Returns:
        The roadmap command parser.
    """
    roadmap_parser = subparsers.add_parser(
        "roadmap",
        help="View and manage roadmap items (source of truth)",
    )
    roadmap_subparsers = roadmap_parser.add_subparsers(
        dest="roadmap_command",
        help="Roadmap commands",
    )

    # motus roadmap (default: show all by phase)
    roadmap_parser.add_argument(
        "--all",
        action="store_true",
        help="Include soft-deleted items",
    )
    roadmap_parser.add_argument(
        "--phase",
        help="Filter to specific phase (e.g., phase_c)",
    )
    roadmap_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON",
    )

    # motus roadmap ready
    ready_parser = roadmap_subparsers.add_parser(
        "ready",
        help="Show items ready to work on (no blocking deps)",
    )
    ready_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON",
    )

    # motus roadmap claim <id> - DEPRECATED
    claim_parser = roadmap_subparsers.add_parser(
        "claim",
        help="[DEPRECATED] Claim an item (use 'motus work claim' instead)",
    )
    claim_parser.add_argument(
        "item_id",
        help="ID of item to claim",
    )
    claim_parser.add_argument(
        "--agent",
        help="Agent ID (default: MC_AGENT_ID or 'default')",
    )

    # motus roadmap complete <id>
    complete_parser = roadmap_subparsers.add_parser(
        "complete",
        help="Mark item as complete",
    )
    complete_parser.add_argument(
        "item_id",
        help="ID of item to complete",
    )

    # motus roadmap status <id>
    status_parser = roadmap_subparsers.add_parser(
        "status",
        help="Get detailed status of an item",
    )
    status_parser.add_argument(
        "item_id",
        help="ID of item to check",
    )
    status_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON",
    )

    # motus roadmap release <id>
    release_parser = roadmap_subparsers.add_parser(
        "release",
        help="Release claim without completing",
    )
    release_parser.add_argument(
        "item_id",
        help="ID of item to release",
    )

    # motus roadmap my-work
    my_work_parser = roadmap_subparsers.add_parser(
        "my-work",
        help="Show items assigned to you",
    )
    my_work_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON",
    )

    # motus roadmap export
    export_parser = roadmap_subparsers.add_parser(
        "export",
        help="Export roadmap to markdown (for backup)",
    )
    export_parser.add_argument(
        "--output",
        "-o",
        help="Output file (default: stdout)",
    )
    export_parser.add_argument(
        "--include-deleted",
        action="store_true",
        help="Include soft-deleted items in export",
    )

    # motus roadmap delete <id> (soft delete)
    delete_parser = roadmap_subparsers.add_parser(
        "delete",
        help="Soft-delete an item (rebaseline)",
    )
    delete_parser.add_argument(
        "item_id",
        help="ID of item to delete",
    )
    delete_parser.add_argument(
        "--reason",
        help="Reason for deletion (stored for audit)",
    )

    return roadmap_parser
