"""Tests for CLI functions."""

import json
import tempfile
from pathlib import Path

import pytest

pytestmark = [pytest.mark.smoke, pytest.mark.critical]


class TestRiskAssessment:
    """Test risk assessment logic."""

    def test_safe_operations(self):
        """Test safe operations are classified correctly."""
        from motus.cli import assess_risk
        from motus.schema.events import RiskLevel

        assert assess_risk("Read", {"file_path": "/test.py"}) == RiskLevel.SAFE
        assert assess_risk("Glob", {"pattern": "*.py"}) == RiskLevel.SAFE
        assert assess_risk("Grep", {"pattern": "test"}) == RiskLevel.SAFE

    def test_medium_risk_operations(self):
        """Test medium risk operations."""
        from motus.cli import assess_risk
        from motus.schema.events import RiskLevel

        assert assess_risk("Write", {"file_path": "/test.py"}) == RiskLevel.MEDIUM
        assert assess_risk("Edit", {"file_path": "/test.py"}) == RiskLevel.MEDIUM

    def test_high_risk_operations(self):
        """Test high risk operations."""
        from motus.cli import assess_risk
        from motus.schema.events import RiskLevel

        assert assess_risk("Bash", {"command": "ls -la"}) == RiskLevel.HIGH

    def test_critical_operations(self):
        """Test critical/destructive operations."""
        from motus.cli import assess_risk
        from motus.schema.events import RiskLevel

        assert assess_risk("Bash", {"command": "rm -rf /tmp/test"}) == RiskLevel.CRITICAL
        assert assess_risk("Bash", {"command": "git reset --hard"}) == RiskLevel.CRITICAL
        assert assess_risk("Bash", {"command": "sudo apt install"}) == RiskLevel.CRITICAL

    def test_sensitive_file_detection(self):
        """Test sensitive file path detection."""
        from motus.cli import assess_risk
        from motus.schema.events import RiskLevel

        assert assess_risk("Edit", {"file_path": ".env"}) == RiskLevel.HIGH
        assert assess_risk("Write", {"file_path": "/path/credentials.json"}) == RiskLevel.HIGH
        assert assess_risk("Edit", {"file_path": "/path/secret_key.txt"}) == RiskLevel.HIGH


class TestTranscriptParsing:
    """Test transcript line parsing."""

    def test_parse_thinking_event(self):
        """Test parsing thinking events."""
        from motus.cli import ThinkingEvent, parse_transcript_line

        line = json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [{"type": "thinking", "thinking": "Let me analyze this..."}]
                },
            }
        )

        events = parse_transcript_line(line)
        assert len(events) == 1
        assert isinstance(events[0], ThinkingEvent)
        assert "analyze" in events[0].content

    def test_parse_tool_event(self):
        """Test parsing tool events."""
        from motus.cli import ToolEvent, parse_transcript_line

        line = json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "tool_use", "name": "Read", "input": {"file_path": "/test.py"}}
                    ]
                },
            }
        )

        events = parse_transcript_line(line)
        assert len(events) == 1
        assert isinstance(events[0], ToolEvent)
        assert events[0].name == "Read"
        assert events[0].input["file_path"] == "/test.py"

    def test_parse_task_event(self):
        """Test parsing Task/subagent events."""
        from motus.cli import TaskEvent, parse_transcript_line

        line = json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Task",
                            "input": {
                                "description": "Search codebase",
                                "prompt": "Find all Python files",
                                "subagent_type": "Explore",
                                "model": "haiku",
                            },
                        }
                    ]
                },
            }
        )

        events = parse_transcript_line(line)
        assert len(events) == 1
        assert isinstance(events[0], TaskEvent)
        assert events[0].subagent_type == "Explore"
        assert events[0].model == "haiku"

    def test_parse_invalid_json(self):
        """Test handling of invalid JSON."""
        from motus.cli import parse_transcript_line

        events = parse_transcript_line("not valid json")
        assert events == []

    def test_parse_non_assistant_message(self):
        """Test non-assistant messages are ignored."""
        from motus.cli import parse_transcript_line

        line = json.dumps({"type": "user", "message": "Hello"})
        events = parse_transcript_line(line)
        assert events == []


class TestProjectPathExtraction:
    """Test project path extraction from encoded names."""

    def test_extract_project_path(self):
        """Test extracting readable path from encoded directory name."""
        from motus.commands.utils import extract_project_path

        # Claude encodes: /home/user/projects/myapp -> -home-user-projects-myapp
        result = extract_project_path("-home-user-projects-myapp")
        assert "projects/myapp" in result or "myapp" in result

    def test_extract_short_path(self):
        """Test short paths are handled correctly."""
        from motus.commands.utils import extract_project_path

        result = extract_project_path("-home-test")
        assert "/" in result


