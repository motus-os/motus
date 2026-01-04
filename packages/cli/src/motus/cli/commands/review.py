# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Argparse registration for review command."""

from __future__ import annotations

import argparse


def register_review_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Register argparse parsers for review command.

    Args:
        subparsers: Argparse subparser collection for CLI commands.
    """
    review_parser = subparsers.add_parser(
        "review",
        help="Request review for a roadmap item",
    )
    review_parser.add_argument(
        "item_id",
        help="ID of item to mark for review",
    )
    review_parser.add_argument(
        "--comment",
        "-c",
        help="Add a review comment or note",
    )
    review_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON",
    )
