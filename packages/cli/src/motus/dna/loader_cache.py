# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Cache helpers for DNA loader file reads.

DEPRECATED: Use motus.capabilities.loader_cache instead.
"""

from __future__ import annotations

# Import from new location
from motus.capabilities.loader_cache import (
    CapabilitiesHelperMixin as DNAHelperMixin,
)
from motus.capabilities.loader_cache import (
    detect_product_from_repo,
    get_registry_suggestion,
    invalidate_cache,
    log_gap,
    read_text_cached,
)

__all__ = [
    "DNAHelperMixin",
    "detect_product_from_repo",
    "get_registry_suggestion",
    "invalidate_cache",
    "log_gap",
    "read_text_cached",
]
