# Request: Consolidated SPEC.md for Motus Work Compiler

**To**: GPT Pro
**From**: Motus Steering Committee
**Date**: 2025-12-24
**Purpose**: Single implementation contract for engineering

---

## Context

We've completed strategic alignment and have your excellent Rust kernel spec (WORKC-RS-0.1) plus algorithmic answers to all 9 hard questions. We also have a comprehensive testing framework.

We're ready to build. Not MVP - the full system.

**Goal**: A single SPEC.md that an engineer (human or AI) can implement from without ambiguity.

---

## What We Need

### 1. Consolidated Type Definitions

All Rust types in one place:
- Core newtypes (Permille, Millis, Hash256, LoopId, EventId)
- Phase, LockLevel, Transition, SpawnMode
- Intent, Outcome, Actor, ArtifactRef
- LoopState, DecisionRecord, ErrorRecord, ErrorClass
- EventEnvelope, PhaseEventPayload
- WorkReceipt, IntegrityBlock, PhaseMetrics
- BundleManifest, FileHashEntry, BundleRoots
- VerificationSpec, VerificationLevel, CheckResult
- Strategy, StrategyTrigger, StrategySuggestion
- LensSnapshot, LensQuality
- Effect, EffectSet (ENF-0.1)
- Policy trait definitions

### 2. All Algorithms (Pseudocode + Rust Signatures)

For each algorithm, provide:
- Input types
- Output types
- Determinism requirements
- Edge cases

Algorithms needed:
1. **CJ-0.1 Canonicalization** - Exact byte-level spec
2. **Event Hash Chain** - h(i) formula with domain separators
3. **Merkle Root** - Odd leaf handling, node construction
4. **Proof Digest** - All inputs, order, domain separator
5. **Receipt Projection** - From events to receipt
6. **FSM Runner** - Main loop with transitions
7. **NEXT Transition Function** - Decision logic
8. **verify_bundle** - All validation steps in order
9. **FSM Replay Validator** - Legal transition checking
10. **ENF-0.1 Effect Normalization** - Dedup, sort, compress
11. **Effect Compression** - Trie-based merge with cost function
12. **Lens Quality Scoring** - coverage, freshness, conflict, provenance formulas
13. **Lens Aggregate** - min() calculation
14. **HITL-EVI Calculation** - p(override) × L(loss) > C(cost)
15. **Strategy Matching** - Trigger evaluation, tie-breaking
16. **Work Graph Rollup** - Child outcome aggregation

### 3. All Merkle Root Formulas

Explicit formulas with domain separators:
- `event_log_root`
- `artifacts_root`
- `evidence_root`
- `lens_root`
- `effects_root`
- `gates_root`
- `verification_root`
- `workgraph_root`

### 4. Canonicalization Spec (CJ-0.1)

Byte-level specification:
- UTF-8 encoding rules
- Object key sorting (lexicographic by UTF-8 bytes)
- Array sorting rules (when schema-defined as sorted)
- Number representation (integers only)
- String normalization (NFC optional but versioned)
- Whitespace handling (none)
- Escape sequences

### 5. FSM Transition Rules (FSM-0.1)

Explicit legal transitions:
- Nominal sequence
- Allowed repeats (with conditions)
- Allowed backtracks (with conditions)
- Spawn semantics
- Join semantics (parent waits for children)
- Escalation rules
- Halt conditions

### 6. verify_bundle Specification

Input: bundle path
Output: Verdict with structured failures

Validation steps in order:
1. File hashing
2. Roots recomputation
3. Receipt hash
4. Proof digest comparison
5. FSM replay validity
6. Policy compliance validity
7. Effect bounds check (if enabled)

Failure codes:
- `HASH_MISMATCH`
- `MERKLE_MISMATCH`
- `EVENT_CHAIN_MISMATCH`
- `RECEIPT_HASH_MISMATCH`
- `PROOF_DIGEST_MISMATCH`
- `FSM_ILLEGAL_TRANSITION`
- `POLICY_VIOLATION`
- `EFFECT_BOUNDS_EXCEEDED`
- `VERIFICATION_INCOMPLETE`

