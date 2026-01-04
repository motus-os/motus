# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

import sqlite3
from pathlib import Path
from typing import Optional

from ..config import config
from ..core import configure_connection
from .models import ContributionEvent, EvidenceBundle, WorkReceipt


class GovernanceLayer:
    def __init__(self) -> None:
        self._conn: Optional[sqlite3.Connection] = None
        if config.governance.enabled and config.governance.storage.type == "sqlite":
            self._init_db()

    def _init_db(self) -> None:
        db_path = Path(config.governance.storage.path).expanduser()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        configure_connection(self._conn)
        c = self._conn.cursor()
        # Create tables if not exist
        c.execute(
            """CREATE TABLE IF NOT EXISTS work_receipts
                     (id TEXT PRIMARY KEY, data TEXT, timestamp TEXT)"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS evidence_bundles
                     (id TEXT PRIMARY KEY, data TEXT, timestamp TEXT)"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS contribution_ledger
                     (id TEXT PRIMARY KEY, data TEXT, timestamp TEXT)"""
        )
        self._conn.commit()

    def emit_receipt(self, receipt: WorkReceipt) -> None:
        if not config.governance.enabled or not config.governance.work_receipts:
            return
        if self._conn:
            c = self._conn.cursor()
            c.execute(
                "INSERT INTO work_receipts VALUES (?, ?, ?)",
                (
                    receipt.work_id,
                    receipt.model_dump_json(),
                    receipt.timestamp_utc.isoformat(),
                ),
            )
            self._conn.commit()

    def store_bundle(self, bundle: EvidenceBundle) -> None:
        if not config.governance.enabled or not config.governance.evidence_bundles:
            return
        if self._conn:
            c = self._conn.cursor()
            c.execute(
                "INSERT INTO evidence_bundles VALUES (?, ?, ?)",
                (
                    bundle.bundle_id,
                    bundle.model_dump_json(),
                    bundle.timestamp_utc.isoformat(),
                ),
            )
            self._conn.commit()

    def log_contribution(self, event: ContributionEvent) -> None:
        if not config.governance.enabled or not config.governance.contribution_ledger:
            return
        if self._conn:
            c = self._conn.cursor()
            c.execute(
                "INSERT INTO contribution_ledger VALUES (?, ?, ?)",
                (
                    event.event_id,
                    event.model_dump_json(),
                    event.timestamp_utc.isoformat(),
                ),
            )
            self._conn.commit()

    def close(self) -> None:
        if self._conn:
            self._conn.close()


# Singleton instance
governance = GovernanceLayer()
