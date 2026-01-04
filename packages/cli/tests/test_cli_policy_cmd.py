from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest


def _fixture_dir() -> Path:
    return Path(__file__).parent / "fixtures" / "vault_policy"


def _write_vault_tree(tmp_path: Path) -> Path:
    fixtures = _fixture_dir()
    registry_src = fixtures / "registry.json"
    gates_src = fixtures / "gates.json"
    profiles_src = fixtures / "profiles.json"
    evidence_schema_src = fixtures / "evidence-manifest.schema.json"

    registry_dest = tmp_path / "core/best-practices/skill-packs/registry.json"
    registry_dest.parent.mkdir(parents=True, exist_ok=True)
    registry_dest.write_text(registry_src.read_text(encoding="utf-8"), encoding="utf-8")

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


def test_policy_plan_help_exists(capsys) -> None:
    with patch("sys.argv", ["motus", "policy", "plan", "--help"]):
        from motus.cli.core import main

        with pytest.raises(SystemExit) as e:
            main()

    assert e.value.code == 0
    out = capsys.readouterr().out
    assert "usage: motus policy plan" in out


def test_policy_run_help_exists(capsys) -> None:
    with patch("sys.argv", ["motus", "policy", "run", "--help"]):
        from motus.cli.core import main

        with pytest.raises(SystemExit) as e:
            main()

    assert e.value.code == 0
    out = capsys.readouterr().out
    assert "usage: motus policy run" in out


def test_policy_verify_help_exists(capsys) -> None:
    with patch("sys.argv", ["motus", "policy", "verify", "--help"]):
        from motus.cli.core import main

        with pytest.raises(SystemExit) as e:
            main()

    assert e.value.code == 0
    out = capsys.readouterr().out
    assert "usage: motus policy verify" in out


def test_policy_prune_help_exists(capsys) -> None:
    with patch("sys.argv", ["motus", "policy", "prune", "--help"]):
        from motus.cli.core import main

        with pytest.raises(SystemExit) as e:
            main()

    assert e.value.code == 0
    out = capsys.readouterr().out
    assert "usage: motus policy prune" in out


def test_policy_plan_requires_change_input(tmp_path: Path) -> None:
    vault_dir = _write_vault_tree(tmp_path / "vault")
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    with patch(
        "sys.argv",
        [
            "motus",
            "policy",
            "plan",
            "--vault-dir",
            str(vault_dir),
            "--repo",
            str(repo_dir),
        ],
    ):
        from motus.cli.core import main

        with pytest.raises(SystemExit) as e:
            main()

    # argparse error for missing required mutual-exclusive group
    assert e.value.code == 2


def test_policy_plan_outputs_deterministic_plan(tmp_path: Path, capsys) -> None:
    vault_dir = _write_vault_tree(tmp_path / "vault")
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    with patch(
        "sys.argv",
        [
            "motus",
            "policy",
            "plan",
            "--vault-dir",
            str(vault_dir),
            "--repo",
            str(repo_dir),
            "--profile",
            "personal",
            "--files",
            "src/example.py",
        ],
    ):
        from motus.cli.core import main

        main()

    out = capsys.readouterr().out
    assert "profile_id: personal" in out
    assert "gate_tier: T0" in out
    assert "BP-PACK-BASELINE" in out
    assert "GATE-INTAKE-001" in out
    assert "GATE-PLAN-001" in out
    assert "gate_details:" in out


def test_policy_run_exits_with_runner_code(tmp_path: Path) -> None:
    vault_dir = _write_vault_tree(tmp_path / "vault")
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    evidence_root = tmp_path / "evidence"
    evidence_dir = evidence_root / "run-123"
    manifest_path = evidence_dir / "manifest.json"
    summary_path = evidence_dir / "summary.md"
    evidence_dir.mkdir(parents=True)
    manifest_path.write_text(json.dumps({"run_id": "run-123"}), encoding="utf-8")
    summary_path.write_text("# summary\n", encoding="utf-8")

    from motus.policy.run import RunResult

    with patch(
        "motus.policy.runner.run_gate_plan",
        return_value=RunResult(
            exit_code=7,
            evidence_dir=evidence_dir,
            manifest_path=manifest_path,
            summary_path=summary_path,
        ),
    ):
        with patch(
            "sys.argv",
            [
                "motus",
                "policy",
                "run",
                "--vault-dir",
                str(vault_dir),
                "--repo",
                str(repo_dir),
                "--profile",
                "personal",
                "--files",
                "src/example.py",
                "--evidence-dir",
                str(evidence_root),
            ],
        ):
            from motus.cli.core import main

            with pytest.raises(SystemExit) as e:
                main()

    assert e.value.code == 7
