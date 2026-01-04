# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Deterministic glob matching utilities.

We intentionally avoid relying on `Path.match()` because its `**` behavior differs
from common globstar semantics (where `**` matches zero-or-more directories).
"""

from __future__ import annotations

import re
from functools import lru_cache


def _normalize_posix_path(path: str) -> str:
    """Normalize a path to POSIX format, stripping leading ./ and //."""
    candidate = path.strip().replace("\\", "/")
    while candidate.startswith("./"):
        candidate = candidate[2:]
    candidate = candidate.lstrip("/")
    candidate = re.sub(r"/{2,}", "/", candidate)
    return candidate


def _translate_segment(segment: str) -> str:
    """Translate a single glob path segment to regex pattern."""
    regex = ""
    i = 0
    length = len(segment)
    while i < length:
        ch = segment[i]
        if ch == "*":
            regex += "[^/]*"
        elif ch == "?":
            regex += "[^/]"
        elif ch == "[":
            j = i + 1
            if j < length and segment[j] == "!":
                j += 1
            if j < length and segment[j] == "]":
                j += 1
            while j < length and segment[j] != "]":
                j += 1

            if j >= length:
                regex += re.escape(ch)
            else:
                stuff = segment[i + 1 : j]
                if stuff.startswith("!"):
                    stuff = "^" + stuff[1:]
                stuff = stuff.replace("\\", "\\\\")
                regex += f"[{stuff}]"
                i = j
        else:
            regex += re.escape(ch)
        i += 1
    return regex


@lru_cache(maxsize=1024)
def _compile_glob(pattern: str) -> re.Pattern[str]:
    """Compile glob pattern to regex with globstar support."""
    normalized = _normalize_posix_path(pattern)
    if not normalized or normalized == "**":
        return re.compile(r"^.*$")

    parts = [p for p in normalized.split("/") if p]

    regex = "^"
    for idx, part in enumerate(parts):
        is_last = idx == len(parts) - 1
        if part == "**":
            if is_last:
                regex += r"(?:[^/]+/)*[^/]*"
            else:
                regex += r"(?:[^/]+/)*"
            continue

        regex += _translate_segment(part)
        if not is_last:
            regex += "/"

    regex += "$"

    return re.compile(regex)


def glob_match(pattern: str, path: str) -> bool:
    """Return True if `path` matches the glob `pattern` (globstar-aware)."""

    if not pattern:
        return False

    normalized_path = _normalize_posix_path(path)
    return bool(_compile_glob(pattern).match(normalized_path))


def matches_any(patterns: list[str], path: str) -> bool:
    """Return True if any glob in `patterns` matches `path`."""

    return any(glob_match(pattern, path) for pattern in patterns)
