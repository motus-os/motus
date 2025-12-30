"""Tests for formatters module (Rich formatting utilities)."""

from datetime import datetime
from pathlib import Path

from motus.cli.formatters import (
    create_header,
    create_summary_table,
    format_error,
    format_task,
    format_thinking,
    format_tool,
    get_risk_style,
)
from motus.cli.output import (
    ErrorEvent,
    SessionInfo,
    SessionStats,
    TaskEvent,
    ThinkingEvent,
    ToolEvent,
)
from motus.schema.events import RiskLevel


class TestGetRiskStyle:
    """Test get_risk_style function."""

    def test_safe_risk_level(self):
        """Test safe risk level styling."""
        color, icon = get_risk_style("safe")
        assert color == "green"
        assert icon == "✓"

    def test_medium_risk_level(self):
        """Test medium risk level styling."""
        color, icon = get_risk_style("medium")
        assert color == "yellow"
        assert icon == "◐"

    def test_high_risk_level(self):
        """Test high risk level styling."""
        color, icon = get_risk_style("high")
        assert color == "red"
        assert icon == "●"

    def test_critical_risk_level(self):
        """Test critical risk level styling."""
        color, icon = get_risk_style("critical")
        assert color == "bold red"
        assert icon == "⚠"

    def test_unknown_risk_level(self):
        """Test unknown risk level returns default."""
        color, icon = get_risk_style("unknown")
        assert color == "white"
        assert icon == "?"

    def test_risk_level_enum(self):
        """Test with RiskLevel enum."""
        color, icon = get_risk_style(RiskLevel.SAFE)
        assert color == "green"
        assert icon == "✓"

        color, icon = get_risk_style(RiskLevel.HIGH)
        assert color == "red"
        assert icon == "●"


class TestFormatThinking:
    """Test format_thinking function."""

    def test_format_thinking_basic(self):
        """Test basic thinking event formatting."""
        event = ThinkingEvent(
            content="I need to analyze the code structure.",
            timestamp=datetime.now(),
        )
        stats = SessionStats()

        panel = format_thinking(event, stats)

        assert panel is not None
        assert stats.thinking_count == 1

    def test_format_thinking_long_content(self):
        """Test thinking event with long content gets truncated."""
        long_content = "A" * 1200
        event = ThinkingEvent(
            content=long_content,
            timestamp=datetime.now(),
        )
        stats = SessionStats()

        panel = format_thinking(event, stats)

        assert panel is not None
        assert stats.thinking_count == 1
        # Content should be truncated
        # Panel internals will contain truncated text

    def test_format_thinking_short_content(self):
        """Test thinking event with medium content (between 500-1000)."""
        medium_content = "B" * 600
        event = ThinkingEvent(
            content=medium_content,
            timestamp=datetime.now(),
        )
        stats = SessionStats()

        panel = format_thinking(event, stats)

        assert panel is not None
        assert stats.thinking_count == 1

    def test_format_thinking_increments_counter(self):
        """Test that multiple thinking events increment counter."""
        event = ThinkingEvent(
            content="First thought",
            timestamp=datetime.now(),
        )
        stats = SessionStats()

        format_thinking(event, stats)
        assert stats.thinking_count == 1

        format_thinking(event, stats)
        assert stats.thinking_count == 2


class TestFormatError:
    """Test format_error function."""

    def test_format_error_basic(self):
        """Test basic error event formatting."""
        event = ErrorEvent(
            message="File not found",
            timestamp=datetime.now(),
        )
        stats = SessionStats()

        panel = format_error(event, stats)

        assert panel is not None
        assert stats.error_count == 1

    def test_format_error_with_type_and_tool(self):
        """Test error event with type and tool information."""
        event = ErrorEvent(
            message="Permission denied",
            timestamp=datetime.now(),
            error_type="tool_error",
            tool_name="Write",
        )
        stats = SessionStats()

        panel = format_error(event, stats)

        assert panel is not None
        assert stats.error_count == 1

    def test_format_error_non_recoverable(self):
        """Test non-recoverable error formatting."""
        event = ErrorEvent(
            message="Critical failure",
            timestamp=datetime.now(),
            recoverable=False,
        )
        stats = SessionStats()

        panel = format_error(event, stats)

        assert panel is not None
        assert stats.error_count == 1

    def test_format_error_increments_counter(self):
        """Test that multiple errors increment counter."""
        event = ErrorEvent(
            message="Error",
            timestamp=datetime.now(),
        )
        stats = SessionStats()

        format_error(event, stats)
        assert stats.error_count == 1

        format_error(event, stats)
        assert stats.error_count == 2


