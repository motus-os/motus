# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Specificity scoring for Cached Orient standards.

Specificity is CSS-like: more (and more important) predicate keys win over less.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

DEFAULT_SPECIFICITY_WEIGHTS: dict[str, int] = {
    "artifact": 100,
    "theme": 50,
    "accessibility": 30,
    "medium": 20,
}


def specificity(
    applies_if: Mapping[str, Any],
    *,
    weights: Mapping[str, int] | None = None,
) -> int:
    """Return a deterministic specificity score (higher is more specific)."""

    w = weights or DEFAULT_SPECIFICITY_WEIGHTS
    return sum(int(w.get(k, 1)) for k in applies_if.keys())

