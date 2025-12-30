"""Tests for test harness detection module."""

import json
import tempfile
from pathlib import Path

from motus.harness import MCTestHarness, detect_harness


class TestMCTestHarness:
    """Test MCTestHarness dataclass."""

    def test_defaults(self):
        """Test default values are all None."""
        harness = MCTestHarness()
        assert harness.test_command is None
        assert harness.lint_command is None
        assert harness.build_command is None
        assert harness.smoke_test is None

    def test_with_values(self):
        """Test creating harness with values."""
        harness = MCTestHarness(
            test_command="pytest tests/",
            lint_command="ruff check src/",
            build_command="hatch build",
            smoke_test="pytest tests/ -x",
        )
        assert harness.test_command == "pytest tests/"
        assert harness.lint_command == "ruff check src/"
        assert harness.build_command == "hatch build"
        assert harness.smoke_test == "pytest tests/ -x"


class TestDetectHarnessEmpty:
    """Test harness detection with empty/missing configs."""

    def test_empty_directory(self):
        """Test detection in empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            harness = detect_harness(Path(tmpdir))
            assert harness.test_command is None
            assert harness.lint_command is None
            assert harness.build_command is None
            assert harness.smoke_test is None

    def test_nonexistent_directory(self):
        """Test detection with non-existent directory."""
        harness = detect_harness(Path("/nonexistent/path"))
        assert harness.test_command is None


class TestDetectPyproject:
    """Test detection from pyproject.toml."""

    def test_pytest_config(self):
        """Test pytest detection from pyproject.toml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pyproject = Path(tmpdir) / "pyproject.toml"
            pyproject.write_text(
                """
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v"
"""
            )

            harness = detect_harness(Path(tmpdir))
            assert harness.test_command is not None
            assert "pytest" in harness.test_command
            assert "tests" in harness.test_command

    def test_ruff_config(self):
        """Test ruff detection from pyproject.toml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pyproject = Path(tmpdir) / "pyproject.toml"
            pyproject.write_text(
                """
[tool.ruff]
line-length = 100
"""
            )

            harness = detect_harness(Path(tmpdir))
            assert harness.lint_command is not None
            assert "ruff" in harness.lint_command

    def test_mypy_config(self):
        """Test mypy detection from pyproject.toml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pyproject = Path(tmpdir) / "pyproject.toml"
            pyproject.write_text(
                """
[tool.mypy]
python_version = "3.10"
"""
            )

            harness = detect_harness(Path(tmpdir))
            assert harness.lint_command is not None
            assert "mypy" in harness.lint_command

    def test_hatch_build(self):
        """Test hatch build detection from pyproject.toml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pyproject = Path(tmpdir) / "pyproject.toml"
            pyproject.write_text(
                """
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
"""
            )

            harness = detect_harness(Path(tmpdir))
            assert harness.build_command == "hatch build"


class TestDetectPackageJson:
    """Test detection from package.json."""

    def test_npm_test(self):
        """Test npm test detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            package_json = Path(tmpdir) / "package.json"
            package_json.write_text(
                json.dumps(
                    {
                        "scripts": {
                            "test": "jest",
                            "lint": "eslint src/",
                            "build": "webpack",
                        }
                    }
                )
            )

            harness = detect_harness(Path(tmpdir))
            assert harness.test_command == "npm test"
            assert harness.lint_command == "npm run lint"
            assert harness.build_command == "npm run build"

    def test_test_unit_smoke_test(self):
        """Test detection of test:unit as smoke test."""
        with tempfile.TemporaryDirectory() as tmpdir:
            package_json = Path(tmpdir) / "package.json"
            package_json.write_text(
                json.dumps({"scripts": {"test": "jest", "test:unit": "jest --unit"}})
            )

            harness = detect_harness(Path(tmpdir))
            assert harness.smoke_test == "npm run test:unit"


class TestDetectCargoToml:
    """Test detection from Cargo.toml."""

    def test_cargo_detection(self):
        """Test Rust cargo detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cargo_toml = Path(tmpdir) / "Cargo.toml"
            cargo_toml.write_text(
                """
[package]
name = "myapp"
version = "0.1.0"
"""
            )

            harness = detect_harness(Path(tmpdir))
            assert harness.test_command == "cargo test"
            assert harness.lint_command == "cargo clippy"
            assert harness.build_command == "cargo build"
            assert harness.smoke_test == "cargo test --lib"


class TestDetectMakefile:
    """Test detection from Makefile."""

    def test_makefile_targets(self):
        """Test detection of make targets."""
        with tempfile.TemporaryDirectory() as tmpdir:
            makefile = Path(tmpdir) / "Makefile"
            makefile.write_text(
                """
