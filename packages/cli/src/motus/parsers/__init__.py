# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Parser module - Abstract base classes for event parsers.

This module provides the base interface that all agent-specific parsers must
implement. The parser architecture follows a plugin pattern where each agent
(Claude, Codex, Gemini) has its own parser implementation.

Key Principles:
- Abstract base class enforces consistent parser interface
- Safe parsing with error handling and logging
- Type-safe with Pydantic models
- Extensible for new agent types

Usage:
    from motus.parsers import BaseParser
    from motus.schema import AgentSource, ParsedEvent

    class MyParser(BaseParser):
        source = AgentSource.CLAUDE

        def can_parse(self, raw_data: dict) -> bool:
            return "claude_specific_field" in raw_data

        def parse(self, raw_data: dict) -> ParsedEvent | None:
            # Parse logic here
            return ParsedEvent(...)
"""

from motus.parsers.base import BaseParser

__all__ = [
    "BaseParser",
]
