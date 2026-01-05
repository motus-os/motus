# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Parser registration for release evidence commands."""

from __future__ import annotations

import argparse


def register_release_parsers(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    release_parser = subparsers.add_parser(
        "release",
        help="Release evidence gates",
    )
    release_subparsers = release_parser.add_subparsers(dest="release_command", help="Release commands")

    check_parser = release_subparsers.add_parser(
        "check",
        help="Run release evidence checks (fail-closed)",
    )
    check_parser.add_argument("--json", action="store_true", help="Emit JSON output")

    bundle_parser = release_subparsers.add_parser(
        "bundle",
        help="Generate release evidence bundle JSON",
    )
    bundle_parser.add_argument(
        "--output",
        default="packages/cli/docs/quality/release-evidence.json",
        help="Output path for release evidence bundle",
    )
    bundle_parser.add_argument("--json", action="store_true", help="Emit JSON output")

    return release_parser
