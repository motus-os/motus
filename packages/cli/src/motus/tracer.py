# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""
Motus Tracer SDK

Use this to instrument any Python AI agent with Motus observability.

Example:
    from motus import Tracer

    tracer = Tracer("my-agent")

    @tracer.track
    def agent_step(prompt):
        return llm.complete(prompt)

    # Or explicit logging
    tracer.thinking("Analyzing the problem...")
    tracer.tool("WebSearch", {"query": "python async"})
    tracer.decision("Using ThreadPoolExecutor", reasoning="Need parallel I/O")
"""

import functools
import json
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Callable, Optional

# Import from centralized config
from .config import MC_STATE_DIR
from .events import (
    AgentSpawnEvent,
    DecisionEvent,
    FileChangeEvent,
    ThinkingEvent,
    ToolEvent,
)

# Global tracer registry
_tracers: dict[str, "Tracer"] = {}

# Ensure state directory exists
MC_STATE_DIR.mkdir(exist_ok=True)


def get_tracer(name: str = "default") -> "Tracer":
    """Get or create a named tracer."""
    if name not in _tracers:
        _tracers[name] = Tracer(name)
    return _tracers[name]


class Tracer:
    """
    Motus Tracer for AI agent observability.

    Logs events to Motus state directory (~/.mc/traces/<session_id>.jsonl) for Motus to watch.
    """

    def __init__(
        self,
        name: str = "default",
        session_id: Optional[str] = None,
        auto_flush: bool = True,
    ):
        self.name = name
        self.session_id = session_id or f"{name}-{uuid.uuid4().hex[:8]}"
        self.auto_flush = auto_flush
        self._events: list = []
        self._start_time = datetime.now()

        # Ensure traces directory exists
        self.traces_dir = MC_STATE_DIR / "traces"
        self.traces_dir.mkdir(exist_ok=True)

        self.trace_file = self.traces_dir / f"{self.session_id}.jsonl"

        # Register globally
        _tracers[name] = self

        # Log session start
        self._write_event(
            {
                "type": "SessionStart",
                "timestamp": self._start_time.isoformat(),
                "session_id": self.session_id,
                "tracer_name": self.name,
            }
        )

    def _write_event(self, event_dict: dict):
        """Write event to trace file."""
        with open(self.trace_file, "a") as f:
            f.write(json.dumps(event_dict) + "\n")

    def thinking(self, content: str):
        """Log a thinking/reasoning event."""
        event = ThinkingEvent(
            content=content,
            session_id=self.session_id,
        )
        self._write_event(event.to_dict())
        return event

    def tool(
        self,
        name: str,
        input: dict,
        output: Any = None,
        status: str = "success",
        risk_level: str = "safe",
        duration_ms: Optional[int] = None,
    ):
        """Log a tool call event."""
        event = ToolEvent(
            name=name,
            input=input,
            output=output,
            status=status,
            risk_level=risk_level,
            duration_ms=duration_ms,
            session_id=self.session_id,
        )
        self._write_event(event.to_dict())
        return event

    def decision(
        self,
        decision: str,
        reasoning: str = "",
        alternatives: Optional[list] = None,
    ):
        """Log a decision event."""
        event = DecisionEvent(
            decision=decision,
            reasoning=reasoning,
            alternatives=alternatives or [],
            session_id=self.session_id,
        )
        self._write_event(event.to_dict())
        return event

    def spawn_agent(
        self,
        agent_type: str,
        description: str,
        prompt: str = "",
        model: Optional[str] = None,
    ):
        """Log spawning a subagent."""
        event = AgentSpawnEvent(
            agent_type=agent_type,
            description=description,
            prompt=prompt,
            model=model,
            session_id=self.session_id,
        )
        self._write_event(event.to_dict())
        return event

    def file_change(
        self,
        path: str,
        operation: str,
        lines_added: int = 0,
        lines_removed: int = 0,
    ):
        """Log a file modification."""
        event = FileChangeEvent(
            path=path,
            operation=operation,
            lines_added=lines_added,
            lines_removed=lines_removed,
            session_id=self.session_id,
        )
        self._write_event(event.to_dict())
        return event

    @contextmanager
    def tool_span(self, name: str, input: dict, risk_level: str = "safe"):
        """
        Context manager for timing tool calls.

        Usage:
            with tracer.tool_span("WebSearch", {"query": "test"}) as span:
                result = search(query)
                span.output = result
        """
        start = time.perf_counter()

        class Span:
            """Mutable container for tool span output and status."""

            output: Any = None
            status: str = "success"

        span = Span()

        try:
            yield span
        except Exception as e:
            span.status = "error"
            span.output = str(e)
            raise
        finally:
            duration_ms = int((time.perf_counter() - start) * 1000)
            self.tool(
                name=name,
                input=input,
                output=span.output,
                status=span.status,
                risk_level=risk_level,
                duration_ms=duration_ms,
            )

    def track(
        self,
        func: Optional[Callable] = None,
        *,
        name: Optional[str] = None,
        risk_level: str = "safe",
    ):
        """
        Decorator to automatically track function calls as tool events.

        Usage:
            @tracer.track
            def my_function(x, y):
                return x + y

            @tracer.track(name="CustomName", risk_level="medium")
            def risky_operation():
                ...
        """

        def decorator(f: Callable) -> Callable:
            """Wrap a function to emit a tool event on completion."""

            @functools.wraps(f)
            def wrapper(*args, **kwargs):
                """Call the wrapped function and record a tool event."""
                tool_name = name or f.__name__
                input_data = {
                    "args": [str(a)[:100] for a in args],
                    "kwargs": {k: str(v)[:100] for k, v in kwargs.items()},
                }

                start = time.perf_counter()
                status = "success"
                output = None

                try:
                    result = f(*args, **kwargs)
                    output = str(result)[:200] if result else None
                    return result
                except Exception as e:
                    status = "error"
                    output = str(e)
                    raise
                finally:
                    duration_ms = int((time.perf_counter() - start) * 1000)
                    self.tool(
                        name=tool_name,
                        input=input_data,
                        output=output,
                        status=status,
                        risk_level=risk_level,
                        duration_ms=duration_ms,
                    )

            return wrapper

        if func is not None:
            return decorator(func)
        return decorator

    def end_session(self):
        """Mark session as ended."""
        self._write_event(
            {
                "type": "SessionEnd",
                "timestamp": datetime.now().isoformat(),
                "session_id": self.session_id,
                "duration_seconds": (datetime.now() - self._start_time).total_seconds(),
            }
        )

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        self.end_session()
        return False
