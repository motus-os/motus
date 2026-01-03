# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Compatibility shim for governance roles (deprecated)."""

from motus.observability.roles import Role, get_agent_role

__all__ = ["Role", "get_agent_role"]
