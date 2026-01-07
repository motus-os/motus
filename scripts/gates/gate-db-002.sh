#!/bin/bash
# GATE-DB-002: DB lock health check
# Reference: .ai/RELEASE-STANDARD.md
# Purpose: Fail release if a stale DB lock or oversized WAL is detected
set -e

echo "GATE-DB-002: DB Lock Health"
echo "============================"

LOCK_FILE="${HOME:?HOME must be set}/.motus/state/locks/db_lock.json"
DB_PATH="${HOME:?HOME must be set}/.motus/coordination.db"
MAX_LOCK_AGE_SECONDS="${MOTUS_DB_LOCK_MAX_AGE_SECONDS:-120}"
MAX_WAL_BYTES="${MOTUS_WAL_MAX_BYTES:-104857600}"

if [ ! -f "$LOCK_FILE" ]; then
  echo "PASS: No lock registry file"
else
  lock_age=$(python3 - "$LOCK_FILE" <<'PY'
import json
import sys
from datetime import datetime, timezone

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as f:
    payload = json.load(f)
started_at = payload.get("started_at")
if not started_at:
    sys.exit(2)
raw = started_at.replace("Z", "+00:00")
dt = datetime.fromisoformat(raw)
age = (datetime.now(timezone.utc) - dt).total_seconds()
print(int(age))
PY
  ) || {
    echo "FAIL: Unable to parse lock registry file"
    exit 1
  }

  if [ "$lock_age" -gt "$MAX_LOCK_AGE_SECONDS" ]; then
    echo "FAIL: Stale DB lock detected (age ${lock_age}s > ${MAX_LOCK_AGE_SECONDS}s)"
    exit 1
  fi
  echo "PASS: Lock registry age ${lock_age}s"
fi

if [ -f "${DB_PATH}-wal" ]; then
  wal_bytes=$(python3 - "${DB_PATH}-wal" <<'PY'
import os
import sys
path = sys.argv[1]
print(os.stat(path).st_size)
PY
  )
  if [ "$wal_bytes" -gt "$MAX_WAL_BYTES" ]; then
    echo "FAIL: WAL size ${wal_bytes} bytes > ${MAX_WAL_BYTES} bytes"
    exit 1
  fi
  echo "PASS: WAL size ${wal_bytes} bytes"
else
  echo "PASS: WAL file not present"
fi

exit 0
