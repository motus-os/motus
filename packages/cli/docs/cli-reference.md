# CLI Reference

## Overview

Motus (`motus`) provides a comprehensive CLI for monitoring AI agent sessions, enforcing policy gates, and managing workspace state.

See also: [Userland Contract](standards/userland-contract.md) (workspace layout + registries).

```bash
motus [COMMAND] [OPTIONS]
```

## Quick Start

```bash
motus web                # Launch web dashboard at http://127.0.0.1:4000
motus list               # List recent sessions
motus watch              # Watch active session in real-time
motus policy plan --files src/main.py  # Plan policy gates for a file
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
| `config` | Manage Motus configuration |
| `db` | Database maintenance utilities |
| `diff` | Show changes between current state and a checkpoint |
| `errors` | Summarize errors from a session |
| `explain` | Explain a policy run decision trace |
| `history` | Show command history |
| `intent` | Extract/show intent from a session |
| `modules` | List registered Motus modules |
| `policy` | Plan and run Vault OS policy gates (proof of compliance) |
| `rollback` | Restore state to a previous checkpoint |
| `scratch` | Manage scratch entries and promotions |
| `teleport` | Export a session bundle for cross-session context transfer |

### Tier 3 (Advanced)

| Command | Description |
|---------|-------------|
| `claims` | Coordination claim registry |
| `harness` | Detect test harness for a repository |
| `init` | Initialize a Motus workspace (.motus/) |
| `mcp` | Start MCP server (stdio transport) |
| `gates` | Release gate registry utilities |
| `orient` | Lookup a cached decision (Cached Orient) |
| `standards` | Standards (Cached Orient) utilities |
| `summary` | Generate a rich summary for CLAUDE.md injection |

---

## Scratch Commands

Scratch entries are stored under `.motus/scratch/` and can be promoted to the roadmap.

### motus scratch add

```bash
motus scratch add --title "Idea" --body "Capture quick thought"
```

### motus scratch list

```bash
motus scratch list
```

### motus scratch show

```bash
motus scratch show SCR-2026-01-06-001
```

### motus scratch promote

```bash
motus scratch promote SCR-2026-01-06-001 --phase phase_h --item-type work
```

### motus scratch rebuild-index

```bash
motus scratch rebuild-index
```

## Database Commands

### motus db migrate-path

Migrate legacy `.mc` directories to `.motus`.

**Synopsis:**
```bash
motus db migrate-path [--dry-run] [--force] [--remove-legacy] [--global-only|--workspace-only]
```

**Examples:**
```bash
# Preview migration
motus db migrate-path --dry-run

# Migrate and remove legacy path after verification
motus db migrate-path --force --remove-legacy
```

Other DB utilities:

- `motus db vacuum`
- `motus db analyze`
- `motus db stats --json`
- `motus db checkpoint`
- `motus db lock-info --json`
- `motus db wait --max-seconds 30`
- `motus db recover`

## Session Commands

### motus list

List recent AI agent sessions from all sources (Claude, Codex, Gemini, SDK).

**Synopsis:**
```bash
motus list [--fast]
```

**Options:**
- `--fast, --no-process-detect` - Skip process detection for faster listing

**Examples:**
```bash
# List sessions from the last 24 hours
motus list

# Fast listing without process detection
motus list --fast
```

**Output:**
Displays a table with status, source, project, session ID, age, size, and last action for each session.

---

### motus watch

Watch an AI agent session in real-time, showing events as they occur.

**Synopsis:**
```bash
motus watch [session_id]
```

**Arguments:**
- `session_id` - Session ID to watch (optional, uses most recent if omitted)

**Options:**
- `-h, --help` - Show help message

**Examples:**
```bash
# Watch the most recent active session
motus watch

# Watch a specific session (prefix match supported)
motus watch abc123

# Exit watching with Ctrl+C
```

**Behavior:**
- Shows last 8 events from session history
- Polls for new events every 300ms
- Displays activity status every 10 polls
- Press Ctrl+C to exit and see session summary

---

### motus show

Show detailed information for a specific session.

**Synopsis:**
```bash
motus show <session_id>
```

**Arguments:**
- `session_id` - Session ID (prefix match supported)

**Examples:**
```bash
# Show session details
motus show abc123

