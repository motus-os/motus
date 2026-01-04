# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Session orchestrator execution logic."""

from typing import Dict, List

from ..protocols import SessionHealth, TeleportBundle, UnifiedEvent, UnifiedSession, compute_health
from ..schema.events import ParsedEvent
from .context import aggregate_context
from .events import (
    load_events,
    load_events_tail,
    load_events_tail_validated,
    load_events_validated,
)
from .teleport import create_teleport_bundle


class ExecutionMixin:
    """Event execution and aggregation behaviors for SessionOrchestrator."""

    def get_events(self, session: UnifiedSession, refresh: bool = False) -> List[UnifiedEvent]:
        builder = self._builders.get(session.source)
        return load_events(session, builder, self._cache, refresh)

    def get_events_tail(self, session: UnifiedSession, n_lines: int = 200) -> List[UnifiedEvent]:
        builder = self._builders.get(session.source)
        return load_events_tail(session, builder, n_lines)

    def get_events_validated(
        self, session: UnifiedSession, refresh: bool = False
    ) -> List[ParsedEvent]:
        builder = self._builders.get(session.source)
        return load_events_validated(session, builder, self._cache, refresh)

    def get_events_tail_validated(
        self, session: UnifiedSession, n_lines: int = 200
    ) -> List[ParsedEvent]:
        builder = self._builders.get(session.source)
        return load_events_tail_validated(session, builder, n_lines)

    def get_health(self, session: UnifiedSession) -> SessionHealth:
        events = self.get_events(session)
        return compute_health(session, events)

    def get_context(self, session: UnifiedSession) -> Dict:
        events = self.get_events(session)
        return aggregate_context(events)

    def export_teleport(
        self, session: UnifiedSession, include_planning_docs: bool = True
    ) -> TeleportBundle:
        events = self.get_events(session)
        context = self.get_context(session)

        builder = self._builders.get(session.source)
        last_action = ""
        if builder:
            last_action = builder.get_last_action(session.file_path)

        return create_teleport_bundle(session, events, context, last_action, include_planning_docs)
