# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""CLI commands: `motus standards ...`."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console

from motus.cli.exit_codes import EXIT_ERROR, EXIT_SUCCESS, EXIT_USAGE
from motus.orient.fs_resolver import find_motus_dir
from motus.standards.proposals import PromotionError, ProposalManager
from motus.standards.validator import StandardsValidator

console = Console()
error_console = Console(stderr=True)


def _load_mapping_from_string(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    if not raw:
        return {}

    # Prefer JSON when it looks like JSON.
    if raw[0] in ("{", "["):
        parsed = json.loads(raw)
    else:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = yaml.safe_load(raw)

    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        raise ValueError("Expected a mapping (object)")
    return parsed


def _load_mapping_arg(arg: str | None) -> dict[str, Any]:
    if arg is None:
        raise ValueError("Missing required mapping argument")

    if arg == "-":
        return _load_mapping_from_string(sys.stdin.read())

    maybe_path = Path(arg).expanduser()
    if maybe_path.exists() and maybe_path.is_file():
        return _load_mapping_from_string(maybe_path.read_text(encoding="utf-8"))

    return _load_mapping_from_string(arg)


def standards_validate_command(args) -> int:
    standard_path = getattr(args, "path", None)
    if not standard_path:
        error_console.print("Missing <path>", style="red", markup=False)
        return EXIT_USAGE

    vault_dir_arg = getattr(args, "vault_dir", None)
    vault_dir = Path(vault_dir_arg).expanduser().resolve() if vault_dir_arg else None

    registry_path = getattr(args, "registry", None)

    validator = StandardsValidator(vault_dir=vault_dir)
    result = validator.validate(standard_path, decision_type_registry_path=registry_path)

    if getattr(args, "json", False):
        console.print(json.dumps(result.to_dict(), indent=2, sort_keys=True), markup=False)
    else:
        status = "PASS" if result.ok else "FAIL"
        console.print(f"status: {status}", markup=False)
        if result.errors:
            console.print("errors:", markup=False)
            for e in result.errors:
                console.print(f"  - {e}", markup=False)

    return EXIT_SUCCESS if result.ok else EXIT_ERROR


def standards_propose_command(args) -> int:
    decision_type = getattr(args, "decision_type", None)
    if not decision_type:
        error_console.print("Missing --type", style="red", markup=False)
        return EXIT_USAGE

    try:
        context = _load_mapping_arg(getattr(args, "context", None))
        output = _load_mapping_arg(getattr(args, "output", None))
    except Exception as e:
        error_console.print(str(e), style="red", markup=False)
        return EXIT_USAGE

    why = getattr(args, "why", None)
    proposed_by = getattr(args, "by", None) or "unknown"

    motus_dir = find_motus_dir(Path.cwd())
    if motus_dir is None:
        error_console.print(
            "Not in a Motus workspace (missing .motus)",
            style="red",
            markup=False,
        )
        return EXIT_USAGE

    manager = ProposalManager(motus_dir=motus_dir)
    try:
        proposal, path = manager.propose(
            decision_type=decision_type,
            context=context,
            output=output,
            proposed_by=proposed_by,
            why=why,
        )
    except Exception as e:
        error_console.print(str(e), style="red", markup=False)
        return EXIT_USAGE

    if getattr(args, "json", False):
        console.print(
            json.dumps(
                {"ok": True, "proposal": proposal.to_dict(), "path": path.as_posix()},
                indent=2,
                sort_keys=True,
            ),
            markup=False,
        )
    else:
        console.print(f"created: {proposal.proposal_id}", markup=False)
        console.print(f"path: {path.as_posix()}", markup=False)

    return EXIT_SUCCESS


def standards_list_proposals_command(args) -> int:
    decision_type = getattr(args, "decision_type", None)
    status = getattr(args, "status", None)

    motus_dir = find_motus_dir(Path.cwd())
    if motus_dir is None:
        error_console.print(
            "Not in a Motus workspace (missing .motus)",
            style="red",
            markup=False,
        )
        return EXIT_USAGE

    manager = ProposalManager(motus_dir=motus_dir)
    try:
        proposals = manager.list_proposals(decision_type=decision_type, status=status)
    except Exception as e:
        error_console.print(str(e), style="red", markup=False)
        return EXIT_USAGE

    if getattr(args, "json", False):
        console.print(
            json.dumps(
                [
                    {"proposal": p.to_dict(), "path": path.as_posix()}
                    for p, path in proposals
                ],
                indent=2,
                sort_keys=True,
            ),
            markup=False,
        )
    else:
        for p, path in proposals:
            console.print(
                f"{p.proposal_id}\t{p.decision_type}\t{p.status}\t{p.created_at}\t{path.as_posix()}",
                markup=False,
            )

    return EXIT_SUCCESS


def standards_promote_command(args) -> int:
    proposal_id = getattr(args, "proposal_id", None)
    if not proposal_id:
        error_console.print("Missing <proposal_id>", style="red", markup=False)
        return EXIT_USAGE

    to_layer = getattr(args, "to", None)
    if not to_layer:
        error_console.print("Missing --to", style="red", markup=False)
        return EXIT_USAGE

    if to_layer == "system":
        error_console.print(
            "System layer is immutable; promote to user/project",
            style="red",
            markup=False,
        )
        return EXIT_USAGE

    motus_dir = find_motus_dir(Path.cwd())
    if motus_dir is None:
        error_console.print(
            "Not in a Motus workspace (missing .motus)",
            style="red",
            markup=False,
        )
        return EXIT_USAGE

    manager = ProposalManager(motus_dir=motus_dir)
    try:
        standard, standard_path, updated_proposal, proposal_path = manager.promote(
            proposal_id,
            to_layer=to_layer,
        )
    except PromotionError as e:
        error_console.print(str(e), style="red", markup=False)
        return EXIT_USAGE
    except Exception as e:
        error_console.print(str(e), style="red", markup=False)
        return EXIT_USAGE

    if getattr(args, "json", False):
        console.print(
            json.dumps(
                {
                    "ok": True,
                    "standard_id": standard.standard_id,
                    "standard_path": standard_path.as_posix(),
                    "proposal": updated_proposal.to_dict(),
                    "proposal_path": proposal_path.as_posix(),
                },
                indent=2,
                sort_keys=True,
            ),
            markup=False,
        )
    else:
        console.print(
            f"promoted: {proposal_id} -> {standard.standard_id}",
            markup=False,
        )
        console.print(f"standard_path: {standard_path.as_posix()}", markup=False)

    return EXIT_SUCCESS


def standards_reject_command(args) -> int:
    proposal_id = getattr(args, "proposal_id", None)
    if not proposal_id:
        error_console.print("Missing <proposal_id>", style="red", markup=False)
        return EXIT_USAGE

    reason = getattr(args, "reason", None)
    if not reason:
        error_console.print("Missing --reason", style="red", markup=False)
        return EXIT_USAGE

    motus_dir = find_motus_dir(Path.cwd())
    if motus_dir is None:
        error_console.print(
            "Not in a Motus workspace (missing .motus)",
            style="red",
            markup=False,
        )
        return EXIT_USAGE

    manager = ProposalManager(motus_dir=motus_dir)
    try:
        proposal, path = manager.reject(proposal_id, reason=reason)
    except Exception as e:
        error_console.print(str(e), style="red", markup=False)
        return EXIT_USAGE

    if getattr(args, "json", False):
        console.print(
            json.dumps(
                {"ok": True, "proposal": proposal.to_dict(), "path": path.as_posix()},
                indent=2,
                sort_keys=True,
            ),
            markup=False,
        )
    else:
        console.print(f"rejected: {proposal_id}", markup=False)
        console.print(f"path: {path.as_posix()}", markup=False)

    return EXIT_SUCCESS
