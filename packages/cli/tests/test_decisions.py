"""Tests for Decision Ledger module."""

from unittest.mock import MagicMock, patch

from src.motus.decisions import (
    Decision,
    DecisionLedger,
    extract_decision_from_text,
    extract_file_references,
    format_decision_ledger,
    format_decisions_for_export,
    get_decisions,
)


class TestDecision:
    """Tests for Decision dataclass."""

    def test_creation(self):
        """Test Decision creation."""
        decision = Decision(
            timestamp="2025-01-01T00:00:00",
            decision="I decided to use pytest over unittest",
            reasoning="pytest is more concise",
            files_affected=["tests/test_main.py"],
            reversible=True,
            context="testing discussion",
        )
        assert decision.decision == "I decided to use pytest over unittest"
        assert decision.reasoning == "pytest is more concise"
        assert "tests/test_main.py" in decision.files_affected

    def test_to_dict(self):
        """Test serialization to dict."""
        decision = Decision(
            timestamp="2025-01-01T00:00:00",
            decision="Chose to use async instead of sync",
            reasoning="better performance",
            files_affected=["src/main.py"],
            reversible=True,
            context="performance discussion",
        )
        data = decision.to_dict()
        assert data["decision"] == "Chose to use async instead of sync"
        assert data["reasoning"] == "better performance"
        assert data["files_affected"] == ["src/main.py"]
        assert data["reversible"] is True


class TestDecisionLedger:
    """Tests for DecisionLedger dataclass."""

    def test_empty_ledger(self):
        """Test empty decision ledger."""
        ledger = DecisionLedger(session_id="test123")
        assert ledger.session_id == "test123"
        assert ledger.decisions == []
        assert ledger.timestamp is None

    def test_to_dict(self):
        """Test serialization to dict."""
        ledger = DecisionLedger(
            session_id="test123",
            decisions=[
                Decision(
                    timestamp="2025-01-01T00:00:00",
                    decision="Test decision",
                    reasoning="",
                    files_affected=[],
                )
            ],
            timestamp="2025-01-01T00:00:00",
        )
        data = ledger.to_dict()
        assert data["session_id"] == "test123"
        assert len(data["decisions"]) == 1
        assert data["decisions"][0]["decision"] == "Test decision"


class TestExtractDecisionFromText:
    """Tests for extract_decision_from_text function."""

    def test_decided_to_pattern(self):
        """Test 'decided to' pattern detection."""
        text = "I decided to use a different approach for the database."
        decision = extract_decision_from_text(text)
        assert decision is not None
        assert "decided to use a different approach" in decision.decision

    def test_chose_to_pattern(self):
        """Test 'chose to' pattern detection."""
        text = "We chose to implement the feature with React instead of Vue."
        decision = extract_decision_from_text(text)
        assert decision is not None
        assert "chose to implement" in decision.decision

    def test_instead_of_pattern(self):
        """Test 'instead of' pattern detection."""
        text = "Using async/await instead of callbacks for better readability."
        decision = extract_decision_from_text(text)
        assert decision is not None
        assert "instead of" in decision.decision.lower()

    def test_because_reasoning(self):
        """Test 'because' reasoning extraction."""
        text = "I decided to use TypeScript because it provides better type safety."
        decision = extract_decision_from_text(text)
        assert decision is not None
        # Reasoning should be extracted
        assert "type safety" in decision.reasoning or "TypeScript" in decision.decision

    def test_no_decision_in_text(self):
        """Test text without decision patterns."""
        text = "This is just a regular comment without any decisions."
        decision = extract_decision_from_text(text)
        assert decision is None

    def test_short_text_ignored(self):
        """Test that very short matches are ignored."""
        text = "I decided."
        decision = extract_decision_from_text(text)
        assert decision is None


