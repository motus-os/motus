# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""CLI command: `motus doctor` (health diagnostics)."""

from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path
from typing import Any, Dict

from rich.console import Console

from motus.cli.exit_codes import EXIT_ERROR, EXIT_SUCCESS
from motus.core import get_db_manager, verify_schema_version
from motus.core.database_connection import get_database_path
from motus.core.errors import DatabaseError, SchemaError
from motus.config import config as motus_config
from motus.config_loader import get_config_path
from motus.hardening.health import HealthChecker, HealthResult, HealthStatus
from motus.hardening.package_conflicts import detect_package_conflicts


MIN_DISK_FREE_BYTES = 100 * 1024 * 1024
MAX_LOG_BYTES = 100 * 1024 * 1024
MAX_WAL_BYTES = 50 * 1024 * 1024


def _package_conflict_check() -> HealthResult:
    result = detect_package_conflicts()
    if not result.conflict:
        return HealthResult(
            name="package_conflict",
            status=HealthStatus.PASS,
            message="No conflicting Motus packages detected",
            details={"origin": result.origin},
        )

    if result.conflicts:
        installed = ", ".join(f"{name}=={ver}" for name, ver in result.conflicts.items())
        message = f"Conflicting packages installed: {installed}. Remove with: pip uninstall motus motus-command -y"
    else:
        message = "Motus import resolves to motus-command path. Remove old packages: pip uninstall motus motus-command -y"

    return HealthResult(
        name="package_conflict",
        status=HealthStatus.FAIL,
        message=message,
        details={"conflicts": result.conflicts, "origin": result.origin},
    )


def _db_exists_check(db_path: Path) -> HealthResult:
    if db_path.exists():
        return HealthResult(
            name="db_exists",
            status=HealthStatus.PASS,
            message=f"Database exists: {db_path}",
        )
    return HealthResult(
        name="db_exists",
        status=HealthStatus.FAIL,
        message=f"Database not found: {db_path}",
    )


def _db_readable_check(db_path: Path) -> HealthResult:
    if not db_path.exists():
        return HealthResult(
            name="db_readable",
            status=HealthStatus.WARN,
            message="Database missing; readability check skipped",
        )
    try:
        db = get_db_manager()
        with db.readonly_connection():
            pass
    except DatabaseError as exc:
        return HealthResult(
            name="db_readable",
            status=HealthStatus.FAIL,
            message=str(exc),
        )
    return HealthResult(
        name="db_readable",
        status=HealthStatus.PASS,
        message="Database readable",
    )


def _db_integrity_check(db_path: Path) -> HealthResult:
    if not db_path.exists():
        return HealthResult(
            name="db_integrity",
            status=HealthStatus.WARN,
            message="Database missing; integrity check skipped",
        )
    try:
        db = get_db_manager()
        with db.readonly_connection() as conn:
            row = conn.execute("PRAGMA integrity_check").fetchone()
            result = row[0] if row else None
    except (DatabaseError, sqlite3.DatabaseError) as exc:
        return HealthResult(
            name="db_integrity",
            status=HealthStatus.FAIL,
            message=str(exc),
        )
    if result == "ok":
        return HealthResult(
            name="db_integrity",
            status=HealthStatus.PASS,
            message="Integrity check ok",
        )
    return HealthResult(
        name="db_integrity",
        status=HealthStatus.FAIL,
        message=f"Integrity check failed: {result}",
    )


def _db_schema_check(db_path: Path) -> HealthResult:
    if not db_path.exists():
        return HealthResult(
            name="db_schema",
            status=HealthStatus.WARN,
            message="Database missing; schema check skipped",
        )
    try:
        db = get_db_manager()
        with db.readonly_connection() as conn:
            verify_schema_version(conn)
    except (SchemaError, DatabaseError) as exc:
        return HealthResult(
            name="db_schema",
            status=HealthStatus.FAIL,
            message=str(exc),
        )
    return HealthResult(
        name="db_schema",
        status=HealthStatus.PASS,
        message="Schema up to date",
    )


def _config_check() -> HealthResult:
    config_path = get_config_path()
    if not config_path.exists():
        return HealthResult(
            name="config",
            status=HealthStatus.PASS,
            message="Config not found; defaults in use",
        )
    try:
        raw = config_path.read_text(encoding="utf-8")
        json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        return HealthResult(
            name="config",
            status=HealthStatus.FAIL,
            message=f"Config parse error: {exc}",
        )
    return HealthResult(
        name="config",
        status=HealthStatus.PASS,
        message="Config valid",
    )


