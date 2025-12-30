"""
Deterministic constants for all test fixtures.

CRITICAL: These values MUST be used consistently across all tests to ensure
deterministic, reproducible test runs. Never use datetime.now(), uuid.uuid4(),
or random values in tests without explicit mocking.

Usage:
    from tests.fixtures.constants import FIXED_TIMESTAMP, FIXED_UUID, FIXED_SEED

Learning (from Codex QC review):
    Phase 0B-γ requires:
    1. Frozen fixtures with deterministic data (this file)
    2. Mocked UUID/timestamps in conftest.py
    3. CI with snapshots ENABLED (no --ignore)
"""

from datetime import datetime, timezone

# Fixed timestamp for all tests - UTC to avoid timezone issues
# Using Jan 15, 2025 12:00:00 UTC as the canonical test time
FIXED_TIMESTAMP = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

# Fixed timestamp without timezone for legacy code compatibility
FIXED_TIMESTAMP_NAIVE = datetime(2025, 1, 15, 12, 0, 0)

# Fixed UUID for deterministic session/event IDs
# This is a valid v4 UUID that will never conflict with real sessions
FIXED_UUID = "550e8400-e29b-41d4-a716-446655440000"

# Additional fixed UUIDs for tests that need multiple IDs
FIXED_UUIDS = [
    "550e8400-e29b-41d4-a716-446655440000",
    "550e8400-e29b-41d4-a716-446655440001",
    "550e8400-e29b-41d4-a716-446655440002",
    "550e8400-e29b-41d4-a716-446655440003",
    "550e8400-e29b-41d4-a716-446655440004",
]

# Fixed random seed for any tests that need reproducible randomness
FIXED_SEED = 42

# Fixed session IDs for golden fixtures
FIXED_SESSION_IDS = {
    "claude": "claude-test-session-001",
    "codex": "codex-test-session-001",
    "gemini": "gemini-test-session-001",
}

# Fixed project paths for tests
FIXED_PROJECT_PATHS = {
    "claude": "/Users/test/projects/web-app",
    "codex": "/Users/test/projects/api-server",
    "gemini": "/Users/test/projects/ml-pipeline",
}
