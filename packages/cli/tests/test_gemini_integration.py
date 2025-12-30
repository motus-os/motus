"""Tests for Gemini integration components."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from motus.llm.gemini_client import GeminiClient
from motus.gemini_hooks import generate_context_injection
from motus.integrations.gemini_bridge import GeminiBridge
from motus.orchestrator.teleport import extract_doc_summary

@pytest.fixture
def mock_genai():
    with patch("motus.llm.gemini_client.genai") as mock:
        yield mock

def test_client_init_no_key(mock_genai):
    """Test client warning when no API key is present."""
    with patch.dict(os.environ, {}, clear=True):
        client = GeminiClient()
        assert client.client is not None  # Should still init, just warn

def test_client_generate_content(mock_genai):
    """Test content generation wrapper."""
    with patch.dict(os.environ, {"GEMINI_API_KEY": "fake-key"}):
        with patch("motus.llm.gemini_client.types") as mock_types:
            client = GeminiClient()
            mock_response = MagicMock()
            mock_response.text = "Summarized text"
            client.client.models.generate_content.return_value = mock_response
    
            result = client.generate_content("test prompt")
            assert result == "Summarized text"
            client.client.models.generate_content.assert_called_once()

# ... (keep existing tests) ...

def test_bridge_logging(tmp_path):
    """Test that the bridge correctly initializes a tracer and logs events."""
    # We patch tracer.MC_STATE_DIR because Tracer imports it at top-level
    with patch("motus.tracer.MC_STATE_DIR", tmp_path):
        bridge = GeminiBridge(session_id="test-session")
        bridge.log_thinking("Checking code")
        bridge.log_tool("ls", {"args": []})
        
        # Verify file creation
        traces_dir = tmp_path / "traces"
        trace_file = traces_dir / "test-session.jsonl"
        assert trace_file.exists()
        
        # Verify content
        lines = trace_file.read_text().splitlines()
        assert len(lines) >= 3 # Start, Thinking, Tool
        
        events = [json.loads(line) for line in lines]
        assert any(e["type"] == "thinking" and e["content"] == "Checking code" for e in events)
        assert any(e["type"] == "tool" and e["name"] == "ls" for e in events)
