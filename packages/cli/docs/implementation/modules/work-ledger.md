# Work Ledger (Partial)

Status: Partial (v0.1.2)
Roadmap: RI-IP-002 (future expansion)

## Purpose

The Work Ledger records work execution so it can be verified independently of
any single agent or vendor. In v0.1.2 it captures work items, steps, artifacts,
and gate outcomes, with append-only guarantees for immutable records.

## Current Scope (v0.1.2)

- Work Items: `roadmap_items` holds work metadata (mode, routing, intent, scope).
- Work Steps: `work_steps` tracks per-work execution steps and status.
- Work Artifacts: `work_artifacts` stores evidence/decision artifacts with hashes.
- Gate Outcomes: `gate_outcomes` persists policy gate decisions by work/step.

## Boundaries

- Work artifacts and gate outcomes are immutable and append-only.
- Work items and steps are mutable to reflect execution state.
- Artifact records include hashes for verification; evidence bundles are stored
  under `.motus/evidence` and referenced via `source_ref`.
- Ledger writes flow through kernel APIs (Work Compiler + policy runner).

## Integration Notes

- Work Compiler writes steps and artifacts on claim/evidence/decision/release.
- Reflection notes are stored as `reflection_note` artifacts.
- Policy runner writes gate outcomes when `--work-id/--step-id` are provided.
- `motus work status` surfaces persisted outcomes, evidence, decisions, and gate outcomes.