class TestFormatTask:
    """Test format_task function."""

    def test_format_task_basic(self):
        """Test basic task event formatting."""
        event = TaskEvent(
            description="Search the codebase",
            prompt="Find all Python files",
            subagent_type="Explore",
            model="haiku",
            timestamp=datetime.now(),
        )
        stats = SessionStats()

        panel = format_task(event, stats)

        assert panel is not None
        assert stats.agent_count == 1

    def test_format_task_without_model(self):
        """Test task event without model specified."""
        event = TaskEvent(
            description="Analyze files",
            prompt="Check for patterns",
            subagent_type="Research",
            model=None,
            timestamp=datetime.now(),
        )
        stats = SessionStats()

        panel = format_task(event, stats)

        assert panel is not None
        assert stats.agent_count == 1

    def test_format_task_with_long_prompt(self):
        """Test task event with long prompt."""
        event = TaskEvent(
            description="Complex task",
            prompt="A" * 1000,
            subagent_type="Analyze",
            model="sonnet",
            timestamp=datetime.now(),
        )
        stats = SessionStats()

        panel = format_task(event, stats)

        assert panel is not None
        assert stats.agent_count == 1

    def test_format_task_increments_counter(self):
        """Test that multiple tasks increment counter."""
        event = TaskEvent(
            description="Task",
            prompt="Do something",
            subagent_type="Execute",
            model="opus",
            timestamp=datetime.now(),
        )
        stats = SessionStats()

        format_task(event, stats)
        assert stats.agent_count == 1

        format_task(event, stats)
        assert stats.agent_count == 2


class TestFormatTool:
    """Test format_tool function."""

    def test_format_tool_read(self):
        """Test Read tool formatting."""
        event = ToolEvent(
            name="Read",
            input={"file_path": "/test/file.py"},
            timestamp=datetime.now(),
            risk_level="safe",
        )
        stats = SessionStats()

        panel = format_tool(event, stats)

        assert panel is not None
        assert stats.tool_count == 1

    def test_format_tool_write(self):
        """Test Write tool formatting and file tracking."""
        event = ToolEvent(
            name="Write",
            input={"file_path": "/output/new.py"},
            timestamp=datetime.now(),
            risk_level="medium",
        )
        stats = SessionStats()

        panel = format_tool(event, stats)

        assert panel is not None
        assert stats.tool_count == 1
        assert "/output/new.py" in stats.files_modified

    def test_format_tool_edit(self):
        """Test Edit tool formatting and file tracking."""
        event = ToolEvent(
            name="Edit",
            input={"file_path": "/existing/file.py", "old_string": "old code here"},
            timestamp=datetime.now(),
            risk_level="medium",
        )
        stats = SessionStats()

        panel = format_tool(event, stats)

        assert panel is not None
        assert stats.tool_count == 1
        assert "/existing/file.py" in stats.files_modified

    def test_format_tool_bash(self):
        """Test Bash tool formatting."""
        event = ToolEvent(
            name="Bash",
            input={"command": "ls -la", "description": "List files"},
            timestamp=datetime.now(),
            risk_level="high",
        )
        stats = SessionStats()

        panel = format_tool(event, stats)

        assert panel is not None
        assert stats.tool_count == 1
        assert stats.high_risk_ops == 1

    def test_format_tool_bash_long_command(self):
        """Test Bash tool with long command."""
        event = ToolEvent(
            name="Bash",
            input={"command": "A" * 200},
            timestamp=datetime.now(),
            risk_level="high",
        )
        stats = SessionStats()

        panel = format_tool(event, stats)

        assert panel is not None
        assert stats.tool_count == 1

    def test_format_tool_glob(self):
        """Test Glob tool formatting."""
        event = ToolEvent(
            name="Glob",
            input={"pattern": "**/*.py", "path": "/src"},
            timestamp=datetime.now(),
            risk_level="safe",
        )
        stats = SessionStats()

        panel = format_tool(event, stats)

        assert panel is not None
        assert stats.tool_count == 1

    def test_format_tool_grep(self):
        """Test Grep tool formatting."""
        event = ToolEvent(
            name="Grep",
            input={"pattern": "def.*test", "path": "/tests"},
            timestamp=datetime.now(),
            risk_level="safe",
        )
        stats = SessionStats()

        panel = format_tool(event, stats)

        assert panel is not None
        assert stats.tool_count == 1

    def test_format_tool_webfetch(self):
        """Test WebFetch tool formatting."""
        event = ToolEvent(
            name="WebFetch",
            input={"url": "https://example.com", "prompt": "Extract main content"},
            timestamp=datetime.now(),
            risk_level="safe",
        )
        stats = SessionStats()

        panel = format_tool(event, stats)

        assert panel is not None
        assert stats.tool_count == 1

    def test_format_tool_websearch(self):
        """Test WebSearch tool formatting."""
        event = ToolEvent(
            name="WebSearch",
            input={"query": "python best practices"},
            timestamp=datetime.now(),
            risk_level="safe",
        )
        stats = SessionStats()

        panel = format_tool(event, stats)

        assert panel is not None
        assert stats.tool_count == 1

    def test_format_tool_todowrite(self):
        """Test TodoWrite tool formatting."""
        event = ToolEvent(
            name="TodoWrite",
            input={
                "todos": [
                    {"content": "Task 1", "status": "pending"},
                    {"content": "Task 2", "status": "in_progress"},
                    {"content": "Task 3", "status": "pending"},
                ]
            },
            timestamp=datetime.now(),
            risk_level="safe",
        )
        stats = SessionStats()

        panel = format_tool(event, stats)

        assert panel is not None
        assert stats.tool_count == 1

    def test_format_tool_todowrite_many_todos(self):
        """Test TodoWrite with many todos (should show only first 3)."""
        todos = [{"content": f"Task {i}", "status": "pending"} for i in range(10)]
        event = ToolEvent(
            name="TodoWrite",
            input={"todos": todos},
            timestamp=datetime.now(),
            risk_level="safe",
        )
        stats = SessionStats()

        panel = format_tool(event, stats)

        assert panel is not None
        assert stats.tool_count == 1

    def test_format_tool_unknown(self):
        """Test unknown tool formatting."""
        event = ToolEvent(
            name="CustomTool",
            input={"param": "value"},
            timestamp=datetime.now(),
            risk_level="safe",
        )
        stats = SessionStats()

        panel = format_tool(event, stats)

        assert panel is not None
        assert stats.tool_count == 1

    def test_format_tool_high_risk_tracking(self):
        """Test that high-risk operations are tracked."""
        event = ToolEvent(
            name="Bash",
            input={"command": "rm file.txt"},
            timestamp=datetime.now(),
            risk_level="high",
        )
        stats = SessionStats()

        panel = format_tool(event, stats)

        assert panel is not None
        assert stats.high_risk_ops == 1

    def test_format_tool_critical_risk_tracking(self):
        """Test that critical-risk operations are tracked."""
        event = ToolEvent(
            name="Edit",
            input={"file_path": "/etc/passwd"},
            timestamp=datetime.now(),
            risk_level="critical",
        )
        stats = SessionStats()

        panel = format_tool(event, stats)

        assert panel is not None
        assert stats.high_risk_ops == 1

    def test_format_tool_risk_level_enum(self):
        """Test formatting with RiskLevel enum."""
        event = ToolEvent(
            name="Bash",
            input={"command": "test"},
            timestamp=datetime.now(),
            risk_level=RiskLevel.HIGH,
        )
        stats = SessionStats()

        panel = format_tool(event, stats)

        assert panel is not None
        assert stats.tool_count == 1

    def test_format_tool_increments_counter(self):
        """Test that multiple tool calls increment counter."""
        event = ToolEvent(
            name="Read",
            input={"file_path": "/test.py"},
            timestamp=datetime.now(),
        )
        stats = SessionStats()

        format_tool(event, stats)
        assert stats.tool_count == 1

        format_tool(event, stats)
        assert stats.tool_count == 2


