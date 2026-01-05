# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Fail-closed release evidence gate."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from motus.hardening.package_conflicts import detect_package_conflicts


MAX_HEALTH_LEDGER_AGE_HOURS = 24


@dataclass(frozen=True)
class EvidenceCheckResult:
    name: str
    passed: bool
    message: str
    details: dict[str, Any] | None = None


@dataclass(frozen=True)
class EvidenceBundleResult:
    passed: bool
    checks: list[EvidenceCheckResult]
    blocked: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "blocked": self.blocked,
            "checks": [
                {
                    "name": c.name,
                    "passed": c.passed,
                    "message": c.message,
                    "details": c.details,
                }
                for c in self.checks
            ],
        }


def _run(cmd: list[str], *, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


def _json_load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _health_files(repo_root: Path) -> dict[str, Path]:
    return {
        "health_baseline": repo_root / "packages/cli/docs/quality/health-baseline.json",
        "health_policy": repo_root / "packages/cli/docs/quality/health-policy.json",
        "health_ledger": repo_root / "packages/cli/docs/quality/health-ledger.md",
    }


def _check_health_files(repo_root: Path) -> EvidenceCheckResult:
    files = _health_files(repo_root)
    missing = [name for name, path in files.items() if not path.exists()]
    if missing:
        return EvidenceCheckResult(
            name="health_files",
            passed=False,
            message=f"Missing health artifacts: {', '.join(missing)}",
        )

    ledger = files["health_ledger"]
    age_seconds = time.time() - ledger.stat().st_mtime
    max_age = MAX_HEALTH_LEDGER_AGE_HOURS * 3600
    if age_seconds > max_age:
        return EvidenceCheckResult(
            name="health_files",
            passed=False,
            message="health-ledger.md is older than 24h",
            details={"age_seconds": int(age_seconds)},
        )

    return EvidenceCheckResult(
        name="health_files",
        passed=True,
        message="Health artifacts present and recent",
        details={"health_ledger_age_seconds": int(age_seconds)},
    )


def _check_package_conflicts() -> EvidenceCheckResult:
    result = detect_package_conflicts()
    if not result.conflict:
        return EvidenceCheckResult(
            name="package_conflicts",
            passed=True,
            message="No conflicting packages detected",
            details={"origin": result.origin},
        )

    details = {"conflicts": result.conflicts, "origin": result.origin}
    if result.conflicts:
        installed = ", ".join(f"{name}=={ver}" for name, ver in result.conflicts.items())
        message = f"Conflicting packages installed: {installed}"
    else:
        message = "Motus import resolves to motus-command path"
    return EvidenceCheckResult(
        name="package_conflicts",
        passed=False,
        message=message,
        details=details,
    )


def _check_pytest(cli_root: Path, report_path: Path) -> EvidenceCheckResult:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "--json-report",
        f"--json-report-file={report_path}",
        "-q",
    ]
    result = _run(cmd, cwd=cli_root)
    if result.returncode != 0 and not report_path.exists():
        return EvidenceCheckResult(
            name="pytest_results",
            passed=False,
            message="pytest failed to produce json report",
            details={"returncode": result.returncode, "stderr": result.stderr.strip()},
        )
    try:
        payload = _json_load(report_path)
    except Exception as exc:
        return EvidenceCheckResult(
            name="pytest_results",
            passed=False,
            message=f"Failed to parse pytest report: {exc}",
        )

    summary = payload.get("summary", {})
    failed = int(summary.get("failed", 0))
    errors = int(summary.get("errors", 0))
    if failed or errors:
        return EvidenceCheckResult(
            name="pytest_results",
            passed=False,
            message=f"pytest failures: failed={failed}, errors={errors}",
            details={"failed": failed, "errors": errors},
        )
    return EvidenceCheckResult(
        name="pytest_results",
        passed=True,
        message="pytest passed",
        details={"failed": failed, "errors": errors},
    )


def _check_bandit(cli_root: Path, report_path: Path) -> EvidenceCheckResult:
    cmd = ["bandit", "-r", "src/", "-f", "json", "-o", str(report_path)]
    result = _run(cmd, cwd=cli_root)
    if result.returncode != 0 and not report_path.exists():
        return EvidenceCheckResult(
            name="bandit_results",
            passed=False,
            message="bandit failed to produce json report",
            details={"returncode": result.returncode, "stderr": result.stderr.strip()},
        )
    try:
        payload = _json_load(report_path)
    except Exception as exc:
        return EvidenceCheckResult(
            name="bandit_results",
            passed=False,
            message=f"Failed to parse bandit report: {exc}",
        )

    high = 0
    critical = 0
    for item in payload.get("results", []):
        severity = str(item.get("issue_severity", "")).upper()
        if severity == "HIGH":
            high += 1
        elif severity == "CRITICAL":
            critical += 1
    if high or critical:
        return EvidenceCheckResult(
            name="bandit_results",
            passed=False,
            message="Bandit HIGH/CRITICAL findings",
            details={"high": high, "critical": critical},
        )
    return EvidenceCheckResult(
        name="bandit_results",
        passed=True,
        message="Bandit clean",
        details={"high": high, "critical": critical},
    )


