# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Argparse registration for gates commands."""

from __future__ import annotations

import argparse


def register_gates_parsers(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    """Register argparse parsers for gates subcommands."""
    gates_parser = subparsers.add_parser(
        "gates", help="Release gate registry utilities"
    )
    gates_subparsers = gates_parser.add_subparsers(
        dest="gates_command", help="Gates commands"
    )

    list_parser = gates_subparsers.add_parser("list", help="List registered gates")
    list_parser.add_argument(
        "--registry",
        help="Gate registry path (default: packages/cli/docs/standards/gates.yaml)",
    )
    list_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    show_parser = gates_subparsers.add_parser("show", help="Show gate details")
    show_parser.add_argument("gate_id", help="Gate id (e.g., GATE-CLI-001)")
    show_parser.add_argument(
        "--registry",
        help="Gate registry path (default: packages/cli/docs/standards/gates.yaml)",
    )
    show_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    return gates_parser