def _disk_space_check(db_path: Path) -> HealthResult:
    try:
        usage = shutil.disk_usage(db_path.parent)
    except OSError as exc:
        return HealthResult(
            name="disk_space",
            status=HealthStatus.WARN,
            message=f"Disk space check failed: {exc}",
        )
    if usage.free < MIN_DISK_FREE_BYTES:
        return HealthResult(
            name="disk_space",
            status=HealthStatus.WARN,
            message=f"Low disk space: {usage.free / (1024 * 1024):.1f} MB free",
        )
    return HealthResult(
        name="disk_space",
        status=HealthStatus.PASS,
        message=f"Disk space ok: {usage.free / (1024 * 1024):.1f} MB free",
    )


def _log_size_check() -> HealthResult:
    log_file = motus_config.paths.logs_dir / "motus.log"
    if not log_file.exists():
        return HealthResult(
            name="log_size",
            status=HealthStatus.PASS,
            message="Log file not present",
        )
    size = log_file.stat().st_size
    if size > MAX_LOG_BYTES:
        return HealthResult(
            name="log_size",
            status=HealthStatus.WARN,
            message=f"Log size {size / (1024 * 1024):.1f} MB (rotate recommended)",
        )
    return HealthResult(
        name="log_size",
        status=HealthStatus.PASS,
        message=f"Log size {size / (1024 * 1024):.1f} MB",
    )


def _wal_check(*, fix: bool = False) -> HealthResult:
    db = get_db_manager()
    size = db.get_wal_size()
    if size <= MAX_WAL_BYTES:
        return HealthResult(
            name="wal_size",
            status=HealthStatus.PASS,
            message=f"WAL size {size / (1024 * 1024):.1f} MB",
            details={"wal_size_bytes": size},
        )
    if fix:
        db.checkpoint_wal()
        size = db.get_wal_size()
        status = HealthStatus.PASS if size <= MAX_WAL_BYTES else HealthStatus.WARN
        return HealthResult(
            name="wal_size",
            status=status,
            message="WAL checkpointed" if status == HealthStatus.PASS else "WAL still large",
            details={"wal_size_bytes": size},
        )
    return HealthResult(
        name="wal_size",
        status=HealthStatus.WARN,
        message=f"WAL size {size / (1024 * 1024):.1f} MB (consider: motus db checkpoint)",
        details={"wal_size_bytes": size},
    )


def doctor_command(*, json_output: bool = False, fix: bool = False) -> int:
    console = Console()
    checker = HealthChecker()
    db_path = get_database_path()
    checker.register(_package_conflict_check)
    checker.register(lambda: _db_exists_check(db_path))
    checker.register(lambda: _db_readable_check(db_path))
    checker.register(lambda: _db_integrity_check(db_path))
    checker.register(lambda: _db_schema_check(db_path))
    checker.register(_config_check)
    checker.register(lambda: _disk_space_check(db_path))
    checker.register(_log_size_check)
    checker.register(lambda: _wal_check(fix=fix))
    results = checker.run_all()
    checker.persist(results)

    worst = HealthStatus.PASS
    for r in results:
        if r.status == HealthStatus.FAIL:
            worst = HealthStatus.FAIL
            break
        if r.status == HealthStatus.WARN:
            worst = HealthStatus.WARN

    passed = sum(1 for r in results if r.status == HealthStatus.PASS)
    warned = sum(1 for r in results if r.status == HealthStatus.WARN)
    failed = sum(1 for r in results if r.status == HealthStatus.FAIL)

    if json_output:
        payload: Dict[str, Any] = {
            "status": worst.value,
            "summary": {"passed": passed, "warned": warned, "failed": failed},
            "checks": [
                {
                    "name": r.name,
                    "status": r.status.value,
                    "message": r.message,
                    "details": r.details,
                    "duration_ms": r.duration_ms,
                }
                for r in results
            ],
        }
        console.print_json(json.dumps(payload, sort_keys=True))
    else:
        for r in results:
            msg = f"{r.name}: {r.status.value}"
            if r.message:
                msg += f" - {r.message}"
            console.print(msg, markup=False)
        console.print(f"Summary: {passed} passed, {warned} warning, {failed} failed", markup=False)
        console.print(f"overall: {worst.value}", markup=False)

    return EXIT_SUCCESS if worst != HealthStatus.FAIL else EXIT_ERROR
