# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Types for reversal coordination."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class VerificationResult:
    """Result of reversal verification."""

    success: bool
    message: str
    failed_actions: list[str]
