# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Git helper functions for the vault policy gate runner.

These helpers provide git state detection and delta path extraction.
Extracted from _runner_utils.py to maintain module size limits.
"""

from __future__ import annotations

from pathlib import Path

from motus.policy.contracts import SourceState
from motus.subprocess_utils import GIT_SHORT_TIMEOUT_SECONDS, run_subprocess

RECON_EXCLUDE_DIR_NAMES = {".mc", ".pytest_cache", ".ruff_cache", ".mypy_cache", "__pycache__"}
RECON_EXCLUDE_FILE_NAMES = {".coverage", ".DS_Store"}

SAFE_SUBPROCESS_ENV_KEYS = {
    "PATH",
    "HOME",
    "USER",
    "LOGNAME",
    "SHELL",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TERM",
    "TMPDIR",
    "TEMP",
    "TMP",
    "TZ",
    "PYTHONHASHSEED",
    "SOURCE_DATE_EPOCH",
    "VIRTUAL_ENV",
    "PYTHONIOENCODING",
    "PYTHONUTF8",
    "PYTHONPATH",
    "PYTHONWARNINGS",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "REQUESTS_CA_BUNDLE",
    "CI",
    "GITHUB_ACTIONS",
    "SYSTEMROOT",
    "COMSPEC",
    "PATHEXT",
    "WINDIR",
}
SAFE_SUBPROCESS_ENV_PREFIXES = ("LC_", "XDG_")


def _safe_subprocess_env_for_git(parent: dict[str, str] | None = None) -> dict[str, str]:
    """Return a sanitized environment for git subprocesses."""
    import os

    source = dict(parent or os.environ)
    safe: dict[str, str] = {}
    for key, value in source.items():
        if key in SAFE_SUBPROCESS_ENV_KEYS or key.startswith(SAFE_SUBPROCESS_ENV_PREFIXES):
            safe[key] = value
    return safe


def is_git_worktree(repo_dir: Path) -> bool:
    """Check if repo_dir is inside a git worktree."""
    try:
        proc = run_subprocess(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            env=_safe_subprocess_env_for_git(),
            timeout_seconds=GIT_SHORT_TIMEOUT_SECONDS,
            what="git rev-parse",
        )
    except Exception:
        return False

    return proc.returncode == 0 and (proc.stdout or "").strip() == "true"


def normalize_scope_path(value: str) -> str:
    """Normalize a path for scope matching."""
    return value.replace("\\", "/").removeprefix("./")


def is_excluded_delta_path(path: str) -> bool:
    """Check if a delta path should be excluded from processing."""
    normalized = normalize_scope_path(path)
    parts = [p for p in normalized.strip("/").split("/") if p]
    if any(part in RECON_EXCLUDE_DIR_NAMES for part in parts):
        return True
    if parts and parts[-1] in RECON_EXCLUDE_FILE_NAMES:
        return True
    return False


def git_status_delta_paths(repo_dir: Path) -> list[str]:
    """Return repo-relative paths reported by `git status --porcelain=v1 -z`."""

    proc = run_subprocess(
        ["git", "status", "--porcelain=v1", "-z"],
        cwd=repo_dir,
        capture_output=True,
        env=_safe_subprocess_env_for_git(),
        timeout_seconds=GIT_SHORT_TIMEOUT_SECONDS,
        what="git status",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git status failed (exit={proc.returncode})")

    raw = proc.stdout or b""
    tokens = raw.split(b"\0")
    paths: set[str] = set()

    i = 0
    while i < len(tokens):
        entry = tokens[i]
        if not entry:
            break

        if len(entry) < 4 or entry[2:3] != b" ":
            i += 1
            continue

        x = chr(entry[0])
        path1 = entry[3:].decode("utf-8", errors="surrogateescape")

        if x in {"R", "C"}:
            # Renames/copies have two paths in -z mode.
            if i + 1 < len(tokens) and tokens[i + 1]:
                path2 = tokens[i + 1].decode("utf-8", errors="surrogateescape")
                paths.add(normalize_scope_path(path2))
                i += 2
                continue

        paths.add(normalize_scope_path(path1))
        i += 1

    return sorted(p for p in paths if p and not is_excluded_delta_path(p))


def git_head_commit_sha(repo_dir: Path) -> str | None:
    """Return the 40-hex HEAD commit SHA, or None if unavailable."""

    try:
        proc = run_subprocess(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            env=_safe_subprocess_env_for_git(),
            timeout_seconds=GIT_SHORT_TIMEOUT_SECONDS,
            what="git rev-parse HEAD",
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    sha = (proc.stdout or "").strip()
    if len(sha) != 40:
        return None
    return sha


def git_head_ref(repo_dir: Path) -> str | None:
    """Return the current symbolic ref (e.g., refs/heads/main) when available."""

    try:
        proc = run_subprocess(
            ["git", "symbolic-ref", "-q", "HEAD"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            env=_safe_subprocess_env_for_git(),
            timeout_seconds=GIT_SHORT_TIMEOUT_SECONDS,
            what="git symbolic-ref",
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    ref = (proc.stdout or "").strip()
    return ref or None


def git_is_dirty(repo_dir: Path) -> bool | None:
    """Return True/False if git status is available, otherwise None."""

    try:
        delta_paths = git_status_delta_paths(repo_dir)
    except Exception:
        return None
    return bool(delta_paths)


def git_source_state(repo_dir: Path) -> SourceState | None:
    """Return SourceState for a git worktree, or None when unavailable."""

    commit_sha = git_head_commit_sha(repo_dir)
    dirty = git_is_dirty(repo_dir)
    if commit_sha is None or dirty is None:
        return None
    return SourceState(vcs="git", commit_sha=commit_sha, dirty=dirty, ref=git_head_ref(repo_dir))
