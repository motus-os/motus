# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Motus Coordination API (6-call).

This module implements the spec-compliant coordination API:
- peek: Scout resources without locking
- claim: Acquire lease with snapshot + Lens
- get_context: Assemble fresh Lens for existing lease (PA-047)
- status: Append structured events (heartbeat, progress, blocker, decision, checkpoint)
- claim_additional: Expand scope mid-lease
- release: Finalize with outcome + evidence
- force_release: Human break-glass override
"""

from __future__ import annotations

from motus.coordination.api.coordinator import Coordinator
from motus.coordination.api.types import (
    ClaimResponse,
    ForceReleaseResponse,
    GetContextResponse,
    PeekResponse,
    ReleaseResponse,
    StatusResponse,
)

__all__ = [
    "Coordinator",
    "PeekResponse",
    "ClaimResponse",
    "GetContextResponse",
    "StatusResponse",
    "ReleaseResponse",
    "ForceReleaseResponse",
]
