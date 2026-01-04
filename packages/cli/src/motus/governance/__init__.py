# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Governance module exports (deprecated)."""

import warnings

from motus.observability.roles import Role, get_agent_role

from .audit import log_governance_action

warnings.warn(
    "motus.governance is deprecated; use motus.observability instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["Role", "get_agent_role", "log_governance_action"]
