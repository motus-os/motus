# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Context extraction helpers for Motus Claude Code hooks."""

import json
from datetime import datetime, timedelta
from pathlib import Path

from .config import config
from .logging import get_logger

logger = get_logger(__name__)

# Use config for directories
MC_STATE_DIR = config.paths.state_dir
CLAUDE_DIR = config.paths.claude_dir

MAX_SESSION_SIZE_BYTES = 100 * 1024 * 1024


def get_project_sessions(
    cwd: str,
    max_age_hours: int = 24,
    claude_dir: Path | None = None,
    mc_state_dir: Path | None = None,
    gemini_dir: Path | None = None,
) -> list:
    """Find recent Motus sessions for a project directory."""
    sessions = []
    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    claude_dir = claude_dir or CLAUDE_DIR
    mc_state_dir = mc_state_dir or MC_STATE_DIR
    gemini_dir = gemini_dir or (Path.home() / ".gemini")

    # Check Claude transcript directory
    projects_dir = claude_dir / "projects"
    if projects_dir.exists():
        for session_dir in projects_dir.iterdir():
            if not session_dir.is_dir():
                continue
            # Match project path (encoded as -home-user-projects-project)
            encoded_cwd = cwd.replace("/", "-").lstrip("-")
            if encoded_cwd in session_dir.name:
                for jsonl_file in session_dir.glob("*.jsonl"):
                    try:
                        mtime = datetime.fromtimestamp(jsonl_file.stat().st_mtime)
                    except OSError as e:
                        logger.warning(
                            "Failed to stat session file",
                            session_path=str(jsonl_file),
                            error_type=type(e).__name__,
                            error=str(e),
                        )
                        continue
                    if mtime > cutoff:
                        sessions.append({"path": jsonl_file, "mtime": mtime, "type": "claude"})

    # Check Gemini session directory
    # Structure: ~/.gemini/tmp/<project_hash>/chats/session-*.json
    gemini_tmp = gemini_dir / "tmp"
    if gemini_tmp.exists():
        for project_dir in gemini_tmp.iterdir():
            if not project_dir.is_dir():
                continue

            # Simple heuristic: if we can't match hash to path easily,
            # we might need to look inside or rely on the project_hash passed in.
            # For now, we'll skip the strict CWD match for Gemini unless we can decode the hash
            # OR we assume the user is passing a matching project context.
            # A safer fallback is to check if the session file contains references to the CWD
            # but that's expensive.
            # Strategy: Search ALL recent Gemini sessions and filter by "project_path" inside if needed?
            # For efficiency, we will assume we want ALL recent Gemini sessions if we are in a Gemini context
            # but that's risky.
            # Better: The 'project_dir' name in Gemini is a hash of the path.
            # We can't easily reverse it. But we can check if `chats` exists.

            chats_dir = project_dir / "chats"
            if chats_dir.exists():
                for json_file in chats_dir.glob("session-*.json"):
                    try:
                        mtime = datetime.fromtimestamp(json_file.stat().st_mtime)
                        if mtime > cutoff:
                             sessions.append({"path": json_file, "mtime": mtime, "type": "gemini"})
                    except OSError:
                        continue

    # Check SDK traces directory
    traces_dir = mc_state_dir / "traces"
    if traces_dir.exists():
        for trace_file in traces_dir.glob("*.jsonl"):
            try:
                mtime = datetime.fromtimestamp(trace_file.stat().st_mtime)
            except OSError as e:
                logger.warning(
                    "Failed to stat trace file",
                    trace_file=str(trace_file),
                    error_type=type(e).__name__,
                    error=str(e),
                )
                continue
            if mtime > cutoff:
                sessions.append({"path": trace_file, "mtime": mtime, "type": "sdk"})

    return sorted(sessions, key=lambda x: x["mtime"], reverse=True)


