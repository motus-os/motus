# CLI Reference

## Overview

Motus Command (`mc`) provides a comprehensive CLI for monitoring AI agent sessions, enforcing policy gates, and managing workspace state.

```bash
mc [COMMAND] [OPTIONS]
```

## Quick Start

```bash
mc web                # Launch web dashboard at http://127.0.0.1:4000
mc list               # List recent sessions
mc watch              # Watch active session in real-time
mc policy plan --files src/main.py  # Plan policy gates for a file
```

## Commands by Tier

### Tier 0 (Instant Value)

| Command | Description |
|---------|-------------|
| `list` | List recent sessions |
| `watch` | Watch a session in real-time |
| `web` | Launch web dashboard at http://127.0.0.1:4000 |

### Tier 1 (Basic)

| Command | Description |
|---------|-------------|
| `context` | Generate context summary for AI agent prompts |
| `doctor` | Run health checks |
| `feed` | Show recent events for a session |
| `install` | Install agent onboarding defaults |
| `show` | Show session details |
| `sync` | Sync session cache into SQLite |

### Tier 2 (Standard)

| Command | Description |
|---------|-------------|
| `checkpoint` | Create a state checkpoint |
| `checkpoints` | List all available checkpoints |
| `config` | Manage MC configuration |
| `diff` | Show changes between current state and a checkpoint |
| `errors` | Summarize errors from a session |
| `explain` | Explain a policy run decision trace |
| `history` | Show command history |
| `intent` | Extract/show intent from a session |
| `policy` | Plan and run Vault OS policy gates (proof of compliance) |
| `rollback` | Restore state to a previous checkpoint |
| `teleport` | Export a session bundle for cross-session context transfer |

### Tier 3 (Advanced)

| Command | Description |
|---------|-------------|
| `claims` | Coordination claim registry |
| `harness` | Detect test harness for a repository |
| `init` | Initialize a Motus workspace (.motus/) |
| `mcp` | Start MCP server (stdio transport) |
| `orient` | Lookup a cached decision (Cached Orient) |
| `standards` | Standards (Cached Orient) utilities |
| `summary` | Generate a rich summary for CLAUDE.md injection |

---

## Session Commands

### mc list

List recent AI agent sessions from all sources (Claude, Codex, Gemini, SDK).

**Synopsis:**
```bash
mc list [--fast]
```

**Options:**
- `--fast, --no-process-detect` - Skip process detection for faster listing

**Examples:**
```bash
# List sessions from the last 24 hours
mc list

# Fast listing without process detection
mc list --fast
```

**Output:**
Displays a table with status, source, project, session ID, age, size, and last action for each session.

---

### mc watch

Watch an AI agent session in real-time, showing events as they occur.

**Synopsis:**
```bash
mc watch [session_id]
```

**Arguments:**
- `session_id` - Session ID to watch (optional, uses most recent if omitted)

**Options:**
- `-h, --help` - Show help message

**Examples:**
```bash
# Watch the most recent active session
mc watch

# Watch a specific session (prefix match supported)
mc watch abc123

# Exit watching with Ctrl+C
```

**Behavior:**
- Shows last 8 events from session history
- Polls for new events every 300ms
- Displays activity status every 10 polls
- Press Ctrl+C to exit and see session summary

---

### mc show

Show detailed information for a specific session.

**Synopsis:**
```bash
mc show <session_id>
```

**Arguments:**
- `session_id` - Session ID (prefix match supported)

**Examples:**
```bash
# Show session details
mc show abc123

# Works with partial session ID
mc show abc
```

**Output:**
Displays session metadata including session ID, file path, status, source, project path, and last action.

**Exit Codes:**
- `0` - Success
- `1` - Session not found

---

### mc feed

Show recent events for a session (like a log tail).

**Synopsis:**
```bash
mc feed <session_id> [--tail-lines N]
```

**Arguments:**
- `session_id` - Session ID (prefix match supported)

**Options:**
- `--tail-lines N` - Number of transcript lines to read from end (default: 200, range: 10-5000)

**Examples:**
```bash
# Show last 200 lines of events
mc feed abc123

# Show last 500 lines
mc feed abc123 --tail-lines 500
```

**Output:**
Prints timestamped events in chronological order with format: `HH:MM:SS [event_type] content`

**Exit Codes:**
- `0` - Success
- `1` - Session not found

