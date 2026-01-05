# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Standards YAML cache with TTL + warm-start persistence."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from motus.config import config
from motus.core.cache import TTLCache, register_cache


_CACHE_TTL_S = int(os.environ.get("MC_STANDARDS_CACHE_TTL_S", "300"))
_CACHE_SIZE = int(os.environ.get("MC_STANDARDS_CACHE_SIZE", "256"))

_CACHE_PATH = config.paths.state_dir / "cache" / "standards-cache.json"

_CACHE = TTLCache(
    max_size=_CACHE_SIZE,
    ttl_s=_CACHE_TTL_S,
    name="standards_yaml",
    persist_path=_CACHE_PATH,
)
register_cache("standards_yaml", _CACHE)


def clear_standards_cache() -> None:
    _CACHE.clear()


def load_standard_yaml(path: Path) -> dict[str, Any]:
    key = path.as_posix()
    mtime_ns = path.stat().st_mtime_ns

    cached = _CACHE.get(key)
    if cached is not None:
        cached_mtime = cached.get("mtime_ns")
        if cached_mtime == mtime_ns:
            return cached.get("data", {})

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        raw = {}
    _CACHE.set(key, {"mtime_ns": mtime_ns, "data": raw})
    return raw
