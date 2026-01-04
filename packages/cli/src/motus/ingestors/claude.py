# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Compatibility shim for Claude builder exports."""

from .claude_session import ClaudeBuilder

ClaudeSessionBuilder = ClaudeBuilder

__all__ = ["ClaudeBuilder", "ClaudeSessionBuilder"]
