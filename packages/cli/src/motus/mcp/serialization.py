# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Safe serialization and redaction helpers for MCP responses."""

from __future__ import annotations

import dataclasses
import re
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

from ..commands.utils import redact_secrets

_HOME_PATH_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"/Users/[^/\\s]+"), "/[REDACTED_HOME]"),
    (re.compile(r"/home/[^/\\s]+"), "/[REDACTED_HOME]"),
    (re.compile(r"\\b[A-Za-z]:\\\\Users\\\\[^\\\\\\s]+"), r"[REDACTED_HOME]"),
]


def _redact_paths(text: str) -> str:
    if not text:
        return text
    result = text
    for pattern, replacement in _HOME_PATH_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def redact_text(text: str) -> str:
    """Redact secrets and common absolute home paths from text."""
    if not text:
        return text
    return _redact_paths(redact_secrets(text))


def redact_obj(obj: Any) -> Any:
    """Recursively redact strings within nested structures."""
    if isinstance(obj, str):
        return redact_text(obj)
    if isinstance(obj, list):
        return [redact_obj(v) for v in obj]
    if isinstance(obj, tuple):
        return [redact_obj(v) for v in obj]
    if isinstance(obj, dict):
        return {k: redact_obj(v) for k, v in obj.items()}
    return obj


def serialize_for_mcp(obj: Any) -> Any:
    """Convert complex objects to JSON-serializable form."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, Enum):
        return obj.value
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        as_dict = dataclasses.asdict(obj)
        return {k: serialize_for_mcp(v) for k, v in as_dict.items()}
    if hasattr(obj, "to_dict") and callable(getattr(obj, "to_dict")):
        try:
            return serialize_for_mcp(obj.to_dict())
        except Exception:
            pass
    if hasattr(obj, "model_dump") and callable(getattr(obj, "model_dump")):
        return serialize_for_mcp(obj.model_dump())
    if isinstance(obj, dict):
        return {str(k): serialize_for_mcp(v) for k, v in obj.items()}
    if isinstance(obj, (list, set, frozenset)):
        return [serialize_for_mcp(v) for v in obj]
    if isinstance(obj, Iterable):
        return [serialize_for_mcp(v) for v in obj]
    if hasattr(obj, "__dict__"):
        return {k: serialize_for_mcp(v) for k, v in vars(obj).items() if not k.startswith("_")}
    return str(obj)
