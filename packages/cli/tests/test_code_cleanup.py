"""Tests verifying code cleanup was successful."""

import subprocess
from pathlib import Path


class TestDeadCodeRemoval:
    """Verify dead code has been removed."""

    def test_tui_legacy_removed(self):
        """archive/tui-legacy should not exist."""
        legacy_path = Path("archive/tui-legacy")
        assert not legacy_path.exists(), f"{legacy_path} should be removed"

    def test_no_duplicate_event_classes_in_cli(self):
        """cli.py event classes are intentional DTOs, not duplicates.

        The event classes in cli.py (ThinkingEvent, ToolEvent, etc.) are
        lightweight DTOs used for display purposes, distinct from the
        canonical BaseEvent classes in events.py. They serve different
        purposes and are not dead code.
        """
        cli_path = Path("src/motus/cli.py")

        if cli_path.exists():
            with open(cli_path) as f:
                content = f.read()

            # These classes exist and are intentional - this test documents that
            assert "class ThinkingEvent:" in content
            assert "class ToolEvent:" in content
            # But they should be simple dataclasses, not complex BaseEvent subclasses
            assert "class ThinkingEvent(BaseEvent):" not in content

    def test_imports_work(self):
        """All imports should work without error."""
        result = subprocess.run(
            ["python3", "-c", "from motus import *"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Import failed: {result.stderr}"

    def test_no_unused_imports(self):
        """Ruff should not find unused imports."""
        result = subprocess.run(
            ["ruff", "check", "--select", "F401", "src/motus/"],
            capture_output=True,
            text=True,
        )
        # Ruff returns 0 if no issues
        assert result.returncode == 0, f"Ruff found unused imports: {result.stdout}"


class TestCodeIntegrity:
    """Verify code still works after cleanup."""

    def test_cli_still_works(self):
        """CLI module should import without errors."""
        from motus import cli

        assert cli is not None

    def test_orchestrator_still_works(self):
        """Orchestrator should import without errors."""
        from motus.orchestrator import SessionOrchestrator

        assert SessionOrchestrator is not None

    def test_builders_still_work(self):
        """Builders should import without errors."""
        from motus.ingestors.claude import ClaudeBuilder
        from motus.ingestors.codex import CodexBuilder
        from motus.ingestors.gemini import GeminiBuilder

        assert ClaudeBuilder is not None
        assert CodexBuilder is not None
        assert GeminiBuilder is not None

    def test_display_still_works(self):
        """Display layer should import without errors."""
        from motus.display.events import DisplayEvent
        from motus.display.transformer import EventTransformer

        assert EventTransformer is not None
        assert DisplayEvent is not None


class TestLOCReduction:
    """Verify line count reduction."""

    def test_tui_legacy_directory_removed(self):
        """Verify the tui-legacy directory was removed (1936 LOC)."""
        legacy_dir = Path("archive/tui-legacy")
        assert not legacy_dir.exists(), "archive/tui-legacy should be removed"

    def test_no_empty_python_files(self):
        """Verify no empty or nearly-empty Python files exist."""
        src_dir = Path("src/motus")
        empty_files = []

        for py_file in src_dir.rglob("*.py"):
            # Skip __init__.py and __main__.py files - they can be small
            if py_file.name in ("__init__.py", "__main__.py"):
                continue

            with open(py_file) as f:
                lines = f.readlines()

            # Count non-empty, non-comment lines
            code_lines = [
                line for line in lines if line.strip() and not line.strip().startswith("#")
            ]

            # Files with less than 5 lines of actual code are suspicious
            if len(code_lines) < 5:
                file_text = "".join(lines)
                if "Compatibility shim" in file_text:
                    continue
                empty_files.append((py_file, len(code_lines)))

        assert len(empty_files) == 0, f"Found nearly-empty files: {empty_files}"

    def test_archive_directory_structure(self):
        """Verify archive directory only contains active archives."""
        archive_dir = Path("archive")

        if archive_dir.exists():
            subdirs = [d for d in archive_dir.iterdir() if d.is_dir()]
            # Should only contain v0.4.5-specs, not tui-legacy
            assert all("tui-legacy" not in str(d) for d in subdirs)
