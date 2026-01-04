# Protocols and Schemas

Motus uses two related representations of “events” and “sessions”:

1. **Unified dataclasses** (`motus.protocols*`): what ingestors produce and UIs consume.
2. **Validated Pydantic schema** (`motus.schema.*`): a strict validation layer for correctness and tooling.

## Unified dataclasses (`motus.protocols`)

The main types are:

- `UnifiedEvent` (source-agnostic event)
- `UnifiedSession` (source-agnostic session)
- `Source`, `EventType`, `RiskLevel`, `SessionStatus` (enums)

### Example: build a `UnifiedEvent`

```python
from datetime import datetime, timezone

from motus.protocols import EventType, UnifiedEvent

event = UnifiedEvent(
    event_id="evt-1",
    session_id="sess-1",
    timestamp=datetime.now(tz=timezone.utc),
    event_type=EventType.DECISION,
    content="Use a local sqlite db",
    decision_text="Use SQLite",
    reasoning="Local-first, easy to inspect",
    files_affected=["pyproject.toml"],
)

print(event.to_dict()["event_type"])
```

### Example: serialize for JSONL

```python
import json
from datetime import datetime, timezone

from motus.protocols import EventType, UnifiedEvent

event = UnifiedEvent(
    event_id="evt-2",
    session_id="sess-1",
    timestamp=datetime.now(tz=timezone.utc),
    event_type=EventType.THINKING,
    content="Check existing patterns in the repo",
)

line = json.dumps(event.to_dict(), sort_keys=True)
print(line)
```

## Validated schema (`motus.schema.events`)

`ParsedEvent` is the canonical validated representation. Builders can produce validated events via:

- `BaseBuilder.parse_events_validated(path)`
- `BaseBuilder.parse_line_validated(raw_line, session_id)`

For integrations that already have a `UnifiedEvent`, use the conversion helper:

- `motus.schema.events.unified_to_parsed(unified, source=AgentSource.…)`

### Example: validate a `UnifiedEvent`

```python
from datetime import datetime, timezone

from motus.protocols import EventType, UnifiedEvent
from motus.schema.events import AgentSource, unified_to_parsed

unified = UnifiedEvent(
    event_id="evt-3",
    session_id="sess-1",
    timestamp=datetime.now(tz=timezone.utc),
    event_type=EventType.TOOL,
    content="Read README",
    tool_name="Read",
    tool_input={"path": "README.md"},
)

parsed = unified_to_parsed(unified, source=AgentSource.CLAUDE)
assert parsed is not None
print(parsed.event_id, parsed.event_type.value, parsed.source.value)
```
