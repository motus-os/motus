# Knowledge Engine (Hot/Cold Framework)

Status: building
Roadmap: RI-MOD-030

## Purpose
Provide authoritative hot knowledge and traceable cold references for context
assembly and decision support.

## Implementation Notes
- Hot knowledge overrides cold reference.
- Retrievals are traceable as evidence.
- Chunk lifecycle is deterministic (ingest, tag, prune).

## Best Practices
- Keep retrieval inputs explicit.
- Record knowledge snapshots with attempts.
- Never write directly to coordination.db.
