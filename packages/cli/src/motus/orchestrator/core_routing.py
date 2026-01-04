# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Session orchestrator routing logic."""

from typing import Dict, List, Optional, Set

from ..ingestors import BaseBuilder, ClaudeBuilder, CodexBuilder, GeminiBuilder
from ..logging import get_logger
from ..process_detector import ProcessDetector
from ..protocols import Source, UnifiedSession
from ..session_cache import SessionSQLiteCache
from .cache import SessionCache
from .discovery import SessionDiscovery
from .teleport import detect_planning_docs, extract_doc_summary


class RoutingMixin:
    """Routing and discovery behaviors for SessionOrchestrator."""

    def _init_routing(self) -> None:
        self._builders_dict: Dict[Source, BaseBuilder] = {
            Source.CLAUDE: ClaudeBuilder(),
            Source.CODEX: CodexBuilder(),
            Source.GEMINI: GeminiBuilder(),
        }
        self._process_detector = ProcessDetector()
        self._cache = SessionCache()
        self._logger = get_logger(__name__)
        self._sqlite_cache = SessionSQLiteCache()
        self._discovery = SessionDiscovery(
            self._builders_dict,
            self._process_detector,
            sqlite_cache=self._sqlite_cache,
        )

    @property
    def _builders(self):
        return self._builders_dict

    @_builders.setter
    def _builders(self, value):
        self._builders_dict = value
        self._discovery._builders = value

    @_builders.deleter
    def _builders(self):
        pass

    @property
    def _session_cache(self):
        return self._cache._session_cache

    @property
    def _event_cache(self):
        return self._cache._event_cache

    @property
    def _event_access_times(self):
        return self._cache._event_access_times

    @property
    def _parsed_event_cache(self):
        return self._cache._parsed_event_cache

    @property
    def _parsed_event_access_times(self):
        return self._cache._parsed_event_access_times

    def _prune_caches(self):
        return self._cache.prune_caches()

    def _detect_planning_docs(self, project_path: str) -> Dict[str, str]:
        return detect_planning_docs(project_path)

    def _extract_doc_summary(self, content: str, max_chars: int = 500) -> str:
        return extract_doc_summary(content, max_chars)

    def discover_all(
        self,
        max_age_hours: int = 24,
        sources: Optional[List[Source]] = None,
        skip_process_detection: bool = False,
    ) -> List[UnifiedSession]:
        sessions = self._discovery.discover_all(
            max_age_hours=max_age_hours,
            sources=sources,
            session_cache=self._cache._session_cache,
            skip_process_detection=skip_process_detection,
        )
        self._cache.prune_caches()
        return sessions

    def get_session(self, session_id: str) -> Optional[UnifiedSession]:
        return self._discovery.find_session(session_id, self._cache._session_cache)

    def get_active_sessions(self) -> List[UnifiedSession]:
        return self._discovery.get_active_sessions(self._cache._session_cache)

    def get_recent_sessions(
        self, max_count: int = 10, sources: Optional[List[Source]] = None
    ) -> List[UnifiedSession]:
        return self._discovery.get_recent_sessions(
            max_count=max_count, sources=sources, session_cache=self._cache._session_cache
        )

    def refresh_cache(self, session_id: Optional[str] = None):
        if session_id:
            self._cache.clear_session(session_id)
        else:
            self._cache.clear_all()

    def get_builder(self, source: Source) -> Optional[BaseBuilder]:
        return self._builders.get(source)

    def get_running_projects(self) -> Set[str]:
        return self._process_detector.get_running_projects()

    def is_process_degraded(self) -> bool:
        return self._process_detector.is_degraded()

    def is_project_active(self, project_path: str) -> bool:
        return self._process_detector.is_project_active(project_path)
