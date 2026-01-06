"""Tests for path migration helpers."""

from motus.migration.path_migration import find_workspace_dir, resolve_workspace_dir


def test_resolve_workspace_dir_prefers_motus(tmp_path):
    motus_dir = tmp_path / ".motus"
    motus_dir.mkdir()
    legacy_dir = tmp_path / ".mc"
    legacy_dir.mkdir()

    resolution = resolve_workspace_dir(tmp_path)
    assert resolution.path == motus_dir
    assert resolution.is_legacy is False


def test_resolve_workspace_dir_legacy_when_only_mc(tmp_path):
    legacy_dir = tmp_path / ".mc"
    legacy_dir.mkdir()

    resolution = resolve_workspace_dir(tmp_path)
    assert resolution.path == legacy_dir
    assert resolution.is_legacy is True


def test_resolve_workspace_dir_creates_motus(tmp_path):
    resolution = resolve_workspace_dir(tmp_path, create=True)
    assert resolution.path == tmp_path / ".motus"
    assert resolution.path.exists()


def test_find_workspace_dir_walks_up(tmp_path):
    legacy_dir = tmp_path / ".mc"
    legacy_dir.mkdir()
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)

    resolution = find_workspace_dir(nested)
    assert resolution is not None
    assert resolution.path == legacy_dir
