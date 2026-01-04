# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""CLI command: `motus claims` (coordination claim registry)."""

from __future__ import annotations

import json
import os
from argparse import Namespace
from pathlib import Path

from rich.console import Console

from motus.cli.exit_codes import EXIT_ERROR, EXIT_SUCCESS, EXIT_USAGE
from motus.coordination.claims import ClaimConflict, ClaimRegistry, ClaimRegistryError
from motus.coordination.namespace_acl import NamespaceACL
from motus.orient.fs_resolver import find_motus_dir

console = Console()
error_console = Console(stderr=True)


def _resolve_agent_id(args: Namespace) -> str:
    agent_id = (getattr(args, "agent", None) or "").strip()
    if agent_id:
        return agent_id
    for env_var in ("MC_AGENT_ID", "MOTUS_AGENT_ID"):
        value = os.environ.get(env_var, "").strip()
        if value:
            return value
    raise ValueError("Missing --agent (or set MC_AGENT_ID)")


def _resolve_motus_dir() -> Path:
    motus_dir = find_motus_dir(Path.cwd())
    if motus_dir is None:
        raise ValueError("Not in a Motus workspace (missing .motus)")
    return motus_dir


def _resolve_registry_dir(args: Namespace, *, motus_dir: Path) -> Path:
    override = (getattr(args, "registry_dir", None) or "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return motus_dir / "state" / "locks" / "claims"


def _resolve_acl_path(args: Namespace, *, motus_dir: Path) -> Path:
    override = (getattr(args, "acl", None) or "").strip()
    if override:
        return Path(override).expanduser().resolve()

    for env_var in ("MC_NAMESPACE_ACL", "MOTUS_NAMESPACE_ACL"):
        raw = os.environ.get(env_var, "").strip()
        if raw:
            return Path(raw).expanduser().resolve()

    candidates = [
        motus_dir / "project" / "config" / "namespace-acl.yaml",
        motus_dir / "user" / "config" / "namespace-acl.yaml",
        motus_dir / "config" / "namespace-acl.yaml",  # legacy
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise ValueError(
        "Missing namespace ACL config. Create `.motus/project/config/namespace-acl.yaml` "
        "or pass `--acl <path>`."
    )


def claims_acquire_command(args: Namespace) -> int:
    """Argparse-dispatched handler for `motus claims acquire`."""

    try:
        agent_id = _resolve_agent_id(args)
        motus_dir = _resolve_motus_dir()
        registry_dir = _resolve_registry_dir(args, motus_dir=motus_dir)
        acl_path = _resolve_acl_path(args, motus_dir=motus_dir)
        acl = NamespaceACL.from_yaml_file(acl_path)
    except Exception as e:
        error_console.print(str(e), style="red", markup=False)
        return EXIT_USAGE

    namespace = (getattr(args, "namespace", None) or "").strip()
    if not namespace:
        error_console.print("Missing --namespace", style="red", markup=False)
        return EXIT_USAGE

    resource = (getattr(args, "resource", None) or "").strip()
    if not resource:
        error_console.print("Missing --resource", style="red", markup=False)
        return EXIT_USAGE

    task_id = (getattr(args, "task_id", None) or "").strip() or resource
    task_type = (getattr(args, "task_type", None) or "").strip() or "CR"
    lease_seconds = getattr(args, "lease_seconds", None)
    json_mode = bool(getattr(args, "json", False))

    registry = ClaimRegistry(registry_dir, namespace_acl=acl)
    try:
        result = registry.register_claim(
            task_id=task_id,
            task_type=task_type,
            agent_id=agent_id,
            namespace=namespace,
            resources=[{"type": "resource", "path": resource}],
            lease_duration_s=lease_seconds,
        )
    except (ClaimRegistryError, ValueError) as e:
        if json_mode:
            console.print(
                json.dumps(
                    {
                        "success": False,
                        "reason": "error",
                        "message": str(e),
                    },
                    indent=2,
                    sort_keys=True,
                ),
                markup=False,
            )
        else:
            error_console.print(str(e), style="red", markup=False)
        return EXIT_USAGE

    if isinstance(result, ClaimConflict):
        if json_mode:
            console.print(
                json.dumps(
                    {
                        "success": False,
                        "reason": "already_claimed",
                        "conflicts": [c.to_json() for c in result.conflicts],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                markup=False,
            )
        else:
            error_console.print(str(result), style="red", markup=False)
        return EXIT_ERROR

    if json_mode:
        console.print(
            json.dumps({"success": True, "claim": result.to_json()}, indent=2, sort_keys=True),
            markup=False,
        )
    else:
        console.print(
            f"Claimed {resource} in {namespace}: {result.claim_id}",
            markup=False,
        )
    return EXIT_SUCCESS


def claims_list_command(args: Namespace) -> int:
    """Argparse-dispatched handler for `motus claims list`."""

    try:
        agent_id = _resolve_agent_id(args)
        motus_dir = _resolve_motus_dir()
        registry_dir = _resolve_registry_dir(args, motus_dir=motus_dir)
        acl_path = _resolve_acl_path(args, motus_dir=motus_dir)
        acl = NamespaceACL.from_yaml_file(acl_path)
    except Exception as e:
        error_console.print(str(e), style="red", markup=False)
        return EXIT_USAGE

    namespace = getattr(args, "namespace", None)
    all_namespaces = bool(getattr(args, "all_namespaces", False))
    json_mode = bool(getattr(args, "json", False))

    registry = ClaimRegistry(registry_dir, namespace_acl=acl)
    try:
        claims = registry.list_claims(
            requesting_agent_id=agent_id,
            namespace=namespace,
            all_namespaces=all_namespaces,
        )
    except (ClaimRegistryError, ValueError) as e:
        if json_mode:
            console.print(
                json.dumps(
                    {
                        "success": False,
                        "reason": "error",
                        "message": str(e),
                    },
                    indent=2,
                    sort_keys=True,
                ),
                markup=False,
            )
        else:
            error_console.print(str(e), style="red", markup=False)
        return EXIT_USAGE

    if json_mode:
        console.print(
            json.dumps(
                {
                    "success": True,
                    "claims": [c.to_json() for c in claims],
                },
                indent=2,
                sort_keys=True,
            ),
            markup=False,
        )
        return EXIT_SUCCESS

    if not claims:
        console.print("No active claims", markup=False)
        return EXIT_SUCCESS

    for claim in claims:
        ns = (claim.namespace or "default").strip() or "default"
        resources = ", ".join(f"{r.type}:{r.path}" for r in claim.claimed_resources)
        console.print(
            f"{claim.claim_id}\t{ns}\t{claim.agent_id}\t{resources}",
            markup=False,
        )
    return EXIT_SUCCESS
