"""Session Orchestrator - Core coordination logic."""

from .core_execution import ExecutionMixin
from .core_routing import RoutingMixin


class SessionOrchestrator(RoutingMixin, ExecutionMixin):
    """Centralized orchestrator for all AI agent session management."""

    def __init__(self):
        self._init_routing()


__all__ = ["SessionOrchestrator"]