### 7. Property-Based Test Specifications

For each property test, specify:
- Generator constraints
- Property assertion
- Shrinking strategy (optional)

Properties:
1. **Tamper Detection**: Any byte flip → verify fails
2. **Event Reorder Detection**: Shuffle events → root changes
3. **Determinism**: Same seed + scenario → identical digests
4. **ENF Idempotence**: normalize(normalize(x)) == normalize(x)
5. **ENF Compression Bound**: |compress(S)| ≤ K
6. **Lens Score Monotonicity**: min() is monotone
7. **FSM Legality**: Random sequences → correct accept/reject

### 8. Golden Bundle Specifications

For each golden bundle, specify:
- Scenario description
- Expected phase sequence
- Expected proof_digest (exact hex)
- Expected verify_bundle result

Golden bundles:
1. `basic_edit` - Simple file modification
2. `verify_fail_backtrack` - Verification fails, backtracks to Orient
3. `parallel_children` - Spawns 3 parallel child loops
4. `effect_compression` - 200 writes compressed to 50 effects
5. `hitl_checkpoint` - Lock level Committed triggers approval
6. `strategy_applied` - Root Cause Loop strategy used
7. `tiered_recovery` - Recoverable error retried, then succeeds

### 9. Benchmark Specifications

Microbench targets with expected complexity:
- `cj_canonicalize`: O(n log n) for n keys
- `hash_event_chain`: O(n) for n events
- `merkle_root`: O(n log n) for n leaves
- `verify_bundle`: O(events + files)
- `effect_compress`: O(n log n) for n effects

Performance budgets (sanity caps):
- verify_bundle < 1s for 10k events
- merkle_root < 100ms for 10k leaves
- effect_compress < 100ms for 1k effects

### 10. Version Compatibility Matrix

| Version | CJ | PROOF | FSM | Compatible With |
|---------|-----|-------|-----|-----------------|
| v0.1.0 | CJ-0.1 | PROOF-0.1 | FSM-0.1 | - |
| v0.2.0 | CJ-0.1 | PROOF-0.2 | FSM-0.1 | v0.1.0 bundles |

---

## Format Request

Please provide as a single markdown file (`MOTUS-SPEC-V0.1.md`) with:
1. Table of contents
2. Numbered sections matching above
3. Rust code blocks for types and signatures
4. Mathematical notation for formulas
5. ASCII diagrams where helpful
6. Implementation notes in callout blocks

---

## Additional Hard Math Questions

While you're at it, please also specify:

### Q11. Exact Trie-Based Effect Compression Algorithm

The compression algorithm mentions "build a trie, merge siblings to parent." Please provide:
- Trie node structure
- Merge cost function (exact formula)
- Tie-breaking rule (lexicographically smallest)
- Worked example with 10 file paths

### Q12. Lens Freshness Scoring - Piecewise Linear Map

You mentioned:
- 0-7 days: 1000
- 8-30 days: linearly to 700
- 31-180 days: linearly to 200
- >180 days: 100

Please provide:
- Exact formula (integer arithmetic only, no floats)
- Weighted median calculation for aggregate freshness

### Q13. Strategy Trigger Matching - Exact Algorithm

For deterministic suggestions:
- How are signals matched to triggers?
- How is match_permille calculated?
- Tie-breaking when multiple strategies match?
- Explanation generation algorithm?

### Q14. Work Graph Rollup - Exact Semantics

For child outcome aggregation:
- Definition of "critical" vs "non-critical" child
- Exact rollup function for success/partial/failed
- workgraph_root construction order (spawn order, not completion)

### Q15. HITL-EVI Calibration - Exact Model

For p(override) estimation:
- Feature vector x_j definition
- Logistic regression formula (or lookup table)
- Default coefficients for v0.1
- Fatigue cost C default value

---

## Deliverable

Single file: `MOTUS-SPEC-V0.1.md`

This becomes the implementation contract. An engineer reads this, implements it, runs the test suite, and if tests pass, Motus works.

Thank you.