test:
\tpytest tests/

lint:
\truff check src/

build:
\tpython -m build
"""
            )

            harness = detect_harness(Path(tmpdir))
            assert harness.test_command == "make test"
            assert harness.lint_command == "make lint"
            assert harness.build_command == "make build"

    def test_makefile_variants(self):
        """Test detection from makefile (lowercase) and GNUmakefile."""
        with tempfile.TemporaryDirectory() as tmpdir:
            makefile = Path(tmpdir) / "makefile"
            makefile.write_text("test:\n\tpytest\n")

            harness = detect_harness(Path(tmpdir))
            assert harness.test_command == "make test"


class TestDetectPytestIni:
    """Test detection from pytest.ini."""

    def test_pytest_ini(self):
        """Test detection from pytest.ini."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pytest_ini = Path(tmpdir) / "pytest.ini"
            pytest_ini.write_text(
                """
[pytest]
testpaths = tests
"""
            )

            harness = detect_harness(Path(tmpdir))
            assert harness.test_command is not None
            assert "pytest" in harness.test_command
            assert "tests" in harness.test_command


class TestDetectSetupCfg:
    """Test detection from setup.cfg."""

    def test_setup_cfg(self):
        """Test detection from setup.cfg."""
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_cfg = Path(tmpdir) / "setup.cfg"
            setup_cfg.write_text(
                """
[tool:pytest]
testpaths = tests
"""
            )

            harness = detect_harness(Path(tmpdir))
            assert harness.test_command is not None
            assert "pytest" in harness.test_command


class TestPriorityOrder:
    """Test that sources are detected in priority order."""

    def test_pyproject_overrides_makefile(self):
        """Test pyproject.toml takes priority over Makefile."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create both files
            makefile = Path(tmpdir) / "Makefile"
            makefile.write_text("test:\n\tmake-test\n")

            pyproject = Path(tmpdir) / "pyproject.toml"
            pyproject.write_text(
                """
[tool.pytest.ini_options]
testpaths = ["tests"]
"""
            )

            harness = detect_harness(Path(tmpdir))
            # pyproject should win
            assert "pytest" in harness.test_command
            assert "make" not in harness.test_command

    def test_package_json_for_node_project(self):
        """Test package.json is used for Node projects."""
        with tempfile.TemporaryDirectory() as tmpdir:
            package_json = Path(tmpdir) / "package.json"
            package_json.write_text(json.dumps({"scripts": {"test": "jest"}}))

            harness = detect_harness(Path(tmpdir))
            assert harness.test_command == "npm test"


class TestRealWorldScenarios:
    """Test real-world project configurations."""

    def test_python_project_full_stack(self):
        """Test comprehensive Python project detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pyproject = Path(tmpdir) / "pyproject.toml"
            pyproject.write_text(
                """
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --cov"

[tool.ruff]
line-length = 100

[tool.mypy]
python_version = "3.10"
"""
            )

            harness = detect_harness(Path(tmpdir))
            assert "pytest" in harness.test_command
            assert "tests" in harness.test_command
            assert "ruff" in harness.lint_command
            assert "mypy" in harness.lint_command
            assert harness.build_command == "hatch build"
            assert harness.smoke_test is not None
            assert "-x" in harness.smoke_test  # Fail fast for smoke tests


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_invalid_json_in_package_json(self):
        """Test graceful handling of invalid package.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            package_json = Path(tmpdir) / "package.json"
            package_json.write_text("{ invalid json }")

            harness = detect_harness(Path(tmpdir))
            # Should not crash, just return empty harness
            assert harness.test_command is None

    def test_multiple_testpaths(self):
        """Test handling of multiple testpaths in pytest config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pyproject = Path(tmpdir) / "pyproject.toml"
            pyproject.write_text(
                """
[tool.pytest.ini_options]
testpaths = ["tests", "integration"]
"""
            )

            harness = detect_harness(Path(tmpdir))
            assert "tests" in harness.test_command
            # Smoke test should only use first path
            assert "tests" in harness.smoke_test
            assert "integration" not in harness.smoke_test


class TestCommandsModule:
    """Test the commands.harness_cmd module."""

    def test_harness_command_import(self):
        """Test that harness_command can be imported."""
        from motus.commands.harness_cmd import harness_command

        assert callable(harness_command)

    def test_harness_command_no_crash_on_empty_dir(self):
        """Test harness_command doesn't crash on empty directory."""
        from motus.commands.harness_cmd import harness_command

        with tempfile.TemporaryDirectory() as tmpdir:
            import os

            os.chdir(tmpdir)
            # Should not crash, just print a message
            harness_command(save=False)
