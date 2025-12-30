"""Tests for event dataclasses."""

from datetime import datetime

from motus.events import DecisionEvent, ThinkingEvent, ToolEvent


class TestThinkingEvent:
    """Test ThinkingEvent dataclass."""

    def test_creation(self):
        """Test creating a thinking event."""
        event = ThinkingEvent(content="Analyzing the problem...", timestamp=datetime.now())
        assert event.content == "Analyzing the problem..."
        assert event.timestamp is not None

    def test_to_dict(self):
        """Test converting to dictionary."""
        event = ThinkingEvent(content="Test content", timestamp=datetime.now())
        d = event.to_dict()
        assert d["type"] == "thinking"
        assert d["content"] == "Test content"
        assert "timestamp" in d


class TestToolEvent:
    """Test ToolEvent dataclass."""

    def test_creation(self):
        """Test creating a tool event."""
        event = ToolEvent(name="Read", input={"file_path": "/test.py"}, timestamp=datetime.now())
        assert event.name == "Read"
        assert event.input["file_path"] == "/test.py"

    def test_to_dict(self):
        """Test converting to dictionary."""
        event = ToolEvent(name="Bash", input={"command": "ls"}, timestamp=datetime.now())
        d = event.to_dict()
        assert d["type"] == "tool"
        assert d["name"] == "Bash"
        assert d["input"]["command"] == "ls"


class TestDecisionEvent:
    """Test DecisionEvent dataclass."""

    def test_creation(self):
        """Test creating a decision event."""
        event = DecisionEvent(
            decision="Use async", reasoning="Better performance for I/O", timestamp=datetime.now()
        )
        assert event.decision == "Use async"
        assert event.reasoning == "Better performance for I/O"

    def test_to_dict(self):
        """Test converting to dictionary."""
        event = DecisionEvent(
            decision="Choose SQLite", reasoning="Simple and embedded", timestamp=datetime.now()
        )
        d = event.to_dict()
        assert d["type"] == "decision"
        assert d["decision"] == "Choose SQLite"
        assert d["reasoning"] == "Simple and embedded"

    def test_optional_reasoning(self):
        """Test decision without reasoning."""
        event = DecisionEvent(decision="Quick fix", timestamp=datetime.now())
        assert event.decision == "Quick fix"
        assert event.reasoning is None
