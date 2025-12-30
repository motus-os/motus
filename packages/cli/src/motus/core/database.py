"""Compatibility shim for database exports."""

from __future__ import annotations

from .database_connection import (
    EXPECTED_SCHEMA_VERSION,
    DatabaseManager,
    _configure_connection,
    configure_connection,
    get_database_path,
    get_db_manager,
    get_default_db_path,
    reset_db_manager,
    verify_schema_version,
)

Database = DatabaseManager


def get_connection():
    """Return a database connection from the global manager."""
    return get_db_manager().get_connection()


__all__ = [
    "Database",
    "DatabaseManager",
    "EXPECTED_SCHEMA_VERSION",
    "_configure_connection",
    "configure_connection",
    "get_connection",
    "get_database_path",
    "get_default_db_path",
    "get_db_manager",
    "reset_db_manager",
    "verify_schema_version",
]