# Works with partial session ID
motus show abc
```

**Output:**
Displays session metadata including session ID, file path, status, source, project path, and last action.

**Exit Codes:**
- `0` - Success
- `1` - Session not found

---

### motus feed

Show recent events for a session (like a log tail).

**Synopsis:**
```bash
motus feed <session_id> [--tail-lines N]
```

**Arguments:**
- `session_id` - Session ID (prefix match supported)

**Options:**
- `--tail-lines N` - Number of transcript lines to read from end (default: 200, range: 10-5000)

**Examples:**
```bash
# Show last 200 lines of events
motus feed abc123

# Show last 500 lines
motus feed abc123 --tail-lines 500
```

**Output:**
Prints timestamped events in chronological order with format: `HH:MM:SS [event_type] content`

**Exit Codes:**
- `0` - Success
- `1` - Session not found

---

### motus sync

Sync session transcripts into SQLite cache for faster access.

**Synopsis:**
```bash
motus sync [--full] [--max-age-hours N]
```

**Options:**
- `--full` - Full sync: scan and ingest all session files
- `--max-age-hours N` - Incremental sync limited to files modified within this window

**Examples:**
```bash
# Incremental sync (default)
motus sync --full

# Sync only sessions modified in last 24 hours
motus sync --max-age-hours 24

# Full sync of all sessions
motus sync --full
```

**Output:**
Reports number of sessions ingested, files seen, unchanged, partial, corrupted, and skipped, plus duration.

**Exit Codes:**
- `0` - Success
- `1` - Sync failed

---

### motus context

Generate context summary for AI agent prompts from the most recent or specified session.

**Synopsis:**
```bash
motus context [session_id]
```

**Arguments:**
- `session_id` - Session ID (optional, uses most recent if omitted)

**Examples:**
```bash
# Generate context for most recent session
motus context

# Generate context for specific session
motus context abc123
```

**Output:**
Displays a markdown panel with session context suitable for AI agent consumption.

---

### motus summary

Generate a rich summary for CLAUDE.md context injection.

**Synopsis:**
```bash
motus summary [session_id]
```

**Arguments:**
- `session_id` - Session ID to summarize (optional, uses most recent if omitted)

**Examples:**
```bash
# Summarize most recent session
motus summary

# Summarize specific session
motus summary abc123
```

**Output:**
Generates a comprehensive markdown summary of the session including decisions, tools used, and key events.

---

### motus history

Show command history and recent events across all sessions.

**Synopsis:**
```bash
motus history
```

**Examples:**
```bash
# Show recent activity across all sessions
motus history
```

**Output:**
Displays a table of the 30 most recent events from the last 48 hours, showing time, session, source, event type, and details.

---

### motus teleport

Export a session bundle for cross-session context transfer.

**Synopsis:**
```bash
motus teleport <session_id> [--no-docs] [-o OUTPUT]
```

**Arguments:**
- `session_id` - Session ID to export

**Options:**
- `--no-docs` - Exclude planning docs (ROADMAP, ARCHITECTURE, etc.) from bundle
- `-o, --output FILE` - Output file path (default: stdout as JSON)

**Examples:**
```bash
# Export session to JSON (stdout)
motus teleport abc123

# Export to file
motus teleport abc123 -o session-bundle.json

# Export without planning docs
motus teleport abc123 --no-docs -o bundle.json
```

**Output:**
JSON bundle containing session context, events, and relevant documentation.

---

## Web Dashboard

### motus web

Launch interactive web dashboard at http://127.0.0.1:4000

**Synopsis:**
```bash
motus web
```

**Examples:**
```bash
# Launch web dashboard
motus web
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

### motus policy plan

Compute and print a deterministic gate plan for changed files.

**Synopsis:**
```bash
motus policy plan --files FILE... [OPTIONS]
motus policy plan --git-diff BASE HEAD [OPTIONS]
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
motus policy plan --files src/main.py src/utils.py

# Plan using git diff
motus policy plan --git-diff main HEAD

# Plan with specific vault and profile
motus policy plan --files src/main.py --vault-dir ~/vault --profile team
```

**Output:**
Displays the gate plan showing which gates will run, their tier, and pack assignments. Creates trace files in `.motus/traces/`.

---

### motus policy run

Execute required gates and emit an evidence bundle.

**Synopsis:**
```bash
motus policy run --files FILE... [OPTIONS]
motus policy run --git-diff BASE HEAD [OPTIONS]
```

