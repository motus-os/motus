# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Lease storage for the Coordination API."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from motus.coordination.api.types import (
    Lease,
    LeaseMode,
    LeaseStatus,
    Outcome,
)
from motus.coordination.schemas import ClaimedResource as Resource
from motus.core import configure_connection

_SCHEMA_VERSION = 1
LEASE_COLUMNS = (
    "lease_id, owner_agent_id, mode, resources, issued_at, expires_at, "
    "heartbeat_deadline, snapshot_id, policy_version, lens_digest, work_id, "
    "attempt_id, status, outcome"
)

_INIT_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS coordination_leases (
    lease_id TEXT PRIMARY KEY,
    owner_agent_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    resources TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    heartbeat_deadline TEXT NOT NULL,
    snapshot_id TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    lens_digest TEXT NOT NULL,
    work_id TEXT,
    attempt_id TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    outcome TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_coordination_leases_status ON coordination_leases(status);
CREATE INDEX IF NOT EXISTS idx_coordination_leases_owner ON coordination_leases(owner_agent_id);
CREATE INDEX IF NOT EXISTS idx_coordination_leases_expires ON coordination_leases(expires_at);

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    lease_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (lease_id) REFERENCES coordination_leases(lease_id)
);

CREATE INDEX IF NOT EXISTS idx_events_lease ON events(lease_id);
"""


def _iso_z(dt: datetime) -> str:
    """Format datetime as ISO 8601 with Z suffix."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_datetime(s: str) -> datetime:
    """Parse ISO 8601 datetime string."""
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _generate_lease_id() -> str:
    """Generate a unique lease ID."""
    now = _utcnow()
    return f"lease-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"


def _generate_event_id() -> str:
    """Generate a unique event ID."""
    return f"evt-{uuid.uuid4().hex[:12]}"