class TestTeleportCommand:
    """Test teleport_command function - critical for v0.3.1 regression prevention."""

    def test_teleport_command_import(self):
        """Verify teleport_command uses correct orchestrator import."""
        # This test ensures we don't regress to using non-existent methods
        from motus.cli import teleport_command

        # teleport_command should be callable
        assert callable(teleport_command)

    def test_teleport_command_uses_get_orchestrator(self):
        """Verify teleport_command imports get_orchestrator (not SessionOrchestrator class)."""
        import inspect

        from motus.cli import teleport_command

        source = inspect.getsource(teleport_command)

        # Should use get_orchestrator(), not SessionOrchestrator()
        assert "get_orchestrator" in source
        # Should NOT instantiate SessionOrchestrator directly (regression check)
        assert "SessionOrchestrator()" not in source

    def test_teleport_command_uses_discover_all(self):
        """Verify teleport_command uses discover_all method (not find_sessions)."""
        import inspect

        from motus.cli import teleport_command

        source = inspect.getsource(teleport_command)

        # Should use discover_all, not non-existent find_sessions
        assert "discover_all" in source
        # Should NOT call non-existent find_sessions method (regression check)
        assert "find_sessions" not in source

    def test_teleport_command_session_not_found(self):
        """Test teleport_command handles missing sessions gracefully."""
        from argparse import Namespace
        from unittest.mock import MagicMock, patch

        from motus.cli import teleport_command

        # Mock args
        args = Namespace(session_id="nonexistent-session-xyz", no_docs=False, output=None)

        # Mock orchestrator to return empty sessions list
        mock_orch = MagicMock()
        mock_orch.discover_all.return_value = []

        # Patch the orchestrator module's get_orchestrator (which is imported inside teleport_command)
        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            # Should not raise, just print error
            teleport_command(args)

        # Verify discover_all was called with correct args
        mock_orch.discover_all.assert_called_once_with(max_age_hours=168)

    def test_teleport_command_exports_bundle(self):
        """Test teleport_command correctly exports a bundle when session exists."""
        import json
        from argparse import Namespace
        from datetime import datetime
        from pathlib import Path
        from unittest.mock import MagicMock, patch

        from motus.cli import teleport_command
        from motus.protocols import SessionStatus, Source, TeleportBundle, UnifiedSession

        # Mock session
        mock_session = UnifiedSession(
            session_id="test-session-123",
            source=Source.CLAUDE,
            file_path=Path("/tmp/test.jsonl"),
            project_path="/project",
            status=SessionStatus.ACTIVE,
            status_reason="test",
            created_at=datetime.now(),
            last_modified=datetime.now(),
        )

        # Mock bundle
        mock_bundle = TeleportBundle(
            source_session="test-session-123",
            source_model="claude",
            intent="Test intent",
            decisions=["Decision 1"],
            files_touched=["file.py"],
            hot_files=["file.py"],
            pending_todos=[],
            last_action="Edit file.py",
            timestamp=datetime.now(),
            planning_docs={},
        )

        # Mock orchestrator
        mock_orch = MagicMock()
        mock_orch.discover_all.return_value = [mock_session]
        mock_orch.export_teleport.return_value = mock_bundle

        # Mock args - use prefix match
        args = Namespace(session_id="test-session", no_docs=False, output=None)

        # Patch the orchestrator module's get_orchestrator (which is imported inside teleport_command)
        with patch("motus.orchestrator.get_orchestrator", return_value=mock_orch):
            # Capture stdout
            import sys
            from io import StringIO

            captured = StringIO()
            old_stdout = sys.stdout
            sys.stdout = captured

            try:
                teleport_command(args)
            finally:
                sys.stdout = old_stdout

            output = captured.getvalue()

        # Should have called export_teleport
        mock_orch.export_teleport.assert_called_once()

        # Output should be valid JSON
        bundle_data = json.loads(output)
        assert bundle_data["source_session"] == "test-session-123"
        assert bundle_data["source_model"] == "claude"

    def test_orchestrator_has_required_methods(self):
        """Verify SessionOrchestrator has all methods used by teleport_command."""
        from motus.orchestrator import SessionOrchestrator

        orch = SessionOrchestrator()

        # These methods must exist (regression prevention)
        assert hasattr(orch, "discover_all"), "discover_all method missing"
        assert hasattr(orch, "export_teleport"), "export_teleport method missing"
        assert callable(orch.discover_all)
        assert callable(orch.export_teleport)

        # Verify method signatures accept the expected arguments
        import inspect

        discover_sig = inspect.signature(orch.discover_all)
        assert "max_age_hours" in discover_sig.parameters

        export_sig = inspect.signature(orch.export_teleport)
        assert "session" in export_sig.parameters
        assert "include_planning_docs" in export_sig.parameters


class TestDecisionExtraction:
    """Test decision pattern extraction from thinking blocks."""

    def test_extract_decisions(self):
        """Test extracting decisions from a session file."""
        from motus.cli import extract_decisions

        # Create a test file with thinking blocks
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {
                            "content": [
                                {
                                    "type": "thinking",
                                    "thinking": "I'll use SQLite because it's simpler.",
                                }
                            ]
                        },
                    }
                )
                + "\n"
            )
            f.write(
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {
                            "content": [
                                {
                                    "type": "thinking",
                                    "thinking": "I decided to use async for better performance.",
                                }
                            ]
                        },
                    }
                )
                + "\n"
            )
            temp_path = Path(f.name)

        try:
            decisions = extract_decisions(temp_path)
            assert len(decisions) >= 1
            assert any("SQLite" in d or "async" in d for d in decisions)
        finally:
            temp_path.unlink()
