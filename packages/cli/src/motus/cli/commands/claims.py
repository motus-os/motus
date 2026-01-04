# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Argparse registration for claims commands."""

from __future__ import annotations

import argparse


def register_claims_parsers(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    """Register argparse parsers for claims subcommands.

    Args:
        subparsers: Argparse subparser collection for CLI commands.

    Returns:
        The claims command parser with acquire/list subcommands configured.
    """
    claims_parser = subparsers.add_parser("claims", help="Coordination claim registry")
    claims_subparsers = claims_parser.add_subparsers(dest="claims_command", help="Claims commands")

    claims_acquire_parser = claims_subparsers.add_parser("acquire", help="Acquire a claim")
    claims_acquire_parser.add_argument("--namespace", required=True, help="Claim namespace")
    claims_acquire_parser.add_argument(
        "--resource", required=True, help="Resource id/path to claim"
    )
    claims_acquire_parser.add_argument("--agent", help="Agent id (or set MC_AGENT_ID)")
    claims_acquire_parser.add_argument("--task-id", help="Task id (default: resource)")
    claims_acquire_parser.add_argument("--task-type", help="Task type (default: CR)")
    claims_acquire_parser.add_argument(
        "--registry-dir",
        help="Override claim registry directory (default: .motus/state/locks/claims)",
    )
    claims_acquire_parser.add_argument(
        "--acl",
        help="Namespace ACL YAML (default: .motus/project/config/namespace-acl.yaml if present)",
    )
    claims_acquire_parser.add_argument(
        "--lease-seconds", type=int, default=None, help="Lease duration seconds"
    )
    claims_acquire_parser.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON"
    )

    claims_list_parser = claims_subparsers.add_parser("list", help="List active claims")
    claims_list_parser.add_argument("--agent", help="Agent id (or set MC_AGENT_ID)")
    claims_list_parser.add_argument(
        "--namespace", help="Filter to one namespace (authorization required)"
    )
    claims_list_parser.add_argument(
        "--all-namespaces",
        action="store_true",
        help="List across all namespaces (global admins only)",
    )
    claims_list_parser.add_argument(
        "--registry-dir",
        help="Override claim registry directory (default: .motus/state/locks/claims)",
    )
    claims_list_parser.add_argument(
        "--acl",
        help="Namespace ACL YAML (default: .motus/project/config/namespace-acl.yaml if present)",
    )
    claims_list_parser.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON"
    )

    return claims_parser