class LeaseStore:
    """SQLite-backed lease storage."""

    def __init__(self, db_path: str | Path) -> None:
        """Initialize lease store.

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
                    f"[LEASE-STORE-001] Incompatible LeaseStore schema version. "
                    f"Database has v{db_version}, code expects v{_SCHEMA_VERSION}. "
                    f"Delete {self._db_path} to reset (leases will be lost)."
                )
        self._ensure_lease_columns()
        self._conn.commit()

    def _ensure_lease_columns(self) -> None:
        """Ensure optional lease metadata columns exist."""
        cursor = self._conn.cursor()
        cursor.execute("PRAGMA table_info(coordination_leases)")
        columns = {row["name"] for row in cursor.fetchall()}

        if "work_id" not in columns:
            cursor.execute("ALTER TABLE coordination_leases ADD COLUMN work_id TEXT")
        if "attempt_id" not in columns:
            cursor.execute("ALTER TABLE coordination_leases ADD COLUMN attempt_id TEXT")

    def close(self) -> None:
        """Close database connection."""
        self._conn.close()

    # =========================================================================
    # Lease operations
    # =========================================================================

    def create_lease(
        self,
        owner_agent_id: str,
        mode: LeaseMode,
        resources: list[Resource],
        ttl_s: int,
        snapshot_id: str,
        policy_version: str,
        lens_digest: str,
        work_id: str | None = None,
        attempt_id: str | None = None,
    ) -> Lease:
        """Create a new lease.

        Args:
            owner_agent_id: Agent acquiring the lease.
            mode: read or write.
            resources: Resources being claimed.
            ttl_s: Time-to-live in seconds.
            snapshot_id: Snapshot baseline ID.
            policy_version: Policy version used for this claim.
            lens_digest: Hash of the Lens assembled for this lease.
            work_id: Optional work item identifier for metadata.
            attempt_id: Optional attempt identifier for metadata.

        Returns:
            The created Lease.
        """
        now = _utcnow()
        lease_id = _generate_lease_id()
        expires_at = now + timedelta(seconds=ttl_s)
        heartbeat_deadline = now + timedelta(seconds=min(ttl_s, 300))  # Max 5 min

        resources_json = json.dumps(
            [{"type": r.type, "path": r.path} for r in resources],
            sort_keys=True,
        )

        cursor = self._conn.cursor()
        cursor.execute(
            """
            INSERT INTO coordination_leases
                (lease_id, owner_agent_id, mode, resources, issued_at, expires_at,
                 heartbeat_deadline, snapshot_id, policy_version, lens_digest,
                 work_id, attempt_id, status, outcome, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lease_id,
                owner_agent_id,
                mode,
                resources_json,
                _iso_z(now),
                _iso_z(expires_at),
                _iso_z(heartbeat_deadline),
                snapshot_id,
                policy_version,
                lens_digest,
                work_id,
                attempt_id,
                "active",
                None,
                _iso_z(now),
                _iso_z(now),
            ),
        )
        self._conn.commit()

        return Lease(
            lease_id=lease_id,
            owner_agent_id=owner_agent_id,
            mode=mode,
            resources=resources,
            issued_at=now,
            expires_at=expires_at,
            heartbeat_deadline=heartbeat_deadline,
            snapshot_id=snapshot_id,
            policy_version=policy_version,
            lens_digest=lens_digest,
            work_id=work_id,
            attempt_id=attempt_id,
            status="active",
            outcome=None,
        )

    def get_lease(self, lease_id: str) -> Lease | None:
        """Get a lease by ID."""
        cursor = self._conn.cursor()
        cursor.execute(
            f"SELECT {LEASE_COLUMNS} FROM coordination_leases WHERE lease_id = ?",
            (lease_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        lease = self._row_to_lease(row)

        if lease.status == "active":
            now = _utcnow()
            if lease.expires_at <= now or lease.heartbeat_deadline <= now:
                cursor.execute(
                    """
                    UPDATE coordination_leases
                    SET status = 'expired', updated_at = ?
                    WHERE lease_id = ?
                    """,
                    (_iso_z(now), lease_id),
                )
                self._conn.commit()
                refreshed = self._conn.execute(
                    f"SELECT {LEASE_COLUMNS} FROM coordination_leases WHERE lease_id = ?",
                    (lease_id,),
                ).fetchone()
                if refreshed is None:
                    return None
                return self._row_to_lease(refreshed)

        return lease

    def get_active_leases_for_resources(
        self, resources: list[Resource], mode: LeaseMode | None = None
    ) -> list[Lease]:
        """Get active leases that overlap with given resources.

        Args:
            resources: Resources to check.
            mode: Optional filter by mode (read/write).

        Returns:
            List of active leases holding any of the resources.
        """
        now = _utcnow()
        cursor = self._conn.cursor()

        query = f"""
            SELECT {LEASE_COLUMNS} FROM coordination_leases
            WHERE status = 'active'
            AND expires_at > ?
            AND heartbeat_deadline > ?
        """
        params: list[Any] = [_iso_z(now), _iso_z(now)]

        if mode is not None:
            query += " AND mode = ?"
            params.append(mode)

        cursor.execute(query, params)

        # Filter by resource overlap
        resource_keys = {(r.type, r.path) for r in resources}
        result: list[Lease] = []

        for row in cursor.fetchall():
            lease = self._row_to_lease(row)
            lease_keys = {(r.type, r.path) for r in lease.resources}
            if lease_keys & resource_keys:
                result.append(lease)

        return result

    def update_heartbeat(self, lease_id: str, ttl_s: int = 300) -> Lease | None:
        """Update heartbeat deadline for a lease.

        Args:
            lease_id: Lease to update.
            ttl_s: New TTL from now.

        Returns:
            Updated lease, or None if not found/not active.
        """
        now = _utcnow()
        new_deadline = now + timedelta(seconds=ttl_s)

        cursor = self._conn.cursor()
        cursor.execute(
            """
            UPDATE coordination_leases
            SET heartbeat_deadline = ?, updated_at = ?
            WHERE lease_id = ? AND status = 'active'
            """,
            (_iso_z(new_deadline), _iso_z(now), lease_id),
        )
        self._conn.commit()

        if cursor.rowcount == 0:
            return None

        return self.get_lease(lease_id)

    def release_lease(
        self, lease_id: str, outcome: Outcome, status: LeaseStatus = "released"
    ) -> Lease | None:
        """Release a lease with an outcome.

        Args:
            lease_id: Lease to release.
            outcome: Final outcome.
            status: Final status (released, aborted).

        Returns:
            Updated lease, or None if not found.
        """
        now = _utcnow()

        cursor = self._conn.cursor()
        cursor.execute(
            """
            UPDATE coordination_leases
            SET status = ?, outcome = ?, updated_at = ?
            WHERE lease_id = ?
            """,
            (status, outcome, _iso_z(now), lease_id),
        )
        self._conn.commit()

        if cursor.rowcount == 0:
            return None

        return self.get_lease(lease_id)

    def expire_stale_leases(self) -> list[str]:
        """Expire leases past their deadline.

        Returns:
            List of expired lease IDs.
        """
        now = _utcnow()
        now_iso = _iso_z(now)

        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT lease_id FROM coordination_leases
            WHERE status = 'active'
            AND (expires_at <= ? OR heartbeat_deadline <= ?)
            """,
            (now_iso, now_iso),
        )
        expired_ids = [row["lease_id"] for row in cursor.fetchall()]

        if expired_ids:
            placeholders = ",".join("?" * len(expired_ids))
            cursor.execute(
                f"""
                UPDATE coordination_leases
                SET status = 'expired', updated_at = ?
                WHERE lease_id IN ({placeholders})
                """,  # nosec B608 - placeholders are ?,?,? count
                [now_iso] + expired_ids,
            )
            self._conn.commit()

        return expired_ids

    def add_resources_to_lease(
        self, lease_id: str, resources: list[Resource]
    ) -> Lease | None:
        """Add resources to an existing lease.

        Args:
            lease_id: Lease to expand.
            resources: Additional resources.

        Returns:
            Updated lease, or None if not found/not active.
        """
        lease = self.get_lease(lease_id)
        if lease is None or lease.status != "active":
            return None

        # Merge resources (deduplicate)
        existing_keys = {(r.type, r.path) for r in lease.resources}
        new_resources = list(lease.resources)
        for r in resources:
            if (r.type, r.path) not in existing_keys:
                new_resources.append(r)

        now = _utcnow()
        resources_json = json.dumps(
            [{"type": r.type, "path": r.path} for r in new_resources],
            sort_keys=True,
        )

        cursor = self._conn.cursor()
        cursor.execute(
            """
            UPDATE coordination_leases
            SET resources = ?, updated_at = ?
            WHERE lease_id = ? AND status = 'active'
            """,
            (resources_json, _iso_z(now), lease_id),
        )
        self._conn.commit()

        return self.get_lease(lease_id)

    # =========================================================================
    # Event operations
    # =========================================================================

    def record_event(
        self,
        lease_id: str,
        event_type: str,
        payload: dict[str, Any],
        event_id: str | None = None,
    ) -> str:
        """Record an event for a lease.

        Args:
            lease_id: Lease this event belongs to.
            event_type: Type of event.
            payload: Event payload.
            event_id: Optional event ID (for idempotency). Generated if not provided.

        Returns:
            The event ID.
        """
        if event_id is None:
            event_id = _generate_event_id()

        now = _utcnow()
        payload_json = json.dumps(payload, sort_keys=True)

        cursor = self._conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO events (event_id, lease_id, event_type, payload, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (event_id, lease_id, event_type, payload_json, _iso_z(now)),
            )
            self._conn.commit()
        except sqlite3.IntegrityError:
            # Idempotent - event already exists
            pass

        return event_id

    def get_events(self, lease_id: str) -> list[dict[str, Any]]:
        """Get all events for a lease."""
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT event_id, event_type, payload, created_at
            FROM events
            WHERE lease_id = ?
            ORDER BY created_at
            """,
            (lease_id,),
        )

        return [
            {
                "event_id": row["event_id"],
                "event_type": row["event_type"],
                "payload": json.loads(row["payload"]),
                "created_at": row["created_at"],
            }
            for row in cursor.fetchall()
        ]

    def event_exists(self, event_id: str) -> bool:
        """Check if an event already exists (for idempotency)."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT 1 FROM events WHERE event_id = ?", (event_id,))
        return cursor.fetchone() is not None

    # =========================================================================
    # Helpers
    # =========================================================================

    def _row_to_lease(self, row: sqlite3.Row) -> Lease:
        """Convert a database row to a Lease object."""
        resources_data = json.loads(row["resources"])
        resources = [Resource(type=r["type"], path=r["path"]) for r in resources_data]
        work_id = row["work_id"] if "work_id" in row.keys() else None
        attempt_id = row["attempt_id"] if "attempt_id" in row.keys() else None

        return Lease(
            lease_id=row["lease_id"],
            owner_agent_id=row["owner_agent_id"],
            mode=row["mode"],
            resources=resources,
            issued_at=_parse_datetime(row["issued_at"]),
            expires_at=_parse_datetime(row["expires_at"]),
            heartbeat_deadline=_parse_datetime(row["heartbeat_deadline"]),
            snapshot_id=row["snapshot_id"],
            policy_version=row["policy_version"],
            lens_digest=row["lens_digest"],
            work_id=work_id,
            attempt_id=attempt_id,
            status=row["status"],
            outcome=row["outcome"],
        )
