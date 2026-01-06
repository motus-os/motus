# Motus Roadmap (Rebaselined 2025-12-24)

**Purpose**: Implementation roadmap for full Motus system
**Status**: Waiting on GPT Pro Round 2 (human-side specs)

---

## The Two-Gap Model

Motus fills two gaps between machines and humans:

```
Computer ←— Motus (precision) —→ LLM ←— Motus (wisdom) —→ Human
```

**Computer-side (MOTUS-SPEC-V0.1 - COMPLETE)**:
- Determinism (CJ-0.1)
- Verification (PROOF-0.1)
- Transitions (FSM-0.1)
- Effects (ENF-0.1)
- Proofs and receipts

**Human-side (MOTUS-HUMAN-SPEC-V0.1 - PENDING)**:
- Empathy (EMPATHY-0.1)
- Perspective (PERSPECTIVE-0.1)
- Truth (TRUTH-0.1)
- Purpose (PURPOSE-0.1)
- Humility (HUMILITY-0.1)
- Fitness (FITNESS-0.1)

> "LLMs are powerful but ungrounded. Motus gives them the precision of computers and the wisdom of humans."

---

## Strategic Context

**No MVP. Full system.**

With AI-assisted development and rigorous specs, we build the complete Work Compiler in ~4 weeks, not an artificial subset.

**The math is done. The spec is (almost) complete. The only question is build order.**

---

## What We Have

| Artifact | Status | Location |
|----------|--------|----------|
| Strategic positioning | Complete | MOTUS-VISION.md |
| Work Compiler design | Complete | MOTUS-COMPLETE-SYNTHESIS.md |
| Steering committee decisions | Locked | MOTUS-ROADMAP.md (this doc) |
| Rust kernel spec | Complete | MOTUS-SPEC-V0.1.md |
| Testing framework spec | Complete | MOTUS-TESTING-FRAMEWORK-SPEC.md |
| Golden bundles | Complete | 7 fixtures delivered |
| Licensing strategy | Complete | MOTUS-LICENSING-STRATEGY.md |
| Human-side specs | **Pending** | GPT Pro Round 2 |

---

## Locked Decisions (Steering Committee)

| Decision | Choice |
|----------|--------|
| Core paradigm | OODA internally, simple labels externally |
| Verification default | Syntactic + Semantic always, Acceptance on artifact changes |
| Human-in-the-loop | Risk-based (EVI model), configurable |
| Receipt storage | Local SQLite + JSONL export |
| Implicit guidance | Allow for low-stakes with logging |
| Open/paid boundary | Core open, services paid |
| Implementation language | Rust (workc_core, workc_runtime, workc_cli) |

---

## Build Order (Proof-First)

### Week 1: Foundation (Verifier First)

The verifier is the oracle. Build it first, then validate everything else against it.

```
Day 1-2: Canonicalization + Hashing
├── CJ-0.1 canonicalization (byte-level)
├── Hash256 helpers
├── Unit tests: same JSON → identical bytes
└── Cross-platform determinism test

Day 2-3: Event Chain + Merkle Roots
├── Event hash chain (h(i) formula)
├── Merkle root construction (odd leaf handling)
├── All 8 roots: event_log, artifacts, evidence, lens, effects, gates, verification, workgraph
└── Property tests: tamper detection, reorder detection

Day 3-4: Proof Digest + Receipt Projection
├── Proof digest computation (PROOF-0.1)
├── Receipt projection from events
├── IntegrityBlock construction
└── Unit tests: digest changes when anything changes

Day 4-5: verify_bundle CLI
├── All validation steps in order
├── Stable failure codes (HASH_MISMATCH, etc.)
├── Structured Verdict output
├── Golden bundle fixtures (7 from GPT Pro)
└── Golden tests: verify_bundle == PASS, digest matches
```

**Week 1 Exit Criteria**: `workc verify-bundle` works on all 7 golden fixtures.

---

### Week 2: Execution (FSM + Adapters)

```
Day 1-2: FSM Runner
├── LoopState initialization
├── Phase execution (Observe → Lock)
├── Transition algebra (Next, Repeat, Backtrack, Spawn, Escalate, Halt, Complete)
├── NEXT transition function
└── FSM replay validator

Day 2-3: SimRuntime + ScenarioRunner
├── FakeClock, SeededRng
├── In-memory stores (evidence, artifacts)
├── Script types (LensScript, PlanScript, etc.)
├── ScenarioRunner produces bundles
└── All scenarios pass verify_bundle

Day 3-4: Motus Adapters
├── Lens adapter + lens_root + LensQuality scoring
├── Skills adapter + effects_root + ENF-0.1 normalization
├── Gates adapter + gates_root + policy_hash
├── Coordination adapter (6-call API wrapper)
└── Integration tests

Day 4-5: Core Scenarios
├── suite_core (10 workmark scenarios)
├── Happy path, verify backtrack, parallel children
├── Effect compression, HITL checkpoint, strategy applied
├── Tiered recovery, implicit decide
└── All scenarios PASS
```

