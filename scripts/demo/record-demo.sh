#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DEMO_DIR="$(mktemp -d)"

cleanup() {
  rm -rf "$DEMO_DIR"
}
trap cleanup EXIT

export MOTUS_DEMO_DIR="$DEMO_DIR"
export PYTHONPATH="$REPO_ROOT/packages/cli/src"
export MC_DB_PATH="$DEMO_DIR/.motus/coordination.db"
export MC_CONTEXT_CACHE_DB_PATH="$DEMO_DIR/.motus/context_cache.db"
export MC_EVIDENCE_DIR="$DEMO_DIR/.motus/state/ledger"

mkdir -p "$DEMO_DIR/bin"
cat <<'EOF' > "$DEMO_DIR/bin/motus"
#!/usr/bin/env bash
exec python3 -m motus.cli "$@"
EOF
chmod +x "$DEMO_DIR/bin/motus"
export PATH="$DEMO_DIR/bin:$PATH"

# Pre-initialize workspace so the demo only shows the core loop.
python3 -m motus.cli init --lite --path "$DEMO_DIR" >/dev/null

cd "$REPO_ROOT"

vhs "$REPO_ROOT/scripts/demo/demo.tape"

echo "Demo recorded to docs/assets/demo.gif"
