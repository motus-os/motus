# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""
Session Discovery Logic.

This module handles session discovery across all sources,
including status computation and process detection.
"""

from datetime import datetime
from typing import Dict, List, Optional

from ..ingestors import BaseBuilder
from ..logging import get_logger
from ..process_detector import ProcessDetector
from ..protocols import SessionStatus, Source, UnifiedSession
from ..session_cache import SessionSQLiteCache

logger = get_logger(__name__)


class SessionDiscovery:
    """Handles session discovery across all sources."""

    def __init__(
        self,
        builders: Dict[Source, BaseBuilder],
        process_detector: ProcessDetector,
        sqlite_cache: SessionSQLiteCache | None = None,
    ):
        """
        Initialize session discovery.

        Args:
            builders: Dictionary of source ingestors.
            process_detector: Process detector for active session detection.
            sqlite_cache: Optional SQLite session cache for fast-path discovery.
        """
        self._builders = builders
        self._process_detector = process_detector
        self._sqlite_cache = sqlite_cache
        self._auto_sync_attempted = False
        self._logger = get_logger(__name__)

    def _maybe_auto_sync(self, max_age_hours: int) -> bool:
        if self._sqlite_cache is None or self._auto_sync_attempted:
            return False
        self._auto_sync_attempted = True
        try:
            from ..core.bootstrap import ensure_database

            ensure_database()
            self._sqlite_cache.sync(
                full=False,
                max_age_hours=max_age_hours,
                force=False,
            )
            return True
        except Exception as e:
            self._logger.debug(
                "SQLite cache auto-sync failed",
                error_type=type(e).__name__,
                error=str(e),
            )
            return False

    def discover_all(
        self,
        max_age_hours: int = 24,
        sources: Optional[List[Source]] = None,
        session_cache: Optional[Dict] = None,
        skip_process_detection: bool = False,
    ) -> List[UnifiedSession]:
        """
        Discover all sessions from specified sources.

        Args:
            max_age_hours: Maximum age of sessions to include.
            sources: List of sources to search. Defaults to all.
            session_cache: Optional session cache to populate.
            skip_process_detection: If True, skip running-process checks for speed.

        Returns:
            List of UnifiedSession objects, sorted by status then recency.
        """
        if sources is None:
            sources = list(self._builders.keys())

        sessions: List[UnifiedSession] = []
        now = datetime.now()

        # Get running projects from ProcessDetector once for all sessions
        running_projects = (
            set() if skip_process_detection else self._process_detector.get_running_projects()
        )

        for source in sources:
            builder = self._builders.get(source)
            if not builder:
                continue

            try:
                if source == Source.CLAUDE and self._sqlite_cache is not None:
                    try:
                        cached = self._sqlite_cache.query(max_age_hours=max_age_hours)
                    except Exception as e:
                        self._logger.debug(
                            "SQLite session cache query failed; falling back to JSONL",
                            error_type=type(e).__name__,
                            error=str(e),
                        )
                        cached = []
                    if not cached and self._maybe_auto_sync(max_age_hours=max_age_hours):
                        try:
                            cached = self._sqlite_cache.query(max_age_hours=max_age_hours)
                        except Exception as e:
                            self._logger.debug(
                                "SQLite session cache query failed after auto-sync; falling back",
                                error_type=type(e).__name__,
                                error=str(e),
                            )
                            cached = []
                    if cached:
                        for row in cached:
                            status, status_reason = builder.compute_status(
                                row.last_modified,
                                now,
                                row.last_action,
                                row.has_completion,
                                row.project_path,
                                running_projects,
                            )
                            session = UnifiedSession(
                                session_id=row.session_id,
                                source=source,
                                file_path=row.file_path,
                                project_path=row.project_path,
                                status=status,
                                status_reason=status_reason,
                                file_size_bytes=row.file_size_bytes,
                                created_at=row.last_modified,
                                last_modified=row.last_modified,
                            )
                            sessions.append(session)
                            if session_cache is not None:
                                session_cache[row.session_id] = session
                    else:
                        raw_sessions = builder.discover(max_age_hours)
                        for raw in raw_sessions:
                            last_action = builder.get_last_action(raw.file_path)
                            has_completion = builder.has_completion_marker(raw.file_path)
                            status, status_reason = builder.compute_status(
                                raw.last_modified,
                                now,
                                last_action,
                                has_completion,
                                raw.project_path,
                                running_projects,
                            )
                            session = UnifiedSession(
                                session_id=raw.session_id,
                                source=source,
                                file_path=raw.file_path,
                                project_path=raw.project_path,
                                status=status,
                                status_reason=status_reason,
                                created_at=raw.created_at or raw.last_modified,
                                last_modified=raw.last_modified,
                            )
                            sessions.append(session)
                            if session_cache is not None:
                                session_cache[raw.session_id] = session
                else:
                    raw_sessions = builder.discover(max_age_hours)
                    for raw in raw_sessions:
                        # Compute status using builder's uniform logic with process detection
                        last_action = builder.get_last_action(raw.file_path)
                        has_completion = builder.has_completion_marker(raw.file_path)
                        status, status_reason = builder.compute_status(
                            raw.last_modified,
                            now,
                            last_action,
                            has_completion,
                            raw.project_path,
                            running_projects,
                        )

                        session = UnifiedSession(
                            session_id=raw.session_id,
                            source=source,
                            file_path=raw.file_path,
                            project_path=raw.project_path,
                            status=status,
                            status_reason=status_reason,
                            created_at=raw.created_at or raw.last_modified,
                            last_modified=raw.last_modified,
                        )

                        sessions.append(session)
                        if session_cache is not None:
                            session_cache[raw.session_id] = session

            except Exception as e:
                self._logger.error(
                    "Error discovering sessions",
                    source=source.value,
                    error_type=type(e).__name__,
                    error=str(e),
                )
                continue

        # Sort: active first, then open, then crashed, then by recency
        def sort_key(s: UnifiedSession):
            status_order = {
                SessionStatus.ACTIVE: 0,
                SessionStatus.OPEN: 1,
                SessionStatus.CRASHED: 2,
                SessionStatus.IDLE: 3,
                SessionStatus.ORPHANED: 4,
            }
            return (status_order.get(s.status, 5), -s.last_modified.timestamp())

        sessions.sort(key=sort_key)
        self._logger.debug("Discovered total sessions", count=len(sessions))
        return sessions

    def find_session(
        self, session_id: str, session_cache: Optional[Dict] = None
    ) -> Optional[UnifiedSession]:
        """
        Find a session by ID.

        Args:
            session_id: The session ID to look up.
            session_cache: Optional session cache to check first.

        Returns:
            UnifiedSession if found, None otherwise.
        """
        # Check cache first
        if session_cache and session_id in session_cache:
            return session_cache[session_id]

        # Try to find it by discovering recent sessions
        sessions = self.discover_all(max_age_hours=168, session_cache=session_cache)  # Last week
        for session in sessions:
            if session.session_id == session_id:
                return session

        return None

    def get_active_sessions(self, session_cache: Optional[Dict] = None) -> List[UnifiedSession]:
        """
        Get only active sessions (currently generating).

        Args:
            session_cache: Optional session cache to populate.

        Returns:
            List of active sessions.
        """
        sessions = self.discover_all(max_age_hours=1, session_cache=session_cache)
        return [s for s in sessions if s.status == SessionStatus.ACTIVE]

    def get_recent_sessions(
        self,
        max_count: int = 10,
        sources: Optional[List[Source]] = None,
        session_cache: Optional[Dict] = None,
    ) -> List[UnifiedSession]:
        """
        Get most recent sessions.

        Args:
            max_count: Maximum number of sessions to return.
            sources: Optional list of sources to filter by.
            session_cache: Optional session cache to populate.

        Returns:
            List of recent sessions, sorted by recency.
        """
        sessions = self.discover_all(
            max_age_hours=168, sources=sources, session_cache=session_cache
        )
        return sessions[:max_count]
