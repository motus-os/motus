# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Parser construction for audit commands."""

from __future__ import annotations

import argparse


def register_audit_parsers(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    audit_parser = subparsers.add_parser(
        "audit",
        help="Audit finding pipeline utilities",
    )
    audit_subparsers = audit_parser.add_subparsers(dest="audit_command", help="Audit commands")

    add_parser = audit_subparsers.add_parser(
        "add", help="Record an audit finding"
    )
    add_parser.add_argument("--title", required=True, help="Finding title")
    add_parser.add_argument("--description", default="", help="Finding description")
    add_parser.add_argument(
        "--severity",
        default="medium",
        choices=["low", "medium", "high", "critical"],
        help="Severity (low|medium|high|critical)",
    )
    add_parser.add_argument(
        "--evidence",
        action="append",
        default=[],
        help="Evidence link or path (repeatable)",
    )
    add_parser.add_argument("--json", action="store_true", help="Emit JSON output")

    promote_parser = audit_subparsers.add_parser(
        "promote", help="Promote a finding to CR and/or roadmap"
    )
    promote_parser.add_argument("finding_id", help="Audit finding ID")
    promote_parser.add_argument("--cr", action="store_true", help="Create change request")
    promote_parser.add_argument(
        "--roadmap", action="store_true", help="Create roadmap item"
    )
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
    promote_parser.add_argument("--title", help="Override title")
    promote_parser.add_argument("--description", help="Override description")
    promote_parser.add_argument(
        "--cr-id",
        help="Use existing CR id when creating roadmap item",
    )
    promote_parser.add_argument("--json", action="store_true", help="Emit JSON output")

    list_parser = audit_subparsers.add_parser("list", help="List audit findings")
    list_parser.add_argument("--limit", type=int, default=50, help="Max rows to show")
    list_parser.add_argument("--json", action="store_true", help="Emit JSON output")

    return audit_parser
