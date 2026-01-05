# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Migration runner for schema evolution."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import List

from motus.logging import get_logger

from .errors import MigrationError
from .migrations_schema import (
    Migration,
    MigrationRecord,
    _apply_audit_columns,
    parse_migration_file,
)

logger = get_logger(__name__)

# Allow known checksum mismatches for historical migrations.
_CHECKSUM_ALLOWLIST = {
    5: {"8e25ba0db729df46"},
    11: {"916955d0d4a93548"},
    16: {"fb79675f0195b2a0"},
}
def _ensure_schema_version_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            migration_name TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT (datetime('now')),
            checksum TEXT NOT NULL,
            execution_time_ms INTEGER
        )
    """
    )
def _get_applied_versions(conn: sqlite3.Connection) -> dict[int, MigrationRecord]:
    _ensure_schema_version_table(conn)

    cursor = conn.execute(
        """
        SELECT version, migration_name, checksum, applied_at, execution_time_ms
        FROM schema_version
        ORDER BY version
    """
    )

    applied: dict[int, MigrationRecord] = {}
    for row in cursor:
        applied[row[0]] = MigrationRecord(
            version=row[0],
            name=row[1],
            checksum=row[2],
            applied_at=row[3],
            execution_time_ms=row[4],
        )
    return applied
def discover_migrations(migrations_dir: Path) -> List[Migration]:
    if not migrations_dir.exists():
        return []

    migrations: List[Migration] = []
    for file_path in sorted(migrations_dir.glob("*.sql")):
        if file_path.name.startswith("."):
            continue

        try:
            migration = parse_migration_file(file_path)
            migrations.append(migration)
        except MigrationError:
            raise
        except Exception as e:
            raise MigrationError(
                f"[MIGRATE-001] Failed to parse {file_path.name}: {e}"
            ) from e

    migrations.sort(key=lambda m: m.version)
    return migrations
def _prepare_legacy_leases(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='leases'"
    ).fetchone()
    if not row:
        return

    cols = {r[1] for r in conn.execute("PRAGMA table_info(leases)").fetchall()}
    required = {"resource_type", "resource_id", "worker_id", "ttl_seconds", "acquired_at"}
    if required.issubset(cols):
        return

    legacy_name = "leases_legacy"
    suffix = 0
    while conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (legacy_name,),
    ).fetchone():
        suffix += 1
        legacy_name = f"leases_legacy_{suffix}"

    conn.execute(f"ALTER TABLE leases RENAME TO {legacy_name}")
def _execute_migration_up(conn: sqlite3.Connection, migration: Migration) -> None:
    try:
        if migration.version == 19:
            _prepare_legacy_leases(conn)
        if migration.up_sql.strip():
            conn.executescript(migration.up_sql)

        if migration.name == "add_audit_columns":
            _apply_audit_columns(conn)
    except sqlite3.Error as e:
        raise MigrationError(
            f"[MIGRATE-003] Migration {migration.version} failed: {e}"
        ) from e
def _record_migration(
    conn: sqlite3.Connection, migration: Migration, duration_ms: int
) -> None:
    conn.execute(
        """
        INSERT INTO schema_version
            (version, migration_name, checksum, execution_time_ms)
        VALUES (?, ?, ?, ?)
    """,
        (migration.version, migration.name, migration.checksum, duration_ms),
    )
def apply_migration(conn: sqlite3.Connection, migration: Migration) -> int:
    start = time.monotonic()
    _execute_migration_up(conn, migration)
    duration_ms = int((time.monotonic() - start) * 1000)

    conn.execute("BEGIN IMMEDIATE")
    try:
        _record_migration(conn, migration, duration_ms)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    return duration_ms
def run_migrations(
    conn: sqlite3.Connection,
    migrations_dir: Path,
    dry_run: bool = False,
) -> int:
    """Run pending migrations.

    Args:
        conn: Database connection.
        migrations_dir: Path to migrations directory.
        dry_run: If True, validate and report what would be applied without
                 actually executing SQL. Useful for CI/CD validation.

    Returns:
        Number of migrations applied (or that would be applied if dry_run).
    """
    _ensure_schema_version_table(conn)
    applied = _get_applied_versions(conn)
    pending = discover_migrations(migrations_dir)

    count = 0
    for migration in pending:
        if migration.version in applied:
            if applied[migration.version].checksum != migration.checksum:
                allowed = _CHECKSUM_ALLOWLIST.get(migration.version, set())
                if applied[migration.version].checksum in allowed:
                    logger.warning(
                        f"[MIGRATE-002] Migration {migration.version} checksum mismatch "
                        "allowed; updating schema_version record"
                    )
                    if not dry_run:
                        conn.execute(
                            """
                            UPDATE schema_version
                            SET checksum = ?, migration_name = ?
                            WHERE version = ?
                            """,
                            (migration.checksum, migration.name, migration.version),
                        )
                        conn.commit()
                    continue
                raise MigrationError(
                    f"[MIGRATE-002] Migration {migration.version} "
                    "changed after application (checksum mismatch)"
                )
            continue

        if dry_run:
            logger.info(
                f"[DRY-RUN] Would apply migration {migration.version}: "
                f"{migration.name} (checksum: {migration.checksum[:8]})"
            )
        else:
            logger.info(f"Applying migration {migration.version}: {migration.name}")
            duration_ms = apply_migration(conn, migration)
            logger.info(f"Migration {migration.version} applied in {duration_ms}ms")

        count += 1

    if count == 0:
        logger.info("No pending migrations")
    elif dry_run:
        logger.info(f"[DRY-RUN] {count} migration(s) would be applied")

    return count
class MigrationRunner:
    """Migration runner for database schema evolution."""

    def __init__(self, conn: sqlite3.Connection, migrations_dir: Path):
        self.conn = conn
        self.migrations_dir = migrations_dir

    def discover_migrations(self) -> List[Migration]:
        return discover_migrations(self.migrations_dir)

    def apply_migrations(self, dry_run: bool = False) -> int:
        """Apply pending migrations.

        Args:
            dry_run: If True, only report what would be applied.

        Returns:
            Number of migrations applied (or that would be applied).
        """
        return run_migrations(self.conn, self.migrations_dir, dry_run=dry_run)

    def get_current_version(self) -> int:
        _ensure_schema_version_table(self.conn)
        cursor = self.conn.execute("SELECT MAX(version) FROM schema_version")
        result = cursor.fetchone()
        return result[0] if result and result[0] is not None else 0

    def rollback_migration(self, version: int) -> None:
        applied = _get_applied_versions(self.conn)
        if version not in applied:
            raise MigrationError(
                f"[MIGRATE-001] Migration {version} not applied"
            )

        migrations = self.discover_migrations()
        migration = next((m for m in migrations if m.version == version), None)
        if not migration:
            raise MigrationError(
                f"[MIGRATE-001] Migration file for version {version} not found"
            )

        if not migration.down_sql:
            raise MigrationError(
                f"[MIGRATE-004] Migration {version} has no DOWN section"
            )

        logger.info(f"Rolling back migration {version}: {migration.name}")

        try:
            self.conn.executescript(migration.down_sql)

            self.conn.execute("BEGIN IMMEDIATE")
            try:
                self.conn.execute(
                    "DELETE FROM schema_version WHERE version = ?", (version,)
                )
                self.conn.execute("COMMIT")
            except Exception:
                self.conn.execute("ROLLBACK")
                raise

            logger.info(f"Migration {version} rolled back")
        except sqlite3.Error as e:
            raise MigrationError(
                f"[MIGRATE-004] Rollback of migration {version} failed: {e}"
            ) from e
