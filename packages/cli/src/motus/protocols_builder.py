# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Ingestor protocol interface for transcript sources."""

from __future__ import annotations

from pathlib import Path
from typing import List, Protocol

from .protocols_enums import Source
from .protocols_models import RawSession, UnifiedEvent


class SessionBuilder(Protocol):
    """
    Protocol that all source ingestors must implement.

    Each ingestor handles one source (Claude, Codex, Gemini, SDK) and produces
    unified data structures that surfaces can consume without knowing the source.
    """

    @property
    def source_name(self) -> Source:
        """Return source identifier."""
        ...

    def discover(self, max_age_hours: int = 24) -> List[RawSession]:
        """
        Find all sessions from this source within age limit.

        Returns RawSession objects that will be converted to UnifiedSession
        by the orchestrator after status computation.
        """
        ...

    def parse_events(self, file_path: Path) -> List[UnifiedEvent]:
        """
        Parse transcript file into unified events.

        Should handle all event types the source can produce:
        - thinking, tool, decision, file_change, agent_spawn, error
        """
        ...

    def extract_thinking(self, file_path: Path) -> List[UnifiedEvent]:
        """
        Extract thinking/reasoning events.

        For Claude: actual thinking blocks from transcript
        For Codex: synthetic thinking from tool planning + response patterns
        For Gemini: thoughts/reasoning fields from JSON
        """
        ...

    def extract_decisions(self, file_path: Path) -> List[UnifiedEvent]:
        """
        Extract decision events from transcript.

        Patterns to match (source-agnostic):
        - "I'll...", "I decided...", "I'm going to..."
        - "Let me...", "Planning to..."
        - Tool selections with reasoning
        """
        ...

    def get_last_action(self, file_path: Path) -> str:
        """
        Get the last action from a session file.

        Returns human-readable description like "Edit src/foo.py" or "Bash: npm test"
        """
        ...

    def has_completion_marker(self, file_path: Path) -> bool:
        """
        Check if session has a completion marker after last tool call.

        A completion marker indicates the session finished normally.
        Used to distinguish crashed vs completed sessions.
        """
        ...
