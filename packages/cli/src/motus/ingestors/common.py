# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Common utilities shared across builder implementations.

Extracted from claude.py, codex.py, gemini.py to eliminate duplication.
"""

from __future__ import annotations

from ..logging import get_logger
from .common_actions import detect_completion_marker, find_last_action
from .common_actions_claude import get_claude_last_action, has_claude_completion_marker
from .common_actions_codex import get_codex_last_action, has_codex_completion_marker
from .common_actions_gemini import get_gemini_last_action, has_gemini_completion_marker
from .common_io import (
    MAX_READ_ATTEMPTS,
    MAX_SESSION_SIZE_BYTES,
    READ_RETRY_DELAY_SECONDS,
    JsonDict,
    _read_tail_text,
    iter_jsonl_dicts,
    iter_jsonl_tail_dicts,
    load_json_file,
    parse_iso_timestamp,
    parse_jsonl_line,
    parse_timestamp_field,
    scan_file_tail,
)

logger = get_logger(__name__)

from ._common_extract import (  # noqa: E402,F401
    extract_claude_decisions,
    extract_claude_thinking,
    extract_codex_decisions,
    extract_codex_thinking,
    extract_gemini_decisions,
    extract_gemini_thinking,
)

__all__ = [
    "JsonDict",
    "MAX_READ_ATTEMPTS",
    "MAX_SESSION_SIZE_BYTES",
    "READ_RETRY_DELAY_SECONDS",
    "_read_tail_text",
    "detect_completion_marker",
    "extract_claude_decisions",
    "extract_claude_thinking",
    "extract_codex_decisions",
    "extract_codex_thinking",
    "extract_gemini_decisions",
    "extract_gemini_thinking",
    "find_last_action",
    "get_claude_last_action",
    "get_codex_last_action",
    "get_gemini_last_action",
    "has_claude_completion_marker",
    "has_codex_completion_marker",
    "has_gemini_completion_marker",
    "iter_jsonl_dicts",
    "iter_jsonl_tail_dicts",
    "load_json_file",
    "parse_iso_timestamp",
    "parse_jsonl_line",
    "parse_timestamp_field",
    "scan_file_tail",
]
