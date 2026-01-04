# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""
Motus Web UI package.

Exports for backward compatibility with existing imports.
"""

# Import from new modular structure
from motus.orchestrator import get_orchestrator
from motus.ui.web.app import MCWebServer, run_web
from motus.ui.web.server import calculate_health

__all__ = [
    "run_web",
    "MCWebServer",
    "get_orchestrator",
    "calculate_health",
]
