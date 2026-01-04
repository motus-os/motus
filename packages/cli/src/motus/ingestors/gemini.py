# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Compatibility shim for Gemini builder exports."""

from .gemini_session import MAX_FILE_SIZE, GeminiBuilder
from .gemini_tools import GEMINI_TOOL_MAP, map_gemini_tool

GeminiSessionBuilder = GeminiBuilder

__all__ = [
    "GEMINI_TOOL_MAP",
    "GeminiBuilder",
    "GeminiSessionBuilder",
    "map_gemini_tool",
    "MAX_FILE_SIZE",
]
