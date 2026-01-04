# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Context Cache: The knowledge store that Lens reads from.

The Context Cache stores ResourceSpecs, PolicyBundles, ToolSpecs, and Outcomes.
It implements the ContextCacheReader protocol required by the Lens compiler.
"""

from __future__ import annotations

from motus.context_cache.store import ContextCache

__all__ = ["ContextCache"]
