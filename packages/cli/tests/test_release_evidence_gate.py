# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

from __future__ import annotations

import os
import time
from pathlib import Path

from motus.release import evidence_gate


def _write(path: Path, text: str = "{}") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_health_files_missing(tmp_path: Path) -> None:
    result = evidence_gate._check_health_files(tmp_path)
    assert result.passed is False
    assert "Missing health artifacts" in result.message


def test_health_files_recent(tmp_path: Path) -> None:
    root = tmp_path
    _write(root / "packages/cli/docs/quality/health-baseline.json")
    _write(root / "packages/cli/docs/quality/health-policy.json")
    ledger = root / "packages/cli/docs/quality/health-ledger.md"
    _write(ledger, "# Health\n")

    now = time.time()
    os.utime(ledger, (now, now))

    result = evidence_gate._check_health_files(root)
    assert result.passed is True