---

### mc sync

Sync session transcripts into SQLite cache for faster access.

**Synopsis:**
```bash
mc sync [--full] [--max-age-hours N]
```

**Options:**
- `--full` - Full sync: scan and ingest all session files
- `--max-age-hours N` - Incremental sync limited to files modified within this window

**Examples:**
```bash
# Incremental sync (default)
mc sync --full

# Sync only sessions modified in last 24 hours
mc sync --max-age-hours 24

# Full sync of all sessions
mc sync --full
```

**Output:**
Reports number of sessions ingested, files seen, unchanged, partial, corrupted, and skipped, plus duration.

**Exit Codes:**
- `0` - Success
- `1` - Sync failed

---

### mc context

Generate context summary for AI agent prompts from the most recent or specified session.

**Synopsis:**
```bash
mc context [session_id]
```

**Arguments:**
- `session_id` - Session ID (optional, uses most recent if omitted)

**Examples:**
```bash
# Generate context for most recent session
mc context

# Generate context for specific session
mc context abc123
```

**Output:**
Displays a markdown panel with session context suitable for AI agent consumption.

---

### mc summary

Generate a rich summary for CLAUDE.md context injection.

**Synopsis:**
```bash
mc summary [session_id]
```

**Arguments:**
- `session_id` - Session ID to summarize (optional, uses most recent if omitted)

**Examples:**
```bash
# Summarize most recent session
mc summary

# Summarize specific session
mc summary abc123
```

**Output:**
Generates a comprehensive markdown summary of the session including decisions, tools used, and key events.

---

### mc history

Show command history and recent events across all sessions.

**Synopsis:**
```bash
mc history
```

**Examples:**
```bash
# Show recent activity across all sessions
mc history
```

**Output:**
Displays a table of the 30 most recent events from the last 48 hours, showing time, session, source, event type, and details.

---

### mc teleport

Export a session bundle for cross-session context transfer.

**Synopsis:**
```bash
mc teleport <session_id> [--no-docs] [-o OUTPUT]
```

**Arguments:**
- `session_id` - Session ID to export

**Options:**
- `--no-docs` - Exclude planning docs (ROADMAP, ARCHITECTURE, etc.) from bundle
- `-o, --output FILE` - Output file path (default: stdout as JSON)

**Examples:**
```bash
# Export session to JSON (stdout)
mc teleport abc123

# Export to file
mc teleport abc123 -o session-bundle.json

# Export without planning docs
mc teleport abc123 --no-docs -o bundle.json
```

**Output:**
JSON bundle containing session context, events, and relevant documentation.

---

## Web Dashboard

### mc web

Launch interactive web dashboard at http://127.0.0.1:4000

**Synopsis:**
```bash
mc web
```

**Examples:**
```bash
# Launch web dashboard
mc web
```

**Behavior:**
- Starts FastAPI server on port 4000
- Opens browser automatically
- Provides real-time WebSocket updates
- Shows session list, event stream, and statistics
- Press Ctrl+C to stop server

**Features:**
- Real-time session monitoring
- Event filtering and search
- Session timeline visualization
- Multi-source support (Claude, Codex, Gemini, SDK)

---

## Policy Commands

### mc policy plan

Compute and print a deterministic gate plan for changed files.

**Synopsis:**
```bash
mc policy plan --files FILE... [OPTIONS]
mc policy plan --git-diff BASE HEAD [OPTIONS]
```

**Options:**
- `--files FILE...` - Explicit changed files (repo-relative preferred)
- `--git-diff BASE HEAD` - Compute changed files via git diff
- `--vault-dir PATH` - Vault root directory (or set MC_VAULT_DIR)
- `--profile ID` - Profile ID (or set MC_PROFILE; default: personal)
- `--repo PATH` - Repository root (default: current directory)
- `--pack-cap N` - Override profile pack cap
- `--json` - Emit machine-readable JSON

**Examples:**
```bash
# Plan for specific files
mc policy plan --files src/main.py src/utils.py

# Plan using git diff
mc policy plan --git-diff main HEAD

# Plan with specific vault and profile
mc policy plan --files src/main.py --vault-dir ~/vault --profile team
```

**Output:**
Displays the gate plan showing which gates will run, their tier, and pack assignments. Creates trace files in `.mc/traces/`.

---

### mc policy run

