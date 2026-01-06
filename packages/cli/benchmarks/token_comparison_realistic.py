#!/usr/bin/env python3
"""
Benchmark v3: REALISTIC token comparison

This simulates what ACTUALLY happens in practice:
- Without Motus: Developers paste code, chat history, explain everything
- With Motus: Structured receipt

Based on real patterns observed in AI-assisted development.
"""

import json
from pathlib import Path

def count_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token"""
    return len(text) // 4

# =============================================================================
# WITHOUT MOTUS: What developers ACTUALLY do
# - Paste relevant code files
# - Explain what was tried
# - Include error messages
# - Describe the architecture
# =============================================================================

REALISTIC_WITHOUT_MOTUS = '''
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
    priority = Column(Integer, default=3)  # 1-5, 1 is highest
    due_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)  # soft delete

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    user = relationship("User", back_populates="tasks")

    tags = relationship("Tag", secondary="task_tags", back_populates="tasks")

    def can_transition_to(self, new_status: TaskStatus) -> bool:
        """Validate status transitions"""
        valid_transitions = {
            TaskStatus.PENDING: [TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED],
            TaskStatus.IN_PROGRESS: [TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.PENDING],
            TaskStatus.COMPLETED: [],  # terminal state
            TaskStatus.CANCELLED: [TaskStatus.PENDING],  # can reopen
        }
        return new_status in valid_transitions.get(self.status, [])
```

### 2. API Endpoints (src/api/tasks.py)

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from ..models.task import Task, TaskStatus
from ..schemas.task import TaskCreate, TaskUpdate, TaskResponse, TaskListResponse
from ..database import get_db
from ..auth import get_current_user

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
    query = db.query(Task).filter(
        Task.user_id == current_user.id,
        Task.deleted_at.is_(None)
    )
    if status:
        query = query.filter(Task.status == status)
    if priority:
        query = query.filter(Task.priority == priority)

    total = query.count()
    tasks = query.offset(offset).limit(limit).all()

    return {"tasks": tasks, "total": total, "offset": offset, "limit": limit}

@router.post("/", response_model=TaskResponse, status_code=201)
async def create_task(
    task_data: TaskCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    task = Task(**task_data.dict(), user_id=current_user.id)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.user_id == current_user.id,
        Task.deleted_at.is_(None)
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

# ... more endpoints
```

### Design Decisions Made
1. Used UUID instead of auto-increment IDs for better distributed systems support
2. Implemented soft delete (deleted_at timestamp) instead of hard delete
3. Status transitions are validated in the model to prevent invalid state changes
4. Pagination has a max limit of 100 to prevent abuse
5. All endpoints require authentication
6. Tasks are scoped to the authenticated user

### What We Tried That Didn't Work
- Initially tried using integer IDs but switched to UUID for distributed compatibility
- First version didn't have status transition validation, added after testing

## Your Task
Write comprehensive integration tests for the API endpoints using pytest and httpx.
'''

# =============================================================================
# WITH MOTUS: Structured receipt chain
# =============================================================================

REALISTIC_WITH_MOTUS = '''
Write integration tests for the API described in this receipt chain:

```receipt rx_001 (data-model)
task_id: TASK-001
agent: claude-opus
status: completed

outcome:
  files:
    - src/models/task.py: Task model with UUID, status enum, soft delete
    - migrations/001_create_tasks.py: Initial schema

evidence:
  - model_fields: [id:UUID, title:str, description:text, status:enum, priority:1-5, due_date, timestamps, deleted_at]
  - relationships: [user_id->users, tags->task_tags]
  - status_enum: [PENDING, IN_PROGRESS, COMPLETED, CANCELLED]

decisions:
  - "UUID over auto-increment: distributed systems compatibility"
  - "Soft delete via deleted_at: audit trail preservation"
  - "Status validation in model: prevents invalid transitions"
```

```receipt rx_002 (api-endpoints)
task_id: TASK-002
parent: rx_001
agent: claude-opus
status: completed

outcome:
  files:
    - src/api/tasks.py: CRUD endpoints
    - src/schemas/task.py: Pydantic models

evidence:
  - endpoints: [GET /, GET /{id}, POST /, PUT /{id}, PATCH /{id}, DELETE /{id}]
  - auth: required on all endpoints
  - pagination: offset/limit, max 100
  - tests_needed: true

decisions:
  - "Pagination max 100: prevent abuse"
  - "Soft delete on DELETE: matches model pattern"
  - "403 on invalid status transition: clear error"
```

Write pytest integration tests using httpx AsyncClient.
'''

def run_benchmark():
    """Run the realistic token comparison"""

    print("=" * 70)
    print("MOTUS TOKEN BENCHMARK: Realistic Scenario")
    print("=" * 70)
    print()
    print("Scenario: Hand off API work for test writing")
    print("Comparison: What developers ACTUALLY do vs structured receipts")
    print()

    without_tokens = count_tokens(REALISTIC_WITHOUT_MOTUS)
    with_tokens = count_tokens(REALISTIC_WITH_MOTUS)

    print("-" * 70)
    print("WITHOUT MOTUS")
    print("-" * 70)
    print("Developer pastes: code files, explanations, decisions, history")
    print(f"Context size: {len(REALISTIC_WITHOUT_MOTUS):,} characters")
    print(f"Token count:  {without_tokens:,} tokens")
    print()

    print("-" * 70)
    print("WITH MOTUS")
    print("-" * 70)
    print("Developer provides: receipt chain (structured, minimal)")
    print(f"Context size: {len(REALISTIC_WITH_MOTUS):,} characters")
    print(f"Token count:  {with_tokens:,} tokens")
    print()

    reduction = ((without_tokens - with_tokens) / without_tokens) * 100
    saved = without_tokens - with_tokens

    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    print()
    print(f"  Without Motus: {without_tokens:,} tokens")
    print(f"  With Motus:    {with_tokens:,} tokens")
    print(f"  Tokens saved:  {saved:,} tokens")
    print()
    print(f"  ╔════════════════════════════════════════════════════╗")
    print(f"  ║   {reduction:.0f}% FEWER CONTEXT TOKENS WITH MOTUS   ║")
    print(f"  ╚════════════════════════════════════════════════════╝")
    print()
    print("WHAT THIS MEANS:")
    print(f"  - Every handoff saves ~{saved:,} tokens")
    print(f"  - At $0.01/1K tokens, that's ${saved * 0.00001:.3f} per handoff")
    print(f"  - 10 handoffs/day = ${saved * 0.0001:.2f}/day saved")
    print(f"  - More importantly: FASTER context loading, LESS noise")
    print()

    # Save results
    results = {
        "scenario": "realistic_handoff",
        "description": "Code + explanations vs structured receipt",
        "without_motus_tokens": without_tokens,
        "with_motus_tokens": with_tokens,
        "tokens_saved": saved,
        "reduction_percent": round(reduction),
        "without_chars": len(REALISTIC_WITHOUT_MOTUS),
        "with_chars": len(REALISTIC_WITH_MOTUS)
    }

    output_path = Path(__file__).parent / "token_benchmark_realistic_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Results saved to: {output_path}")

    return results

if __name__ == "__main__":
    run_benchmark()
