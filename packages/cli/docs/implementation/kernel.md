# Kernel Implementation Guide

Status: current
Scope: Deterministic coordination + evidence ledger

## Purpose
The kernel is the non-negotiable coordination layer. It owns invariants and is the
single source of truth for work state.

## When to Use
- You want coordination, evidence, and releases to be deterministic.
- You want an audit-friendly work ledger without optional modules.

## Required Invariants
- `coordination.db` is the single source of truth.
- All state changes flow through kernel APIs (no raw SQL writes).
- Evidence is append-only and required before completion.

## Primary Interfaces
- Work Compiler (6-call API)
- Roadmap API
- Policy gates (required evidence types)

## Data Paths
- `~/.motus/coordination.db`

## Best Practices
- Keep migrations idempotent and append-only.
- Use read-only DB connections for analysis.
- Record evidence before marking outcomes complete.
- Use deterministic inputs for contract and decision hashing.

## Tests (Minimum)
- Fresh install creates all tables.
- 6-call flow works end-to-end.
- Evidence requirements are enforced.
