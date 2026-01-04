# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Codex session discovery and orchestration."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

from ..protocols import RawSession, Source, UnifiedEvent
from .base import BaseBuilder
from .codex_parser import CodexEventParser
from .codex_tools import build_thinking_surrogate, map_codex_tool
from .common import (
    extract_codex_decisions,
    extract_codex_thinking,
    get_codex_last_action,
    has_codex_completion_marker,
    parse_jsonl_line,
)

# Maximum file size to parse (50MB)
MAX_FILE_SIZE = 50 * 1024 * 1024


class CodexBuilder(BaseBuilder):
    """Builder for OpenAI Codex CLI sessions."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._codex_dir = Path.home() / ".codex"
        self._sessions_dir = self._codex_dir / "sessions"
        self._parser = CodexEventParser(
            logger=self._logger,
            create_tool_event=self._create_tool_event,
            extract_decisions_from_text=self._extract_decisions_from_text,
        )

    @property
    def source_name(self) -> Source:
        return Source.CODEX

    def discover(self, max_age_hours: int = 24) -> List[RawSession]:
        sessions: List[RawSession] = []
        cutoff = datetime.now() - timedelta(hours=max_age_hours)

        if not self._sessions_dir.exists():
            return sessions

        for jsonl_file in self._sessions_dir.rglob("*.jsonl"):
            try:
                stat = jsonl_file.stat()
                modified = datetime.fromtimestamp(stat.st_mtime)

                if modified < cutoff:
                    continue

                with open(jsonl_file, "r", encoding="utf-8", errors="replace") as f:
                    first_line = f.readline()
                    if not first_line:
                        continue

                    data = json.loads(first_line)
                    if data.get("type") != "session_meta":
                        continue

                    payload = data.get("payload", {})
                    session_id = payload.get("id", jsonl_file.stem)
                    cwd = payload.get("cwd", "")

                    sessions.append(
                        RawSession(
                            session_id=session_id,
                            source=Source.CODEX,
                            file_path=jsonl_file,
                            project_path=cwd,
                            last_modified=modified,
                            size=stat.st_size,
                        )
                    )
            except (OSError, json.JSONDecodeError) as e:
                self._logger.debug(
                    "Error reading Codex session",
                    jsonl_file=str(jsonl_file),
                    error_type=type(e).__name__,
                    error=str(e),
                )
                continue

        self._logger.debug("Discovered Codex sessions", count=len(sessions))
        return sessions

    def parse_events(self, file_path: Path) -> List[UnifiedEvent]:
        events: List[UnifiedEvent] = []
        session_id = file_path.stem

        try:
            file_size = file_path.stat().st_size
            if file_size > MAX_FILE_SIZE:
                self._logger.warning(
                    "Skipping large Codex file",
                    file_path=str(file_path),
                    file_size=file_size,
                )
                return events
        except OSError:
            return events

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                for line_num, line in enumerate(f, 1):
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        events.extend(self._parser.parse_line_data(data, session_id))
                    except json.JSONDecodeError as e:
                        self._logger.debug(
                            "Invalid JSON in Codex file",
                            line_num=line_num,
                            file_path=str(file_path),
                            error_type=type(e).__name__,
                            error=str(e),
                        )
                        continue
        except OSError as e:
            self._logger.error(
                "Error reading transcript",
                file_path=str(file_path),
                error_type=type(e).__name__,
                error=str(e),
            )

        return events

    def parse_line(self, raw_line: str, session_id: str) -> List[UnifiedEvent]:
        data = parse_jsonl_line(raw_line)
        if data is None:
            return []
        return self._parser.parse_line_data(data, session_id)

    def extract_thinking(self, file_path: Path) -> List[UnifiedEvent]:
        return extract_codex_thinking(
            file_path,
            session_id=file_path.stem,
            create_thinking_event=self._create_thinking_event,
            map_tool=map_codex_tool,
            build_surrogate=build_thinking_surrogate,
            logger_obj=self._logger,
        )

    def extract_decisions(self, file_path: Path) -> List[UnifiedEvent]:
        return extract_codex_decisions(
            file_path,
            session_id=file_path.stem,
            extract_decisions_from_text=self._extract_decisions_from_text,
            logger_obj=self._logger,
        )

    def get_last_action(self, file_path: Path) -> str:
        return get_codex_last_action(file_path, map_tool=map_codex_tool, logger_obj=self._logger)

    def has_completion_marker(self, file_path: Path) -> bool:
        return has_codex_completion_marker(file_path, logger_obj=self._logger)