class TestCreateHeader:
    """Test create_header function."""

    def test_create_header_basic(self):
        """Test basic header creation."""
        session = SessionInfo(
            session_id="test-session-123456",
            file_path=Path("/tmp/test.jsonl"),
            last_modified=datetime.now(),
            size=1024,
            project_path="/project",
        )

        panel = create_header(session)

        assert panel is not None

    def test_create_header_long_session_id(self):
        """Test header with long session ID (should truncate)."""
        session = SessionInfo(
            session_id="a" * 50,
            file_path=Path("/tmp/test.jsonl"),
            last_modified=datetime.now(),
            size=1024,
            project_path="/project",
        )

        panel = create_header(session)

        assert panel is not None


class TestCreateSummaryTable:
    """Test create_summary_table function."""

    def test_create_summary_table_basic(self):
        """Test basic summary table creation."""
        stats = SessionStats(
            thinking_count=5,
            tool_count=10,
            agent_count=2,
            files_modified={"file1.py", "file2.py"},
            high_risk_ops=0,
        )

        table = create_summary_table(stats)

        assert table is not None

    def test_create_summary_table_with_high_risk_ops(self):
        """Test summary table with high-risk operations."""
        stats = SessionStats(
            thinking_count=3,
            tool_count=15,
            agent_count=1,
            files_modified={"file1.py"},
            high_risk_ops=4,
        )

        table = create_summary_table(stats)

        assert table is not None

    def test_create_summary_table_zero_stats(self):
        """Test summary table with all zeros."""
        stats = SessionStats()

        table = create_summary_table(stats)

        assert table is not None

    def test_create_summary_table_many_files(self):
        """Test summary table with many modified files."""
        stats = SessionStats(
            thinking_count=10,
            tool_count=50,
            agent_count=5,
            files_modified={f"file{i}.py" for i in range(20)},
            high_risk_ops=2,
        )

        table = create_summary_table(stats)

        assert table is not None