**Week 2 Exit Criteria**: FSM runs scenarios end-to-end, all verify_bundle PASS.

---

### Week 3: Intelligence (Strategies + Human-Side)

```
Day 1-2: Strategy Engine
├── Strategy data model (YAML/JSON)
├── Trigger DSL evaluation
├── Deterministic suggestion algorithm
├── Match score calculation + tie-breaking
├── Explanation generation
└── Strategy tests: fixed signals → expected suggestions

Day 2-3: Recursion + Work Graph
├── Child loop spawning (sequential, parallel)
├── Join semantics (parent waits)
├── workgraph_root construction
├── Rollup algorithm (critical vs non-critical)
└── suite_parallel scenarios

Day 3-4: HITL + Risk + Human-Side Integration
├── EVI calculation (p(override) × L(loss) > C(cost))
├── Risk scoring (monotone function)
├── Checkpoint policy evaluation
├── HITL tests: correct prompts at correct times
├── Human-side pre-flight checks (EMPATHY, PURPOSE, HUMILITY)
├── Human-side verification tiers (TRUTH, PERSPECTIVE, FITNESS)
└── Fatigue calibration defaults

Day 4-5: Tamper Suite + Benchmarks
├── TamperMutator (all mutation types)
├── Tamper test matrix (flip, delete, reorder, corrupt)
├── Microbench (criterion)
├── Macrobench (suite runner)
├── bench_report.json generation
└── CI pipeline wiring
```

**Week 3 Exit Criteria**: Full strategy engine, recursion, HITL, human-side specs, all tests pass.

---

### Week 4: Ship

```
Day 1-2: CLI Polish
├── workc run "intent"
├── workc verify-bundle <path>
├── workc explain <bundle>
├── workc receipt <loop_id>
├── workc bench <suite>
├── workc schema test-report / bench-report
└── CLI tests

Day 2-3: Documentation + Licensing
├── README.md
├── MOTUS-SPEC-V0.1.md (computer-side)
├── MOTUS-HUMAN-SPEC-V0.1.md (human-side)
├── Architecture diagrams
├── Getting started guide
├── API reference
├── MFUL-0.1 license text (Motus Fair Use License)
├── License headers on all spec files
└── Publish specs to motusos.ai/docs/

Day 3-4: Website Update
├── New messaging (GPU analogy + two-gap model)
├── SCOPE. BLOCK. TRACE.
├── Open source positioning
├── Getting started teaser
└── Roadmap page

Day 4-5: Launch
├── Final test pass (all suites)
├── Final benchmark baseline
├── Git tag v0.1.0
├── Announcement
└── Monitor feedback
```

**Week 4 Exit Criteria**: Motus v0.1.0 shipped.

---

## Pending from GPT Pro

### Delivered (Round 1)
- `MOTUS-SPEC-V0.1.md` - Complete computer-side specification
- `MOTUS-GOLDEN-BUNDLES-V0.1.zip` - 7 test fixtures

### Requested (Round 2)
`MOTUS-HUMAN-SPEC-V0.1.md` containing:
- EMPATHY-0.1: User understanding verification
- PERSPECTIVE-0.1: Multi-viewpoint verification
- TRUTH-0.1: Grounding verification
- PURPOSE-0.1: Meaningful work verification
- HUMILITY-0.1: Limitation acknowledgment
- FITNESS-0.1: Fit-for-purpose verification

### Follow-up Request
`suite_core` - 10 concrete Scenario instances (if not already in progress)

---

## Success Criteria

| Metric | Target |
|--------|--------|
| All unit tests | PASS |
| All property tests | PASS |
| All golden bundles | verify_bundle == PASS |
| All suite_core scenarios | PASS |
| Tamper suite | Correct failure codes |
| Cross-platform | Linux + macOS + Windows |
| Benchmarks | Baselines established |
| Human-side checks | Integrated with verification tiers |

---

## Risk Mitigations

| Risk | Mitigation |
|------|------------|
| Spec ambiguity | GPT Pro consolidated specs eliminate ambiguity |
| Determinism bugs | Cross-platform CI, property tests |
| Integration issues | Proof-first build order catches issues early |
| Scope creep | Build order is dependency-driven, not feature-driven |
| Human-side vagueness | Algorithm specs with scoring formulas |

---

## What Happens After v0.1.0

| Feature | When |
|---------|------|
| WorkLang (declarative work programs) | v0.2 |
| Cloud sync (optional team receipts) | v0.2 |
| Advanced verification (Adversarial) | v0.2 |
| Cryptographic signatures (Ed25519) | v0.2 |
| VS Code extension | v0.3 |
| Cursor integration | v0.3 |
| Community strategy contributions | v0.3+ |

---

## Current Status

**Waiting on GPT Pro Round 2.**

When `MOTUS-HUMAN-SPEC-V0.1.md` arrives:
1. Review for completeness
2. Integrate with MOTUS-SPEC-V0.1.md
3. Update roadmap Week 3 details
4. Begin Week 1 implementation

---

*Rebaselined 2025-12-24. Full system, not MVP. 4 weeks to ship. Two gaps to fill.*
