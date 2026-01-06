from __future__ import annotations

import json
from pathlib import Path

from motus.coordination.trace import (
    DecisionTraceWriter,
    ensure_trace_paths,
    hash_files,
    hash_json,
    write_pack_match_trace,
)
from motus.policy.contracts import (
    GateRegistry,
    GateTier,
    PackDefinition,
    PackRegistry,
    Profile,
    ProfileDefaults,
    ProfileRegistry,
    VaultPolicyBundle,
)


def _make_policy(tmp_path: Path) -> VaultPolicyBundle:
    pack = PackDefinition(
        id="pack-python",
        path="core/best-practices/skill-packs/python.json",
        precedence=10,
        scopes=["src/*.py"],
        gate_tier="T0",
        coverage_tags=["python"],
        version="1.0.0",
        owner="test",
        status="active",
        replacement="",
    )
    pack_registry = PackRegistry(version="1.0.0", packs=[pack])
    gate_registry = GateRegistry(version="1.0.0", tiers=[GateTier("T0", "T0", "")], gates=[])
    profile_registry = ProfileRegistry(
        version="1.0.0",
        profiles=[Profile(id="personal", description="", defaults=ProfileDefaults(3, "T0"))],
    )
    return VaultPolicyBundle(
        vault_dir=tmp_path,
        pack_registry=pack_registry,
        gate_registry=gate_registry,
        profile_registry=profile_registry,
    )


def test_decision_trace_writer_hash_chain(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    evidence_dir = repo_dir / ".motus" / "evidence" / "run-1"
    evidence_dir.mkdir(parents=True)

    trace_paths = ensure_trace_paths(
        repo_dir=repo_dir,
        evidence_dir=evidence_dir,
        run_id="run-1",
        created_at="2025-01-01T00:00:00+00:00",
    )

    stdout_path = evidence_dir / "logs" / "001-GATE.stdout.txt"
    stderr_path = evidence_dir / "logs" / "001-GATE.stderr.txt"
    meta_path = evidence_dir / "logs" / "001-GATE.meta.txt"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_path.write_text("ok", encoding="utf-8")
    stderr_path.write_text("", encoding="utf-8")
    meta_path.write_text("exit_code: 0", encoding="utf-8")

    inputs_hash = hash_json({"gate_id": "GATE-TEST"})
    outputs_hash = hash_files([stdout_path, stderr_path, meta_path], extra="exit_code:0")

    writer = DecisionTraceWriter(trace_paths.decision_trace_paths)
    writer.append_event(
        {
            "event_id": "evt-1",
            "timestamp": "2025-01-01T00:00:00+00:00",
            "step": "gate/GATE-TEST",
            "status": "pass",
            "reason_codes": [],
            "inputs_hash": inputs_hash,
            "outputs_hash": outputs_hash,
            "evidence_refs": [
                "logs/001-GATE.stdout.txt",
                "logs/001-GATE.stderr.txt",
                "logs/001-GATE.meta.txt",
            ],
            "duration_ms": 5,
        }
    )

    lines = trace_paths.decision_trace_paths[0].read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["event_hash"].startswith("sha256:")
    assert payload["inputs_hash"] == inputs_hash
    assert payload["outputs_hash"] == outputs_hash


def test_pack_match_trace(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    policy = _make_policy(tmp_path)
    output_path = tmp_path / "pack_match_trace.json"

    payload = write_pack_match_trace(
        changed_files=["src/app.py", "README.md"],
        policy=policy,
        created_at="2025-01-01T00:00:00+00:00",
        output_paths=[output_path],
        plan_id="plan-1",
    )

    assert output_path.exists()
    assert payload["plan_id"] == "plan-1"
    entries = payload["entries"]
    assert entries[0]["matched_packs"] == ["pack-python"]
    assert entries[1]["matched_packs"] == []
