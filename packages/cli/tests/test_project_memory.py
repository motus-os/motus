from __future__ import annotations

import sqlite3
from pathlib import Path

from motus.memory import ProjectMemory


def _schema_version(db_path: Path) -> int:
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
        return int(row[0] or 0)
    finally:
        conn.close()


def test_creates_project_and_global_dbs(tmp_path: Path) -> None:
    global_root = tmp_path / ".motus"
    mem = ProjectMemory(tmp_path, global_root=global_root)
    try:
        assert mem.project_db_path.exists()
        assert mem.global_db_path.exists()

        assert _schema_version(mem.project_db_path) >= 2
        assert _schema_version(mem.global_db_path) >= 2
    finally:
        mem.close()


def test_detection_and_learning_persist(tmp_path: Path) -> None:
    global_root = tmp_path / ".motus"
    mem = ProjectMemory(tmp_path, global_root=global_root)
    try:
        mem.record_detection("project_type", "python", "high", detected_from="pyproject.toml")
        mem.learn_pattern("project_type", "python", "detection")
        mem.learn_pattern("project_type", "python", "observation")

        patterns = mem.get_patterns("project_type")
        assert patterns[0].pattern_value == "python"
        assert patterns[0].frequency >= 2
        detections = mem.get_detections("project_type")
        assert detections[0].pattern_value == "python"
        assert detections[0].confidence == "high"
    finally:
        mem.close()

    mem2 = ProjectMemory(tmp_path, global_root=global_root)
    try:
        patterns2 = mem2.get_patterns("project_type")
        assert patterns2
        assert patterns2[0].pattern_value == "python"
        assert patterns2[0].frequency >= 2
    finally:
        mem2.close()


def test_first_session_and_session_count(tmp_path: Path) -> None:
    global_root = tmp_path / ".motus"
    mem = ProjectMemory(tmp_path, global_root=global_root)
    try:
        assert mem.is_first_session() is True
        mem.start_session()
        assert mem.is_first_session() is False
        assert mem.get_session_count() == 0
        mem.end_session()
        assert mem.get_session_count() == 1
    finally:
        mem.close()


def test_record_command_unlocks_skills(tmp_path: Path) -> None:
    global_root = tmp_path / ".motus"
    mem = ProjectMemory(tmp_path, global_root=global_root)
    try:
        mem.record_command("motus go")
        unlocked = mem.get_unlocked_skills()
        assert "first_verification" in unlocked

        for _ in range(9):
            mem.record_command("motus go")
        unlocked = mem.get_unlocked_skills()
        assert "evidence_keeper" in unlocked
    finally:
        mem.close()

