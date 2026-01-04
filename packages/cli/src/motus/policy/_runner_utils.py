# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Internal helpers for the vault policy gate runner.

This module exists to keep `motus.policy.run` small and focused on the
runner's public API (`run_gate_plan`). These helpers are not part of the public
contract and may change between releases.
"""

from __future__ import annotations

import os
import shlex
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

from motus.harness import detect_harness
from motus.policy._git_helpers import (
    SAFE_SUBPROCESS_ENV_KEYS,
    SAFE_SUBPROCESS_ENV_PREFIXES,
    git_head_commit_sha,
    git_head_ref,
    git_is_dirty,
    git_source_state,
    git_status_delta_paths,
    is_excluded_delta_path,
    is_git_worktree,
    normalize_scope_path,
)
from motus.policy.contracts import GateDefinition, VaultPolicyBundle
from motus.subprocess_utils import DEFAULT_GATE_TIMEOUT_SECONDS, run_subprocess

# Re-export git helpers with underscore prefix for backward compatibility
_is_git_worktree = is_git_worktree
_normalize_scope_path = normalize_scope_path
_is_excluded_delta_path = is_excluded_delta_path
_git_status_delta_paths = git_status_delta_paths
_git_head_commit_sha = git_head_commit_sha
_git_head_ref = git_head_ref
_git_is_dirty = git_is_dirty
_git_source_state = git_source_state


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _evidence_base_dir(repo_dir: Path, override: Path | None = None) -> Path:
    if override is not None:
        return override

    env = os.environ.get("MC_EVIDENCE_DIR", "").strip()
    if env:
        return Path(env).expanduser()

    return repo_dir / ".mc" / "evidence"


def _find_gate(policy: VaultPolicyBundle, gate_id: str) -> GateDefinition | None:
    return next((g for g in policy.gate_registry.gates if g.id == gate_id), None)


def _profile_requires_signature(profile_id: str | None) -> bool:
    return (profile_id or "personal") in {"team", "enterprise", "regulated"}


def _profile_requires_reconciliation(profile_id: str | None) -> bool:
    return (profile_id or "personal") in {"team", "enterprise", "regulated"}


def _profile_requires_permits(profile_id: str | None) -> bool:
    return (profile_id or "personal") in {"team", "enterprise", "regulated"}


def _safe_subprocess_env(parent: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return a sanitized environment for gate subprocesses."""

    source = dict(parent or os.environ)
    safe: dict[str, str] = {}
    for key, value in source.items():
        if key in SAFE_SUBPROCESS_ENV_KEYS or key.startswith(SAFE_SUBPROCESS_ENV_PREFIXES):
            safe[key] = value
    return safe


def _pick_harness_command(gate_kind: str, repo_dir: Path) -> str | None:
    """Pick a runnable harness command for a given gate kind."""

    harness = detect_harness(repo_dir)
    preferences_by_kind: dict[str, tuple[str, ...]] = {
        "plan": ("lint_command", "smoke_test", "test_command", "build_command"),
        "tool": ("smoke_test", "test_command", "lint_command", "build_command"),
        "artifact": ("build_command", "lint_command", "smoke_test", "test_command"),
        "egress": ("test_command", "smoke_test", "lint_command", "build_command"),
        "harness": ("smoke_test", "test_command", "lint_command", "build_command"),
    }

    for attr in preferences_by_kind.get(gate_kind, ()):
        value = getattr(harness, attr, None)
        if value:
            return value
    return None


def _parse_command_segments(command: Sequence[str] | str) -> list[list[str]]:
    """Parse a command spec into argv segments."""

    if not isinstance(command, str):
        if not command:
            raise ValueError("empty argv command")
        return [list(command)]

    tokens = shlex.split(command, posix=True)
    if not tokens:
        raise ValueError("empty command")

    unsupported = {"|", "||", ";", "&", ">", ">>", "<"}
    if any(token in unsupported for token in tokens):
        raise ValueError("unsupported shell syntax (only '&&' chaining is allowed)")

    segments: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token == "&&":
            if not current:
                raise ValueError("empty command segment before '&&'")
            segments.append(current)
            current = []
        else:
            current.append(token)

    if current:
        segments.append(current)

    if any(not seg for seg in segments):
        raise ValueError("empty command segment")

    return segments


def _run_command_segments(
    *,
    segments: Sequence[Sequence[str]],
    cwd: Path,
    stdout_path: Path,
    stderr_path: Path,
) -> int:
    """Run one or more argv segments, streaming output to files."""

    gate_timeout_seconds = DEFAULT_GATE_TIMEOUT_SECONDS
    raw_timeout = os.environ.get("MC_GATE_TIMEOUT_SECONDS", "").strip()
    if raw_timeout:
        try:
            gate_timeout_seconds = float(raw_timeout)
        except ValueError:
            gate_timeout_seconds = DEFAULT_GATE_TIMEOUT_SECONDS
    if gate_timeout_seconds <= 0:
        gate_timeout_seconds = DEFAULT_GATE_TIMEOUT_SECONDS

    with (
        stdout_path.open("w", encoding="utf-8") as stdout_file,
        stderr_path.open("w", encoding="utf-8") as stderr_file,
    ):
        for idx, argv in enumerate(segments):
            if idx > 0:
                stdout_file.write("\n")
                stderr_file.write("\n")

            proc = run_subprocess(
                list(argv),
                cwd=cwd,
                stdout=stdout_file,
                stderr=stderr_file,
                text=True,
                env=_safe_subprocess_env(),
                timeout_seconds=gate_timeout_seconds,
                what="gate subprocess",
            )
            if proc.returncode != 0:
                return proc.returncode

    return 0


def _plan_inline_for_manifest(plan) -> dict:
    # EvidenceManifest.plan.inline does not include profile_id (schema has additionalProperties=false).
    return {
        "version": plan.version,
        "policy_versions": plan.policy_versions.to_dict(),
        "packs": list(plan.packs),
        "pack_versions": [p.to_dict() for p in plan.pack_versions],
        "gate_tier": plan.gate_tier,
        "gates": list(plan.gates),
        "pack_cap": plan.pack_cap.to_dict(),
    }


def _signing_env() -> tuple[str | None, str | None]:
    key_id = os.environ.get("MC_EVIDENCE_KEY_ID", "").strip() or None
    key = os.environ.get("MC_EVIDENCE_SIGNING_KEY", "").strip() or None
    return key_id, key


def _parse_iso_datetime(value: str) -> datetime | None:
    raw = value.strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
