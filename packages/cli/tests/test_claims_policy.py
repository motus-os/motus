from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from motus.core.claims import can_deploy
from motus.core.migrations_schema import parse_migration_file
import motus.core.database_connection as database_connection
from tests import conftest as test_conftest


@pytest.fixture
def claims_db(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "claims_policy.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(
        """
        CREATE TABLE roadmap_items (
            id TEXT PRIMARY KEY,
            phase_key TEXT NOT NULL,
            status_key TEXT NOT NULL DEFAULT 'pending',
            deleted_at TEXT DEFAULT NULL
        );
        """
    )

    migration_path = Path(__file__).parent.parent / "migrations" / "008_claims_policy.sql"
    migration = parse_migration_file(migration_path)
    conn.executescript(migration.up_sql)
    yield conn
    conn.close()


class ClaimsDBManager:
    def __init__(self, conn: sqlite3.Connection):
        self._connection = conn

    def connection(self):
        @contextmanager
        def ctx():
            yield self._connection

        return ctx()

    def transaction(self):
        @contextmanager
        def ctx():
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                yield self._connection
                self._connection.execute("COMMIT")
            except Exception:
                self._connection.execute("ROLLBACK")
                raise

        return ctx()

    def get_connection(self):
        return self._connection


@pytest.fixture
def claims_api_db(monkeypatch, claims_db: sqlite3.Connection) -> sqlite3.Connection:
    test_manager = ClaimsDBManager(claims_db)
    monkeypatch.setattr(database_connection, "_db_manager", test_manager)
    monkeypatch.setattr(database_connection, "get_db_manager", lambda: test_manager)
    return claims_db


class TestClaimConstraints:
    def test_quantitative_claim_requires_test(self, claims_db: sqlite3.Connection) -> None:
        with pytest.raises(sqlite3.IntegrityError):
            claims_db.execute(
                """
                INSERT INTO claims (id, claim_text, page, claim_type)
                VALUES ('C-001', 'Valid claim text', 'index', 'quantitative')
                """
            )

    def test_claim_text_minimum_length(self, claims_db: sqlite3.Connection) -> None:
        with pytest.raises(sqlite3.IntegrityError):
            claims_db.execute(
                """
                INSERT INTO claims (id, claim_text, page, claim_type)
                VALUES ('C-002', 'abcd', 'index', 'qualitative')
                """
            )

    def test_default_status_pending(self, claims_db: sqlite3.Connection) -> None:
        claims_db.execute(
            """
            INSERT INTO claims (id, claim_text, page, claim_type)
            VALUES ('C-003', 'Claim text ok', 'index', 'qualitative')
            """
        )
        row = claims_db.execute(
            "SELECT test_status FROM claims WHERE id = 'C-003'"
        ).fetchone()
        assert row["test_status"] == "pending"


class TestClaimViews:
    def test_v_can_deploy_blocked_with_fail(self, claims_db: sqlite3.Connection) -> None:
        claims_db.execute(
            """
            INSERT INTO claims (id, claim_text, page, claim_type, test_function, test_status)
            VALUES ('C-010', 'Claim text ok', 'index', 'quantitative', 'test_func', 'fail')
            """
        )
        row = claims_db.execute("SELECT * FROM v_can_deploy").fetchone()
        assert row["status"] == "BLOCKED"
        assert row["failed_count"] == 1
        assert row["failed_claims"] == "C-010"

    def test_v_can_deploy_pending_with_quantitative(self, claims_db: sqlite3.Connection) -> None:
        claims_db.execute(
            """
            INSERT INTO claims (id, claim_text, page, claim_type, test_function)
            VALUES ('C-011', 'Claim text ok', 'index', 'quantitative', 'test_func')
            """
        )
        row = claims_db.execute("SELECT * FROM v_can_deploy").fetchone()
        assert row["status"] == "PENDING"

    def test_v_can_deploy_ready_with_no_claims(self, claims_db: sqlite3.Connection) -> None:
        row = claims_db.execute("SELECT * FROM v_can_deploy").fetchone()
        assert row["status"] == "READY"

    def test_v_claims_needing_tests_includes_pending_quant(self, claims_db: sqlite3.Connection) -> None:
        claims_db.execute(
            """
            INSERT INTO claims (id, claim_text, page, claim_type, test_function)
            VALUES ('C-012', 'Claim text ok', 'index', 'quantitative', 'test_func')
            """
        )
        row = claims_db.execute(
            "SELECT id FROM v_claims_needing_tests WHERE id = 'C-012'"
        ).fetchone()
        assert row is not None

    def test_v_claims_needing_tests_excludes_qualitative(self, claims_db: sqlite3.Connection) -> None:
        claims_db.execute(
            """
            INSERT INTO claims (id, claim_text, page, claim_type)
            VALUES ('C-013', 'Claim text ok', 'index', 'qualitative')
            """
        )
        row = claims_db.execute(
            "SELECT id FROM v_claims_needing_tests WHERE id = 'C-013'"
        ).fetchone()
        assert row is None


