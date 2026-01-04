# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Coordination primitives for multi-agent operation.

Initial v0 focus: filesystem-backed claim registry.
"""

from __future__ import annotations

from motus.coordination.claims import ClaimConflict, ClaimRegistry
from motus.coordination.schemas import ClaimedResource, ClaimRecord

__all__ = [
    "ClaimConflict",
    "ClaimRegistry",
    "ClaimRecord",
    "ClaimedResource",
]

