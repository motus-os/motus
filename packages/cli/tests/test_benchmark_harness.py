from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from motus.bench.harness import BenchmarkHarness, BenchmarkTask
from motus.policy.reason_codes import RECON_UNTRACKED_DELTA


def _fixture_policy_dir() -> Path:
    return Path(__file__).parent / "fixtures" / "vault_policy"


def _write_minimal_vault_tree(tmp_path: Path) -> Path:
    fixtures = _fixture_policy_dir()
    registry_src = fixtures / "registry.json"
    profiles_src = fixtures / "profiles.json"
    schema_src = fixtures / "evidence-manifest.schema.json"

    registry_dest = tmp_path / "core/best-practices/skill-packs/registry.json"
    registry_dest.parent.mkdir(parents=True, exist_ok=True)
    registry_dest.write_text(registry_src.read_text(encoding="utf-8"), encoding="utf-8")

    profiles_dest = tmp_path / "core/best-practices/profiles/profiles.json"
    profiles_dest.parent.mkdir(parents=True, exist_ok=True)
    profiles_dest.write_text(profiles_src.read_text(encoding="utf-8"), encoding="utf-8")

    gates_dest = tmp_path / "core/best-practices/gates.json"
    gates_dest.parent.mkdir(parents=True, exist_ok=True)
    gates_dest.write_text(
        json.dumps(
            {
                "version": "0.1.0",
                "tiers": [{"id": "T0", "name": "Tier 0", "description": "Fast checks"}],
                "gates": [
                    {
                        "id": "GATE-INTAKE-001",
                        "tier": "T0",
                        "kind": "intake",
                        "description": "DoR",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    schema_dest = tmp_path / "core/best-practices/control-plane/evidence-manifest.schema.json"
    schema_dest.parent.mkdir(parents=True, exist_ok=True)
    schema_dest.write_text(schema_src.read_text(encoding="utf-8"), encoding="utf-8")

    return tmp_path


def _git(repo_dir: Path, argv: list[str]) -> None:
    proc = subprocess.run(["git", *argv], cwd=repo_dir, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def _build_repo(repo_dir: Path) -> None:
    (repo_dir / "src").mkdir(parents=True, exist_ok=True)
    (repo_dir / "src/app.py").write_text("VALUE = 0\n", encoding="utf-8")
    (repo_dir / "README.md").write_text("baseline\n", encoding="utf-8")

    _git(repo_dir, ["init"])
    _git(repo_dir, ["config", "user.email", "bench@example.com"])
    _git(repo_dir, ["config", "user.name", "Motus Bench"])
    _git(repo_dir, ["add", "-A"])
    _git(repo_dir, ["commit", "--allow-empty", "-m", "init"])


def _evaluate_has_changed(repo_dir: Path, paths: list[str]) -> bool:
    for rel in paths:
        if "CHANGED" not in (repo_dir / rel).read_text(encoding="utf-8"):
            return False
    return True


def test_benchmark_harness_emits_deterministic_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault_dir = _write_minimal_vault_tree(tmp_path / "vault")

    monotonic_calls = {"value": 0}

    def fake_monotonic_ns() -> int:
        monotonic_calls["value"] += 1_000_000
        return monotonic_calls["value"]

    harness = BenchmarkHarness(
        vault_dir=vault_dir,
        profile_id="personal",
        now_iso=lambda: "2025-01-01T00:00:00Z",
        monotonic_ns=fake_monotonic_ns,
    )

    tasks = [
        BenchmarkTask(
            task_id="01-happy-path",
            description="Modify one in-scope file",
            declared_scope=("src/app.py",),
            build_fixture=_build_repo,
            apply_changes=lambda repo: (repo / "src/app.py").write_text(
                "VALUE = 0\n# CHANGED\n", encoding="utf-8"
            ),
            evaluate=lambda repo: _evaluate_has_changed(repo, ["src/app.py"]),
        ),
        BenchmarkTask(
            task_id="02-scope-creep",
            description="Modify an extra file outside declared scope",
            declared_scope=("src/app.py",),
            build_fixture=_build_repo,
            apply_changes=lambda repo: (
                (repo / "src/app.py").write_text("VALUE = 0\n# CHANGED\n", encoding="utf-8"),
                (repo / "README.md").write_text("baseline\n# CHANGED\n", encoding="utf-8"),
            ),
            evaluate=lambda repo: _evaluate_has_changed(repo, ["src/app.py", "README.md"]),
        ),
        BenchmarkTask(
            task_id="03-expanded-scope",
            description="Modify two files with both in declared scope",
            declared_scope=("src/app.py", "README.md"),
            build_fixture=_build_repo,
            apply_changes=lambda repo: (
                (repo / "src/app.py").write_text("VALUE = 0\n# CHANGED\n", encoding="utf-8"),
                (repo / "README.md").write_text("baseline\n# CHANGED\n", encoding="utf-8"),
            ),
            evaluate=lambda repo: _evaluate_has_changed(repo, ["src/app.py", "README.md"]),
        ),
    ]

    report = harness.run(tasks=tasks)
    payload = report.to_dict()

    assert payload["version"] == "0.1.1"
    assert [t["task_id"] for t in payload["tasks"]] == [
        "01-happy-path",
        "02-scope-creep",
        "03-expanded-scope",
    ]

    by_id = {t["task_id"]: t for t in payload["tasks"]}

    happy = by_id["01-happy-path"]
    assert happy["declared_scope"] == ["src/app.py"]
    assert happy["baseline"]["ok"] is True
    assert happy["baseline"]["delta_scope"]["in_scope"] is True
    assert {"path": "src/app.py", "status": "M"} in happy["baseline"]["diff"]["name_status"]
    assert happy["motus"]["ok"] is True
    assert happy["motus"]["enforcement"]["exit_code"] == 0
    assert happy["motus"]["enforcement"]["verification"]["ok"] is True

    creep = by_id["02-scope-creep"]
    assert creep["declared_scope"] == ["src/app.py"]
    assert creep["baseline"]["ok"] is True
    assert creep["baseline"]["delta_scope"]["in_scope"] is False
    assert {"path": "README.md", "status": "M"} in creep["baseline"]["diff"]["name_status"]
    assert creep["motus"]["ok"] is False
    assert creep["motus"]["enforcement"]["exit_code"] == 1
    assert creep["motus"]["enforcement"]["verification"]["ok"] is False
    assert RECON_UNTRACKED_DELTA in set(
        creep["motus"]["enforcement"]["verification"]["reason_codes"]
    )
    assert creep["motus"]["enforcement"]["untracked_delta_count"] == 1

    expanded = by_id["03-expanded-scope"]
    assert expanded["declared_scope"] == ["src/app.py", "README.md"]
    assert expanded["baseline"]["ok"] is True
    assert expanded["baseline"]["delta_scope"]["in_scope"] is True
    assert expanded["motus"]["ok"] is True
    assert expanded["motus"]["enforcement"]["exit_code"] == 0
    assert expanded["motus"]["enforcement"]["verification"]["ok"] is True

    assert all(task["baseline"]["duration_ms"] == 1 for task in payload["tasks"])
    assert all(task["motus"]["duration_ms"] == 1 for task in payload["tasks"])
