#!/bin/bash
# Optional helper for running canvas-grabber on a schedule (e.g. via cron).
# It just runs the normal pipeline and logs failures to ./sync-errors.log.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

LOG="$SCRIPT_DIR/sync-errors.log"

echo "$(date): Starting canvas sync..."

# .env is loaded by the npm scripts themselves via --env-file-if-exists.
if ! npm run auth; then
  echo "$(date): Auth failed — check .env credentials or Canvas login flow" >> "$LOG"
  exit 1
fi

if ! npm run grab; then
  echo "$(date): grab failed after successful auth" >> "$LOG"
  exit 1
fi

if ! npm run parse; then
  echo "$(date): parse failed" >> "$LOG"
  exit 1
fi

echo "$(date): Canvas sync complete."
