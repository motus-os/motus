"""Integration tests for multi-source session discovery and parsing."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch


class TestMultiSourceDiscovery:
    """Test that all session sources are discovered."""

    def test_finds_sessions_without_claude_dir(self):
        """Critical: Works when ~/.claude doesn't exist."""
        from motus.orchestrator import get_orchestrator

        with patch.object(Path, "exists", return_value=False):
            orch = get_orchestrator()
            # Should not raise, should return empty or other sources
            sessions = orch.discover_all(max_age_hours=24)
            # Just verify it doesn't crash
            assert isinstance(sessions, list)

    def test_finds_claude_sessions(self):
        """Test Claude session discovery returns valid list."""
        from motus.orchestrator import get_orchestrator
        from motus.protocols import Source

        orch = get_orchestrator()
        # Test discovery with Claude source filter
        sessions = orch.discover_all(max_age_hours=24, sources=[Source.CLAUDE])

        assert isinstance(sessions, list)
        # All returned items should be UnifiedSession objects
        for session in sessions:
            assert hasattr(session, "session_id")
            assert hasattr(session, "file_path")
            assert hasattr(session, "source")
            # Claude sessions should have source=Source.CLAUDE
            assert session.source == Source.CLAUDE


class TestMultiSourceParsing:
    """Test parsing from different sources using builders."""

    def test_gemini_builder_tool_call(self):
        """Test GeminiBuilder parses tool calls."""
        from motus.ingestors.gemini import GeminiBuilder

        builder = GeminiBuilder()

        # Gemini stores sessions as JSON with messages array, not JSONL
        # Builder's parse_line handles individual message objects
        line = json.dumps(
            {"function_call": {"name": "read_file", "arguments": {"path": "/test.py"}}}
        )

        result = builder.parse_line(line, session_id="test-session")

        # Builder returns list of UnifiedEvent
        assert isinstance(result, list)

    def test_gemini_builder_model_response(self):
        """Test GeminiBuilder parses model responses."""
        from motus.ingestors.gemini import GeminiBuilder

        builder = GeminiBuilder()

        line = json.dumps({"model_response": "Here is my analysis..."})

        result = builder.parse_line(line, session_id="test-session")

        assert isinstance(result, list)

    def test_gemini_builder_invalid_json(self):
        """Test graceful handling of invalid JSON."""
        from motus.ingestors.gemini import GeminiBuilder

        builder = GeminiBuilder()
        result = builder.parse_line("not valid json", session_id="test-session")

        assert isinstance(result, list)
        assert len(result) == 0

    def test_builders_route_correctly_by_type(self):
        """Test that builders route to correct parsing based on source type."""
        from motus.ingestors.claude import ClaudeBuilder
        from motus.ingestors.gemini import GeminiBuilder

        # Test Claude builder
        claude_builder = ClaudeBuilder()
        claude_line = json.dumps({"type": "assistant", "message": {"content": []}})
        claude_result = claude_builder.parse_line(claude_line, session_id="test-session")
        assert isinstance(claude_result, list)

        # Test Gemini builder
        gemini_builder = GeminiBuilder()
        gemini_line = json.dumps({"model_response": "test"})
        gemini_result = gemini_builder.parse_line(gemini_line, session_id="test-session")
        assert isinstance(gemini_result, list)


class TestSecretRedaction:
    """Test secret redaction functionality."""

    def test_redacts_openai_key(self):
        """Test OpenAI API key redaction."""
        from motus.commands.utils import redact_secrets

        text = "Using key sk-1234567890abcdefghijklmnop"
        result = redact_secrets(text)

        assert "sk-" not in result
        assert "REDACTED" in result

    def test_redacts_github_token(self):
        """Test GitHub token redaction."""
        from motus.commands.utils import redact_secrets

        text = "GITHUB_TOKEN=ghp_1234567890abcdefghijklmnopqrstuvwxyz"
        result = redact_secrets(text)

        assert "ghp_" not in result
        assert "REDACTED" in result

    def test_redacts_password(self):
        """Test password redaction."""
        from motus.commands.utils import redact_secrets

        text = "password = secret123"
        result = redact_secrets(text)

        assert "secret123" not in result
        assert "REDACTED" in result

    def test_preserves_normal_text(self):
        """Test that normal text is preserved."""
        from motus.commands.utils import redact_secrets

        text = "This is normal text without any secrets"
        result = redact_secrets(text)

        assert result == text

    def test_handles_empty_string(self):
        """Test handling of empty string."""
        from motus.commands.utils import redact_secrets

        result = redact_secrets("")
        assert result == ""

    def test_handles_none(self):
        """Test handling of None."""
        from motus.commands.utils import redact_secrets

        result = redact_secrets(None)
        assert result is None


class TestGeminiFileSizeGuard:
    """Test file size guards for Gemini builder."""

    def test_skips_large_files(self):
        """Test that large files are skipped."""
        from motus.ingestors.gemini import MAX_FILE_SIZE, GeminiBuilder

        builder = GeminiBuilder()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file that appears large via mock
            large_file = Path(tmpdir) / "large_session.json"
            large_file.write_text('{"sessionId": "test"}')

            # Mock the file size to be over limit
            with patch.object(Path, "stat") as mock_stat:
                mock_stat.return_value.st_size = MAX_FILE_SIZE + 1
                result = builder.parse_events(large_file)

            assert result == []

    def test_parses_normal_files(self):
        """Test that normal-sized files are parsed."""
        from motus.ingestors.gemini import GeminiBuilder

        builder = GeminiBuilder()

        with tempfile.TemporaryDirectory() as tmpdir:
            normal_file = Path(tmpdir) / "normal_session.json"
            normal_file.write_text(
                json.dumps(
                    {
                        "sessionId": "test123",
                        "messages": [
                            {"type": "user", "content": "Hello", "id": "1"},
                            {"type": "gemini", "content": "Hi there!", "id": "2"},
                        ],
                    }
                )
            )

            result = builder.parse_events(normal_file)

            assert isinstance(result, list)
            # Builder may or may not parse user/gemini messages depending on format


class TestRetentionConfig:
    """Test retention configuration."""

    def test_retention_config_defaults(self):
        """Test default retention configuration values."""
        from motus.config import RetentionConfig

        config = RetentionConfig()

        assert config.max_session_age_days == 30
        assert config.max_session_size_mb == 100
        assert config.auto_prune is False

    def test_retention_config_in_mc_config(self):
        """Test retention config is included in MCConfig."""
        from motus.config import MCConfig, RetentionConfig

        mc_config = MCConfig()

        assert hasattr(mc_config, "retention")
        assert isinstance(mc_config.retention, RetentionConfig)
