# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Review command handler."""

from __future__ import annotations

from typing import Any

from .roadmap_cmd import cmd_roadmap_review


def review_command(args: Any) -> int:
    """Request review for a roadmap item."""
    return cmd_roadmap_review(args)
