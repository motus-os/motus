# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Governance audit logging for builder/reviewer workflows."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from motus.logging import get_logger

from .roles import get_agent_role

logger = get_logger(__name__)


def log_governance_action(
    action: str,
    actor: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Log a governance action for audit visibility."""
    payload = {
        "action": action,
        "actor": actor or "unknown",
        "role": get_agent_role(actor).value,
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "metadata": metadata or {},
    }
    logger.info("governance_action", extra={"governance": payload})
    return payload
