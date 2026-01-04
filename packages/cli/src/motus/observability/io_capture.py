# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Best-effort IO capture (filesystem + network).

These helpers log metadata only (paths, sizes, status codes), never content.
Failures are swallowed to avoid disrupting core flows.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from motus.observability.activity import ActivityLedger


def _emit_event(category: str, action: str, subject: dict[str, Any]) -> None:
    try:
        ActivityLedger().emit(
            actor="system",
            category=category,
            action=action,
            subject=subject,
        )
    except Exception:
        # Best-effort logging only.
        return


def record_file_read(path: Path, *, bytes_read: int | None = None, source: str | None = None) -> None:
    _emit_event(
        "fs",
        "read",
        {
            "path": str(path),
            "bytes": bytes_read,
            "source": source,
        },
    )


def record_file_write(path: Path, *, bytes_written: int | None = None, source: str | None = None) -> None:
    _emit_event(
        "fs",
        "write",
        {
            "path": str(path),
            "bytes": bytes_written,
            "source": source,
        },
    )


def record_network_call(
    *,
    url: str,
    method: str | None,
    status_code: int | None,
    bytes_in: int | None = None,
    bytes_out: int | None = None,
    source: str | None = None,
) -> None:
    _emit_event(
        "net",
        "request",
        {
            "url": url,
            "method": method,
            "status": status_code,
            "bytes_in": bytes_in,
            "bytes_out": bytes_out,
            "source": source,
        },
    )
