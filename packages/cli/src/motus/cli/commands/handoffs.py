# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Argparse registration for handoff commands."""

from __future__ import annotations

import argparse


def register_handoffs_parsers(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    """Register argparse parsers for handoff subcommands.

    Args:
        subparsers: Argparse subparser collection for CLI commands.

    Returns:
        The handoffs command parser with list/check/archive subcommands.
    """
    handoffs_parser = subparsers.add_parser("handoffs", help="Handoff hygiene utilities")
    handoffs_subparsers = handoffs_parser.add_subparsers(
        dest="handoffs_command", help="Handoff commands"
    )

    list_parser = handoffs_subparsers.add_parser("list", help="List handoff files")
    list_parser.add_argument("--root", help="Handoff root directory")

    check_parser = handoffs_subparsers.add_parser("check", help="Check handoff count")
    check_parser.add_argument("--root", help="Handoff root directory")
    check_parser.add_argument("--max", type=int, default=10, help="Max allowed files")

    archive_parser = handoffs_subparsers.add_parser("archive", help="Archive old handoffs")
    archive_parser.add_argument("--root", help="Handoff root directory")
    archive_parser.add_argument(
        "--days", type=int, default=7, help="Archive files older than N days"
    )

    return handoffs_parser
