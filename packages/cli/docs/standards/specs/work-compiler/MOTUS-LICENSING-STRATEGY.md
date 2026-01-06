# Motus Licensing Strategy

**Date**: 2025-12-24
**Status**: To be finalized before v0.1.0 launch

---

## Goal

Protect Motus intellectual property while building developer mindshare through public documentation.

**Principle**: "Open to read, licensed to use commercially."

---

## What Must Be Licensed

### Algorithms (Core IP)

| Algorithm | Identifier | Purpose |
|-----------|------------|---------|
| Canonical JSON | CJ-0.1 | Deterministic serialization |
| Proof Digest | PROOF-0.1 | Tamper-evident checksums |
| FSM Transitions | FSM-0.1 | Legal phase transitions |
| Effect Normal Form | ENF-0.1 | Effect canonicalization |
| Lens Quality Scoring | LENS-0.1 | Context quality metrics |
| HITL-EVI | HITL-0.1 | Checkpoint decision model |
| Work Graph Rollup | GRAPH-0.1 | Recursive outcome aggregation |

### Protocols

| Protocol | Purpose |
|----------|---------|
| Event Hash Chain | Append-only audit trail |
| Merkle Root Construction | Tamper-evident trees |
| Receipt Projection | Events → Receipt |
| Bundle Verification | PASS/FAIL oracle |
| Strategy Matching | Trigger evaluation |

### Data Formats

| Format | Purpose |
|--------|---------|
| WorkReceipt | Proof of work |
| EvidenceBundle | Audit artifacts |
| BundleManifest | Bundle integrity |
| IntegrityBlock | Checksum surface |

### Strategy Library

All strategies (STRAT-001 through STRAT-009+) are covered.

---

## Recommended License: Motus Fair Use License (MFUL)

### Terms

**Free Use:**
- Personal projects
- Evaluation and testing
- Academic research
- Open source projects (with attribution)
- Companies under $1M ARR (with registration)

**Commercial License Required:**
- Companies over $1M ARR
- Embedding in commercial products
- Offering as a service
- Removing attribution

**Restrictions:**
- No sublicensing without permission
- No claiming independent invention
- Must include license notice in derivatives

### Conversion Clause

After 4 years, each version converts to Apache 2.0.
- MFUL-0.1 (2025) → Apache 2.0 (2029)
- Ensures eventual openness while protecting early investment

---

## Documentation Strategy

### Public on motusos.ai/docs/

All specs published with:
- Full algorithm descriptions
- Mathematical formulas
- Rust type definitions
- Example implementations

**Why public?**
1. Establishes prior art and timestamp
2. Builds developer trust
3. Creates "CUDA effect" (developers think in Motus)
4. Transparent = trustworthy

### License Headers

Every spec file includes:

```
Copyright (c) 2025 Motus Authors
Licensed under the Motus Fair Use License (MFUL-0.1)
See LICENSE.md for terms

Commercial licensing: licensing@motusos.ai
```

---

## Site Structure

```
motusos.ai/
  docs/
    specs/
      cj-0.1.md           # Canonical JSON
      proof-0.1.md        # Proof Digest
      fsm-0.1.md          # FSM Transitions
      enf-0.1.md          # Effect Normal Form
      lens-0.1.md         # Lens Quality
      hitl-0.1.md         # HITL-EVI
      graph-0.1.md        # Work Graph
    formats/
      work-receipt.md
      evidence-bundle.md
      bundle-manifest.md
    strategies/
      overview.md
      strat-001-time-travel.md
      strat-002-parallel-spike.md
      ...
    reference/
      rust-types.md
      failure-codes.md
      version-matrix.md
    license.md            # MFUL-0.1 full text
```

---

## Implementation Timeline

| Task | When |
|------|------|
| Draft MFUL-0.1 text | Week 3 |
| Legal review (if needed) | Week 3 |
| Add license headers to all specs | Week 4 |
| Publish docs on motusos.ai | Week 4 (launch) |
| Set up licensing@motusos.ai | Week 4 |

---

## Comparison to Alternatives

| License | Pros | Cons |
|---------|------|------|
| **MFUL (recommended)** | Custom control, clear terms | Requires drafting |
| BSL | Established, well-understood | Less flexible |
| AGPL | Strong copyleft | May scare enterprises |
| Apache 2.0 | Very permissive | No protection |
| Proprietary | Full control | No community |

MFUL gives us the best of both: community building + commercial protection.

---

## Key Insight

> "The spec is public. The implementation is ours. Commercial use pays."

This is exactly how NVIDIA operates:
- CUDA docs are public
- CUDA runtime is proprietary
- Commercial use requires hardware (payment)

For Motus:
- Specs are public (documented)
- Core implementation is open (community)
- Commercial use at scale requires license (payment)

---

*To be finalized before v0.1.0 launch.*
