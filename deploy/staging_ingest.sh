#!/usr/bin/env bash
# Hourly staging run on the VPS, started by cron: processes the raw rows that
# arrived since the last run via staging.ingest_snapshots() and prints one log
# line "<time> accepted rejected watermark_from watermark_to".
# If the previous run is still going, this one exits without doing anything.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCK_FILE="${LOCK_FILE:-/tmp/flights_staging_ingest.lock}"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    echo "$(date -u '+%Y-%m-%d %H:%M:%S UTC')  previous run still active, skipped"
    exit 0
fi

cd "$REPO_DIR"
RESULT="$(docker compose exec -T postgres psql -U flights -d flights \
    -v ON_ERROR_STOP=1 -At -F ' ' \
    -c "SELECT accepted, rejected, watermark_from, watermark_to FROM staging.ingest_snapshots();")"

echo "$(date -u '+%Y-%m-%d %H:%M:%S UTC')  $RESULT"
