#!/usr/bin/env python3
"""Generate and verify the Motus health ledger.

This script runs deterministic checks, produces a JSON ledger, and compares
against a committed baseline with policy thresholds.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Iterable


def _run(cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_junit(junit_path: Path) -> dict[str, Any]:
    tree = ET.parse(junit_path)
    root = tree.getroot()

    if root.tag == "testsuites":
        suites = root.findall("testsuite")
    else:
        suites = [root]

    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0, "time": 0.0}
    for suite in suites:
        totals["tests"] += int(suite.attrib.get("tests", "0"))
        totals["failures"] += int(suite.attrib.get("failures", "0"))
        totals["errors"] += int(suite.attrib.get("errors", "0"))
        totals["skipped"] += int(suite.attrib.get("skipped", "0"))
        totals["time"] += float(suite.attrib.get("time", "0") or 0.0)

    return totals


def _coverage_for_prefixes(coverage: dict[str, Any], prefixes: Iterable[str]) -> float | None:
    files = coverage.get("files", {})
    if not files:
        return None

    total_lines = 0
    covered_lines = 0
    prefixes_norm = [p.replace("/", os.sep) for p in prefixes]

    for filename, info in files.items():
        if not any(prefix in filename for prefix in prefixes_norm):
            continue
        summary = info.get("summary", {})
        total_lines += int(summary.get("num_statements", 0))
        covered_lines += int(summary.get("covered_lines", 0))

    if total_lines == 0:
        return None
    return round(covered_lines / total_lines * 100, 2)


def _parse_coverage(coverage_path: Path, cli_root: Path) -> dict[str, Any]:
    coverage = _load_json(coverage_path)
    totals = coverage.get("totals", {})
    overall = round(float(totals.get("percent_covered", 0.0)), 2)

    core_prefixes = [
        str(cli_root / "src/motus/core"),
        str(cli_root / "src/motus/coordination"),
        str(cli_root / "src/motus/policy"),
        str(cli_root / "src/motus/orchestrator"),
        str(cli_root / "src/motus/cli"),
        str(cli_root / "src/motus/mcp"),
    ]
    secondary_prefixes = [
        str(cli_root / "src/motus/ingestors"),
        str(cli_root / "src/motus/ui"),
        str(cli_root / "src/motus/standards"),
    ]

    return {
        "overall_percent": overall,
        "core_percent": _coverage_for_prefixes(coverage, core_prefixes),
        "secondary_percent": _coverage_for_prefixes(coverage, secondary_prefixes),
    }


def _count_ruff_errors(stdout: str) -> int:
    stdout = stdout.strip()
    if not stdout:
        return 0
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return len([line for line in stdout.splitlines() if line.strip()])
    return len(data)


def _count_mypy_errors(output: str) -> int:
    errors = 0
    for line in output.splitlines():
        if ": error:" in line:
            errors += 1
    return errors


def _pip_audit_counts(stdout: str) -> dict[str, int]:
    if not stdout.strip():
        return {"critical": 0, "high": 0, "total": 0}
    data = json.loads(stdout)
    high = 0
    critical = 0
    total = 0
    for dep in data.get("dependencies", []):
        for vuln in dep.get("vulns", []):
            total += 1
            severity = (vuln.get("severity") or "").upper()
            if severity == "CRITICAL":
                critical += 1
            elif severity == "HIGH":
                high += 1
    return {"critical": critical, "high": high, "total": total}


def _policy_metrics(db_path: Path) -> dict[str, Any]:
    if not db_path.exists():
        return {"count": 0, "p95_ms": None, "max_ms": None, "latest": None}

    with sqlite3.connect(str(db_path)) as conn:
        rows = conn.execute(
            "SELECT elapsed_ms, metadata FROM metrics WHERE operation = 'policy_run' ORDER BY id DESC LIMIT 50"
        ).fetchall()

    if not rows:
        return {"count": 0, "p95_ms": None, "max_ms": None, "latest": None}

    elapsed = [float(r[0]) for r in rows]
    elapsed_sorted = sorted(elapsed)
    idx = int(round(0.95 * (len(elapsed_sorted) - 1)))
    p95 = elapsed_sorted[idx]
    latest_metadata = None
    if rows[0][1]:
        try:
            latest_metadata = json.loads(rows[0][1])
        except json.JSONDecodeError:
            latest_metadata = None

    return {
        "count": len(elapsed),
        "p95_ms": round(p95, 2),
        "max_ms": round(max(elapsed), 2),
        "latest": latest_metadata,
    }


def _init_clean_repo(repo_dir: Path) -> None:
    repo_dir.mkdir(parents=True, exist_ok=True)
    src_dir = repo_dir / "src"
    tests_dir = repo_dir / "tests"
    src_dir.mkdir(parents=True, exist_ok=True)
    tests_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "README.md").write_text("Motus health ledger repo\n", encoding="utf-8")
    (src_dir / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tests_dir / "test_smoke.py").write_text(
        "def test_smoke():\n    assert True\n",
        encoding="utf-8",
    )
    (repo_dir / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\n"
        "testpaths = ['tests']\n"
        "\n"
        "[tool.ruff]\n"
        "line-length = 88\n",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "motus",
            "GIT_AUTHOR_EMAIL": "motus@local",
            "GIT_COMMITTER_NAME": "motus",
            "GIT_COMMITTER_EMAIL": "motus@local",
        }
    )
    init_proc = _run(["git", "init"], cwd=repo_dir, env=env)
    if init_proc.returncode != 0:
        raise RuntimeError("git init failed: " + init_proc.stderr.strip())
    add_proc = _run(["git", "add", "."], cwd=repo_dir, env=env)
    if add_proc.returncode != 0:
        raise RuntimeError("git add failed: " + add_proc.stderr.strip())
    commit_proc = _run(["git", "commit", "-m", "init"], cwd=repo_dir, env=env)
    if commit_proc.returncode != 0:
        raise RuntimeError("git commit failed: " + commit_proc.stderr.strip())


def _run_policy_smoke(cli_root: Path, work_dir: Path) -> Path:
    fixtures = cli_root / "tests/fixtures/vault_policy"
    vault_dir = work_dir / "vault"
    registry_src = fixtures / "registry.json"
    gates_src = fixtures / "gates.json"
    profiles_src = fixtures / "profiles.json"
    evidence_schema_src = fixtures / "evidence-manifest.schema.json"

    registry_dest = vault_dir / "core/best-practices/skill-packs/registry.json"
    registry_dest.parent.mkdir(parents=True, exist_ok=True)
    registry_dest.write_text(registry_src.read_text(encoding="utf-8"), encoding="utf-8")

    gates_dest = vault_dir / "core/best-practices/gates.json"
    gates_dest.parent.mkdir(parents=True, exist_ok=True)
    gates_dest.write_text(gates_src.read_text(encoding="utf-8"), encoding="utf-8")

    profiles_dest = vault_dir / "core/best-practices/profiles/profiles.json"
    profiles_dest.parent.mkdir(parents=True, exist_ok=True)
    profiles_dest.write_text(profiles_src.read_text(encoding="utf-8"), encoding="utf-8")

    evidence_schema_dest = (
        vault_dir / "core/best-practices/control-plane/evidence-manifest.schema.json"
    )
    evidence_schema_dest.parent.mkdir(parents=True, exist_ok=True)
    evidence_schema_dest.write_text(
        evidence_schema_src.read_text(encoding="utf-8"), encoding="utf-8"
    )
    evidence_dir = work_dir / "evidence"
    db_path = work_dir / "coordination.db"
    cache_path = work_dir / "context_cache.db"

    repo_dir = work_dir / "repo"
    _init_clean_repo(repo_dir)

    env = os.environ.copy()
    env["PYTHONPATH"] = str(cli_root / "src")
    env["MC_DB_PATH"] = str(db_path)
    env["MC_CONTEXT_CACHE_DB_PATH"] = str(cache_path)
    env["MC_METRICS_ENABLED"] = "1"

    cmd = [
        sys.executable,
        "-m",
        "motus.cli.core",
        "policy",
        "run",
        "--files",
        "src/app.py",
        "--vault-dir",
        str(vault_dir),
        "--repo",
        str(repo_dir),
        "--evidence-dir",
        str(evidence_dir),
    ]
    proc = _run(cmd, cwd=cli_root, env=env)
    if proc.returncode != 0:
        raise RuntimeError(
            "policy run failed: "
            + (proc.stderr.strip() or proc.stdout.strip() or f"exit={proc.returncode}")
        )

    return db_path


def _compare(baseline: dict[str, Any], current: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    failures: list[str] = []

    tests = current["tests"]
    if tests["failures"] > policy["tests"]["max_failures"] or tests["errors"] > 0:
        failures.append("tests: failures or errors present")

    security = current["security"]
    baseline_sec = baseline.get("security", {})
    if not security.get("skipped") and not baseline_sec.get("skipped"):
        if security["critical"] - baseline_sec.get("critical", 0) > policy["security"]["max_new_critical"]:
            failures.append("security: new critical vulnerabilities")
        if security["high"] - baseline_sec.get("high", 0) > policy["security"]["max_new_high"]:
            failures.append("security: new high vulnerabilities")

    runtime = current["tests"]["duration_seconds"]
    baseline_runtime = baseline.get("tests", {}).get("duration_seconds")
    if baseline_runtime is not None:
        max_runtime = baseline_runtime * (1 + policy["runtime"]["max_delta_pct"] / 100)
        if runtime > max_runtime:
            failures.append("tests: runtime regression beyond threshold")

    coverage = current["coverage"]
    baseline_cov = baseline.get("coverage", {})
    if coverage.get("core_percent") is not None and baseline_cov.get("core_percent") is not None:
        min_cov = baseline_cov["core_percent"] + policy["coverage"]["min_delta_pct"]
        if coverage["core_percent"] < min_cov:
            failures.append("coverage: core coverage regression beyond threshold")

    policy_run = current["policy_run"]
    baseline_policy = baseline.get("policy_run", {})
    if policy_run.get("p95_ms") is not None and baseline_policy.get("p95_ms") is not None:
        max_p95 = baseline_policy["p95_ms"] * (1 + policy["policy_run"]["max_delta_pct"] / 100)
        if policy_run["p95_ms"] > max_p95:
            failures.append("policy_run: p95 regression beyond threshold")

    if current["lint"]["errors"] > policy["lint"]["max_errors"]:
        failures.append("lint: ruff errors present")

    if current["typecheck"]["errors"] > policy["typecheck"]["max_errors"]:
        failures.append("typecheck: mypy errors present")

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate and verify Motus health ledger")
    parser.add_argument("--baseline", default="docs/quality/health-baseline.json")
    parser.add_argument("--policy", default="docs/quality/health-policy.json")
    parser.add_argument("--output", default="artifacts/health.json")
    parser.add_argument("--write-baseline", action="store_true")
    parser.add_argument("--skip-security", action="store_true", help="Skip pip-audit (offline)")

    args = parser.parse_args()

    cli_root = Path(__file__).resolve().parents[2]
    artifacts_dir = cli_root / "artifacts"
    junit_path = artifacts_dir / "pytest-junit.xml"
    coverage_path = artifacts_dir / "coverage.json"

    start = time.monotonic()

    pytest_cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests",
        "--ignore=tests/test_benchmark_adversarial_suite.py",
        "--ignore=tests/test_benchmark_harness.py",
        "--junitxml",
        str(junit_path),
        "--cov=motus",
        f"--cov-report=json:{coverage_path}",
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(cli_root / "src")

    pytest_proc = _run(pytest_cmd, cwd=cli_root, env=env)
    if pytest_proc.returncode != 0:
        print(pytest_proc.stdout)
        print(pytest_proc.stderr, file=sys.stderr)
        return pytest_proc.returncode

    tests_summary = _parse_junit(junit_path)
    tests_summary["duration_seconds"] = round(time.monotonic() - start, 2)

    coverage_summary = _parse_coverage(coverage_path, cli_root)

    ruff_proc = _run(
        ["ruff", "check", "src", "--output-format", "json"],
        cwd=cli_root,
        env=env,
    )
    ruff_errors = _count_ruff_errors(ruff_proc.stdout)

    mypy_proc = _run(["mypy", "src"], cwd=cli_root, env=env)
    mypy_errors = _count_mypy_errors(mypy_proc.stdout + mypy_proc.stderr)

    if args.skip_security:
        security_counts = {"critical": 0, "high": 0, "total": 0, "skipped": True}
    else:
        audit_proc = _run(["pip-audit", "--format", "json"], cwd=cli_root, env=env)
        if audit_proc.returncode != 0:
            print(audit_proc.stdout)
            print(audit_proc.stderr, file=sys.stderr)
            return audit_proc.returncode
        security_counts = _pip_audit_counts(audit_proc.stdout)

    policy_db = _run_policy_smoke(cli_root, artifacts_dir)
    policy_metrics = _policy_metrics(policy_db)

    current = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tests": {
            "tests": tests_summary["tests"],
            "failures": tests_summary["failures"],
            "errors": tests_summary["errors"],
            "skipped": tests_summary["skipped"],
            "duration_seconds": tests_summary["duration_seconds"],
        },
        "coverage": coverage_summary,
        "lint": {"errors": ruff_errors},
        "typecheck": {"errors": mypy_errors},
        "security": security_counts,
        "policy_run": policy_metrics,
    }

    output_path = cli_root / args.output
    _write_json(output_path, current)

    baseline_path = cli_root / args.baseline
    policy_path = cli_root / args.policy

    if args.write_baseline:
        _write_json(baseline_path, current)
        print(f"Baseline written to {baseline_path}")
        return 0

    if not baseline_path.exists():
        raise FileNotFoundError(f"Baseline not found: {baseline_path}")
    if not policy_path.exists():
        raise FileNotFoundError(f"Policy not found: {policy_path}")

    baseline = _load_json(baseline_path)
    policy = _load_json(policy_path)

    failures = _compare(baseline, current, policy)
    if failures:
        print("Health ledger gate failures:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Health ledger checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
