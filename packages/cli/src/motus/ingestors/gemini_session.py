# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Session discovery and builder integration for Gemini."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

from ..commands.utils import assess_risk
from ..logging import get_logger
from ..protocols import RawSession, Source, UnifiedEvent
from .base import BaseBuilder
from .common import (
    extract_gemini_decisions,
    extract_gemini_thinking,
    get_gemini_last_action,
    has_gemini_completion_marker,
)
from .gemini_parser import parse_gemini_events
from .gemini_tools import map_gemini_tool

logger = get_logger(__name__)

MAX_FILE_SIZE = 50 * 1024 * 1024


class GeminiBuilder(BaseBuilder):
    """Builder for Google Gemini CLI sessions."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._gemini_dir = Path.home() / ".gemini"
        self._tmp_dir = self._gemini_dir / "tmp"

    @property
    def source_name(self) -> Source:
        return Source.GEMINI

    def discover(self, max_age_hours: int = 24) -> List[RawSession]:
        """Find all Gemini sessions within age limit."""
        sessions: List[RawSession] = []
        cutoff = datetime.now() - timedelta(hours=max_age_hours)

        if not self._tmp_dir.exists():
            return sessions

        for project_dir in self._tmp_dir.iterdir():
            if not project_dir.is_dir():
                continue

            chats_dir = project_dir / "chats"
            if not chats_dir.exists():
                continue

            for json_file in chats_dir.glob("session-*.json"):
                try:
                    stat = json_file.stat()
                    modified = datetime.fromtimestamp(stat.st_mtime)

                    if modified < cutoff:
                        continue

                    if stat.st_size > MAX_FILE_SIZE:
                        self._logger.warning(
                            "Skipping large session file",
                            file_path=str(json_file),
                            file_size=stat.st_size,
                        )
                        continue

                    with open(json_file, "r", encoding="utf-8", errors="replace") as f:
                        data = json.load(f)

                    session_id = data.get("sessionId", json_file.stem)
                    project_hash = data.get("projectHash", project_dir.name)
                    project_path = f"gemini:{project_hash[:8]}"

                    sessions.append(
                        RawSession(
                            session_id=session_id,
                            source=Source.GEMINI,
                            file_path=json_file,
                            project_path=project_path,
                            last_modified=modified,
                            size=stat.st_size,
                        )
                    )
                except (OSError, json.JSONDecodeError) as e:
                    self._logger.debug(
                        "Error reading Gemini session",
                        json_file=str(json_file),
                        error_type=type(e).__name__,
                        error=str(e),
                    )
                    continue

        self._logger.debug("Discovered Gemini sessions", count=len(sessions))
        return sessions

    def parse_events(self, file_path: Path) -> List[UnifiedEvent]:
        return parse_gemini_events(
            file_path,
            session_id=file_path.stem,
            max_file_size=MAX_FILE_SIZE,
            create_thinking_event=self._create_thinking_event,
            extract_decisions_from_text=self._extract_decisions_from_text,
            create_tool_event=self._create_tool_event,
            assess_risk=assess_risk,
            logger_obj=self._logger,
        )

    def extract_thinking(self, file_path: Path) -> List[UnifiedEvent]:
        return extract_gemini_thinking(
            file_path,
            session_id=file_path.stem,
            create_thinking_event=self._create_thinking_event,
            logger_obj=self._logger,
        )

    def extract_decisions(self, file_path: Path) -> List[UnifiedEvent]:
        return extract_gemini_decisions(
            file_path,
            session_id=file_path.stem,
            extract_decisions_from_text=self._extract_decisions_from_text,
            logger_obj=self._logger,
        )

    def get_last_action(self, file_path: Path) -> str:
        return get_gemini_last_action(file_path, map_tool=map_gemini_tool, logger_obj=self._logger)

    def has_completion_marker(self, file_path: Path) -> bool:
        return has_gemini_completion_marker(file_path, logger_obj=self._logger)


GeminiSessionBuilder = GeminiBuilder
