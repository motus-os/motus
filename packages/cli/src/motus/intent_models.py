# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Intent data models."""

from dataclasses import dataclass, field


@dataclass
class Intent:
    """
    Structured representation of an agent's task.

    Attributes:
        task: Main task description (extracted from first user message)
        constraints: List of constraints/requirements (e.g., "Don't modify tests")
        out_of_scope: List of things explicitly out of scope
        priority_files: List of file paths that are central to the task
    """

    task: str
    constraints: list[str] = field(default_factory=list)
    out_of_scope: list[str] = field(default_factory=list)
    priority_files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert Intent to dictionary for serialization."""
        return {
            "task": self.task,
            "constraints": self.constraints,
            "out_of_scope": self.out_of_scope,
            "priority_files": self.priority_files,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Intent":
        """Create Intent from dictionary."""
        return cls(
            task=data.get("task", ""),
            constraints=data.get("constraints", []),
            out_of_scope=data.get("out_of_scope", []),
            priority_files=data.get("priority_files", []),
        )
