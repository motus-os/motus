# Website Content Standard

Purpose: Marketing pages only. Rigorous proof work, confident copy, proof link adjacent.

Applies to: homepage, marketing pages, README banners. Not technical docs.

## Before Writing (Hard Gates)
1. Claim exists in `standards/proof-ledger.json` with status `verified`.
2. Evidence bundle exists at `docs/proof/<claim-id>/` with: `methodology.md`, `results.json`, `reproduce.sh`, `manifest.json`.
3. Terms are approved in `standards/terminology.json`; any `requires_definition` term is defined inline.
4. Every claim has a proof-link destination.

## Writing Rules
- Lead with outcome, then how, then proof.
- Use exact claim text from `standards/proof-ledger.json`.
- One idea per sentence; no jargon without definition.
- Proof link within one scroll of the claim.
- One primary CTA per screen; CTA restates the promise.

## Validation
- 5-second test: user answers what/for whom/benefit/action.
- Swap test: competitor name makes the claim false.
- Proof test: every number has a working link.

## Enforcement
- CI blocks if claim text not in proof ledger or proof link missing.
- CI blocks arbitrary Tailwind values not in `standards/tailwind-arbitrary-allowlist.txt`.
- Homepage + claims pages require external reviewer sign-off (record in `artifacts/sign-offs/`).
