# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Checkpoint storage helpers for git-backed state."""

import json
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Optional, Sequence

from .atomic_io import atomic_write_json
from .checkpoint_models import Checkpoint
from .exceptions import SubprocessError, SubprocessTimeoutError
from .file_lock import FileLockError, file_lock
from .logging import get_logger
from .subprocess_utils import GIT_SHORT_TIMEOUT_SECONDS, run_subprocess

logger = get_logger(__name__)


def _git(
    repo_dir: Path,
    argv: Sequence[str],
    *,
    timeout_seconds: float = GIT_SHORT_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str]:
    """Run a git command with a timeout and consistent failures."""

    try:
        return run_subprocess(
            ["git", *argv],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout_seconds=timeout_seconds,
            what="git",
        )
    except (SubprocessTimeoutError, SubprocessError) as e:
        raise RuntimeError(str(e)) from e


def _get_checkpoints_file(repo_path: Path) -> Path:
    """Get the checkpoints metadata file for a repository."""
    mc_dir = repo_path / ".mc"
    mc_dir.mkdir(exist_ok=True)
    return mc_dir / "checkpoints.json"


def _is_git_repo(repo_path: Path) -> bool:
    """Check if directory is a git repository."""
    result = _git(repo_path, ["rev-parse", "--is-inside-work-tree"])
    return result.returncode == 0 and (result.stdout or "").strip() == "true"


def _get_git_root(repo_path: Path) -> Optional[Path]:
    """Get the git repository root directory."""
    result = _git(repo_path, ["rev-parse", "--show-toplevel"])
    if result.returncode == 0:
        return Path(result.stdout.strip())
    return None


def _get_modified_files(repo_path: Path) -> list[str]:
    """Get list of modified files in the working directory."""
    result = _git(repo_path, ["status", "--porcelain"])

    if result.returncode != 0:
        return []

    files = []
    for line in result.stdout.strip().split("\n"):
        if line.strip():
            filename = line[3:]
            if not filename.startswith(".mc/"):
                files.append(filename)

    return files


def _find_stash_ref(repo_path: Path, stash_message: str) -> Optional[str]:
    """Find the git stash reference for a given message."""
    result = _git(repo_path, ["stash", "list", "--format=%gd %s"])

    if result.returncode != 0:
        return None

    for line in result.stdout.strip().split("\n"):
        if stash_message in line:
            parts = line.split()
            if parts:
                return parts[0]

    return None


def list_checkpoints(repo_path: Path) -> list[Checkpoint]:
    """List all available checkpoints for a repository."""
    if not _is_git_repo(repo_path):
        return []

    git_root = _get_git_root(repo_path)
    if git_root is None:
        return []

    checkpoints_file = _get_checkpoints_file(git_root)

    if not checkpoints_file.exists():
        return []

    try:
        with file_lock(checkpoints_file, exclusive=False):
            data = json.loads(checkpoints_file.read_text())
        return [Checkpoint(**cp) for cp in data]
    except FileLockError as e:
        logger.warning(
            "Failed to acquire checkpoints lock",
            checkpoints_file=str(checkpoints_file),
            error_type=type(e).__name__,
            error=str(e),
        )
        return []
    except (OSError, json.JSONDecodeError, TypeError, KeyError) as e:
        logger.warning(
            "Failed to read checkpoints file",
            checkpoints_file=str(checkpoints_file),
            error_type=type(e).__name__,
            error=str(e),
        )
        return []


def _save_checkpoints(checkpoints: list[Checkpoint], repo_path: Path) -> None:
    """Save checkpoints metadata to disk."""
    git_root = _get_git_root(repo_path)
    if git_root is None:
        raise ValueError("Not in a git repository")

    checkpoints_file = _get_checkpoints_file(git_root)
    data = [asdict(cp) for cp in checkpoints]
    try:
        with file_lock(checkpoints_file, exclusive=True):
            atomic_write_json(checkpoints_file, data)
    except FileLockError as e:
        raise RuntimeError(f"Failed to acquire checkpoints lock: {checkpoints_file}: {e}") from e
