# Prompt for GPT Pro

## Task

Produce `MOTUS-SPEC-V0.1.md` - the single implementation contract for Motus Work Compiler.

## Context

You've been helping design Motus - execution infrastructure for AI agents ("the GPU for agents"). We've completed:

1. Strategic alignment (GPU analogy, NVIDIA playbook, open core model)
2. Work Compiler design (recursive OODA + VERIFY + LOCK)
3. Algorithmic specs for all primitives (Lens, Skills, Gates, Coordination)
4. Testing framework
5. Steering committee validation

**We're ready to build the full system, not an MVP.** With AI-assisted development, we can implement the complete spec in ~4 weeks.

## Files Included

| File | What It Contains |
|------|------------------|
| `GPT-PRO-REQUEST-CONSOLIDATED-SPEC.md` | Detailed request with all requirements |
| `MOTUS-COMPLETE-SYNTHESIS.md` | Full strategic + technical synthesis |
| `MOTUS-ROADMAP.md` | Build order + locked decisions |
| `MOTUS-VISION.md` | Product positioning |
| `STRAT-009-AGENT-COUNCIL.yaml` | Example strategy format |
| `TESTING-FRAMEWORK.md` | Test suite specifications |

## Your Deliverable

A single markdown file: `MOTUS-SPEC-V0.1.md`

This must include (see request doc for full details):

### 1. All Type Definitions (Rust)
- Core newtypes, Phase, LockLevel, Transition
- Intent, Outcome, Actor, ArtifactRef
- LoopState, WorkReceipt, IntegrityBlock
- BundleManifest, VerificationSpec
- Strategy types, LensSnapshot, LensQuality
- Effect types (ENF-0.1)
- All trait definitions

### 2. All Algorithms
With input/output types, determinism requirements, edge cases:
1. CJ-0.1 Canonicalization (byte-level)
2. Event Hash Chain
3. Merkle Root construction
4. Proof Digest computation
5. Receipt Projection
6. FSM Runner
7. NEXT Transition Function
8. verify_bundle (all steps)
9. FSM Replay Validator
10. ENF-0.1 Effect Normalization
11. Effect Compression (trie-based)
12. Lens Quality Scoring
13. HITL-EVI Calculation
14. Strategy Matching
15. Work Graph Rollup

### 3. All Merkle Root Formulas
With domain separators:
- event_log_root, artifacts_root, evidence_root
- lens_root, effects_root, gates_root
- verification_root, workgraph_root

### 4. Failure Codes
For verify_bundle:
- HASH_MISMATCH, MERKLE_MISMATCH, EVENT_CHAIN_MISMATCH
- RECEIPT_HASH_MISMATCH, PROOF_DIGEST_MISMATCH
- FSM_ILLEGAL_TRANSITION, POLICY_VIOLATION
- EFFECT_BOUNDS_EXCEEDED, VERIFICATION_INCOMPLETE

### 5. Property-Based Test Specifications
- Tamper Detection
- Event Reorder Detection
- Determinism
- ENF Idempotence
- ENF Compression Bound
- Lens Score Monotonicity
- FSM Legality

### 6. Golden Bundle Specifications
7 bundles with exact expected proof_digest values

### 7. Answers to Q11-Q15
- Q11: Exact trie-based effect compression algorithm
- Q12: Lens freshness piecewise linear (integer arithmetic)
- Q13: Strategy trigger matching algorithm
- Q14: Work graph rollup semantics
- Q15: HITL-EVI calibration defaults

### 8. JSON Schemas
- test_report.json
- bench_report.json

## Format

- Table of contents
- Numbered sections
- Rust code blocks for types/signatures
- Mathematical notation for formulas
- ASCII diagrams where helpful
- Implementation notes in callout blocks

## Success Criteria

An engineer (human or AI) can read `MOTUS-SPEC-V0.1.md` and implement Motus without ambiguity. When the test suite passes, Motus works.

---

**Please produce the complete spec now.**