class TestClaimsAPI:
    def test_can_deploy_returns_blocked(self, claims_api_db: sqlite3.Connection) -> None:
        claims_api_db.execute(
            """
            INSERT INTO claims (id, claim_text, page, claim_type, test_function, test_status)
            VALUES ('C-020', 'Claim text ok', 'index', 'quantitative', 'test_func', 'fail')
            """
        )
        result = can_deploy()
        assert result.can_deploy is False
        assert result.status == "BLOCKED"
        assert result.blockers == ["C-020"]
        assert "Fix 1 failing claim tests" in result.action
        assert result.command == "pytest -k claim"

    def test_can_deploy_returns_pending(self, claims_api_db: sqlite3.Connection) -> None:
        claims_api_db.execute(
            """
            INSERT INTO claims (id, claim_text, page, claim_type, test_function)
            VALUES ('C-021', 'Claim text ok', 'index', 'quantitative', 'test_func')
            """
        )
        result = can_deploy()
        assert result.can_deploy is False
        assert result.status == "PENDING"
        assert result.blockers == []
        assert result.action
        assert result.command == "pytest -k claim"

    def test_can_deploy_returns_ready(self, claims_api_db: sqlite3.Connection) -> None:
        result = can_deploy()
        assert result.can_deploy is True
        assert result.status == "READY"
        assert result.blockers == []
        assert result.action
        assert result.command == "make deploy"


class TestPytestIntegration:
    def test_claim_decorator_registers_claim(self, monkeypatch, claims_api_db: sqlite3.Connection) -> None:
        monkeypatch.setattr(test_conftest, "CLAIMS_TRACKING_ENABLED", True)

        marker = SimpleNamespace(kwargs={"id": "C-030", "page": "index", "text": "Claim text ok"})
        item = SimpleNamespace(
            name="test_claims_registers",
            fspath=SimpleNamespace(basename="test_claims_policy.py"),
            get_closest_marker=lambda name: marker if name == "claim" else None,
        )

        test_conftest.pytest_collection_modifyitems([item])

        row = claims_api_db.execute(
            "SELECT id, claim_text, page, test_file, test_function, claim_type FROM claims WHERE id = 'C-030'"
        ).fetchone()
        assert row is not None
        assert row["claim_text"] == "Claim text ok"
        assert row["page"] == "index"
        assert row["test_file"] == "test_claims_policy.py"
        assert row["test_function"] == "test_claims_registers"
        assert row["claim_type"] == "quantitative"

    def test_test_pass_updates_status(self, monkeypatch, claims_api_db: sqlite3.Connection) -> None:
        monkeypatch.setattr(test_conftest, "CLAIMS_TRACKING_ENABLED", True)

        marker = SimpleNamespace(kwargs={"id": "C-031", "page": "index", "text": "Claim text ok"})
        item = SimpleNamespace(
            name="test_claims_pass",
            fspath=SimpleNamespace(basename="test_claims_policy.py"),
            get_closest_marker=lambda name: marker if name == "claim" else None,
        )
        test_conftest.pytest_collection_modifyitems([item])

        call = SimpleNamespace(when="call")
        report = SimpleNamespace(passed=True)

        class DummyOutcome:
            def __init__(self, report_obj):
                self._report = report_obj

            def get_result(self):
                return self._report

        generator = test_conftest.pytest_runtest_makereport(item, call)
        next(generator)
        try:
            generator.send(DummyOutcome(report))
        except StopIteration:
            pass

        row = claims_api_db.execute(
            "SELECT test_status FROM claims WHERE id = 'C-031'"
        ).fetchone()
        assert row["test_status"] == "pass"

    def test_test_fail_updates_status(self, monkeypatch, claims_api_db: sqlite3.Connection) -> None:
        monkeypatch.setattr(test_conftest, "CLAIMS_TRACKING_ENABLED", True)

        marker = SimpleNamespace(kwargs={"id": "C-032", "page": "index", "text": "Claim text ok"})
        item = SimpleNamespace(
            name="test_claims_fail",
            fspath=SimpleNamespace(basename="test_claims_policy.py"),
            get_closest_marker=lambda name: marker if name == "claim" else None,
        )
        test_conftest.pytest_collection_modifyitems([item])

        call = SimpleNamespace(when="call")
        report = SimpleNamespace(passed=False)

        class DummyOutcome:
            def __init__(self, report_obj):
                self._report = report_obj

            def get_result(self):
                return self._report

        generator = test_conftest.pytest_runtest_makereport(item, call)
        next(generator)
        try:
            generator.send(DummyOutcome(report))
        except StopIteration:
            pass

        row = claims_api_db.execute(
            "SELECT test_status FROM claims WHERE id = 'C-032'"
        ).fetchone()
        assert row["test_status"] == "fail"
