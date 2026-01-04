# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Forensics boundary policy for transcript-derived data.

Transcript parsing is never used to drive runtime coordination or enforcement decisions.
Forensics-derived data is non-authoritative and intended for context or diagnostics only.
"""

from __future__ import annotations

FORENSICS_AUTHORITY = "forensics"
FORENSICS_POLICY_ID = "forensics.boundary.v1"


def apply_forensics_boundary(raw_data: dict | None) -> dict:
    """Return raw_data annotated with the forensics boundary policy."""
    if raw_data is None:
        data = {}
    elif isinstance(raw_data, dict):
        data = dict(raw_data)
    else:
        data = {}
    data.setdefault("authority", FORENSICS_AUTHORITY)
    data.setdefault("boundary_policy_id", FORENSICS_POLICY_ID)
    data.setdefault("non_authoritative", True)
    return data
