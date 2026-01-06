#!/usr/bin/env python3
"""Generate a clean-venv proof artifact for release evidence."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def _run(cmd: list[str], *, env: dict[str, str] | None = None, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _bin_dir(venv_dir: Path) -> Path:
    return venv_dir / ("Scripts" if os.name == "nt" else "bin")


def _env_for_venv(venv_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    bin_path = str(_bin_dir(venv_dir))
    env["PATH"] = f"{bin_path}{os.pathsep}{env.get('PATH', '')}"
    env["VIRTUAL_ENV"] = str(venv_dir)
    return env


def _pip_list(pip_bin: Path, env: dict[str, str]) -> dict[str, str]:
    result = _run([str(pip_bin), "list", "--format", "json"], env=env)
    if result.returncode != 0:
        return {}
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}
    return {item.get("name", ""): item.get("version", "") for item in data if item.get("name")}


def _motus_info(python_bin: Path, env: dict[str, str]) -> dict[str, str]:
    code = (
        "import json, motus, sys; "
        "print(json.dumps({'file': motus.__file__, "
        "'version': getattr(motus, '__version__', 'unknown')}))"
    )
    result = _run([str(python_bin), "-c", code], env=env)
    if result.returncode != 0:
        return {"error": result.stderr.strip() or "motus import failed"}
    try:
        return json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        return {"error": "motus import output not parseable"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Create clean-venv proof artifact")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("packages/cli/docs/quality/clean-venv-proof.json"),
        help="Output JSON path for proof artifact",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Install source path (defaults to packages/cli)",
    )
    args = parser.parse_args()

    script_dir = Path(__file__).resolve()
    cli_root = script_dir.parents[2]
    repo_root = script_dir.parents[4]
    source_path = args.source or cli_root

    output_path = args.output
    if not output_path.is_absolute():
        output_path = repo_root / output_path

    payload: dict[str, object] = {
        "passed": False,
        "timestamp": time.time(),
        "source_path": str(source_path),
        "motus_import": {},
        "motus_help_ok": False,
        "conflicts": [],
        "packages": {},
        "errors": [],
    }

    with tempfile.TemporaryDirectory(prefix="motus-clean-venv-") as tmp_dir:
        venv_dir = Path(tmp_dir)
        python_bin = _bin_dir(venv_dir) / "python"
        pip_bin = _bin_dir(venv_dir) / "pip"
        env = _env_for_venv(venv_dir)

        create = _run([sys.executable, "-m", "venv", str(venv_dir)])
        if create.returncode != 0:
            payload["errors"] = [f"venv create failed: {create.stderr.strip()}"]
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            return 1

        install = _run([str(pip_bin), "install", "."], env=env, cwd=source_path)
        if install.returncode != 0:
            payload["errors"] = [f"pip install failed: {install.stderr.strip()}"]
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            return 1

        payload["packages"] = _pip_list(pip_bin, env)
        conflicts = [
            name for name in payload["packages"].keys() if name.lower() in {"motus", "motus-command"}
        ]
        payload["conflicts"] = conflicts

        motus_info = _motus_info(python_bin, env)
        payload["motus_import"] = motus_info

        motus_path = motus_info.get("file", "")
        expected_prefix = str(venv_dir)
        import_ok = bool(motus_path) and expected_prefix in str(motus_path)
        shadowed = any(marker in str(motus_path) for marker in ("motus-command",))
        payload["shadowed"] = shadowed

        motus_bin = _bin_dir(venv_dir) / "motus"
        help_result = _run([str(motus_bin), "--help"], env=env)
        payload["motus_help_ok"] = help_result.returncode == 0

        payload["passed"] = (
            not payload["conflicts"]
            and import_ok
            and payload["motus_help_ok"]
            and not payload["shadowed"]
            and "error" not in motus_info
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