class TestExtractFileReferences:
    """Tests for extract_file_references function."""

    def test_python_files(self):
        """Test extracting Python file references."""
        text = "Modified src/main.py and tests/test_main.py for the fix."
        files = extract_file_references(text)
        assert "src/main.py" in files
        assert "tests/test_main.py" in files

    def test_javascript_files(self):
        """Test extracting JavaScript/TypeScript file references."""
        text = "Updated components/Button.tsx and utils/helpers.js."
        files = extract_file_references(text)
        assert any("Button.tsx" in f for f in files)
        assert any("helpers.js" in f for f in files)

    def test_config_files(self):
        """Test extracting config file references."""
        text = "Changed config/settings.yaml and package.json."
        files = extract_file_references(text)
        assert any("settings.yaml" in f for f in files)
        assert any("package.js" in f for f in files)  # Matches json as js extension

    def test_no_files(self):
        """Test text without file references."""
        text = "This is a general discussion without file mentions."
        files = extract_file_references(text)
        assert files == []


class TestGetDecisions:
    """Tests for get_decisions function."""

    def test_no_sessions(self):
        """Test with no sessions available."""
        with patch("src.motus.decisions.get_orchestrator") as mock_get_orch:
            mock_orch = MagicMock()
            mock_orch.discover_all.return_value = []
            mock_get_orch.return_value = mock_orch
            ledger = get_decisions()
            assert ledger.session_id == "none"
            assert ledger.decisions == []

    def test_with_session_path(self, tmp_path):
        """Test with direct session path."""
        # Create a mock session file
        session_file = tmp_path / "test_session.jsonl"
        session_file.write_text('{"type": "test"}\n')

        with patch("src.motus.decisions.get_orchestrator") as mock_get_orch:
            mock_orch = MagicMock()
            mock_session = MagicMock()
            mock_session.file_path = session_file
            mock_orch.discover_all.return_value = [mock_session]
            mock_orch.get_events_validated.return_value = []
            mock_get_orch.return_value = mock_orch

            ledger = get_decisions(session_path=session_file)
            assert ledger.session_id == "test_session"
            assert ledger.decisions == []

    def test_extract_from_thinking_events_claude(self, tmp_path):
        """Test extracting decisions from THINKING events with Claude."""
        from datetime import datetime

        from motus.schema.events import AgentSource, EventType, ParsedEvent

        session_file = tmp_path / "claude_session.jsonl"
        session_file.write_text('{"type": "test"}\n')

        # Create THINKING events with decision text
        events = [
            ParsedEvent(
                event_id="1",
                session_id="test",
                event_type=EventType.THINKING,
                source=AgentSource.CLAUDE,
                timestamp=datetime.now(),
                content="I decided to use async/await instead of callbacks because it's more readable and easier to maintain.",
            ),
            ParsedEvent(
                event_id="2",
                session_id="test",
                event_type=EventType.THINKING,
                source=AgentSource.CLAUDE,
                timestamp=datetime.now(),
                content="We chose to implement caching at the database layer rather than the application layer.",
            ),
        ]

        with patch("src.motus.decisions.get_orchestrator") as mock_get_orch:
            mock_orch = MagicMock()
            mock_session = MagicMock()
            mock_session.file_path = session_file

            mock_orch.discover_all.return_value = [mock_session]
            mock_orch.get_events_validated.return_value = events
            mock_get_orch.return_value = mock_orch

            ledger = get_decisions(session_path=session_file)

            # Should extract both decisions
            assert len(ledger.decisions) == 2
            assert any("async/await" in d.decision for d in ledger.decisions)
            assert any("caching" in d.decision for d in ledger.decisions)

    def test_extract_from_thinking_events_codex(self, tmp_path):
        """Test extracting decisions from THINKING events with Codex."""
        from datetime import datetime

        from motus.schema.events import AgentSource, EventType, ParsedEvent

        session_file = tmp_path / "codex_session.jsonl"
        session_file.write_text('{"type": "test"}\n')

        # Create THINKING event from Codex
        events = [
            ParsedEvent(
                event_id="1",
                session_id="test",
                event_type=EventType.THINKING,
                source=AgentSource.CODEX,
                timestamp=datetime.now(),
                content="I chose to use TypeScript over JavaScript because it provides better type safety and catches errors at compile time.",
            ),
        ]

        with patch("src.motus.decisions.get_orchestrator") as mock_get_orch:
            mock_orch = MagicMock()
            mock_session = MagicMock()
            mock_session.file_path = session_file

            mock_orch.discover_all.return_value = [mock_session]
            mock_orch.get_events_validated.return_value = events
            mock_get_orch.return_value = mock_orch

            ledger = get_decisions(session_path=session_file)

            # Should extract decision from Codex
            assert len(ledger.decisions) == 1
            assert "TypeScript" in ledger.decisions[0].decision

    def test_extract_from_thinking_events_gemini(self, tmp_path):
        """Test extracting decisions from THINKING events with Gemini."""
        from datetime import datetime

        from motus.schema.events import AgentSource, EventType, ParsedEvent

        session_file = tmp_path / "gemini_session.jsonl"
        session_file.write_text('{"type": "test"}\n')

        # Create THINKING event from Gemini
        events = [
            ParsedEvent(
                event_id="1",
                session_id="test",
                event_type=EventType.THINKING,
                source=AgentSource.GEMINI,
                timestamp=datetime.now(),
                content="We decided to implement the feature using a microservices architecture instead of a monolith because it provides better scalability.",
            ),
        ]

        with patch("src.motus.decisions.get_orchestrator") as mock_get_orch:
            mock_orch = MagicMock()
            mock_session = MagicMock()
            mock_session.file_path = session_file

            mock_orch.discover_all.return_value = [mock_session]
            mock_orch.get_events_validated.return_value = events
            mock_get_orch.return_value = mock_orch

            ledger = get_decisions(session_path=session_file)

            # Should extract decision from Gemini
            assert len(ledger.decisions) == 1
            assert "microservices" in ledger.decisions[0].decision


