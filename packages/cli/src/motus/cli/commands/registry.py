# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Parser construction for CLI commands."""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from motus import __version__

from .activity import register_activity_parsers
from .audit import register_audit_parsers
from .claims import register_claims_parsers
from .db import register_db_parsers
from .handoffs import register_handoffs_parsers
from .health import register_health_parsers
from .policy import register_policy_parsers
from .release import register_release_parsers
from .review import register_review_parsers
from .roadmap import register_roadmap_parsers
from .sessions import register_session_parsers
from .standards import register_standards_parsers
from .system import register_system_parsers
from .verify import register_verify_parsers
from .work import register_work_parsers


@dataclass(frozen=True)
class ParserBundle:
    """Bundle of parser objects used for CLI dispatch and help output."""

    parser: argparse.ArgumentParser
    standards_parser: argparse.ArgumentParser
    claims_parser: argparse.ArgumentParser
    policy_parser: argparse.ArgumentParser
    roadmap_parser: argparse.ArgumentParser
    work_parser: argparse.ArgumentParser
    health_parser: argparse.ArgumentParser
    verify_parser: argparse.ArgumentParser
    handoffs_parser: argparse.ArgumentParser
    activity_parser: argparse.ArgumentParser
    audit_parser: argparse.ArgumentParser
    db_parser: argparse.ArgumentParser
    release_parser: argparse.ArgumentParser


def build_parser() -> ParserBundle:
    """Build the CLI argument parser tree and return the parser bundle.

    Returns:
        ParserBundle containing the root parser and key subcommand parsers.
    """
    parser = argparse.ArgumentParser(
        description="""
Motus: Command Center for AI Agents.
Run 'motus web' for web dashboard at http://127.0.0.1:4000
Run 'motus --help' for a list of commands.
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        "-V",
        action="version",
        version=f"motus {__version__} (MCSL)",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    register_session_parsers(subparsers)
    activity_parser = register_activity_parsers(subparsers)
    standards_parser = register_standards_parsers(subparsers)
    claims_parser = register_claims_parsers(subparsers)
    policy_parser = register_policy_parsers(subparsers)
    roadmap_parser = register_roadmap_parsers(subparsers)
    work_parser = register_work_parsers(subparsers)
    health_parser = register_health_parsers(subparsers)
    verify_parser = register_verify_parsers(subparsers)
    handoffs_parser = register_handoffs_parsers(subparsers)
    audit_parser = register_audit_parsers(subparsers)
    db_parser = register_db_parsers(subparsers)
    release_parser = register_release_parsers(subparsers)
    register_review_parsers(subparsers)
    register_system_parsers(subparsers)

    return ParserBundle(
        parser=parser,
        standards_parser=standards_parser,
        claims_parser=claims_parser,
        policy_parser=policy_parser,
        roadmap_parser=roadmap_parser,
        work_parser=work_parser,
        health_parser=health_parser,
        verify_parser=verify_parser,
        handoffs_parser=handoffs_parser,
        activity_parser=activity_parser,
        audit_parser=audit_parser,
        db_parser=db_parser,
        release_parser=release_parser,
    )
