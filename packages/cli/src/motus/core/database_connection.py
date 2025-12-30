"""Database connection management for Motus Command."""

import os
import sqlite3
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from motus.logging import get_logger

from .database_queries import DatabaseQueryMixin
from .errors import DatabaseError, DiskFullError, SchemaError
from .layered_config import get_config

logger = get_logger(__name__)

EXPECTED_SCHEMA_VERSION = 18


def configure_connection(conn: sqlite3.Connection, set_row_factory: bool = True) -> None:
    """Apply standard PRAGMA settings for all Motus SQLite connections.

    Use this for ALL SQLite connections to ensure consistent behavior:
    - WAL mode for concurrent reads during writes
    - NORMAL sync for balance of safety and speed
    - Foreign keys ON for referential integrity
    - 5 second busy timeout to handle contention
    - 64MB cache for better read performance

    Args:
        conn: SQLite connection to configure.
        set_row_factory: If True, set row_factory to sqlite3.Row.
    """
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA cache_size = -64000")
    if set_row_factory:
        conn.row_factory = sqlite3.Row
    from .sqlite_udfs import register_udfs

    register_udfs(conn)


# Backwards compatibility alias
_configure_connection = configure_connection


def _secure_database_file(db_path: Path) -> None:
    """Apply secure permissions to database files."""
    db_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        os.chmod(db_path.parent, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    except OSError:
        pass

    if db_path.exists():
        os.chmod(db_path, stat.S_IRUSR | stat.S_IWUSR)

    for suffix in ["-wal", "-shm"]:
        aux_path = Path(str(db_path) + suffix)
        if aux_path.exists():
            os.chmod(aux_path, stat.S_IRUSR | stat.S_IWUSR)


def verify_schema_version(conn: sqlite3.Connection) -> None:
    """Verify schema version matches expected."""
    try:
        result = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
        db_version = result[0] if result and result[0] is not None else 0
    except sqlite3.OperationalError:
        db_version = 0

    if db_version < EXPECTED_SCHEMA_VERSION:
        raise SchemaError(
            f"[DB-SCHEMA-001] Database schema v{db_version} is older than "
            f"expected v{EXPECTED_SCHEMA_VERSION}. Re-run `mc` to apply migrations."
        )
    if db_version > EXPECTED_SCHEMA_VERSION:
        raise SchemaError(
            f"[DB-SCHEMA-002] Database schema v{db_version} is newer than "
            f"expected v{EXPECTED_SCHEMA_VERSION}. Update your tool version."
        )


def get_database_path() -> Path:
    """Get database path from configuration."""
    config = get_config()
    db_path_str = config.get_value("database.path", "~/.motus/coordination.db")
    return Path(db_path_str).expanduser()


def get_default_db_path() -> Path:
    """Get default database path without loading config."""
    return Path("~/.motus/coordination.db").expanduser()


class DatabaseManager(DatabaseQueryMixin):
    """Database connection manager with a single pooled connection."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or get_database_path()
        self._connection: sqlite3.Connection | None = None

    def ensure_database(self) -> None:
        """Ensure database exists and schema version is valid."""
        is_fresh = not self.db_path.exists()
        _secure_database_file(self.db_path)
        conn = self.get_connection()

        if is_fresh:
            logger.info(f"Creating fresh database at {self.db_path}")

        verify_schema_version(conn)

    def get_connection(self) -> sqlite3.Connection:
        """Get database connection (creates if needed)."""
        if self._connection is None:
            _secure_database_file(self.db_path)
            try:
                self._connection = sqlite3.connect(
                    str(self.db_path), isolation_level=None, check_same_thread=False
                )
                _configure_connection(self._connection)
                _secure_database_file(self.db_path)
            except sqlite3.OperationalError as e:
                msg = str(e).lower()
                if "database or disk is full" in msg:
                    raise DiskFullError("[DB-DISK-001] Disk full, free space and retry.") from e
                raise DatabaseError.from_sqlite_error(e, "database connection") from e
            except Exception as e:
                raise DatabaseError(
                    f"[DB-ERR-999] Failed to connect to database: {e}"
                ) from e

        return self._connection

    def release_connection(self, conn: sqlite3.Connection) -> None:
        """Release connection (no-op in single-connection mode)."""
        pass

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for database connections."""
        conn = self.get_connection()
        try:
            yield conn
        finally:
            self.release_connection(conn)

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for BEGIN IMMEDIATE transactions."""
        conn = self.get_connection()
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            self.release_connection(conn)

    def close(self) -> None:
        """Close database connection."""
        if self._connection is not None:
            try:
                self._connection.close()
            except Exception as e:
                logger.error(f"Error closing database: {e}")
            finally:
                self._connection = None


_db_manager: DatabaseManager | None = None


def get_db_manager() -> DatabaseManager:
    """Get global database manager (lazy init)."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


def reset_db_manager() -> None:
    """Reset global database manager (for test isolation)."""
    global _db_manager
    if _db_manager is not None:
        _db_manager.checkpoint_and_close()
    _db_manager = None
