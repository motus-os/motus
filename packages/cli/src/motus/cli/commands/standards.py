# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Argparse registration for standards and orient commands."""

from __future__ import annotations

import argparse


def register_standards_parsers(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    """Register argparse parsers for orient and standards subcommands.

    Args:
        subparsers: Argparse subparser collection for CLI commands.

    Returns:
        The standards command parser with orient and standards subcommands.
    """
    orient_parser = subparsers.add_parser("orient", help="Lookup a cached decision")
    orient_parser.add_argument("decision_type", help="Decision type to lookup (e.g. color_palette)")
    orient_parser.add_argument(
        "--context",
        help="Context as JSON/YAML string, file path, or '-' for stdin (required if stdin is TTY)",
    )
    orient_parser.add_argument(
        "--constraints",
        help="Optional constraints as JSON/YAML string, file path, or '-' for stdin",
    )
    orient_parser.add_argument(
        "--registry",
        help="Decision type registry path (default: .motus/config/decision_types.yaml if present)",
    )
    orient_parser.add_argument(
        "--explain",
        action="store_true",
        help="Include match trace / debugging details in output",
    )
    orient_parser.add_argument(
        "--rebuild-index",
        action="store_true",
        help="Rebuild the standards index before lookup",
    )
    orient_parser.add_argument(
        "--high-miss",
        action="store_true",
        help="(stats) Show top 5 decision types with lowest hit rate",
    )
    orient_parser.add_argument(
        "--min-calls",
        type=int,
        default=1,
        help="(stats) Minimum calls to include (default: 1)",
    )
    orient_parser.add_argument(
        "--stats-path",
        help="(stats) Override events.jsonl path (default: .motus/state/orient/events.jsonl)",
    )
    orient_parser.add_argument(
        "--json",
        action="store_true",
        help="(stats) Emit machine-readable JSON for `motus orient stats`",
    )

    standards_parser = subparsers.add_parser(
        "standards", help="Standards lookup utilities"
    )
    standards_subparsers = standards_parser.add_subparsers(
        dest="standards_command", help="Standards commands"
    )
    standards_validate_parser = standards_subparsers.add_parser(
        "validate", help="Validate a standard.yaml against schema"
    )
    standards_validate_parser.add_argument("path", help="Path to a standard.yaml file")
    standards_validate_parser.add_argument(
        "--vault-dir", help="Vault root directory (or set MC_VAULT_DIR)"
    )
    standards_validate_parser.add_argument(
        "--registry", help="Decision type registry path (optional)"
    )
    standards_validate_parser.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON"
    )

    standards_propose_parser = standards_subparsers.add_parser(
        "propose", help="Create a proposal from a slow-path decision"
    )
    standards_propose_parser.add_argument(
        "--type", dest="decision_type", required=True, help="Decision type"
    )
    standards_propose_parser.add_argument(
        "--context",
        required=True,
        help="Context as JSON/YAML string, file path, or '-' for stdin",
    )
    standards_propose_parser.add_argument(
        "--output",
        required=True,
        help="Output decision as JSON/YAML string, file path, or '-' for stdin",
    )
    standards_propose_parser.add_argument("--why", help="Why this proposal should be promoted")
    standards_propose_parser.add_argument("--by", help="Agent or user id creating the proposal")
    standards_propose_parser.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON"
    )

    standards_list_parser = standards_subparsers.add_parser(
        "list-proposals", help="List cached proposals"
    )
    standards_list_parser.add_argument(
        "--type", dest="decision_type", help="Filter by decision type"
    )
    standards_list_parser.add_argument(
        "--status",
        choices=["pending", "approved", "rejected"],
        help="Filter by status",
    )
    standards_list_parser.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON"
    )

    standards_promote_parser = standards_subparsers.add_parser(
        "promote", help="Promote a proposal to an active standard"
    )
    standards_promote_parser.add_argument("proposal_id", help="Proposal id to promote")
    standards_promote_parser.add_argument(
        "--to",
        required=True,
        choices=["user", "project", "system"],
        help="Target layer (system is immutable and will fail)",
    )
    standards_promote_parser.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON"
    )

    standards_reject_parser = standards_subparsers.add_parser("reject", help="Reject a proposal")
    standards_reject_parser.add_argument("proposal_id", help="Proposal id to reject")
    standards_reject_parser.add_argument("--reason", required=True, help="Rejection reason")
    standards_reject_parser.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON"
    )

    return standards_parser
