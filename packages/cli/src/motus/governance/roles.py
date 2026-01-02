"""Roles and access helpers for governance workflows."""

from __future__ import annotations

import os
from enum import Enum


class Role(str, Enum):
    BUILDER = "builder"
    REVIEWER = "reviewer"
    ARCHITECT = "architect"


def get_agent_role(agent_id: str | None = None) -> Role:
    """Return the agent role based on environment overrides.

    Priority:
    - MC_REVIEWER=1 forces reviewer role.
    - MC_AGENT_ROLE or MC_ROLE can override to architect/reviewer/builder.
    """
    if os.environ.get("MC_REVIEWER", "0") == "1":
        return Role.REVIEWER

    env_role = (os.environ.get("MC_AGENT_ROLE") or os.environ.get("MC_ROLE") or "").lower()
    if env_role == Role.ARCHITECT.value:
        return Role.ARCHITECT
    if env_role == Role.REVIEWER.value:
        return Role.REVIEWER
    if env_role == Role.BUILDER.value:
        return Role.BUILDER

    return Role.BUILDER