# Dev-only packages excluded from vulnerability checks (not shipped with motusos)
DEV_ONLY_PACKAGES = frozenset([
    "ansible",
    "ansible-core",
    "cbor2",  # Not a runtime dependency
])


def _check_pip_audit(cli_root: Path, report_path: Path) -> EvidenceCheckResult:
    cmd = ["pip-audit", "--format", "json", "-o", str(report_path)]
    result = _run(cmd, cwd=cli_root)
    if result.returncode != 0 and not report_path.exists():
        return EvidenceCheckResult(
            name="pip_audit_results",
            passed=False,
            message="pip-audit failed to produce json report",
            details={"returncode": result.returncode, "stderr": result.stderr.strip()},
        )
    try:
        payload = _json_load(report_path)
    except Exception as exc:
        return EvidenceCheckResult(
            name="pip_audit_results",
            passed=False,
            message=f"Failed to parse pip-audit report: {exc}",
        )

    core_vulns = 0
    dev_vulns = 0
    for dep in payload.get("dependencies", []):
        pkg_name = dep.get("name", "").lower()
        vuln_count = len(dep.get("vulns", []))
        if pkg_name in DEV_ONLY_PACKAGES:
            dev_vulns += vuln_count
        else:
            core_vulns += vuln_count

    if core_vulns:
        return EvidenceCheckResult(
            name="pip_audit_results",
            passed=False,
            message=f"pip-audit found {core_vulns} core vulnerabilities",
            details={"core": core_vulns, "dev_only": dev_vulns},
        )
    return EvidenceCheckResult(
        name="pip_audit_results",
        passed=True,
        message=f"pip-audit clean (dev-only: {dev_vulns})",
        details={"core": core_vulns, "dev_only": dev_vulns},
    )


def _check_clean_venv(repo_root: Path) -> EvidenceCheckResult:
    script_path = repo_root / "packages/cli/scripts/ci/clean_venv_proof.py"
    output_path = repo_root / "packages/cli/docs/quality/clean-venv-proof.json"
    if not script_path.exists():
        return EvidenceCheckResult(
            name="clean_venv_proof",
            passed=False,
            message="clean_venv_proof script missing",
            details={"script": str(script_path)},
        )

    cmd = [sys.executable, str(script_path), "--output", str(output_path)]
    result = _run(cmd, cwd=repo_root)
    if result.returncode != 0 and not output_path.exists():
        return EvidenceCheckResult(
            name="clean_venv_proof",
            passed=False,
            message="clean_venv_proof failed to produce artifact",
            details={"returncode": result.returncode, "stderr": result.stderr.strip()},
        )
    try:
        payload = _json_load(output_path)
    except Exception as exc:
        return EvidenceCheckResult(
            name="clean_venv_proof",
            passed=False,
            message=f"Failed to parse clean-venv proof: {exc}",
        )

    passed = bool(payload.get("passed"))
    message = "Clean venv proof passed" if passed else "Clean venv proof failed"
    return EvidenceCheckResult(
        name="clean_venv_proof",
        passed=passed,
        message=message,
        details=payload,
    )


def run_release_evidence(repo_root: Path) -> EvidenceBundleResult:
    cli_root = repo_root / "packages/cli"
    if not cli_root.exists():
        cli_root = repo_root

    checks: list[EvidenceCheckResult] = []

    checks.append(_check_health_files(repo_root))
    if not checks[-1].passed:
        return EvidenceBundleResult(False, checks, blocked=checks[-1].name)

    checks.append(_check_package_conflicts())
    if not checks[-1].passed:
        return EvidenceBundleResult(False, checks, blocked=checks[-1].name)

    checks.append(_check_pytest(cli_root, Path("/tmp/pytest.json")))
    if not checks[-1].passed:
        return EvidenceBundleResult(False, checks, blocked=checks[-1].name)

    checks.append(_check_bandit(cli_root, Path("/tmp/bandit.json")))
    if not checks[-1].passed:
        return EvidenceBundleResult(False, checks, blocked=checks[-1].name)

    checks.append(_check_pip_audit(cli_root, Path("/tmp/pip-audit.json")))
    if not checks[-1].passed:
        return EvidenceBundleResult(False, checks, blocked=checks[-1].name)

    checks.append(_check_clean_venv(repo_root))
    if not checks[-1].passed:
        return EvidenceBundleResult(False, checks, blocked=checks[-1].name)

    return EvidenceBundleResult(True, checks)


def write_release_bundle(output_path: Path, result: EvidenceBundleResult) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
