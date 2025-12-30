from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from motus.policy.contracts import (
    GateDefinition,
    GateRegistry,
    GateTier,
    PackRegistry,
    ProfileRegistry,
    VaultPolicyBundle,
)
from motus.policy.loader import GatePlan, PackCap, PolicyVersions
from motus.policy.permit import (
    Permit,
    PermitValidationError,
    issue_permit_hmac_sha256,
    validate_permit_hmac_sha256,
)
from motus.policy.run import run_gate_plan


def test_validate_permit_missing() -> None:
    with pytest.raises(PermitValidationError) as exc:
        validate_permit_hmac_sha256(
            None,
            expected_run_id="run-1",
            expected_tool_id="tool-1",
            expected_plan_hash="plan-1",
            expected_cwd="/repo",
            expected_argv_segments=[["echo", "ok"]],
            expected_scope_paths=["README.md"],
            signing_key="secret",
        )
    assert exc.value.reason_code == "PERMIT.MISSING"


def test_validate_permit_invalid_signature() -> None:
    permit = issue_permit_hmac_sha256(
        permit_id="permit-1",
        run_id="run-1",
        tool_id="tool-1",
        plan_hash="plan-1",
        issued_at="2025-01-01T00:00:00Z",
        expires_at="2025-01-01T00:30:00+00:00",
        cwd="/repo",
        argv_segments=[["echo", "ok"]],
        scope_paths=["README.md"],
        signing_key="secret",
        key_id="k1",
    )

    tampered = Permit.from_dict({**permit.to_dict(), "signature": "hmac-sha256:deadbeef"})
    with pytest.raises(PermitValidationError) as exc:
        validate_permit_hmac_sha256(
            tampered,
            expected_run_id="run-1",
            expected_tool_id="tool-1",
            expected_plan_hash="plan-1",
            expected_cwd="/repo",
            expected_argv_segments=[["echo", "ok"]],
            expected_scope_paths=["README.md"],
            signing_key="secret",
            now=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        )
    assert exc.value.reason_code == "PERMIT.INVALID_SIGNATURE"


def test_validate_permit_mismatched_scope() -> None:
    permit = issue_permit_hmac_sha256(
        permit_id="permit-1",
        run_id="run-1",
        tool_id="tool-1",
        plan_hash="plan-1",
        issued_at="2025-01-01T00:00:00Z",
        expires_at="2025-01-01T00:30:00+00:00",
        cwd="/repo",
        argv_segments=[["echo", "ok"]],
        scope_paths=["README.md"],
        signing_key="secret",
    )

    with pytest.raises(PermitValidationError) as exc:
        validate_permit_hmac_sha256(
            permit,
            expected_run_id="run-1",
            expected_tool_id="tool-1",
            expected_plan_hash="plan-1",
            expected_cwd="/repo",
            expected_argv_segments=[["echo", "ok"]],
            expected_scope_paths=["src/app.py"],
            signing_key="secret",
            now=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        )
    assert exc.value.reason_code == "PERMIT.MISMATCH_SCOPE"


def test_validate_permit_mismatched_args() -> None:
    permit = issue_permit_hmac_sha256(
        permit_id="permit-1",
        run_id="run-1",
        tool_id="tool-1",
        plan_hash="plan-1",
        issued_at="2025-01-01T00:00:00Z",
        expires_at="2025-01-01T00:30:00+00:00",
        cwd="/repo",
        argv_segments=[["echo", "ok"]],
        scope_paths=["README.md"],
        signing_key="secret",
    )

    with pytest.raises(PermitValidationError) as exc:
        validate_permit_hmac_sha256(
            permit,
            expected_run_id="run-1",
            expected_tool_id="tool-1",
            expected_plan_hash="plan-1",
            expected_cwd="/repo",
            expected_argv_segments=[["echo", "different"]],
            expected_scope_paths=["README.md"],
            signing_key="secret",
            now=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        )
    assert exc.value.reason_code == "PERMIT.MISMATCH_ARGS"


def test_validate_permit_expired() -> None:
    permit = issue_permit_hmac_sha256(
        permit_id="permit-1",
        run_id="run-1",
        tool_id="tool-1",
        plan_hash="plan-1",
        issued_at="2025-01-01T00:00:00Z",
        expires_at="2025-01-01T00:00:01+00:00",
        cwd="/repo",
        argv_segments=[["echo", "ok"]],
        scope_paths=["README.md"],
        signing_key="secret",
    )

    with pytest.raises(PermitValidationError) as exc:
        validate_permit_hmac_sha256(
            permit,
            expected_run_id="run-1",
            expected_tool_id="tool-1",
            expected_plan_hash="plan-1",
            expected_cwd="/repo",
            expected_argv_segments=[["echo", "ok"]],
            expected_scope_paths=["README.md"],
            signing_key="secret",
            now=datetime(2025, 1, 1, 0, 1, 0, tzinfo=timezone.utc),
        )
    assert exc.value.reason_code == "PERMIT.EXPIRED"


def _policy_with_gate(gate_id: str, vault_dir: Path) -> VaultPolicyBundle:
    return VaultPolicyBundle(
        vault_dir=vault_dir,
        pack_registry=PackRegistry(version="0.1.0", packs=[]),
        gate_registry=GateRegistry(
            version="0.1.0",
            tiers=[GateTier(id="T0", name="Tier 0", description="fast")],
            gates=[GateDefinition(id=gate_id, tier="T0", kind="command", description="cmd")],
        ),
        profile_registry=ProfileRegistry(version="0.1.0", profiles=[]),
    )


def _plan(profile_id: str, gate_id: str) -> GatePlan:
    return GatePlan(
        version="1.0.0",
        profile_id=profile_id,
        policy_versions=PolicyVersions(skill_packs_registry="0.1.0", gates="0.1.0"),
        packs=[],
        pack_versions=[],
        gate_tier="T0",
        gates=[gate_id],
        pack_cap=PackCap(cap=10, selected=0, exceeded=False),
    )


def test_run_gate_plan_records_permit_in_evidence_when_profile_requires(
    tmp_path: Path, monkeypatch
) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    subprocess.run(
        ["git", "init"],
        cwd=repo_dir,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )

    policy = _policy_with_gate("GATE-CMD-1", vault_dir=tmp_path / "vault")
    plan = _plan("team", "GATE-CMD-1")

    monkeypatch.setenv("MC_EVIDENCE_KEY_ID", "dev-key")
    monkeypatch.setenv("MC_EVIDENCE_SIGNING_KEY", "dev-secret")

    result = run_gate_plan(
        plan=plan,
        declared_files=["README.md"],
        repo_dir=repo_dir,
        policy=policy,
        gate_command_overrides={"GATE-CMD-1": [sys.executable, "-c", "print('ok')"]},
        run_id="run-team-permit",
        created_at="2025-01-01T00:00:00Z",
    )

    assert result.exit_code == 0
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["profile_id"] == "team"

    meta_rel = next(p for p in manifest["gate_results"][0]["log_paths"] if p.endswith(".meta.txt"))
    meta_text = (result.evidence_dir / meta_rel).read_text(encoding="utf-8")

    assert "permit_id:" in meta_text
    assert "permit_hash:" in meta_text
    assert "permit_signature:" in meta_text
