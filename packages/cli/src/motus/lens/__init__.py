# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Lens compiler package.

The Lens is assembled knowledge for a specific task. It provides:
- Resource specs: What files/resources are involved
- Policy snippets: What rules apply
- Tool guidance: How to use available tools
- Recent outcomes: What happened before (for learning)

Usage:
    # Register cache reader (one-time setup)
    from motus.context_cache import ContextCache
    cache = ContextCache(db_path="~/.motus/context_cache.db")
    set_cache_reader(cache)

    # Assemble a Lens
    lens = assemble_lens(
        policy_version="v1.0.0",
        resources=[Resource(type="file", path="src/main.py")],
        intent="implement feature X",
        cache_state_hash=cache.state_hash(),
        timestamp=datetime.now(timezone.utc),
    )

Protocols:
    LensAssembler: Interface for custom Lens assembly implementations.
    ContextCacheReader: Interface for cache backends.
"""

from .compiler import (
    ContextCacheReader,
    LensItem,
    LensPacket,
    assemble_lens,
    set_cache_reader,
)
from .interface import LensAssembler

__all__ = [
    # Core function
    "assemble_lens",
    "set_cache_reader",
    # Types
    "LensItem",
    "LensPacket",
    # Protocols
    "ContextCacheReader",
    "LensAssembler",
]
