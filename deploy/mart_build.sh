#!/usr/bin/env bash
# Hourly mart build chain, started by cron on the VPS. Replaces the standalone
# staging cron (deploy/staging_ingest.sh): it runs the staging ingest first, then the
# three mart fact loads in dependency order. Each step is its own transaction and is
# incremental and idempotent, so a missed run is caught up by the next one. flock keeps
# runs from overlapping; one log line is printed per step; the chain stops at the first
# failing step and alerts the webhook. Dimensions are loaded once by mart_dims.sh, not here.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCK_FILE="${LOCK_FILE:-/tmp/flights_mart_build.lock}"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    echo "$(date -u '+%Y-%m-%d %H:%M:%S UTC')  previous run still active, skipped"
    exit 0
fi

cd "$REPO_DIR"

# make .env values (ALERT_WEBHOOK_URL) available when started from cron, which
# does not read .env; harmless when run by hand with the var already exported.
[ -f .env ] && { set -a; . ./.env; set +a; }
WEBHOOK_URL="${ALERT_WEBHOOK_URL:-}"

ts() { date -u '+%Y-%m-%d %H:%M:%S UTC'; }

alert() {
    [ -n "$WEBHOOK_URL" ] || return 0
    curl -fsS -m 10 -X POST -H 'Content-Type: application/json' \
         -d "{\"content\": \"$1\"}" "$WEBHOOK_URL" >/dev/null 2>&1 || true
}

run_step() {
    local label="$1" sql="$2" out
    if out="$(docker compose exec -T postgres psql -U flights -d flights \
                -v ON_ERROR_STOP=1 -At -c "$sql" 2>&1)"; then
        echo "$(ts)  ${label}: ${out}"
    else
        echo "$(ts)  ${label}: FAILED: ${out}"
        alert "mart build step '${label}' failed: ${out}"
        exit 1
    fi
}

run_step staging   "SELECT accepted, rejected FROM staging.ingest_snapshots();"
run_step positions "SELECT mart.load_fact_position_snapshot();"
run_step transits  "SELECT mart.load_fact_flight_transit();"
run_step coverage  "SELECT mart.load_fact_hourly_coverage();"