Execute required gates and emit an evidence bundle.

**Synopsis:**
```bash
mc policy run --files FILE... [OPTIONS]
mc policy run --git-diff BASE HEAD [OPTIONS]
```

**Options:**
- `--files FILE...` - Explicit changed files (repo-relative preferred)
- `--git-diff BASE HEAD` - Compute changed files via git diff
- `--vault-dir PATH` - Vault root directory (or set MC_VAULT_DIR)
- `--profile ID` - Profile ID (or set MC_PROFILE; default: personal)
- `--repo PATH` - Repository root (default: current directory)
- `--pack-cap N` - Override profile pack cap
- `--evidence-dir PATH` - Evidence root (default: .mc/evidence or MC_EVIDENCE_DIR)
- `--json` - Emit machine-readable JSON

**Examples:**
```bash
# Run gates for specific files
mc policy run --files src/main.py

# Run gates using git diff
mc policy run --git-diff main HEAD

# Run with custom evidence directory
mc policy run --files src/main.py --evidence-dir /tmp/evidence
```

**Output:**
Executes gates and creates an evidence bundle with manifest.json, summary.txt, and HMAC signature.

**Exit Codes:**
- `0` - All gates passed
- `1` - One or more gates failed

---

### mc policy verify

Verify an evidence bundle's cryptographic integrity.

**Synopsis:**
```bash
mc policy verify --evidence PATH [OPTIONS]
```

**Options:**
- `--evidence PATH` - Evidence run directory containing manifest.json (required)
- `--vault-dir PATH` - Vault root directory (or set MC_VAULT_DIR)
- `--json` - Emit machine-readable JSON

**Examples:**
```bash
# Verify evidence bundle
mc policy verify --evidence .mc/evidence/run_abc123

# Verify with JSON output
mc policy verify --evidence .mc/evidence/run_abc123 --json
```

**Output:**
Reports verification status (PASS/FAIL), reason codes, and any validation messages.

**Exit Codes:**
- `0` - Verification passed
- `1` - Verification failed

---

### mc policy prune

Prune old evidence bundles to reclaim disk space.

**Synopsis:**
```bash
mc policy prune [--keep N] [--older-than DAYS] [--dry-run]
```

**Options:**
- `--keep N` - Keep the N most recent bundles (default: 10)
- `--older-than DAYS` - Delete bundles older than DAYS
- `--repo PATH` - Repository root (default: current directory)
- `--evidence-dir PATH` - Evidence root (default: .mc/evidence or MC_EVIDENCE_DIR)
- `--dry-run` - Show what would be deleted without deleting

**Examples:**
```bash
# Preview what would be deleted
mc policy prune --dry-run

# Keep 5 most recent, delete rest
mc policy prune --keep 5

# Delete bundles older than 30 days
mc policy prune --older-than 30

# Combine: keep 10 most recent AND delete those older than 90 days
mc policy prune --keep 10 --older-than 90
```

**Output:**
Reports bundles found, kept, deleted, and bytes reclaimed.

**Exit Codes:**
- `0` - Success

---

## Error Analysis

### mc errors

Summarize errors from one or more sessions.

**Synopsis:**
```bash
mc errors [session_id] [OPTIONS]
mc errors --last N [OPTIONS]
```

**Arguments:**
- `session_id` - Session ID (prefix match supported, optional)

**Options:**
- `--last N` - Summarize last N sessions (range: 1-50)
- `--session PATH` - Explicit session file path (.jsonl)
- `--category TYPE` - Filter to one category: api, exit, file_io
- `--json` - Emit machine-readable JSON

**Examples:**
```bash
# Summarize errors from most recent session
mc errors

# Summarize errors from specific session
mc errors abc123

# Summarize errors from last 5 sessions
mc errors --last 5

# Show only API errors
mc errors abc123 --category api

# JSON output for last 3 sessions
mc errors --last 3 --json
```

**Output:**
Groups errors by category and displays error counts, types, and sample messages.

**Exit Codes:**
- `0` - Success
- `1` - Session not found or other error
- `2` - Invalid arguments

---

### mc explain

Explain a policy run decision trace showing the timeline of gate executions.

**Synopsis:**
```bash
mc explain <run_id> [--repo PATH]
```

**Arguments:**
- `run_id` - Policy run ID (evidence directory name)

