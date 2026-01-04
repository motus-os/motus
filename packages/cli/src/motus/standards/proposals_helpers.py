# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Helper utilities for proposal management."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from motus.standards.schemas import ProposalStatus


class ProposalError(Exception):
    pass


class PromotionError(ProposalError):
    pass


def context_hash(context: dict[str, Any]) -> str:
    """Deterministic hash: sha256(canonical_json(context))."""

    canonical = json.dumps(context, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _utc_now_iso_z() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _slugify(raw: str) -> str:
    s = raw.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-") or "x"


def _proposal_filename(proposal_id: str) -> str:
    if not proposal_id or "/" in proposal_id or "\\" in proposal_id:
        raise ProposalError("Invalid proposal_id")
    return f"{proposal_id}.yaml"


def _require_mapping(raw: Any, *, path: Path) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ProposalError(f"Invalid proposal (expected mapping): {path}")
    return raw


def _require_str(raw: Any, *, field: str, path: Path) -> str:
    if not isinstance(raw, str) or not raw:
        raise ProposalError(f"Invalid proposal ({field} must be non-empty string): {path}")
    return raw


def _require_dict(raw: Any, *, field: str, path: Path) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ProposalError(f"Invalid proposal ({field} must be mapping): {path}")
    return raw


def _status_dir(root: Path, status: ProposalStatus) -> Path:
    return root / status
