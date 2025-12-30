"""Tests for the MC SDK Tracer."""

import json
import tempfile
from pathlib import Path

import pytest

from motus import Tracer, get_tracer


class TestTracer:
    """Test the Tracer class."""

    def test_tracer_initialization(self):
        """Test basic tracer initialization."""
        tracer = Tracer("test-agent")
        assert tracer.name == "test-agent"
        assert tracer.session_id is not None

    def test_tracer_with_custom_session_id(self):
        """Test tracer with custom session ID."""
        tracer = Tracer("test-agent", session_id="custom-123")
        assert tracer.session_id == "custom-123"

    def test_thinking_event(self):
        """Test logging thinking events."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            tracer = Tracer("test-think")
            # Override the trace file location
            tracer.traces_dir = tmppath
            tracer.trace_file = tmppath / f"{tracer.session_id}.jsonl"

            tracer.thinking("Analyzing the problem...")

            # Verify event was logged
            assert tracer.trace_file.exists()

            with open(tracer.trace_file) as f:
                lines = f.readlines()
                # First line is session start, second is thinking
                assert len(lines) >= 1
                # Find the thinking event
                for line in lines:
                    event = json.loads(line)
                    if event.get("type") == "thinking":
                        assert "Analyzing" in event["content"]
                        break
                else:
                    # If loop completes without break, fail
                    pytest.fail("No thinking event found")

    def test_tool_event(self):
        """Test logging tool events."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            tracer = Tracer("test-tool")
            tracer.traces_dir = tmppath
            tracer.trace_file = tmppath / f"{tracer.session_id}.jsonl"

            tracer.tool("WebSearch", {"query": "python tips"})

            with open(tracer.trace_file) as f:
                lines = f.readlines()
                for line in lines:
                    event = json.loads(line)
                    if event.get("type") == "tool":
                        assert event["name"] == "WebSearch"
                        assert event["input"]["query"] == "python tips"
                        break
                else:
                    pytest.fail("No tool event found")

    def test_decision_event(self):
        """Test logging decision events."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            tracer = Tracer("test-decision")
            tracer.traces_dir = tmppath
            tracer.trace_file = tmppath / f"{tracer.session_id}.jsonl"

            tracer.decision("Using async", reasoning="Batch is large")

            with open(tracer.trace_file) as f:
                lines = f.readlines()
                for line in lines:
                    event = json.loads(line)
                    if event.get("type") == "decision":
                        assert event["decision"] == "Using async"
                        assert event["reasoning"] == "Batch is large"
                        break
                else:
                    pytest.fail("No decision event found")

    def test_track_decorator(self):
        """Test the @tracer.track decorator."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            tracer = Tracer("test-track")
            tracer.traces_dir = tmppath
            tracer.trace_file = tmppath / f"{tracer.session_id}.jsonl"

            @tracer.track
            def add_numbers(a, b):
                return a + b

            result = add_numbers(2, 3)
            assert result == 5

            # Verify function was tracked
            with open(tracer.trace_file) as f:
                content = f.read()
                assert "add_numbers" in content


class TestGetTracer:
    """Test the get_tracer factory function."""

    def test_get_tracer_creates_new(self):
        """Test get_tracer creates a new tracer."""
        tracer = get_tracer("new-agent-test")
        assert tracer.name == "new-agent-test"

    def test_get_tracer_returns_same_instance(self):
        """Test get_tracer returns same instance for same name."""
        tracer1 = get_tracer("singleton-agent-test")
        tracer2 = get_tracer("singleton-agent-test")
        assert tracer1 is tracer2
