# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Release evidence CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rich.console import Console

from motus.cli.exit_codes import EXIT_ERROR, EXIT_SUCCESS
from motus.observability.audit import AuditEvent, AuditLogger
from motus.release.evidence_gate import run_release_evidence, write_release_bundle

console = Console()


def _repo_root() -> Path:
    cwd = Path.cwd()
    if (cwd / "packages/cli").exists():
        return cwd
    if (cwd / "pyproject.toml").exists() and cwd.name == "cli":
        return cwd.parent.parent
    return cwd


def _emit_audit(action: str, payload: dict[str, Any]) -> None:
    try:
        AuditLogger().emit(
            AuditEvent(
                event_type="release_evidence",
                actor="user",
                action=action,
                resource_type="release",
                resource_id=None,
                context=payload,
            )
        )
    except Exception:
        pass


def release_check_command(args: Any) -> int:
    repo_root = _repo_root()
    result = run_release_evidence(repo_root)
    payload = result.to_dict()
    _emit_audit("check", payload)

    if getattr(args, "json", False):
        console.print_json(json.dumps(payload, sort_keys=True))
    else:
        for check in payload["checks"]:
            status = "PASS" if check["passed"] else "FAIL"
            console.print(f"[{status}] {check['name']}: {check['message']}")
        console.print(f"\nOverall: {'PASS' if payload['passed'] else 'FAIL'}")
        if payload["blocked"]:
            console.print(f"Blocked by: {payload['blocked']}")

    return EXIT_SUCCESS if payload["passed"] else EXIT_ERROR


def release_bundle_command(args: Any) -> int:
    repo_root = _repo_root()
    result = run_release_evidence(repo_root)
    payload = result.to_dict()

    output_path = Path(getattr(args, "output", "release-evidence.json")).expanduser()
    if not output_path.is_absolute():
        output_path = repo_root / output_path
    write_release_bundle(output_path, result)
    payload["bundle_path"] = str(output_path)

    _emit_audit("bundle", payload)

    if getattr(args, "json", False):
        console.print_json(json.dumps(payload, sort_keys=True))
    else:
        console.print(f"Release evidence bundle: {output_path}", markup=False)
        console.print(f"Overall: {'PASS' if payload['passed'] else 'FAIL'}")

    return EXIT_SUCCESS if payload["passed"] else EXIT_ERROR
