# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Lens assembly interface definitions.

This module defines the protocol interfaces for Lens assembly, enabling:
1. Custom Lens assemblers for different contexts
2. Module conformance testing (RI-C-203)
3. Dependency injection for testing

The LensAssembler protocol is the primary interface that modules can implement
to provide custom context assembly logic.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from motus.coordination.schemas import ClaimedResource as Resource

from .compiler import LensPacket


class LensAssembler(Protocol):
    """Protocol for Lens assembly implementations.

    This interface defines the contract for assembling context (Lens) for tasks.
    Implement this protocol to provide custom Lens assembly logic.

    The default implementation is the `assemble_lens` function in compiler.py,
    which uses the ContextCache to gather resource specs, policies, etc.

    Example:
        class CustomLensAssembler:
            def assemble(
                self,
                policy_version: str,
                resources: list[Resource],
                intent: str,
                cache_state_hash: str,
                timestamp: datetime,
            ) -> LensPacket:
                # Custom assembly logic
                return {...}

        # Use in coordinator
        assembler = CustomLensAssembler()
        lens = assembler.assemble(...)
    """

    def assemble(
        self,
        policy_version: str,
        resources: list[Resource],
        intent: str,
        cache_state_hash: str,
        timestamp: datetime,
    ) -> LensPacket:
        """Assemble a Lens for a task.

        Args:
            policy_version: Current policy version (e.g., "v1.0.0").
            resources: List of resources the task will operate on.
            intent: Description of what the task will do.
            cache_state_hash: Hash of the cache state for provenance.
            timestamp: When assembly occurred (must be timezone-aware).

        Returns:
            LensPacket containing assembled context with provenance tags.

        Raises:
            ValueError: If required parameters are invalid.
            RuntimeError: If assembly fails due to missing dependencies.
        """
        ...


class LensRefresher(Protocol):
    """Protocol for refreshing Lens context.

    This interface enables mid-execution context refresh without
    re-claiming resources. Used by get_context().
    """

    def refresh(
        self,
        lease_id: str,
        intent: str | None = None,
        lens_level: int = 0,
    ) -> LensPacket:
        """Refresh Lens for an existing lease.

        Args:
            lease_id: Active lease ID from a prior claim.
            intent: Optional updated intent.
            lens_level: Lens tier (0=minimal, 1=standard, 2=full).

        Returns:
            Fresh LensPacket with updated context.

        Raises:
            ValueError: If lease_id is invalid or lease is not active.
        """
        ...


class ContextProvider(Protocol):
    """Protocol for providing context data to Lens assembly.

    This is a more granular interface for components that provide
    specific types of context (resource specs, policies, etc.).
    """

    def get_context_for_resources(
        self,
        resources: list[Resource],
        timestamp: datetime,
    ) -> dict[str, Any]:
        """Get context data for a set of resources.

        Args:
            resources: Resources to get context for.
            timestamp: Current timestamp for staleness calculation.

        Returns:
            Dictionary with context data, including:
            - resource_specs: List of resource specifications
            - warnings: Any warnings about missing/stale data
        """
        ...


# Type alias for Lens assembly results with metadata
class LensAssemblyResult:
    """Result of Lens assembly with additional metadata.

    This class wraps a LensPacket with assembly metadata for
    debugging and auditing purposes.
    """

    def __init__(
        self,
        lens: LensPacket,
        *,
        assembly_time_ms: int = 0,
        cache_hits: int = 0,
        cache_misses: int = 0,
    ) -> None:
        """Initialize assembly result.

        Args:
            lens: The assembled LensPacket.
            assembly_time_ms: Time taken to assemble (milliseconds).
            cache_hits: Number of cache hits during assembly.
            cache_misses: Number of cache misses during assembly.
        """
        self.lens = lens
        self.assembly_time_ms = assembly_time_ms
        self.cache_hits = cache_hits
        self.cache_misses = cache_misses

    @property
    def lens_hash(self) -> str:
        """Get the Lens hash for provenance."""
        return self.lens.get("lens_hash", "")

    @property
    def warnings(self) -> list[dict[str, Any]]:
        """Get any warnings from assembly."""
        return self.lens.get("warnings", [])

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "lens": self.lens,
            "metadata": {
                "assembly_time_ms": self.assembly_time_ms,
                "cache_hits": self.cache_hits,
                "cache_misses": self.cache_misses,
            },
        }