**Options:**
- `--repo PATH` - Repository root (default: current working directory)

**Examples:**
```bash
# Explain policy run
mc explain run_abc123

# Explain from different repo
mc explain run_abc123 --repo /path/to/repo
```

**Output:**
Displays a timeline table showing each gate step, status, reason codes, and evidence references. Highlights the first failing gate if any.

**Exit Codes:**
- `0` - Success
- `1` - Decision trace not found or empty
- `2` - Invalid arguments

---

## System Commands

### mc doctor

Run health checks on the Motus Command installation and database.

**Synopsis:**
```bash
mc doctor [--json]
```

**Options:**
- `--json` - Emit machine-readable JSON

**Examples:**
```bash
# Run health checks
mc doctor

# JSON output
mc doctor --json
```

**Output:**
Reports status of database, WAL size, and other health metrics.

**Exit Codes:**
- `0` - All checks passed
- `1` - One or more checks failed

---

### mc install

Install agent onboarding defaults and enable protocol enforcement.

**Synopsis:**
```bash
mc install
```

**Examples:**
```bash
# Install agent onboarding
mc install
```

**Output:**
Displays vault pointers, protocol summary, and updates configuration to enable Motus with strict protocol enforcement.

---

### mc init

Initialize a Motus workspace with `.motus/` directory structure.

**Synopsis:**
```bash
mc init --full [--path PATH] [--force]
mc init --lite [--path PATH] [--force]
mc init --integrate PATH [--force]
```

**Options:**
- `--full` - Create fresh Motus workspace with full structure
- `--lite` - Minimal footprint mode
- `--integrate PATH` - Overlay on existing workspace (creates PATH/.motus only)
- `--path PATH` - Target directory for --full/--lite (default: .)
- `--force` - Repair missing directories and update current pointer (never deletes data)

**Examples:**
```bash
# Initialize full workspace in current directory
mc init --full

# Initialize in specific directory
mc init --full --path ~/projects/myapp

# Minimal workspace
mc init --lite

# Integrate with existing workspace
mc init --integrate ~/projects/existing

# Repair existing workspace
mc init --full --force
```

**Output:**
Reports workspace root, mode, Motus directory, and current release pointer.

---

### mc config

Manage MC configuration settings.

**Synopsis:**
```bash
mc config show
mc config get <key>
mc config set <key> <value>
mc config reset
mc config path
```

**Subcommands:**
- `show` - Display current configuration as JSON
- `get <key>` - Get a single configuration value
- `set <key> <value>` - Set a configuration value
- `reset` - Reset configuration to defaults
- `path` - Show configuration file path

**Examples:**
```bash
# Show all configuration
mc config show

# Get specific value
mc config get motus_enabled

# Set value
mc config set motus_enabled true

# Reset to defaults
mc config reset

# Show config file location
mc config path
```

---

### mc harness

Detect test harness commands for the current repository.

**Synopsis:**
```bash
mc harness [--save]
```

**Options:**
- `--save` - Save detected harness to .mc/harness.json

**Examples:**
```bash
# Detect test harness
mc harness

# Detect and save
mc harness --save
```

**Output:**
Displays detected commands for test, lint, build, and smoke test with confidence levels.

---

### mc intent

Extract and display intent from a session.

**Synopsis:**
```bash
mc intent <session_id> [--save]
```

**Arguments:**
- `session_id` - Session ID to analyze

**Options:**
- `--save` - Save intent to .mc/intent.yaml

**Examples:**
```bash
# Extract intent
mc intent abc123

# Extract and save
mc intent abc123 --save
```

---

### mc mcp

Start MCP (Model Context Protocol) server using stdio transport.

**Synopsis:**
```bash
mc mcp
```

**Examples:**
```bash
# Start MCP server
mc mcp
```

**Behavior:**
Starts an MCP server that communicates via stdin/stdout, suitable for integration with MCP-compatible tools.

---

## Advanced Commands

### mc orient

Lookup a cached decision using the Cached Orient system.

**Synopsis:**
```bash
mc orient <decision_type> --context CONTEXT [OPTIONS]
mc orient stats [OPTIONS]
```

**Arguments:**
- `decision_type` - Decision type to lookup (e.g., "color_palette") or "stats" for analytics

