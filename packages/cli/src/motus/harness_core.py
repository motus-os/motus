# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""
Test Harness Detection for Motus v0.3.0.

Auto-detect test, lint, build, and smoke test commands from repository structure.
Supports multiple build systems: Python, JavaScript/Node, Rust, Make, and CI configs.
"""

import json
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from motus.logging import get_logger

from .harness_runners import (
    _detect_from_cargo_toml,
    _detect_from_github_workflows,
    _detect_from_makefile,
    _detect_from_pytest_ini,
    _detect_from_setup_cfg,
)

logger = get_logger(__name__)
PYTHON_BIN = shlex.quote(sys.executable)

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]


@dataclass
class MCTestHarness:
    """Detected test harness commands for a repository.

    Attributes:
        test_command: Full test suite command (e.g., "pytest tests/ -v")
        lint_command: Linting/style check command (e.g., "ruff check src/")
        build_command: Build/compile command (e.g., "npm run build")
        smoke_test: Fast subset of tests for quick validation
    """

    test_command: Optional[str] = None
    lint_command: Optional[str] = None
    build_command: Optional[str] = None
    smoke_test: Optional[str] = None


# Backward compatibility alias (prevents pytest from treating it as a test class)
TestHarness = MCTestHarness


def detect_harness(repo_path: Path) -> MCTestHarness:
    """Auto-detect test harness from repository structure."""
    if not repo_path.is_dir():
        return MCTestHarness()

    harness = MCTestHarness()

    # Priority order: specific configs > package managers > Makefile > CI
    _detect_from_pyproject(repo_path, harness)
    _detect_from_package_json(repo_path, harness)
    _detect_from_cargo_toml(repo_path, harness)
    _detect_from_pytest_ini(repo_path, harness)
    _detect_from_setup_cfg(repo_path, harness)
    _detect_from_makefile(repo_path, harness)
    _detect_from_github_workflows(repo_path, harness)

    return harness


def _detect_from_pyproject(repo_path: Path, harness: MCTestHarness) -> None:
    """Detect Python test commands from pyproject.toml."""
    pyproject_file = repo_path / "pyproject.toml"
    if not pyproject_file.exists() or tomllib is None:
        return

    try:
        with open(pyproject_file, "rb") as f:
            data = tomllib.load(f)

        # Test command - check for pytest configuration
        if "tool" in data and "pytest" in data["tool"]:
            pytest_opts = data["tool"]["pytest"].get("ini_options", {})
            testpaths = pytest_opts.get("testpaths", ["tests"])
            if isinstance(testpaths, list):
                testpaths_str = " ".join(testpaths)
            else:
                testpaths_str = str(testpaths)

            # Add verbosity if not specified
            addopts = pytest_opts.get("addopts", "")
            verbose_flag = "-v" if "-v" not in addopts else ""

            harness.test_command = f"{PYTHON_BIN} -m pytest {testpaths_str} {verbose_flag}".strip()

            # Smoke test - run a subset (first test path only)
            if isinstance(testpaths, list) and testpaths:
                harness.smoke_test = (
                    f"{PYTHON_BIN} -m pytest {testpaths[0]} {verbose_flag} -x".strip()
                )

        # Lint command - check for ruff configuration
        if "tool" in data and "ruff" in data["tool"]:
            harness.lint_command = f"{PYTHON_BIN} -m ruff check src/"

        # Also check for mypy
        if "tool" in data and "mypy" in data["tool"]:
            if harness.lint_command:
                harness.lint_command += f" && {PYTHON_BIN} -m mypy src/"
            else:
                harness.lint_command = f"{PYTHON_BIN} -m mypy src/"

        # Check for build system
        if "build-system" in data:
            build_backend = data["build-system"].get("build-backend", "")
            if "hatch" in build_backend:
                harness.build_command = "hatch build"
            elif "setuptools" in build_backend:
                harness.build_command = f"{PYTHON_BIN} -m build"
            elif "poetry" in build_backend:
                harness.build_command = "poetry build"

    except (OSError, tomllib.TOMLDecodeError) as e:
        logger.warning(
            "pyproject.toml parse failed",
            path=str(pyproject_file),
            error_type=type(e).__name__,
            error=str(e),
        )
        return


def _detect_from_package_json(repo_path: Path, harness: MCTestHarness) -> None:
    """Detect Node.js/JavaScript test commands from package.json."""
    package_json = repo_path / "package.json"
    if not package_json.exists():
        return

    try:
        with open(package_json, "r") as f:
            data = json.load(f)

        scripts = data.get("scripts", {})

        # Test command
        if "test" in scripts and not harness.test_command:
            harness.test_command = "npm test"

        # Lint command
        if "lint" in scripts and not harness.lint_command:
            harness.lint_command = "npm run lint"

        # Build command
        if "build" in scripts and not harness.build_command:
            harness.build_command = "npm run build"

        # Smoke test - look for test:unit or test:quick
        if "test:unit" in scripts and not harness.smoke_test:
            harness.smoke_test = "npm run test:unit"
        elif "test:quick" in scripts and not harness.smoke_test:
            harness.smoke_test = "npm run test:quick"

    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.warning(
            "package.json parse failed",
            path=str(package_json),
            error_type=type(e).__name__,
            error=str(e),
        )
        return
