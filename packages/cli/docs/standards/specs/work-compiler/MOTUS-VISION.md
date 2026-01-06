# Motus Vision

**Purpose**: Define what Motus is for the website builder agent.
**Audience**: Marketing/website team, not engineers.
**Read time**: 3 minutes

---

## The One-Liner

> **"Models are powerful. Motus makes them capable."**

---

## The Problem (Pain)

AI coding agents break things:

| What Happens | Real Quote |
|--------------|------------|
| Touch files you didn't ask | "The agent 'helped' by rewriting critical paths I had not asked it to touch." |
| Lose context mid-task | "After 2-3 context compactions, Claude prioritizes context preservation over correctness." |
| Hallucinate paths and functions | "The AI invents functions that look completely legitimate but don't exist." |
| Cause production disasters | "I destroyed months of your work in seconds." |

**The numbers**:
- 66% of developers spend more time fixing AI code than they saved
- 16 of 18 CTOs report production disasters from AI coding
- 92% of security leaders are concerned about AI code oversight

**Users are burned. They don't trust agents.**

---

## The Solution (Concrete)

Motus gives you three things:

### 1. SCOPE
Define what files and resources the agent can read.
- No more "reading the entire codebase"
- No more context pollution from irrelevant files
- Agent sees only what it needs

### 2. BLOCK
Prevent the agent from touching files outside its scope.
- No more "mystery edits at 2am"
- No more "slipped into the diff" surprises
- Agent works within explicit boundaries

### 3. TRACE
Get a complete, auditable log of what the agent did and why.
- Every file read, logged
- Every file touched, logged
- Every decision, recorded
- Immutable receipts you own (not a vendor's cloud)

---

## The Reframe (Why This Works)

**Motus is the GPU for AI agents.**

| GPU | Motus |
|-----|-------|
| Doesn't make CPUs smarter | Doesn't make models smarter |
| Makes parallel compute *possible* | Makes complex agent work *completable* |
| Handles a specific workload | Handles execution so models can think |
| Infrastructure, not restriction | Infrastructure, not restriction |

The model is the CPU. Motus is the GPU.

**This is not about limiting agents. It's about making them capable of real work.**

---

## The Differentiators

### 1. Open Source
- Claude, Cursor, Copilot have built-in scoping. It's closed.
- Motus is open source. You can see, audit, and trust it.
- Your receipts are YOUR data. Local by default.

### 2. Accumulated Wisdom (Expanding)
- Fresh agents start from zero every session.
- Motus is building a library of expert strategies (Root Cause Loop, Progressive Disclosure, etc.)
- **MVP**: 2-3 core strategies built in.
- **v1.0+**: Community-contributed strategies. Not a vendor lock-in.

### 3. Execution Infrastructure
- Competitors offer documentation (rules, guidelines).
- Motus offers enforcement (actual blocking, actual logging).
- Agents ignore docs when context gets polluted. They can't ignore Motus.

---

## What Exists Today

| Component | Status | What It Does |
|-----------|--------|--------------|
| Coordination API | ✅ Built | Prevents agent collisions on shared files |
| Lens Assembly | ✅ Built | Compiles grounded context (real files, not hallucinated) |
| Policy Gates | ✅ Built | Enforces rules before/after actions |
| Work Receipts | 🔶 Partial | Logs what agents did (expanding to full audit trail) |
| Work Compiler | 📋 Spec | The core execution engine (coming soon) |
| Strategy Library | 📋 Spec | Accumulated wisdom (coming soon) |

---

## What's Coming (Roadmap Summary)

**MVP (Months)**:
- Single-level execution with full receipts
- 2-3 core strategies (Root Cause Loop, Progressive Disclosure)
- Local SQLite storage with export
- Risk-based verification

**v1.0 (Quarters)**:
- Recursive execution (complex work decomposition)
- Full strategy library (9+ strategies)
- Advanced verification
- Optional cloud sync for teams

---

## The Hero (For Website)

**Headline**: "Stop agents from breaking production."

**Subhead**: "Scope what they read. Block what they touch. Trace what happened."

**Supporting**: "Open source execution infrastructure for AI agents."

**CTA**: "Help build the open standard."

---

## The Dual Hooks

**For burned users (hero)**: Pain-first
> "Your agent edited 47 files. You asked for 3."

**For proactive users (features)**: Aspiration
> "Ship faster with AI agents you can trust."

---

## What Motus Is NOT

- ❌ Not a prompt engineering tool
- ❌ Not a model provider
- ❌ Not a code review tool
- ❌ Not just documentation/rules (it's enforcement)
- ❌ Not closed source / vendor lock-in

---

## The Trust Message

> "Built by developers who've been burned. Open source so you can verify every claim. Your data stays yours."

---

## Get Started (Coming Soon)

```bash
pip install motusos
motus init
motus scope ./src --allow-read
motus run "Refactor the auth module"
# → Agent works within scope
# → You get receipts of everything it did
```

**Status**: CLI coming with MVP. [Request early access →]

---

## Compatibility

**Works with**:
- Claude Code (primary target)
- Any agent that can be configured to use Motus coordination

**Coming soon**:
- Cursor integration
- GitHub Copilot integration
- VS Code extension

**Limitations**:
- Requires agent to respect Motus coordination (can't retrofit closed agents)
- Scoping is file-level, not line-level (MVP)
- Single-level execution in MVP (no recursive decomposition yet)

---

## Summary for Website Agent

**What is Motus?**
Execution infrastructure for AI agents. The GPU for agent work.

**What does it do?**
Scope. Block. Trace. Makes agents capable of finishing complex work reliably.

**Why is it different?**
Open source. Accumulated wisdom. Enforcement, not just documentation.

**Who is it for?**
Developers using AI coding agents who want reliability without babysitting.

**What's the emotional hook?**
Pain recognition ("we know agents break things") → Solution ("here's how to fix it") → Trust ("open source, you own your data").
