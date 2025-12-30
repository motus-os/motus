"""Event factory functions for testing."""

from datetime import datetime
from typing import Optional


def make_thinking_event(content: str = "Analyzing...") -> dict:
    """Create a thinking event dict."""
    return {
        "type": "assistant",
        "message": {"content": [{"type": "thinking", "thinking": content}]},
    }


def make_tool_event(
    name: str = "Read",
    input_data: Optional[dict] = None,
) -> dict:
    """Create a tool use event dict."""
    input_data = input_data or {}
    return {
        "type": "assistant",
        "message": {"content": [{"type": "tool_use", "name": name, "input": input_data}]},
    }


def make_task_event(
    description: str = "Search codebase",
    prompt: str = "Find files",
    subagent_type: str = "Explore",
    model: Optional[str] = None,
) -> dict:
    """Create a Task (subagent) event dict."""
    input_data = {
        "description": description,
        "prompt": prompt,
        "subagent_type": subagent_type,
    }
    if model:
        input_data["model"] = model

    return make_tool_event(name="Task", input_data=input_data)


def make_assistant_message(
    text: str = "Here's my response...",
    include_thinking: bool = False,
    thinking_content: str = "Let me think about this...",
) -> dict:
    """Create an assistant message event."""
    content = []

    if include_thinking:
        content.append({"type": "thinking", "thinking": thinking_content})

    content.append({"type": "text", "text": text})

    return {"type": "assistant", "message": {"content": content}}


def make_user_message(content: str = "Please help me...") -> dict:
    """Create a user message event."""
    return {"type": "user", "message": {"content": content}}


def make_edit_event(
    file_path: str = "/test.py",
    old_string: str = "old",
    new_string: str = "new",
) -> dict:
    """Create an Edit tool event."""
    return make_tool_event(
        name="Edit",
        input_data={
            "file_path": file_path,
            "old_string": old_string,
            "new_string": new_string,
        },
    )


def make_bash_event(
    command: str = "ls -la",
    description: str = "List files",
) -> dict:
    """Create a Bash tool event."""
    return make_tool_event(
        name="Bash",
        input_data={
            "command": command,
            "description": description,
        },
    )


def make_decision_event(
    decision: str = "Use async for better performance",
    reasoning: str = "The batch is large",
) -> dict:
    """Create an SDK Decision event."""
    return {
        "type": "Decision",
        "decision": decision,
        "reasoning": reasoning,
    }


def make_codex_function_call(
    name: str = "shell_command",
    arguments: Optional[dict] = None,
) -> dict:
    """Create a Codex CLI function call event."""
    arguments = arguments or {"command": "ls"}
    return {
        "type": "response_item",
        "timestamp": datetime.now().isoformat(),
        "payload": {
            "type": "function_call",
            "name": name,
            "arguments": arguments,
        },
    }
