# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Typed models for Project Memory tables."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Confidence = Literal["high", "medium", "low"]
PatternSource = Literal["detection", "user_input", "observation"]
PreferenceSource = Literal["cli", "config_file", "learned"]
GroundRuleSource = Literal["default", "user_defined", "imported"]


@dataclass(frozen=True)
class DetectedPattern:
    pattern_type: str
    pattern_value: str
    confidence: Confidence
    detected_from: str | None
    detected_at: str
    last_confirmed_at: str | None


@dataclass(frozen=True)
class LearnedPattern:
    pattern_type: str
    pattern_value: str
    learned_at: str
    source: PatternSource
    frequency: int
    last_seen_at: str

