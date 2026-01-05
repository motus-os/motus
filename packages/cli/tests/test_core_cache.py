from __future__ import annotations

from pathlib import Path

import yaml

from motus.core.cache import TTLCache
from motus.orient import standards_cache
from motus.session_store import SessionStore


def test_ttlcache_evicts_lru() -> None:
    cache = TTLCache(max_size=2, ttl_s=60, name="test")

    cache.set("a", 1)
    cache.set("b", 2)
    assert cache.get("a") == 1

    cache.set("c", 3)

    assert cache.get("b") is None
    stats = cache.stats()
    assert stats["evictions"] == 1
    assert stats["hits"] >= 1


def test_ttlcache_persist_roundtrip(tmp_path: Path) -> None:
    cache_path = tmp_path / "cache.json"

    cache = TTLCache(max_size=2, ttl_s=60, name="persist", persist_path=cache_path)
    cache.set("a", {"value": 1})
    cache.persist()

    restored = TTLCache(max_size=2, ttl_s=60, name="persist", persist_path=cache_path)
    assert restored.get("a") == {"value": 1}


def test_standards_cache_hits(monkeypatch, tmp_path: Path) -> None:
    data = {
        "id": "std-1",
        "type": "policy",
        "version": "v1",
        "applies_if": {},
        "output": {},
    }
    path = tmp_path / "standard.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")

    calls = {"count": 0}

    def _fake_load(raw: str):
        calls["count"] += 1
        return data

    monkeypatch.setattr(standards_cache.yaml, "safe_load", _fake_load)
    standards_cache.clear_standards_cache()

    first = standards_cache.load_standard_yaml(path)
    second = standards_cache.load_standard_yaml(path)

    assert first == data
    assert second == data
    assert calls["count"] == 1


def test_session_query_cache_invalidates(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.db")

    store.create_session(tmp_path, "codex")
    assert len(store.get_active_sessions()) == 1

    store.create_session(tmp_path, "sonnet")
    assert len(store.get_active_sessions()) == 2
