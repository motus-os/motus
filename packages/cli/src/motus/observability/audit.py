# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Database-backed audit logging.

Writes immutable events to the `audit_log` table.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict

from motus.core.bootstrap import get_instance_id
from motus.core.database import DatabaseManager, get_db_manager


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _format_ts(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class AuditEvent:
    event_type: str
    actor: str
    action: str
    resource_type: str | None = None
    resource_id: str | None = None
    old_value: Dict[str, Any] | None = None
    new_value: Dict[str, Any] | None = None
    context: Dict[str, Any] | None = None
    timestamp: datetime | None = None
    protocol_version: int = 1


class AuditLogger:
    def __init__(self, *, db: DatabaseManager | None = None) -> None:
        self._db = db or get_db_manager()

    def emit(self, event: AuditEvent) -> None:
        ts = _format_ts(event.timestamp or _utc_now())
        instance_id = get_instance_id()

        with self._db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO audit_log (
                    timestamp, event_type, actor, resource_type, resource_id,
                    action, old_value, new_value, context, instance_id, protocol_version
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ts,
                    event.event_type,
                    event.actor,
                    event.resource_type,
                    event.resource_id,
                    event.action,
                    json.dumps(event.old_value, sort_keys=True) if event.old_value is not None else None,
                    json.dumps(event.new_value, sort_keys=True) if event.new_value is not None else None,
                    json.dumps(event.context, sort_keys=True) if event.context is not None else None,
                    instance_id,
                    event.protocol_version,
                ),
            )
