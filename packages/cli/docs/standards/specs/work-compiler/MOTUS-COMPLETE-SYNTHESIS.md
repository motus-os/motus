# Motus Complete Synthesis

**Date**: 2025-12-24
**Purpose**: Single source of truth capturing all strategic and technical decisions
**Status**: Ready for implementation

---

## Part 1: What Is Motus?

### The One-Liner
> **"Models are powerful. Motus makes them capable."**

### The Problem
AI coding agents break things:
- Touch files you didn't ask them to touch
- Lose context mid-task (after 2-3 compactions)
- Hallucinate paths and functions that look legitimate
- Cause production disasters ("I destroyed months of work in seconds")

**The numbers**:
- 66% of developers spend more time fixing AI code than they saved
- 16 of 18 CTOs report production disasters from AI coding
- 92% of security leaders are concerned about AI code oversight

### The Solution
Motus gives you three things:

| Capability | What It Does |
|------------|--------------|
| **SCOPE** | Define what files/resources the agent can read |
| **BLOCK** | Prevent touching files outside scope |
| **TRACE** | Complete, auditable log of what the agent did |

### The Reframe: GPU Analogy
**Motus is the GPU for AI agents.**

| GPU | Motus |
|-----|-------|
| Doesn't make CPUs smarter | Doesn't make models smarter |
| Makes parallel compute *possible* | Makes complex agent work *completable* |
| Handles a specific workload | Handles execution so models can think |
| Infrastructure, not restriction | Infrastructure, not restriction |

**The model is the CPU. Motus is the GPU.**

This is not about limiting agents. It's about making them capable of real work.

---

## Part 2: Strategic Positioning (NVIDIA Playbook)

### The Moat Analysis

NVIDIA's moat isn't hardware - it's:
1. **CUDA** - The paradigm (developers think in CUDA)
2. **cuDNN** - Pre-built intelligence (why rebuild what experts optimized?)
3. **Ecosystem** - Network effects (if you do ML, you use NVIDIA)

**Applied to Motus**:
| NVIDIA | Motus |
|--------|-------|
| CUDA (paradigm) | Work Compiler (OODA execution model) |
| cuDNN (libraries) | Strategy Library (accumulated wisdom) |
| Hardware | Execution Engine (coordination, lens, gates) |

### The Moat Is Not The Engine

The execution engine (coordination API, policy gates, lens assembly) is commoditizable.

