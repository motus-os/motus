# Codex Handoff: Homepage Benchmark Environment

**Date**: 2026-01-06
**From**: Opus (website review)
**To**: Codex (implementation review)
**Status**: Ready for review

---

## Context

We're redesigning the Motus homepage to **show, not claim**. The current homepage says "95% fewer tokens" but this claim:
1. Uses char/4 approximation, not a real tokenizer
2. Is based on n=16 samples
3. Isn't in our proof ledger
4. Fails our own content standards

### The Insight

Instead of claiming "95% fewer tokens", we show actual side-by-side logs of an agent task:
- **Left**: Without Motus (raw context passing)
- **Right**: With Motus (receipt-based compression)
- **Bottom**: Real token counts (tiktoken)
- **User does the math**

This creates the "oh shit" moment while being completely defensible.

---

## Proposed Solution

A Docker-based benchmark environment that:
1. Runs the same agent task two ways (with/without Motus)
2. Captures actual logs from both approaches
3. Measures real token counts
4. Outputs artifacts suitable for homepage embed
5. Is reproducible by anyone (`docker run motus/benchmark`)

---

## Technical Requirements

### Directory Structure

```
packages/website/benchmark/
├── Dockerfile
├── docker-compose.yml
├── README.md                    # How to run, methodology
├── task/
│   └── source-files/            # Files the agent will read
│       ├── models/
│       │   └── task.py          # ~200 line SQLAlchemy model
│       └── api/
│           └── tasks.py         # ~150 line FastAPI endpoints
├── agents/
│   ├── without-motus/
│   │   ├── agent.py             # Naive agent, passes full context
│   │   └── config.yaml
│   └── with-motus/
│       ├── agent.py             # Motus-enabled agent
│       └── config.yaml
├── measure.py                   # Token counter using tiktoken
├── run-benchmark.sh             # Orchestrates both runs
└── output/
    ├── without-motus.jsonl      # Raw event log
    ├── with-motus.jsonl         # Raw event log
    ├── report.json              # Comparison metrics
    └── embed/
        ├── left-panel.html      # For homepage embed
        └── right-panel.html
```

### The Benchmark Task

**Scenario**: Multi-agent handoff for building integration tests

1. **Agent 1** reads `models/task.py` (data model)
2. **Agent 1** produces output (full file OR receipt)
3. **Agent 2** receives Agent 1's output
4. **Agent 2** reads `api/tasks.py` (API endpoints)
5. **Agent 2** produces output for Agent 3
6. **Agent 3** receives cumulative context
7. **Agent 3** writes integration test plan

**Measurement Point**: What does Agent 3 receive as context?

### Without Motus Behavior

```python
# Agent passes full context
context = {
    "previous_agent_output": full_file_contents,  # 200 lines
    "conversation_history": [...],                 # grows each turn
    "current_file": full_api_contents,            # 150 lines
}
# Token count: O(n) growth with each handoff
```

### With Motus Behavior

```python
# Agent creates receipt
receipt = {
    "id": "rx_001",
    "outcome": "Task model with UUID pk, status enum, soft delete",
    "evidence": ["4 methods", "SQLAlchemy Base", "Alembic ready"],
    "decisions": ["UUID for distributed", "deleted_at pattern"],
    "files_touched": ["src/models/task.py"],
}
# Next agent receives receipt, not raw content
# Token count: O(1) - receipts stay flat
```

### Token Measurement

Must use real tokenizer, not char/4:

```python
import tiktoken

def count_tokens(text: str, model: str = "gpt-4") -> int:
    enc = tiktoken.encoding_for_model(model)
    return len(enc.encode(text))
```

### Output Format

`report.json`:
```json
{
  "benchmark_id": "task-model-api-tests-v1",
  "run_date": "2026-01-06T14:30:00Z",
  "commit_sha": "abc123",
  "task_description": "3-agent handoff: model → API → tests",
  "results": {
    "without_motus": {
      "agent_1_output_tokens": 847,
      "agent_2_output_tokens": 1623,
      "agent_3_input_tokens": 2847,
      "total_tokens": 5317
    },
    "with_motus": {
      "agent_1_output_tokens": 43,
      "agent_2_output_tokens": 51,
      "agent_3_input_tokens": 147,
      "total_tokens": 241
    },
    "reduction_percent": 95.5,
    "methodology": "tiktoken gpt-4 encoding"
  },
  "reproduce": "docker run motus/benchmark"
}
```

---

## Success Criteria

