"""Tests for Phase 0 hardening modules."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from motus.core.database import DatabaseManager
from motus.core.migrations import MigrationRunner
from motus.hardening.circuit_breaker import CircuitBreaker, CircuitOpenError
from motus.hardening.health import HealthChecker, HealthResult, HealthStatus
from motus.hardening.idempotency import IdempotencyManager, IdempotencyState
from motus.hardening.quotas import QuotaExceededError, QuotaManager


def _init_db(tmp_path: Path) -> DatabaseManager:
    db_path = tmp_path / "coordination.db"
    db = DatabaseManager(db_path)
    conn = db.get_connection()
    runner = MigrationRunner(conn, migrations_dir=Path(__file__).resolve().parents[1] / "migrations")
    runner.apply_migrations()
    return db


class TestCircuitBreaker:
    def test_opens_after_threshold_and_recovers(self, tmp_path: Path) -> None:
        db = _init_db(tmp_path)

        start = datetime(2025, 12, 19, 9, 0, 0, tzinfo=timezone.utc)
        now = {"t": start}

        def _now() -> datetime:
            return now["t"]

        cb = CircuitBreaker("database", db=db, now=_now)

        def _fail() -> None:
            raise RuntimeError("boom")

        # Force a low threshold for test determinism.
        with db.transaction() as conn:
            conn.execute(
                "UPDATE circuit_breakers SET failure_threshold = 2, recovery_timeout_seconds = 5 WHERE name = ?",
                ("database",),
            )

        with pytest.raises(RuntimeError):
            cb.call(_fail)
        with pytest.raises(RuntimeError):
            cb.call(_fail)

        with pytest.raises(CircuitOpenError):
            cb.call(lambda: 123)

        # After timeout, circuit transitions to half-open and a success closes it.
        now["t"] = start + timedelta(seconds=6)
        assert cb.call(lambda: "ok") == "ok"
        assert cb.get_state().is_closed


class TestQuotaManager:
    def test_soft_warn_and_hard_fail(self, tmp_path: Path) -> None:
        db = _init_db(tmp_path)
        qm = QuotaManager(db=db, now=lambda: datetime(2025, 12, 19, 9, 0, 0, tzinfo=timezone.utc))

        with db.transaction() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO resource_quotas
                    (resource_type, soft_limit, hard_limit, current_usage, reset_interval_hours)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("test_resource", 2, 3, 0, None),
            )

        r1 = qm.consume("test_resource", 1)
        assert r1.new_usage == 1
        assert r1.warned is False

        r2 = qm.consume("test_resource", 2)
        assert r2.new_usage == 3
        assert r2.warned is True

        with pytest.raises(QuotaExceededError):
            qm.consume("test_resource", 1)


class TestIdempotency:
    def test_get_or_create_and_complete(self, tmp_path: Path) -> None:
        db = _init_db(tmp_path)
        now = datetime(2025, 12, 19, 9, 0, 0, tzinfo=timezone.utc)
        mgr = IdempotencyManager(db=db, now=lambda: now)

        rec1 = mgr.get_or_create(operation="op", request_hash="abc", ttl_seconds=60)
        assert rec1.status == IdempotencyState.PENDING

        mgr.complete(rec1.key, {"ok": True})

        rec2 = mgr.get(rec1.key)
        assert rec2 is not None
        assert rec2.status == IdempotencyState.COMPLETE
        assert rec2.response == {"ok": True}


class TestHealthChecker:
    def test_persists_results(self, tmp_path: Path) -> None:
        db = _init_db(tmp_path)

        checker = HealthChecker(db=db)
        checker.register(lambda: HealthResult(name="a", status=HealthStatus.PASS, message="ok"))
        checker.register(lambda: HealthResult(name="b", status=HealthStatus.WARN, message="warn"))

        results = checker.run_all()
        checker.persist(results)

        with db.connection() as conn:
            rows = conn.execute(
                "SELECT check_name, status FROM health_check_results ORDER BY check_name"
            ).fetchall()
        assert [(r["check_name"], r["status"]) for r in rows] == [("a", "pass"), ("b", "warn")]

