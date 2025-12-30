from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from motus.knowledge import KnowledgeStore


@pytest.fixture
def store() -> KnowledgeStore:
    knowledge_store = KnowledgeStore(db_path=":memory:")
    yield knowledge_store
    knowledge_store.close()


def _seed_basic(store: KnowledgeStore) -> tuple[str, str]:
    store.put_item(
        item_type="product",
        content="Product alpha",
        source_id="product:alpha",
        trust_level="authoritative",
        item_id="product:alpha",
    )
    base_id = store.put_item(
        item_type="workflow",
        content="Deploy workflow for product alpha",
        source_id="doc:alpha",
        trust_level="reviewed",
        item_id="wf-alpha",
    )
    related_id = store.put_item(
        item_type="workflow",
        content="Related workflow for alpha",
        source_id="doc:alpha",
        trust_level="reviewed",
        item_id="wf-alpha-related",
    )
    store.link_edge(from_id="product:alpha", to_id=base_id, edge_type="applies_to", weight=10)
    store.link_edge(from_id=base_id, to_id=related_id, edge_type="variant_of", weight=5)
    store.pin_item(product_id="alpha", knowledge_id=base_id, pinned=True)
    return base_id, related_id


def test_schema_contract(store: KnowledgeStore) -> None:
    required = {"created_at", "updated_at", "deleted_at", "version", "parent_id"}
    tables = [
        "knowledge_items",
        "knowledge_chunks",
        "knowledge_edges",
        "product_working_set",
        "knowledge_snapshots",
        "knowledge_snapshot_items",
    ]
    fts_row = store._conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'knowledge_fts'"
    ).fetchone()
    if fts_row:
        tables.append("knowledge_fts")

    for table in tables:
        cols = {
            row[1]
            for row in store._conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        assert required.issubset(cols)


def test_put_item_increments_version(store: KnowledgeStore) -> None:
    item_id = store.put_item(
        item_type="workflow",
        content="Initial content",
        source_id="doc:alpha",
        trust_level="draft",
        item_id="wf-1",
    )
    row = store._conn.execute(
        "SELECT version FROM knowledge_items WHERE id = ?",
        (item_id,),
    ).fetchone()
    assert row[0] == 1

    store.put_item(
        item_type="workflow",
        content="Updated content",
        source_id="doc:alpha",
        trust_level="reviewed",
        item_id="wf-1",
        parent_id="wf-0",
    )
    row = store._conn.execute(
        "SELECT version, parent_id FROM knowledge_items WHERE id = ?",
        (item_id,),
    ).fetchone()
    assert row[0] == 2
    assert row[1] == "wf-0"


def test_soft_delete_excludes_retrieval(store: KnowledgeStore) -> None:
    item_id = store.put_item(
        item_type="workflow",
        content="Workflow for product alpha",
        source_id="doc:alpha",
        trust_level="reviewed",
        item_id="wf-soft",
    )
    store.pin_item(product_id="alpha", knowledge_id=item_id, pinned=True)

    snapshot_id, results = store.retrieve(product_id="alpha", intent="workflow")
    assert snapshot_id
    assert item_id in {r.knowledge_id for r in results}

    store.soft_delete_item(knowledge_id=item_id)
    _, results_after = store.retrieve(product_id="alpha", intent="workflow")
    assert item_id not in {r.knowledge_id for r in results_after}


def test_edge_expansion(store: KnowledgeStore) -> None:
    base_id, related_id = _seed_basic(store)
    _, results = store.retrieve(product_id="alpha", intent="deploy")
    ids = [r.knowledge_id for r in results]
    assert base_id in ids
    assert related_id in ids


def test_search_finds_unpinned_item(store: KnowledgeStore) -> None:
    store.put_item(
        item_type="product",
        content="Product alpha",
        source_id="product:alpha",
        trust_level="authoritative",
        item_id="product:alpha",
    )
    item_id = store.put_item(
        item_type="workflow",
        content="Emergency rollback workflow",
        source_id="doc:alpha",
        trust_level="reviewed",
        item_id="wf-rollback",
    )
    store.link_edge(from_id="product:alpha", to_id=item_id, edge_type="applies_to", weight=10)
    _, results = store.retrieve(product_id="alpha", intent="rollback")
    assert item_id in {r.knowledge_id for r in results}


def test_min_trust_filters_results(store: KnowledgeStore) -> None:
    store.put_item(
        item_type="product",
        content="Product alpha",
        source_id="product:alpha",
        trust_level="authoritative",
        item_id="product:alpha",
    )
    reviewed_id = store.put_item(
        item_type="workflow",
        content="Reviewed workflow",
        source_id="doc:alpha",
        trust_level="reviewed",
        item_id="wf-reviewed",
    )
    auth_id = store.put_item(
        item_type="workflow",
        content="Authoritative workflow",
        source_id="doc:alpha",
        trust_level="authoritative",
        item_id="wf-auth",
    )
    store.link_edge(from_id="product:alpha", to_id=reviewed_id, edge_type="applies_to", weight=5)
    store.link_edge(from_id="product:alpha", to_id=auth_id, edge_type="applies_to", weight=10)

    _, results = store.retrieve(product_id="alpha", intent="workflow", min_trust="authoritative")
    ids = {r.knowledge_id for r in results}
    assert auth_id in ids
    assert reviewed_id not in ids


def test_snapshot_records(store: KnowledgeStore) -> None:
    _seed_basic(store)
    snapshot_id, results = store.retrieve(product_id="alpha", intent="deploy")

    row = store._conn.execute(
        "SELECT snapshot_id, state_hash FROM knowledge_snapshots WHERE snapshot_id = ?",
        (snapshot_id,),
    ).fetchone()
    assert row is not None
    assert row[0] == snapshot_id

    rows = store._conn.execute(
        "SELECT knowledge_id FROM knowledge_snapshot_items WHERE snapshot_id = ? AND deleted_at IS NULL",
        (snapshot_id,),
    ).fetchall()
    snapshot_ids = {r[0] for r in rows}
    assert snapshot_ids == {r.knowledge_id for r in results}


def test_deterministic_across_stores(tmp_path: Path) -> None:
    def build_store(path: Path) -> KnowledgeStore:
        knowledge_store = KnowledgeStore(db_path=path)
        _seed_basic(knowledge_store)
        return knowledge_store

    store_a = build_store(tmp_path / "a.db")
    store_b = build_store(tmp_path / "b.db")
    try:
        snapshot_a, results_a = store_a.retrieve(product_id="alpha", intent="deploy")
        snapshot_b, results_b = store_b.retrieve(product_id="alpha", intent="deploy")
    finally:
        store_a.close()
        store_b.close()

    assert snapshot_a == snapshot_b
    assert [r.knowledge_id for r in results_a] == [r.knowledge_id for r in results_b]


def test_retrieve_is_deterministic_with_same_state(store: KnowledgeStore) -> None:
    _seed_basic(store)
    snapshot_a, results_a = store.retrieve(product_id="alpha", intent="deploy")
    snapshot_b, results_b = store.retrieve(product_id="alpha", intent="deploy")
    assert snapshot_a == snapshot_b
    assert [r.knowledge_id for r in results_a] == [r.knowledge_id for r in results_b]


def test_edge_changes_affect_snapshot(store: KnowledgeStore) -> None:
    _seed_basic(store)
    snapshot_a, _ = store.retrieve(product_id="alpha", intent="deploy")
    extra_id = store.put_item(
        item_type="workflow",
        content="Extra workflow",
        source_id="doc:alpha",
        trust_level="reviewed",
        item_id="wf-extra",
    )
    store.link_edge(from_id="product:alpha", to_id=extra_id, edge_type="applies_to", weight=9)
    snapshot_b, results_b = store.retrieve(product_id="alpha", intent="deploy")
    assert snapshot_a != snapshot_b
    assert extra_id in {r.knowledge_id for r in results_b}


def test_unscoped_search_returns_empty(store: KnowledgeStore) -> None:
    store.put_item(
        item_type="workflow",
        content="Unscoped workflow",
        source_id="doc:alpha",
        trust_level="reviewed",
        item_id="wf-unscoped",
    )
    _, results = store.retrieve(product_id="alpha", intent="workflow")
    assert results == []


def test_schema_version_mismatch(tmp_path: Path) -> None:
    db_path = tmp_path / "knowledge.db"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA user_version = 999")
    conn.close()

    with pytest.raises(RuntimeError, match="Incompatible knowledge schema"):
        KnowledgeStore(db_path=db_path)
