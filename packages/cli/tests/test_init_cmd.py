from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

from motus.commands.init_cmd import init_command
from motus.motus_fs import BOOTSTRAP_RELEASE_VERSION, MOTUS_TREE_DIRS


def _assert_tree(root: Path) -> None:
    motus_dir = root / ".motus"
    assert motus_dir.exists()
    for rel in MOTUS_TREE_DIRS:
        p = motus_dir / rel
        assert p.is_dir(), f"expected directory: {p}"


def test_init_full_creates_tree_and_current_symlink(tmp_path: Path) -> None:
    init_command(Namespace(full=True, lite=False, integrate=None, path=str(tmp_path), force=False))
    _assert_tree(tmp_path)

    current = tmp_path / ".motus" / "current"
    assert current.is_symlink()
    assert current.resolve() == (tmp_path / ".motus" / "releases" / BOOTSTRAP_RELEASE_VERSION)


def test_init_integrate_is_additive_and_writes_config(tmp_path: Path) -> None:
    # Pre-existing content must remain untouched.
    sentinel_dir = tmp_path / "existing-notes"
    sentinel_dir.mkdir()
    sentinel_file = sentinel_dir / "note.txt"
    sentinel_file.write_text("hello\n", encoding="utf-8")

    init_command(Namespace(full=False, lite=False, integrate=str(tmp_path), path=".", force=False))

    _assert_tree(tmp_path)
    assert sentinel_file.read_text(encoding="utf-8") == "hello\n"

    cfg = tmp_path / ".motus" / "project" / "config" / "init.yaml"
    assert cfg.exists()
    content = cfg.read_text(encoding="utf-8")
    assert "init_mode: integrate" in content
    assert f"vault_root: {tmp_path}" in content


def test_init_lite_uses_packaged_release_dir_when_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    packaged = tmp_path / "packaged-release"
    packaged.mkdir()

    monkeypatch.setenv("MOTUS_PACKAGED_RELEASE_DIR", str(packaged))
    init_command(Namespace(full=False, lite=True, integrate=None, path=str(tmp_path), force=False))

    current = tmp_path / ".motus" / "current"
    assert current.is_symlink()
    assert current.resolve() == packaged


def test_init_rerun_is_idempotent(tmp_path: Path) -> None:
    init_command(Namespace(full=True, lite=False, integrate=None, path=str(tmp_path), force=False))
    init_command(Namespace(full=True, lite=False, integrate=None, path=str(tmp_path), force=False))
    _assert_tree(tmp_path)


def test_existing_malformed_motus_dir_fails_closed(tmp_path: Path) -> None:
    motus_dir = tmp_path / ".motus"
    motus_dir.mkdir()
    # Missing required dirs => should fail without --force
    with pytest.raises(Exception):
        init_command(Namespace(full=True, lite=False, integrate=None, path=str(tmp_path), force=False))


def test_force_repairs_missing_dirs(tmp_path: Path) -> None:
    motus_dir = tmp_path / ".motus"
    motus_dir.mkdir()

    init_command(Namespace(full=True, lite=False, integrate=None, path=str(tmp_path), force=True))
    _assert_tree(tmp_path)


def test_current_must_be_symlink(tmp_path: Path) -> None:
    init_command(Namespace(full=True, lite=False, integrate=None, path=str(tmp_path), force=False))
    current = tmp_path / ".motus" / "current"
    assert current.is_symlink()

    current.unlink()
    current.write_text("not a symlink\n", encoding="utf-8")

    with pytest.raises(Exception):
        init_command(Namespace(full=True, lite=False, integrate=None, path=str(tmp_path), force=False))


def test_init_writes_valid_yaml(tmp_path: Path) -> None:
    init_command(Namespace(full=False, lite=False, integrate=str(tmp_path), path=".", force=False))
    cfg = tmp_path / ".motus" / "project" / "config" / "init.yaml"
    data = cfg.read_text(encoding="utf-8")
    assert "created_at" in data

