# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Detection helpers for test harness discovery."""

from __future__ import annotations

import re
import shlex
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from motus.logging import get_logger

logger = get_logger(__name__)
PYTHON_BIN = shlex.quote(sys.executable)

try:
    import yaml  # type: ignore[import-untyped]

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

if TYPE_CHECKING:
    from .harness_core import MCTestHarness


def _detect_from_cargo_toml(repo_path: Path, harness: "MCTestHarness") -> None:
    """Detect Rust test commands from Cargo.toml."""
    cargo_toml = repo_path / "Cargo.toml"
    if not cargo_toml.exists():
        return

    if not harness.test_command:
        harness.test_command = "cargo test"

    if not harness.lint_command:
        harness.lint_command = "cargo clippy"

    if not harness.build_command:
        harness.build_command = "cargo build"

    if not harness.smoke_test:
        harness.smoke_test = "cargo test --lib"


def _detect_from_pytest_ini(repo_path: Path, harness: "MCTestHarness") -> None:
    """Detect pytest configuration from pytest.ini."""
    pytest_ini = repo_path / "pytest.ini"
    if not pytest_ini.exists() or harness.test_command:
        return

    try:
        # Simple INI parsing for testpaths
        content = pytest_ini.read_text()
        testpaths_match = re.search(r"testpaths\s*=\s*(.+)", content)
        if testpaths_match:
            testpaths = testpaths_match.group(1).strip()
            harness.test_command = f"{PYTHON_BIN} -m pytest {testpaths} -v"
        else:
            harness.test_command = f"{PYTHON_BIN} -m pytest tests/ -v"
    except (OSError, UnicodeDecodeError) as e:
        logger.warning(  # type: ignore[call-arg]
            "pytest.ini parse failed",
            path=str(pytest_ini),
            error_type=type(e).__name__,
            error=str(e),
        )
        return


def _detect_from_setup_cfg(repo_path: Path, harness: "MCTestHarness") -> None:
    """Detect pytest configuration from setup.cfg."""
    setup_cfg = repo_path / "setup.cfg"
    if not setup_cfg.exists() or harness.test_command:
        return

    try:
        content = setup_cfg.read_text()
        # Look for [tool:pytest] section
        if "[tool:pytest]" in content or "[pytest]" in content:
            harness.test_command = f"{PYTHON_BIN} -m pytest tests/ -v"
    except (OSError, UnicodeDecodeError) as e:
        logger.warning(  # type: ignore[call-arg]
            "setup.cfg parse failed",
            path=str(setup_cfg),
            error_type=type(e).__name__,
            error=str(e),
        )
        return


def _detect_from_makefile(repo_path: Path, harness: "MCTestHarness") -> None:
    """Detect test commands from Makefile."""
    for makefile_name in ["Makefile", "makefile", "GNUmakefile"]:
        makefile = repo_path / makefile_name
        if not makefile.exists():
            continue

        try:
            content = makefile.read_text()

            if not harness.test_command and re.search(r"^test:", content, re.MULTILINE):
                harness.test_command = "make test"

            if not harness.lint_command and re.search(r"^lint:", content, re.MULTILINE):
                harness.lint_command = "make lint"

            if not harness.build_command and re.search(r"^build:", content, re.MULTILINE):
                harness.build_command = "make build"

            # Check for smoke/quick test targets
            if not harness.smoke_test:
                if re.search(r"^test-quick:", content, re.MULTILINE):
                    harness.smoke_test = "make test-quick"
                elif re.search(r"^smoke:", content, re.MULTILINE):
                    harness.smoke_test = "make smoke"

            break  # Found a Makefile, stop searching
        except (OSError, UnicodeDecodeError) as e:
            logger.warning(  # type: ignore[call-arg]
                "Makefile parse failed",
                path=str(makefile),
                error_type=type(e).__name__,
                error=str(e),
            )
            continue


def _detect_from_github_workflows(repo_path: Path, harness: "MCTestHarness") -> None:
    """Extract test commands from GitHub Actions workflows."""
    workflows_dir = repo_path / ".github" / "workflows"
    if not workflows_dir.exists() or not YAML_AVAILABLE:
        return

    try:
        for workflow_file in workflows_dir.glob("*.yml"):
            try:
                with open(workflow_file, "r") as f:
                    workflow = yaml.safe_load(f)

                if not isinstance(workflow, dict):
                    continue

                jobs = workflow.get("jobs", {})
                for job_name, job_config in jobs.items():
                    if not isinstance(job_config, dict):
                        continue

                    steps = job_config.get("steps", [])
                    for step in steps:
                        if not isinstance(step, dict):
                            continue

                        run_cmd = step.get("run", "")
                        if not run_cmd:
                            continue

                        # Extract test commands
                        if not harness.test_command and (
                            "pytest" in run_cmd or "npm test" in run_cmd or "cargo test" in run_cmd
                        ):
                            # Clean up multiline commands
                            clean_cmd = " ".join(run_cmd.split())
                            if len(clean_cmd) < 100:  # Reasonable command length
                                harness.test_command = clean_cmd

                        # Extract lint commands
                        if not harness.lint_command and (
                            "ruff" in run_cmd or "npm run lint" in run_cmd or "clippy" in run_cmd
                        ):
                            clean_cmd = " ".join(run_cmd.split())
                            if len(clean_cmd) < 100:
                                harness.lint_command = clean_cmd

                        # Extract build commands
                        if not harness.build_command and (
                            "build" in run_cmd or "compile" in run_cmd
                        ):
                            clean_cmd = " ".join(run_cmd.split())
                            if len(clean_cmd) < 100:
                                harness.build_command = clean_cmd

            except (OSError, UnicodeDecodeError, yaml.YAMLError) as e:
                logger.warning(
                    "GitHub workflow file parse failed",
                    path=str(workflow_file),
                    error_type=type(e).__name__,
                    error=str(e),
                )
                continue

    except OSError as e:
        logger.warning(
            "GitHub workflows directory scan failed",
            path=str(workflows_dir),
            error_type=type(e).__name__,
            error=str(e),
        )
        return
