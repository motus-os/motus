# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from motus.bench.harness import BenchmarkTask
from motus.exceptions import SubprocessError, SubprocessTimeoutError
from motus.subprocess_utils import GIT_LONG_TIMEOUT_SECONDS, run_subprocess


def _git(repo_dir: Path, argv: Sequence[str]) -> None:
    try:
        proc = run_subprocess(
            ["git", *argv],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=False,
            timeout_seconds=GIT_LONG_TIMEOUT_SECONDS,
            what="git",
        )
    except (SubprocessTimeoutError, SubprocessError) as e:
        raise RuntimeError(str(e)) from e
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or f"git {' '.join(argv)} failed")


def _build_python_fixture_repo(repo_dir: Path) -> None:
    (repo_dir / "src").mkdir(parents=True, exist_ok=True)
    (repo_dir / "tests").mkdir(parents=True, exist_ok=True)

    (repo_dir / "README.md").write_text("demo repo\n", encoding="utf-8")
    (repo_dir / "src/app.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n\nVALUE = 0\n",
        encoding="utf-8",
    )
    (repo_dir / "tests/test_app.py").write_text(
        "from __future__ import annotations\n"
        "\n"
        "import sys\n"
        "from pathlib import Path\n"
        "\n"
        "sys.path.append(str(Path(__file__).resolve().parents[1] / 'src'))\n"
        "import app\n"
        "\n"
        "\n"
        "def test_add() -> None:\n"
        "    assert app.add(1, 2) == 3\n",
        encoding="utf-8",
    )
    (repo_dir / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\n"
        "testpaths = ['tests']\n"
        "\n"
        "[tool.ruff]\n"
        "line-length = 88\n"
        "\n"
        "[tool.mypy]\n"
        "python_version = '3.10'\n",
        encoding="utf-8",
    )

    _git(repo_dir, ["init"])
    _git(repo_dir, ["config", "user.email", "bench@example.com"])
    _git(repo_dir, ["config", "user.name", "Motus Bench"])
    _git(repo_dir, ["add", "-A"])
    _git(repo_dir, ["commit", "--allow-empty", "-m", "init"])


def _always_ok(_: Path) -> bool:
    return True


def kernel_suite_v0_1() -> list[BenchmarkTask]:
    """Kernel benchmark suite v0.1.

    This suite is intentionally small and covers:
    - Clean changes (should pass)
    - Planted violations (should be blocked by gates/reconciliation)
    """

    def write_clean_change(repo_dir: Path) -> None:
        (repo_dir / "src/app.py").write_text(
            "def add(a: int, b: int) -> int:\n    return a + b\n\nVALUE = 1\n",
            encoding="utf-8",
        )

    def write_lint_violation(repo_dir: Path) -> None:
        (repo_dir / "src/app.py").write_text(
            "def add(a: int, b: int) -> int:\n    unused = 123\n    return a + b\n\nVALUE = 0\n",
            encoding="utf-8",
        )

    def write_test_failure(repo_dir: Path) -> None:
        (repo_dir / "src/app.py").write_text(
            "def add(a: int, b: int) -> int:\n    return a - b\n\nVALUE = 0\n",
            encoding="utf-8",
        )

    def write_scope_creep(repo_dir: Path) -> None:
        write_clean_change(repo_dir)
        (repo_dir / "README.md").write_text("demo repo\nscope creep\n", encoding="utf-8")

    def write_multi_file_clean(repo_dir: Path) -> None:
        write_clean_change(repo_dir)
        (repo_dir / "README.md").write_text("demo repo\nupdated\n", encoding="utf-8")

    def write_type_error(repo_dir: Path) -> None:
        (repo_dir / "src/app.py").write_text(
            "def add(a: int, b: int) -> str:\n    return a + b\n\nVALUE = 0\n",
            encoding="utf-8",
        )

    return [
        BenchmarkTask(
            task_id="01-clean-change",
            description="Clean in-scope edit (should pass).",
            declared_scope=("src/app.py",),
            build_fixture=_build_python_fixture_repo,
            apply_changes=write_clean_change,
            evaluate=_always_ok,
        ),
        BenchmarkTask(
            task_id="02-lint-violation",
            description="Introduce a lint violation (should be blocked by gates).",
            declared_scope=("src/app.py",),
            build_fixture=_build_python_fixture_repo,
            apply_changes=write_lint_violation,
            evaluate=_always_ok,
        ),
        BenchmarkTask(
            task_id="03-test-failure",
            description="Introduce a unit test failure (should be blocked by gates).",
            declared_scope=("src/app.py",),
            build_fixture=_build_python_fixture_repo,
            apply_changes=write_test_failure,
            evaluate=_always_ok,
        ),
        BenchmarkTask(
            task_id="04-scope-creep",
            description="Modify a file outside declared scope (should be blocked by reconciliation).",
            declared_scope=("src/app.py",),
            build_fixture=_build_python_fixture_repo,
            apply_changes=write_scope_creep,
            evaluate=_always_ok,
        ),
        BenchmarkTask(
            task_id="05-multi-file-clean",
            description="Clean multi-file edit within scope (should pass).",
            declared_scope=("src/app.py", "README.md"),
            build_fixture=_build_python_fixture_repo,
            apply_changes=write_multi_file_clean,
            evaluate=_always_ok,
        ),
        BenchmarkTask(
            task_id="06-type-error",
            description="Introduce a type inconsistency (should be blocked by mypy).",
            declared_scope=("src/app.py",),
            build_fixture=_build_python_fixture_repo,
            apply_changes=write_type_error,
            evaluate=_always_ok,
        ),
    ]
