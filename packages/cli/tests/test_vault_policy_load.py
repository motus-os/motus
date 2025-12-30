from __future__ import annotations

import json
from pathlib import Path

import pytest

from motus.exceptions import ConfigError
from motus.policy.load import (
    load_gate_registry,
    load_pack_registry,
    load_profile_registry,
    load_vault_policy,
)


def _fixture_dir() -> Path:
    return Path(__file__).parent / "fixtures" / "vault_policy"


def _write_vault_tree(tmp_path: Path) -> Path:
    fixtures = _fixture_dir()
    registry_src = fixtures / "registry.json"
    gates_src = fixtures / "gates.json"
    profiles_src = fixtures / "profiles.json"

    registry_dest = tmp_path / "core/best-practices/skill-packs/registry.json"
    registry_dest.parent.mkdir(parents=True, exist_ok=True)
    registry_dest.write_text(registry_src.read_text(encoding="utf-8"), encoding="utf-8")

    gates_dest = tmp_path / "core/best-practices/gates.json"
    gates_dest.parent.mkdir(parents=True, exist_ok=True)
    gates_dest.write_text(gates_src.read_text(encoding="utf-8"), encoding="utf-8")

    profiles_dest = tmp_path / "core/best-practices/profiles/profiles.json"
    profiles_dest.parent.mkdir(parents=True, exist_ok=True)
    profiles_dest.write_text(profiles_src.read_text(encoding="utf-8"), encoding="utf-8")

    return tmp_path


def test_load_happy_path_explicit_vault_dir(tmp_path: Path) -> None:
    vault_dir = _write_vault_tree(tmp_path)

    pack_registry = load_pack_registry(vault_dir)
    gate_registry = load_gate_registry(vault_dir)
    profile_registry = load_profile_registry(vault_dir)

    assert pack_registry.version == "0.1.0"
    assert len(pack_registry.packs) >= 1

    assert gate_registry.version == "0.1.0"
    assert len(gate_registry.tiers) >= 1
    assert len(gate_registry.gates) >= 1

    assert profile_registry.version == "0.1.0"
    assert {p.id for p in profile_registry.profiles} >= {"personal", "team"}


def test_load_uses_env_var_when_vault_dir_not_passed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault_dir = _write_vault_tree(tmp_path)
    monkeypatch.setenv("MC_VAULT_DIR", str(vault_dir))

    bundle = load_vault_policy()
    assert bundle.vault_dir == vault_dir
    assert bundle.pack_registry.version == "0.1.0"
    assert bundle.gate_registry.version == "0.1.0"
    assert bundle.profile_registry.version == "0.1.0"


def test_missing_vault_dir_config_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MC_VAULT_DIR", raising=False)
    with pytest.raises(ConfigError, match="Vault directory not configured"):
        load_vault_policy()


def test_missing_policy_file_raises(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    with pytest.raises(ConfigError, match="Vault policy file missing"):
        load_pack_registry(tmp_path)


def test_unsupported_version_raises(tmp_path: Path) -> None:
    vault_dir = _write_vault_tree(tmp_path)
    registry_path = vault_dir / "core/best-practices/skill-packs/registry.json"
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    data["version"] = "9.9.9"
    registry_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ConfigError, match="Unsupported vault policy version"):
        load_pack_registry(vault_dir)


def test_invalid_shape_raises(tmp_path: Path) -> None:
    vault_dir = _write_vault_tree(tmp_path)
    registry_path = vault_dir / "core/best-practices/skill-packs/registry.json"
    registry_path.write_text(json.dumps({"version": "0.1.0"}), encoding="utf-8")

    with pytest.raises(ConfigError, match="Invalid vault policy shape"):
        load_pack_registry(vault_dir)


def test_missing_profiles_file_raises(tmp_path: Path) -> None:
    vault_dir = _write_vault_tree(tmp_path)
    profiles_path = vault_dir / "core/best-practices/profiles/profiles.json"
    profiles_path.unlink()

    with pytest.raises(ConfigError, match="Vault policy file missing"):
        load_profile_registry(vault_dir)
