# Request: Human-Side Specifications (Round 2)

**To**: GPT Pro
**From**: Motus Steering Committee
**Date**: 2025-12-24
**Context**: MOTUS-SPEC-V0.1.md delivered successfully

---

## The Insight

You said agents "want to be human." We've built that into our thinking:

**Motus fills two gaps:**

```
Computer ←— Motus (precision) —→ LLM ←— Motus (wisdom) —→ Human
```

MOTUS-SPEC-V0.1.md covers the **computer-side** completely:
- Determinism (CJ-0.1)
- Verification (PROOF-0.1)
- Transitions (FSM-0.1)
- Effects (ENF-0.1)
- Proofs and receipts

But we haven't formalized the **human-side**:
- How do we verify the agent understood what was actually needed?
- How do we verify multiple perspectives were considered?
- How do we verify claims are grounded and honest?
- How do we verify the work serves a meaningful goal?
- How do we verify the agent acknowledged its limitations?

These are the "philosophy algorithms" - frameworks that encode human wisdom into verifiable structure.

---

## Request: Formalize Human-Side Specs

Please create specifications for these verification tiers and pre-flight checks, integrated with the Work Compiler (OODA phases, verification tiers, strategies).

### EMPATHY-0.1: User Understanding Verification

**Purpose**: Verify the agent understood what was actually needed, not just what was literally said.

**Questions to answer**:
1. Who will receive this output?
2. What do they already know?
3. What do they need to understand/feel?
4. What might confuse or frustrate them?
5. What would make them trust this?

**Integration points**:
- Pre-flight check in DECIDE phase?
- Verification tier after VERIFY?
- Backtrack trigger if answers are shallow?

**Deliverable**: Algorithm spec with:
- Input/output types
- Scoring function (permille)
- Threshold rules
- Transition decisions

---

### PERSPECTIVE-0.1: Multi-Viewpoint Verification

**Purpose**: Verify multiple perspectives were considered before claiming something is "done."

**Questions to answer**:
1. How would a skeptic view this?
2. How would a novice view this?
3. How would an expert view this?
4. What am I not seeing because I'm too close?

**Integration points**:
- When is Agent Council mandatory vs suggested?
- Minimum perspectives required by lock_level?
- How to score perspective coverage?

**Deliverable**: Algorithm spec with:
- Perspective types and weights
- Coverage scoring (permille)
- When to trigger Agent Council automatically
- Evidence format for perspective checks

---

### TRUTH-0.1: Grounding Verification

**Purpose**: Verify claims are traceable to real sources and honestly represented.

**Questions to answer**:
1. How do I know this? (source)
2. Could I be wrong? (confidence)
3. Is the source reliable? (provenance)
4. Am I representing it accurately? (fidelity)

**Integration points**:
- New verification tier between Semantic and Acceptance?
- Backtrack to OBSERVE if grounding fails?
- Claim types (statistic, quote, path, API, etc.)?

**Deliverable**: Algorithm spec with:
- Claim extraction algorithm
- Source verification algorithm
- Grounding score (permille)
- Failure codes (GROUNDING_VIOLATION, SOURCE_MISSING, etc.)

---

### PURPOSE-0.1: Meaningful Work Verification

**Purpose**: Verify the work serves a meaningful goal, not just completes a task.

**Questions to answer**:
1. Why does this matter?
2. What problem does this solve?
3. Who benefits?
4. What's the cost of getting this wrong?

**Integration points**:
- Required in ORIENT phase?
- Part of intent validation?
- Affects risk scoring?

**Deliverable**: Algorithm spec with:
- Purpose statement requirements
- Validation against Devil's Advocate
- Connection to risk/HITL calculation

---

### HUMILITY-0.1: Limitation Acknowledgment

**Purpose**: Verify the agent acknowledged its limitations and uncertainties.

**Questions to answer**:
1. What might I be missing?
2. What am I uncertain about?
3. Where should a human double-check?
4. What assumptions am I making?

**Integration points**:
- Required disclosures in receipt?
- Affects lock_level eligibility?
- Triggers HITL when uncertainty high?

**Deliverable**: Algorithm spec with:
- Uncertainty quantification (permille)
- Required disclosure fields in receipt
- Threshold for HITL escalation
- Evidence format for assumptions/limitations

---

### FITNESS-0.1: Fit-for-Purpose Verification

**Purpose**: Verify the output is fit for its intended purpose, not just technically correct.

**Questions to answer**:
1. Does this meet the user's actual need (not just stated requirement)?
2. Is this appropriate for the context?
3. Would this work in the real world?
4. Does this match quality exemplars?

**Integration points**:
- New verification tier after Acceptance?
- Reference comparison algorithm?
- Subjective quality scoring?

**Deliverable**: Algorithm spec with:
- Fitness criteria types
- Reference comparison algorithm
- Quality scoring (permille)
- When to require human judgment (FIT_SUBJECTIVE flag)

---

## Integration with MOTUS-SPEC-V0.1

Please specify how these human-side specs integrate with:

1. **Verification tiers** (add Grounding, Fitness?)
2. **Pre-flight checks** (Empathy, Purpose, Humility in DECIDE?)
3. **Transition rules** (new backtrack conditions)
4. **Receipt fields** (new evidence/disclosure sections)
5. **verify_bundle** (new failure codes)
6. **Strategies** (when to suggest Agent Council, Devil's Advocate)

---

## Format

Please deliver as `MOTUS-HUMAN-SPEC-V0.1.md` with:

1. Each spec as a numbered section (matching MOTUS-SPEC-V0.1 style)
2. Rust type definitions
3. Algorithm pseudocode + signatures
4. Scoring formulas (integer-only, permille)
5. Integration points with existing spec
6. New failure codes
7. Example scenarios (like golden bundles but for human-side checks)

---

## The Vision

When complete, Motus will give agents:

**From computers**: Determinism, proofs, verification, receipts
**From humans**: Empathy, perspective, truth, purpose, humility

> "LLMs are powerful but ungrounded. Motus gives them the precision of computers and the wisdom of humans."

---

**Please produce MOTUS-HUMAN-SPEC-V0.1.md.**
