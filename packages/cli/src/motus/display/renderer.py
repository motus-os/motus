# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""SafeRenderer - centralized escaping. ALL user content flows through here."""

import html

from rich.markup import escape as rich_escape


class SafeRenderer:
    """Centralized escaping. Escaping is automatic and unavoidable."""

    @staticmethod
    def escape(content: str) -> str:
        """Escape for Rich markup."""
        if not content:
            return ""
        return rich_escape(str(content))

    @staticmethod
    def escape_html(content: str) -> str:
        """Escape for HTML (Web UI)."""
        if not content:
            return ""
        return html.escape(str(content))

    @staticmethod
    def truncate(content: str, max_len: int, suffix: str = "...") -> str:
        """Truncate safely."""
        if not content:
            return ""
        if len(content) <= max_len:
            return content
        return content[: max_len - len(suffix)] + suffix

    @classmethod
    def file_path(cls, path: str, max_len: int = 60) -> str:
        """Escape and optionally truncate file path."""
        return cls.escape(cls.truncate(path, max_len))

    @classmethod
    def command(cls, cmd: str, max_len: int = 100) -> str:
        """Escape and truncate command."""
        return cls.escape(cls.truncate(cmd, max_len))

    @classmethod
    def content(cls, text: str, max_len: int = 200) -> str:
        """Escape and truncate content preview."""
        if not text:
            return ""
        # Normalize whitespace
        normalized = " ".join(text.split())
        return cls.escape(cls.truncate(normalized, max_len))
