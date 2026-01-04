# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Argparse registration for health commands."""

from __future__ import annotations

import argparse


def register_health_parsers(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    """Register argparse parsers for health subcommands.

    Args:
        subparsers: Argparse subparser collection for CLI commands.

    Returns:
        The health command parser with capture/compare/history subcommands.
    """
    health_parser = subparsers.add_parser("health", help="Health baseline utilities")
    health_subparsers = health_parser.add_subparsers(dest="health_command", help="Health commands")

    capture_parser = health_subparsers.add_parser(
        "capture", help="Capture health baseline and append history"
    )
    capture_parser.add_argument(
        "--skip-security",
        action="store_true",
        help="Skip pip-audit (offline mode)",
    )

    compare_parser = health_subparsers.add_parser(
        "compare", help="Compare current health vs baseline"
    )
    compare_parser.add_argument(
        "--skip-security",
        action="store_true",
        help="Skip pip-audit (offline mode)",
    )

    history_parser = health_subparsers.add_parser(
        "history", help="Show recent health history"
    )
    history_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of entries to show (default: 10)",
    )

    return health_parser
