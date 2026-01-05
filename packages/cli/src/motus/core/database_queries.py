# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Database query helpers and metrics tracking."""

import json
from pathlib import Path

from motus.logging import get_logger

logger = get_logger(__name__)


class DatabaseQueryMixin:
    """Query helpers for DatabaseManager."""

    def record_metric(
        self,
        operation: str,
        elapsed_ms: float,
        success: bool = True,
        metadata: dict | None = None,
    ) -> None:
        """Record a performance metric."""
        with self.connection() as conn:
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
            columns = {
                row[1]
                for row in conn.execute("PRAGMA table_info(metrics)").fetchall()
            }
            success_column = "is_success" if "is_success" in columns else "success"
            conn.execute(
                f"""
                INSERT INTO metrics (
                    timestamp, operation, elapsed_ms, {success_column}, metadata
                )
                VALUES (datetime('now'), ?, ?, ?, ?)
                """,  # nosec B608 - success_column is hardcoded
                (
                    operation,
                    float(elapsed_ms),
                    1 if success else 0,
                    json.dumps(metadata) if metadata else None,
                ),
            )

    def checkpoint_wal(self) -> None:
        """Checkpoint WAL to flush writes to main database."""
        if self._connection is not None:
            try:
                self._connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            except Exception as e:
                logger.error(f"WAL checkpoint failed: {e}")

    def checkpoint_and_close(self) -> None:
        """Checkpoint WAL and close connection (for shutdown)."""
        if self._connection is not None:
            try:
                self._connection.execute("PRAGMA optimize")
            except Exception as e:
                logger.debug(f"PRAGMA optimize skipped: {e}")
        self.checkpoint_wal()
        self.close()

    def get_wal_size(self) -> int:
        """Get WAL file size in bytes."""
        wal_path = Path(str(self.db_path) + "-wal")
        if wal_path.exists():
            return wal_path.stat().st_size
        return 0

    def check_wal_size(self) -> tuple[str, int]:
        """Check WAL file size and checkpoint if needed."""
        size = self.get_wal_size()

        if size > 100_000_000:  # 100MB
            logger.warning(
                f"WAL file too large ({size / 1_000_000:.1f}MB), "
                "forcing checkpoint"
            )
            with self.connection() as conn:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            return ("checkpoint_forced", size)

        if size > 50_000_000:  # 50MB
            logger.warning(f"WAL file growing: {size / 1_000_000:.1f}MB")
            return ("warning", size)

        return ("ok", size)
