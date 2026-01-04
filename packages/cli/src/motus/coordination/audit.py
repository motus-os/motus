# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

from __future__ import annotations

import json
import os
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from motus.coordination.schemas import AUDIT_EVENT_SCHEMA, AuditEvent


class AuditLogError(Exception):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _generate_uuidv7() -> str:
    """Generate UUIDv7 (time-ordered UUID).

    UUIDv7 format: 48-bit timestamp (ms) + 12-bit random + 62-bit random.
    For now, we use uuid4() and prepend timestamp-based prefix for ordering.
    """
    now = _utcnow()
    timestamp_ms = int(now.timestamp() * 1000)
    # Use first 12 hex digits of timestamp for time-ordering
    time_prefix = f"{timestamp_ms:012x}"
    random_suffix = uuid4().hex[:20]
    return f"evt-{time_prefix}-{random_suffix}"


class AuditLog:
    """Filesystem-backed append-only audit log.

    Events are stored in date-partitioned JSONL files:
    - `root_dir/YYYY-MM-DD.jsonl` (one JSON object per line)
    - Each event has a UUIDv7 event_id for time-ordering
    - Sequence numbers are per-agent monotonic counters
    """

    def __init__(self, root_dir: str | Path) -> None:
        self._root = Path(root_dir)
        self._sequence_counters: dict[str, int] = {}
        self._agent_id = self._get_agent_id()
        self._session_id = self._get_session_id()

    def _get_agent_id(self) -> str:
        """Get current agent ID (placeholder - should be passed in or from config)."""
        return f"agent-{socket.gethostname()}"

    def _get_session_id(self) -> str:
        """Get current session ID (placeholder - should be passed in or from config)."""
        return f"session-{uuid4().hex[:8]}"

    def _ledger_path(self, date: datetime) -> Path:
        """Get path to JSONL file for given date."""
        date_str = date.strftime("%Y-%m-%d")
        return self._root / f"{date_str}.jsonl"

    def _next_sequence(self, agent_id: str) -> int:
        """Get next sequence number for agent."""
        if agent_id not in self._sequence_counters:
            self._sequence_counters[agent_id] = 1
        else:
            self._sequence_counters[agent_id] += 1
        return self._sequence_counters[agent_id]

    def emit(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        task_id: str | None = None,
        correlation_id: str | None = None,
        parent_event_id: str | None = None,
        agent_id: str | None = None,
        session_id: str | None = None,
    ) -> str:
        """Emit an event to the audit log.

        Args:
            event_type: Type of event (e.g., "TASK_CLAIMED", "TASK_COMPLETED")
            payload: Event-specific data
            task_id: Optional task identifier
            correlation_id: Optional correlation ID for cross-agent tracing
            parent_event_id: Optional parent event ID for causal chains
            agent_id: Optional agent ID (defaults to instance agent_id)
            session_id: Optional session ID (defaults to instance session_id)

        Returns:
            The generated event_id
        """
        now = _utcnow()
        agent = agent_id or self._agent_id
        session = session_id or self._session_id
        event_id = _generate_uuidv7()
        sequence = self._next_sequence(agent)

        event = AuditEvent(
            schema=AUDIT_EVENT_SCHEMA,
            event_id=event_id,
            event_type=event_type,
            timestamp=now,
            agent_id=agent,
            session_id=session,
            task_id=task_id,
            correlation_id=correlation_id,
            parent_event_id=parent_event_id,
            sequence_number=sequence,
            payload=payload,
        )

        # Append to date-partitioned JSONL file
        self._append_event(event)

        return event_id

    def _append_event(self, event: AuditEvent) -> None:
        """Append event to date-partitioned JSONL file."""
        self._root.mkdir(parents=True, exist_ok=True)
        ledger_path = self._ledger_path(event.timestamp)

        # Convert to JSON line
        json_line = json.dumps(event.to_json(), separators=(",", ":")) + "\n"

        # Append to file (atomic append)
        # Note: On POSIX, appends <PIPE_BUF bytes are atomic
        # For production, consider using file locking for safety
        try:
            with ledger_path.open("a", encoding="utf-8") as f:
                f.write(json_line)
        except Exception as e:
            raise AuditLogError(f"failed to append event to {ledger_path}") from e

    def _load_events_from_file(self, path: Path) -> list[AuditEvent]:
        """Load all events from a JSONL file."""
        if not path.exists():
            return []

        events = []
        try:
            with path.open("r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                        events.append(AuditEvent.from_json(payload))
                    except Exception as e:
                        # Log error but continue (fail-safe: don't crash on malformed lines)
                        print(f"Warning: Failed to parse event at {path}:{line_num}: {e}")
        except Exception as e:
            raise AuditLogError(f"failed to read events from {path}") from e

        return events

    def query(
        self,
        *,
        event_type: str | None = None,
        task_id: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[AuditEvent]:
        """Query events with filters.

        Args:
            event_type: Filter by event type
            task_id: Filter by task ID
            since: Filter events >= this timestamp
            until: Filter events <= this timestamp

        Returns:
            List of matching events, ordered by timestamp
        """
        if not self._root.exists():
            return []

        # Determine which JSONL files to scan
        files_to_scan: list[Path] = []
        if since is not None or until is not None:
            # Scan specific date range
            # Use today as max bound - can't have events from the future
            from datetime import timedelta
            max_days = max(1, int(os.environ.get("MC_AUDIT_MAX_DAYS", "3650")))
            min_date = datetime(1970, 1, 1, tzinfo=timezone.utc)
            today = _utcnow().date()
            start_date = (since or min_date).date()
            end_date = (until.date() if until is not None else today)
            if (end_date - start_date).days > max_days:
                start_date = end_date - timedelta(days=max_days)
            current_date = start_date
            while current_date <= end_date:
                dt = datetime.combine(current_date, datetime.min.time(), tzinfo=timezone.utc)
                path = self._ledger_path(dt)
                if path.exists():
                    files_to_scan.append(path)
                # Move to next day (with safety check to avoid overflow)
                try:
                    current_date += timedelta(days=1)
                except OverflowError:
                    break
        else:
            # Scan all JSONL files
            files_to_scan = sorted(p for p in self._root.glob("*.jsonl") if p.is_file())

        # Load and filter events
        all_events: list[AuditEvent] = []
        for path in files_to_scan:
            events = self._load_events_from_file(path)
            for event in events:
                # Apply filters
                if event_type is not None and event.event_type != event_type:
                    continue
                if task_id is not None and event.task_id != task_id:
                    continue
                if since is not None and event.timestamp < since:
                    continue
                if until is not None and event.timestamp > until:
                    continue
                all_events.append(event)

        # Sort by timestamp (UUIDv7 should already be ordered, but enforce)
        all_events.sort(key=lambda e: e.timestamp)

        return all_events

    def get_task_history(self, task_id: str) -> list[AuditEvent]:
        """Get all events for a task, ordered by causal chain.

        Returns events in causal order (parent before child).
        """
        events = self.query(task_id=task_id)

        # Build parent-child map
        children_map: dict[str | None, list[AuditEvent]] = {}
        for event in events:
            parent_id = event.parent_event_id
            if parent_id not in children_map:
                children_map[parent_id] = []
            children_map[parent_id].append(event)

        # Topological sort (DFS from roots)
        ordered: list[AuditEvent] = []
        visited: set[str] = set()

        def visit(start: AuditEvent) -> None:
            stack = [start]
            while stack:
                event = stack.pop()
                if event.event_id in visited:
                    continue
                visited.add(event.event_id)
                ordered.append(event)
                children = children_map.get(event.event_id, [])
                for child in reversed(children):
                    stack.append(child)

        # Start from root events (no parent or parent not in task)
        root_events = children_map.get(None, [])
        for event in root_events:
            visit(event)

        # Handle events with parents not in task (orphaned)
        for event in events:
            if event.event_id not in visited:
                visit(event)

        return ordered
