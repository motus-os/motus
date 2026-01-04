# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""
Motus Safety Features Package.

This package provides safety features for AI agent interactions:
- Checkpoint and rollback
- Dry run simulation
- Test harness detection
- Cross-session memory
- Context hints injection

All public APIs are re-exported here for backward compatibility.
"""

import glob as _glob
from pathlib import Path

from .checkpoint import (
    Checkpoint,
    checkpoint_command,
    get_checkpoints_file,
    list_checkpoints_command,
    load_checkpoints,
    rollback_command,
    save_checkpoints,
)
from .context import get_context_hints
from .dry_run import (
    DryRunResult,
    dry_run_command,
    dry_run_git_clean,
    dry_run_git_reset,
    dry_run_mv,
    dry_run_rm,
)
from .memory import (
    MemoryEntry,
    get_file_memories,
    get_memory_file,
    load_memory,
    memory_command,
    record_memory,
    remember_command,
    save_memory,
)
from .test_harness import (
    detect_test_harness,
    find_related_tests,
    test_harness_command,
)

# Motus state directory
MC_DIR = Path.home() / ".mc"
MC_DIR.mkdir(exist_ok=True)

glob = _glob

__all__ = [
    # MC_DIR
    "MC_DIR",
    "glob",
    # Checkpoint
    "Checkpoint",
    "get_checkpoints_file",
    "load_checkpoints",
    "save_checkpoints",
    "checkpoint_command",
    "list_checkpoints_command",
    "rollback_command",
    # Dry Run
    "DryRunResult",
    "dry_run_rm",
    "dry_run_git_reset",
    "dry_run_git_clean",
    "dry_run_mv",
    "dry_run_command",
    # Test Harness
    "detect_test_harness",
    "find_related_tests",
    "test_harness_command",
    # Memory
    "MemoryEntry",
    "get_memory_file",
    "load_memory",
    "save_memory",
    "record_memory",
    "get_file_memories",
    "memory_command",
    "remember_command",
    # Context
    "get_context_hints",
]
