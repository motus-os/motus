from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

import motus.motus_fs as motus_fs
from motus.motus_fs import (
    DEFAULT_NAMESPACE_ACL_YAML,
    MOTUS_TREE_DIRS,
    MotusInitError,
    MotusLayout,
    create_motus_tree,
    ensure_current_symlink,
    find_packaged_release_dir,
    repair_motus_tree,
    validate_motus_dir,
    write_init_config_yaml,
)


def _build_motus_tree(root: Path) -> Path:
    motus_dir = root / ".motus"
    for rel in MOTUS_TREE_DIRS:
        (motus_dir / rel).mkdir(parents=True, exist_ok=True)
    return motus_dir


def test_find_packaged_release_dir_returns_none_when_env_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MOTUS_PACKAGED_RELEASE_DIR", raising=False)
    assert find_packaged_release_dir() is None


def test_find_packaged_release_dir_returns_none_for_missing_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    missing = tmp_path / "missing"
    monkeypatch.setenv("MOTUS_PACKAGED_RELEASE_DIR", str(missing))
    assert find_packaged_release_dir() is None


def test_find_packaged_release_dir_returns_existing_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "release"
    target.mkdir()
    monkeypatch.setenv("MOTUS_PACKAGED_RELEASE_DIR", str(target))
    assert find_packaged_release_dir() == target


def test_validate_motus_dir_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(MotusInitError):
        validate_motus_dir(tmp_path / ".motus")


def test_validate_motus_dir_non_dir_raises(tmp_path: Path) -> None:
    motus_dir = tmp_path / ".motus"
    motus_dir.write_text("nope")
    with pytest.raises(MotusInitError):
        validate_motus_dir(motus_dir)


def test_validate_motus_dir_missing_required_dir_raises(tmp_path: Path) -> None:
    motus_dir = tmp_path / ".motus"
    motus_dir.mkdir()
    with pytest.raises(MotusInitError):
        validate_motus_dir(motus_dir)


def test_validate_motus_dir_missing_current_symlink_raises(tmp_path: Path) -> None:
    motus_dir = _build_motus_tree(tmp_path)
    with pytest.raises(MotusInitError):
        validate_motus_dir(motus_dir)


def test_validate_motus_dir_current_not_symlink_raises(tmp_path: Path) -> None:
    motus_dir = _build_motus_tree(tmp_path)
    current = motus_dir / "current"
    current.write_text("not link")
    with pytest.raises(MotusInitError):
        validate_motus_dir(motus_dir)


def test_validate_motus_dir_success(tmp_path: Path) -> None:
    motus_dir = _build_motus_tree(tmp_path)
    current = motus_dir / "current"
    target = motus_dir / "releases" / "0.0.0"
    target.mkdir(parents=True)
    current.symlink_to(os.path.relpath(target, start=current.parent))
    validate_motus_dir(motus_dir)


def test_create_motus_tree_creates_dirs_and_acl(tmp_path: Path) -> None:
    motus_dir = tmp_path / ".motus"
    create_motus_tree(motus_dir)
    assert (motus_dir / "releases").exists()
    acl_path = motus_dir / "project" / "config" / "namespace-acl.yaml"
    assert acl_path.exists()
    assert DEFAULT_NAMESPACE_ACL_YAML in acl_path.read_text(encoding="utf-8")


def test_repair_motus_tree_creates_missing(tmp_path: Path) -> None:
    motus_dir = tmp_path / ".motus"
    repair_motus_tree(motus_dir)
    assert (motus_dir / "state" / "ledger").exists()


def test_repair_motus_tree_raises_on_non_dir(tmp_path: Path) -> None:
    motus_dir = tmp_path / ".motus"
    motus_dir.write_text("nope")
    with pytest.raises(MotusInitError):
        repair_motus_tree(motus_dir)


def test_ensure_current_symlink_requires_existing_dir(tmp_path: Path) -> None:
    link = tmp_path / ".motus" / "current"
    with pytest.raises(MotusInitError):
        ensure_current_symlink(link=link, target_dir=tmp_path / "missing", force=False)


def test_ensure_current_symlink_updates_when_force(tmp_path: Path) -> None:
    motus_dir = tmp_path / ".motus"
    motus_dir.mkdir()
    link = motus_dir / "current"
    target_a = motus_dir / "releases" / "a"
    target_b = motus_dir / "releases" / "b"
    target_a.mkdir(parents=True)
    target_b.mkdir(parents=True)

    link.symlink_to(os.path.relpath(target_a, start=link.parent))

    ensure_current_symlink(link=link, target_dir=target_b, force=True)
    assert Path(os.readlink(link)) == Path(os.path.relpath(target_b, start=link.parent))


def test_ensure_current_symlink_noop_when_same(tmp_path: Path) -> None:
    motus_dir = tmp_path / ".motus"
    motus_dir.mkdir()
    link = motus_dir / "current"
    target = motus_dir / "releases" / "a"
    target.mkdir(parents=True)

    link.symlink_to(os.path.relpath(target, start=link.parent))

    ensure_current_symlink(link=link, target_dir=target, force=False)
    assert Path(os.readlink(link)) == Path(os.path.relpath(target, start=link.parent))


def test_ensure_current_symlink_raises_when_existing_non_symlink(tmp_path: Path) -> None:
    motus_dir = tmp_path / ".motus"
    motus_dir.mkdir()
    link = motus_dir / "current"
    link.write_text("not a link")
    target = motus_dir / "releases" / "a"
    target.mkdir(parents=True)

    with pytest.raises(MotusInitError):
        ensure_current_symlink(link=link, target_dir=target, force=False)


def test_write_init_config_yaml(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(motus_fs, "_utc_now_iso_z", lambda: "2025-01-01T00:00:00Z")

    layout = MotusLayout(root=tmp_path)
    path = write_init_config_yaml(layout, init_mode="fresh")

    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert payload["vault_root"] == str(tmp_path)
    assert payload["created_at"] == "2025-01-01T00:00:00Z"
    assert payload["init_mode"] == "fresh"
