"""Governance module exports (deprecated)."""

import warnings

from .audit import log_governance_action
from motus.observability.roles import Role, get_agent_role

warnings.warn(
    "motus.governance is deprecated; use motus.observability instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["Role", "get_agent_role", "log_governance_action"]