**Options:**
- `--files FILE...` - Explicit changed files (repo-relative preferred)
- `--git-diff BASE HEAD` - Compute changed files via git diff
- `--vault-dir PATH` - Vault root directory (or set MC_VAULT_DIR)
- `--profile ID` - Profile ID (or set MC_PROFILE; default: personal)
- `--repo PATH` - Repository root (default: current directory)
- `--pack-cap N` - Override profile pack cap
- `--evidence-dir PATH` - Evidence root (default: .motus/evidence or MC_EVIDENCE_DIR)
- `--json` - Emit machine-readable JSON

**Examples:**
```bash
# Run gates for specific files
motus policy run --files src/main.py

# Run gates using git diff
motus policy run --git-diff main HEAD

# Run with custom evidence directory
motus policy run --files src/main.py --evidence-dir /tmp/evidence
```

**Output:**
Executes gates and creates an evidence bundle with manifest.json, summary.txt, and HMAC signature.

**Exit Codes:**
- `0` - All gates passed
- `1` - One or more gates failed

---

### motus policy verify

Verify an evidence bundle's cryptographic integrity.

**Synopsis:**
```bash
motus policy verify --evidence PATH [OPTIONS]
```

**Options:**
- `--evidence PATH` - Evidence run directory containing manifest.json (required)
- `--vault-dir PATH` - Vault root directory (or set MC_VAULT_DIR)
- `--json` - Emit machine-readable JSON

**Examples:**
```bash
# Verify evidence bundle
motus policy verify --evidence .motus/evidence/run_abc123

# Verify with JSON output
motus policy verify --evidence .motus/evidence/run_abc123 --json
```

**Output:**
Reports verification status (PASS/FAIL), reason codes, and any validation messages.

**Exit Codes:**
- `0` - Verification passed
- `1` - Verification failed

---

### motus policy prune

Prune old evidence bundles to reclaim disk space.

**Synopsis:**
```bash
motus policy prune [--keep N] [--older-than DAYS] [--dry-run]
```

**Options:**
- `--keep N` - Keep the N most recent bundles (default: 10)
- `--older-than DAYS` - Delete bundles older than DAYS
- `--repo PATH` - Repository root (default: current directory)
- `--evidence-dir PATH` - Evidence root (default: .motus/evidence or MC_EVIDENCE_DIR)
- `--dry-run` - Show what would be deleted without deleting

**Examples:**
```bash
# Preview what would be deleted
motus policy prune --dry-run

# Keep 5 most recent, delete rest
motus policy prune --keep 5

# Delete bundles older than 30 days
motus policy prune --older-than 30

# Combine: keep 10 most recent AND delete those older than 90 days
motus policy prune --keep 10 --older-than 90
```

**Output:**
Reports bundles found, kept, deleted, and bytes reclaimed.

**Exit Codes:**
- `0` - Success

---

## Error Analysis

### motus errors

Summarize errors from one or more sessions.

**Synopsis:**
```bash
motus errors [session_id] [OPTIONS]
motus errors --last N [OPTIONS]
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
motus errors

# Summarize errors from specific session
motus errors abc123

# Summarize errors from last 5 sessions
motus errors --last 5

# Show only API errors
motus errors abc123 --category api

# JSON output for last 3 sessions
motus errors --last 3 --json
```

**Output:**
Groups errors by category and displays error counts, types, and sample messages.

**Exit Codes:**
- `0` - Success
- `1` - Session not found or other error
- `2` - Invalid arguments

---

### motus explain

Explain a policy run decision trace showing the timeline of gate executions.

**Synopsis:**
```bash
motus explain <run_id> [--repo PATH]
```

**Arguments:**
- `run_id` - Policy run ID (evidence directory name)

**Options:**
- `--repo PATH` - Repository root (default: current working directory)

**Examples:**
```bash
# Explain policy run
motus explain run_abc123

# Explain from different repo
motus explain run_abc123 --repo /path/to/repo
```

**Output:**
Displays a timeline table showing each gate step, status, reason codes, and evidence references. Highlights the first failing gate if any.

**Exit Codes:**
- `0` - Success
- `1` - Decision trace not found or empty
- `2` - Invalid arguments

---

## System Commands

### motus doctor

Run health checks on the Motus installation and database.

**Synopsis:**
```bash
motus doctor [--json]
```

**Options:**
- `--json` - Emit machine-readable JSON

**Examples:**
```bash
# Run health checks
motus doctor

# JSON output
motus doctor --json
```

**Output:**
Reports status of database, WAL size, and other health metrics.

**Exit Codes:**
- `0` - All checks passed
- `1` - One or more checks failed

