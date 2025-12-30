# MCP Interface

## Overview

Motus Command exposes an MCP server over stdio. It wraps core session
operations so external tools can list sessions, fetch events, and export
teleport bundles.

## Installation

MCP support is an optional dependency:

```bash
pip install "motusos[mcp]"
```

For editable installs:

```bash
pip install -e ".[mcp]"
```

## Run the server

```bash
mc mcp
```

You can also run the module directly:

```bash
python -m motus.mcp
```

If the MCP extra is not installed, `mc mcp` will exit with an error message
prompting you to install `.[mcp]`.

## Tools

### list_sessions

List recent sessions discovered by Motus.

Parameters:
- `max_age_hours` (int, default: 24)
- `sources` (list[str], default: ["claude", "codex", "gemini", "sdk"])
- `limit` (int, default: 50, max: 200)

Notes:
- Results are always redacted (project paths may include home paths).

### get_session

Fetch a single session by ID. Prefix match is supported.

Parameters:
- `session_id` (str, required)
- `redact` (bool, default: true)

Notes:
- Raises an error if the session ID is not found or is ambiguous.

### get_events

Return events for a session (tail by default).

Parameters:
- `session_id` (str, required)
- `validated` (bool, default: false)
- `tail_lines` (int, default: 200, min: 10, max: 5000)
- `full` (bool, default: false)
- `redact` (bool, default: true)
- `include_raw_data` (bool, default: false)

Notes:
- When `full` is false, results are truncated to the tail and `truncated` is true.
- `raw_data` fields are omitted unless `include_raw_data` is true.

### get_context

Return aggregated session context.

Parameters:
- `session_id` (str, required)
- `redact` (bool, default: true)

### export_teleport

Export a teleport bundle for cross-session handoffs.

Parameters:
- `session_id` (str, required)
- `include_planning_docs` (bool, default: true)
- `redact` (bool, default: true)

