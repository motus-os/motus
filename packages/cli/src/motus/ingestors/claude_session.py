# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Claude builder session discovery and orchestration."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import List

from ..commands.utils import extract_project_path
from ..config import config
from ..protocols import RawSession, Source, UnifiedEvent
from .base import BaseBuilder
from .claude_parser import parse_events as parse_claude_events
from .claude_parser import parse_line as parse_claude_line
from .common import (
    extract_claude_decisions,
    extract_claude_thinking,
    get_claude_last_action,
    has_claude_completion_marker,
)


class ClaudeBuilder(BaseBuilder):
    """Builder for Claude Code sessions."""

    @property
    def source_name(self) -> Source:
        return Source.CLAUDE

    def discover(self, max_age_hours: int = 24) -> List[RawSession]:
        """Find all Claude sessions within age limit."""
        sessions: List[RawSession] = []
        cutoff = datetime.now() - timedelta(hours=max_age_hours)

        if not config.paths.projects_dir.exists():
            self._logger.debug(
                "Claude projects directory does not exist",
                projects_dir=str(config.paths.projects_dir),
            )
            return sessions

        for project_dir in config.paths.projects_dir.iterdir():
            if not project_dir.is_dir():
                continue

            project_path = extract_project_path(project_dir.name)

            for jsonl_file in project_dir.glob("*.jsonl"):
                try:
                    stat = jsonl_file.stat()
                    modified = datetime.fromtimestamp(stat.st_mtime)

                    if modified > cutoff:
                        sessions.append(
                            RawSession(
                                session_id=jsonl_file.stem,
                                source=Source.CLAUDE,
                                file_path=jsonl_file,
                                project_path=project_path,
                                last_modified=modified,
                                size=stat.st_size,
                            )
                        )
                except OSError as e:
                    self._logger.debug(
                        "Error reading session file",
                        jsonl_file=str(jsonl_file),
                        error_type=type(e).__name__,
                        error=str(e),
                    )
                    continue

        self._logger.debug("Discovered Claude sessions", count=len(sessions))
        return sessions

    def parse_events(self, file_path: Path) -> List[UnifiedEvent]:
        return parse_claude_events(self, file_path)

    def parse_line(self, raw_line: str, session_id: str) -> List[UnifiedEvent]:
        return parse_claude_line(self, raw_line, session_id)

    def extract_thinking(self, file_path: Path) -> List[UnifiedEvent]:
        return extract_claude_thinking(
            file_path,
            session_id=file_path.stem,
            create_thinking_event=self._create_thinking_event,
            logger_obj=self._logger,
        )

    def extract_decisions(self, file_path: Path) -> List[UnifiedEvent]:
        return extract_claude_decisions(
            file_path,
            session_id=file_path.stem,
            extract_decisions_from_text=self._extract_decisions_from_text,
            logger_obj=self._logger,
        )

    def get_last_action(self, file_path: Path) -> str:
        return get_claude_last_action(file_path, logger_obj=self._logger)

    def has_completion_marker(self, file_path: Path) -> bool:
        return has_claude_completion_marker(file_path, logger_obj=self._logger)
