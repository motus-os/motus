# `mc orient stats`

Show hit-rate and conflict-rate analytics for Cached Orient decisions, based on local telemetry in `.motus/state/orient/events.jsonl`.

## Usage

```bash
# Summary (all decision types)
mc orient stats

# Top 5 lowest hit-rate types (optimization targets)
mc orient stats --high-miss

# Only include types with enough volume
mc orient stats --min-calls 10

# Machine-readable output
mc orient stats --json
```

## Metrics

- **Hit Rate:** `HITs / (HITs + MISSes)`
- **Conflict Rate:** `CONFLICTs / total_calls`

## Notes

- Telemetry is **workspace-local** (stored under `.motus/`), and is **best-effort** (lookup behavior must never fail due to telemetry write errors).
- If you have no telemetry yet, run `mc orient <decision_type> ...` a few times to generate events.

