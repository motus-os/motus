# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Argparse registration for modules commands."""

from __future__ import annotations

import argparse


def register_modules_parsers(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    """Register argparse parsers for modules subcommands."""
    modules_parser = subparsers.add_parser(
        "modules", help="Module registry utilities"
    )
    modules_subparsers = modules_parser.add_subparsers(
        dest="modules_command", help="Modules commands"
    )

    list_parser = modules_subparsers.add_parser("list", help="List registered modules")
    list_parser.add_argument(
        "--registry",
        help="Module registry path (default: packages/cli/docs/standards/module-registry.yaml)",
    )
    list_parser.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON"
    )

    return modules_parser
