# Ingestors (Source Adapters)

Ingestors are the source adapters that turn agent-specific logs into Motus “unified” events.

## Available ingestors

- `motus.ingestors.ClaudeBuilder`
- `motus.ingestors.CodexBuilder`
- `motus.ingestors.GeminiBuilder`

All ingestors inherit from `motus.ingestors.BaseBuilder` and produce:

- `motus.protocols.UnifiedSession`
- `motus.protocols.UnifiedEvent`

## Common APIs

- `discover(max_age_hours=24) -> list[RawSession]`
- `parse_events(path) -> list[UnifiedEvent]`
- `parse_events_validated(path) -> list[ParsedEvent]`
- `compute_status(...) -> (SessionStatus, reason)`

### Example: deterministic status computation

```python
from datetime import datetime, timedelta, timezone

from motus.ingestors import ClaudeBuilder

builder = ClaudeBuilder()

now = datetime(2025, 1, 1, tzinfo=timezone.utc)
last_modified = now - timedelta(seconds=30)

status, reason = builder.compute_status(
    last_modified=last_modified,
    now=now,
    last_action="Tool: Read",
    has_completion=True,
    project_path="/tmp/example",
    running_projects=set(),
)

print(status.value, reason)
```

### Example: discover sessions (may be empty)

```python
from motus.ingestors import CodexBuilder

try:
    sessions = CodexBuilder().discover(max_age_hours=0)
except FileNotFoundError:
    sessions = []
print("sessions:", len(sessions))
```
