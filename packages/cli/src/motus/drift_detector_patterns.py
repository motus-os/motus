# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Pattern matching and drift rules for drift detection."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set

from .exceptions import InvalidIntentError


@dataclass
class UserIntent:
    raw_message: str
    timestamp: datetime
    mentioned_directories: Set[str] = field(default_factory=set)
    mentioned_file_types: Set[str] = field(default_factory=set)
    keywords: Set[str] = field(default_factory=set)
    confidence: float = 0.5


@dataclass
class DriftSignal:
    signal_type: str
    description: str
    severity: float
    expected: str
    actual: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class DriftState:
    session_id: str
    is_drifting: bool = False
    drift_score: float = 0.0
    signals: List[DriftSignal] = field(default_factory=list)
    last_checked: datetime = field(default_factory=datetime.now)

    def add_signal(self, signal: DriftSignal) -> None:
        self.signals.append(signal)
        if len(self.signals) > 10:
            self.signals = self.signals[-10:]
        self._update_score()

    def _update_score(self) -> None:
        if not self.signals:
            self.drift_score = 0.0
            self.is_drifting = False
            return

        now = datetime.now()
        weighted_sum = 0.0
        weight_total = 0.0

        for signal in self.signals:
            age = (now - signal.timestamp).total_seconds()
            weight = max(0.1, 1.0 - (age / 300))
            weighted_sum += signal.severity * weight
            weight_total += weight

        self.drift_score = weighted_sum / weight_total if weight_total > 0 else 0.0
        self.is_drifting = self.drift_score > 0.5
        self.last_checked = now


CONTENT_KEYWORDS = {"content", "blog", "post", "essay", "article", "write", "writing", "linkedin", "twitter", "social", "calendar", "newsletter", "copy", "headline", "draft", "edit", "publish", "voice", "tone", "audience"}
CODE_KEYWORDS = {"code", "function", "class", "bug", "fix", "implement", "refactor", "test", "deploy", "build", "compile", "package", "install", "pip", "npm", "git", "commit", "merge", "branch", "api", "endpoint", "database"}
CONTENT_FILE_TYPES = {".md", ".txt", ".doc", ".docx", ".rtf"}
CODE_FILE_TYPES = {".py", ".js", ".ts", ".tsx", ".jsx", ".css", ".html", ".json", ".toml", ".yaml", ".yml"}


def extract_intent(message: str) -> UserIntent:
    message_lower = message.lower()

    directories: Set[str] = set()
    file_types: Set[str] = set()
    try:
        path_pattern = r"[/~][\w\-./]+"
        for match in re.findall(path_pattern, message):
            directories.add(match)

        type_pattern = r"\.\w{1,4}\b"
        for match in re.findall(type_pattern, message_lower):
            file_types.add(match)
    except re.error as e:
        raise InvalidIntentError("Failed to extract intent", details=str(e)) from e

    if any(kw in message_lower for kw in CONTENT_KEYWORDS):
        file_types.update(CONTENT_FILE_TYPES)
    if any(kw in message_lower for kw in CODE_KEYWORDS):
        file_types.update(CODE_FILE_TYPES)

    keywords = set()
    words = set(re.findall(r"\b\w+\b", message_lower))
    keywords.update(words & CONTENT_KEYWORDS)
    keywords.update(words & CODE_KEYWORDS)

    confidence = 0.3
    if directories:
        confidence += 0.2
    if file_types:
        confidence += 0.2
    if keywords:
        confidence += 0.3

    return UserIntent(
        raw_message=message,
        timestamp=datetime.now(),
        mentioned_directories=directories,
        mentioned_file_types=file_types,
        keywords=keywords,
        confidence=min(1.0, confidence),
    )


def check_directory_drift(intent: UserIntent, file_path: str) -> Optional[DriftSignal]:
    if not intent.mentioned_directories:
        return None

    path = Path(file_path)
    path_str = str(path)

    for expected_dir in intent.mentioned_directories:
        if expected_dir in path_str or path_str.startswith(expected_dir):
            return None

    return DriftSignal(
        signal_type="directory",
        description=f"Working in {path.parent} but expected {intent.mentioned_directories}",
        severity=0.7,
        expected=str(intent.mentioned_directories),
        actual=str(path.parent),
    )


def check_file_type_drift(intent: UserIntent, file_path: str) -> Optional[DriftSignal]:
    if not intent.mentioned_file_types:
        return None

    path = Path(file_path)
    ext = path.suffix.lower()

    if not ext:
        return None

    if ext in intent.mentioned_file_types:
        return None

    is_content_intent = bool(intent.keywords & CONTENT_KEYWORDS)
    is_code_intent = bool(intent.keywords & CODE_KEYWORDS)

    if is_content_intent and not is_code_intent and ext in CODE_FILE_TYPES:
        return DriftSignal(
            signal_type="file_type",
            description=f"Editing {ext} file but intent was content-focused",
            severity=0.8,
            expected="content files (.md, .txt)",
            actual=f"{ext} file",
        )

    if is_code_intent and not is_content_intent and ext in CONTENT_FILE_TYPES:
        return DriftSignal(
            signal_type="file_type",
            description=f"Editing {ext} file but intent was code-focused",
            severity=0.3,
            expected="code files",
            actual=f"{ext} file",
        )

    return None


def check_tool_pattern_drift(
    intent: UserIntent, recent_actions: List[dict]
) -> Optional[DriftSignal]:
    is_content_intent = bool(intent.keywords & CONTENT_KEYWORDS)
    is_code_intent = bool(intent.keywords & CODE_KEYWORDS)

    code_tools = {"Edit", "Bash", "Write"}

    if is_content_intent and not is_code_intent:
        code_tool_count = sum(
            1 for a in recent_actions[-5:] if a["tool"] in code_tools
        )
        if code_tool_count >= 3:
            return DriftSignal(
                signal_type="tool_pattern",
                description=(
                    f"Heavy code tool usage ({code_tool_count}/5) but intent was content-focused"
                ),
                severity=0.6,
                expected="content-focused tools (Read, Write markdown)",
                actual=f"{code_tool_count} code tools in last 5 actions",
            )

    return None
