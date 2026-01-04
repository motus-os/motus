# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Trace discovery helpers for the CLI."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from motus.logging import get_logger

logger = get_logger(__name__)

def find_sdk_traces_in_dir(state_dir: Path) -> list[dict]:
    """Find SDK trace files under a given Motus state directory."""

    traces: list[dict] = []
    traces_dir = state_dir / "traces"

    if not traces_dir.exists():
        return traces

    for trace_file in traces_dir.glob("*.jsonl"):
        try:
            stat = trace_file.stat()
        except OSError as e:
            logger.warning(
                "Failed to stat trace file",
                trace_file=str(trace_file),
                error_type=type(e).__name__,
                error=str(e),
            )
            continue
        modified = datetime.fromtimestamp(stat.st_mtime)
        age_seconds = (datetime.now() - modified).total_seconds()

        # Read first line to get session info
        try:
            with trace_file.open("r", encoding="utf-8") as handle:
                first_line = handle.readline()
                data = json.loads(first_line)
                tracer_name = data.get("tracer_name", trace_file.stem)
        except (OSError, json.JSONDecodeError, KeyError) as e:
            logger.warning(
                "Failed to read trace file header",
                trace_file=str(trace_file),
                error_type=type(e).__name__,
                error=str(e),
            )
            tracer_name = trace_file.stem

        traces.append(
            {
                "name": tracer_name,
                "file": trace_file,
                "modified": modified,
                "size": stat.st_size,
                "is_active": age_seconds < 60,
            }
        )

    traces.sort(key=lambda t: t["modified"], reverse=True)
    return traces[:5]
