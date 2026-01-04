# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Session identity utilities."""

from __future__ import annotations

import hashlib

PREFIX = "mot_ses"


def _normalize_timestamp(timestamp: str) -> str:
    return timestamp.replace("-", "").replace(":", "").replace(".", "")


def _hash_context(context: bytes) -> str:
    return hashlib.sha256(context).hexdigest()[:8]


def generate_session_id(timestamp: str, agent_type: str, context: bytes) -> str:
    """Generate a session ID string.

    Format: mot_ses_{timestamp}_{agent_type}_{hash8}
    """
    normalized = _normalize_timestamp(timestamp)
    return f"{PREFIX}_{normalized}_{agent_type}_{_hash_context(context)}"


__all__ = ["generate_session_id"]
