# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Work command parser registration.

Provides CLI access to the 6-call Work Compiler API:
- motus work claim <task_id> - Claim work and get lease
- motus work context <lease_id> - Get/refresh context (Lens)
- motus work outcome <lease_id> - Register deliverable
- motus work evidence <lease_id> - Record verification artifact
- motus work decision <lease_id> - Log decision
- motus work release <lease_id> - Release with outcome
- motus work status <lease_id> - Show current lease status
- motus work cleanup - Expire stale leases
- motus work list - List active leases
"""

from __future__ import annotations

import argparse


def register_work_parsers(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    """Register work subcommand and its sub-subcommands."""
    work_parser = subparsers.add_parser(
        "work",
        help="6-call Work Compiler API",
        description="Execute work using the 6-call Work Compiler protocol",
    )
    work_subparsers = work_parser.add_subparsers(dest="work_command", help="Work commands")

    # motus work claim <task_id>
    claim_parser = work_subparsers.add_parser(
        "claim",
        help="Claim work (get lease)",
        description="Reserve a roadmap item and get a lease with initial context",
    )
    claim_parser.add_argument("task_id", help="Roadmap item ID (e.g., PA-047)")
    claim_parser.add_argument(
        "--resource",
        "-r",
        action="append",
        dest="resources",
        metavar="TYPE:PATH",
        help="Resource to claim (e.g., file:src/main.py). Can specify multiple.",
    )
    claim_parser.add_argument("--intent", "-i", help="Description of what you'll do")
    claim_parser.add_argument("--agent", "-a", help="Agent ID (default: from MC_AGENT_ID)")
    claim_parser.add_argument("--ttl", type=int, default=3600, help="Lease TTL in seconds (default: 3600)")
    claim_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # motus work context <lease_id>
    context_parser = work_subparsers.add_parser(
        "context",
        help="Get/refresh context (Lens)",
        description="Assemble fresh context for an active lease",
    )
    context_parser.add_argument("lease_id", help="Active lease ID")
    context_parser.add_argument("--intent", "-i", help="Updated intent description")
    context_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # motus work outcome <lease_id>
    outcome_parser = work_subparsers.add_parser(
        "outcome",
        help="Register deliverable",
        description="Register a primary deliverable produced by the task",
    )
    outcome_parser.add_argument("lease_id", help="Active lease ID")
    outcome_parser.add_argument("outcome_type", help="Type of outcome (file, api, config, etc.)")
    outcome_parser.add_argument("--path", "-p", help="Path or identifier for the outcome")
    outcome_parser.add_argument("--description", "-d", help="Human-readable description")
    outcome_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # motus work evidence <lease_id>
    evidence_parser = work_subparsers.add_parser(
        "evidence",
        help="Record verification artifact",
        description="Store verification artifacts proving work was done correctly",
    )
    evidence_parser.add_argument("lease_id", help="Active lease ID")
    evidence_parser.add_argument(
        "evidence_type",
        help="Type of evidence (test_result, build_artifact, diff, log, "
        "attestation, screenshot, reference, document, policy_bundle, other)",
    )
    evidence_parser.add_argument("--passed", type=int, help="Number of tests passed")
    evidence_parser.add_argument("--failed", type=int, help="Number of tests failed")
    evidence_parser.add_argument("--skipped", type=int, help="Number of tests skipped")
    evidence_parser.add_argument("--diff", help="Summary of changes made")
    evidence_parser.add_argument("--log", help="Relevant log excerpt")
    evidence_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # motus work decision <lease_id>
    decision_parser = work_subparsers.add_parser(
        "decision",
        help="Log decision",
        description="Append a decision to the task's decision log",
    )
    decision_parser.add_argument("lease_id", help="Active lease ID")
    decision_parser.add_argument("decision_text", help="The decision made")
    decision_parser.add_argument("--rationale", "-r", help="Why this decision was made")
    decision_parser.add_argument(
        "--alternative",
        "-a",
        action="append",
        dest="alternatives",
        help="Alternative that was considered (can specify multiple)",
    )
    decision_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # motus work release <lease_id>
    release_parser = work_subparsers.add_parser(
        "release",
        help="Release with outcome",
        description="End the lease and record final disposition",
    )
    release_parser.add_argument("lease_id", help="Lease ID to release")
    release_parser.add_argument(
        "outcome",
        choices=["success", "failure", "partial", "aborted"],
        help="Final outcome",
    )
    release_parser.add_argument("--no-rollback", action="store_true", help="Skip rollback on failure")
    release_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # motus work status <lease_id>
    status_parser = work_subparsers.add_parser(
        "status",
        help="Show lease status",
        description="Show current status of a lease including outcomes, evidence, and decisions",
    )
    status_parser.add_argument("lease_id", help="Lease ID to check")
    status_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # motus work cleanup
    cleanup_parser = work_subparsers.add_parser(
        "cleanup",
        help="Expire stale leases",
        description="Expire stale leases to clear blocking entries",
    )
    cleanup_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # motus work list
    list_parser = work_subparsers.add_parser(
        "list",
        help="List active leases",
        description="List active work leases and their status",
    )
    list_parser.add_argument("--all", action="store_true", help="Include expired and released leases")
    list_parser.add_argument("--json", action="store_true", help="Output as JSON")

    return work_parser
