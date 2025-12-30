from __future__ import annotations

import json
from pathlib import Path

import pytest

from motus.tail_reader import count_lines, get_file_stats, tail_jsonl, tail_lines


def _write_bytes(path: Path, data: bytes) -> None:
    path.write_bytes(data)


def test_tail_lines_missing_returns_empty(tmp_path: Path) -> None:
    assert tail_lines(tmp_path / "missing.txt") == []


def test_tail_lines_returns_last_n(tmp_path: Path) -> None:
    path = tmp_path / "file.txt"
    path.write_text("one\ntwo\nthree\n", encoding="utf-8")
    assert tail_lines(path, n_lines=2) == ["two", "three"]


def test_tail_lines_strips_newlines(tmp_path: Path) -> None:
    path = tmp_path / "file.txt"
    path.write_text("one\n", encoding="utf-8")
    assert tail_lines(path, n_lines=1) == ["one"]


def test_tail_lines_handles_bad_bytes(tmp_path: Path) -> None:
    path = tmp_path / "file.bin"
    _write_bytes(path, b"good\n\xffbad\n")
    lines = tail_lines(path, n_lines=2)
    assert len(lines) == 2
    assert "good" in lines[0]


def test_tail_jsonl_missing_returns_empty(tmp_path: Path) -> None:
    assert tail_jsonl(tmp_path / "missing.jsonl") == []


def test_tail_jsonl_parses_valid(tmp_path: Path) -> None:
    path = tmp_path / "data.jsonl"
    path.write_text(json.dumps({"a": 1}) + "\n" + json.dumps({"b": 2}) + "\n")
    result = tail_jsonl(path, n_lines=1)
    assert result == [{"b": 2}]


def test_tail_jsonl_skips_invalid_when_enabled(tmp_path: Path) -> None:
    path = tmp_path / "data.jsonl"
    path.write_text("{bad}\n" + json.dumps({"ok": True}) + "\n")
    result = tail_jsonl(path, n_lines=2, skip_invalid=True)
    assert result == [{"ok": True}]


def test_tail_jsonl_raises_on_invalid_when_disabled(tmp_path: Path) -> None:
    path = tmp_path / "data.jsonl"
    path.write_text("{bad}\n")
    with pytest.raises(json.JSONDecodeError):
        tail_jsonl(path, n_lines=1, skip_invalid=False)


def test_count_lines_missing_returns_zero(tmp_path: Path) -> None:
    assert count_lines(tmp_path / "missing.txt") == 0


def test_count_lines_counts(tmp_path: Path) -> None:
    path = tmp_path / "file.txt"
    path.write_text("one\ntwo\nthree\n", encoding="utf-8")
    assert count_lines(path) == 3


def test_get_file_stats_missing_returns_zeros(tmp_path: Path) -> None:
    stats = get_file_stats(tmp_path / "missing.txt")
    assert stats == {"size_bytes": 0, "size_mb": 0.0, "line_count": 0}


def test_get_file_stats_estimates_lines(tmp_path: Path) -> None:
    path = tmp_path / "file.txt"
    _write_bytes(path, b"a" * 12010)
    stats = get_file_stats(path)
    assert stats["size_bytes"] == 12010
    assert stats["line_count"] == 2
