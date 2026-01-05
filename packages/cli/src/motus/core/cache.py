# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Lightweight TTL cache with optional persistence and telemetry."""

from __future__ import annotations

import atexit
import json
import os
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from motus.core.database_connection import get_db_manager
from motus.logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class CacheEntry:
    value: Any
    expires_at: float
    stored_at: float


class TTLCache:
    """In-memory TTL cache with LRU eviction."""

    def __init__(
        self,
        *,
        max_size: int,
        ttl_s: int,
        name: str,
        persist_path: Path | None = None,
    ) -> None:
        self.name = name
        self.max_size = max(1, int(max_size))
        self.ttl_s = max(1, int(ttl_s))
        self.persist_path = persist_path
        self._data: OrderedDict[str, CacheEntry] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._sets = 0

        if self.persist_path:
            self._load_persisted()

    def get(self, key: str) -> Any | None:
        now = time.time()
        entry = self._data.get(key)
        if entry is None:
            self._misses += 1
            return None
        if entry.expires_at <= now:
            self._data.pop(key, None)
            self._misses += 1
            return None
        self._data.move_to_end(key)
        self._hits += 1
        return entry.value

    def set(self, key: str, value: Any) -> None:
        now = time.time()
        expires_at = now + self.ttl_s
        entry = CacheEntry(value=value, expires_at=expires_at, stored_at=now)
        if key in self._data:
            self._data[key] = entry
            self._data.move_to_end(key)
        else:
            if len(self._data) >= self.max_size:
                self._data.popitem(last=False)
                self._evictions += 1
            self._data[key] = entry
        self._sets += 1

    def clear(self) -> None:
        self._data.clear()

    def invalidate_prefix(self, prefix: str) -> None:
        keys = [k for k in self._data.keys() if k.startswith(prefix)]
        for k in keys:
            self._data.pop(k, None)

    def stats(self) -> dict[str, int]:
        return {
            "hits": self._hits,
            "misses": self._misses,
            "evictions": self._evictions,
            "sets": self._sets,
            "size": len(self._data),
            "max_size": self.max_size,
            "ttl_s": self.ttl_s,
        }

    def _load_persisted(self) -> None:
        if not self.persist_path:
            return
        if not self.persist_path.exists():
            return
        try:
            payload = json.loads(self.persist_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning(f"Cache {self.name} failed to load persisted data: {exc}")
            return

        entries = payload.get("entries", [])
        now = time.time()
        for entry in entries:
            try:
                key = str(entry["key"])
                expires_at = float(entry["expires_at"])
                stored_at = float(entry.get("stored_at", now))
                if expires_at <= now:
                    continue
                value = entry["value"]
                self._data[key] = CacheEntry(value=value, expires_at=expires_at, stored_at=stored_at)
            except Exception:
                continue

    def persist(self) -> None:
        if not self.persist_path:
            return
        self.persist_path.parent.mkdir(parents=True, exist_ok=True)
        entries: list[dict[str, Any]] = []
        for key, entry in self._data.items():
            try:
                json.dumps(entry.value)
            except TypeError:
                continue
            entries.append(
                {
                    "key": key,
                    "value": entry.value,
                    "expires_at": entry.expires_at,
                    "stored_at": entry.stored_at,
                }
            )
        payload = {"name": self.name, "saved_at": time.time(), "entries": entries}
        self.persist_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


_REGISTERED: dict[str, TTLCache] = {}


def register_cache(name: str, cache: TTLCache) -> None:
    _REGISTERED[name] = cache


def emit_cache_metrics() -> None:
    if os.environ.get("MC_CACHE_METRICS", "1").lower() in {"0", "false", "no"}:
        return
    for name, cache in _REGISTERED.items():
        stats = cache.stats()
        if stats["hits"] + stats["misses"] + stats["sets"] == 0:
            continue
        try:
            db = get_db_manager()
            db.record_metric(
                operation="cache.metrics",
                elapsed_ms=0.0,
                success=True,
                metadata={"cache": name, **stats},
            )
        except Exception as exc:
            logger.warning(f"Failed to record cache metrics for {name}: {exc}")


def persist_registered_caches() -> None:
    for cache in _REGISTERED.values():
        cache.persist()


atexit.register(emit_cache_metrics)
atexit.register(persist_registered_caches)
