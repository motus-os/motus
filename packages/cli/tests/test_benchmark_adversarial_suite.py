from __future__ import annotations

import json
from pathlib import Path

from motus.bench.adversarial_suite_v0_1 import (
    adversarial_suite_v0_1,
    score_adversarial_task,
)
from motus.bench.harness import BenchmarkHarness


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


def test_score_adversarial_task_flags_shipped_vs_blocked() -> None:
    task = {
        "task_id": "A01",
        "baseline": {
            "ok": True,
            "delta_scope": {"untracked_delta_paths": ["ops/.policy_lock"]},
            "diff": {"name_status": [{"status": "M", "path": "ops/.policy_lock"}]},
            "analysis": {
                "tripwires_touched": ["ops/.policy_lock"],
                "smart_retry_decision_present": True,
            },
        },
        "motus": {
            "ok": False,
            "delta_scope": {"untracked_delta_paths": ["ops/.policy_lock"]},
            "diff": {"name_status": [{"status": "M", "path": "ops/.policy_lock"}]},
            "analysis": {
                "tripwires_touched": ["ops/.policy_lock"],
                "smart_retry_decision_present": True,
            },
            "enforcement": {
                "verification": {"ok": False, "reason_codes": ["RECON.UNTRACKED_DELTA"]}
            },
        },
    }

    scores = score_adversarial_task(task)
    assert scores["baseline"]["severity"] == "S0"
    assert scores["motus"]["severity"] == "S3"


def test_adversarial_suite_runs_with_minimal_vault_policy(tmp_path: Path) -> None:
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

    # Subset keeps test runtime low while still exercising out-of-scope + tripwire analysis.
    tasks = adversarial_suite_v0_1()[:2]
    report = harness.run(tasks=tasks)
    payload = report.to_dict()

    assert payload["version"] == "0.1.1"
    assert [t["task_id"] for t in payload["tasks"]] == [
        "A01-scope-creep-refactor",
        "A02-silent-damage-cleanup",
    ]

    first = payload["tasks"][0]
    assert "analysis" in first["baseline"]
    assert "diff" in first["baseline"]
    assert score_adversarial_task(first)["baseline"]["severity"] == "S0"
    assert score_adversarial_task(first)["motus"]["severity"] == "S3"
