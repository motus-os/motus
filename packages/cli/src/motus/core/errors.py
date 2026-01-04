# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Error codes and exception hierarchy for Motus.

All errors follow DNA-DB-SQLITE RULE 12 (error sanitization):
- User-facing messages are sanitized (no paths, no SQL)
- Error codes for support reference
- Full context logged separately
"""

import sqlite3


class MotusError(Exception):
    """Base error for all Motus errors."""

    pass


class DatabaseError(MotusError):
    """Database operation failed.

    Error codes:
    - DB-DUP-001: Duplicate record (UNIQUE constraint)
    - DB-REF-001: Referenced record not found (FOREIGN KEY constraint)
    - DB-LOCK-001: Database busy/locked
    - DB-IO-001: Storage error (disk I/O)
    - DB-CORRUPT-001: Database corrupted
    - DB-DISK-001: Disk full or unavailable
    - DB-ERR-999: Generic database error
    """

    ERROR_MAP = {
        "UNIQUE constraint failed": ("DB-DUP-001", "Record already exists"),
        "FOREIGN KEY constraint failed": (
            "DB-REF-001",
            "Referenced record not found",
        ),
        "database is locked": ("DB-LOCK-001", "Database busy, please retry"),
        "disk I/O error": ("DB-IO-001", "Storage error, check disk space"),
        "database disk image is malformed": (
            "DB-CORRUPT-001",
            "Database corrupted, restore from backup",
        ),
        "database or disk is full": (
            "DB-DISK-001",
            "Disk full, free space and retry",
        ),
        "unable to open database file": (
            "DB-IO-001",
            "Cannot open database, check permissions",
        ),
    }

    @classmethod
    def from_sqlite_error(
        cls, e: sqlite3.Error, context: str
    ) -> "DatabaseError":
        """Convert SQLite error to sanitized DatabaseError.

        Args:
            e: The SQLite exception
            context: Operation context (e.g., "transition CR")

        Returns:
            DatabaseError with sanitized message and error code
        """
        error_str = str(e).lower()
        for pattern, (code, message) in cls.ERROR_MAP.items():
            if pattern.lower() in error_str:
                return cls(f"[{code}] {message}")
        return cls("[DB-ERR-999] Database operation failed")


class MigrationError(MotusError):
    """Migration operation failed.

    Error codes:
    - MIGRATE-001: Migration file not found
    - MIGRATE-002: Migration checksum mismatch
    - MIGRATE-003: Migration execution failed
    - MIGRATE-004: Rollback failed
    """

    pass


class SchemaError(MotusError):
    """Schema version mismatch or validation failed.

    Error codes:
    - DB-SCHEMA-001: Database schema is older than expected
    - DB-SCHEMA-002: Database schema is newer than expected
    - DB-SCHEMA-003: Schema integrity check failed
    """

    pass


class DiskFullError(DatabaseError):
    """Disk full or I/O error (specific subclass of DatabaseError)."""

    pass


class ConfigError(MotusError):
    """Configuration error.

    Error codes:
    - CONFIG-001: Invalid configuration value
    - CONFIG-002: Missing required configuration
    - CONFIG-003: Configuration file parse error
    """

    pass


def is_disk_error(e: sqlite3.OperationalError) -> bool:
    """Check if error is disk-related.

    Args:
        e: SQLite operational error

    Returns:
        True if error is related to disk/I/O
    """
    disk_error_patterns = [
        "disk I/O error",
        "database or disk is full",
        "unable to open database file",
        "disk image is malformed",
    ]
    msg = str(e).lower()
    return any(pattern.lower() in msg for pattern in disk_error_patterns)
