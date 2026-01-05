# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Bootstrap logic for first-run database setup.

Handles:
- First-run detection
- Directory creation
- Database initialization
- Migration application
- Instance configuration
"""

from pathlib import Path

from motus.logging import get_logger

from .database import DatabaseManager, get_database_path, verify_schema_version
from .errors import DatabaseError, MigrationError
from .migrations import MigrationRunner

logger = get_logger(__name__)


def is_first_run() -> bool:
    """Check if this is the first run (no database exists).

    Returns:
        True if database doesn't exist
    """
    db_path = get_database_path()
    return not db_path.exists()


def bootstrap_database() -> None:
    """Bootstrap database on first run.

    Creates:
    - Database directory structure
    - Fresh database with secure permissions
    - Applies all migrations
    - Seeds initial data

    Raises:
        DatabaseError: If bootstrap fails
        MigrationError: If migrations fail
    """
    bootstrap_database_at_path(get_database_path())


def ensure_database() -> None:
    """Ensure database exists and is current.

    This is the main entry point called by CLI commands.
    - On first run: bootstraps database
    - On subsequent runs: checks schema version, applies pending migrations

    Raises:
        DatabaseError: If database operations fail
        MigrationError: If migrations fail
    """
    bootstrap_database()


def ensure_database_at_path(db_path: Path) -> None:
    """Ensure an arbitrary SQLite database exists and is current."""
    bootstrap_database_at_path(db_path)


def bootstrap_database_at_path(db_path: Path) -> None:
    """Bootstrap database at an explicit path (first-run + migrations).

    Args:
        db_path: Destination SQLite path.
    """
    is_fresh = not db_path.exists()

    if is_fresh:
        logger.info(f"First run detected. Creating database at {db_path}")

    db = DatabaseManager(db_path)
    conn = db.get_connection()

    migrations_dir = _get_migrations_dir()
    if not migrations_dir.exists():
        raise MigrationError(
            f"[MIGRATE-001] Migrations directory not found: {migrations_dir}"
        )

    runner = MigrationRunner(conn, migrations_dir)
    count = runner.apply_migrations()

    verify_schema_version(conn)
    _prune_old_metrics(conn, days=30)

    if is_fresh:
        logger.info(f"Database created successfully. Applied {count} migrations.")
    elif count > 0:
        logger.info(f"Applied {count} pending migrations.")
    else:
        logger.debug("Database schema up to date.")


def _prune_old_metrics(conn, *, days: int) -> None:
    """Prune metrics older than the retention window."""
    try:
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
        conn.execute(
            "DELETE FROM metrics WHERE timestamp < datetime('now', ?)",
            (f"-{days} days",),
        )
    except Exception as exc:
        logger.debug(f"Metrics retention skipped: {exc}")


def _get_migrations_dir() -> Path:
    """Get migrations directory path.

    Returns:
        Path to migrations directory
    """
    import motus

    package_dir = Path(motus.__file__).resolve().parent
    try:
        cwd = Path.cwd()
    except FileNotFoundError:
        cwd = None
    candidates = [
        # Development checkout: <repo>/migrations (when importing from <repo>/src)
        package_dir.parent.parent / "migrations",
        # Installed wheel: site-packages/migrations (packaged as top-level data)
        package_dir.parent / "migrations",
        # Alternative packaging: motus/migrations (package data)
        package_dir / "migrations",
    ]
    if cwd is not None:
        # Last resort (allows running from a repo without editable install)
        candidates.append(cwd / "migrations")

    for candidate in candidates:
        if candidate.exists():
            return candidate

    # Return the most likely dev location for error messaging.
    return candidates[0]


def get_instance_id() -> str:
    """Get instance ID from database.

    Returns:
        Instance ID string

    Raises:
        DatabaseError: If database not initialized
    """
    from .database import get_db_manager

    db = get_db_manager()
    with db.connection() as conn:
        result = conn.execute(
            "SELECT value FROM instance_config WHERE key = 'instance_id'"
        ).fetchone()
        if not result:
            raise DatabaseError(
                "[DB-ERR-999] Instance ID not found in database. "
                "Database may be corrupted."
            )
        return result[0]


def get_instance_name() -> str:
    """Get instance name from database.

    Returns:
        Instance name string

    Raises:
        DatabaseError: If database not initialized
    """
    from .database import get_db_manager

    db = get_db_manager()
    with db.connection() as conn:
        result = conn.execute(
            "SELECT value FROM instance_config WHERE key = 'instance_name'"
        ).fetchone()
        if not result:
            return "default"
        return result[0]


def set_instance_name(name: str) -> None:
    """Set instance name in database.

    Args:
        name: New instance name

    Raises:
        DatabaseError: If update fails
    """
    from .database import get_db_manager

    db = get_db_manager()
    with db.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                """
                UPDATE instance_config
                SET value = ?, updated_at = datetime('now')
                WHERE key = 'instance_name'
            """,
                (name,),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
