"""Tests for Context Cache."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from motus.context_cache import ContextCache
from motus.coordination.schemas import ClaimedResource as Resource
from motus.lens.compiler import assemble_lens, set_cache_reader


@pytest.fixture
def cache() -> ContextCache:
    """Create an in-memory Context Cache for testing."""
    return ContextCache(db_path=":memory:")


@pytest.fixture
def populated_cache(cache: ContextCache) -> ContextCache:
    """Cache with sample data for testing.

    Note: Data is kept minimal to fit within Lens Tier-0 token budgets.
    Budget: resource_specs=110 tokens, ~440 chars.
    """
    # Add a minimal ResourceSpec (fits in budget)
    cache.put_resource_spec(
        resource_type="file",
        resource_path="a.py",
        spec={
            "id": "a.py",
            "type": "file",
        },
    )

    # Add a minimal PolicyBundle
    cache.put_policy_bundle(
        policy_version="v1",
        bundle={
            "id": "p1",
            "tools": ["edit"],
        },
    )

    # Add a minimal ToolSpec
    cache.put_tool_spec(
        name="edit",
        spec={"name": "edit"},
    )

    # Add a minimal Outcome
    cache.put_outcome(
        outcome_id="o1",
        resource_type="file",
        resource_path="a.py",
        outcome={"ok": True},
    )

    return cache


class TestContextCacheBasics:
    """Basic Context Cache operations."""

    def test_create_in_memory(self, cache: ContextCache) -> None:
        """In-memory cache initializes without error."""
        assert cache is not None

    def test_put_and_get_resource_spec(self, cache: ContextCache) -> None:
        """Can store and retrieve ResourceSpec."""
        cache.put_resource_spec(
            resource_type="file",
            resource_path="test.py",
            spec={"id": "test.py", "type": "file"},
        )

        resource = Resource(type="file", path="test.py")
        result = cache.get_resource_spec(resource)

        assert result is not None
        assert result["payload"]["id"] == "test.py"
        assert "source_hash" in result
        assert "observed_at" in result

    def test_get_missing_resource_spec(self, cache: ContextCache) -> None:
        """Returns None for missing ResourceSpec."""
        resource = Resource(type="file", path="nonexistent.py")
        result = cache.get_resource_spec(resource)
        assert result is None

    def test_put_and_get_policy_bundle(self, cache: ContextCache) -> None:
        """Can store and retrieve PolicyBundle."""
        cache.put_policy_bundle(
            policy_version="v1.0.0",
            bundle={"policies": [{"id": "test"}]},
        )

        result = cache.get_policy_bundle("v1.0.0")

        assert result is not None
        assert result["payload"]["policies"][0]["id"] == "test"

    def test_put_and_get_tool_specs(self, cache: ContextCache) -> None:
        """Can store and retrieve ToolSpecs."""
        cache.put_tool_spec(name="edit", spec={"name": "edit"})
        cache.put_tool_spec(name="write", spec={"name": "write"})

        result = cache.get_tool_specs(["edit", "write"])

        assert len(result) == 2
        names = {r["payload"]["name"] for r in result}
        assert names == {"edit", "write"}

    def test_get_tool_specs_partial(self, cache: ContextCache) -> None:
        """Returns only existing ToolSpecs."""
        cache.put_tool_spec(name="edit", spec={"name": "edit"})

        result = cache.get_tool_specs(["edit", "nonexistent"])

        assert len(result) == 1
        assert result[0]["payload"]["name"] == "edit"

    def test_put_and_get_outcomes(self, cache: ContextCache) -> None:
        """Can store and retrieve outcomes."""
        cache.put_outcome(
            outcome_id="o1",
            resource_type="file",
            resource_path="test.py",
            outcome={"result": "success"},
        )

        resource = Resource(type="file", path="test.py")
        result = cache.get_recent_outcomes([resource], limit=10)

        assert len(result) == 1
        assert result[0]["payload"]["result"] == "success"

    def test_state_hash_deterministic(self, cache: ContextCache) -> None:
        """State hash is deterministic."""
        cache.put_resource_spec("file", "a.py", {"id": "a"})
        cache.put_resource_spec("file", "b.py", {"id": "b"})

        hash1 = cache.state_hash()
        hash2 = cache.state_hash()

        assert hash1 == hash2
        assert len(hash1) == 16  # Truncated to 16 chars

    def test_state_hash_changes_on_update(self, cache: ContextCache) -> None:
        """State hash changes when data changes."""
        cache.put_resource_spec("file", "a.py", {"id": "a"})
        hash1 = cache.state_hash()

        cache.put_resource_spec("file", "b.py", {"id": "b"})
        hash2 = cache.state_hash()

        assert hash1 != hash2


class TestContextCacheWithLens:
    """Test Context Cache integration with Lens compiler."""

    def test_lens_compiler_reads_from_cache(self, populated_cache: ContextCache) -> None:
        """Lens compiler successfully reads from Context Cache."""
        set_cache_reader(populated_cache)

        resources = [Resource(type="file", path="a.py")]
        now = datetime.now(timezone.utc)

        lens = assemble_lens(
            policy_version="v1",
            resources=resources,
            intent="edit",
            cache_state_hash=populated_cache.state_hash(),
            timestamp=now,
        )

        # Verify Lens structure
        assert lens["tier"] == "tier0"
        assert lens["policy_version"] == "v1"
        assert lens["intent"] == "edit"
        assert lens["lens_hash"]  # Non-empty

        # Verify resource_specs populated (minimal data fits in budget)
        assert len(lens["resource_specs"]) == 1
        assert lens["resource_specs"][0]["source_type"] == "resource_spec"

        # Note: policy_snippets, tool_guidance, recent_outcomes may be empty
        # due to tight token budgets. The important thing is the Lens assembles
        # without error and the cache integration works.

    def test_lens_handles_missing_resource(self, cache: ContextCache) -> None:
        """Lens assembles successfully even when ResourceSpec is missing."""
        # Use a fresh cache with just policy (no resource specs)
        cache.put_policy_bundle("v1", {"id": "p1"})
        set_cache_reader(cache)

        resources = [Resource(type="file", path="nonexistent.py")]
        now = datetime.now(timezone.utc)

        # Should not raise - graceful handling of missing data
        lens = assemble_lens(
            policy_version="v1",
            resources=resources,
            intent="edit",
            cache_state_hash=cache.state_hash(),
            timestamp=now,
        )

        # Lens should still be valid
        assert lens["tier"] == "tier0"
        assert lens["lens_hash"]  # Non-empty hash

        # resource_specs should be empty (no matching specs in cache)
        assert len(lens["resource_specs"]) == 0

        # Note: warnings may be generated internally but could be trimmed
        # due to tight token budgets. The key behavior is graceful handling.

    def test_lens_deterministic_hash(self, populated_cache: ContextCache) -> None:
        """Lens hash is deterministic for same inputs."""
        set_cache_reader(populated_cache)

        resources = [Resource(type="file", path="a.py")]
        now = datetime(2025, 12, 23, 12, 0, 0, tzinfo=timezone.utc)
        cache_hash = populated_cache.state_hash()

        lens1 = assemble_lens(
            policy_version="v1",
            resources=resources,
            intent="edit",
            cache_state_hash=cache_hash,
            timestamp=now,
        )

        lens2 = assemble_lens(
            policy_version="v1",
            resources=resources,
            intent="edit",
            cache_state_hash=cache_hash,
            timestamp=now,
        )

        assert lens1["lens_hash"] == lens2["lens_hash"]


class TestContextCacheDelete:
    """Test delete operations."""

    def test_delete_resource_spec(self, cache: ContextCache) -> None:
        """Can delete ResourceSpec."""
        cache.put_resource_spec("file", "test.py", {"id": "test"})
        assert cache.get_resource_spec(Resource(type="file", path="test.py")) is not None

        result = cache.delete_resource_spec("file", "test.py")
        assert result is True
        assert cache.get_resource_spec(Resource(type="file", path="test.py")) is None

    def test_delete_nonexistent_returns_false(self, cache: ContextCache) -> None:
        """Delete of nonexistent item returns False."""
        result = cache.delete_resource_spec("file", "nonexistent.py")
        assert result is False

    def test_prune_old_outcomes(self, cache: ContextCache) -> None:
        """Can prune old outcomes."""
        old_time = datetime(2020, 1, 1, tzinfo=timezone.utc)
        new_time = datetime(2025, 12, 23, tzinfo=timezone.utc)

        cache.put_outcome("old", "file", "a.py", {"old": True}, occurred_at=old_time)
        cache.put_outcome("new", "file", "b.py", {"new": True}, occurred_at=new_time)

        cutoff = datetime(2024, 1, 1, tzinfo=timezone.utc)
        pruned = cache.prune_old_outcomes(older_than=cutoff)

        assert pruned == 1

        # Old one gone, new one remains
        resource_a = Resource(type="file", path="a.py")
        resource_b = Resource(type="file", path="b.py")

        assert len(cache.get_recent_outcomes([resource_a], limit=10)) == 0
        assert len(cache.get_recent_outcomes([resource_b], limit=10)) == 1
