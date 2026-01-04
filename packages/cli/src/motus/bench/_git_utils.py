# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Git inspection helpers for benchmark fixtures.

Benchmarks run in temporary git repos. These helpers provide deterministic,
repo-relative diff signals (changed paths, numstat, etc) for scoring.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from motus.exceptions import SubprocessError, SubprocessTimeoutError
from motus.subprocess_utils import GIT_SHORT_TIMEOUT_SECONDS, run_subprocess


def _run_git(repo_dir: Path, argv: Sequence[str]) -> subprocess.CompletedProcess[bytes]:
    return run_subprocess(
        ["git", *argv],
        cwd=repo_dir,
        capture_output=True,
        check=False,
        timeout_seconds=GIT_SHORT_TIMEOUT_SECONDS,
        what="git",
    )


def _is_git_worktree(repo_dir: Path) -> bool:
    try:
        proc = _run_git(repo_dir, ["rev-parse", "--is-inside-work-tree"])
    except (SubprocessTimeoutError, SubprocessError, FileNotFoundError):
        return False
    return proc.returncode == 0 and (proc.stdout or b"").strip() == b"true"


def _normalize_repo_rel_path(value: str) -> str:
    return value.replace("\\", "/").removeprefix("./")


def _git_status_delta_paths(repo_dir: Path) -> list[str]:
    proc = _run_git(repo_dir, ["status", "--porcelain=v1", "-z"])
    if proc.returncode != 0:
        return []

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
            if i + 1 < len(tokens) and tokens[i + 1]:
                path2 = tokens[i + 1].decode("utf-8", errors="surrogateescape")
                paths.add(_normalize_repo_rel_path(path2))
                i += 2
                continue

        paths.add(_normalize_repo_rel_path(path1))
        i += 1

    return sorted(p for p in paths if p)


@dataclass(frozen=True)
class GitNameStatusEntry:
    status: str
    path: str
    old_path: str | None = None

    def to_dict(self) -> dict:
        payload: dict = {"status": self.status, "path": self.path}
        if self.old_path is not None:
            payload["old_path"] = self.old_path
        return payload


@dataclass(frozen=True)
class GitNumStatEntry:
    path: str
    added: int | None
    deleted: int | None

    def to_dict(self) -> dict:
        return {"path": self.path, "added": self.added, "deleted": self.deleted}


def _git_untracked_paths(repo_dir: Path) -> list[str]:
    proc = _run_git(repo_dir, ["ls-files", "--others", "--exclude-standard", "-z"])
    if proc.returncode != 0:
        return []
    raw = proc.stdout or b""
    tokens = raw.split(b"\0")
    paths: list[str] = []
    for token in tokens:
        if not token:
            continue
        path = token.decode("utf-8", errors="surrogateescape")
        paths.append(_normalize_repo_rel_path(path))
    return sorted(set(p for p in paths if p))


def _count_file_lines(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8").splitlines())
    except (OSError, UnicodeDecodeError):
        return 0


def _git_status_name_status(repo_dir: Path) -> list[GitNameStatusEntry]:
    """Return repo-relative name-status entries (includes untracked) from git status porcelain."""

    proc = _run_git(repo_dir, ["status", "--porcelain=v1", "-z"])
    if proc.returncode != 0:
        return []

    raw = proc.stdout or b""
    tokens = raw.split(b"\0")
    entries: list[GitNameStatusEntry] = []

    i = 0
    while i < len(tokens):
        entry = tokens[i]
        if not entry:
            break

        if len(entry) < 4 or entry[2:3] != b" ":
            i += 1
            continue

        xy = entry[:2].decode("utf-8", errors="surrogateescape")
        path1 = entry[3:].decode("utf-8", errors="surrogateescape")
        path1 = _normalize_repo_rel_path(path1)
        x, y = xy[0], xy[1]

        def _map_status() -> str:
            if xy == "??":
                return "A"
            if "D" in {x, y}:
                return "D"
            if "R" in {x, y}:
                return "R"
            if "C" in {x, y}:
                return "C"
            if "A" in {x, y}:
                return "A"
            if "M" in {x, y}:
                return "M"
            return "M"

        status = _map_status()

        if status in {"R", "C"}:
            if i + 1 < len(tokens) and tokens[i + 1]:
                path2 = tokens[i + 1].decode("utf-8", errors="surrogateescape")
                path2 = _normalize_repo_rel_path(path2)
                entries.append(GitNameStatusEntry(status=status, path=path2, old_path=path1))
                i += 2
                continue

        entries.append(GitNameStatusEntry(status=status, path=path1))
        i += 1

    by_key = {(e.status, e.path, e.old_path): e for e in entries}
    return sorted(by_key.values(), key=lambda e: (e.path, e.status))


def _git_diff_numstat(repo_dir: Path) -> tuple[list[GitNumStatEntry], int, int]:
    """Return numstat entries plus total added/deleted line counts (best-effort)."""

    proc = _run_git(repo_dir, ["diff", "--numstat", "-z"])
    if proc.returncode != 0:
        return [], 0, 0

    raw = proc.stdout or b""
    tokens = raw.split(b"\0")
    entries: list[GitNumStatEntry] = []
    total_added = 0
    total_deleted = 0

    for token in tokens:
        if not token:
            continue
        parts = token.split(b"\t")
        if len(parts) < 3:
            continue
        added_raw, deleted_raw, path_raw = parts[0], parts[1], parts[2]
        path = _normalize_repo_rel_path(path_raw.decode("utf-8", errors="surrogateescape"))

        def _parse_count(value: bytes) -> int | None:
            text = value.decode("utf-8", errors="surrogateescape")
            if text.strip() == "-":
                return None
            try:
                return int(text)
            except ValueError:
                return None

        added = _parse_count(added_raw)
        deleted = _parse_count(deleted_raw)
        if added is not None:
            total_added += added
        if deleted is not None:
            total_deleted += deleted
        entries.append(GitNumStatEntry(path=path, added=added, deleted=deleted))

    # Best-effort accounting for untracked files (git diff doesn't include them).
    for untracked in _git_untracked_paths(repo_dir):
        lines = _count_file_lines(repo_dir / untracked)
        total_added += lines
        entries.append(GitNumStatEntry(path=untracked, added=lines, deleted=0))

    by_path = {e.path: e for e in entries}
    return list(sorted(by_path.values(), key=lambda e: e.path)), total_added, total_deleted
