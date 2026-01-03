# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Schema definitions and audit helpers for migrations."""

from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from motus.logging import get_logger

from .errors import MigrationError

logger = get_logger(__name__)
AUDIT_TABLES = [
    "sessions", "metrics", "session_cache_state", "session_event_cache",
    "session_file_cache", "circuit_breakers", "detected_patterns", "learned_patterns",
    "ground_rules", "skills", "preferences", "instance_config",
    "extension_points", "health_check_results", "idempotency_keys", "resource_quotas",
    "terminology",
]
AUDIT_COLUMNS = [
    ("created_at", "TEXT DEFAULT NULL"), ("updated_at", "TEXT DEFAULT NULL"),
    ("created_by", "TEXT DEFAULT NULL"), ("updated_by", "TEXT DEFAULT NULL"),
    ("deleted_at", "TEXT DEFAULT NULL"), ("deleted_by", "TEXT DEFAULT NULL"),
    ("deletion_reason", "TEXT DEFAULT NULL"),
]
@dataclass
class MigrationRecord:
    version: int
    name: str
    checksum: str
    applied_at: str | None = None
    execution_time_ms: int | None = None
@dataclass
class Migration:
    version: int
    name: str
    file_path: Path
    up_sql: str
    down_sql: str
    checksum: str
def parse_migration_file(file_path: Path) -> Migration:
    content = file_path.read_text()

    match = re.match(r"(\d+)_(.+)\.sql", file_path.name)
    if not match:
        raise MigrationError(
            f"[MIGRATE-001] Invalid migration filename: {file_path.name}. "
            "Expected format: NNN_description.sql"
        )

    version = int(match.group(1))
    name = match.group(2)

    up_match = re.search(
        r"-- UP\s*\n(.*?)(?:-- DOWN|\Z)", content, re.DOTALL | re.IGNORECASE
    )
    down_match = re.search(r"-- DOWN\s*\n(.*)", content, re.DOTALL | re.IGNORECASE)

    if not up_match:
        raise MigrationError(
            f"[MIGRATE-001] Missing -- UP section in {file_path.name}"
        )

    up_sql = up_match.group(1).strip()
    down_sql = down_match.group(1).strip() if down_match else ""
    checksum = hashlib.sha256(content.encode()).hexdigest()[:16]

    return Migration(
        version=version, name=name, file_path=file_path,
        up_sql=up_sql, down_sql=down_sql, checksum=checksum,
    )

def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _create_metrics_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            operation TEXT NOT NULL,
            elapsed_ms REAL NOT NULL,
            success INTEGER NOT NULL DEFAULT 1 CHECK (success IN (0, 1)),
            metadata TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            created_by TEXT DEFAULT NULL,
            updated_by TEXT DEFAULT NULL,
            deleted_at TEXT DEFAULT NULL,
            deleted_by TEXT DEFAULT NULL,
            deletion_reason TEXT DEFAULT NULL
        )
        """
    )


def _create_updated_at_triggers(conn: sqlite3.Connection, tables: list[str]) -> None:
    for table in tables:
        conn.execute(
            f"""
            CREATE TRIGGER IF NOT EXISTS {table}_updated_at
            AFTER UPDATE ON {table}
            FOR EACH ROW
            WHEN NEW.updated_at == OLD.updated_at
            BEGIN
                UPDATE {table} SET updated_at = datetime('now')
                WHERE rowid = NEW.rowid;
            END
            """  # nosec B608 - table from AUDIT_TABLES constant
        )


def _create_audit_insert_triggers(conn: sqlite3.Connection, tables: list[str]) -> None:
    for table in tables:
        conn.execute(
            f"""
            CREATE TRIGGER IF NOT EXISTS {table}_audit_insert
            AFTER INSERT ON {table}
            FOR EACH ROW
            WHEN NEW.created_at IS NULL
                OR NEW.created_at = ''
                OR NEW.updated_at IS NULL
                OR NEW.updated_at = ''
            BEGIN
                UPDATE {table}
                SET created_at = CASE
                        WHEN NEW.created_at IS NULL OR NEW.created_at = ''
                        THEN datetime('now')
                        ELSE NEW.created_at
                    END,
                    updated_at = CASE
                        WHEN NEW.updated_at IS NULL OR NEW.updated_at = ''
                        THEN datetime('now')
                        ELSE NEW.updated_at
                    END
                WHERE rowid = NEW.rowid;
            END
            """  # nosec B608 - table from AUDIT_TABLES constant
        )


def _create_audit_indexes(conn: sqlite3.Connection, tables: list[str]) -> None:
    for table in tables:
        conn.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{table}_created_at ON {table}(created_at)"
        )
        conn.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{table}_updated_at ON {table}(updated_at)"
        )
        conn.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{table}_deleted_at ON {table}(deleted_at)"
        )


def _apply_audit_columns(conn: sqlite3.Connection) -> None:
    for table in AUDIT_TABLES:
        if not _table_exists(conn, table):
            if table == "metrics":
                _create_metrics_table(conn)
            else:
                logger.info(f"Skipping audit columns for non-existent table: {table}")
                continue

        existing = {
            row[1]
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        for col_name, col_def in AUDIT_COLUMNS:
            if col_name not in existing:
                conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}"
                )

        if _table_exists(conn, table):
            conn.execute(
                f"""
                UPDATE {table}
                SET created_at = COALESCE(NULLIF(created_at, ''), datetime('now')),
                    updated_at = COALESCE(NULLIF(updated_at, ''), datetime('now'))
                WHERE created_at IS NULL OR created_at = ''
                    OR updated_at IS NULL OR updated_at = ''
            """  # nosec B608 - table from AUDIT_TABLES constant
            )

    existing_tables = [t for t in AUDIT_TABLES if _table_exists(conn, t)]
    _create_audit_insert_triggers(conn, existing_tables)
    _create_updated_at_triggers(conn, existing_tables)
    _create_audit_indexes(conn, existing_tables)