**Options:**
- `--context DATA` - Context as JSON/YAML string, file path, or '-' for stdin (required)
- `--constraints DATA` - Optional constraints as JSON/YAML string, file path, or '-' for stdin
- `--registry PATH` - Decision type registry path (default: .motus/config/decision_types.yaml)
- `--explain` - Include match trace / debugging details in output
- `--rebuild-index` - Rebuild the standards index before lookup
- `--json` - Emit machine-readable JSON

**Stats Options:**
- `--high-miss` - Show top 5 decision types with lowest hit rate
- `--min-calls N` - Minimum calls to include (default: 1)
- `--stats-path PATH` - Override events.jsonl path

**Examples:**
```bash
# Lookup decision with inline context
mc orient color_palette --context '{"theme": "dark", "brand": "tech"}'

# Lookup with context from file
mc orient color_palette --context context.json

# Lookup with context from stdin
echo '{"theme": "dark"}' | mc orient color_palette --context -

# Lookup with constraints
mc orient color_palette --context ctx.json --constraints '{"max_colors": 5}'

# Explain decision
mc orient color_palette --context ctx.json --explain

# Show orient statistics
mc orient stats

# Show high-miss decision types
mc orient stats --high-miss

# Stats with minimum call threshold
mc orient stats --min-calls 10 --json
```

**Output:**
JSON output with result (HIT/MISS/CONFLICT), decision data, standard_id, and layer.

**Exit Codes:**
- `0` - Success (HIT or MISS)
- `2` - Conflict detected

---

### mc standards

Standards and proposal management utilities.

**Synopsis:**
```bash
mc standards validate <path> [OPTIONS]
mc standards propose --type TYPE --context CTX --output OUT [OPTIONS]
mc standards list-proposals [OPTIONS]
mc standards promote <proposal_id> --to LAYER [OPTIONS]
mc standards reject <proposal_id> --reason REASON [OPTIONS]
```

**Subcommands:**

#### validate
Validate a standard.yaml file against schema.

**Options:**
- `path` - Path to standard.yaml file (required)
- `--vault-dir PATH` - Vault root directory
- `--registry PATH` - Decision type registry path
- `--json` - Emit machine-readable JSON

**Example:**
```bash
mc standards validate /vault/user/standards/color_palette/std_001.yaml
mc standards validate std.yaml --json
```

#### propose
Create a proposal from a slow-path decision.

**Options:**
- `--type TYPE` - Decision type (required)
- `--context DATA` - Context as JSON/YAML string, file, or '-' (required)
- `--output DATA` - Output decision as JSON/YAML string, file, or '-' (required)
- `--why TEXT` - Why this proposal should be promoted
- `--by ID` - Agent or user ID creating the proposal
- `--json` - Emit machine-readable JSON

**Example:**
```bash
mc standards propose \
  --type color_palette \
  --context '{"theme": "dark"}' \
  --output '{"primary": "#007acc"}' \
  --why "Standard dark theme palette" \
  --by agent-123
```

#### list-proposals
List cached proposals.

**Options:**
- `--type TYPE` - Filter by decision type
- `--status STATUS` - Filter by status: pending, approved, rejected
- `--json` - Emit machine-readable JSON

**Example:**
```bash
mc standards list-proposals
mc standards list-proposals --type color_palette --status pending
```

#### promote
Promote a proposal to an active standard.

**Options:**
- `proposal_id` - Proposal ID to promote (required)
- `--to LAYER` - Target layer: user, project (required; system is immutable)
- `--json` - Emit machine-readable JSON

**Example:**
```bash
mc standards promote prop_abc123 --to user
mc standards promote prop_abc123 --to project --json
```

#### reject
Reject a proposal.

**Options:**
- `proposal_id` - Proposal ID to reject (required)
- `--reason TEXT` - Rejection reason (required)
- `--json` - Emit machine-readable JSON

**Example:**
```bash
mc standards reject prop_abc123 --reason "Conflicts with existing palette"
```

**Exit Codes:**
- `0` - Success
- `1` - Operation failed
- `2` - Invalid arguments

---

### mc claims

Coordination claim registry for multi-agent resource locking.

**Synopsis:**
```bash
mc claims acquire --namespace NS --resource RES [OPTIONS]
mc claims list [OPTIONS]
```

**Subcommands:**

#### acquire
Acquire a claim on a resource.

