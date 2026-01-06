# Specification Index

> Status of all Motus specifications.

| Spec | Status | Version | Description |
|------|--------|---------|-------------|
| [evidence-bundle](evidence-bundle.md) | Stable | 0.1.0 | Tamper-evident proof format |
| [gate-contract](gate-contract.md) | Stable | 0.1.0 | Verification gate interface |
| [reconciliation](reconciliation.md) | Stable | 0.1.0 | D ⊆ R scope enforcement |
| [plan-seal](plan-seal.md) | Draft | 0.1.0 | Plan commitment before execution |
| [permit-token](permit-token.md) | Draft | 0.1.0 | Authorization for side effects |
| [canonicalization](canonicalization.md) | Draft | 0.1.0 | Deterministic serialization + hashing |
| [conformance-validity](conformance-validity.md) | Draft | 0.1.0 | Conformance vectors must self-validate (anti-theater) |
| [work-completion](work-completion.md) | Draft | 0.1.0 | Bind “DONE” to evidence + immutable source state |

## Status Definitions

- **Stable:** Safe to implement. Breaking changes require major version bump.
- **Draft:** API may change. Feedback welcome. Not recommended for production.
- **Experimental:** Research only. Will change significantly.

## Versioning

Specs follow [SemVer](https://semver.org/):
- MAJOR: Breaking changes
- MINOR: Backward-compatible additions
- PATCH: Clarifications, typo fixes
