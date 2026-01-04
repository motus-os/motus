# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Local knowledge store for agent mesh retrieval."""

from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

from motus.core.database import DatabaseManager
from motus.core.database_connection import configure_connection

_SCHEMA_VERSION = 1

_BASE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS knowledge_items (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    content TEXT NOT NULL,
    checksum TEXT NOT NULL,
    source_id TEXT NOT NULL,
    trust_level TEXT NOT NULL CHECK (trust_level IN ('authoritative', 'reviewed', 'draft')),
    observed_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    deleted_at TEXT,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    parent_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_knowledge_items_type ON knowledge_items(type);
CREATE INDEX IF NOT EXISTS idx_knowledge_items_deleted ON knowledge_items(deleted_at);
CREATE INDEX IF NOT EXISTS idx_knowledge_items_expires ON knowledge_items(expires_at);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    knowledge_id TEXT NOT NULL,
    chunk_id TEXT NOT NULL,
    content TEXT NOT NULL,
    checksum TEXT NOT NULL,
    embedding_version TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    deleted_at TEXT,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    parent_id TEXT,
    PRIMARY KEY (knowledge_id, chunk_id),
    FOREIGN KEY (knowledge_id) REFERENCES knowledge_items(id)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_deleted ON knowledge_chunks(deleted_at);

CREATE TABLE IF NOT EXISTS knowledge_edges (
    from_id TEXT NOT NULL,
    to_id TEXT NOT NULL,
    edge_type TEXT NOT NULL CHECK (edge_type IN ('applies_to', 'depends_on', 'variant_of', 'references')),
    weight INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    deleted_at TEXT,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    parent_id TEXT,
    PRIMARY KEY (from_id, to_id, edge_type),
    FOREIGN KEY (from_id) REFERENCES knowledge_items(id),
    FOREIGN KEY (to_id) REFERENCES knowledge_items(id)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_edges_from ON knowledge_edges(from_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_edges_to ON knowledge_edges(to_id);

CREATE TABLE IF NOT EXISTS product_working_set (
    product_id TEXT NOT NULL,
    knowledge_id TEXT NOT NULL,
    pinned INTEGER NOT NULL DEFAULT 0 CHECK (pinned IN (0, 1)),
    usage_score INTEGER NOT NULL DEFAULT 0 CHECK (usage_score >= 0),
    last_verified_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    deleted_at TEXT,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    parent_id TEXT,
    PRIMARY KEY (product_id, knowledge_id),
    FOREIGN KEY (knowledge_id) REFERENCES knowledge_items(id)
);

CREATE INDEX IF NOT EXISTS idx_working_set_product ON product_working_set(product_id);
CREATE INDEX IF NOT EXISTS idx_working_set_usage ON product_working_set(product_id, usage_score DESC);

CREATE TABLE IF NOT EXISTS knowledge_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    product_id TEXT NOT NULL,
    query_hash TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    state_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    deleted_at TEXT,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    parent_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_knowledge_snapshots_product ON knowledge_snapshots(product_id);

CREATE TABLE IF NOT EXISTS knowledge_snapshot_items (
    snapshot_id TEXT NOT NULL,
    knowledge_id TEXT NOT NULL,
    rank INTEGER NOT NULL,
    rationale TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    deleted_at TEXT,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    parent_id TEXT,
    PRIMARY KEY (snapshot_id, knowledge_id),
    FOREIGN KEY (snapshot_id) REFERENCES knowledge_snapshots(snapshot_id),
    FOREIGN KEY (knowledge_id) REFERENCES knowledge_items(id)
);

CREATE INDEX IF NOT EXISTS idx_snapshot_items_rank ON knowledge_snapshot_items(snapshot_id, rank);
"""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso_z(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _hash_parts(parts: Iterable[str]) -> str:
    joined = "|".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class KnowledgeResult:
    knowledge_id: str
    rationale: str


class KnowledgeStore:
    """Local knowledge store with deterministic retrieval."""

    def __init__(self, db_path: str | Path) -> None:
        if db_path is None:
            raise ValueError("db_path is required")
        self._db_path = str(db_path)
        self._db: DatabaseManager | None = None
        self._conn: sqlite3.Connection
        self._fts_enabled = False

        if self._db_path == ":memory:":
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            configure_connection(self._conn)
        else:
            self._db = DatabaseManager(Path(self._db_path))
            self._conn = self._db.get_connection()

        self._init_schema()

    def close(self) -> None:
        if self._db is not None:
            self._db.checkpoint_and_close()
        else:
            self._conn.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            yield self._conn
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise

    def _init_schema(self) -> None:
        self._conn.executescript(_BASE_SCHEMA_SQL)

        current = self._conn.execute("PRAGMA user_version").fetchone()[0]
        if current == 0:
            self._conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
        elif current != _SCHEMA_VERSION:
            raise RuntimeError(
                f"[KNOWLEDGE-001] Incompatible knowledge schema. "
                f"Database has v{current}, code expects v{_SCHEMA_VERSION}."
            )

        self._init_fts()
        self._conn.commit()

    def _init_fts(self) -> None:
        try:
            self._conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts
                USING fts5(
                    knowledge_id,
                    content,
                    created_at,
                    updated_at,
                    deleted_at,
                    version,
                    parent_id
                )
                """
            )
            self._fts_enabled = True
        except sqlite3.OperationalError:
            self._fts_enabled = False

    def _fts_upsert(self, knowledge_id: str, content: str) -> None:
        if not self._fts_enabled:
            return
        row = self._conn.execute(
            """
            SELECT created_at, updated_at, deleted_at, version, parent_id
            FROM knowledge_items
            WHERE id = ?
            """,
            (knowledge_id,),
        ).fetchone()
        self._conn.execute(
            "DELETE FROM knowledge_fts WHERE knowledge_id = ?",
            (knowledge_id,),
        )
        self._conn.execute(
            """
            INSERT INTO knowledge_fts (
                knowledge_id, content, created_at, updated_at, deleted_at, version, parent_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                knowledge_id,
                content,
                row[0] if row else None,
                row[1] if row else None,
                row[2] if row else None,
                row[3] if row else None,
                row[4] if row else None,
            ),
        )

    def _fts_delete(self, knowledge_id: str) -> None:
        if not self._fts_enabled:
            return
        self._conn.execute(
            "DELETE FROM knowledge_fts WHERE knowledge_id = ?",
            (knowledge_id,),
        )

    def state_hash(self) -> str:
        cursor = self._conn.execute(
            """
            SELECT id, checksum, version
            FROM knowledge_items
            WHERE deleted_at IS NULL
            ORDER BY id
            """
        )
        parts = [f"item:{row[0]}:{row[1]}:{row[2]}" for row in cursor.fetchall()]
        edge_cursor = self._conn.execute(
            """
            SELECT from_id, to_id, edge_type, weight, version
            FROM knowledge_edges
            WHERE deleted_at IS NULL
            ORDER BY from_id, to_id, edge_type
            """
        )
        parts.extend(
            f"edge:{row[0]}:{row[1]}:{row[2]}:{row[3]}:{row[4]}"
            for row in edge_cursor.fetchall()
        )
        return _hash_parts(parts)[:16]

    def working_set_hash(self, *, product_id: str) -> str:
        cursor = self._conn.execute(
            """
            SELECT knowledge_id, pinned, usage_score, version
            FROM product_working_set
            WHERE product_id = ? AND deleted_at IS NULL
            ORDER BY knowledge_id
            """,
            (product_id,),
        )
        parts = [f"{row[0]}:{row[1]}:{row[2]}:{row[3]}" for row in cursor.fetchall()]
        return _hash_parts(parts)[:16]

    def put_item(
        self,
        *,
        item_type: str,
        content: str,
        source_id: str,
        trust_level: str = "draft",
        observed_at: datetime | None = None,
        expires_at: datetime | None = None,
        item_id: str | None = None,
        parent_id: str | None = None,
    ) -> str:
        knowledge_id = item_id or _hash_text(content)
        checksum = _hash_text(content)
        now = _utcnow()
        observed = observed_at or now
        expires = _iso_z(expires_at) if expires_at else None

        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO knowledge_items (
                    id, type, content, checksum, source_id, trust_level,
                    observed_at, expires_at, parent_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    type = excluded.type,
                    content = excluded.content,
                    checksum = excluded.checksum,
                    source_id = excluded.source_id,
                    trust_level = excluded.trust_level,
                    observed_at = excluded.observed_at,
                    expires_at = excluded.expires_at,
                    updated_at = datetime('now'),
                    version = knowledge_items.version + 1,
                    parent_id = excluded.parent_id
                """,
                (
                    knowledge_id,
                    item_type,
                    content,
                    checksum,
                    source_id,
                    trust_level,
                    _iso_z(observed),
                    expires,
                    parent_id,
                ),
            )
            self._fts_upsert(knowledge_id, content)

        return knowledge_id

    def put_chunk(
        self,
        *,
        knowledge_id: str,
        chunk_id: str,
        content: str,
        embedding_version: str | None = None,
        parent_id: str | None = None,
    ) -> None:
        checksum = _hash_text(content)
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO knowledge_chunks (
                    knowledge_id, chunk_id, content, checksum, embedding_version, parent_id
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(knowledge_id, chunk_id) DO UPDATE SET
                    content = excluded.content,
                    checksum = excluded.checksum,
                    embedding_version = excluded.embedding_version,
                    updated_at = datetime('now'),
                    version = knowledge_chunks.version + 1,
                    parent_id = excluded.parent_id
                """,
                (
                    knowledge_id,
                    chunk_id,
                    content,
                    checksum,
                    embedding_version,
                    parent_id,
                ),
            )

    def link_edge(
        self,
        *,
        from_id: str,
        to_id: str,
        edge_type: str,
        weight: int = 1,
        parent_id: str | None = None,
    ) -> None:
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO knowledge_edges (
                    from_id, to_id, edge_type, weight, parent_id
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(from_id, to_id, edge_type) DO UPDATE SET
                    weight = excluded.weight,
                    updated_at = datetime('now'),
                    version = knowledge_edges.version + 1,
                    parent_id = excluded.parent_id
                """,
                (from_id, to_id, edge_type, weight, parent_id),
            )

    def pin_item(
        self,
        *,
        product_id: str,
        knowledge_id: str,
        pinned: bool = True,
        parent_id: str | None = None,
    ) -> None:
        pinned_val = 1 if pinned else 0
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO product_working_set (
                    product_id, knowledge_id, pinned, parent_id
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(product_id, knowledge_id) DO UPDATE SET
                    pinned = excluded.pinned,
                    updated_at = datetime('now'),
                    version = product_working_set.version + 1,
                    parent_id = excluded.parent_id
                """,
                (product_id, knowledge_id, pinned_val, parent_id),
            )

    def record_usage(self, *, product_id: str, knowledge_id: str, delta: int = 1) -> None:
        if delta <= 0:
            return
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO product_working_set (
                    product_id, knowledge_id, usage_score
                )
                VALUES (?, ?, ?)
                ON CONFLICT(product_id, knowledge_id) DO UPDATE SET
                    usage_score = product_working_set.usage_score + excluded.usage_score,
                    updated_at = datetime('now'),
                    version = product_working_set.version + 1
                """,
                (product_id, knowledge_id, delta),
            )

    def _anchor_ids(self, *, product_id: str) -> list[str]:
        rows = self._conn.execute(
            """
            SELECT knowledge_id
            FROM product_working_set
            WHERE product_id = ? AND deleted_at IS NULL
            ORDER BY knowledge_id ASC
            """,
            (product_id,),
        ).fetchall()
        anchors = {row[0] for row in rows}

        product_rows = self._conn.execute(
            """
            SELECT id
            FROM knowledge_items
            WHERE deleted_at IS NULL
              AND type = 'product'
              AND id IN (?, ?)
            """,
            (product_id, f"product:{product_id}"),
        ).fetchall()
        anchors.update(row[0] for row in product_rows)

        return sorted(anchors)

    def _allowed_ids(self, *, product_id: str, anchor_ids: list[str]) -> set[str]:
        allowed = set(anchor_ids)
        if not anchor_ids:
            return set()
        rows = self._conn.execute(
            """
            SELECT to_id
            FROM knowledge_edges
            WHERE from_id IN ({placeholders})
              AND deleted_at IS NULL
            ORDER BY to_id ASC
            """.format(  # nosec B608 - placeholders are ?,?,? count
                placeholders=",".join("?" * len(anchor_ids))
            ),
            anchor_ids,
        ).fetchall()
        allowed.update(row[0] for row in rows)
        return allowed

    def soft_delete_item(self, *, knowledge_id: str) -> None:
        with self.transaction() as conn:
            conn.execute(
                """
                UPDATE knowledge_items
                SET deleted_at = datetime('now'),
                    updated_at = datetime('now'),
                    version = version + 1
                WHERE id = ? AND deleted_at IS NULL
                """,
                (knowledge_id,),
            )
            conn.execute(
                """
                UPDATE product_working_set
                SET deleted_at = datetime('now'),
                    updated_at = datetime('now'),
                    version = version + 1
                WHERE knowledge_id = ? AND deleted_at IS NULL
                """,
                (knowledge_id,),
            )
            self._fts_delete(knowledge_id)

    def retrieve(
        self,
        *,
        product_id: str,
        intent: str,
        max_items: int = 20,
        policy_version: str = "v1",
        min_trust: str = "draft",
    ) -> tuple[str, list[KnowledgeResult]]:
        normalized_intent = " ".join(intent.strip().split())
        if max_items <= 0:
            state_hash = self.state_hash()
            working_set_hash = self.working_set_hash(product_id=product_id)
            query_hash = _hash_parts(
                [product_id, normalized_intent, str(max_items), state_hash, working_set_hash]
            )
            return self._create_snapshot(
                product_id, normalized_intent, policy_version, [], state_hash, query_hash
            )

        state_hash = self.state_hash()
        working_set_hash = self.working_set_hash(product_id=product_id)
        query_hash = _hash_parts(
            [product_id, normalized_intent, str(max_items), state_hash, working_set_hash]
        )
        now = _iso_z(_utcnow())
        trust_rank = {"draft": 0, "reviewed": 1, "authoritative": 2}
        min_rank = trust_rank.get(min_trust, 0)

        def is_allowed(row) -> bool:
            return trust_rank.get(row["trust_level"], 0) >= min_rank

        results: list[KnowledgeResult] = []
        seen: set[str] = set()

        anchor_ids = self._anchor_ids(product_id=product_id)
        allowed_ids = self._allowed_ids(product_id=product_id, anchor_ids=anchor_ids)

        pinned_rows = self._conn.execute(
            """
            SELECT pw.knowledge_id, pw.usage_score, ki.trust_level
            FROM product_working_set pw
            JOIN knowledge_items ki ON ki.id = pw.knowledge_id
            WHERE pw.product_id = ?
              AND pw.pinned = 1
              AND pw.deleted_at IS NULL
              AND ki.deleted_at IS NULL
              AND (ki.expires_at IS NULL OR ki.expires_at > ?)
            ORDER BY pw.usage_score DESC, pw.knowledge_id ASC
            """,
            (product_id, now),
        ).fetchall()

        for row in pinned_rows:
            if row["knowledge_id"] in seen or not is_allowed(row):
                continue
            results.append(KnowledgeResult(row["knowledge_id"], "pinned"))
            seen.add(row["knowledge_id"])
            if len(results) >= max_items:
                return self._create_snapshot(
                    product_id,
                    normalized_intent,
                    policy_version,
                    results,
                    state_hash,
                    query_hash,
                )

        working_rows = self._conn.execute(
            """
            SELECT pw.knowledge_id, pw.usage_score, ki.trust_level
            FROM product_working_set pw
            JOIN knowledge_items ki ON ki.id = pw.knowledge_id
            WHERE pw.product_id = ?
              AND pw.pinned = 0
              AND pw.deleted_at IS NULL
              AND ki.deleted_at IS NULL
              AND (ki.expires_at IS NULL OR ki.expires_at > ?)
            ORDER BY pw.usage_score DESC, pw.knowledge_id ASC
            """,
            (product_id, now),
        ).fetchall()

        for row in working_rows:
            if row["knowledge_id"] in seen or not is_allowed(row):
                continue
            results.append(KnowledgeResult(row["knowledge_id"], "working_set"))
            seen.add(row["knowledge_id"])
            if len(results) >= max_items:
                return self._create_snapshot(
                    product_id,
                    normalized_intent,
                    policy_version,
                    results,
                    state_hash,
                    query_hash,
                )

        if anchor_ids:
            edge_rows = self._conn.execute(
                """
                SELECT ke.to_id, ke.edge_type, ke.weight, ki.trust_level
                FROM knowledge_edges ke
                JOIN knowledge_items ki ON ki.id = ke.to_id
                WHERE ke.from_id IN ({placeholders})
                  AND ke.deleted_at IS NULL
                  AND ki.deleted_at IS NULL
                  AND (ki.expires_at IS NULL OR ki.expires_at > ?)
                ORDER BY ke.weight DESC, ke.to_id ASC
                """.format(  # nosec B608 - placeholders are ?,?,? count
                    placeholders=",".join("?" * len(anchor_ids))
                ),
                anchor_ids + [now],
            ).fetchall()

            for row in edge_rows:
                if row["to_id"] in seen or not is_allowed(row):
                    continue
                results.append(KnowledgeResult(row["to_id"], f"edge:{row['edge_type']}"))
                seen.add(row["to_id"])
                if len(results) >= max_items:
                    return self._create_snapshot(
                        product_id,
                        normalized_intent,
                        policy_version,
                        results,
                        state_hash,
                        query_hash,
                    )

        search_ids = self._search(normalized_intent, exclude=seen, allowed_ids=allowed_ids)
        trust_by_id: dict[str, str] = {}
        if search_ids:
            id_list = [knowledge_id for knowledge_id, _ in search_ids]
            placeholders = ",".join("?" * len(id_list))
            trust_rows = self._conn.execute(
                """
                SELECT id, trust_level
                FROM knowledge_items
                WHERE id IN ({placeholders})
                  AND deleted_at IS NULL
                  AND (expires_at IS NULL OR expires_at > ?)
                """.format(  # nosec B608 - placeholders are ?,?,? count
                    placeholders=placeholders
                ),
                id_list + [now],
            ).fetchall()
            trust_by_id = {row["id"]: row["trust_level"] for row in trust_rows}

        for knowledge_id, rationale in search_ids:
            if knowledge_id in seen:
                continue
            trust_level = trust_by_id.get(knowledge_id)
            if trust_level is None or not is_allowed({"trust_level": trust_level}):
                continue
            results.append(KnowledgeResult(knowledge_id, rationale))
            seen.add(knowledge_id)
            if len(results) >= max_items:
                break

        return self._create_snapshot(
            product_id,
            normalized_intent,
            policy_version,
            results,
            state_hash,
            query_hash,
        )

    def _search(
        self,
        intent: str,
        *,
        exclude: set[str],
        allowed_ids: set[str],
    ) -> list[tuple[str, str]]:
        intent = " ".join(intent.strip().split())
        if not intent:
            return []
        if not allowed_ids:
            return []

        if self._fts_enabled:
            rows = self._conn.execute(
                """
                SELECT knowledge_id
                FROM knowledge_fts
                WHERE knowledge_fts MATCH ?
                ORDER BY bm25(knowledge_fts), knowledge_id ASC
                """,
                (intent,),
            ).fetchall()
            return [
                (row[0], "search")
                for row in rows
                if row[0] not in exclude and row[0] in allowed_ids
            ]

        tokens = intent.split()
        if not tokens:
            return []
        like_expr = "%" + "%".join(tokens) + "%"
        rows = self._conn.execute(
            """
            SELECT id
            FROM knowledge_items
            WHERE content LIKE ?
            ORDER BY id ASC
            """,
            (like_expr,),
        ).fetchall()
        return [
            (row[0], "search")
            for row in rows
            if row[0] not in exclude and row[0] in allowed_ids
        ]

    def _create_snapshot(
        self,
        product_id: str,
        intent: str,
        policy_version: str,
        results: list[KnowledgeResult],
        state_hash: str,
        query_hash: str,
    ) -> tuple[str, list[KnowledgeResult]]:
        if not state_hash:
            state_hash = self.state_hash()
        snapshot_id = _hash_parts([query_hash, policy_version])[:32]

        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO knowledge_snapshots (
                    snapshot_id, product_id, query_hash, policy_version, state_hash
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(snapshot_id) DO UPDATE SET
                    updated_at = datetime('now'),
                    version = knowledge_snapshots.version + 1
                """,
                (snapshot_id, product_id, query_hash, policy_version, state_hash),
            )

            conn.execute(
                """
                UPDATE knowledge_snapshot_items
                SET deleted_at = datetime('now'),
                    updated_at = datetime('now'),
                    version = version + 1
                WHERE snapshot_id = ? AND deleted_at IS NULL
                """,
                (snapshot_id,),
            )

            for rank, entry in enumerate(results, start=1):
                conn.execute(
                    """
                    INSERT INTO knowledge_snapshot_items (
                        snapshot_id, knowledge_id, rank, rationale
                    )
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(snapshot_id, knowledge_id) DO UPDATE SET
                        rank = excluded.rank,
                        rationale = excluded.rationale,
                        deleted_at = NULL,
                        updated_at = datetime('now'),
                        version = knowledge_snapshot_items.version + 1
                    """,
                    (snapshot_id, entry.knowledge_id, rank, entry.rationale),
                )

        return snapshot_id, results

    def get_snapshot(self, snapshot_id: str) -> list[dict[str, str]]:
        rows = self._conn.execute(
            """
            SELECT ksi.knowledge_id, ksi.rank, ksi.rationale
            FROM knowledge_snapshot_items ksi
            WHERE ksi.snapshot_id = ? AND ksi.deleted_at IS NULL
            ORDER BY ksi.rank ASC
            """,
            (snapshot_id,),
        ).fetchall()
        return [
            {
                "knowledge_id": row[0],
                "rank": row[1],
                "rationale": row[2],
            }
            for row in rows
        ]
