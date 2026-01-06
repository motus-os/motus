# Motus Testing + Benchmarking Framework

**Purpose**: Implementation-ready testing framework for Motus Work Compiler
**Status**: Approved by steering committee

---

## 0) Core Principle: One Test Oracle

Everything flows through a single oracle:

**Oracle**: `verify_bundle(bundle) -> Verdict { PASS | FAIL + reasons }`

A run is "correct" when:
1. **Integrity**: hashes/merkle roots/event-chain match
2. **Semantic validity**: FSM replay is legal
3. **Policy compliance**: required gates/verification/HITL rules satisfied
4. **Declared verification satisfied**: checks exist + evidence hashes match
5. **Effect bounds respected**: executed effects ⊆ declared effects

---

## 1) Repository Layout

```
workc_core/        # Kernel: types, CJ-0.1, PROOF-0.1, FSM, verify_bundle()
workc_runtime/     # Motus adapters (Lens, Skills, Gates, Coordination)
workc_testkit/     # Deterministic testing harness
workc_scenarios/   # Scenario suite ("workmarks")
workc_bench/       # Benchmarks (criterion)
workc_cli/         # CLI: run, verify-bundle, bench, explain
```

---

## 2) Testkit: Deterministic Harness

### SimRuntime Components
- `FakeClock { now_utc() }` - monotonic, stepable
- `SeededRng(u64)` - recorded when used
- `InMemoryReceiptStore` - append-only JSONL
- `InMemoryEvidenceStore` - maps path → bytes + sha256
- `MockCoordinationApi` - simulate contention, deadlocks
- `MockGates` - pass/fail at step N
- `MockSkills` - deterministic effects and outputs

### Scenario Format

```rust
pub struct Scenario {
    pub id: &'static str,
    pub description: &'static str,
    pub intent: Intent,
    pub lens_script: LensScript,
    pub plan_script: PlanScript,
    pub skill_script: SkillScript,
    pub gate_script: GateScript,
    pub verify_script: VerifyScript,
    pub coord_script: CoordScript,
    pub expect: Expectations,
}
```

---

## 3) Testing Pyramid

### Layer A: Pure Unit Tests (workc_core)

**A1) Canonicalization (CJ-0.1)**
- Same JSON → identical bytes
- Key sorting correct
- Array sorting rules applied
- No floats
- Cross-platform determinism

**A2) Hash-chain and Merkle**
- Event chain recomputation matches
- Merkle root correct (odd leaf duplication)
- Tamper: flip 1 byte → root changes

**A3) Proof Digest (PROOF-0.1)**
- Recomputed equals recorded
- Changes when: receipt changes, events reorder, evidence changes, artifacts change

**A4) FSM Transition Legality (FSM-0.1)**
- Accept legal flows
- Accept allowed backtracks/repeats
- Reject illegal transitions

### Layer B: Property-Based Tests (proptest)

**B1) Tamper Detection**
- Mutate bundle (byte flip, reorder, missing file)
- Expect: verifier fails with specific code

**B2) Determinism**
- Same seed + scenario → identical digests

**B3) Effect Normalization (ENF)**
- Dedup works, ordering stable
- Compression reduces to ≤ K
- Tie-breaking deterministic

**B4) Lens Scoring**
- min(components) monotonic
- Thresholds trigger correct transitions

### Layer C: Integration Tests (workc_runtime)

**C1) Golden Bundle Verification**
- Pre-generated bundles in `fixtures/golden/`
- verify_bundle() == PASS
- proof_digest matches stored constant

**C2) Cross-Version Acceptance**
- Old version bundles still verify
- Verifier dispatches by version

### Layer D: End-to-End Scenarios (workc_scenarios)

**Required Scenario Categories:**
1. Happy path: Observe→Lock success
2. Insufficient signals: Observe repeats
3. Lens conflict: Orient spawns child to resolve
4. Verify fail → backtrack
5. Tiered recovery: recoverable/unrecoverable/catastrophic
6. Effect explosion: compression + HITL trigger
7. Parallel children: coordination prevents collisions
8. Lock-level policy: Committed requires HITL
9. Implicit decide: low-risk only, logged
10. Strategy triggers: deterministic, reproducible

---

## 4) Benchmarks

### Microbench (criterion)
- `cj_canonicalize_receipt_small/medium/large`
- `hash_event_chain_N` (N=10, 100, 1k, 10k)
- `merkle_root_M` (M=10, 100, 1k, 10k)
- `verify_bundle_small/medium/large`
- `effect_normalize_and_compress`

### Macrobench (workmark suites)
- `suite_smoke`: 10 tiny scenarios, <1s
- `suite_core`: 10 required categories
- `suite_scale`: 10k events
- `suite_parallel`: depth 3, fanout 8

### Metrics
- p50/p95/p99 latency to LOCK
- events/sec
- verify-bundle latency
- retries/backtracks distribution
- effect compression ratio
- HITL override rate

---

## 5) Security Testing

### Tamper Suite
Mutation matrix:
- Flip byte in evidence
- Remove evidence file
- Change manifest sha256
- Reorder events
- Alter receipt field
- Swap artifacts order

Expect: specific failure codes

### Concurrency (loom)
- No deadlocks under canonical ordering
- Force release only when allowed
- Deterministic join semantics

---

## 6) Strategy Testing

**Rules:**
- `suggest(signals)` is pure, deterministic
- Suggestions sorted by `(match_permille, strategy_id)`
- Explanations stable and hashable

**Tests:**
- Golden: fixed signals → expected suggestions
- Property: irrelevant signals don't change score
- Scenario: strategy applied → receipt records it

---

## 7) Implementation Checklist

1. Build `verify_bundle()` first (oracle)
2. Build golden bundle fixtures (3-5)
3. Add `ScenarioRunner` with SimRuntime
4. Add property tests (tamper, determinism)
5. Add microbench and macrobench
6. Wire CI pipeline

---

## 8) CI Pipeline

1. Lint/format: `cargo fmt`, `cargo clippy`
2. Unit + property: `cargo test -p workc_core`
3. Integration: `cargo test -p workc_runtime`
4. Scenarios: `cargo test -p workc_scenarios`
5. Golden bundles: verify all fixtures
6. (Optional) Loom: nightly toolchain

**Outputs:**
- `test_report.json`
- `bench_report.json`
- Proof digests for scenario outputs

---

## 9) Quality Benchmarks

Beyond speed:
- **Validity rate**: % runs producing PASS bundles
- **Backtrack rate**: per run
- **Retry rate**: per run
- **Verification strength**: coverage score
- **Effect compression expansion**: scope growth
- **HITL meaningfulness**: override rate
- **Cross-agent trust readiness**: % with full integrity

All computed deterministically from receipts.
