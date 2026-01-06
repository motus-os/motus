# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Parser construction for scratch commands."""

from __future__ import annotations

import argparse


def register_scratch_parsers(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    scratch_parser = subparsers.add_parser(
        "scratch",
        help="Scratch store utilities",
    )
    scratch_parser.add_argument(
        "--root",
        help="Scratch root directory (defaults to .motus/scratch)",
    )
    scratch_subparsers = scratch_parser.add_subparsers(
        dest="scratch_command",
        help="Scratch commands",
    )

    add_parser = scratch_subparsers.add_parser("add", help="Create a scratch entry")
    add_parser.add_argument("--title", required=True, help="Entry title")
    add_parser.add_argument("--body", default="", help="Entry body")
    add_parser.add_argument(
        "--tag",
        action="append",
        default=[],
        help="Tag (repeatable)",
    )
    add_parser.add_argument("--json", action="store_true", help="Emit JSON output")

    list_parser = scratch_subparsers.add_parser("list", help="List scratch entries")
    list_parser.add_argument(
        "--status",
        help="Filter by status (open|promoted)",
    )
    list_parser.add_argument("--json", action="store_true", help="Emit JSON output")

    show_parser = scratch_subparsers.add_parser("show", help="Show a scratch entry")
    show_parser.add_argument("entry_id", help="Scratch entry ID")
    show_parser.add_argument("--json", action="store_true", help="Emit JSON output")

    promote_parser = scratch_subparsers.add_parser(
        "promote", help="Promote a scratch entry to roadmap"
    )
    promote_parser.add_argument("entry_id", help="Scratch entry ID")
    promote_parser.add_argument(
        "--phase",
        default="phase_h",
        help="Roadmap phase (default: phase_h)",
    )
    promote_parser.add_argument(
        "--item-type",
        default="work",
        help="Roadmap item type (default: work)",
    )
    promote_parser.add_argument("--title", help="Override roadmap title")
    promote_parser.add_argument("--description", help="Override roadmap description")
    promote_parser.add_argument("--json", action="store_true", help="Emit JSON output")

    rebuild_parser = scratch_subparsers.add_parser(
        "rebuild-index", help="Rebuild scratch index"
    )
    rebuild_parser.add_argument("--json", action="store_true", help="Emit JSON output")

    return scratch_parser


__all__ = ["register_scratch_parsers"]
