# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Capabilities Configuration System for Motus.

This module provides access to vault capabilities configuration, enabling
zero-thinking configuration injection for policy decisions, thresholds,
and standards.

Usage:
    from motus.capabilities import Capabilities

    # Load capabilities for a product
    caps = Capabilities.load("emmaus")

    # Get values (returns None if not found)
    max_loc = caps.get("code.max_lines_per_file")  # 300

    # Get with gap logging (logs missing paths to GAP-LOG.md)
    value = caps.get_with_prompt("some.path", "agent-id")

    # Use helper methods for common lookups
    gates = caps.get_gates("code")  # ["T0-SYNTAX-001", "T1-LINT-001"]
    priority = caps.infer_priority("defect")  # "P1"

Aliases:
    DNA is provided as an alias for backwards compatibility.
    New code should use Capabilities.

Example Integration:
    # In policy/run.py
    from motus.capabilities import Capabilities

    def run_policy(repo: Path, files: list[str]):
        caps = Capabilities.load_for_repo(repo)
        max_loc = caps.get("code.max_lines_per_file", 300)
        gates = caps.get_gates("code")
        ...
"""

from motus.capabilities.loader import Capabilities, deep_merge, get_nested

# Backwards compatibility alias
DNA = Capabilities

__all__ = ["Capabilities", "DNA", "get_nested", "deep_merge"]
