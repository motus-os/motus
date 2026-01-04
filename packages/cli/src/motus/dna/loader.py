# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Compatibility shim for DNA loader exports.

DEPRECATED: Use motus.capabilities instead.
"""

from __future__ import annotations

# Import from new location
from motus.capabilities import Capabilities as DNA  # noqa: N814 - intentional alias
from motus.capabilities import deep_merge, get_nested

__all__ = ["DNA", "deep_merge", "get_nested"]