**Options:**
- `--namespace NS` - Claim namespace (required)
- `--resource RES` - Resource ID/path to claim (required)
- `--agent ID` - Agent ID (or set MC_AGENT_ID)
- `--task-id ID` - Task ID (default: resource)
- `--task-type TYPE` - Task type (default: CR)
- `--registry-dir PATH` - Override claim registry directory
- `--acl PATH` - Namespace ACL YAML path
- `--lease-seconds N` - Lease duration in seconds
- `--json` - Emit machine-readable JSON

**Example:**
```bash
# Acquire claim
mc claims acquire \
  --namespace codebase \
  --resource src/main.py \
  --agent agent-001

# With custom lease
mc claims acquire \
  --namespace codebase \
  --resource src/main.py \
  --agent agent-001 \
  --lease-seconds 3600
```

#### list
List active claims.

**Options:**
- `--agent ID` - Agent ID (or set MC_AGENT_ID)
- `--namespace NS` - Filter to one namespace (authorization required)
- `--all-namespaces` - List across all namespaces (global admins only)
- `--registry-dir PATH` - Override claim registry directory
- `--acl PATH` - Namespace ACL YAML path
- `--json` - Emit machine-readable JSON

**Example:**
```bash
# List all claims
mc claims list --agent agent-001

# List for specific namespace
mc claims list --agent agent-001 --namespace codebase

# JSON output
mc claims list --agent agent-001 --json
```

**Exit Codes:**
- `0` - Success
- `1` - Claim conflict or operation failed
- `2` - Invalid arguments

---

## Checkpoint Commands

### mc checkpoint

Create a state checkpoint for later rollback.

**Synopsis:**
```bash
mc checkpoint <label>
```

**Arguments:**
- `label` - Descriptive label for the checkpoint

**Examples:**
```bash
# Create checkpoint before major change
mc checkpoint "before-refactor"

# Create checkpoint with timestamp
mc checkpoint "feature-complete-$(date +%Y%m%d)"
```

---

### mc checkpoints

List all available checkpoints.

**Synopsis:**
```bash
mc checkpoints
```

**Examples:**
```bash
# List all checkpoints
mc checkpoints
```

---

### mc rollback

Restore state to a previous checkpoint.

**Synopsis:**
```bash
mc rollback <checkpoint_id>
```

**Arguments:**
- `checkpoint_id` - Checkpoint ID to roll back to

**Examples:**
```bash
# Rollback to checkpoint
mc rollback chk_abc123
```

---

### mc diff

Show changes between current state and a checkpoint.

**Synopsis:**
```bash
mc diff <checkpoint_id>
```

**Arguments:**
- `checkpoint_id` - Checkpoint ID to diff against

**Examples:**
```bash
# Show changes since checkpoint
mc diff chk_abc123
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MC_HELP_TIER` | Visible help tier override (0-3) | Auto-detected |
| `MC_VAULT_DIR` | Vault root directory | None |
| `MC_PROFILE` | Policy profile ID | "personal" |
| `MC_EVIDENCE_DIR` | Evidence output directory | `.mc/evidence` |
| `MC_AGENT_ID` | Agent ID for claims | None |
| `MC_NAMESPACE_ACL` | Namespace ACL config path | `.motus/project/config/namespace-acl.yaml` |
| `MC_USE_SQLITE` | Use SQLite for sessions (1=yes, 0=no) | "1" |

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Operational error (session not found, gate failed, etc.) |
| `2` | Invalid arguments or usage error |

## Configuration

MC stores configuration in `~/.mc/config.yaml`. Use `mc config` to manage settings:

```bash
# View current config
mc config show

# Enable Motus
mc config set motus_enabled true

# Set protocol enforcement
mc config set protocol_enforcement strict

# Reset to defaults
mc config reset
```

## Tips

1. **Session IDs**: Most commands support prefix matching, so you can use just the first few characters: `mc watch abc` instead of `mc watch abc123def456`

2. **Fast Listing**: Use `mc list --fast` when you just need session IDs without process detection

3. **Policy Gates**: Always run `mc policy plan` before `mc policy run` to preview which gates will execute

4. **Error Analysis**: Use `mc errors --last 5` to quickly spot patterns across recent sessions

5. **Real-time Monitoring**: `mc watch` is great for debugging; `mc web` is better for multi-session overview

6. **Evidence Verification**: Policy evidence bundles are cryptographically signed and can be verified offline with `mc policy verify`
