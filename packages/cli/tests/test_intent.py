"""Tests for intent extraction and management."""

import json
import tempfile
from pathlib import Path


class TestIntent:
    """Test Intent dataclass."""

    def test_creation(self):
        """Test basic creation of Intent."""
        from motus.intent import Intent

        intent = Intent(
            task="Add feature X",
            constraints=["Don't modify tests", "Keep changes minimal"],
            out_of_scope=["Refactoring unrelated code"],
            priority_files=["src/main.py", "src/utils.py"],
        )

        assert intent.task == "Add feature X"
        assert len(intent.constraints) == 2
        assert len(intent.out_of_scope) == 1
        assert len(intent.priority_files) == 2

    def test_to_dict(self):
        """Test Intent to_dict conversion."""
        from motus.intent import Intent

        intent = Intent(
            task="Add feature X", constraints=["Keep minimal"], out_of_scope=[], priority_files=[]
        )

        data = intent.to_dict()
        assert data["task"] == "Add feature X"
        assert "constraints" in data
        assert "out_of_scope" in data
        assert "priority_files" in data

    def test_from_dict(self):
        """Test Intent from_dict conversion."""
        from motus.intent import Intent

        data = {
            "task": "Fix bug",
            "constraints": ["Don't break tests"],
            "out_of_scope": ["Adding features"],
            "priority_files": ["src/main.py"],
        }

        intent = Intent.from_dict(data)
        assert intent.task == "Fix bug"
        assert len(intent.constraints) == 1
        assert len(intent.out_of_scope) == 1
        assert len(intent.priority_files) == 1


class TestExtractTaskFromPrompt:
    """Test _extract_task_from_prompt function."""

    def test_simple_prompt(self):
        """Test extracting task from simple prompt."""
        from motus.intent import _extract_task_from_prompt

        task = _extract_task_from_prompt("add source badges to session display")
        assert task == "Add source badges to session display"

    def test_prompt_with_prefix(self):
        """Test extracting task with common prefix."""
        from motus.intent import _extract_task_from_prompt

        prompts = [
            ("I want to add feature X", "Add feature X"),
            ("Can you fix the bug", "Fix the bug"),
            ("Please update the docs", "Update the docs"),
            ("Help me implement feature Y", "Implement feature Y"),
        ]

        for prompt, expected in prompts:
            task = _extract_task_from_prompt(prompt)
            assert task == expected

    def test_long_prompt_truncation(self):
        """Test that long prompts are truncated."""
        from motus.intent import _extract_task_from_prompt

        long_prompt = "a" * 200
        task = _extract_task_from_prompt(long_prompt)
        assert len(task) <= 150
        assert task.endswith("...")


class TestExtractConstraints:
    """Test _extract_constraints function."""

    def test_extract_dont_constraint(self):
        """Test extracting 'don't' constraints."""
        from motus.intent import _extract_constraints

        prompt = "Add feature X. Don't modify test files. Keep changes minimal."
        constraints = _extract_constraints(prompt)

        assert len(constraints) >= 1
        assert any("Don't modify test files" in c for c in constraints)

    def test_extract_make_sure_constraint(self):
        """Test extracting 'make sure' constraints."""
        from motus.intent import _extract_constraints

        prompt = "Fix bug. Make sure tests pass. Ensure no breaking changes."
        constraints = _extract_constraints(prompt)

        assert len(constraints) >= 2

    def test_no_constraints(self):
        """Test prompt with no constraints."""
        from motus.intent import _extract_constraints

        prompt = "Add feature X"
        constraints = _extract_constraints(prompt)

        assert len(constraints) == 0


class TestInferOutOfScope:
    """Test _infer_out_of_scope function."""

    def test_infer_from_dont_modify(self):
        """Test inferring out-of-scope from 'don't modify'."""
        from motus.intent import _infer_out_of_scope

        constraints = ["Don't modify test files"]
        out_of_scope = _infer_out_of_scope(constraints)

        assert len(out_of_scope) >= 1

    def test_no_out_of_scope(self):
        """Test when no out-of-scope items can be inferred."""
        from motus.intent import _infer_out_of_scope

        constraints = ["Make sure tests pass"]
        out_of_scope = _infer_out_of_scope(constraints)

        # This constraint doesn't imply out-of-scope items
        assert len(out_of_scope) == 0