def extract_decisions_from_session(
    session_path: Path,
    max_decisions: int = 5,
    max_session_size_bytes: int | None = None,
) -> list:
    """Extract key decisions from a session transcript."""
    decisions = []
    parse_error_logged = False
    max_session_size_bytes = max_session_size_bytes or MAX_SESSION_SIZE_BYTES

    try:
        try:
            file_size = session_path.stat().st_size
            if file_size > max_session_size_bytes:
                return []
        except OSError:
            return []

        # Handle Gemini JSON files
        if session_path.suffix == ".json":
            try:
                with open(session_path, encoding="utf-8", errors="replace") as f:
                    data = json.load(f)
                    messages = data.get("messages", [])
                    for msg in messages:
                        if msg.get("type") == "gemini":
                            # Check thoughts
                            for thought in msg.get("thoughts", []):
                                desc = thought.get("description", "")
                                # Check for decision markers
                                decision_markers = ["I'll ", "I will ", "I decided ", "I should "]
                                if any(m in desc for m in decision_markers):
                                     decisions.append({"decision": desc[:200], "reasoning": thought.get("subject", "")})

                            # Check content text
                            content = msg.get("content", "")
                            # (Reuse generic text scanning if needed, but thoughts are better)
            except (json.JSONDecodeError, OSError) as e:
                 logger.warning("Error reading Gemini session", path=str(session_path), error=str(e))
            return decisions[:max_decisions]

        # Handle JSONL (Claude/SDK)
        with open(session_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    event = json.loads(line)

                    # SDK decision events (case-insensitive for tracer compatibility)
                    event_type = event.get("type", "").lower()
                    if event_type == "decision":
                        decisions.append(
                            {
                                "decision": event.get("decision", ""),
                                "reasoning": event.get("reasoning", ""),
                            }
                        )

                    # Claude thinking blocks with decision patterns
                    if event.get("type") == "assistant":
                        content = event.get("message", {}).get("content", [])
                        for block in content:
                            if block.get("type") == "thinking":
                                text = block.get("thinking", "")
                                # Look for decision patterns
                                decision_markers = [
                                    "I'll ",
                                    "I will ",
                                    "I decided ",
                                    "I'm going to ",
                                    "The best approach ",
                                    "I should ",
                                    "Let's ",
                                ]
                                for marker in decision_markers:
                                    if marker in text:
                                        # Extract the sentence containing the decision
                                        sentences = text.split(". ")
                                        for s in sentences:
                                            if marker in s:
                                                decisions.append(
                                                    {"decision": s.strip()[:200], "reasoning": ""}
                                                )
                                                break
                                        break

                except json.JSONDecodeError:
                    if not parse_error_logged:
                        logger.warning(
                            "Invalid JSON line in session file",
                            session_path=str(session_path),
                        )
                        parse_error_logged = True
                    continue
    except OSError as e:
        logger.warning(
            "Error reading session file",
            session_path=str(session_path),
            error_type=type(e).__name__,
            error=str(e),
        )
    except (ValueError, TypeError, UnicodeDecodeError) as e:
        logger.warning(
            "Error parsing session file for decisions",
            session_path=str(session_path),
            error_type=type(e).__name__,
            error=str(e),
        )

    return decisions[:max_decisions]


def extract_file_patterns(
    session_path: Path,
    max_session_size_bytes: int | None = None,
) -> dict:
    """Extract frequently modified files from a session."""
    file_counts: dict[str, int] = {}
    parse_error_logged = False
    max_session_size_bytes = max_session_size_bytes or MAX_SESSION_SIZE_BYTES

    try:
        try:
            file_size = session_path.stat().st_size
            if file_size > max_session_size_bytes:
                return {}
        except OSError:
            return {}

        # Handle Gemini JSON files
        if session_path.suffix == ".json":
            try:
                with open(session_path, encoding="utf-8", errors="replace") as f:
                    data = json.load(f)
                    messages = data.get("messages", [])
                    for msg in messages:
                        if msg.get("type") == "gemini":
                            for tool_call in msg.get("toolCalls", []):
                                name = tool_call.get("name", "")
                                args = tool_call.get("args", {})
                                if name in ["run_terminal_cmd", "run_shell_command"]:
                                    # Heuristic for file touches in shell commands?
                                    # Maybe too noisy. Skip for now.
                                    pass
                                elif name in ["write_file", "replace_in_file", "replace"]:
                                    path = args.get("file_path") or args.get("path")
                                    if path:
                                        file_counts[path] = file_counts.get(path, 0) + 1
            except (json.JSONDecodeError, OSError):
                pass
            return file_counts

        # Handle JSONL
        with open(session_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    event = json.loads(line)

                    event_type = event.get("type", "")

                    # Claude: tool_use events
                    if event_type == "tool_use":
                        tool_name = event.get("name", "")
                        tool_input = event.get("input", {})

                        if tool_name in ["Write", "Edit"]:
                            file_path = tool_input.get("file_path", "")
                            if file_path:
                                file_counts[file_path] = file_counts.get(file_path, 0) + 1

                    # Codex: response_item with function_call
                    elif event_type == "response_item":
                        item = event.get("item", {})
                        func_call = item.get("function_call", {})
                        tool_name = func_call.get("name", "")
                        if tool_name in ["write_file", "edit_file", "Write", "Edit"]:
                            args = func_call.get("arguments", "{}")
                            if isinstance(args, str):
                                try:
                                    args = json.loads(args)
                                except json.JSONDecodeError:
                                    args = {}
                            file_path = args.get("file_path", "") or args.get("path", "")
                            if file_path:
                                file_counts[file_path] = file_counts.get(file_path, 0) + 1

                    # SDK: FileChange events (case-insensitive)
                    elif event_type.lower() == "filechange":
                        file_path = event.get("path", "")
                        if file_path:
                            file_counts[file_path] = file_counts.get(file_path, 0) + 1

                except json.JSONDecodeError:
                    if not parse_error_logged:
                        logger.warning(
                            "Invalid JSON line in session file",
                            session_path=str(session_path),
                        )
                        parse_error_logged = True
                    continue
    except OSError as e:
        logger.warning(
            "Error reading session file for file patterns",
            session_path=str(session_path),
            error_type=type(e).__name__,
            error=str(e),
        )
    except (ValueError, TypeError, UnicodeDecodeError) as e:
        logger.warning(
            "Error parsing session file for file patterns",
            session_path=str(session_path),
            error_type=type(e).__name__,
            error=str(e),
        )

    return file_counts