---

### motus install

Install agent onboarding defaults and enable protocol enforcement.

**Synopsis:**
```bash
motus install
```

**Examples:**
```bash
# Install agent onboarding
motus install
```

**Output:**
Displays vault pointers, protocol summary, and updates configuration to enable Motus with strict protocol enforcement.

---

### motus init

Initialize a Motus workspace with `.motus/` directory structure.

**Synopsis:**
```bash
motus init --full [--path PATH] [--force]
motus init --lite [--path PATH] [--force]
motus init --integrate PATH [--force]
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
motus init --full

# Initialize in specific directory
motus init --full --path ~/projects/myapp

# Minimal workspace
motus init --lite

# Integrate with existing workspace
motus init --integrate ~/projects/existing

# Repair existing workspace
motus init --full --force
```

**Output:**
Reports workspace root, mode, Motus directory, and current release pointer.

---

### motus modules

List modules from the canonical module registry.

**Synopsis:**
```bash
motus modules list [--registry PATH] [--json]
```

**Options:**
- `--registry PATH` - Override registry path (default: packages/cli/docs/standards/module-registry.yaml)
- `--json` - Emit JSON instead of a table

**Examples:**
```bash
# List modules (table)
motus modules list

# List modules as JSON
motus modules list --json
```

**Output:**
Shows module id, name, status, and target release (version).

---

### motus gates

List or inspect gates from the canonical release gate registry.

**Synopsis:**
```bash
motus gates list [--registry PATH] [--json]
motus gates show <gate-id> [--registry PATH] [--json]
```

**Options:**
- `--registry PATH` - Override registry path (default: packages/cli/docs/standards/gates.yaml)
- `--json` - Emit JSON instead of a table

**Examples:**
```bash
# List gates
motus gates list

# Show one gate
motus gates show GATE-CLI-001
```

**Output:**
Shows gate id, tier, kind, and command.

---

### motus config

Manage Motus configuration settings.

**Synopsis:**
```bash
motus config show
motus config get <key>
motus config set <key> <value>
motus config reset
motus config path
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
motus config show

# Get specific value
motus config get motus_enabled

# Set value
motus config set motus_enabled true

# Reset to defaults
motus config reset

# Show config file location
motus config path
```

---

### motus harness

Detect test harness commands for the current repository.

**Synopsis:**
```bash
motus harness [--save]
```

**Options:**
- `--save` - Save detected harness to .motus/harness.json

**Examples:**
```bash
# Detect test harness
motus harness

# Detect and save
motus harness --save
```

**Output:**
Displays detected commands for test, lint, build, and smoke test with confidence levels.

---

### motus intent

Extract and display intent from a session.

**Synopsis:**
```bash
motus intent <session_id> [--save]
```

**Arguments:**
- `session_id` - Session ID to analyze

**Options:**
- `--save` - Save intent to .motus/intent.yaml

**Examples:**
```bash
# Extract intent
motus intent abc123

# Extract and save
motus intent abc123 --save
```

---

### motus mcp

Start MCP (Model Context Protocol) server using stdio transport.

**Synopsis:**
```bash
motus mcp
```

**Examples:**
```bash
# Start MCP server
motus mcp
```

**Behavior:**
Starts an MCP server that communicates via stdin/stdout, suitable for integration with MCP-compatible tools.

---

## Advanced Commands

### motus orient

Lookup a cached decision using the Cached Orient system.

**Synopsis:**
```bash
motus orient <decision_type> --context CONTEXT [OPTIONS]
motus orient stats [OPTIONS]
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
motus orient color_palette --context '{"theme": "dark", "brand": "tech"}'

# Lookup with context from file
motus orient color_palette --context context.json

# Lookup with context from stdin
echo '{"theme": "dark"}' | motus orient color_palette --context -

# Lookup with constraints
motus orient color_palette --context ctx.json --constraints '{"max_colors": 5}'

# Explain decision
motus orient color_palette --context ctx.json --explain

# Show orient statistics
motus orient stats

# Show high-miss decision types
motus orient stats --high-miss

# Stats with minimum call threshold
motus orient stats --min-calls 10 --json
```

**Output:**
JSON output with result (HIT/MISS/CONFLICT), decision data, standard_id, and layer.

**Exit Codes:**
- `0` - Success (HIT or MISS)
- `2` - Conflict detected

---

### motus standards

Standards and proposal management utilities.