**The moat is**:
1. **The Work Compiler paradigm** - Developers who internalize "OBSERVE → ORIENT → DECIDE → ACT → VERIFY → LOCK" will think in Motus
2. **The Strategy Library** - Pre-built expert strategies (Root Cause Loop, Progressive Disclosure, Devil's Advocate) that accumulate wisdom
3. **Developer mindshare** - "If you do agent work, you use Motus"

### Business Model Resolution

**Tension**: Boyd wanted OODA open. Feels wrong to monetize his framework.

**Resolution**: Open core honors Boyd. Services fund development.

| Tier | What's Included | Why |
|------|-----------------|-----|
| **Open Source** | Work Compiler, Strategy Library core, CLI | Boyd's framework stays free |
| **Paid Services** | Hosting, team sync, compliance features | Infrastructure has a cost |
| **Enterprise** | Audit dashboards, SLA, support | Enterprises pay for peace of mind |

**Principle**: "The idea stays free. The infrastructure has a cost."

---

## Part 3: The Work Compiler

### Philosophy: Why OODA?

John Boyd's OODA loop is the most validated decision-action framework:
- Developed for fighter pilots (millisecond decisions)
- Adopted by Marines, DARPA, business strategists
- Battle-tested across domains for 40+ years

**Key insight from Boyd**: Orient is the schwerpunkt (center of gravity). Understanding happens in Orient, not Observe. Observe gathers signals. Orient makes meaning.

### The Algorithm

```
OBSERVE → ORIENT → DECIDE → ACT → VERIFY → LOCK
   ↑                                        |
   └────────── feedback loop ───────────────┘
```

### Six Phases

| Phase | Input | Output | Key Insight |
|-------|-------|--------|-------------|
| **OBSERVE** | Intent, Lens | Signals | Gather, don't interpret |
| **ORIENT** | Signals | Meaning | This is where understanding happens |
| **DECIDE** | Meaning, Strategies | Plan | Select, don't execute |
| **ACT** | Plan | Artifacts | Bounded execution only |
| **VERIFY** | Artifacts, Spec | Results | Independent validation |
| **LOCK** | Results | Receipt | Commit or feedback |

### Transition Algebra

Every phase must return a typed transition:

```typescript
type Transition =
  | { kind: "Next", phase: Phase }
  | { kind: "Repeat", phase: Phase, reason: string }
  | { kind: "Backtrack", phase: Phase, reason: string }
  | { kind: "Spawn", childIntents: Intent[], mode: "sequential"|"parallel" }
  | { kind: "EscalateToParent", error: ErrorRecord }
  | { kind: "Halt", reason: string, requiresHuman: true }
  | { kind: "Complete", outcome: Outcome };
```

### Transition Policy Rules

| Condition | Transition |
|-----------|------------|
| OBSERVE insufficient signals | Repeat(OBSERVE) or Escalate |
| VERIFY failed (missing context) | Backtrack(ORIENT) |
| VERIFY failed (bad signals) | Backtrack(OBSERVE) |
| ACT error (recoverable) | Repeat(ACT) |
| ACT error (unrecoverable) | EscalateToParent |
| ACT error (catastrophic) | Halt(requiresHuman: true) |
| Budget exceeded | Halt |
| All phases pass | Complete |

### LoopState (Typed Contract)

```typescript
type LoopState = {
  loopId: string;
  parentLoopId: string | null;
  phase: Phase;
  intent: Intent;
  lensId: string | null;
  signals: Signal[];
  meaning: Meaning | null;
  plan: Plan | null;
  verificationSpec: VerificationSpec;
  verificationResults: CheckResult[];
  artifactsIn: ArtifactRef[];
  artifactsOut: ArtifactRef[];
  decisions: Decision[];
  strategySuggestions: StrategySuggestion[];
  strategyUsed: string | null;
  childLoopIds: string[];
  errors: ErrorRecord[];
  counters: { retries: number; stuckMs: number; steps: number; ... };
  lockLevel: "Draft" | "Staged" | "Committed" | "Published" | "Immutable";
  budgets: { maxSteps: number; maxWallMs: number; maxDepth: number; maxFanout: number };
  startTimeUtc: string;
};
```

---

## Part 4: Strategy Library

### The 9 Strategies

| ID | Name | Trigger Signal | What It Does |
|----|------|----------------|--------------|
| **001** | Time Travel | Risky exploration | Spawn separate session, discard if bad |
| **002** | Parallel Spike | Multiple valid approaches | Try N approaches, pick winner |
| **003** | Devil's Advocate | High-stakes decision | Force counter-arguments before commit |
| **004** | Progressive Disclosure | Scope unclear | Expand scope incrementally |
| **005** | Breadcrumb Trail | Work spans sessions | Leave explicit waypoints for resumption |
| **006** | Rubber Duck | Stuck on problem | Explain to inanimate object |
| **007** | Integration Pause | Emotional tangent | Separate insight from execution |
| **008** | Root Cause Loop | Verification failed | Keep asking "why" until root cause |
| **009** | Agent Council | Multi-perspective needed | Spawn async agents with distinct roles |

### Strategy Trigger DSL (To Be Defined)

```yaml
triggers:
  - signal: verification_failed_twice
    confidence_threshold: 0.9
    suggest: STRAT-008  # Root Cause Loop

  - signal: high_stakes_decision
    confidence_threshold: 0.8
    suggest: STRAT-003  # Devil's Advocate
```

### MVP Strategies (2-3 only)

1. **Root Cause Loop** (STRAT-008) - Essential for error recovery
2. **Progressive Disclosure** (STRAT-004) - Essential for scope management
3. **Breadcrumb Trail** (STRAT-005) - Essential for session continuity

---

## Part 5: Proof System (GPT Pro's Contribution)

### The Proof Digest

```
ProofDigest = SHA256(
    "MOTUS_PROOF_V0.1" ||
    ReceiptHash ||
    EventLogRoot ||
    ArtifactsRoot ||
    EvidenceRoot
)
```

**PASS means**:
- **Tamper-evident**: Hash chain intact
- **FSM-valid**: Transitions followed rules
- **Policy-compliant**: Gates not bypassed
- **Verification passed**: Checks succeeded

### Work Receipt Schema

```typescript
type WorkReceipt = {
  receipt_version: "0.1";
  loop_id: string;
  timestamp_utc: string;
  intent: Intent;
  outcome: Outcome;
  actor: ActorInfo;
  phases: PhaseRecord[];
  artifacts: { in: ArtifactRef[]; out: ArtifactRef[] };
  decisions: Decision[];
  verification: VerificationSummary;
  child_loops: string[];
  parent_loop: string | null;
  proof_digest: string;
};
```

### Evidence Bundle Structure

```
evidence_bundle/
├── manifest.json          # Bundle metadata + Merkle root
├── work_receipt.json      # The receipt
├── event_log.jsonl        # All events (append-only)
├── artifacts/             # Input/output artifacts
│   ├── inputs/
│   └── outputs/
├── verification/          # Check results
│   ├── syntactic.json
│   ├── semantic.json
│   └── acceptance.json
└── signatures/            # Optional cryptographic signatures
```

---

## Part 6: Implementation Architecture (GPT Pro's Spec)

### Rust Crate Structure

```
work_compiler_core/        # Pure kernel (no Motus dependencies)
├── fsm.rs                 # Loop runner, transition logic
├── receipts.rs            # Receipt builder, hashing
├── proofs.rs              # Proof digest, Merkle trees
└── types.rs               # All typed contracts

work_compiler_runtime/     # Motus-specific adapters
├── lens_adapter.rs        # Connect to Lens Assembly
├── skill_adapter.rs       # Connect to Skills
├── gate_adapter.rs        # Connect to Policy Gates
└── coordination.rs        # Multi-agent coordination

work_compiler_strategies/  # Strategy library
├── registry.rs            # Strategy loading
├── triggers.rs            # Trigger DSL evaluation
└── strategies/            # Individual strategy implementations

work_compiler_cli/         # User-facing CLI
├── run.rs                 # motus run "intent"
├── verify.rs              # motus verify-bundle
├── explain.rs             # motus explain <loop_id>
└── receipt.rs             # motus receipt <loop_id>
```

### 13 Algorithms (from GPT Pro)

1. **LoopRunner.run()** - Main FSM execution
2. **NEXT(phase, result)** - Transition function
3. **Observe.execute()** - Signal gathering
4. **Orient.execute()** - Meaning synthesis
5. **Decide.execute()** - Plan selection
6. **Act.execute()** - Bounded execution
7. **Verify.execute()** - Independent validation
8. **Lock.execute()** - Commit or feedback
9. **ReceiptBuilder.build()** - Receipt construction
10. **ProofDigest.compute()** - Hash computation
11. **EventLog.append()** - Append-only logging
12. **StrategyMatcher.match()** - Trigger evaluation
13. **BundleVerifier.verify()** - Bundle integrity check

---

## Part 7: Steering Committee Decisions (Locked)

These decisions were made by the steering committee (Gemini, Codex, Claude, GPT Pro) and are not up for debate:

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Core paradigm** | OODA internally, simple labels externally | Users shouldn't need to "learn OODA" |
| **Strategies in MVP** | 2-3 only | Start minimal, expand with evidence |
| **Verification default** | Syntactic + Semantic always, risk-escalation to Acceptance | Balance speed and safety |
| **Human-in-the-loop** | Risk-based, configurable | Pause before irreversible actions only |
| **Receipt storage** | Local SQLite + JSONL export | Privacy-first, user owns data |
| **Implicit guidance** | Allow for low-stakes with logging | Conservative thresholds |
| **Open/paid boundary** | Core open, services paid | Build community, monetize ops |

---

## Part 8: Updated Roadmap

### MVP Scope ("A+" Tier)

**Timeline direction**: Months (not weeks, not quarters)

#### INCLUDE in MVP

| Feature | Status |
|---------|--------|
| Single-level OODA loop | To build |
| Work receipts (SQLite + JSONL) | To build |
| Automated verification (Syntactic + Semantic) | To build |
| 2-3 strategies (Root Cause Loop, Progressive Disclosure) | To build |
| Error recovery (minimal classification) | To build |
| Coordination API | ✅ Built |
| Lens Assembly | ✅ Built |
| Policy Gates | ✅ Built |

#### DEFER to v1.0

| Feature | Reason |
|---------|--------|
| Recursion (child loops) | Complexity; needs stable single-level first |
| Full strategy library (9+) | Start minimal, expand with evidence |
| Strategy suggestions | Need trigger DSL and evidence |
| Advanced verification (Adversarial) | Overhead; later optimization |
| Cloud receipt sync | Privacy concerns; keep optional |
| Cryptographic sealing | Nice-to-have; hashing is enough for MVP |

### Build Order

```
Phase 1: Event Model + LoopState + Transition Algebra
         └── Enables everything else; must be typed and frozen
         └── Rust: work_compiler_core/types.rs

Phase 2: Loop Runner (FSM)
         └── OBSERVE → ORIENT → DECIDE → ACT → VERIFY → LOCK
         └── Single-level only
         └── Rust: work_compiler_core/fsm.rs

Phase 3: Receipt Engine
         └── Build from event log
         └── SHA256 hashing
         └── Append-only storage
         └── Rust: work_compiler_core/receipts.rs

Phase 4: Verification Harness
         └── BLOCKER: Must define risk classification rules first
         └── BLOCKER: Must define verification spec format first
         └── Rust: work_compiler_runtime/

Phase 5: ACT Integration
         └── Wire to Skills / Gates / Coordination API
         └── Bounded side effects only

Phase 6: Error Recovery
         └── Error classification (recoverable / unrecoverable / catastrophic)
         └── Recovery transitions

Phase 7: Strategy Engine (Minimal)
         └── 2-3 strategies only
         └── Deterministic trigger matching
```

### What Must Be Defined Before Build

| Gap | Priority | When Needed |
|-----|----------|-------------|
| Intent schema | High | Phase 1 |
| Risk classification rules | High | Phase 4 |
| Verification spec format | High | Phase 4 |
| Strategy trigger DSL | Medium | Phase 7 |

### Success Criteria for MVP

| Metric | Target |
|--------|--------|
| Single loop completes | 100% of test cases |
| Receipts generated | Every loop, every time |
| Verification passes | Schema + semantic on all outputs |
| Strategies trigger correctly | > 80% precision on test scenarios |
| Error recovery works | Correct classification on test errors |

---

## Part 9: What Was Discovered Today

### Strategic Insights

1. **GPU analogy reframes everything** - From defensive (restrictions) to enabling (infrastructure)

2. **The moat is the paradigm** - NVIDIA's moat isn't hardware, it's CUDA. Motus's moat isn't the engine, it's the Work Compiler paradigm + Strategy Library

3. **Open core honors Boyd** - The framework stays open, services fund development

4. **Agent Council is powerful** - Multi-agent async deliberation surfaces blind spots (discovered and formalized as STRAT-009)

### Technical Insights

1. **Orient is the schwerpunkt** - Understanding happens in Orient, not Observe. Boyd was clear on this.

2. **Transition algebra is essential** - Without typed transitions, loops become ad-hoc

3. **Proof Digest enables "yep, that's good"** - Mathematical checksum proves tamper-evident + FSM-valid + policy-compliant + verification-passed

4. **Rust is the right choice** - Pure kernel (no runtime dependencies) + adapters for Motus-specific integrations

### Process Insights

1. **Gap between conceptual OODA and Work Compiler** - Using OODA as mental model ≠ executing the Work Compiler algorithm. MVP must make execution accessible.

2. **Strategies that require session spawning need tags** - Time Travel, Agent Council can't be simulated without losing value

3. **Dogfooding reveals gaps** - We used OODA phases narratively but didn't produce typed PhaseResults or event logs

---

## Part 10: Next Steps

### Immediate (This Week)

1. [ ] **Freeze Phase 1 contracts** - LoopState, PhaseResult, Transition types
2. [ ] **Define Intent schema** - Block for Phase 1
3. [ ] **Set up Rust workspace** - work_compiler_core crate structure

### Short-term (Before MVP)

4. [ ] **Build Loop Runner** - Phase 2
5. [ ] **Build Receipt Engine** - Phase 3
6. [ ] **Define risk classification rules** - Block for Phase 4
7. [ ] **Define verification spec format** - Block for Phase 4
8. [ ] **Build Verification Harness** - Phase 4
9. [ ] **Wire ACT to existing Motus** - Phase 5
10. [ ] **Build Error Recovery** - Phase 6
11. [ ] **Build minimal Strategy Engine** - Phase 7 (2-3 strategies)

### Post-MVP

12. [ ] Recursion (child loops)
13. [ ] Full strategy library (9+)
14. [ ] Strategy suggestions
15. [ ] Cloud sync (optional)
16. [ ] Website launch with new messaging

---

## Part 11: Key Documents Reference

| Document | Location | Purpose |
|----------|----------|---------|
| MOTUS-VISION.md | Handoff archive | Website agent handoff |
| MOTUS-ROADMAP.md | Handoff archive | Go-live path |
| MOTUS-COMPLETE-SYNTHESIS.md | Handoff archive | This document |
| WORK-COMPILER-SPEC.md | Handoff archive | Full algorithm spec |
| STRAT-009-AGENT-COUNCIL.yaml | .ai/specs/strategies/ | Agent Council strategy |
| Dogfooding artifacts | .scratch/ | Process audit trail |

---

## Part 12: The Vision Statement

> **Motus is the GPU for AI agents.**
>
> Models are powerful. Motus makes them capable.
>
> We scope what they read. Block what they touch. Trace what happened.
>
> Open source execution infrastructure - so you can trust every claim.
>
> Built by developers who've been burned. Your data stays yours.

---

*Generated 2025-12-24. Steering committee approved. Ready for implementation.*
