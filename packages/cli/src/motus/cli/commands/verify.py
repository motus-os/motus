# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Argparse registration for verify commands."""

from __future__ import annotations

import argparse


def register_verify_parsers(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    """Register argparse parsers for verify subcommands.

    Args:
        subparsers: Argparse subparser collection for CLI commands.

    Returns:
        The verify command parser with clean subcommand configured.
    """
    verify_parser = subparsers.add_parser("verify", help="Verification utilities")
    verify_subparsers = verify_parser.add_subparsers(dest="verify_command", help="Verify commands")

    clean_parser = verify_subparsers.add_parser(
        "clean", help="Run clean-clone verification"
    )
    clean_parser.add_argument(
        "--source",
        help="Source repo path (default: current git repo)",
    )
    clean_parser.add_argument(
        "--skip-security",
        action="store_true",
        help="Skip pip-audit (offline mode)",
    )
    clean_parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Keep temp directory on failure",
    )

    return verify_parser
