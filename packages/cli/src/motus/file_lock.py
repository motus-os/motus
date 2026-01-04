# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""File locking helpers for shared resources."""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class FileLockError(RuntimeError):
    """Raised when a file lock cannot be acquired."""


class PlatformNotSupportedError(FileLockError):
    """Raised when file locking is not supported on this platform."""


@contextmanager
def file_lock(
    path: Path,
    *,
    timeout: float = 10.0,
    exclusive: bool = True,
) -> Iterator[int | None]:
    """Acquire a file lock with timeout (best-effort on non-POSIX).

    On POSIX platforms, uses fcntl advisory locks. On platforms without fcntl,
    raises PlatformNotSupportedError (Motus v0.1.x does not support Windows).
    """
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
    except OSError as e:
        raise FileLockError(f"Could not open lock file: {lock_path}: {e}") from e

    try:
        try:
            import fcntl  # type: ignore[import-not-found]
        except ImportError as e:
            raise PlatformNotSupportedError(
                "Motus v0.1.x does not support Windows file locking."
            ) from e

        mode = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(lock_fd, mode | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise FileLockError(f"Could not acquire lock on {path} after {timeout}s")
                time.sleep(0.05)

        yield lock_fd
    finally:
        try:
            try:
                import fcntl  # type: ignore[import-not-found]

                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            except ImportError:
                pass
        finally:
            os.close(lock_fd)
