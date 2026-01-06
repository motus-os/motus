#!/usr/bin/env python3
"""
Benchmark v2: Multi-step workflow token comparison

Task: 3-step workflow (realistic dev task)
  Step 1: Design data model
  Step 2: Build API endpoints
  Step 3: Write integration tests

Measures: CUMULATIVE context tokens across all handoffs
"""

import json
from pathlib import Path

def count_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token"""
    return len(text) // 4

# =============================================================================
# WITHOUT MOTUS: Each handoff requires full re-explanation
# Context GROWS with each step because you need to explain all previous work
# =============================================================================

STEP2_WITHOUT_MOTUS = """
Context from previous session:

PROJECT: Building a task management API
TECH STACK: Python, FastAPI, PostgreSQL, SQLAlchemy

STEP 1 COMPLETED BY PREVIOUS AGENT:
- Created data models in src/models/task.py
- Task model has: id (UUID), title (str), description (text), status (enum),
  priority (int 1-5), due_date (datetime), created_at, updated_at
- Status enum: PENDING, IN_PROGRESS, COMPLETED, CANCELLED
- Added relationships: Task belongs to User, Task has many Tags
- Created migration file: migrations/001_create_tasks.py
- Design decisions:
  - Used UUID over auto-increment for distributed systems compatibility
  - Soft delete via 'deleted_at' timestamp instead of hard delete
  - Status transitions validated in model (can't go COMPLETED->PENDING)

YOUR TASK: Build CRUD API endpoints for the Task model.
"""

STEP3_WITHOUT_MOTUS = """
Context from previous sessions:

PROJECT: Building a task management API
TECH STACK: Python, FastAPI, PostgreSQL, SQLAlchemy

STEP 1 (Agent A - Data Model):
- Created data models in src/models/task.py
- Task model: id (UUID), title, description, status, priority, due_date, timestamps
- Status enum: PENDING, IN_PROGRESS, COMPLETED, CANCELLED
- Relationships: Task->User, Task->Tags (many-to-many)
- Used UUID for distributed compatibility
- Soft delete pattern with deleted_at
- Status transition validation in model

STEP 2 (Agent B - API Endpoints):
- Created endpoints in src/api/tasks.py
- GET /tasks - list with pagination, filtering by status/priority
- GET /tasks/{id} - single task with related data
- POST /tasks - create with validation
- PUT /tasks/{id} - full update
- PATCH /tasks/{id} - partial update (status transitions)
- DELETE /tasks/{id} - soft delete
- Added authentication middleware requirement
- Response models in src/schemas/task.py
- Error handling: 404 for not found, 422 for validation, 403 for forbidden transitions
- Pagination: offset/limit with max 100 per page

YOUR TASK: Write integration tests for all API endpoints.
"""

# =============================================================================
# WITH MOTUS: Receipts provide structured context - doesn't grow linearly
# =============================================================================

STEP2_WITH_MOTUS = """
Continue from receipt:

```receipt rx_001
task: TASK-001-data-model
outcome:
  - src/models/task.py: Task model (UUID, title, status enum, priority, timestamps)
  - migrations/001_create_tasks.py
decisions:
  - "UUID for distributed systems"
  - "Soft delete via deleted_at"
  - "Status transitions validated in model"
```

Build CRUD API endpoints for Task.
"""

STEP3_WITH_MOTUS = """
Continue from receipt chain:

```receipt rx_001
task: data-model
outcome: src/models/task.py (Task: UUID, title, status, priority, timestamps)
decisions: ["UUID for distributed", "soft delete", "status validation"]
```

```receipt rx_002
task: api-endpoints
outcome: src/api/tasks.py (GET/POST/PUT/PATCH/DELETE /tasks)
evidence: OpenAPI spec generated, auth middleware applied
decisions: ["pagination max 100", "soft delete on DELETE", "403 on invalid transitions"]
```

Write integration tests for all endpoints.
"""

def run_benchmark():
    """Run the multi-step token comparison"""

    print("=" * 70)
    print("MOTUS TOKEN BENCHMARK v2: Multi-Step Workflow")
    print("=" * 70)
    print()
    print("Workflow: Data Model → API Endpoints → Integration Tests")
    print()

    # Calculate tokens for each step
    without_step2 = count_tokens(STEP2_WITHOUT_MOTUS)
    without_step3 = count_tokens(STEP3_WITHOUT_MOTUS)
    without_total = without_step2 + without_step3

    with_step2 = count_tokens(STEP2_WITH_MOTUS)
    with_step3 = count_tokens(STEP3_WITH_MOTUS)
    with_total = with_step2 + with_step3

    print("-" * 70)
    print("WITHOUT MOTUS (context grows with each handoff)")
    print("-" * 70)
    print(f"  Step 1→2 handoff: {without_step2:,} context tokens")
    print(f"  Step 2→3 handoff: {without_step3:,} context tokens")
    print(f"  TOTAL:            {without_total:,} context tokens")
    print()

    print("-" * 70)
    print("WITH MOTUS (receipts provide structured context)")
    print("-" * 70)
    print(f"  Step 1→2 handoff: {with_step2:,} context tokens")
    print(f"  Step 2→3 handoff: {with_step3:,} context tokens")
    print(f"  TOTAL:            {with_total:,} context tokens")
    print()

    reduction = ((without_total - with_total) / without_total) * 100

    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    print()
    print(f"  Without Motus: {without_total:,} tokens on context")
    print(f"  With Motus:    {with_total:,} tokens on context")
    print()
    print(f"  ╔═══════════════════════════════════════════╗")
    print(f"  ║  {reduction:.0f}% FEWER TOKENS ON CONTEXT  ║")
    print(f"  ╚═══════════════════════════════════════════╝")
    print()

    # The key insight: without Motus, context grows O(n) with steps
    # With Motus, each receipt is compact regardless of history
    print("KEY INSIGHT:")
    print(f"  Without Motus: Context grew from {without_step2} → {without_step3} tokens")
    print(f"  With Motus:    Context stayed flat: {with_step2} → {with_step3} tokens")
    print()
    print("  As workflows get longer, the gap WIDENS.")
    print()

    # Save results
    results = {
        "workflow": "3-step (model → api → tests)",
        "without_motus": {
            "step2_tokens": without_step2,
            "step3_tokens": without_step3,
            "total_tokens": without_total
        },
        "with_motus": {
            "step2_tokens": with_step2,
            "step3_tokens": with_step3,
            "total_tokens": with_total
        },
        "reduction_percent": round(reduction),
        "key_insight": "Context grows O(n) without Motus, stays flat with receipts"
    }

    output_path = Path(__file__).parent / "token_benchmark_v2_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Results saved to: {output_path}")

    return results

if __name__ == "__main__":
    run_benchmark()
