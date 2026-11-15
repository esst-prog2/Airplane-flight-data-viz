#!/usr/bin/env bash
# Freshness watch, run by its own cron entry on the VPS, independent of the build chain
# so it still fires when the chain has failed or did not start. Reports how far the mart
# lags raw and alerts the webhook when the lag exceeds the threshold (default 3 hours).
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$REPO_DIR"

# Read ALERT_WEBHOOK_URL for cron, which does not inherit .env. Pull only that one
# key instead of shell-sourcing the whole file: a malformed .env line (a character
# the shell treats specially, e.g. an unquoted '<') once aborted this script before
# it could alert, so the freshness check that should have caught a frozen mart died
# on the same line. Reading one key with grep cannot execute anything.
WEBHOOK_URL="${ALERT_WEBHOOK_URL:-}"
if [ -z "$WEBHOOK_URL" ] && [ -f .env ]; then
    WEBHOOK_URL="$(grep -E '^[[:space:]]*ALERT_WEBHOOK_URL=' .env | tail -n1 | cut -d= -f2-)"
fi
THRESHOLD="${MART_FRESHNESS_THRESHOLD_MINUTES:-180}"

row="$(docker compose exec -T postgres psql -U flights -d flights -At -F '|' \
        -c "SELECT coalesce(lag_minutes::text, 'n/a'), is_stale FROM ops.check_freshness(${THRESHOLD});")"
lag="${row%%|*}"
stale="${row##*|}"

echo "$(date -u '+%Y-%m-%d %H:%M:%S UTC')  mart lag ${lag} min  stale=${stale}  threshold=${THRESHOLD}min"

if [ "$stale" = "t" ] && [ -n "$WEBHOOK_URL" ]; then
    curl -fsS -m 10 -X POST -H 'Content-Type: application/json' \
         -d "{\"content\": \"mart is stale: ${lag} min behind raw (threshold ${THRESHOLD} min)\"}" \
         "$WEBHOOK_URL" >/dev/null 2>&1 || true
fi