**Synopsis:**
```bash
motus standards validate <path> [OPTIONS]
motus standards propose --type TYPE --context CTX --output OUT [OPTIONS]
motus standards list-proposals [OPTIONS]
motus standards promote <proposal_id> --to LAYER [OPTIONS]
motus standards reject <proposal_id> --reason REASON [OPTIONS]
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
motus standards validate /vault/user/standards/color_palette/std_001.yaml
motus standards validate std.yaml --json
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
motus standards propose \
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
motus standards list-proposals
motus standards list-proposals --type color_palette --status pending
```

#### promote
Promote a proposal to an active standard.

**Options:**
- `proposal_id` - Proposal ID to promote (required)
- `--to LAYER` - Target layer: user, project (required; system is immutable)
- `--json` - Emit machine-readable JSON

**Example:**
```bash
motus standards promote prop_abc123 --to user
motus standards promote prop_abc123 --to project --json
```

#### reject
Reject a proposal.

**Options:**
- `proposal_id` - Proposal ID to reject (required)
- `--reason TEXT` - Rejection reason (required)
- `--json` - Emit machine-readable JSON

**Example:**
```bash
motus standards reject prop_abc123 --reason "Conflicts with existing palette"
```

**Exit Codes:**
- `0` - Success
- `1` - Operation failed
- `2` - Invalid arguments

---

### motus claims

Coordination claim registry for multi-agent resource locking.

**Synopsis:**
```bash
motus claims acquire --namespace NS --resource RES [OPTIONS]
motus claims list [OPTIONS]
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
motus claims acquire \
  --namespace codebase \
  --resource src/main.py \
  --agent agent-001

# With custom lease
motus claims acquire \
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
motus claims list --agent agent-001

# List for specific namespace
motus claims list --agent agent-001 --namespace codebase

# JSON output
motus claims list --agent agent-001 --json
```

**Exit Codes:**
- `0` - Success
- `1` - Claim conflict or operation failed
- `2` - Invalid arguments

---

## Checkpoint Commands

### motus checkpoint

Create a state checkpoint for later rollback.

**Synopsis:**
```bash
motus checkpoint <label>
```

**Arguments:**
- `label` - Descriptive label for the checkpoint

**Examples:**
```bash
# Create checkpoint before major change
motus checkpoint "before-refactor"

# Create checkpoint with timestamp
motus checkpoint "feature-complete-$(date +%Y%m%d)"
```

---

### motus checkpoints

List all available checkpoints.

**Synopsis:**
```bash
motus checkpoints
```

**Examples:**
```bash
# List all checkpoints
motus checkpoints
```

---

### motus rollback

Restore state to a previous checkpoint.

**Synopsis:**
```bash
motus rollback <checkpoint_id>
```

**Arguments:**
- `checkpoint_id` - Checkpoint ID to roll back to

**Examples:**
```bash
# Rollback to checkpoint
motus rollback chk_abc123
```

---

### motus diff

Show changes between current state and a checkpoint.

**Synopsis:**
```bash
motus diff <checkpoint_id>
```

**Arguments:**
- `checkpoint_id` - Checkpoint ID to diff against

**Examples:**
```bash
# Show changes since checkpoint
motus diff chk_abc123
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MC_HELP_TIER` | Visible help tier override (0-3) | Auto-detected |
| `MC_VAULT_DIR` | Vault root directory | None |
| `MC_PROFILE` | Policy profile ID | "personal" |
| `MC_EVIDENCE_DIR` | Evidence output directory | `.motus/evidence` |
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

Motus stores configuration in `~/.motus/config.json`. Use `motus config` to manage settings:

```bash
# View current config
motus config show

# Enable Motus
motus config set motus_enabled true

# Set protocol enforcement
motus config set protocol_enforcement strict

# Reset to defaults
motus config reset
```

## Tips

1. **Session IDs**: Most commands support prefix matching, so you can use just the first few characters: `motus watch abc` instead of `motus watch abc123def456`

2. **Fast Listing**: Use `motus list --fast` when you just need session IDs without process detection

3. **Policy Gates**: Always run `motus policy plan` before `motus policy run` to preview which gates will execute

4. **Error Analysis**: Use `motus errors --last 5` to quickly spot patterns across recent sessions

5. **Real-time Monitoring**: `motus watch` is great for debugging; `motus web` is better for multi-session overview

6. **Evidence Verification**: Policy evidence bundles are cryptographically signed and can be verified offline with `motus policy verify`
