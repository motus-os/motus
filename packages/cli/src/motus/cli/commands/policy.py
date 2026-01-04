# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Argparse registration for policy commands."""

from __future__ import annotations

import argparse


def register_policy_parsers(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    """Register argparse parsers for policy subcommands.

    Args:
        subparsers: Argparse subparser collection for CLI commands.

    Returns:
        The policy command parser with plan/run/verify/prune subcommands.
    """
    policy_parser = subparsers.add_parser(
        "policy", help="Plan and run policy gates (proof of compliance)"
    )
    policy_subparsers = policy_parser.add_subparsers(dest="policy_command", help="Policy commands")

    def _add_policy_common_flags(p: argparse.ArgumentParser) -> None:
        p.add_argument("--vault-dir", help="Vault root directory (or set MC_VAULT_DIR)")
        p.add_argument("--profile", help="Profile id (or set MC_PROFILE; default: personal)")
        p.add_argument("--repo", help="Repository root (default: current directory)")
        p.add_argument(
            "--pack-cap",
            type=int,
            default=None,
            help="Override profile pack cap (default: profile default)",
        )
        p.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

        change = p.add_mutually_exclusive_group(required=True)
        change.add_argument(
            "--files", nargs="+", help="Explicit changed files (repo-relative preferred)"
        )
        change.add_argument(
            "--git-diff",
            nargs=2,
            metavar=("BASE", "HEAD"),
            help="Compute changed files via: git diff --name-only BASE HEAD",
        )

    policy_plan_parser = policy_subparsers.add_parser(
        "plan", help="Compute deterministic packs/tier/gates for a change"
    )
    _add_policy_common_flags(policy_plan_parser)

    policy_run_parser = policy_subparsers.add_parser(
        "run", help="Run required gates and emit an evidence bundle (fail closed)"
    )
    _add_policy_common_flags(policy_run_parser)
    policy_run_parser.add_argument(
        "--evidence-dir",
        help="Evidence root directory (defaults to <repo>/.mc/evidence or MC_EVIDENCE_DIR)",
    )

    policy_verify_parser = policy_subparsers.add_parser(
        "verify", help="Verify an evidence bundle (hashes + signature)"
    )
    policy_verify_parser.add_argument(
        "--vault-dir", help="Vault root directory (or set MC_VAULT_DIR)"
    )
    policy_verify_parser.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON"
    )
    policy_verify_parser.add_argument(
        "--evidence",
        required=True,
        help="Evidence run directory containing manifest.json (e.g., <evidence>/<run_id>)",
    )

    policy_prune_parser = policy_subparsers.add_parser(
        "prune", help="Prune old evidence bundles under .mc/evidence"
    )
    policy_prune_parser.add_argument("--repo", help="Repository root (default: current directory)")
    policy_prune_parser.add_argument(
        "--evidence-dir",
        help="Evidence root directory (defaults to <repo>/.mc/evidence or MC_EVIDENCE_DIR)",
    )
    policy_prune_parser.add_argument(
        "--keep",
        type=int,
        default=10,
        help="Keep the N most recent bundles (default: 10)",
    )
    policy_prune_parser.add_argument(
        "--older-than",
        type=int,
        default=None,
        metavar="DAYS",
        help="Delete bundles older than DAYS (in addition to keep policy)",
    )
    policy_prune_parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be deleted without deleting"
    )

    return policy_parser
