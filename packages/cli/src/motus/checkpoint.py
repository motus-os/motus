# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""
State Checkpoints Module for Motus v0.3.

Git-based checkpoints that allow safe experimentation and rollback.
Uses git stash for state storage with a manifest of modified files.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from .checkpoint_models import Checkpoint
from .checkpoint_storage import (
    _find_stash_ref,
    _get_git_root,
    _get_modified_files,
    _git,
    _is_git_repo,
    _save_checkpoints,
    list_checkpoints,
)
from .subprocess_utils import GIT_LONG_TIMEOUT_SECONDS


def _require_git_root(repo_path: Path) -> Path:
    if not _is_git_repo(repo_path):
        raise ValueError("Not in a git repository")
    git_root = _get_git_root(repo_path)
    if git_root is None:
        raise ValueError("Could not determine git repository root")
    return git_root


def _resolve_checkpoint(checkpoint_id: str, git_root: Path) -> Checkpoint:
    for cp in list_checkpoints(git_root):
        if cp.id == checkpoint_id or cp.id.startswith(checkpoint_id):
            if cp.git_stash_ref is None:
                raise ValueError(f"Checkpoint {checkpoint_id} has no stash reference")
            return cp
    raise ValueError(f"Checkpoint not found: {checkpoint_id}")


def _resolve_checkpoint_stash_ref(target: Checkpoint, git_root: Path) -> str:
    stash_message = f"mc-checkpoint: {target.label}"
    stash_ref = _find_stash_ref(git_root, stash_message) or target.git_stash_ref
    if not stash_ref:
        raise ValueError(f"Checkpoint {target.id} has no stash reference")
    return stash_ref


def _update_checkpoint_stash_ref(
    checkpoint_id: str,
    stash_ref: Optional[str],
    git_root: Path,
) -> None:
    checkpoints = list_checkpoints(git_root)
    for idx, cp in enumerate(checkpoints):
        if cp.id == checkpoint_id:
            checkpoints[idx] = Checkpoint(
                id=cp.id,
                label=cp.label,
                timestamp=cp.timestamp,
                git_stash_ref=stash_ref,
                file_manifest=cp.file_manifest,
            )
            break
    _save_checkpoints(checkpoints, git_root)


def create_checkpoint(label: str, repo_path: Path) -> Checkpoint:
    """Create a new checkpoint of the current repository state."""
    git_root = _require_git_root(repo_path)

    modified_files = _get_modified_files(git_root)
    if not modified_files:
        raise ValueError("No changes to checkpoint")

    timestamp = datetime.now()
    checkpoint_id = f"mc-{timestamp.strftime('%Y%m%d-%H%M%S')}-{timestamp.microsecond // 1000:03d}"

    checkpoint = Checkpoint(
        id=checkpoint_id,
        label=label,
        timestamp=timestamp.isoformat(),
        git_stash_ref=None,
        file_manifest=modified_files,
    )

    checkpoints = list_checkpoints(git_root)
    checkpoints.insert(0, checkpoint)
    _save_checkpoints(checkpoints, git_root)

    stash_message = f"mc-checkpoint: {label}"
    result = _git(
        git_root,
        ["stash", "push", "-u", "-m", stash_message, "--", ".", ":(exclude).mc"],
        timeout_seconds=GIT_LONG_TIMEOUT_SECONDS,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Failed to create git stash: {result.stderr}")

    stash_ref = _find_stash_ref(git_root, stash_message)
    checkpoint.git_stash_ref = stash_ref
    _update_checkpoint_stash_ref(checkpoint_id, stash_ref, git_root)

    if stash_ref:
        result = _git(
            git_root,
            ["stash", "apply", "--index", stash_ref],
            timeout_seconds=GIT_LONG_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            _ = _git(
                git_root,
                ["stash", "apply", stash_ref],
                timeout_seconds=GIT_LONG_TIMEOUT_SECONDS,
            )

    return checkpoint


def rollback_checkpoint(checkpoint_id: str, repo_path: Path) -> Checkpoint:
    """Restore repository state to a previous checkpoint."""
    git_root = _require_git_root(repo_path)
    target = _resolve_checkpoint(checkpoint_id, git_root)

    _ = _git(
        git_root,
        ["stash", "push", "-u", "-m", "mc-rollback-safety", "--", ".", ":(exclude).mc"],
        timeout_seconds=GIT_LONG_TIMEOUT_SECONDS,
    )
    _ = _git(git_root, ["reset", "--hard", "HEAD"], timeout_seconds=GIT_LONG_TIMEOUT_SECONDS)
    _ = _git(git_root, ["clean", "-ffd", "-e", ".mc/"], timeout_seconds=GIT_LONG_TIMEOUT_SECONDS)

    checkpoint_stash_ref = _resolve_checkpoint_stash_ref(target, git_root)
    result = _git(
        git_root,
        ["stash", "apply", checkpoint_stash_ref],
        timeout_seconds=GIT_LONG_TIMEOUT_SECONDS,
    )

    if result.returncode != 0:
        _ = _git(git_root, ["reset", "--hard", "HEAD"], timeout_seconds=GIT_LONG_TIMEOUT_SECONDS)
        _ = _git(git_root, ["stash", "pop", "--quiet"], timeout_seconds=GIT_LONG_TIMEOUT_SECONDS)
        raise RuntimeError(f"Failed to apply checkpoint: {result.stderr}")

    return target


def diff_checkpoint(checkpoint_id: str, repo_path: Path) -> str:
    """Show changes between current state and a checkpoint."""
    git_root = _require_git_root(repo_path)
    target = _resolve_checkpoint(checkpoint_id, git_root)
    checkpoint_stash_ref = _resolve_checkpoint_stash_ref(target, git_root)

    result = _git(
        git_root,
        ["stash", "show", "-p", "--include-untracked", checkpoint_stash_ref],
        timeout_seconds=GIT_LONG_TIMEOUT_SECONDS,
    )

    if result.returncode != 0:
        result = _git(
            git_root,
            ["stash", "show", "-p", checkpoint_stash_ref],
            timeout_seconds=GIT_LONG_TIMEOUT_SECONDS,
        )

    if not result.stdout.strip() and target.file_manifest:
        untracked_info = "Checkpoint contains untracked files:\n"
        for f in target.file_manifest:
            untracked_info += f"  + {f}\n"
        return untracked_info

    if result.returncode != 0:
        raise RuntimeError(f"Failed to show diff: {result.stderr}")

    return result.stdout
