# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

from __future__ import annotations

from argparse import Namespace

from motus.commands.claude_cmd import (
    BLOCK_END,
    BLOCK_START,
    _apply_managed_block,
    _build_claude_block,
    claude_command,
)


def test_apply_managed_block_appends() -> None:
    block = _build_claude_block("docs/AGENT-INSTRUCTIONS.md")
    content, status = _apply_managed_block(
        "Existing content",
        block,
        allow_append=True,
        force=False,
    )
    assert status == "added"
    assert "Existing content" in content
    assert BLOCK_START in content
    assert BLOCK_END in content


def test_apply_managed_block_conflict_without_force() -> None:
    block = _build_claude_block("docs/AGENT-INSTRUCTIONS.md")
    modified = block.replace("full guide", "custom guide")
    content, status = _apply_managed_block(
        modified,
        block,
        allow_append=True,
        force=False,
    )
    assert status == "conflict"
    assert content == modified


def test_claude_command_stdout_does_not_write(tmp_path, capsys) -> None:
    args = Namespace(
        path=str(tmp_path),
        claude_path=None,
        docs_path="docs/AGENT-INSTRUCTIONS.md",
        no_docs=False,
        dry_run=False,
        stdout=True,
        force=False,
    )
    rc = claude_command(args)
    assert rc == 0
    assert not (tmp_path / "CLAUDE.md").exists()
    assert not (tmp_path / "docs" / "AGENT-INSTRUCTIONS.md").exists()

    output = capsys.readouterr().out
    assert "Motus Agent Instructions" in output
