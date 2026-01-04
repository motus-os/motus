# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Runtime context for dependency injection and deterministic testing.

Provides injectable time, randomness, and configuration for testability.
"""

import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


class Clock(Protocol):
    """Clock protocol for time dependency injection."""

    def now(self) -> datetime:
        """Return current UTC datetime."""
        ...


class RandomSource(Protocol):
    """Random source protocol for randomness dependency injection."""

    def uuid(self) -> str:
        """Generate UUID string."""
        ...

    def choice(self, seq: list[Any]) -> Any:
        """Choose random element from sequence."""
        ...


class SystemClock:
    """System clock using real time (production)."""

    def now(self) -> datetime:
        """Return current UTC datetime."""
        return datetime.utcnow()


class SystemRandom:
    """System random using Python's random module (production)."""

    def uuid(self) -> str:
        """Generate UUID4 string."""
        return str(uuid.uuid4())

    def choice(self, seq: list[Any]) -> Any:
        """Choose random element from sequence."""
        return random.choice(seq)


@dataclass
class RuntimeContext:
    """Injectable runtime context for deterministic testing.

    This allows tests to inject fake clock, random, etc. for deterministic
    behavior while production uses real implementations.

    Example:
        # Production
        ctx = RuntimeContext()
        timestamp = ctx.now()  # Real time

        # Testing
        class FakeClock:
            def now(self):
                return datetime(2025, 1, 1, 12, 0, 0)

        ctx = RuntimeContext(clock=FakeClock())
        timestamp = ctx.now()  # Fixed time
    """

    clock: Clock = field(default_factory=SystemClock)
    random: RandomSource = field(default_factory=SystemRandom)
    instance_id: str = ""
    protocol_version: int = 1

    # Lazy-loaded from database
    _config: dict = field(default_factory=dict)

    def now(self) -> datetime:
        """Get current UTC datetime (injected clock)."""
        return self.clock.now()

    def new_id(self) -> str:
        """Generate new UUID (injected random)."""
        return self.random.uuid()

    def choice(self, seq: list[Any]) -> Any:
        """Choose random element (injected random)."""
        return self.random.choice(seq)


# Global context (can be replaced for testing)
_context: RuntimeContext | None = None


def get_context() -> RuntimeContext:
    """Get global runtime context (lazy init)."""
    global _context
    if _context is None:
        _context = RuntimeContext()
    return _context


def set_context(ctx: RuntimeContext) -> None:
    """Set global runtime context (for testing)."""
    global _context
    _context = ctx


def reset_context() -> None:
    """Reset global context to None (for test isolation)."""
    global _context
    _context = None
