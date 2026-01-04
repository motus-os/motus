# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Skill progression tracking for Motus.

Skills are intentionally simple in Phase 0: counters with unlock thresholds.
The schema lives in `migrations/002_project_memory.sql`.
"""

from __future__ import annotations

import sqlite3

SKILL_THRESHOLDS: dict[str, int] = {
    "first_verification": 1,
    "evidence_keeper": 10,
    "test_guardian": 50,
    "security_sentinel": 5,
    "speed_demon": 100,
}


def ensure_skill_rows(conn: sqlite3.Connection) -> None:
    """Ensure all known skills exist in the `skills` table."""
    for skill_name, threshold in SKILL_THRESHOLDS.items():
        conn.execute(
            """
            INSERT INTO skills (skill_name, unlock_threshold)
            VALUES (?, ?)
            ON CONFLICT(skill_name) DO UPDATE SET unlock_threshold = excluded.unlock_threshold
        """,
            (skill_name, threshold),
        )


def record_progress(conn: sqlite3.Connection, *, skill_name: str, delta: int) -> bool:
    """Increment progress for a skill and unlock if threshold is reached.

    Returns:
        True if the skill was unlocked by this call.
    """
    if delta < 0:
        return False

    ensure_skill_rows(conn)

    row = conn.execute(
        "SELECT progress_count, unlock_threshold, unlocked_at FROM skills WHERE skill_name = ?",
        (skill_name,),
    ).fetchone()
    if row is None:
        return False

    progress_count, unlock_threshold, unlocked_at = row[0], row[1], row[2]
    new_progress = int(progress_count) + int(delta)

    if delta > 0:
        conn.execute(
            "UPDATE skills SET progress_count = ? WHERE skill_name = ?",
            (new_progress, skill_name),
        )

    if unlocked_at is None and new_progress >= int(unlock_threshold):
        conn.execute(
            "UPDATE skills SET unlocked_at = datetime('now') WHERE skill_name = ?",
            (skill_name,),
        )
        return True

    return False


def get_unlocked_skills(conn: sqlite3.Connection) -> list[str]:
    ensure_skill_rows(conn)
    cursor = conn.execute(
        "SELECT skill_name FROM skills WHERE unlocked_at IS NOT NULL ORDER BY skill_name"
    )
    return [row[0] for row in cursor.fetchall()]


def skill_deltas_for_command(command: str) -> dict[str, int]:
    """Best-effort mapping from a command string to skill deltas."""
    normalized = " ".join(command.strip().split())
    if not normalized:
        return {}

    deltas: dict[str, int] = {}

    # `motus go` is treated as a verification run that typically emits evidence.
    if normalized.startswith("motus go") or normalized == "motus go":
        deltas["first_verification"] = deltas.get("first_verification", 0) + 1
        deltas["evidence_keeper"] = deltas.get("evidence_keeper", 0) + 1

    if "pytest" in normalized or (normalized.startswith("python") and "-m pytest" in normalized):
        deltas["test_guardian"] = deltas.get("test_guardian", 0) + 1

    if "bandit" in normalized:
        deltas["security_sentinel"] = deltas.get("security_sentinel", 0) + 1

    return deltas

