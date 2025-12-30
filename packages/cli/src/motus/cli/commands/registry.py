"""Parser construction for CLI commands."""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from motus import __version__

from .claims import register_claims_parsers
from .policy import register_policy_parsers
from .review import register_review_parsers
from .roadmap import register_roadmap_parsers
from .sessions import register_session_parsers
from .standards import register_standards_parsers
from .system import register_system_parsers
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


def build_parser() -> ParserBundle:
    """Build the CLI argument parser tree and return the parser bundle.

    Returns:
        ParserBundle containing the root parser and key subcommand parsers.
    """
    parser = argparse.ArgumentParser(
        description="""
Motus Command: Command Center for AI Agents.
Run 'mc web' for web dashboard at http://127.0.0.1:4000
Run 'mc --help' for a list of commands.
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", "-V", action="version", version=f"motus {__version__}")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    register_session_parsers(subparsers)
    standards_parser = register_standards_parsers(subparsers)
    claims_parser = register_claims_parsers(subparsers)
    policy_parser = register_policy_parsers(subparsers)
    roadmap_parser = register_roadmap_parsers(subparsers)
    work_parser = register_work_parsers(subparsers)
    register_review_parsers(subparsers)
    register_system_parsers(subparsers)

    return ParserBundle(
        parser=parser,
        standards_parser=standards_parser,
        claims_parser=claims_parser,
        policy_parser=policy_parser,
        roadmap_parser=roadmap_parser,
        work_parser=work_parser,
    )
