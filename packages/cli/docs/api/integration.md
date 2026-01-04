# Integration Guide

This guide shows a few practical integration patterns for Motus as a library.

## Pattern: validate + store events you already have

If you already have a stream of “unified” events (e.g., from your own agent runtime), validate them against the Motus schema at ingress.

```python
from datetime import datetime, timezone

from motus.protocols import EventType, UnifiedEvent
from motus.schema.events import AgentSource, unified_to_parsed

unified = UnifiedEvent(
    event_id="evt-1",
    session_id="sess-1",
    timestamp=datetime.now(tz=timezone.utc),
    event_type=EventType.ERROR,
    content="Tool failed",
)

parsed = unified_to_parsed(unified, source=AgentSource.UNKNOWN)
assert parsed is not None
print(parsed.to_dict().keys())
```

## Pattern: call external APIs with resilience defaults

Motus includes a small resilience helper for external HTTP APIs (429/5xx backoff and retry).

```python
import httpx

from motus.api.resilience import call_with_backoff

attempts = {"n": 0}


def flaky() -> str:
    attempts["n"] += 1
    if attempts["n"] < 3:
        request = httpx.Request("GET", "https://example.invalid")
        response = httpx.Response(503, request=request)
        raise httpx.HTTPStatusError("Service Unavailable", request=request, response=response)
    return "ok"


result = call_with_backoff(
    flaky,
    provider="example",
    what="demo call",
    max_retries=3,
    transient_base_delay_seconds=0.01,
    rate_limit_base_delay_seconds=0.01,
    log=lambda msg: None,
)

print(result)
```
