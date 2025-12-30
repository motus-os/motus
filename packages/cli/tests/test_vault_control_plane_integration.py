from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest


def _fixture_vault_policy_dir() -> Path:
    return Path(__file__).parent / "fixtures" / "vault_policy"


def _write_vault_tree(tmp_path: Path, *, registry_override: dict | None = None) -> Path:
    fixtures = _fixture_vault_policy_dir()

    registry_src = fixtures / "registry.json"
    gates_src = fixtures / "gates.json"
    profiles_src = fixtures / "profiles.json"
    evidence_schema_src = fixtures / "evidence-manifest.schema.json"

    registry_dest = tmp_path / "core/best-practices/skill-packs/registry.json"
    registry_dest.parent.mkdir(parents=True, exist_ok=True)
    if registry_override is None:
        registry_dest.write_text(registry_src.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        registry_dest.write_text(
            json.dumps(registry_override, indent=2, sort_keys=True), encoding="utf-8"
        )

    gates_dest = tmp_path / "core/best-practices/gates.json"
    gates_dest.parent.mkdir(parents=True, exist_ok=True)
    gates_dest.write_text(gates_src.read_text(encoding="utf-8"), encoding="utf-8")

    profiles_dest = tmp_path / "core/best-practices/profiles/profiles.json"
    profiles_dest.parent.mkdir(parents=True, exist_ok=True)
    profiles_dest.write_text(profiles_src.read_text(encoding="utf-8"), encoding="utf-8")

    evidence_schema_dest = (
        tmp_path / "core/best-practices/control-plane/evidence-manifest.schema.json"
    )
    evidence_schema_dest.parent.mkdir(parents=True, exist_ok=True)
    evidence_schema_dest.write_text(
        evidence_schema_src.read_text(encoding="utf-8"), encoding="utf-8"
    )

    return tmp_path


def _write_minimal_python_repo(repo_dir: Path, *, failing_test: bool = False) -> None:
    repo_dir.mkdir(parents=True, exist_ok=True)

    (repo_dir / "src/example_pkg").mkdir(parents=True, exist_ok=True)
    (repo_dir / "src/example_pkg/__init__.py").write_text("", encoding="utf-8")
    (repo_dir / "src/example_pkg/app.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n", encoding="utf-8"
    )

    (repo_dir / "tests").mkdir(parents=True, exist_ok=True)
    if failing_test:
        test_body = "def test_fail():\n    assert False\n"
    else:
        test_body = "def test_ok():\n    assert True\n"
    (repo_dir / "tests/test_smoke.py").write_text(test_body, encoding="utf-8")

    # Minimal pyproject.toml so Motus harness detection can pick pytest + ruff.
    (repo_dir / "pyproject.toml").write_text(
        "\n".join(
            [
                "[tool.pytest.ini_options]",
                "testpaths = ['tests']",
                "",
                "[tool.ruff]",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    subprocess.run(["git", "init", "-q"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_dir, check=True)
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-m", "init", "-q"], cwd=repo_dir, check=True)


def _patch_deterministic_run_ids(monkeypatch, *, run_hex: str) -> None:
    from motus.policy import runner as runner_mod

    run_uuid = uuid.UUID(hex=run_hex)
    monkeypatch.setattr(runner_mod.uuid, "uuid4", lambda: run_uuid)
    monkeypatch.setattr(runner_mod, "_now_iso_utc", lambda: "2025-01-01T00:00:00Z")


def test_control_plane_happy_path_run_and_verify(tmp_path: Path, monkeypatch) -> None:
    vault_dir = _write_vault_tree(tmp_path / "vault")
    repo_dir = tmp_path / "repo"
    _write_minimal_python_repo(repo_dir, failing_test=False)

    evidence_root = tmp_path / "evidence"

    monkeypatch.setenv("MC_EVIDENCE_KEY_ID", "local-dev")
    monkeypatch.setenv("MC_EVIDENCE_SIGNING_KEY", "dev-secret")
    _patch_deterministic_run_ids(monkeypatch, run_hex="11111111111111111111111111111111")

    with patch(
        "sys.argv",
        [
            "mc",
            "policy",
            "run",
            "--vault-dir",
            str(vault_dir),
            "--repo",
            str(repo_dir),
            "--profile",
            "team",
            "--files",
            "src/example_pkg/app.py",
            "--evidence-dir",
            str(evidence_root),
        ],
    ):
        from motus.cli.core import main

        with pytest.raises(SystemExit) as e:
            main()

    assert e.value.code == 0

    run_dir = evidence_root / "11111111111111111111111111111111"
    assert (run_dir / "manifest.json").exists()
    assert (run_dir / "summary.md").exists()

    from motus.policy.verify import verify_evidence_bundle

    verified = verify_evidence_bundle(evidence_dir=run_dir, vault_dir=vault_dir)
    assert verified.ok


def test_control_plane_fail_closed_writes_evidence(tmp_path: Path, monkeypatch) -> None:
    vault_dir = _write_vault_tree(tmp_path / "vault")
    repo_dir = tmp_path / "repo"
    _write_minimal_python_repo(repo_dir, failing_test=True)

    evidence_root = tmp_path / "evidence"

    monkeypatch.setenv("MC_EVIDENCE_KEY_ID", "local-dev")
    monkeypatch.setenv("MC_EVIDENCE_SIGNING_KEY", "dev-secret")
    _patch_deterministic_run_ids(monkeypatch, run_hex="22222222222222222222222222222222")

    with patch(
        "sys.argv",
        [
            "mc",
            "policy",
            "run",
            "--vault-dir",
            str(vault_dir),
            "--repo",
            str(repo_dir),
            "--profile",
            "team",
            "--files",
            "src/example_pkg/app.py",
            "--evidence-dir",
            str(evidence_root),
        ],
    ):
        from motus.cli.core import main

        with pytest.raises(SystemExit) as e:
            main()

    assert e.value.code != 0

    run_dir = evidence_root / "22222222222222222222222222222222"
    manifest_path = run_dir / "manifest.json"
    assert manifest_path.exists()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert any(gr.get("status") == "fail" for gr in manifest.get("gate_results", []))


def test_control_plane_scope_creep_detected_by_reconciliation(tmp_path: Path, monkeypatch) -> None:
    vault_dir = _write_vault_tree(tmp_path / "vault")
    repo_dir = tmp_path / "repo"
    _write_minimal_python_repo(repo_dir, failing_test=False)

    # Introduce an out-of-scope change (untracked file) not included in --files.
    (repo_dir / "README.md").write_text("scope creep\n", encoding="utf-8")

    evidence_root = tmp_path / "evidence"

    monkeypatch.setenv("MC_EVIDENCE_KEY_ID", "local-dev")
    monkeypatch.setenv("MC_EVIDENCE_SIGNING_KEY", "dev-secret")
    _patch_deterministic_run_ids(monkeypatch, run_hex="33333333333333333333333333333333")

    with patch(
        "sys.argv",
        [
            "mc",
            "policy",
            "run",
            "--vault-dir",
            str(vault_dir),
            "--repo",
            str(repo_dir),
            "--profile",
            "team",
            "--files",
            "src/example_pkg/app.py",
            "--evidence-dir",
            str(evidence_root),
        ],
    ):
        from motus.cli.core import main

        with pytest.raises(SystemExit) as e:
            main()

    assert e.value.code != 0

    run_dir = evidence_root / "33333333333333333333333333333333"
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert "README.md" in (manifest.get("untracked_delta_paths") or [])

    from motus.policy.verify import verify_evidence_bundle

    verified = verify_evidence_bundle(evidence_dir=run_dir, vault_dir=vault_dir)
    assert not verified.ok
    assert "RECON.UNTRACKED_DELTA" in verified.reason_codes


def test_control_plane_pack_cap_exceeded_is_actionable(tmp_path: Path) -> None:
    registry_override = {
        "version": "0.1.0",
        "packs": [
            {
                "id": "BP-PACK-ONE",
                "path": "core/best-practices/skill-packs/REGISTRY.md",
                "precedence": 100,
                "scopes": ["**/*"],
                "gate_tier": "T0",
                "coverage_tags": ["CDIO:all"],
                "version": "0.1.0",
                "owner": "Example",
                "status": "active",
                "replacement": "",
            },
            {
                "id": "BP-PACK-TWO",
                "path": "core/best-practices/skill-packs/REGISTRY.md",
                "precedence": 90,
                "scopes": ["**/*"],
                "gate_tier": "T0",
                "coverage_tags": ["CDIO:all"],
                "version": "0.1.0",
                "owner": "Example",
                "status": "active",
                "replacement": "",
            },
        ],
    }
    vault_dir = _write_vault_tree(tmp_path / "vault", registry_override=registry_override)
    repo_dir = tmp_path / "repo"
    _write_minimal_python_repo(repo_dir, failing_test=False)

    with patch(
        "sys.argv",
        [
            "mc",
            "policy",
            "plan",
            "--vault-dir",
            str(vault_dir),
            "--repo",
            str(repo_dir),
            "--profile",
            "personal",
            "--pack-cap",
            "1",
            "--files",
            "src/example_pkg/app.py",
        ],
    ):
        from motus.cli.core import main

        with pytest.raises(SystemExit) as e:
            main()

    assert e.value.code == 2


def test_control_plane_profile_defaults_change_gate_tier(tmp_path: Path, capsys) -> None:
    vault_dir = _write_vault_tree(tmp_path / "vault")
    repo_dir = tmp_path / "repo"
    _write_minimal_python_repo(repo_dir, failing_test=False)

    def _plan_json(profile_id: str) -> dict:
        with patch(
            "sys.argv",
            [
                "mc",
                "policy",
                "plan",
                "--vault-dir",
                str(vault_dir),
                "--repo",
                str(repo_dir),
                "--profile",
                profile_id,
                "--files",
                "src/example_pkg/app.py",
                "--json",
            ],
        ):
            from motus.cli.core import main

            main()
        out = capsys.readouterr().out
        return json.loads(out)

    personal = _plan_json("personal")
    team = _plan_json("team")

    assert personal["gate_tier"] == "T0"
    assert team["gate_tier"] == "T1"
    assert "GATE-TOOL-001" not in personal["gates"]
    assert "GATE-TOOL-001" in team["gates"]