class TestIdentifyPriorityFiles:
    """Test _identify_priority_files function."""

    def test_modified_files_are_priority(self):
        """Test that modified files become priority files."""
        from datetime import datetime

        from motus.intent import _identify_priority_files
        from motus.schema.events import AgentSource, EventType, ParsedEvent

        # Create mock events with file modifications
        events = [
            ParsedEvent(
                event_id="1",
                session_id="test",
                event_type=EventType.TOOL_USE,
                source=AgentSource.CLAUDE,
                timestamp=datetime.now(),
                tool_name="Edit",
                file_path="src/main.py",
            ),
            ParsedEvent(
                event_id="2",
                session_id="test",
                event_type=EventType.TOOL_USE,
                source=AgentSource.CLAUDE,
                timestamp=datetime.now(),
                tool_name="Write",
                file_path="src/utils.py",
            ),
        ]

        priority = _identify_priority_files(events)
        assert len(priority) == 2
        assert "src/main.py" in priority
        assert "src/utils.py" in priority

    def test_limit_priority_files(self):
        """Test that priority files are limited to 10."""
        from datetime import datetime

        from motus.intent import _identify_priority_files
        from motus.schema.events import AgentSource, EventType, ParsedEvent

        # Create 15 events with file modifications
        events = [
            ParsedEvent(
                event_id=str(i),
                session_id="test",
                event_type=EventType.TOOL_USE,
                source=AgentSource.CLAUDE,
                timestamp=datetime.now(),
                tool_name="Edit",
                file_path=f"src/file{i}.py",
            )
            for i in range(15)
        ]

        priority = _identify_priority_files(events)
        assert len(priority) <= 10


class TestGenerateIntentYaml:
    """Test generate_intent_yaml function."""

    def test_generate_yaml(self):
        """Test generating YAML from Intent."""
        from motus.intent import Intent, generate_intent_yaml

        intent = Intent(
            task="Add feature X",
            constraints=["Keep minimal"],
            out_of_scope=["Refactoring"],
            priority_files=["src/main.py"],
        )

        yaml_str = generate_intent_yaml(intent)

        # Check that YAML contains expected keys
        assert "task:" in yaml_str
        assert "Add feature X" in yaml_str
        assert "constraints:" in yaml_str
        assert "out_of_scope:" in yaml_str
        assert "priority_files:" in yaml_str