### Must Have
- [ ] Reproducible: `docker run` produces same results
- [ ] Real tokens: Uses tiktoken, not char/4
- [ ] Actual agents: Not simulated, real code execution
- [ ] Defensible: Methodology documented, anyone can verify
- [ ] Embeddable: Output suitable for homepage component

### Should Have
- [ ] Multiple task scenarios (not just one)
- [ ] Confidence intervals (run N times)
- [ ] Comparison across different models (GPT-4, Claude, etc.)

### Nice to Have
- [ ] Live demo mode (run in browser via WebContainer?)
- [ ] CI integration (benchmark runs on every PR)

---

## Integration with Content Standards

Once benchmark is verified, we need to:

1. **Add to proof ledger** (`standards/proof-ledger.json`):
```json
{
  "id": "claim-token-reduction",
  "claim": "95% fewer tokens in multi-agent handoffs",
  "status": "verified",
  "evidence_path": "docs/proof/token-reduction/",
  "methodology": "tiktoken measurement, 3-agent task, N=100 runs",
  "last_verified": "2026-01-06",
  "commit_sha": "abc123"
}
```

2. **Create evidence bundle** (`docs/proof/token-reduction/`):
```
methodology.md      # How we measured
results.json        # Raw data
reproduce.sh        # One-command verification
manifest.json       # File checksums
```

3. **Update homepage** to embed actual logs, not synthetic examples

---

## Open Questions for Codex

1. **Agent Implementation**: Should we use a real LLM call or mock it?
   - Real: More authentic, but costs money and adds variance
   - Mock: Deterministic, free, but less "real"
   - Recommendation: Mock with recorded LLM responses (golden fixtures)

2. **Source Files**: Use the existing Task model example or create new?
   - Existing: Consistent with current homepage
   - New: Could be more representative
   - Recommendation: Keep Task model, it's relatable

3. **Motus Version**: Pin to specific version or use latest?
   - Pinned: Reproducible
   - Latest: Shows current capability
   - Recommendation: Pin in Dockerfile, document version

4. **Token Model**: Which tokenizer model?
   - gpt-4: Most common
   - cl100k_base: Claude-compatible
   - Recommendation: Run both, report both

5. **Statistical Rigor**: How many runs for confidence?
   - Single run: Simple but not rigorous
   - N=100: Statistical significance
   - Recommendation: N=100, report mean and 95% CI

6. **Homepage Integration**: Static embed or live component?
   - Static: Faster to ship, pre-rendered
   - Live: More impressive, more complex
   - Recommendation: Static first, live later

---

## Reference Files

- `/packages/website/CONTENT-STANDARD.md` - Writing gates
- `/packages/website/standards/proof-ledger.json` - Claims registry
- `/packages/website/standards/terminology.json` - Approved terms
- `/packages/website/REVIEW-PROCESS.md` - Full review process
- `/packages/website/src/pages/index.astro` - Current homepage

---

## Existing Homepage Code (for context)

The current "Without Motus" panel shows:
```
# Developer pastes context manually
Here's the code from the previous session:
```python
class Task(Base):
    id = Column(UUID, primary_key=True)
    ...
```
# 887 tokens of context
```

The current "With Motus" panel shows:
```
$ motus work context TASK-003
{
  "task": "integration-tests",
  "parent_receipts": ["rx_001", "rx_002"],
  "summary": {...}
}
# 43 tokens • 0.15ms
```

These need to be replaced with actual benchmark output.

---

## Requested Deliverables

1. **Review this proposal** - identify gaps, risks, improvements
2. **Scaffold the benchmark directory** - if approach is sound
3. **Implement measure.py** - token counting utility
4. **Draft Dockerfile** - reproducible environment
5. **Define golden fixtures** - mock LLM responses for determinism

---

## Constraints

- No external API calls in CI (cost, flakiness)
- Must work offline after initial docker pull
- Output must be visually compelling (this is marketing)
- Must satisfy our own CONTENT-STANDARD.md gates

---

## Timeline Consideration

This blocks homepage launch. Current homepage claims are unverified. We either:
1. Remove claims and ship minimal homepage
2. Build benchmark and ship with proof
3. Ship with "preliminary" status and prominent methodology link

Recommendation: Option 2 - build the benchmark. It's the right thing and becomes a product asset (users can run it too).

---

## Sign-off

- [ ] Codex reviewed proposal
- [ ] Architecture approved
- [ ] Implementation started
- [ ] Benchmark passing
- [ ] Proof ledger updated
- [ ] Homepage updated
- [ ] External reviewer sign-off

---

*Generated by Opus during website review session. Handoff created 2026-01-06.*
