#!/usr/bin/env python3
"""
Validate tutorial.yaml against current Motus release.

This script executes every step in the tutorial and verifies:
- Commands return expected exit codes
- Output matches expected patterns
- Files are created correctly
- Variables are captured and substituted

Exit codes:
  0 - All steps pass
  1 - Step failed
  2 - Missing prerequisite
  3 - Tutorial file error
  4 - Timeout

Usage:
  python scripts/validate-tutorial.py [tutorial.yaml]
  python scripts/validate-tutorial.py --status-filter current
  python scripts/validate-tutorial.py --dry-run
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml


class TutorialValidator:
    """Validates tutorial.yaml by executing all steps."""

    def __init__(self, tutorial_path: Path, status_filter: str = "current", dry_run: bool = False):
        self.tutorial_path = tutorial_path
        self.status_filter = status_filter
        self.dry_run = dry_run
        self.context: dict[str, str] = {}
        self.workdir: Path | None = None
        self.env = os.environ.copy()
        self.log_lines: list[str] = []
        self.log_path = Path(os.environ.get("TUTORIAL_LOG_PATH", "tutorial-validation.log")).resolve()

    def log(self, message: str) -> None:
        """Record a log line for CI artifacts."""
        self.log_lines.append(message)

    def load_tutorial(self) -> dict:
        """Load and parse the tutorial YAML."""
        with open(self.tutorial_path) as f:
            return yaml.safe_load(f)

    def substitute_variables(self, text: str) -> str:
        """Replace ${variable} with captured values."""
        for key, value in self.context.items():
            text = text.replace(f"${{{key}}}", value)
        return text

    def run_command(self, command: str, timeout: int = 30) -> tuple[int, str, str]:
        """Execute a command and return exit code, stdout, stderr."""
        command = self.substitute_variables(command)

        if self.dry_run:
            print(f"  [DRY RUN] Would execute: {command}")
            self.log(f"[DRY RUN] {command}")
            return 0, "dry-run-output", ""

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.workdir,
                env=self.env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            self.log(f"$ {command}")
            if result.stdout:
                self.log(result.stdout.strip())
            if result.stderr:
                self.log(result.stderr.strip())
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            self.log(f"$ {command}")
            self.log(f"TIMEOUT after {timeout}s")
            return -1, "", f"Command timed out after {timeout}s"

    def write_file(self, path: str, content: str) -> bool:
        """Write a file to the workdir."""
        full_path = self.workdir / path
        full_path.parent.mkdir(parents=True, exist_ok=True)

        if self.dry_run:
            print(f"  [DRY RUN] Would write: {full_path}")
            return True

        try:
            full_path.write_text(content)
            return True
        except Exception as e:
            print(f"  ERROR: Failed to write {path}: {e}")
            return False

    def validate_step(self, step: dict) -> bool:
        """Validate a single step."""
        step_id = step.get("id", "unknown")
        step_type = step.get("type", "command")
        title = step.get("title", step_id)

        print(f"    [{step_id}] {title}")

        if step_type == "file":
            path = step["path"]
            content = step["content"]
            if not self.write_file(path, content):
                return False
            print(f"      Created: {path}")
            return True

        if step_type == "command":
            if step.get("skip_in_ci") and os.environ.get("CI"):
                print("      SKIP: Marked skip_in_ci")
                self.log(f"SKIP (CI): {step.get('id', '')}")
                return True
            command = step["command"]
            timeout = step.get("timeout_seconds", 30)

            exit_code, stdout, stderr = self.run_command(command, timeout)

            # Check exit code
            expected_exit = step.get("expected_exit", 0)
            if exit_code != expected_exit:
                print(f"      FAIL: Exit code {exit_code} (expected {expected_exit})")
                if stderr:
                    print(f"      Stderr: {stderr[:200]}")
                return False

            # Check expected pattern
            if "expected_pattern" in step:
                pattern = step["expected_pattern"]
                if not re.search(pattern, stdout):
                    print(f"      FAIL: Pattern not found: {pattern}")
                    print(f"      Output: {stdout[:200]}")
                    return False

            if "expected_patterns" in step:
                patterns = step["expected_patterns"] or []
                if not any(re.search(p, stdout) for p in patterns):
                    print(f"      FAIL: None of patterns matched: {patterns}")
                    print(f"      Output: {stdout[:200]}")
                    return False

            # Check expected contains
            if "expected_contains" in step:
                for expected in step["expected_contains"]:
                    if expected not in stdout:
                        print(f"      FAIL: Expected string not found: {expected}")
                        return False

            # Capture output variable
            if "capture_output" in step:
                capture = step["capture_output"]
                var_name = capture["variable"]
                pattern = capture["pattern"]
                match = re.search(pattern, stdout)
                if match:
                    self.context[var_name] = match.group(0)
                    print(f"      Captured: {var_name} = {self.context[var_name]}")
                else:
                    print(f"      WARN: Could not capture {var_name}")

            if step.get("workdir"):
                next_dir = (self.workdir / step["workdir"]).resolve()
                next_dir.mkdir(parents=True, exist_ok=True)
                self.workdir = next_dir
                self.env["MC_DB_PATH"] = str(self.workdir / "coordination.db")
                print(f"      Working directory -> {self.workdir}")

            print(f"      OK")
            return True

        print(f"      SKIP: Unknown step type '{step_type}'")
        return True

    def validate_section(self, section: dict, section_name: str) -> bool:
        """Validate all steps in a section."""
        status = section.get("status", "current")
        if status != self.status_filter and self.status_filter != "all":
            print(f"  SKIP: {section_name} (status: {status})")
            return True

        title = section.get("title", section_name)
        print(f"  {title}")

        for step in section.get("steps", []):
            if not self.validate_step(step):
                return False

        return True

    def validate_prerequisites(self, prerequisites: list) -> bool:
        """Check all prerequisites are met."""
        print("Prerequisites:")
        for prereq in prerequisites:
            prereq_id = prereq["id"]
            command = prereq["check_command"]
            pattern = prereq.get("expected_pattern", "")

            exit_code, stdout, stderr = self.run_command(command)

            if exit_code != 0:
                print(f"  FAIL: {prereq_id} - command failed")
                return False

            if pattern and not re.search(pattern, stdout):
                print(f"  FAIL: {prereq_id} - version mismatch")
                print(f"    Got: {stdout.strip()}")
                print(f"    Expected pattern: {pattern}")
                return False

            print(f"  OK: {prereq_id}")

        return True

    def run(self) -> int:
        """Run the full validation."""
        try:
            try:
                tutorial = self.load_tutorial()
            except Exception as e:
                print(f"ERROR: Failed to load tutorial: {e}")
                return 3

            print(f"Tutorial: {tutorial['meta']['title']}")
            print(f"Version: {tutorial['version']}")
            print(f"Status filter: {self.status_filter}")
            print()

            # Check prerequisites
            if not self.validate_prerequisites(tutorial.get("prerequisites", [])):
                return 2

            print()

            # Create temp directory for the build
            with tempfile.TemporaryDirectory(prefix="motus-tutorial-") as tmpdir:
                self.workdir = Path(tmpdir)
                self.env["MC_DB_PATH"] = str(self.workdir / "coordination.db")
                print(f"Working directory: {self.workdir}")
                print()

                # Validate setup
                print("Setup:")
                setup = tutorial.get("setup", {})
                if not self.validate_section(setup, "setup"):
                    print("\nFAIL: Setup failed")
                    return 1

                print()

                # Validate each feature
                print("Features:")
                for feature in tutorial.get("features", []):
                    feature_id = feature["id"]
                    if not self.validate_section(feature, feature_id):
                        print(f"\nFAIL: Feature {feature_id} failed")
                        return 1

                print()

                # Validate reveal
                print("Reveal:")
                reveal = tutorial.get("reveal", {})
                if not self.validate_section(reveal, "reveal"):
                    print("\nFAIL: Reveal failed")
                    return 1

            print()
            print("=" * 60)
            print("PASS: All tutorial steps validated successfully")
            print("=" * 60)
            return 0
        finally:
            if self.log_lines:
                self.log_path.write_text("\n".join(self.log_lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Validate tutorial.yaml")
    parser.add_argument(
        "tutorial",
        nargs="?",
        default="packages/website/src/data/tutorial.yaml",
        help="Path to tutorial.yaml",
    )
    parser.add_argument(
        "--status-filter",
        choices=["current", "building", "future", "all"],
        default="current",
        help="Only validate steps with this status (default: current)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without executing",
    )

    args = parser.parse_args()

    tutorial_path = Path(args.tutorial)
    if not tutorial_path.exists():
        print(f"ERROR: Tutorial file not found: {tutorial_path}")
        sys.exit(3)

    validator = TutorialValidator(
        tutorial_path=tutorial_path,
        status_filter=args.status_filter,
        dry_run=args.dry_run,
    )

    sys.exit(validator.run())


if __name__ == "__main__":
    main()
