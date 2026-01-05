# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Parser construction for database maintenance commands."""

from __future__ import annotations

import argparse


def register_db_parsers(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    db_parser = subparsers.add_parser(
        "db",
        help="Database maintenance utilities",
    )
    db_subparsers = db_parser.add_subparsers(dest="db_command", help="DB commands")

    vacuum_parser = db_subparsers.add_parser("vacuum", help="Run VACUUM on coordination DB")
    vacuum_parser.add_argument(
        "--full",
        action="store_true",
        help="Run ANALYZE after VACUUM",
    )

    db_subparsers.add_parser("analyze", help="Run ANALYZE for query planner stats")

    stats_parser = db_subparsers.add_parser("stats", help="Show DB size and table counts")
    stats_parser.add_argument("--json", action="store_true", help="Emit JSON output")

    db_subparsers.add_parser("checkpoint", help="Force WAL checkpoint")

    return db_parser
