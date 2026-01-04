# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Checkpoint models for git-backed session state."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Checkpoint:
    """A saved state checkpoint using git stash.

    Attributes:
        id: Unique checkpoint identifier (timestamp-based)
        label: User-provided description of the checkpoint
        timestamp: ISO format timestamp when checkpoint was created
        git_stash_ref: Git stash reference (e.g., "stash@{0}")
        file_manifest: List of modified files at checkpoint time
    """

    id: str
    label: str
    timestamp: str
    git_stash_ref: Optional[str] = None
    file_manifest: list[str] = field(default_factory=list)
