"""Transcript fixtures for testing."""

import json
import tempfile
from pathlib import Path
from typing import Optional

# Sample events for transcript files
SAMPLE_THINKING_EVENT = {
    "type": "assistant",
    "message": {
        "content": [
            {
                "type": "thinking",
                "thinking": "I'll analyze the code structure first. Looking at the imports...",
            }
        ]
    },
}

SAMPLE_TOOL_EVENT = {
    "type": "assistant",
    "message": {
        "content": [
            {
                "type": "tool_use",
                "name": "Edit",
                "input": {
                    "file_path": "/home/user/projects/myapp/src/test.py",
                    "old_string": "def old():",
                    "new_string": "def new():",
                },
            }
        ]
    },
}

SAMPLE_TASK_EVENT = {
    "type": "assistant",
    "message": {
        "content": [
            {
                "type": "tool_use",
                "name": "Task",
                "input": {
                    "description": "Search for tests",
                    "prompt": "Find all test files",
                    "subagent_type": "Explore",
                },
            }
        ]
    },
}

SAMPLE_USER_MESSAGE = {
    "type": "user",
    "message": {"content": "Please fix the bug in the login function"},
}

SAMPLE_READ_EVENT = {
    "type": "assistant",
    "message": {
        "content": [
            {
                "type": "tool_use",
                "name": "Read",
                "input": {"file_path": "/home/user/projects/myapp/README.md"},
            }
        ]
    },
}

SAMPLE_BASH_EVENT = {
    "type": "assistant",
    "message": {
        "content": [
            {"type": "tool_use", "name": "Bash", "input": {"command": "python -m pytest tests/ -v"}}
        ]
    },
}


def create_mock_transcript(events: Optional[list] = None, include_samples: bool = True) -> Path:
    """Create a temporary transcript file with events.

    Args:
        events: Custom events to include
        include_samples: Whether to include sample events

    Returns:
        Path to the temporary transcript file
    """
    all_events = []

    if include_samples:
        all_events.extend(
            [
                SAMPLE_USER_MESSAGE,
                SAMPLE_THINKING_EVENT,
                SAMPLE_READ_EVENT,
                SAMPLE_TOOL_EVENT,
            ]
        )

    if events:
        all_events.extend(events)

    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with open(fd, "w") as f:
        for event in all_events:
            f.write(json.dumps(event) + "\n")

    return Path(path)


def create_transcript_with_events(
    thinking_count: int = 0,
    tool_count: int = 0,
    task_count: int = 0,
    bash_count: int = 0,
    file_edits: Optional[list[str]] = None,
) -> Path:
    """Create a transcript with specific event counts.

    Args:
        thinking_count: Number of thinking events
        tool_count: Number of tool events (Edit/Write)
        task_count: Number of Task (subagent) events
        bash_count: Number of Bash events
        file_edits: List of file paths to include in edits

    Returns:
        Path to the temporary transcript file
    """
    events = []
    file_edits = file_edits or ["/test.py"]

    for i in range(thinking_count):
        events.append(
            {
                "type": "assistant",
                "message": {
                    "content": [{"type": "thinking", "thinking": f"Thinking block {i}..."}]
                },
            }
        )

    for i in range(tool_count):
        file_path = file_edits[i % len(file_edits)]
        events.append(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "tool_use", "name": "Edit", "input": {"file_path": file_path}}
                    ]
                },
            }
        )

    for i in range(task_count):
        events.append(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Task",
                            "input": {
                                "description": f"Task {i}",
                                "prompt": "Do something",
                                "subagent_type": "Explore",
                            },
                        }
                    ]
                },
            }
        )

    for i in range(bash_count):
        events.append(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Bash",
                            "input": {"command": f"echo 'Command {i}'"},
                        }
                    ]
                },
            }
        )

    return create_mock_transcript(events=events, include_samples=False)
