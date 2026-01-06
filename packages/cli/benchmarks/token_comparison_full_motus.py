#!/usr/bin/env python3
"""
Benchmark v4: FULL Motus capabilities

Comparison:
1. WITHOUT MOTUS: Manual paste of code, context, decisions
2. WITH MOTUS (basic): Paste receipt manually
3. WITH MOTUS (full): Use `motus work context` - system assembles what's needed

The full Motus flow:
- Agent calls `motus work context TASK-001`
- System returns ONLY relevant context, pre-assembled
- No manual curation, no paste, no noise
"""

import json
from pathlib import Path

def count_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token"""
    return len(text) // 4

# =============================================================================
# WITHOUT MOTUS: Manual context dump (realistic)
# =============================================================================

WITHOUT_MOTUS = '''
I need help continuing work from a previous session. Let me give you all the context:

## Project Overview
We're building a task management API. The tech stack is Python 3.11, FastAPI, PostgreSQL with SQLAlchemy ORM, and we're using Alembic for migrations.

## What was done in the previous session

### 1. Data Model (src/models/task.py)

```python
from sqlalchemy import Column, String, Text, DateTime, Integer, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
import enum
from datetime import datetime

from .base import Base

class TaskStatus(enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class Task(Base):
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING)
    priority = Column(Integer, default=3)
    due_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    user = relationship("User", back_populates="tasks")
    tags = relationship("Tag", secondary="task_tags", back_populates="tasks")

    def can_transition_to(self, new_status: TaskStatus) -> bool:
        valid_transitions = {
            TaskStatus.PENDING: [TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED],
            TaskStatus.IN_PROGRESS: [TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.PENDING],
            TaskStatus.COMPLETED: [],
            TaskStatus.CANCELLED: [TaskStatus.PENDING],
        }
        return new_status in valid_transitions.get(self.status, [])
```

### 2. API Endpoints (src/api/tasks.py)

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

router = APIRouter(prefix="/tasks", tags=["tasks"])

@router.get("/", response_model=TaskListResponse)
async def list_tasks(
    status: Optional[TaskStatus] = None,
    priority: Optional[int] = Query(None, ge=1, le=5),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    # ... implementation
    pass

@router.post("/", response_model=TaskResponse, status_code=201)
async def create_task(task_data: TaskCreate, db: Session = Depends(get_db)):
    # ... implementation
    pass

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: UUID, db: Session = Depends(get_db)):
    # ... implementation
    pass

@router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: UUID, db: Session = Depends(get_db)):
    # ... soft delete implementation
    pass
```

### Design Decisions Made
1. Used UUID instead of auto-increment IDs for distributed systems
2. Implemented soft delete (deleted_at timestamp)
3. Status transitions validated in model
4. Pagination max limit of 100
5. All endpoints require authentication

### What We Tried That Didn't Work
- Initially tried integer IDs but switched to UUID
- First version didn't have status transition validation

## Your Task
Write comprehensive integration tests for the API endpoints.
'''

# =============================================================================
# WITH MOTUS (basic): Manually paste receipt
# =============================================================================

WITH_MOTUS_BASIC = '''
Write integration tests for the API in this receipt chain:

```receipt rx_001
task: data-model
outcome: src/models/task.py (Task: UUID, title, status enum, priority, timestamps, soft delete)
decisions: ["UUID for distributed", "soft delete pattern", "status transition validation"]
```

```receipt rx_002
task: api-endpoints
outcome: src/api/tasks.py (CRUD: GET/, GET/{id}, POST/, PUT/{id}, DELETE/{id})
evidence: auth required, pagination max 100, soft delete on DELETE
decisions: ["403 on invalid transition", "scope to authenticated user"]
```

Write pytest integration tests.
'''

# =============================================================================
# WITH MOTUS (full): Agent uses motus work context
# =============================================================================

WITH_MOTUS_FULL = '''
Write integration tests for TASK-003.

Context retrieved via `motus work context TASK-003`:
{
  "task": "TASK-003-integration-tests",
  "depends_on": ["rx_001", "rx_002"],
  "summary": {
    "model": "Task (UUID pk, status enum, soft delete)",
    "api": "CRUD /tasks, auth required, pagination",
    "key_decisions": ["status validation", "soft delete", "max 100 pagination"]
  }
}

Write pytest tests with httpx AsyncClient.
'''

# =============================================================================
# WITH MOTUS (optimal): Just the task ID, agent queries what it needs
# =============================================================================

WITH_MOTUS_OPTIMAL = '''
Continue work on TASK-003: Write integration tests.

Lease: rx_003
Parent receipts: rx_001 (model), rx_002 (api)

Use `motus work context rx_003` for full context if needed.
'''

def run_benchmark():
    """Run the full Motus capabilities benchmark"""

    scenarios = [
        ("WITHOUT MOTUS (manual paste)", WITHOUT_MOTUS,
         "Developer copies code, explains context, lists decisions"),
        ("WITH MOTUS (basic - paste receipt)", WITH_MOTUS_BASIC,
         "Developer pastes receipt chain manually"),
        ("WITH MOTUS (full - context API)", WITH_MOTUS_FULL,
         "Agent calls motus work context, gets assembled summary"),
        ("WITH MOTUS (optimal - query on demand)", WITH_MOTUS_OPTIMAL,
         "Agent has task ID, queries context only if needed"),
    ]

    print("=" * 70)
    print("MOTUS TOKEN BENCHMARK: Full Capabilities Comparison")
    print("=" * 70)
    print()

    results = []
    baseline = None

    for name, content, description in scenarios:
        tokens = count_tokens(content)
        if baseline is None:
            baseline = tokens
        reduction = ((baseline - tokens) / baseline) * 100 if baseline else 0

        results.append({
            "scenario": name,
            "tokens": tokens,
            "reduction": round(reduction)
        })

        print("-" * 70)
        print(f"{name}")
        print("-" * 70)
        print(f"  {description}")
        print(f"  Tokens: {tokens:,}")
        if reduction > 0:
            print(f"  Reduction: {reduction:.0f}% vs baseline")
        print()

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print()
    print(f"  {'Scenario':<45} {'Tokens':>8} {'Reduction':>10}")
    print(f"  {'-'*45} {'-'*8} {'-'*10}")
    for r in results:
        reduction_str = f"{r['reduction']}%" if r['reduction'] > 0 else "baseline"
        print(f"  {r['scenario']:<45} {r['tokens']:>8,} {reduction_str:>10}")
    print()

    # The key numbers
    without = results[0]['tokens']
    optimal = results[-1]['tokens']
    max_reduction = ((without - optimal) / without) * 100

    print(f"  ╔═══════════════════════════════════════════════════════════╗")
    print(f"  ║  MAXIMUM REDUCTION: {max_reduction:.0f}% fewer context tokens  ║")
    print(f"  ╚═══════════════════════════════════════════════════════════╝")
    print()
    print(f"  From {without:,} tokens → {optimal:,} tokens")
    print()

    # Save results
    output = {
        "scenarios": results,
        "baseline_tokens": without,
        "optimal_tokens": optimal,
        "max_reduction_percent": round(max_reduction)
    }

    output_path = Path(__file__).parent / "token_benchmark_full_results.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Results saved to: {output_path}")

    return output

if __name__ == "__main__":
    run_benchmark()
