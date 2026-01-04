# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""
Intent Spine - Structured task representation for AI agents.

The Intent Spine provides a structured way to capture and persist the agent's
task understanding. This helps agents stay on-task during long sessions and
enables context recovery across sessions.

Key features:
- Parse task from first user message in session
- Extract constraints and out-of-scope items
- Track priority files
- Save/load from .mc/intent.yaml
- Generate YAML output for easy inspection
"""

from .intent_models import Intent
from .intent_parser_core import (
    _determine_source,
    _extract_constraints,
    _extract_task_from_prompt,
    _identify_priority_files,
    _infer_out_of_scope,
    parse_intent,
)
from .intent_parser_yaml import generate_intent_yaml, load_intent, save_intent

__all__ = [
    "Intent",
    "_determine_source",
    "_extract_constraints",
    "_extract_task_from_prompt",
    "_identify_priority_files",
    "_infer_out_of_scope",
    "generate_intent_yaml",
    "load_intent",
    "parse_intent",
    "save_intent",
]
