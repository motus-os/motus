# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""
Teleport Export Logic.

This module handles the creation of TeleportBundle objects for
cross-session context transfer, including planning document detection.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from ..logging import get_logger
from ..protocols import EventType, TeleportBundle, UnifiedEvent, UnifiedSession

logger = get_logger(__name__)
MAX_TELEPORT_DOC_BYTES = int(os.environ.get("MC_TELEPORT_MAX_BYTES", "1048576"))


def _safe_read_text(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_TELEPORT_DOC_BYTES:
            logger.debug("Skipping large doc file", doc_file=str(path))
            return None
    except OSError as e:
        logger.debug(
            "Failed to stat doc file",
            doc_file=str(path),
            error_type=type(e).__name__,
            error=str(e),
        )
        return None
    return path.read_text(encoding="utf-8", errors="ignore")


def detect_planning_docs(project_path: str) -> Dict[str, str]:
    """
    Detect and load planning documents from project.

    Args:
        project_path: Path to the project directory.

    Returns:
        Dictionary mapping document names to their content.
    """
    planning_docs: dict[str, str] = {}
    project_dir = Path(project_path)

    if not project_dir.exists():
        return planning_docs

    # Define planning doc patterns to search for
    doc_patterns = [
        "ROADMAP.md",
        "ROADMAP-*.md",
        "ARCHITECTURE.md",
        "DESIGN.md",
        "CONTRIBUTING.md",
    ]

    # Search for matching docs
    for pattern in doc_patterns:
        if "*" in pattern:
            # Glob pattern
            for doc_file in project_dir.glob(pattern):
                if doc_file.is_file():
                    try:
                        # Security: Check for symlinks and validate resolved path
                        if doc_file.is_symlink():
                            resolved = doc_file.resolve()
                            # Verify resolved path stays under project directory
                            if not str(resolved).startswith(str(project_dir.resolve())):
                                logger.debug(
                                    "Skipping symlink outside project",
                                    doc_file=str(doc_file),
                                    resolved=str(resolved),
                                )
                                continue

                        content = _safe_read_text(doc_file)
                        if content is None:
                            continue
                        # Get first 500 chars or first section
                        preview = extract_doc_summary(content)
                        planning_docs[doc_file.name] = preview
                    except Exception as e:
                        logger.debug(
                            "Failed to read doc file",
                            doc_file=str(doc_file),
                            error_type=type(e).__name__,
                            error=str(e),
                        )
        else:
            # Exact match
            doc_file = project_dir / pattern
            if doc_file.is_file():
                try:
                    # Security: Check for symlinks and validate resolved path
                    if doc_file.is_symlink():
                        resolved = doc_file.resolve()
                        # Verify resolved path stays under project directory
                        if not str(resolved).startswith(str(project_dir.resolve())):
                            logger.debug(
                                "Skipping symlink outside project",
                                doc_file=str(doc_file),
                                resolved=str(resolved),
                            )
                            continue

                    content = _safe_read_text(doc_file)
                    if content is None:
                        continue
                    preview = extract_doc_summary(content)
                    planning_docs[doc_file.name] = preview
                except Exception as e:
                    logger.debug(
                        "Failed to read doc file",
                        doc_file=str(doc_file),
                        error_type=type(e).__name__,
                        error=str(e),
                    )

    # Check for .claude/commands/*.md (custom slash commands)
    claude_commands_dir = project_dir / ".claude" / "commands"
    if claude_commands_dir.exists():
        command_files = list(claude_commands_dir.glob("*.md"))
        if command_files:
            # Combine all command files into one summary
            command_summary = "**Custom Slash Commands:**\n\n"
            for cmd_file in command_files[:5]:  # Limit to 5 commands
                try:
                    # Security: Check for symlinks and validate resolved path
                    if cmd_file.is_symlink():
                        resolved = cmd_file.resolve()
                        if not str(resolved).startswith(str(project_dir.resolve())):
                            logger.debug(
                                "Skipping symlink outside project",
                                cmd_file=str(cmd_file),
                                resolved=str(resolved),
                            )
                            continue

                    content = _safe_read_text(cmd_file)
                    if content is None:
                        continue
                    # Extract just the first line or first 100 chars
                    first_line = content.split("\n")[0] if "\n" in content else content[:100]
                    command_summary += f"- `/{cmd_file.stem}`: {first_line[:100]}\n"
                except Exception as e:
                    logger.debug(
                        "Failed to read command file",
                        cmd_file=str(cmd_file),
                        error_type=type(e).__name__,
                        error=str(e),
                    )
            if len(command_summary) > 50:  # Only add if we got content
                planning_docs[".claude/commands"] = command_summary

    # Check for .mc/intent.yaml
    intent_file = project_dir / ".mc" / "intent.yaml"
    if intent_file.is_file():
        try:
            # Security: Check for symlinks and validate resolved path
            if intent_file.is_symlink():
                resolved = intent_file.resolve()
                if not str(resolved).startswith(str(project_dir.resolve())):
                    logger.debug(
                        "Skipping symlink outside project",
                        intent_file=str(intent_file),
                        resolved=str(resolved),
                    )
                else:
                    content = _safe_read_text(intent_file)
                    if content is None:
                        return planning_docs
                    planning_docs["intent.yaml"] = content[:500]
            else:
                content = _safe_read_text(intent_file)
                if content is None:
                    return planning_docs
                planning_docs["intent.yaml"] = content[:500]
        except Exception as e:
            logger.debug(
                "Failed to read intent file",
                intent_file=str(intent_file),
                error_type=type(e).__name__,
                error=str(e),
            )

    return planning_docs


def extract_doc_summary(content: str, max_chars: int = 500) -> str:
    """
    Extract a summary from document content.

    Tries to use Gemini LLM for semantic summarization.
    Falls back to first 500 chars or first major section break.

    Args:
        content: Full document content.
        max_chars: Maximum characters to include.

    Returns:
        Document summary.
    """
    # Try LLM summarization first
    try:
        from ..llm.gemini_client import get_gemini_client
        client = get_gemini_client()
        if client.api_key:
            return client.summarize_text(content, max_words=100)
    except (ImportError, Exception) as e:
        # Fallback if google-genai not installed or configured
        logger.debug("LLM summarization skipped", reason=str(e))

    # Fallback logic
    lines = content.split("\n")
    summary_lines = []
    char_count = 0

    for i, line in enumerate(lines):
        # Stop at second major heading (##) or max chars
        if i > 0 and line.startswith("## "):
            break

        summary_lines.append(line)
        char_count += len(line) + 1  # +1 for newline

        if char_count >= max_chars:
            summary_lines.append("...")
            break

    return "\n".join(summary_lines).strip()


def create_teleport_bundle(
    session: UnifiedSession,
    events: List[UnifiedEvent],
    context: Dict,
    last_action: str,
    include_planning_docs: bool = True,
) -> TeleportBundle:
    """
    Create a TeleportBundle for cross-session context transfer.

    Args:
        session: The session to export.
        events: Session events.
        context: Session context from get_context().
        last_action: Last action from builder.
        include_planning_docs: Whether to include planning documents (default: True).

    Returns:
        TeleportBundle for injection into another session.
    """
    # Find intent from thinking blocks
    intent = ""
    for event in events:
        if event.event_type == EventType.THINKING:
            # Look for intent patterns
            content = event.content.lower()
            if any(marker in content for marker in ["i'll ", "i will ", "goal:", "task:"]):
                intent = event.content[:300]
                break

    # Hot files are recently modified
    hot_files = context["files_modified"][-5:]  # Last 5 modified

    # Detect planning docs if enabled
    planning_docs = {}
    if include_planning_docs:
        planning_docs = detect_planning_docs(session.project_path)

    return TeleportBundle(
        source_session=session.session_id,
        source_model=session.source.value,
        intent=intent,
        decisions=context["decisions"],
        files_touched=context["files_read"] + context["files_modified"],
        hot_files=hot_files,
        pending_todos=[],  # Not tracking todos yet
        last_action=last_action,
        timestamp=datetime.now(),
        planning_docs=planning_docs,
    )
