# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""SQLite UDFs for deterministic operations."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any


def _to_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _parse_iso(value: Any) -> datetime | None:
    text = _to_text(value)
    if text is None:
        return None
    raw = text.strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def mc_strip_prefix(value: Any, prefix: Any) -> str | None:
    text = _to_text(value)
    if text is None:
        return None
    prefix_text = _to_text(prefix) or ""
    if prefix_text and text.startswith(prefix_text):
        return text[len(prefix_text):]
    return text


def mc_sha256(value: Any) -> str | None:
    text = _to_text(value)
    if text is None:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def mc_id(prefix: Any, seed: Any) -> str | None:
    prefix_text = _to_text(prefix) or ""
    seed_text = _to_text(seed)
    if seed_text is None:
        return None
    digest = hashlib.sha256(seed_text.encode("utf-8")).hexdigest()[:12]
    return f"{prefix_text}-{digest}" if prefix_text else digest


def mc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def mc_date_add(value: Any, delta_seconds: Any) -> str | None:
    base = _parse_iso(value)
    if base is None:
        return None
    try:
        delta = int(delta_seconds)
    except (TypeError, ValueError):
        return None
    result = base + timedelta(seconds=delta)
    return result.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def mc_date_diff(a: Any, b: Any) -> int | None:
    left = _parse_iso(a)
    right = _parse_iso(b)
    if left is None or right is None:
        return None
    return int((right - left).total_seconds())


def register_udfs(conn) -> None:
    """Register deterministic UDFs on a SQLite connection."""
    conn.create_function("mc_strip_prefix", 2, mc_strip_prefix, deterministic=True)
    conn.create_function("mc_sha256", 1, mc_sha256, deterministic=True)
    conn.create_function("mc_id", 2, mc_id, deterministic=True)
    conn.create_function("mc_date_add", 2, mc_date_add, deterministic=True)
    conn.create_function("mc_date_diff", 2, mc_date_diff, deterministic=True)
    conn.create_function("mc_now_iso", 0, mc_now_iso)
