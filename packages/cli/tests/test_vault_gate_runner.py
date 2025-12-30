from __future__ import annotations

import json
import shutil
import subprocess
import sys
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
from motus.policy.run import run_gate_plan


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


def _plan_with_gates(gate_ids: list[str]) -> GatePlan:
    return GatePlan(
        version="1.0.0",
        profile_id="personal",
        policy_versions=PolicyVersions(skill_packs_registry="0.1.0", gates="0.1.0"),
        packs=[],
        pack_versions=[],
        gate_tier="T0",
        gates=gate_ids,
        pack_cap=PackCap(cap=10, selected=0, exceeded=False),
    )


def _git(repo_dir: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo_dir,
        check=True,
        capture_output=True,
        text=True,
    )
    return (proc.stdout or "").strip()


def test_gate_runner_all_pass_writes_evidence_bundle(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    policy = _policy_with_gates(
        gates=[
            GateDefinition(id="GATE-CMD-1", tier="T0", kind="command", description="cmd1"),
            GateDefinition(id="GATE-CMD-2", tier="T0", kind="command", description="cmd2"),
        ],
        vault_dir=tmp_path / "vault",
    )
    plan = _plan_with_gates(["GATE-CMD-1", "GATE-CMD-2"])

    result = run_gate_plan(
        plan=plan,
        declared_files=[],
        repo_dir=repo_dir,
        policy=policy,
        gate_command_overrides={
            "GATE-CMD-1": [sys.executable, "-c", "print('ok1')"],
            "GATE-CMD-2": [sys.executable, "-c", "print('ok2')"],
        },
        run_id="run-pass",
        created_at="2025-01-01T00:00:00Z",
    )

    assert result.exit_code == 0
    assert result.manifest_path.exists()
    assert result.summary_path.exists()
    assert (result.evidence_dir / "logs").is_dir()

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["run_id"] == "run-pass"
    assert manifest["profile_id"] == "personal"
    assert manifest["policy_versions"] == {"gates": "0.1.0", "skill_packs_registry": "0.1.0"}
    assert isinstance(manifest.get("run_hash"), str)
    assert manifest["run_hash"]

    artifact_hashes = manifest.get("artifact_hashes")
    assert isinstance(artifact_hashes, list)
    assert artifact_hashes
    assert all(
        isinstance(h.get("path"), str) and isinstance(h.get("sha256"), str) for h in artifact_hashes
    )
    assert all(h["path"] != "manifest.json" for h in artifact_hashes)

    assert "stdout" not in manifest
    assert "stderr" not in manifest
    assert all("log_paths" in gr for gr in manifest["gate_results"])
    assert all(isinstance(p, str) for gr in manifest["gate_results"] for p in gr["log_paths"])


def test_gate_runner_emits_source_state_for_git_worktree(tmp_path: Path, monkeypatch) -> None:
    if shutil.which("git") is None:
        pytest.skip("git not installed")

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    _git(repo_dir, "init")
    _git(repo_dir, "config", "user.email", "test@example.com")
    _git(repo_dir, "config", "user.name", "Test")
    (repo_dir / "file.txt").write_text("hello\n", encoding="utf-8")
    _git(repo_dir, "add", "file.txt")
    _git(repo_dir, "commit", "-m", "init")
    commit_sha = _git(repo_dir, "rev-parse", "HEAD")

    evidence_root = tmp_path / "evidence-root"
    monkeypatch.setenv("MC_EVIDENCE_DIR", str(evidence_root))

    policy = _policy_with_gates(
        gates=[GateDefinition(id="GATE-CMD-1", tier="T0", kind="command", description="cmd")],
        vault_dir=tmp_path / "vault",
    )
    plan = _plan_with_gates(["GATE-CMD-1"])

    result = run_gate_plan(
        plan=plan,
        declared_files=[],
        repo_dir=repo_dir,
        policy=policy,
        gate_command_overrides={"GATE-CMD-1": [sys.executable, "-c", "print('ok')"]},
        run_id="run-source-state",
        created_at="2025-01-01T00:00:00Z",
    )

    assert result.exit_code == 0
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    source_state = manifest.get("source_state")
    assert isinstance(source_state, dict)
    assert source_state["vcs"] == "git"
    assert source_state["commit_sha"] == commit_sha
    assert source_state["dirty"] is False
    assert isinstance(source_state.get("ref"), str) and source_state["ref"].startswith("refs/")


def test_gate_runner_source_state_dirty_flag(tmp_path: Path, monkeypatch) -> None:
    if shutil.which("git") is None:
        pytest.skip("git not installed")

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    _git(repo_dir, "init")
    _git(repo_dir, "config", "user.email", "test@example.com")
    _git(repo_dir, "config", "user.name", "Test")
    file_path = repo_dir / "file.txt"
    file_path.write_text("hello\n", encoding="utf-8")
    _git(repo_dir, "add", "file.txt")
    _git(repo_dir, "commit", "-m", "init")

    file_path.write_text("hello2\n", encoding="utf-8")

    evidence_root = tmp_path / "evidence-root"
    monkeypatch.setenv("MC_EVIDENCE_DIR", str(evidence_root))

    policy = _policy_with_gates(
        gates=[GateDefinition(id="GATE-CMD-1", tier="T0", kind="command", description="cmd")],
        vault_dir=tmp_path / "vault",
    )
    plan = _plan_with_gates(["GATE-CMD-1"])

    result = run_gate_plan(
        plan=plan,
        declared_files=[],
        repo_dir=repo_dir,
        policy=policy,
        gate_command_overrides={"GATE-CMD-1": [sys.executable, "-c", "print('ok')"]},
        run_id="run-source-state-dirty",
        created_at="2025-01-01T00:00:00Z",
    )

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    source_state = manifest.get("source_state")
    assert isinstance(source_state, dict)
    assert source_state["dirty"] is True


def test_gate_runner_supports_string_commands_with_and_and(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    policy = _policy_with_gates(
        gates=[GateDefinition(id="GATE-CMD-1", tier="T0", kind="command", description="cmd")],
        vault_dir=tmp_path / "vault",
    )
    plan = _plan_with_gates(["GATE-CMD-1"])

    command = f"{sys.executable} -c \"print('ok1')\" && {sys.executable} -c \"print('ok2')\""
    result = run_gate_plan(
        plan=plan,
        declared_files=[],
        repo_dir=repo_dir,
        policy=policy,
        gate_command_overrides={"GATE-CMD-1": command},
        run_id="run-and-and",
        created_at="2025-01-01T00:00:00Z",
    )

    assert result.exit_code == 0
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    stdout_rel = next(
        p for p in manifest["gate_results"][0]["log_paths"] if p.endswith(".stdout.txt")
    )
    stdout_text = (result.evidence_dir / stdout_rel).read_text(encoding="utf-8")
    assert "ok1" in stdout_text
    assert "ok2" in stdout_text


def test_gate_runner_rejects_unsupported_shell_syntax(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    policy = _policy_with_gates(
        gates=[GateDefinition(id="GATE-CMD-1", tier="T0", kind="command", description="cmd")],
        vault_dir=tmp_path / "vault",
    )
    plan = _plan_with_gates(["GATE-CMD-1"])

    command = f"{sys.executable} -c \"print('ok')\" ; {sys.executable} -c \"print('nope')\""
    result = run_gate_plan(
        plan=plan,
        declared_files=[],
        repo_dir=repo_dir,
        policy=policy,
        gate_command_overrides={"GATE-CMD-1": command},
        run_id="run-unsupported",
        created_at="2025-01-01T00:00:00Z",
    )

    assert result.exit_code != 0
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    stderr_rel = next(
        p for p in manifest["gate_results"][0]["log_paths"] if p.endswith(".stderr.txt")
    )
    stderr_text = (result.evidence_dir / stderr_rel).read_text(encoding="utf-8")
    assert "unsupported shell syntax" in stderr_text


def test_gate_runner_honors_mc_evidence_dir_env_var(tmp_path: Path, monkeypatch) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    policy = _policy_with_gates(
        gates=[GateDefinition(id="GATE-CMD-1", tier="T0", kind="command", description="cmd")],
        vault_dir=tmp_path / "vault",
    )
    plan = _plan_with_gates(["GATE-CMD-1"])

    evidence_root = tmp_path / "evidence-root"
    monkeypatch.setenv("MC_EVIDENCE_DIR", str(evidence_root))

    result = run_gate_plan(
        plan=plan,
        declared_files=[],
        repo_dir=repo_dir,
        policy=policy,
        gate_command_overrides={"GATE-CMD-1": [sys.executable, "-c", "print('ok')"]},
        run_id="run-env",
        created_at="2025-01-01T00:00:00Z",
    )

    assert result.evidence_dir == evidence_root / "run-env"


def test_gate_runner_sanitizes_subprocess_env_to_prevent_secret_leaks(
    tmp_path: Path, monkeypatch
) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    policy = _policy_with_gates(
        gates=[GateDefinition(id="GATE-CMD-1", tier="T0", kind="command", description="cmd")],
        vault_dir=tmp_path / "vault",
    )
    plan = _plan_with_gates(["GATE-CMD-1"])

    secret = "SECRET-LEAK-TEST-DO-NOT-LOG"
    monkeypatch.setenv("MC_EVIDENCE_KEY_ID", "test-key")
    monkeypatch.setenv("MC_EVIDENCE_SIGNING_KEY", secret)

    result = run_gate_plan(
        plan=plan,
        declared_files=[],
        repo_dir=repo_dir,
        policy=policy,
        gate_command_overrides={
            "GATE-CMD-1": [
                sys.executable,
                "-c",
                "import os; print(dict(os.environ))",
            ],
        },
        run_id="run-env-sanitized",
        created_at="2025-01-01T00:00:00Z",
    )

    secret_bytes = secret.encode("utf-8")
    for path in result.evidence_dir.rglob("*"):
        if not path.is_file():
            continue
        assert secret_bytes not in path.read_bytes()


def test_gate_runner_fail_closed_on_failing_gate(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    policy = _policy_with_gates(
        gates=[
            GateDefinition(id="GATE-CMD-1", tier="T0", kind="command", description="cmd1"),
            GateDefinition(id="GATE-CMD-2", tier="T0", kind="command", description="cmd2"),
        ],
        vault_dir=tmp_path / "vault",
    )
    plan = _plan_with_gates(["GATE-CMD-1", "GATE-CMD-2"])

    result = run_gate_plan(
        plan=plan,
        declared_files=[],
        repo_dir=repo_dir,
        policy=policy,
        gate_command_overrides={
            "GATE-CMD-1": [sys.executable, "-c", "print('ok1')"],
            "GATE-CMD-2": [sys.executable, "-c", "import sys; sys.exit(2)"],
        },
        run_id="run-fail",
        created_at="2025-01-01T00:00:00Z",
    )

    assert result.exit_code != 0
    assert result.manifest_path.exists()
    assert result.summary_path.exists()

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    statuses = {r["gate_id"]: r["status"] for r in manifest["gate_results"]}
    assert statuses["GATE-CMD-1"] == "pass"
    assert statuses["GATE-CMD-2"] == "fail"


def test_gate_runner_fail_closed_on_unresolvable_gate(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    policy = _policy_with_gates(
        gates=[
            GateDefinition(id="GATE-CMD-1", tier="T0", kind="command", description="cmd1"),
            GateDefinition(id="GATE-CMD-2", tier="T0", kind="command", description="cmd2"),
        ],
        vault_dir=tmp_path / "vault",
    )
    plan = _plan_with_gates(["GATE-CMD-1", "GATE-CMD-2"])

    result = run_gate_plan(
        plan=plan,
        declared_files=[],
        repo_dir=repo_dir,
        policy=policy,
        gate_command_overrides={
            "GATE-CMD-1": [sys.executable, "-c", "print('ok1')"],
        },
        run_id="run-unresolvable",
        created_at="2025-01-01T00:00:00Z",
    )

    assert result.exit_code != 0
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    statuses = {r["gate_id"]: r["status"] for r in manifest["gate_results"]}
    assert statuses["GATE-CMD-2"] == "fail"


def test_gate_runner_treats_intake_as_manual_pass(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    policy = _policy_with_gates(
        gates=[GateDefinition(id="GATE-INTAKE", tier="T0", kind="intake", description="manual")],
        vault_dir=tmp_path / "vault",
    )
    plan = _plan_with_gates(["GATE-INTAKE"])

    result = run_gate_plan(
        plan=plan,
        declared_files=[],
        repo_dir=repo_dir,
        policy=policy,
        run_id="run-intake",
        created_at="2025-01-01T00:00:00Z",
    )

    assert result.exit_code == 0
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["gate_results"][0]["status"] == "pass"

    meta_rel = next(p for p in manifest["gate_results"][0]["log_paths"] if p.endswith(".meta.txt"))
    meta_text = (result.evidence_dir / meta_rel).read_text(encoding="utf-8")
    assert "manual/internal" in meta_text


def test_gate_runner_missing_gate_id_in_registry(tmp_path: Path) -> None:
    """Test that a gate ID missing from the registry fails with exit_code=127."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    policy = _policy_with_gates(
        gates=[
            GateDefinition(id="GATE-CMD-1", tier="T0", kind="command", description="cmd1"),
        ],
        vault_dir=tmp_path / "vault",
    )
    plan = _plan_with_gates(["GATE-CMD-1", "GATE-MISSING"])

    result = run_gate_plan(
        plan=plan,
        declared_files=[],
        repo_dir=repo_dir,
        policy=policy,
        gate_command_overrides={
            "GATE-CMD-1": [sys.executable, "-c", "print('ok1')"],
        },
        run_id="run-missing-gate",
        created_at="2025-01-01T00:00:00Z",
    )

    assert result.exit_code != 0
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

    gate_missing_result = next(
        r for r in manifest["gate_results"] if r["gate_id"] == "GATE-MISSING"
    )
    assert gate_missing_result["status"] == "fail"
    assert gate_missing_result["exit_code"] == 127
    assert gate_missing_result["duration_ms"] == 0


def test_gate_runner_intake_gate_auto_pass(tmp_path: Path) -> None:
    """Test that intake gates auto-pass without running a command."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    policy = _policy_with_gates(
        gates=[
            GateDefinition(id="GATE-INTAKE-1", tier="T0", kind="intake", description="intake1"),
        ],
        vault_dir=tmp_path / "vault",
    )
    plan = _plan_with_gates(["GATE-INTAKE-1"])

    result = run_gate_plan(
        plan=plan,
        declared_files=[],
        repo_dir=repo_dir,
        policy=policy,
        run_id="run-intake",
        created_at="2025-01-01T00:00:00Z",
    )

    assert result.exit_code == 0
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

    intake_result = manifest["gate_results"][0]
    assert intake_result["gate_id"] == "GATE-INTAKE-1"
    assert intake_result["status"] == "pass"
    assert intake_result["exit_code"] == 0
    assert intake_result["duration_ms"] == 0


def test_gate_runner_harness_command_none_fails(tmp_path: Path) -> None:
    """Test that a harness gate with no resolvable command fails."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    policy = _policy_with_gates(
        gates=[
            GateDefinition(id="GATE-PLAN-1", tier="T0", kind="plan", description="plan gate"),
        ],
        vault_dir=tmp_path / "vault",
    )
    plan = _plan_with_gates(["GATE-PLAN-1"])

    result = run_gate_plan(
        plan=plan,
        declared_files=[],
        repo_dir=repo_dir,
        policy=policy,
        run_id="run-no-harness",
        created_at="2025-01-01T00:00:00Z",
    )

    assert result.exit_code != 0
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

    plan_result = manifest["gate_results"][0]
    assert plan_result["gate_id"] == "GATE-PLAN-1"
    assert plan_result["status"] == "fail"
    assert plan_result["exit_code"] == 127


def test_gate_runner_subprocess_exception_handling(tmp_path: Path) -> None:
    """Test that subprocess exceptions are caught and recorded as failures."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    policy = _policy_with_gates(
        gates=[
            GateDefinition(id="GATE-CMD-1", tier="T0", kind="command", description="cmd1"),
        ],
        vault_dir=tmp_path / "vault",
    )
    plan = _plan_with_gates(["GATE-CMD-1"])

    result = run_gate_plan(
        plan=plan,
        declared_files=[],
        repo_dir=repo_dir,
        policy=policy,
        gate_command_overrides={
            "GATE-CMD-1": ["/nonexistent/command/path"],
        },
        run_id="run-subprocess-error",
        created_at="2025-01-01T00:00:00Z",
    )

    assert result.exit_code != 0
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

    cmd_result = manifest["gate_results"][0]
    assert cmd_result["gate_id"] == "GATE-CMD-1"
    assert cmd_result["status"] == "fail"
    assert cmd_result["exit_code"] == 127


def test_gate_runner_shell_command_execution(tmp_path: Path) -> None:
    """Test that string commands are executed via the safe argv parser."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    policy = _policy_with_gates(
        gates=[
            GateDefinition(id="GATE-SHELL-1", tier="T0", kind="command", description="shell cmd"),
        ],
        vault_dir=tmp_path / "vault",
    )
    plan = _plan_with_gates(["GATE-SHELL-1"])

    result = run_gate_plan(
        plan=plan,
        declared_files=[],
        repo_dir=repo_dir,
        policy=policy,
        gate_command_overrides={
            "GATE-SHELL-1": f"{sys.executable} -c 'print(\"shell ok\")'",
        },
        run_id="run-shell-cmd",
        created_at="2025-01-01T00:00:00Z",
    )

    assert result.exit_code == 0
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["gate_results"][0]["status"] == "pass"
