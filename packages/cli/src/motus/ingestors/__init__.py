# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""
Motus Ingestors

Source-specific ingestors that implement the SessionBuilder protocol.
Each ingestor handles one source and produces unified data structures.

PERFORMANCE: Lazy imports - ingestors loaded only when orchestrator needs them.
"""

__all__ = [
    "BaseBuilder",
    "ClaudeBuilder",
    "CodexBuilder",
    "GeminiBuilder",
]


def __getattr__(name):
    """Lazy load builder modules."""
    if name == "BaseBuilder":
        from .base import BaseBuilder

        return BaseBuilder
    elif name == "ClaudeBuilder":
        from .claude import ClaudeBuilder

        return ClaudeBuilder
    elif name == "CodexBuilder":
        from .codex import CodexBuilder

        return CodexBuilder
    elif name == "GeminiBuilder":
        from .gemini import GeminiBuilder

        return GeminiBuilder
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
