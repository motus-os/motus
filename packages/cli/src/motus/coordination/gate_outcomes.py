# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Gate outcome persistence for the Work Ledger."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone

from motus.core.database_connection import get_db_manager
from motus.core.sqlite_udfs import mc_id
from motus.logging import get_logger

_logger = get_logger(__name__)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _generate_gate_outcome_id() -> str:
    seed = uuid.uuid4().hex
    return mc_id("gate", seed) or f"gate-{seed}"


def persist_gate_outcome(
    *,
    gate_id: str,
    status: str,
    work_id: str,
    decided_by: str,
    reason: str | None = None,
    policy_ref: str | None = None,
    step_id: str | None = None,
    decided_at: str | None = None,
) -> bool:
    """Append a gate outcome row to the Work Ledger."""
    if not gate_id or not work_id or not decided_by:
        return False

    result = "pass" if status == "pass" else "fail"
    outcome_id = _generate_gate_outcome_id()
    decided_at_value = decided_at or _utcnow_iso()

    try:
        db = get_db_manager()
        with db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO gate_outcomes (
                    id, gate_id, result, reason, policy_ref, decided_by,
                    decided_at, work_id, step_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    outcome_id,
                    gate_id,
                    result,
                    reason,
                    policy_ref,
                    decided_by,
                    decided_at_value,
                    work_id,
                    step_id,
                ),
            )
        return True
    except sqlite3.IntegrityError as exc:
        _logger.warning(f"Failed to persist gate outcome {gate_id}: {exc}")
        return False
    except sqlite3.OperationalError as exc:
        _logger.warning(f"Gate outcomes table unavailable: {exc}")
        return False
    except Exception as exc:  # noqa: BLE001
        _logger.warning(f"Failed to persist gate outcome {gate_id}: {exc}")
        return False
