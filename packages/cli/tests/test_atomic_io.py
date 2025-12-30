from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

import motus.atomic_io as atomic_io
from motus.atomic_io import atomic_write_json, atomic_write_text


def _tmp_glob(path: Path) -> list[Path]:
    return list(path.parent.glob(f".{path.name}.*.tmp"))


def test_atomic_write_text_writes_file(tmp_path: Path) -> None:
    target = tmp_path / "hello.txt"
    atomic_write_text(target, "hello\n")
    assert target.read_text(encoding="utf-8") == "hello\n"
    assert _tmp_glob(target) == []


def test_atomic_write_json_writes_file(tmp_path: Path) -> None:
    target = tmp_path / "payload.json"
    atomic_write_json(target, {"b": 2, "a": 1})
    assert json.loads(target.read_text(encoding="utf-8")) == {"a": 1, "b": 2}
    assert _tmp_glob(target) == []


def test_atomic_write_text_creates_parent_dirs(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b" / "hello.txt"
    atomic_write_text(target, "hello\n")
    assert target.read_text(encoding="utf-8") == "hello\n"
    assert _tmp_glob(target) == []


def test_atomic_write_text_uses_destination_dir_for_tempfile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "nested" / "state.txt"
    call_args: dict[str, str] = {}
    original_mkstemp = tempfile.mkstemp

    def _mkstemp(*args: object, **kwargs: object) -> tuple[int, str]:
        dir_value = str(kwargs.get("dir"))
        call_args["dir"] = dir_value
        return original_mkstemp(*args, **kwargs)  # type: ignore[no-any-return]

    monkeypatch.setattr("motus.atomic_io.tempfile.mkstemp", _mkstemp)

    atomic_write_text(target, "new\n")
    assert Path(call_args["dir"]).resolve() == target.parent.resolve()


def test_atomic_write_text_cleans_temp_file_on_replace_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "state.txt"
    target.write_text("old\n", encoding="utf-8")

    def _boom(src: str | Path, dst: str | Path) -> None:
        raise OSError("boom")

    monkeypatch.setattr("motus.atomic_io.os.replace", _boom)

    with pytest.raises(OSError):
        atomic_write_text(target, "new\n")

    assert target.read_text(encoding="utf-8") == "old\n"
    assert _tmp_glob(target) == []


def test_atomic_write_text_cleans_temp_file_on_fsync_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "state.txt"
    target.write_text("old\n", encoding="utf-8")

    def _boom(fd: int) -> None:
        raise OSError("boom")

    monkeypatch.setattr("motus.atomic_io.os.fsync", _boom)

    with pytest.raises(OSError):
        atomic_write_text(target, "new\n")

    assert target.read_text(encoding="utf-8") == "old\n"
    assert _tmp_glob(target) == []


def test_atomic_write_text_propagates_mkstemp_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "hello.txt"

    def _mkstemp(*args: object, **kwargs: object) -> tuple[int, str]:
        raise OSError("boom")

    monkeypatch.setattr("motus.atomic_io.tempfile.mkstemp", _mkstemp)

    with pytest.raises(OSError):
        atomic_write_text(target, "hello\n")


def test_atomic_write_json_is_newline_terminated_and_preserves_unicode(tmp_path: Path) -> None:
    target = tmp_path / "payload.json"
    payload = {"emoji": "☃", "text": "café"}
    atomic_write_json(target, payload)
    text = target.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert "café" in text
    assert json.loads(text) == payload


def test_atomic_write_text_does_not_mask_cleanup_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "state.txt"
    target.write_text("old\n", encoding="utf-8")

    created_tmp: dict[str, str] = {}
    original_mkstemp = tempfile.mkstemp

    def _mkstemp(*args: object, **kwargs: object) -> tuple[int, str]:
        fd, name = original_mkstemp(*args, **kwargs)  # type: ignore[misc]
        created_tmp["path"] = name
        return fd, name

    def _replace_boom(src: str | Path, dst: str | Path) -> None:
        raise OSError("boom")

    original_unlink = Path.unlink

    def _unlink_boom(self: Path, *, missing_ok: bool = False) -> None:
        if created_tmp.get("path") and self == Path(created_tmp["path"]):
            raise OSError("cannot cleanup")
        original_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr("motus.atomic_io.tempfile.mkstemp", _mkstemp)
    monkeypatch.setattr("motus.atomic_io.os.replace", _replace_boom)
    monkeypatch.setattr(Path, "unlink", _unlink_boom)

    with pytest.raises(OSError, match="boom"):
        atomic_write_text(target, "new\n")

    assert target.read_text(encoding="utf-8") == "old\n"
    original_unlink(Path(created_tmp["path"]), missing_ok=True)


def test_fsync_dir_swallows_open_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _open_boom(*args: object, **kwargs: object) -> int:
        raise OSError("boom")

    monkeypatch.setattr("motus.atomic_io.os.open", _open_boom)
    atomic_io._fsync_dir(tmp_path)


def test_fsync_dir_without_o_directory_flag_swallows_close_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delattr("motus.atomic_io.os", "O_DIRECTORY", raising=False)

    def _open_ok(*args: object, **kwargs: object) -> int:
        return 123

    def _close_boom(fd: int) -> None:
        raise OSError("boom")

    monkeypatch.setattr("motus.atomic_io.os.open", _open_ok)
    monkeypatch.setattr("motus.atomic_io.os.fsync", lambda fd: None)
    monkeypatch.setattr("motus.atomic_io.os.close", _close_boom)

    atomic_io._fsync_dir(tmp_path)


def test_fsync_dir_swallows_fsync_errors_and_closes_fd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    closed: list[int] = []
    original_close = os.close

    def _fsync_boom(fd: int) -> None:
        raise OSError("boom")

    def _close(fd: int) -> None:
        closed.append(fd)
        original_close(fd)

    monkeypatch.setattr("motus.atomic_io.os.fsync", _fsync_boom)
    monkeypatch.setattr("motus.atomic_io.os.close", _close)

    atomic_io._fsync_dir(tmp_path)
    assert closed
