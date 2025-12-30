"""Compatibility shim for migration exports."""

from .errors import MigrationError
from .migrations_runner import (
    MigrationRunner,
    apply_migration,
    discover_migrations,
    run_migrations,
)
from .migrations_schema import (
    AUDIT_COLUMNS,
    AUDIT_TABLES,
    Migration,
    MigrationRecord,
)

__all__ = [
    "AUDIT_COLUMNS",
    "AUDIT_TABLES",
    "Migration",
    "MigrationError",
    "MigrationRecord",
    "MigrationRunner",
    "apply_migration",
    "discover_migrations",
    "run_migrations",
]
