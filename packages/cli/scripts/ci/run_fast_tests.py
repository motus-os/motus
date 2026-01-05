#!/usr/bin/env python3
"""Run smoke/critical tests with safe parallelism."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    cli_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(cli_root / "src")

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-m",
        "smoke or critical",
        "-n",
        "auto",
        "--dist=loadfile",
    ]
    proc = subprocess.run(cmd, cwd=cli_root, env=env)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
