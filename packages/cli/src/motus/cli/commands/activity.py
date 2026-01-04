# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Parser construction for activity commands."""

from __future__ import annotations

import argparse


def register_activity_parsers(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    activity_parser = subparsers.add_parser(
        "activity",
        help="Activity proof ledger utilities",
    )
    activity_subparsers = activity_parser.add_subparsers(
        dest="activity_command", help="Activity commands"
    )

    list_parser = activity_subparsers.add_parser(
        "list", help="List recent activity ledger entries"
    )
    list_parser.add_argument("--limit", type=int, default=50, help="Max entries to show")

    activity_subparsers.add_parser(
        "status", help="Show ledger file location and size"
    )

    return activity_parser