class TestFormatDecisionLedger:
    """Tests for format_decision_ledger function."""

    def test_no_decisions(self):
        """Test formatting when no decisions."""
        ledger = DecisionLedger(
            session_id="test12345678",
            decisions=[],
        )
        formatted = format_decision_ledger(ledger)
        assert "No decisions found" in formatted
        assert "test1234" in formatted  # Short ID

    def test_with_decisions(self):
        """Test formatting with decisions."""
        ledger = DecisionLedger(
            session_id="test12345678",
            decisions=[
                Decision(
                    timestamp="2025-01-01T00:00:00",
                    decision="Decided to use pytest",
                    reasoning="better assertions",
                    files_affected=["tests/test_main.py"],
                ),
                Decision(
                    timestamp="2025-01-01T00:01:00",
                    decision="Chose async over sync",
                    reasoning="performance",
                    files_affected=[],
                ),
            ],
        )
        formatted = format_decision_ledger(ledger)
        assert "Decided to use pytest" in formatted
        assert "Chose async over sync" in formatted
        assert "better assertions" in formatted
        assert "Total: 2 decision(s)" in formatted

    def test_files_displayed(self):
        """Test that files are displayed in report."""
        ledger = DecisionLedger(
            session_id="test12345678",
            decisions=[
                Decision(
                    timestamp="2025-01-01T00:00:00",
                    decision="Updated the config",
                    reasoning="",
                    files_affected=["config.py", "settings.yaml"],
                ),
            ],
        )
        formatted = format_decision_ledger(ledger)
        assert "config.py" in formatted
        assert "settings.yaml" in formatted


class TestFormatDecisionsForExport:
    """Tests for format_decisions_for_export function."""

    def test_no_decisions(self):
        """Test export formatting when no decisions."""
        ledger = DecisionLedger(
            session_id="test123",
            decisions=[],
        )
        formatted = format_decisions_for_export(ledger)
        assert "## Decisions Made" in formatted
        assert "No significant decisions recorded" in formatted

    def test_with_decisions_markdown(self):
        """Test markdown export format."""
        ledger = DecisionLedger(
            session_id="test123",
            decisions=[
                Decision(
                    timestamp="2025-01-01T00:00:00",
                    decision="Implemented caching",
                    reasoning="improve performance",
                    files_affected=["cache.py"],
                ),
            ],
        )
        formatted = format_decisions_for_export(ledger)
        assert "## Decisions Made" in formatted
        assert "**Implemented caching**" in formatted
        assert "Reasoning: improve performance" in formatted
        assert "`cache.py`" in formatted
