# Work Ledger (Future)

Status: Future
Roadmap: RI-IP-002

## Purpose

The Work Ledger signs and records work receipts so execution can be verified
independently of any single agent or vendor. It extends proof capture into a
long-lived, append-only ledger.

## Boundaries

- Ledger entries are immutable and append-only.
- Entries must reference evidence bundle hashes.
- Signing keys are rotated and auditable.
- Ledger writes flow through kernel APIs.

## Integration Notes

- Depends on the Proof Engine output format.
- Used by Asset Registry and Motus Exchange for attribution.
