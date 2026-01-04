# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Atomic file I/O helpers.

This module provides best-effort atomic write primitives for critical Motus data
files (e.g., evidence manifests, checkpoint metadata). The goal is that a crash
mid-write never leaves a truncated/corrupt file behind: the file is either the
previous complete version or the new complete version.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from motus.observability.io_capture import record_file_write


def _fsync_dir(path: Path) -> None:
    """Best-effort fsync on a directory (durability for rename/replace)."""

    try:
        flags = os.O_RDONLY
        # O_DIRECTORY is POSIX-only.
        if hasattr(os, "O_DIRECTORY"):
            flags |= os.O_DIRECTORY  # type: ignore[attr-defined]
        fd = os.open(path, flags)
    except OSError:
        return

    try:
        os.fsync(fd)
    except OSError:
        return
    finally:
        try:
            os.close(fd)
        except OSError:
            pass


def atomic_write_text(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    """Write text to `path` atomically (temp file + replace).

    Implementation notes:
    - Temp file is created in the destination directory to keep the operation on
      the same filesystem/device (required for atomic replace).
    - `os.replace()` is used (atomic on POSIX, and overwrites on Windows).
    - The file is fsynced before replace; directory fsync is best-effort.
    """

    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    tmp_path = Path(tmp_name)

    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="\n") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())

        os.replace(tmp_path, path)
        _fsync_dir(path.parent)
        record_file_write(path, bytes_written=len(content.encode(encoding)), source="atomic_write_text")
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def atomic_write_json(
    path: Path,
    payload: Any,
    *,
    indent: int = 2,
    sort_keys: bool = True,
    encoding: str = "utf-8",
) -> None:
    """Write JSON to `path` atomically (pretty-printed, newline-terminated)."""

    content = json.dumps(payload, indent=indent, sort_keys=sort_keys, ensure_ascii=False) + "\n"
    atomic_write_text(path, content, encoding=encoding)
