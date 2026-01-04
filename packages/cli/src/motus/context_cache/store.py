# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Context Cache store implementation.

SQLite-backed storage for ResourceSpecs, PolicyBundles, ToolSpecs, and Outcomes.
Implements ContextCacheReader protocol for the Lens compiler.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from motus.coordination.schemas import ClaimedResource as Resource
from motus.core import configure_connection

_SCHEMA_VERSION = 1

_INIT_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS resource_specs (
    id TEXT PRIMARY KEY,
    resource_type TEXT NOT NULL,
    resource_path TEXT NOT NULL,
    payload TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_resource_specs_type_path
    ON resource_specs(resource_type, resource_path);

CREATE TABLE IF NOT EXISTS policy_bundles (
    policy_version TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tool_specs (
    name TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS outcomes (
    outcome_id TEXT PRIMARY KEY,
    resource_type TEXT NOT NULL,
    resource_path TEXT NOT NULL,
    payload TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_outcomes_resource
    ON outcomes(resource_type, resource_path);

CREATE INDEX IF NOT EXISTS idx_outcomes_occurred
    ON outcomes(occurred_at DESC);
"""


def _iso_z(dt: datetime) -> str:
    """Format datetime as ISO 8601 with Z suffix."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ContextCache:
    """SQLite-backed Context Cache.

    Implements ContextCacheReader protocol for the Lens compiler.
    """

    def __init__(self, db_path: str | Path) -> None:
        """Initialize Context Cache.

        Args:
            db_path: Path to SQLite database. Use ":memory:" for testing only.

        Raises:
            ValueError: If db_path is None (must be explicit about persistence).
        """
        if db_path is None:
            raise ValueError(
                "db_path is required. Use ':memory:' explicitly for in-memory testing."
            )
        self._db_path = str(db_path)
        if self._db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        configure_connection(self._conn)
        self._init_schema()

    def _init_schema(self) -> None:
        """Initialize database schema.

        Raises:
            RuntimeError: If database schema version is incompatible.
        """
        cursor = self._conn.cursor()
        cursor.executescript(_INIT_SQL)

        # Check/set schema version
        cursor.execute("SELECT version FROM schema_version LIMIT 1")
        row = cursor.fetchone()
        if row is None:
            # Fresh database - set version
            cursor.execute("INSERT INTO schema_version (version) VALUES (?)", (_SCHEMA_VERSION,))
        else:
            # Existing database - validate version
            db_version = row[0]
            if db_version != _SCHEMA_VERSION:
                raise RuntimeError(
                    f"[CONTEXT-CACHE-001] Incompatible ContextCache schema version. "
                    f"Database has v{db_version}, code expects v{_SCHEMA_VERSION}. "
                    f"Delete {self._db_path} to reset (data will be regenerated)."
                )
        self._conn.commit()

    def close(self) -> None:
        """Close database connection."""
        self._conn.close()

    # =========================================================================
    # ContextCacheReader protocol implementation
    # =========================================================================

    def get_resource_spec(self, resource: Resource) -> dict[str, Any] | None:
        """Get ResourceSpec for a resource.

        Args:
            resource: Resource to look up (type + path).

        Returns:
            ResourceSpec payload with metadata, or None if not found.
        """
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT payload, source_hash, observed_at
            FROM resource_specs
            WHERE resource_type = ? AND resource_path = ?
            """,
            (resource.type, resource.path),
        )
        row = cursor.fetchone()
        if row is None:
            return None

        payload = json.loads(row["payload"])
        return {
            "payload": payload,
            "source_hash": row["source_hash"],
            "observed_at": row["observed_at"],
            "source_id": payload.get("id", f"{resource.type}:{resource.path}"),
        }

    def get_policy_bundle(self, policy_version: str) -> dict[str, Any] | None:
        """Get PolicyBundle for a version.

        Args:
            policy_version: Version string to look up.

        Returns:
            PolicyBundle payload with metadata, or None if not found.
        """
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT payload, source_hash, observed_at
            FROM policy_bundles
            WHERE policy_version = ?
            """,
            (policy_version,),
        )
        row = cursor.fetchone()
        if row is None:
            return None

        payload = json.loads(row["payload"])
        return {
            "payload": payload,
            "source_hash": row["source_hash"],
            "observed_at": row["observed_at"],
            "source_id": policy_version,
        }

    def get_tool_specs(
        self, tool_names: list[str]
    ) -> list[dict[str, Any]] | dict[str, dict[str, Any]]:
        """Get ToolSpecs for a list of tool names.

        Args:
            tool_names: List of tool names to look up.

        Returns:
            List of ToolSpec payloads with metadata.
        """
        if not tool_names:
            return []
        max_tools = max(1, int(os.environ.get("MC_TOOL_SPECS_MAX", "500")))
        if len(tool_names) > max_tools:
            raise ValueError(f"Too many tool names requested (max {max_tools})")

        cursor = self._conn.cursor()
        placeholders = ",".join("?" * len(tool_names))
        cursor.execute(
            f"""
            SELECT name, payload, source_hash, observed_at
            FROM tool_specs
            WHERE name IN ({placeholders})
            """,  # nosec B608 - placeholders are ?,?,? count
            tool_names,
        )

        results: list[dict[str, Any]] = []
        for row in cursor.fetchall():
            payload = json.loads(row["payload"])
            results.append(
                {
                    "payload": payload,
                    "source_hash": row["source_hash"],
                    "observed_at": row["observed_at"],
                    "source_id": row["name"],
                }
            )
        return results

    def get_recent_outcomes(
        self, resources: list[Resource], limit: int = 25
    ) -> list[dict[str, Any]]:
        """Get recent outcomes for resources.

        Args:
            resources: List of resources to get outcomes for.
            limit: Maximum number of outcomes to return.

        Returns:
            List of outcome payloads, most recent first.
        """
        if not resources:
            return []
        max_resources = max(1, int(os.environ.get("MC_OUTCOME_MAX_RESOURCES", "200")))
        if len(resources) > max_resources:
            raise ValueError(f"Too many resources requested (max {max_resources})")

        cursor = self._conn.cursor()
        conditions = " OR ".join(
            "(resource_type = ? AND resource_path = ?)" for _ in resources
        )
        params: list[str] = []
        for r in resources:
            params.extend([r.type, r.path])

        cursor.execute(
            f"""
            SELECT outcome_id, payload, occurred_at
            FROM outcomes
            WHERE {conditions}
            ORDER BY occurred_at DESC
            LIMIT ?
            """,  # nosec B608 - conditions are (type=? AND path=?) templates
            params + [limit],
        )

        results: list[dict[str, Any]] = []
        for row in cursor.fetchall():
            payload = json.loads(row["payload"])
            payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            source_hash = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
            results.append({
                "payload": payload,
                "source_hash": source_hash,
                "observed_at": row["occurred_at"],
                "source_id": row["outcome_id"],
            })
        return results

    # =========================================================================
    # State hash for provenance
    # =========================================================================

    def state_hash(self) -> str:
        """Compute deterministic hash of cache state.

        Used for Lens provenance tagging. Same data = same hash.
        """
        cursor = self._conn.cursor()

        # Collect all hashes in deterministic order
        hashes: list[str] = []

        cursor.execute("SELECT source_hash FROM resource_specs ORDER BY id")
        for row in cursor.fetchall():
            hashes.append(row["source_hash"])

        cursor.execute("SELECT source_hash FROM policy_bundles ORDER BY policy_version")
        for row in cursor.fetchall():
            hashes.append(row["source_hash"])

        cursor.execute("SELECT source_hash FROM tool_specs ORDER BY name")
        for row in cursor.fetchall():
            hashes.append(row["source_hash"])

        # Don't include outcomes in state hash (they're advisory, not authoritative)

        combined = "|".join(hashes)
        cursor.execute("SELECT mc_sha256(?)", (combined,))
        combined_hash = cursor.fetchone()[0] or ""
        return combined_hash[:16]

    # =========================================================================
    # Write operations (for populating the cache)
    # =========================================================================

    def put_resource_spec(
        self,
        resource_type: str,
        resource_path: str,
        spec: dict[str, Any],
        observed_at: datetime | None = None,
    ) -> str:
        """Store a ResourceSpec.

        Args:
            resource_type: Resource type (file, dir, external, db).
            resource_path: Resource path/identifier.
            spec: ResourceSpec payload (must match resource-spec.schema.json).
            observed_at: When this spec was observed. Defaults to now.

        Returns:
            The resource ID.
        """
        cursor = self._conn.cursor()
        cursor.execute("SELECT mc_strip_prefix(?, ?)", (resource_path, "./"))
        normalized_path = cursor.fetchone()[0] or resource_path
        resource_id = f"{resource_type}:{normalized_path}"
        payload_json = json.dumps(spec, sort_keys=True, separators=(",", ":"))
        cursor.execute("SELECT mc_sha256(?)", (payload_json,))
        source_hash = cursor.fetchone()[0]
        observed_value = _iso_z(observed_at) if observed_at else None

        cursor.execute(
            """
            INSERT INTO resource_specs
                (id, resource_type, resource_path, payload, source_hash, observed_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, COALESCE(?, mc_now_iso()), mc_now_iso(), mc_now_iso())
            ON CONFLICT(id) DO UPDATE SET
                payload = excluded.payload,
                source_hash = excluded.source_hash,
                observed_at = excluded.observed_at,
                updated_at = mc_now_iso()
            """,
            (
                resource_id,
                resource_type,
                normalized_path,
                payload_json,
                source_hash,
                observed_value,
            ),
        )
        self._conn.commit()
        return resource_id

    def put_policy_bundle(
        self,
        policy_version: str,
        bundle: dict[str, Any],
        observed_at: datetime | None = None,
    ) -> str:
        """Store a PolicyBundle.

        Args:
            policy_version: Version identifier for this bundle.
            bundle: PolicyBundle payload.
            observed_at: When this bundle was observed. Defaults to now.

        Returns:
            The policy version.
        """
        payload_json = json.dumps(bundle, sort_keys=True, separators=(",", ":"))
        cursor = self._conn.cursor()
        cursor.execute("SELECT mc_sha256(?)", (payload_json,))
        source_hash = cursor.fetchone()[0]
        observed_value = _iso_z(observed_at) if observed_at else None

        cursor.execute(
            """
            INSERT INTO policy_bundles
                (policy_version, payload, source_hash, observed_at, created_at, updated_at)
            VALUES (?, ?, ?, COALESCE(?, mc_now_iso()), mc_now_iso(), mc_now_iso())
            ON CONFLICT(policy_version) DO UPDATE SET
                payload = excluded.payload,
                source_hash = excluded.source_hash,
                observed_at = excluded.observed_at,
                updated_at = mc_now_iso()
            """,
            (
                policy_version,
                payload_json,
                source_hash,
                observed_value,
            ),
        )
        self._conn.commit()
        return policy_version

    def put_tool_spec(
        self,
        name: str,
        spec: dict[str, Any],
        observed_at: datetime | None = None,
    ) -> str:
        """Store a ToolSpec.

        Args:
            name: Tool name (must be unique).
            spec: ToolSpec payload.
            observed_at: When this spec was observed. Defaults to now.

        Returns:
            The tool name.
        """
        payload_json = json.dumps(spec, sort_keys=True, separators=(",", ":"))
        cursor = self._conn.cursor()
        cursor.execute("SELECT mc_sha256(?)", (payload_json,))
        source_hash = cursor.fetchone()[0]
        observed_value = _iso_z(observed_at) if observed_at else None

        cursor.execute(
            """
            INSERT INTO tool_specs
                (name, payload, source_hash, observed_at, created_at, updated_at)
            VALUES (?, ?, ?, COALESCE(?, mc_now_iso()), mc_now_iso(), mc_now_iso())
            ON CONFLICT(name) DO UPDATE SET
                payload = excluded.payload,
                source_hash = excluded.source_hash,
                observed_at = excluded.observed_at,
                updated_at = mc_now_iso()
            """,
            (
                name,
                payload_json,
                source_hash,
                observed_value,
            ),
        )
        self._conn.commit()
        return name

    def put_outcome(
        self,
        outcome_id: str,
        resource_type: str,
        resource_path: str,
        outcome: dict[str, Any],
        occurred_at: datetime | None = None,
    ) -> str:
        """Store an outcome.

        Args:
            outcome_id: Unique outcome identifier.
            resource_type: Resource type this outcome relates to.
            resource_path: Resource path this outcome relates to.
            outcome: Outcome payload.
            occurred_at: When this outcome occurred. Defaults to now.

        Returns:
            The outcome ID.
        """
        payload_json = json.dumps(outcome, sort_keys=True, separators=(",", ":"))
        cursor = self._conn.cursor()
        cursor.execute("SELECT mc_strip_prefix(?, ?)", (resource_path, "./"))
        normalized_path = cursor.fetchone()[0] or resource_path
        occurred_value = _iso_z(occurred_at) if occurred_at else None

        cursor.execute(
            """
            INSERT INTO outcomes
                (outcome_id, resource_type, resource_path, payload, occurred_at, created_at)
            VALUES (?, ?, ?, ?, COALESCE(?, mc_now_iso()), mc_now_iso())
            ON CONFLICT(outcome_id) DO UPDATE SET
                payload = excluded.payload,
                occurred_at = excluded.occurred_at
            """,
            (
                outcome_id,
                resource_type,
                normalized_path,
                payload_json,
                occurred_value,
            ),
        )
        self._conn.commit()
        return outcome_id

    # =========================================================================
    # Delete operations (for maintenance)
    # =========================================================================

    def delete_resource_spec(self, resource_type: str, resource_path: str) -> bool:
        """Delete a ResourceSpec."""
        cursor = self._conn.cursor()
        cursor.execute(
            "DELETE FROM resource_specs WHERE resource_type = ? AND resource_path = ?",
            (resource_type, resource_path),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def delete_policy_bundle(self, policy_version: str) -> bool:
        """Delete a PolicyBundle."""
        cursor = self._conn.cursor()
        cursor.execute(
            "DELETE FROM policy_bundles WHERE policy_version = ?",
            (policy_version,),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def delete_tool_spec(self, name: str) -> bool:
        """Delete a ToolSpec."""
        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM tool_specs WHERE name = ?", (name,))
        self._conn.commit()
        return cursor.rowcount > 0

    def prune_old_outcomes(self, older_than: datetime) -> int:
        """Delete outcomes older than a threshold."""
        cursor = self._conn.cursor()
        cursor.execute(
            "DELETE FROM outcomes WHERE occurred_at < ?",
            (_iso_z(older_than),),
        )
        self._conn.commit()
        return cursor.rowcount
