# Integration Guide

## Overview

Motus reads local session logs produced by supported agent CLIs and
presents them via `motus list` and `motus web`. It does not require any cloud
integration or additional SDK for these sources.

Supported sources in this guide:
- Claude Code
- OpenAI Codex CLI
- Google Gemini CLI

## Prerequisites

```bash
pip install motusos
```

Generate at least one session in the agent CLI you want to integrate. Motus
only shows sessions it can find on disk.

## Claude Code

**Session logs:** `~/.claude/projects/<project>/*.jsonl`

Motus discovers Claude sessions by scanning the Claude projects directory and
reading JSONL files inside each project. If the directory does not exist, run
Claude Code once to create it.

**Verify logs exist:**
```bash
ls ~/.claude/projects
```

**View sessions:**
```bash
motus list
motus web
```

## OpenAI Codex CLI

**Session logs:** `~/.codex/sessions/**/*.jsonl`

Motus walks the Codex sessions directory and looks for JSONL files whose first
line is a `session_meta` record. The session ID and working directory are read
from that metadata.

**Verify logs exist:**
```bash
ls ~/.codex/sessions
```

**View sessions:**
```bash
motus list
motus web
```

## Google Gemini CLI

**Session logs:** `~/.gemini/tmp/<project>/chats/session-*.json`

Motus scans Gemini project temp directories for `session-*.json` files and
shows them with a `gemini:<hash>` project identifier.

**Verify logs exist:**
```bash
ls ~/.gemini/tmp
```

**View sessions:**
```bash
motus list
motus web
```

## Notes

- Motus stores its own logs and traces under `~/.mc/`.
- Use `motus list --fast` to skip process detection when you only want cached
  session discovery.

