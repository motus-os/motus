"""
Test configuration for Motus.

Determinism Requirements (from Codex QC review):
- Phase 0B-γ MUST deliver:
  1. Frozen fixtures with deterministic data
  2. Mocked UUID/timestamps (not just env vars)
  3. CI with snapshots ENABLED

- Runs snapshot tests first to avoid state pollution from other suites.
  Ordering stateful UI tests first can keep the environment clean when enabled.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

import pytest

# Import deterministic constants
from tests.fixtures.constants import (
    FIXED_TIMESTAMP,
    FIXED_TIMESTAMP_NAIVE,
    FIXED_UUID,
    FIXED_UUIDS,
)

CLAIMS_TRACKING_ENABLED = os.environ.get("MOTUS_TRACK_CLAIMS", "0") == "1"
OPTIONAL_DEPENDENCIES = (
    ("fastapi", "fastapi", lambda name: name.startswith("test_web")),
    ("mcp", "mcp", lambda name: name in {"test_mcp.py", "test_messages.py"}),
    ("google-genai", "google.genai", lambda name: "gemini" in name),
)
SNAPSHOT_TEST_FILES = {"test_cli_snapshots.py"}


def _module_missing(module: str) -> bool:
    return importlib.util.find_spec(module) is None

# Ensure tests import the local package, not a globally installed motus.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

# If an installed motus package is already imported, purge it so tests
# exercise the local source tree under src/.
for name, module in list(sys.modules.items()):
    if not name.startswith("motus"):
        continue
    module_file = getattr(module, "__file__", "") or ""
    if module_file and str(SRC_PATH) not in module_file:
        sys.modules.pop(name, None)

# ============================================================================
# Determinism Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def deterministic_environment():
    """Ensure all tests run in a deterministic environment.

    This fixture runs automatically for ALL tests and sets environment
    variables that affect determinism (timezone, hash seed).
    """
    # Save original values
    original_tz = os.environ.get("TZ")
    original_seed = os.environ.get("PYTHONHASHSEED")

    # Set deterministic values
    os.environ["TZ"] = "UTC"
    os.environ["PYTHONHASHSEED"] = "0"

    yield

    # Restore original values
    if original_tz is not None:
        os.environ["TZ"] = original_tz
    elif "TZ" in os.environ:
        del os.environ["TZ"]

    if original_seed is not None:
        os.environ["PYTHONHASHSEED"] = original_seed
    elif "PYTHONHASHSEED" in os.environ:
        del os.environ["PYTHONHASHSEED"]


@pytest.fixture
def mock_uuid(monkeypatch):
    """Mock uuid.uuid4 to return deterministic values.

    Usage:
        def test_something(mock_uuid):
            # uuid.uuid4() will now return FIXED_UUID
            session_id = str(uuid.uuid4())
            assert session_id == FIXED_UUID

    For tests needing multiple UUIDs, use mock_uuid_sequence instead.
    """
    monkeypatch.setattr(uuid, "uuid4", lambda: uuid.UUID(FIXED_UUID))
    return FIXED_UUID


@pytest.fixture
def mock_uuid_sequence(monkeypatch):
    """Mock uuid.uuid4 to return a sequence of deterministic UUIDs.

    Usage:
        def test_multiple_uuids(mock_uuid_sequence):
            id1 = str(uuid.uuid4())  # Returns FIXED_UUIDS[0]
            id2 = str(uuid.uuid4())  # Returns FIXED_UUIDS[1]
    """
    uuid_iter = iter(FIXED_UUIDS)

    def next_uuid():
        try:
            return uuid.UUID(next(uuid_iter))
        except StopIteration:
            # Cycle back to start if we run out
            return uuid.UUID(FIXED_UUIDS[0])

    monkeypatch.setattr(uuid, "uuid4", next_uuid)
    return FIXED_UUIDS


@pytest.fixture
def mock_datetime_now(monkeypatch):
    """Mock datetime.now() to return FIXED_TIMESTAMP.

    Usage:
        def test_timestamp(mock_datetime_now):
            now = datetime.now()
            assert now == FIXED_TIMESTAMP_NAIVE
    """
    # Keep reference for potential restoration; prefix with _ to mark intentionally unused
    _original_datetime = datetime

    class MockDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is not None:
                return FIXED_TIMESTAMP
            return FIXED_TIMESTAMP_NAIVE

        @classmethod
        def utcnow(cls):
            return FIXED_TIMESTAMP_NAIVE

    # Patch datetime in the datetime module
    monkeypatch.setattr("datetime.datetime", MockDatetime)
    return FIXED_TIMESTAMP


@pytest.fixture
def frozen_time():
    """Provide the fixed timestamp for tests that need it explicitly.

    Usage:
        def test_with_time(frozen_time):
            event = create_event(timestamp=frozen_time)
    """
    return FIXED_TIMESTAMP


@pytest.fixture
def frozen_time_naive():
    """Provide the fixed timestamp without timezone for legacy compatibility."""
    return FIXED_TIMESTAMP_NAIVE


# ============================================================================
# Golden Fixture Helpers
# ============================================================================


@pytest.fixture
def golden_fixtures_path():
    """Return the path to golden fixture files."""
    return Path(__file__).parent / "fixtures" / "golden"


@pytest.fixture
def load_golden_fixture(golden_fixtures_path):
    """Factory fixture to load golden JSON fixtures.

    Usage:
        def test_with_fixture(load_golden_fixture):
            claude_data = load_golden_fixture("claude_session.json")
    """
    import json

    def _load(filename: str) -> dict:
        fixture_path = golden_fixtures_path / filename
        with open(fixture_path) as f:
            return json.load(f)

    return _load


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "smoke: Quick import tests")
    config.addinivalue_line("markers", "critical: Core functionality")
    config.addinivalue_line("markers", "integration: Full integration")
    config.addinivalue_line("markers", "slow: Long-running tests")
    config.addinivalue_line(
        "markers", "claim(id, page, text): mark test as verifying a website claim"
    )


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items):
    """Skip optional dependency tests and auto-discover claims."""
    missing_optional = {
        label: _module_missing(module)
        for label, module, _predicate in OPTIONAL_DEPENDENCIES
    }

    for item in items:
        name = item.fspath.basename
        for label, _module, predicate in OPTIONAL_DEPENDENCIES:
            if missing_optional[label] and predicate(name):
                item.add_marker(
                    pytest.mark.skip(reason=f"Optional dependency missing: {label}")
                )
                break

    if _module_missing("syrupy"):
        for item in items:
            if item.fspath.basename in SNAPSHOT_TEST_FILES:
                raise pytest.UsageError(
                    "Snapshot tests require syrupy. Install with: pip install syrupy"
                )

    if not CLAIMS_TRACKING_ENABLED:
        return

    from motus.core.database_connection import get_db_manager

    db = get_db_manager()

    for item in items:
        if item.get_closest_marker("skip") or item.get_closest_marker("skipif"):
            continue

        marker = item.get_closest_marker("claim")
        if marker:
            claim_id = marker.kwargs.get("id")
            page = marker.kwargs.get("page", "index")
            text = marker.kwargs.get("text", "")

            # Validate required fields (match DB constraints)
            if not claim_id:
                raise ValueError(
                    f"@pytest.mark.claim requires id= kwarg: {item.nodeid}"
                )
            if len(text) < 5:
                raise ValueError(
                    f"@pytest.mark.claim requires text= with at least 5 chars: {item.nodeid}"
                )

            with db.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO claims (id, claim_text, page, claim_type, test_file, test_function)
                    VALUES (?, ?, ?, 'quantitative', ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        claim_text = excluded.claim_text,
                        page = excluded.page,
                        test_file = excluded.test_file,
                        test_function = excluded.test_function,
                        updated_at = datetime('now')
                    """,
                    (claim_id, text, page, str(item.fspath.basename), item.name),
                )


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Update claim status after test execution."""
    outcome = yield
    report = outcome.get_result()

    if not CLAIMS_TRACKING_ENABLED:
        return

    if call.when == "call":
        marker = item.get_closest_marker("claim")
        if marker:
            claim_id = marker.kwargs.get("id")
            status = "pass" if report.passed else "fail"

            from motus.core.database_connection import get_db_manager

            db = get_db_manager()
            with db.connection() as conn:
                conn.execute(
                    """
                    UPDATE claims
                    SET test_status = ?, last_verified_at = datetime('now')
                    WHERE id = ?
                    """,
                    (status, claim_id),
                )
