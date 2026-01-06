#!/bin/bash
# GATE-SEC-002: Secrets Scan
# Reference: .ai/RELEASE-STANDARD.md
# Purpose: Detect accidentally committed secrets before release
# Security: Fail-closed - missing baseline or tool = blocked release
set -e

echo "GATE-SEC-002: Secrets Scan"
echo "=========================="

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="${REPO_ROOT:-${MOTUS_REPO_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}}"
cd "$REPO_ROOT"

# Check for scanning tools (prefer detect-secrets, fall back to gitleaks)
SCANNER=""
if command -v detect-secrets >/dev/null 2>&1; then
  SCANNER="detect-secrets"
elif command -v gitleaks >/dev/null 2>&1; then
  SCANNER="gitleaks"
else
  echo "FAIL: No secrets scanner found"
  echo ""
  echo "Install one of:"
  echo "  pip install detect-secrets"
  echo "  brew install gitleaks"
  exit 1
fi

echo "Scanner: $SCANNER"

if [ "$SCANNER" = "detect-secrets" ]; then
  BASELINE="${DETECT_SECRETS_BASELINE:-.secrets.baseline}"

  # If baseline exists, audit against it
  if [ -f "$BASELINE" ]; then
    echo "Auditing against baseline: $BASELINE"
    if detect-secrets scan --baseline "$BASELINE" 2>&1 | grep -q "potential secrets"; then
      echo ""
      echo "FAIL: New secrets detected"
      echo ""
      echo "Review with: detect-secrets audit $BASELINE"
      echo "If false positive, update baseline with:"
      echo "  detect-secrets scan --baseline $BASELINE"
      exit 1
    fi
    echo "No new secrets found"
  else
    # No baseline - full scan
    echo "No baseline found, running full scan..."
    results=$(detect-secrets scan 2>&1)

    # Check if any secrets found (results will have "results" key with findings)
    if echo "$results" | python3 -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if not d.get('results') else 1)" 2>/dev/null; then
      echo "No secrets found"
      echo ""
      echo "WARN: Consider creating baseline for future scans:"
      echo "  detect-secrets scan > $BASELINE"
    else
      echo ""
      echo "FAIL: Potential secrets found"
      echo "$results" | python3 -c "import json,sys; d=json.load(sys.stdin); print(json.dumps(d.get('results',{}), indent=2))" 2>/dev/null || echo "$results"
      echo ""
      echo "Review each finding. If false positive, add to baseline:"
      echo "  detect-secrets scan > $BASELINE"
      echo "  detect-secrets audit $BASELINE"
      exit 1
    fi
  fi

elif [ "$SCANNER" = "gitleaks" ]; then
  echo "Running gitleaks scan..."

  # Run gitleaks, capture exit code
  if gitleaks detect --source "$REPO_ROOT" --no-git 2>&1; then
    echo "No secrets found"
  else
    echo ""
    echo "FAIL: Secrets detected by gitleaks"
    echo ""
    echo "Review findings above. If false positive, add to .gitleaksignore"
    exit 1
  fi
fi

echo ""
echo "PASS: Secrets scan complete"
exit 0