class TestSaveLoadIntent:
    """Test save_intent and load_intent functions."""

    def test_save_and_load(self):
        """Test saving and loading intent."""
        from motus.intent import Intent, load_intent, save_intent

        intent = Intent(
            task="Test task",
            constraints=["Constraint 1"],
            out_of_scope=["Scope 1"],
            priority_files=["file1.py"],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            motus_dir = Path(tmpdir) / ".motus"
            success = save_intent(motus_dir, intent)
            assert success

            # Load it back
            loaded = load_intent(motus_dir)
            assert loaded is not None
            assert loaded.task == "Test task"
            assert len(loaded.constraints) == 1
            assert len(loaded.out_of_scope) == 1
            assert len(loaded.priority_files) == 1

    def test_load_nonexistent(self):
        """Test loading intent when file doesn't exist."""
        from motus.intent import load_intent

        with tempfile.TemporaryDirectory() as tmpdir:
            motus_dir = Path(tmpdir) / ".motus"
            loaded = load_intent(motus_dir)
            assert loaded is None

    def test_save_creates_directory(self):
        """Test that save_intent creates .motus directory if needed."""
        from motus.intent import Intent, save_intent

        intent = Intent(task="Test")

        with tempfile.TemporaryDirectory() as tmpdir:
            motus_dir = Path(tmpdir) / ".motus"
            assert not motus_dir.exists()

            success = save_intent(motus_dir, intent)
            assert success
            assert motus_dir.exists()
            assert (motus_dir / "intent.yaml").exists()


class TestParseIntent:
    """Test parse_intent function."""

    def test_parse_intent_from_session(self):
        """Test parsing intent from a session transcript."""
        from motus.intent import parse_intent

        # Create a minimal session transcript
        events = [
            {
                "type": "user",
                "timestamp": "2025-12-02T12:00:00Z",
                "message": {
                    "content": [
                        {
                            "type": "text",
                            "text": "I want to add source badges to session display. Don't modify test files. Keep changes minimal.",
                        }
                    ]
                },
            },
            {
                "type": "assistant",
                "timestamp": "2025-12-02T12:01:00Z",
                "message": {
                    "model": "claude-sonnet-4",
                    "usage": {"input_tokens": 100, "output_tokens": 50},
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Edit",
                            "input": {"file_path": "src/motus/cli.py"},
                        }
                    ],
                },
            },
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create path that looks like a Claude session
            claude_dir = Path(tmpdir) / ".claude" / "projects" / "test_project"
            claude_dir.mkdir(parents=True, exist_ok=True)
            temp_path = claude_dir / "session.jsonl"

            with open(temp_path, "w") as f:
                for event in events:
                    f.write(json.dumps(event) + "\n")

            intent = parse_intent(temp_path)

            assert intent.task
            assert "badge" in intent.task.lower() or "source" in intent.task.lower()
            # Should have constraints from the prompt
            assert len(intent.constraints) >= 1
            # Should have priority files (from modified files)
            assert len(intent.priority_files) >= 1
            assert "src/motus/cli.py" in intent.priority_files

    def test_parse_intent_no_user_messages(self):
        """Test parsing intent when there are no user messages."""
        from motus.intent import parse_intent

        events = [
            {
                "type": "assistant",
                "message": {"model": "claude", "usage": {}, "content": []},
            }
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for event in events:
                f.write(json.dumps(event) + "\n")
            temp_path = Path(f.name)

        try:
            intent = parse_intent(temp_path)
            assert intent.task == "No task specified"
        finally:
            temp_path.unlink()

    def test_identify_priority_files_codex_source(self):
        """Test _identify_priority_files with Codex ParsedEvent objects."""
        from datetime import datetime

        from motus.intent import _identify_priority_files
        from motus.schema.events import AgentSource, EventType, ParsedEvent

        # Create TOOL_USE events from Codex
        events = [
            ParsedEvent(
                event_id="1",
                session_id="test",
                event_type=EventType.TOOL_USE,
                source=AgentSource.CODEX,
                timestamp=datetime.now(),
                tool_name="Edit",
                file_path="src/auth.py",
            ),
            ParsedEvent(
                event_id="2",
                session_id="test",
                event_type=EventType.TOOL_USE,
                source=AgentSource.CODEX,
                timestamp=datetime.now(),
                tool_name="Write",
                file_path="tests/test_auth.py",
            ),
        ]

        priority = _identify_priority_files(events)
        assert len(priority) == 2
        assert "src/auth.py" in priority
        assert "tests/test_auth.py" in priority

    def test_identify_priority_files_gemini_source(self):
        """Test _identify_priority_files with Gemini ParsedEvent objects."""
        from datetime import datetime

        from motus.intent import _identify_priority_files
        from motus.schema.events import AgentSource, EventType, ParsedEvent

        # Create TOOL_USE events from Gemini
        events = [
            ParsedEvent(
                event_id="1",
                session_id="test",
                event_type=EventType.TOOL_USE,
                source=AgentSource.GEMINI,
                timestamp=datetime.now(),
                tool_name="Write",
                file_path="src/pipeline.py",
            ),
            ParsedEvent(
                event_id="2",
                session_id="test",
                event_type=EventType.TOOL_USE,
                source=AgentSource.GEMINI,
                timestamp=datetime.now(),
                tool_name="Edit",
                file_path="src/logger.py",
            ),
        ]

        priority = _identify_priority_files(events)
        assert len(priority) == 2
        assert "src/pipeline.py" in priority
        assert "src/logger.py" in priority
