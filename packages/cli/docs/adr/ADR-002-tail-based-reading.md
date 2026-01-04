# ADR-002: Tail-Based Reading for Large Session Files

## Status
Accepted (retroactive)

## Date
2025-12-18 (documented); retroactive to v0.4.x performance work

## Context
Agent session logs can grow very large (hundreds of MB). Fully reading and parsing entire JSONL transcripts on every refresh creates latency and undermines the “live dashboard” feel.

Motus needs a fast “recent activity” view for:

- `motus feed` and live streaming surfaces
- MCP tools that return a small tail of events by default
- Web UI polling and incremental updates

Evidence of the tail-based approach in the codebase:

- Tail reader implementation: `src/motus/tail_reader.py` (`tail_lines`, `tail_jsonl`, `get_file_stats`)
- Orchestrator uses tail reads: `src/motus/orchestrator/events.py` imports `tail_lines` and provides tail-loading helpers
- CLI/MCP defaults: `src/motus/commands/feed_cmd.py`, `src/motus/mcp/tools.py` reference `tail_lines` parameters and enforce bounds

## Decision
Default to **tail-based reading** for large session transcripts:

- Read only the last *N* lines for “live” views.
- Parse those lines into unified events (and optionally validated events) for display and downstream tooling.
- Keep full-file parsing available for workflows that require complete history, but do not make it the default path on every refresh.

## Consequences

### Positive
- Dramatically better responsiveness for large session files (recent activity loads without scanning the entire file).
- Reduced memory pressure and lower risk of OOM behavior during parsing.
- A consistent “safety default” across interfaces (CLI, MCP, web).

### Negative
- The default experience is biased toward **recent** events; older context may require explicit full-history operations.
- Tail parsing must be defensive (partial writes, encoding issues, malformed lines). This pushes more complexity into the file IO layer and test coverage.

