from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from motus.policy.contracts import (
    GateDefinition,
    GateRegistry,
    GateTier,
    PackRegistry,
    ProfileRegistry,
    VaultPolicyBundle,
)
from motus.policy.loader import GatePlan, PackCap, PolicyVersions
from motus.policy.run import run_gate_plan
from motus.policy.verify import verify_evidence_bundle


def _init_git_repo(repo_dir: Path) -> None:
    repo_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "init", "-q"], cwd=repo_dir, check=True)


def _write_vault_schema(vault_dir: Path) -> None:
    fixtures = Path(__file__).parent / "fixtures" / "vault_policy"
    schema_src = fixtures / "evidence-manifest.schema.json"
    schema_dest = vault_dir / "core/best-practices/control-plane/evidence-manifest.schema.json"
    schema_dest.parent.mkdir(parents=True, exist_ok=True)
    schema_dest.write_text(schema_src.read_text(encoding="utf-8"), encoding="utf-8")


def _policy_with_gates(gates: list[GateDefinition], vault_dir: Path) -> VaultPolicyBundle:
    return VaultPolicyBundle(
        vault_dir=vault_dir,
        pack_registry=PackRegistry(version="0.1.0", packs=[]),
        gate_registry=GateRegistry(
            version="0.1.0",
            tiers=[GateTier(id="T0", name="Tier 0", description="fast")],
            gates=gates,
        ),
        profile_registry=ProfileRegistry(version="0.1.0", profiles=[]),
    )


def _plan_with_gates(*, gate_ids: list[str], profile_id: str) -> GatePlan:
    return GatePlan(
        version="1.0.0",
        profile_id=profile_id,
        policy_versions=PolicyVersions(skill_packs_registry="0.1.0", gates="0.1.0"),
        packs=[],
        pack_versions=[],
        gate_tier="T0",
        gates=gate_ids,
        pack_cap=PackCap(cap=10, selected=0, exceeded=False),
    )


def test_policy_verify_passes_on_untampered_bundle(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    _init_git_repo(repo_dir)
    vault_dir = tmp_path / "vault"
    _write_vault_schema(vault_dir)

    policy = _policy_with_gates(
        gates=[GateDefinition(id="GATE-CMD-1", tier="T0", kind="command", description="cmd")],
        vault_dir=vault_dir,
    )
    plan = _plan_with_gates(gate_ids=["GATE-CMD-1"], profile_id="personal")

    run = run_gate_plan(
        plan=plan,
        declared_files=[],
        repo_dir=repo_dir,
        policy=policy,
        gate_command_overrides={"GATE-CMD-1": [sys.executable, "-c", "print('ok')"]},
        run_id="run-verify-pass",
        created_at="2025-01-01T00:00:00Z",
    )

    result = verify_evidence_bundle(evidence_dir=run.evidence_dir)
    assert result.ok
    assert result.reason_codes == []


def test_policy_verify_detects_artifact_tamper(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    _init_git_repo(repo_dir)
    vault_dir = tmp_path / "vault"
    _write_vault_schema(vault_dir)

    policy = _policy_with_gates(
        gates=[GateDefinition(id="GATE-CMD-1", tier="T0", kind="command", description="cmd")],
        vault_dir=vault_dir,
    )
    plan = _plan_with_gates(gate_ids=["GATE-CMD-1"], profile_id="personal")

    run = run_gate_plan(
        plan=plan,
        declared_files=[],
        repo_dir=repo_dir,
        policy=policy,
        gate_command_overrides={"GATE-CMD-1": [sys.executable, "-c", "print('ok')"]},
        run_id="run-verify-tamper",
        created_at="2025-01-01T00:00:00Z",
    )

    log_file = next(run.evidence_dir.glob("logs/*.stdout.txt"))
    log_file.write_text(log_file.read_text(encoding="utf-8") + "tamper\n", encoding="utf-8")

    result = verify_evidence_bundle(evidence_dir=run.evidence_dir)
    assert not result.ok
    assert "EVIDENCE.ARTIFACT_HASH_MISMATCH" in result.reason_codes


def test_team_profile_requires_signature(monkeypatch, tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    _init_git_repo(repo_dir)
    vault_dir = tmp_path / "vault"
    _write_vault_schema(vault_dir)

    policy = _policy_with_gates(
        gates=[GateDefinition(id="GATE-CMD-1", tier="T0", kind="command", description="cmd")],
        vault_dir=vault_dir,
    )
    plan = _plan_with_gates(gate_ids=["GATE-CMD-1"], profile_id="team")

    monkeypatch.delenv("MC_EVIDENCE_KEY_ID", raising=False)
    monkeypatch.delenv("MC_EVIDENCE_SIGNING_KEY", raising=False)

    run = run_gate_plan(
        plan=plan,
        declared_files=[],
        repo_dir=repo_dir,
        policy=policy,
        gate_command_overrides={"GATE-CMD-1": [sys.executable, "-c", "print('ok')"]},
        run_id="run-team-unsigned",
        created_at="2025-01-01T00:00:00Z",
    )

    assert run.exit_code != 0
    result = verify_evidence_bundle(evidence_dir=run.evidence_dir)
    assert not result.ok
    assert "EVIDENCE.SIGNATURE_REQUIRED" in result.reason_codes


def test_team_profile_signature_verifies(monkeypatch, tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    _init_git_repo(repo_dir)
    vault_dir = tmp_path / "vault"
    _write_vault_schema(vault_dir)

    policy = _policy_with_gates(
        gates=[GateDefinition(id="GATE-CMD-1", tier="T0", kind="command", description="cmd")],
        vault_dir=vault_dir,
    )
    plan = _plan_with_gates(gate_ids=["GATE-CMD-1"], profile_id="team")

    monkeypatch.setenv("MC_EVIDENCE_KEY_ID", "local-dev")
    monkeypatch.setenv("MC_EVIDENCE_SIGNING_KEY", "dev-secret")

    run = run_gate_plan(
        plan=plan,
        declared_files=[],
        repo_dir=repo_dir,
        policy=policy,
        gate_command_overrides={"GATE-CMD-1": [sys.executable, "-c", "print('ok')"]},
        run_id="run-team-signed",
        created_at="2025-01-01T00:00:00Z",
    )

    assert run.exit_code == 0
    result = verify_evidence_bundle(evidence_dir=run.evidence_dir)
    assert result.ok
