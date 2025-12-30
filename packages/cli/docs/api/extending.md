# Extending Motus Command

Motus Command is structured around a small set of primitives:

- Ingestors (source adapters)
- Protocols (unified dataclasses + validated schema)
- Orchestrator (the single “composition root”)

This page documents how to add support for a new agent/source.

## Add a new source (high level)

1. Add a new `Source` value in `motus.protocols_enums.Source`.
2. Implement a `BaseBuilder` subclass in `motus/ingestors/`.
3. Wire the builder into `SessionOrchestrator` (`motus/orchestrator/core.py`).
4. Add tests and fixtures for discovery + parsing.

## Example: minimal custom builder (for tests / prototyping)

```python
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from motus.ingestors import BaseBuilder
from motus.protocols import EventType, RawSession, Source, UnifiedEvent


class ToyBuilder(BaseBuilder):
    @property
    def source_name(self) -> Source:
        return Source.UNKNOWN

    def discover(self, max_age_hours: int = 24) -> list[RawSession]:
        return []

    def parse_events(self, file_path: Path) -> list[UnifiedEvent]:
        return [
            UnifiedEvent(
                event_id="evt-1",
                session_id="sess-1",
                timestamp=datetime.utcnow(),
                event_type=EventType.THINKING,
                content=f"Parsed: {file_path.name}",
            )
        ]

    def get_last_action(self, file_path: Path) -> str:
        return "Toy last action"

    def has_completion_marker(self, file_path: Path) -> bool:
        return True


events = ToyBuilder().parse_events(Path("demo.jsonl"))
print(events[0].content)
```

## Example: inject a builder into the orchestrator (test-only)

`SessionOrchestrator` exposes `_builders` as a patchable property so tests can inject custom ingestors.

```python
from motus.orchestrator import SessionOrchestrator
from motus.protocols import Source

from motus.ingestors import ClaudeBuilder

orch = SessionOrchestrator()
orch._builders = {Source.CLAUDE: ClaudeBuilder()}  # test-only injection
print(sorted(orch._builders.keys()))
```
