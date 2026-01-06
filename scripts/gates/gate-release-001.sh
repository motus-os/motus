#!/bin/bash
# GATE-RELEASE-001: Release Coordination Check
# Reference: .ai/RELEASE-STANDARD.md
# Purpose: Verify all release artifacts are in sync before publishing
# Security: Prevents version mismatches and incomplete releases
set -e

echo "GATE-RELEASE-001: Release Coordination Check"
echo "============================================="

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="${REPO_ROOT:-${MOTUS_REPO_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}}"

# Get version from argument or detect from code
VERSION="${1:-}"

# Verify required commands
for cmd in git python3 curl; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "FAIL: Required command '$cmd' not found"
    exit 1
  fi
done

echo ""
echo "=== Version Detection ==="

# Get version from code (pyproject.toml or __init__.py)
code_version=""
pyproject_paths=(
  "$REPO_ROOT/pyproject.toml"
  "$REPO_ROOT/packages/cli/pyproject.toml"
)

for pyproject in "${pyproject_paths[@]}"; do
  if [ -f "$pyproject" ]; then
    code_version=$(grep -E "^version\s*=" "$pyproject" 2>/dev/null | head -1 | sed 's/.*"\(.*\)".*/\1/' || echo "")
    if [ -n "$code_version" ]; then
      break
    fi
  fi
done

if [ -z "$code_version" ]; then
  # Try __init__.py
  init_paths=(
    "$REPO_ROOT/src/motus/__init__.py"
    "$REPO_ROOT/packages/cli/src/motus/__init__.py"
  )
  for init_file in "${init_paths[@]}"; do
    if [ -f "$init_file" ]; then
      code_version=$(grep -E "^__version__\s*=" "$init_file" 2>/dev/null | sed 's/.*"\(.*\)".*/\1/' || echo "")
      if [ -n "$code_version" ]; then
        break
      fi
    fi
  done
fi

if [ -z "$code_version" ]; then
  # Try motus --version
  code_version=$(motus --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "")
fi

echo "Code version: ${code_version:-UNKNOWN}"

# Use provided version or detected version
if [ -n "$VERSION" ]; then
  TARGET_VERSION="$VERSION"
  echo "Target version (provided): $TARGET_VERSION"
else
  TARGET_VERSION="$code_version"
  echo "Target version (from code): $TARGET_VERSION"
fi

if [ -z "$TARGET_VERSION" ]; then
  echo "FAIL: Cannot determine version"
  echo "  Provide version as argument: $0 X.Y.Z"
  exit 1
fi

# Track failures
failures=0

# Check 1: Git tag exists
echo ""
echo "=== Check 1: Git Tag ==="
git_tag="v$TARGET_VERSION"
if git rev-parse "$git_tag" >/dev/null 2>&1; then
  tag_sha=$(git rev-parse "$git_tag")
  echo "  [OK] Tag $git_tag exists (SHA: ${tag_sha:0:8})"
else
  echo "  [FAIL] Tag $git_tag does not exist"
  echo "         Create with: git tag -a $git_tag -m 'Release $git_tag'"
  failures=$((failures + 1))
fi

# Check 2: CHANGELOG entry exists
echo ""
echo "=== Check 2: CHANGELOG Entry ==="
changelog_files="CHANGELOG.md docs/CHANGELOG.md"
changelog_found=0

for f in $changelog_files; do
  if [ -f "$REPO_ROOT/$f" ]; then
    if grep -qE "^##.*$TARGET_VERSION|^\[$TARGET_VERSION\]" "$REPO_ROOT/$f" 2>/dev/null; then
      echo "  [OK] Version $TARGET_VERSION found in $f"
      changelog_found=1
      break
    fi
  fi
done

if [ $changelog_found -eq 0 ]; then
  echo "  [FAIL] No CHANGELOG entry for $TARGET_VERSION"
  echo "         Add entry to CHANGELOG.md before release"
  failures=$((failures + 1))
fi

# Check 3: PyPI version (if checking published release)
echo ""
echo "=== Check 3: PyPI Version ==="
pypi_version=$(curl -s "https://pypi.org/pypi/motusos/json" 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin).get('info',{}).get('version',''))" 2>/dev/null || echo "")

if [ -n "$pypi_version" ]; then
  echo "  PyPI latest: $pypi_version"
  if [ "$pypi_version" = "$TARGET_VERSION" ]; then
    echo "  [OK] PyPI version matches target"
  else
    echo "  [INFO] PyPI version differs (OK if not yet published)"
  fi
else
  echo "  [INFO] Package not on PyPI or not accessible"
fi

# Check 4: GitHub Release (if gh CLI available)
echo ""
echo "=== Check 4: GitHub Release ==="
if command -v gh >/dev/null 2>&1; then
  gh_release=$(gh release view "$git_tag" --json tagName -q '.tagName' 2>/dev/null || echo "")
  if [ "$gh_release" = "$git_tag" ]; then
    echo "  [OK] GitHub release $git_tag exists"
  else
    echo "  [INFO] GitHub release $git_tag not found (OK if not yet created)"
  fi
else
  echo "  [SKIP] gh CLI not available"
fi

# Check 5: Website messaging (if messaging.json exists)
echo ""
echo "=== Check 5: Website Version ==="
messaging_files="packages/website/src/data/messaging.json website/src/data/messaging.json"
website_checked=0

for f in $messaging_files; do
  if [ -f "$REPO_ROOT/$f" ]; then
    website_version=$(python3 -c "import json; print(json.load(open('$REPO_ROOT/$f')).get('version',''))" 2>/dev/null || echo "")
    if [ -n "$website_version" ]; then
      echo "  Website version: $website_version"
      if [ "$website_version" = "$TARGET_VERSION" ]; then
        echo "  [OK] Website version matches"
      else
        echo "  [WARN] Website version differs: $website_version vs $TARGET_VERSION"
      fi
      website_checked=1
      break
    fi
  fi
done

if [ $website_checked -eq 0 ]; then
  echo "  [SKIP] No messaging.json found"
fi

# Check 6: No uncommitted changes
echo ""
echo "=== Check 6: Working Directory ==="
if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
  echo "  [WARN] Uncommitted changes in working directory"
  git status --short | head -5
else
  echo "  [OK] Working directory clean"
fi

# Check 7: Tag points to HEAD (for new releases)
echo ""
echo "=== Check 7: Tag Alignment ==="
if git rev-parse "$git_tag" >/dev/null 2>&1; then
  tag_sha=$(git rev-parse "$git_tag")
  head_sha=$(git rev-parse HEAD)
  if [ "$tag_sha" = "$head_sha" ]; then
    echo "  [OK] Tag $git_tag points to HEAD"
  else
    echo "  [INFO] Tag $git_tag does not point to HEAD"
    echo "         Tag: ${tag_sha:0:8}"
    echo "         HEAD: ${head_sha:0:8}"
    echo "         (This is OK if verifying an older release)"
  fi
fi

# Final summary
echo ""
echo "============================================="
if [ $failures -gt 0 ]; then
  echo "FAIL: $failures coordination check(s) failed"
  echo ""
  echo "Release artifacts are not in sync."
  echo "Fix the issues above before publishing."
  exit 1
fi

echo "PASS: Release coordination verified"
echo "  Version: $TARGET_VERSION"
echo "  Tag: $git_tag"
echo "  All artifacts aligned"
exit 0
