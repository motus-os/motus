"""Compatibility shim for Claude builder exports."""

from .claude_session import ClaudeBuilder

ClaudeSessionBuilder = ClaudeBuilder

__all__ = ["ClaudeBuilder", "ClaudeSessionBuilder"]
